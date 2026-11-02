"""Carga la venta del dia de **todas** las sucursales, en un comando sin argumentos.

Para que existe, si ya esta `clip_load.py`: `clip_load` carga **una** sucursal en
**un** rango que le dictan. Eso sirve a mano, pero un disparo programado no tiene
a nadie que le dicte el rango, y las dos decisiones que hay que tomar para
armarlo son justo las dos donde es facil equivocarse:

1. **Cual es "hoy".** El dia de operacion es UTC-6 (`business_day.BUSINESS_TZ`).
   El disparo de la tarde cae a las `01:45Z`, que en UTC ya es **el dia
   siguiente**: calcular "hoy" con `datetime.utcnow().date()` pediria a Clip un
   dia que apenas empieza y dejaria el corte de las 20:00 CDMX en cero. Aqui el
   dia sale de `business_date(now)`, igual que el campo con el que se guarda cada
   venta, asi que el rango pedido y el `business_date` escrito no pueden
   discrepar.

2. **Que sucursales son.** El mapeo sucursal-de-Clip -> cafeteria de la base ya
   vive en `branches_init.GROUP_BRANCHES`. Se lee de ahi en vez de repetirlo: el
   dia que se abra una tercera sucursal, el disparo diario la incluye sin que
   nadie se acuerde de este archivo. De ahi sale tambien la **marca** con la que
   se sella cada venta (`brand`), para que el corte por marca no dependa de que
   alguien la escriba bien a mano.

Una sucursal que falla **no** cancela a la otra. Son dos cuentas de Clip
distintas, con credenciales distintas, y la falla tipica (una credencial
revocada) es de una sola. Cada sucursal se reporta aparte y el codigo de salida
es 1 si alguna fallo, para que el disparo programado se note en lugar de
silenciarse.

    # ver que pasaria, sin escribir (default)
    python backend/clip_daily.py --db casa_dorelia

    # el disparo de la tarde (01:45Z = 19:45 CDMX): solo el dia en curso
    python backend/clip_daily.py --db casa_dorelia --commit

    # el disparo de la mañana (13:45Z = 07:45 CDMX): cierra ayer y siembra hoy
    python backend/clip_daily.py --db casa_dorelia --catch-up 1 --commit

    # recuperar un dia suelto que se quedo sin cargar
    python backend/clip_daily.py --db casa_dorelia --date 2026-09-29 --commit

Por que la mañana carga **dos** dias y no uno: el disparo de la tarde corre a las
19:45 locales, asi que la venta que entra despues de esa hora (lo que queda de
servicio hasta cerrar) no la vio nadie. Si la corrida de la mañana solo pidiera
"hoy", esas horas no se cargarian **nunca**. Con `--catch-up 1` la mañana vuelve
a pedir el dia anterior completo y lo cierra. Es gratis en riesgo: reimportar es
idempotente (la clave cuelga de `dedup_key`), asi que un dia ya cargado inserta
cero y no duplica nada.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from branches_init import GROUP_BRANCHES
from business_day import BUSINESS_TZ, business_date
from clip_api import ClipApiError, _parse_day
from clip_load import ClipLoadError, load_branch, open_sales_collection
from sales_import import SalesImportError


def target_business_date(now: Optional[datetime] = None, *, days_back: int = 0) -> str:
    """Dia de operacion a cargar (`YYYY-MM-DD`), en hora del negocio.

    `days_back` resta dias **de operacion**, no de 24 h UTC, porque es para
    recuperar "el dia anterior", no "hace 24 horas".
    """
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=BUSINESS_TZ)
    return business_date(moment.astimezone(BUSINESS_TZ) - timedelta(days=days_back))


def _count_in_db(sales: Any, *, cafeteria_id: str, day: str,
                 tenant_id: Optional[str] = None) -> Optional[int]:
    """Renglones que ya hay en la base para ese dia y esa cafeteria.

    Es la evidencia de cierre: distingue "la carga corrio y la sucursal no cobro
    con tarjeta" (cero) de "la carga no corrio" (la llave no aparece). Si la
    coleccion no sabe contar (un doble de prueba), devuelve `None` en vez de
    tronar: el conteo es evidencia, no parte de la carga.
    """
    counter = getattr(sales, "count_documents", None)
    if counter is None:
        return None
    query: Dict[str, Any] = {"cafeteria_id": cafeteria_id, "business_date": day}
    if tenant_id:
        query["tenant_id"] = tenant_id
    return counter(query)


def run_daily(sales: Any, *, day: str, commit: bool = False,
              branches: Sequence[Mapping[str, Any]] = GROUP_BRANCHES,
              tenant_id: Optional[str] = None,
              loader: Callable[..., Dict[str, Any]] = load_branch) -> Dict[str, Any]:
    """Carga `day` en cada sucursal activa. Aisla la falla de cada una."""
    start = _parse_day(day)
    end = _parse_day(day, end_of_day=True)

    results: List[Dict[str, Any]] = []
    for branch in branches:
        if not branch.get("is_active", True):
            continue
        clip_branch = branch["clip_branch"]
        cafeteria_id = branch["id"]
        brand = branch.get("brand")
        entry: Dict[str, Any] = {"branch": clip_branch, "cafeteria_id": cafeteria_id,
                                 "brand": brand}
        try:
            loaded = loader(
                sales,
                branch=clip_branch,
                start=start,
                end=end,
                cafeteria_id=cafeteria_id,
                brand=brand,
                tenant_id=tenant_id,
                created_by="clip_daily",
                commit=commit,
            )
        except (ClipLoadError, ClipApiError, SalesImportError) as exc:
            # El texto del error nunca trae la credencial (ver `ClipCredentials`).
            entry["ok"] = False
            entry["error"] = f"{type(exc).__name__}: {exc}"
        else:
            entry["ok"] = True
            entry.update({
                "inserted": loaded["inserted"],
                "to_insert": loaded["to_insert"],
                "skipped": loaded["skipped"],
                "skipped_reasons": loaded["skipped_reasons"],
                "gross_total": loaded["gross_total"],
            })
        entry["db_rows"] = _count_in_db(sales, cafeteria_id=cafeteria_id, day=day,
                                        tenant_id=tenant_id)
        results.append(entry)

    failed = [r["branch"] for r in results if not r["ok"]]
    return {
        "business_date": day,
        "committed": bool(commit),
        "branches": results,
        "failed_branches": failed,
        "ok": not failed,
        # El corte que lee esto siempre tiene que decirlo: la API de Clip no
        # entrega efectivo, asi que este total es piso, no la venta del dia.
        "includes_cash": False,
    }


def days_to_load(*, date: Optional[str] = None, catch_up: int = 0,
                 now: Optional[datetime] = None) -> List[str]:
    """Dias de operacion a cargar, del mas viejo al mas nuevo.

    `--date` manda y pide un dia solo. Si no, son `catch_up` dias previos mas el
    dia en curso, para que la corrida de la mañana cierre el dia anterior.
    """
    if date:
        return [date]
    if catch_up < 0:
        raise ValueError("--catch-up no puede ser negativo")
    return [target_business_date(now, days_back=back)
            for back in range(catch_up, -1, -1)]


def run_days(sales: Any, *, days: Sequence[str], **kwargs: Any) -> Dict[str, Any]:
    """`run_daily` sobre varios dias. Un dia que falla no detiene a los demas."""
    loaded = [run_daily(sales, day=day, **kwargs) for day in days]
    failed = sorted({f"{d['business_date']}:{b}" for d in loaded for b in d["failed_branches"]})
    return {
        "days": loaded,
        "failed": failed,
        "ok": not failed,
        "inserted_total": sum(b.get("inserted", 0) for d in loaded for b in d["branches"]),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="clip_daily",
        description="Carga la venta del dia de todas las sucursales. En seco por default.",
    )
    parser.add_argument("--date", default=None,
                        help="un dia de operacion concreto (default: hoy en hora del negocio)")
    parser.add_argument("--catch-up", type=int, default=0, metavar="N",
                        help="tambien recargar los N dias de operacion anteriores "
                             "(usar 1 en la corrida de la mañana; ignorado si hay --date)")
    parser.add_argument("--db", default=None, help="base destino (default: $DB_NAME)")
    parser.add_argument("--mongo-url", default=None, help="default: $MONGO_URL o localhost")
    parser.add_argument("--tenant", default=None, help="`tenant_id`, si la base es multi-empresa")
    parser.add_argument("--commit", action="store_true",
                        help="escribir de verdad; sin esto solo enseña el plan")

    args = parser.parse_args(argv)

    try:
        days = days_to_load(date=args.date, catch_up=args.catch_up)
        sales = open_sales_collection(args.mongo_url, args.db)
    except (ClipLoadError, ClipApiError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1

    result = run_days(sales, days=days, commit=args.commit, tenant_id=args.tenant)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not args.commit:
        print("\n(en seco: no se escribio nada. Agrega --commit para cargar)")
    return 0 if result["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
