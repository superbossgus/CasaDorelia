"""Saca de `sales` los cobros que Clip tiene como **cancelados** (BOS-119).

La API de Clip manda `status: ""` en un cobro cancelado, y `clip_import.classify_status("")`
devuelve `"paid"` — con razon para el export del panel, donde una columna de
estado ausente si significa cobrada, y al reves para la API. Resultado: una
cancelacion entraba como venta. Paso con $108.00 del 21/09 en Tecnoparque, que
Gustavo reconocio como "cancelacion de pago con tarjeta".

El cargador ya no las mete (`clip_api._status`), pero las que entraron antes
siguen sumando en el reporte: hay que sacarlas.

## Como decide

Le pregunta otra vez a Clip por el rango que la base tiene cargado y se queda
**solo** con los renglones que la API entrega como `?status=cancelled`. No
clasifica por su cuenta: usa el filtro de la propia API, que es la unica
autoridad sobre si un cobro se cobro.

Un renglon de la base que la API ya no entrega **no se toca**: la ausencia no es
una cancelacion.

## Borra, y por eso imprime lo que borra

Es el unico script de esta cadena que elimina documentos, porque un cobro
cancelado no es una venta "mal etiquetada": no es una venta. Antes de borrar
imprime folio, monto, dia y marca de cada uno, para que el renglon quede en el
comentario de la tarea y se pueda reconstruir desde Clip si hiciera falta.

En seco por default:

    python backend/purge_cancelled.py --db casa_dorelia
    python backend/purge_cancelled.py --db casa_dorelia --commit
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from branches_init import GROUP_BRANCHES
from business_day import BUSINESS_TZ
from clip_api import ClipApiError, fetch_rows, load_credentials
from clip_load import ClipLoadError, open_sales_collection
from sales_import import SOURCE_CLIP_API


def plan_purge(stored: Sequence[Mapping[str, Any]],
               cancelled_keys: Sequence[str]) -> List[Dict[str, Any]]:
    """Los documentos de la base que Clip tiene como cancelados."""
    wanted = set(cancelled_keys)
    return [
        {"_id": sale.get("_id"), "dedup_key": sale.get("dedup_key"),
         "receipt_no": sale.get("receipt_no"), "total": sale.get("total"),
         "business_date": sale.get("business_date"), "brand": sale.get("brand"),
         "payment_method": sale.get("payment_method")}
        for sale in stored if sale.get("dedup_key") in wanted
    ]


def purge_branch(sales: Any, *, branch: str, cafeteria_id: str,
                 commit: bool = False, fetch: Any = fetch_rows) -> Dict[str, Any]:
    stored = list(sales.find(
        {"source": SOURCE_CLIP_API, "clip_branch": branch},
        {"_id": 1, "dedup_key": 1, "receipt_no": 1, "total": 1,
         "business_date": 1, "brand": 1, "payment_method": 1},
    ))
    if not stored:
        return {"branch": branch, "cafeteria_id": cafeteria_id, "stored": 0,
                "cancelled_in_db": 0, "deleted": 0, "rows": [], "commit": commit}

    days = sorted({s["business_date"] for s in stored if s.get("business_date")})
    if not days:
        raise ClipLoadError(
            f"las ventas de {branch} no traen `business_date`: corre primero "
            "python backend/backfill_business_date.py"
        )

    start = datetime.fromisoformat(days[0]).replace(tzinfo=BUSINESS_TZ)
    end = datetime.fromisoformat(days[-1]).replace(tzinfo=BUSINESS_TZ) + timedelta(days=1)

    credentials = load_credentials(branch)
    # `status="cancelled"` lo decide Clip, no este script.
    cancelled = fetch(credentials, start, end, status="cancelled")
    keys = [f"clip:{row['transaction_id']}" for row in cancelled if row.get("transaction_id")]

    rows = plan_purge(stored, keys)

    deleted = 0
    if rows and commit:
        from pymongo import DeleteOne

        result = sales.bulk_write([DeleteOne({"_id": row["_id"]}) for row in rows],
                                  ordered=False)
        deleted = result.deleted_count

    return {
        "branch": branch,
        "cafeteria_id": cafeteria_id,
        "stored": len(stored),
        "days": [days[0], days[-1]],
        "cancelled_in_clip": len(keys),
        "cancelled_in_db": len(rows),
        "deleted": deleted,
        "gross_removed": round(sum(float(r.get("total") or 0.0) for r in rows), 2),
        "rows": [{k: v for k, v in row.items() if k != "_id"} for row in rows],
        "commit": commit,
    }


def purge_all(sales: Any, *, branches: Sequence[Mapping[str, Any]] = GROUP_BRANCHES,
              commit: bool = False, fetch: Any = fetch_rows) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    failed: Dict[str, str] = {}
    for spec in branches:
        branch = spec.get("clip_branch")
        if not branch:
            continue
        try:
            results.append(purge_branch(sales, branch=branch, cafeteria_id=spec["id"],
                                        commit=commit, fetch=fetch))
        except (ClipApiError, ClipLoadError) as exc:
            failed[branch] = str(exc)

    return {
        "ok": not failed,
        "commit": commit,
        "branches": results,
        "failed": failed,
        "cancelled_in_db_total": sum(r["cancelled_in_db"] for r in results),
        "deleted_total": sum(r["deleted"] for r in results),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="purge_cancelled",
        description="Saca de `sales` los cobros que Clip tiene como cancelados (BOS-119).",
    )
    parser.add_argument("--db", default=None, help="base (default: $DB_NAME)")
    parser.add_argument("--mongo-url", default=None, help="default: $MONGO_URL o localhost")
    parser.add_argument("--branch", default=None, help="solo esta sucursal de Clip")
    parser.add_argument("--commit", action="store_true",
                        help="borra; sin esto solo dice que borraria")
    args = parser.parse_args(argv)

    try:
        sales = open_sales_collection(args.mongo_url, args.db)
        branches = [b for b in GROUP_BRANCHES
                    if not args.branch or b.get("clip_branch") == args.branch]
        if args.branch and not branches:
            raise ClipLoadError(
                f"no hay sucursal con `clip_branch: {args.branch!r}` en branches_init"
            )
        summary = purge_all(sales, branches=branches, commit=args.commit)
    except (ClipApiError, ClipLoadError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["commit"] and summary["cancelled_in_db_total"]:
        print("\nEn seco: no se borro nada. Repite con --commit para aplicarlo.")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
