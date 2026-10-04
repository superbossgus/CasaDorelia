"""Re-etiqueta el metodo de pago de las ventas ya cargadas de Clip (BOS-119).

Hasta BOS-119 `clip_api._payment_method` devolvia `"tarjeta"` para **todo** lo
que no fuera debito o credito, porque terminaba en un `return "tarjeta"`. En esa
bolsa caen dos cosas que no son tarjeta bancaria:

- **vales** de despensa/restaurante (`OTHER` con emisor: PLUXEE MEXICO, EDENRED,
  TOKA, TODITO...), que en Tecnoparque son ~12% de los pesos de un año; y
- **cobros sin tarjeta** (`OTHER` con marca `XX`, `last4` `0000`), que la API no
  nombra y que podrian ser el efectivo registrado en la app.

Las ventas cargadas antes del arreglo quedaron con `payment_method: "tarjeta"`,
asi que **ninguna consulta las puede separar**. Esto las vuelve a etiquetar.

## Como decide, y por que vuelve a pedirle a Clip

No adivina desde `notes`: le pregunta otra vez a la API por el mismo rango y
pasa cada cobro por `clip_api.map_payment`, **la misma funcion** que usa la
carga diaria. Asi el renglon re-etiquetado queda identico al que insertaria una
carga nueva, y no hay una segunda tabla de reglas que pueda divergir de la
primera. De paso repone `notes` con el emisor del vale, que la version anterior
tiraba.

El empate es por `dedup_key` (`clip:<receipt_no>`), que es la llave con la que
se inserto. No se toca `dedup_key`, ni `id`, ni `total`, ni la fecha: **solo**
`payment_method` y `notes`, y solo donde cambian.

## Lo que no hace

- No inserta ni borra. Un cobro que esta en Clip y no en la base se **reporta**
  (`missing_in_db`) para que lo cargue `clip_daily.py`, que es quien sabe.
- No toca ventas de otro origen: la captura manual tiene el metodo que escribio
  una persona y ahi manda la persona.

Es idempotente: la segunda corrida no cambia nada (`updated: 0`).

    python backend/backfill_payment_method.py --db casa_dorelia --dry-run
    python backend/backfill_payment_method.py --db casa_dorelia --commit
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from branches_init import GROUP_BRANCHES
from business_day import BUSINESS_TZ
from clip_api import ClipApiError, fetch_rows, load_credentials
from clip_load import ClipLoadError, open_sales_collection
from sales_import import SOURCE_CLIP_API

# Solo campos de rotulo. La lista esta aqui y no inline para que se vea de un
# golpe que no incluye dinero ni fechas ni llaves.
MUTABLE_FIELDS = ("payment_method", "notes")


def plan_relabel(stored: Iterable[Mapping[str, Any]],
                 fresh: Mapping[str, Mapping[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Decide que re-etiquetar, sin tocar la base.

    `stored` son los documentos de `sales`; `fresh` es `{dedup_key: fila}` con
    lo que Clip entrega hoy, ya mapeado.

    Devuelve `{"to_update", "unchanged", "missing_in_api"}`. Un cobro que la
    base tiene y la API ya no entrega **no se toca**: puede ser una ventana que
    quedo fuera del rango pedido, y borrar o re-etiquetar a ciegas por eso seria
    perder un rotulo bueno.
    """
    to_update: List[Dict[str, Any]] = []
    unchanged: List[str] = []
    missing_in_api: List[str] = []

    for sale in stored:
        key = sale.get("dedup_key")
        row = fresh.get(key)
        if row is None:
            missing_in_api.append(str(key))
            continue

        changes = {
            field: row.get(field)
            for field in MUTABLE_FIELDS
            if (row.get(field) or None) != (sale.get(field) or None)
        }
        if changes:
            to_update.append({
                "_id": sale.get("_id"),
                "dedup_key": key,
                "from": {field: sale.get(field) for field in changes},
                "to": changes,
                "total": sale.get("total"),
            })
        else:
            unchanged.append(str(key))

    return {"to_update": to_update, "unchanged": unchanged,
            "missing_in_api": missing_in_api}


def _day_bounds(days: Sequence[str]) -> tuple:
    """Rango UTC que cubre por completo esos dias de operacion (UTC-6)."""
    first = datetime.fromisoformat(min(days)).replace(tzinfo=BUSINESS_TZ)
    last = datetime.fromisoformat(max(days)).replace(tzinfo=BUSINESS_TZ)
    return first, last + timedelta(days=1)


def relabel_branch(sales: Any, *, branch: str, cafeteria_id: str,
                   commit: bool = False,
                   fetch: Any = fetch_rows) -> Dict[str, Any]:
    """Re-etiqueta una sucursal. `commit=False` dice que haria y no escribe."""
    stored = list(sales.find(
        {"source": SOURCE_CLIP_API, "clip_branch": branch},
        {"_id": 1, "dedup_key": 1, "payment_method": 1, "notes": 1,
         "total": 1, "business_date": 1},
    ))
    if not stored:
        return {"branch": branch, "cafeteria_id": cafeteria_id, "stored": 0,
                "to_update": 0, "updated": 0, "by_method": {}, "commit": commit}

    days = sorted({s["business_date"] for s in stored if s.get("business_date")})
    if not days:
        raise ClipLoadError(
            f"las ventas de {branch} no traen `business_date`: corre primero "
            "python backend/backfill_business_date.py"
        )

    start, end = _day_bounds(days)
    credentials = load_credentials(branch)
    rows = fetch(credentials, start, end)
    fresh = {f"clip:{row['transaction_id']}": row for row in rows if row.get("transaction_id")}

    plan = plan_relabel(stored, fresh)

    updated = 0
    if plan["to_update"] and commit:
        from pymongo import UpdateOne

        result = sales.bulk_write(
            [UpdateOne({"_id": row["_id"]}, {"$set": row["to"]}) for row in plan["to_update"]],
            ordered=False,
        )
        updated = result.modified_count

    # Dos cosas muy distintas viajan en el mismo `to_update`, y mezclarlas
    # esconde la que importa: un cambio de **metodo** mueve dinero de un cajon a
    # otro en el reporte, y un cambio de **notas** solo repone el emisor (el
    # banco de la tarjeta, o el vale) que la version anterior tiraba. El resumen
    # los cuenta aparte para que "118 renglones tocados" no se lea como "118
    # renglones mal cobrados".
    by_method: Dict[str, Dict[str, Any]] = {}
    notes_only = 0
    for row in plan["to_update"]:
        method = row["to"].get("payment_method")
        if not method:
            notes_only += 1
            continue
        bucket = by_method.setdefault(f"{row['from'].get('payment_method')} -> {method}",
                                      {"rows": 0, "gross": 0.0})
        bucket["rows"] += 1
        bucket["gross"] = round(bucket["gross"] + float(row.get("total") or 0.0), 2)

    return {
        "branch": branch,
        "cafeteria_id": cafeteria_id,
        "stored": len(stored),
        "days": [days[0], days[-1]],
        "api_rows": len(rows),
        "to_update": len(plan["to_update"]),
        "method_changed": len(plan["to_update"]) - notes_only,
        "notes_only": notes_only,
        "updated": updated,
        "unchanged": len(plan["unchanged"]),
        "missing_in_api": len(plan["missing_in_api"]),
        "missing_in_db": sorted(set(fresh) - {s.get("dedup_key") for s in stored}),
        "by_method": by_method,
        "commit": commit,
    }


def relabel_all(sales: Any, *, branches: Sequence[Mapping[str, Any]] = GROUP_BRANCHES,
                commit: bool = False, fetch: Any = fetch_rows) -> Dict[str, Any]:
    """Todas las sucursales del grupo. Una credencial muerta no detiene a la otra."""
    results: List[Dict[str, Any]] = []
    failed: Dict[str, str] = {}
    for spec in branches:
        branch = spec.get("clip_branch")
        if not branch:
            continue
        try:
            results.append(relabel_branch(sales, branch=branch, cafeteria_id=spec["id"],
                                          commit=commit, fetch=fetch))
        except (ClipApiError, ClipLoadError) as exc:
            failed[branch] = str(exc)

    return {
        "ok": not failed,
        "commit": commit,
        "branches": results,
        "failed": failed,
        "to_update_total": sum(r["to_update"] for r in results),
        "method_changed_total": sum(r.get("method_changed", 0) for r in results),
        "updated_total": sum(r["updated"] for r in results),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="backfill_payment_method",
        description="Re-etiqueta metodo de pago de ventas de Clip ya cargadas (BOS-119).",
    )
    parser.add_argument("--db", default=None, help="base (default: $DB_NAME)")
    parser.add_argument("--mongo-url", default=None, help="default: $MONGO_URL o localhost")
    parser.add_argument("--branch", default=None,
                        help="solo esta sucursal de Clip (default: todas)")
    parser.add_argument("--commit", action="store_true",
                        help="escribe; sin esto solo dice que cambiaria")
    args = parser.parse_args(argv)

    try:
        sales = open_sales_collection(args.mongo_url, args.db)
        branches = [b for b in GROUP_BRANCHES
                    if not args.branch or b.get("clip_branch") == args.branch]
        if args.branch and not branches:
            raise ClipLoadError(
                f"no hay sucursal con `clip_branch: {args.branch!r}` en branches_init"
            )
        summary = relabel_all(sales, branches=branches, commit=args.commit)
    except (ClipApiError, ClipLoadError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["commit"] and summary["to_update_total"]:
        print("\nEn seco: no se escribio nada. Repite con --commit para aplicarlo.")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
