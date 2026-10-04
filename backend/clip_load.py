"""Carga ventas de Clip a Mongo en un comando, idempotente y en seco por default.

Cierra la cadena que ya existia por partes: `clip_api` lee de Clip,
`sales_import.plan_import` decide que se inserta y esto lo escribe.

    # ver que pasaria, sin escribir (default)
    python backend/clip_load.py --branch tecnoparque --from 2026-09-21 --to 2026-10-01 \
        --cafeteria c-tecno

    # escribir de verdad
    python backend/clip_load.py --branch tecnoparque --from 2026-09-21 --to 2026-10-01 \
        --cafeteria c-tecno --commit

Por que un script y no `POST /api/sales/import`: el endpoint hace exactamente lo
mismo y es el que usara la pantalla, pero exige el server arriba y un token de
admin. Para la carga historica y para el cron diario conviene un comando sin
esas dos piezas. La logica de decision es la MISMA funcion (`plan_import`), asi
que los dos caminos no pueden divergir en como calculan IVA, fecha o dedup.

Dos cosas que este script NO hace, a proposito:
  - No mueve inventario. La venta ya salio por el POS de Clip; descontarla otra
    vez la contaria doble (defecto #3 del analisis de BOS-71).
  - No trae efectivo. La API de Clip entrega lo que cobro la terminal (tarjeta y
    vales); el efectivo que la app de Clip registra aparte no viaja por ahi
    (medido en BOS-119), asi que el total cargado siempre es menor a la venta
    real de la sucursal.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from branches_init import brand_for
from clip_api import ClipApiError, _parse_day, fetch_rows, load_credentials, summarize_corte
from sales_import import SOURCE_CLIP_API, SalesImportError, plan_import

DEFAULT_MONGO_URL = "mongodb://127.0.0.1:27017"


class ClipLoadError(RuntimeError):
    """Algo impide cargar. Siempre dice que falta y como arreglarlo."""


def _existing_keys(sales: Any, keys: Sequence[str], tenant_filter: Mapping[str, Any]) -> set:
    """Que claves de este lote ya estan en la base. Solo consulta las del lote."""
    if not keys:
        return set()
    cursor = sales.find({**tenant_filter, "dedup_key": {"$in": list(keys)}},
                        {"_id": 0, "dedup_key": 1})
    return {doc["dedup_key"] for doc in cursor}


def plan_against_db(rows: Iterable[Mapping[str, Any]], sales: Any, *, cafeteria_id: str,
                    tenant_id: Optional[str] = None, brand: Optional[str] = None,
                    created_by: Optional[str] = None):
    """`plan_import` consultando la base dos veces, igual que el endpoint.

    La segunda pasada no es redundante: las filas que llegan sin `dedup_key`
    explicito reciben una clave derivada dentro de `plan_import`, y esa clave
    tambien puede existir ya en la base. Sin la segunda consulta, reimportar un
    rango duplicaria justo esas.
    """
    rows = list(rows)
    tenant_filter = {"tenant_id": tenant_id} if tenant_id else {}

    declared = [r["dedup_key"] for r in rows if r.get("dedup_key")]
    already = _existing_keys(sales, declared, tenant_filter)

    plan = plan_import(rows, cafeteria_id=cafeteria_id, source=SOURCE_CLIP_API,
                       existing_keys=already, tenant_id=tenant_id, brand=brand,
                       created_by=created_by)

    derived = [d["dedup_key"] for d in plan.documents if d["dedup_key"] not in already]
    duplicated = _existing_keys(sales, derived, tenant_filter)
    if duplicated:
        kept = []
        for doc in plan.documents:
            if doc["dedup_key"] in duplicated:
                plan.skipped.append({
                    "row": None,
                    "business_date": doc["business_date"],
                    "dedup_key": doc["dedup_key"],
                    "reason": "ya_importada",
                    "gross_amount": doc["total"],
                })
            else:
                kept.append(doc)
        plan.documents = kept

    return plan


def load_branch(sales: Any, *, branch: str, start: datetime, end: datetime,
                cafeteria_id: str, commit: bool = False,
                tenant_id: Optional[str] = None,
                brand: Optional[str] = None,
                created_by: Optional[str] = None,
                rows: Optional[Sequence[Mapping[str, Any]]] = None,
                **fetch_kwargs: Any) -> Dict[str, Any]:
    """Baja el rango de Clip, decide que se inserta y solo escribe con `commit`.

    `rows` permite pasar las filas ya bajadas (o de prueba) y saltarse la red.

    `brand` no hace falta pasarlo: si no viene, sale del catalogo por
    `cafeteria_id` (`branches_init.brand_for`). Asi ninguna via de carga puede
    dejar la venta sin marca por olvido, que es como se produjo BOS-101.
    """
    if rows is None:
        rows = fetch_rows(load_credentials(branch), start, end, **fetch_kwargs)

    if brand is None:
        brand = brand_for(cafeteria_id)

    plan = plan_against_db(rows, sales, cafeteria_id=cafeteria_id,
                           tenant_id=tenant_id, brand=brand, created_by=created_by)

    inserted = 0
    if commit and plan.documents:
        sales.insert_many(list(plan.documents))
        inserted = len(plan.documents)

    corte = summarize_corte(rows, branch=branch)
    return {
        "branch": branch,
        "cafeteria_id": cafeteria_id,
        "brand": brand,
        "committed": bool(commit),
        "inserted": inserted,
        "to_insert": len(plan.documents),
        "skipped": len(plan.skipped),
        "skipped_reasons": _count_reasons(plan.skipped),
        "rejected": plan.rejected,
        "gross_total": plan.gross_total,
        # El corte sale de las filas crudas, asi que no cambia cuando una
        # reimportacion salta todo: es la venta del periodo, no lo insertado hoy.
        "by_business_date": corte["by_business_date"],
        "cash_coverage": corte["cash_coverage"],
    }


def _count_reasons(skipped: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for item in skipped:
        reason = item.get("reason", "?")
        out[reason] = out.get(reason, 0) + 1
    return out


def open_sales_collection(mongo_url: Optional[str] = None, db_name: Optional[str] = None):
    """Coleccion `sales`, con un mensaje util cuando falta la configuracion."""
    try:
        from pymongo import MongoClient
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise ClipLoadError(
            "falta el driver de Mongo: pip install pymongo"
        ) from exc

    url = mongo_url or os.environ.get("MONGO_URL") or DEFAULT_MONGO_URL
    name = db_name or os.environ.get("DB_NAME")
    if not name:
        raise ClipLoadError(
            "falta `DB_NAME` (o --db): no se adivina a que base se cargan las ventas"
        )
    # 45 s, no 5: el servicio MongoDB de Windows ahora reintenta a los 5, 10 y 30
    # segundos cuando se cae (BOS-140). Con 5 s de espera, una carga que dispara
    # justo durante ese reinicio fallaba aunque la base volviera sola dos
    # segundos despues. La espera cubre la escalera completa de reintentos; en
    # una base de verdad muerta solo retrasa el error, que a un disparo
    # programado no le cuesta nada.
    client = MongoClient(url, serverSelectionTimeoutMS=45_000)
    try:
        client.admin.command("ping")  # falla aqui, no a medio insert
    except Exception as exc:  # pragma: no cover - depende del entorno
        # Sin esto el error de pymongo sube crudo: `clip_daily.main` solo atrapa
        # `ClipLoadError`, asi que un mongod apagado terminaba en traceback y el
        # corte se quedaba sin cifra sin que nadie supiera por que.
        raise ClipLoadError(
            f"el mongod de {url} no responde ({type(exc).__name__}). "
            "Si es el local de Windows: Start-Service MongoDB"
        ) from exc
    return client[name].sales


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="clip_load",
        description="Carga ventas de Clip a Mongo. En seco por default.",
    )
    parser.add_argument("--branch", required=True, help="sucursal en Clip (sji | tecnoparque)")
    parser.add_argument("--from", dest="start", required=True)
    parser.add_argument("--to", dest="end", required=True)
    parser.add_argument("--cafeteria", required=True, help="`id` de la cafeteria en la base")
    parser.add_argument("--tenant", default=None, help="`tenant_id`, si la base es multi-empresa")
    parser.add_argument("--db", default=None, help="base destino (default: $DB_NAME)")
    parser.add_argument("--mongo-url", default=None, help="default: $MONGO_URL o localhost")
    parser.add_argument("--commit", action="store_true",
                        help="escribir de verdad; sin esto solo enseña el plan")

    args = parser.parse_args(argv)

    try:
        sales = open_sales_collection(args.mongo_url, args.db)
        result = load_branch(
            sales,
            branch=args.branch,
            start=_parse_day(args.start),
            end=_parse_day(args.end, end_of_day=True),
            cafeteria_id=args.cafeteria,
            tenant_id=args.tenant,
            created_by="clip_load",
            commit=args.commit,
        )
    except (ClipLoadError, ClipApiError, SalesImportError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not args.commit:
        print("\n(en seco: no se escribio nada. Agrega --commit para cargar)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
