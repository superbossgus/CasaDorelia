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
            # `None`, no 0: no se sabe cuantos cobros habia, no es que hubiera
            # cero. Un 0 aqui se leeria como "Clip contesto vacio".
            entry["seen"] = None
        else:
            entry["ok"] = True
            entry.update({
                # Cobros que contesto Clip para esta celda sucursal x dia. Lo
                # que hace legible un cero: con `seen: 0` y `ok: true`, la
                # consulta se hizo y no habia cobros.
                "seen": loaded.get("rows_seen",
                                   loaded["to_insert"] + loaded["skipped"]),
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
    answered = [r for r in results if r["ok"]]
    return {
        "business_date": day,
        "committed": bool(commit),
        "branches": results,
        "failed_branches": failed,
        "ok": not failed,
        # Cobros vistos del dia, sumando solo las sucursales que contestaron.
        # Se suma aparte de `inserted` a proposito: un dia reimportado inserta
        # cero y aun asi prueba que Clip contesto con contenido.
        "seen_total": sum(r["seen"] for r in answered),
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

    cells = [b for d in loaded for b in d["branches"]]
    answered = [b for b in cells if b.get("ok")]
    seen_total = sum(b.get("seen") or 0 for b in answered)

    reasons: Dict[str, int] = {}
    for cell in answered:
        for reason, count in (cell.get("skipped_reasons") or {}).items():
            reasons[reason] = reasons.get(reason, 0) + count

    return {
        "days": loaded,
        "days_requested": list(days),
        "failed": failed,
        "ok": not failed,
        "inserted_total": sum(b.get("inserted", 0) for d in loaded for b in d["branches"]),
        # Cobros que contesto Clip en toda la corrida, insertados o no.
        "seen_total": seen_total,
        "skipped_reasons_total": reasons,
        # El caso que el comentario tiene que decir con palabras: todas las
        # celdas sucursal x dia contestaron y ninguna traia un solo cobro. Sin
        # esto la corrida es indistinguible de una que nunca pregunto, porque
        # `inserted_total: 0` sale igual en ambas (BOS-232).
        #
        # Exige `not failed` a proposito: con una credencial caida el cero ya no
        # es un cero medido de toda la corrida, y `failed` es el que lo dice.
        "clip_answered_empty": bool(answered) and not failed and seen_total == 0,
    }


def _format_reasons(reasons: Optional[Mapping[str, int]]) -> str:
    if not reasons:
        return "—"
    return ", ".join(f"{reason} {count}" for reason, count in sorted(reasons.items()))


def render_comment(result: Mapping[str, Any]) -> str:
    """Comentario listo para pegar en la tarea, una fila por sucursal x dia.

    Existe porque el dato se perdia en el ultimo tramo: el JSON ya traia los
    cobros vistos por celda y el comentario de cierre publicaba solo lo
    insertado, asi que una corrida que pregunto y no encontro nada se leia
    igual que una que nunca corrio (BOS-232). Rendirlo aqui hace que el
    comentario correcto sea el camino facil: se copia, no se deriva.
    """
    dias = ", ".join(result.get("days_requested") or [])
    lineas = [
        f"**Carga de Clip** — dias pedidos: {dias or '—'} · "
        f"escribio: {'si' if any(d.get('committed') for d in result['days']) else 'no (en seco)'}",
        "",
        "| dia | sucursal | cobros vistos | insertados | en base | bruto nuevo | saltados |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for day in result["days"]:
        for cell in day["branches"]:
            quien = f"{cell['branch']} (`{cell['cafeteria_id']}`)"
            if not cell.get("ok"):
                lineas.append(
                    f"| {day['business_date']} | {quien} | **no contesto** | — | "
                    f"{cell.get('db_rows')} | — | — |"
                )
                continue
            lineas.append(
                f"| {day['business_date']} | {quien} | **{cell['seen']}** | "
                f"{cell['inserted']} | {cell.get('db_rows')} | "
                f"${cell['gross_total']:,.2f} | {_format_reasons(cell['skipped_reasons'])} |"
            )

    lineas += [
        "",
        f"**Cobros vistos en toda la corrida: {result['seen_total']}** · "
        f"insertados: {result['inserted_total']} · "
        f"saltados por motivo: {_format_reasons(result.get('skipped_reasons_total'))}",
        "",
        "*Cobros vistos* = renglones que devolvio la API de Clip para esa celda, "
        "insertados o no. Un **0** con la celda contestada quiere decir **Clip "
        "contesto y no habia cobros**, que no es lo mismo que no haber "
        "preguntado: `insertados`, `en base` y `max(imported_at)` dan cero en los "
        "dos casos.",
        "",
        "*Bruto nuevo* = solo lo que esta corrida insertaria. Un dia ya cargado "
        "da **$0.00** aunque tenga cobros vistos; la venta del dia se lee de la "
        "base (`en base`), no de esta columna.",
    ]

    if result.get("clip_answered_empty"):
        lineas += [
            "",
            f"⚠️ **Esta corrida no obtuvo ni un renglon de ninguno de los dias "
            f"pedidos** ({dias}). Las {len([b for d in result['days'] for b in d['branches']])} "
            "celdas sucursal x dia contestaron y todas vinieron vacias. No hay "
            "control positivo de que la API traiga contenido en esta corrida: la "
            "unica evidencia de que la consulta se hizo es este comentario.",
        ]
    if result.get("failed"):
        lineas += [
            "",
            "**Celdas que no contestaron** (una credencial muerta no detiene a la otra):",
        ]
        for day in result["days"]:
            for cell in day["branches"]:
                if not cell.get("ok"):
                    lineas.append(
                        f"- `{day['business_date']}:{cell['branch']}` — {cell['error']}"
                    )

    lineas += [
        "",
        "El efectivo **no** viene por la API de Clip: el total cargado es piso, "
        "no la venta del dia.",
    ]
    return "\n".join(lineas)


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
    # Despues del JSON, no antes: el JSON es lo que decide si la cifra del dia
    # es confiable, y esto es el comentario de cierre ya armado para pegarlo.
    print("\n--- comentario de cierre (pegar tal cual) ---\n")
    print(render_comment(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
