"""Carga historica de Clip mes por mes, con los huecos rotulados.

`clip_load` carga un rango. Esto carga un año: parte el rango en meses de
operacion, carga cada uno por separado y entrega el corte de cada mes antes de
pasar al siguiente. La diferencia no es comodidad:

  - **Un error de rango se ve.** Son ~1,800 renglones de dinero; en un solo JSON
    de un año nadie nota que falta una semana. Mes por mes, el renglon vacio
    salta.
  - **Un `400` de Clip no se lleva el año entero.** La ventana
    2026-02-14..2026-03-15 la API la contesta `400 payclip.bad.request` (medido
    en BOS-119). Aqui ese mes se **parte a la mitad** y se vuelve a pedir, hasta
    llegar al dia; solo los dias que sigan fallando quedan fuera, y quedan
    **rotulados** en `gaps`.
  - **Un hueco sin rotular miente.** Un mes faltante en una serie anual se lee
    como una caida de ventas, no como un dato que no llego. Por eso `gaps` es
    parte del resultado y no un comentario en el log: quien dibuje la serie
    tiene con que marcar la banda.

Idempotente, porque `clip_load.load_branch` lo es (`dedup_key`): volver a correr
un mes ya cargado da `inserted: 0`. En seco por default.

    python backend/clip_backfill.py --db casa_dorelia \
        --from 2025-10-21 --to 2026-10-04 \
        --branch tecnoparque:c-tecno --branch sji:c-sji

    # ... y con --commit escribe.

La marca no se pasa: la sella `clip_load` desde el catalogo por `cafeteria_id`,
asi que una carga de un año no puede dejar dinero sin marca por olvido.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clip_api import ClipApiError, ClipAuthError, _parse_day, fetch_rows, load_credentials
from clip_load import ClipLoadError, load_branch, open_sales_collection
from sales_import import SalesImportError

# `payclip.bad.request` sobre una ventana que la API deberia aceptar: no es un
# error de nuestro lado, se arregla pidiendo menos dias. Un 401/403 no: ese se
# propaga, porque partir el rango solo multiplicaria el rechazo.
SPLITTABLE_STATUSES = (400, 404, 422, 500, 502, 503, 504)


class BranchSpec:
    """`sucursal-en-clip:cafeteria-en-la-base`, como lo pide --branch."""

    def __init__(self, branch: str, cafeteria_id: str) -> None:
        self.branch = branch
        self.cafeteria_id = cafeteria_id

    @classmethod
    def parse(cls, raw: str) -> "BranchSpec":
        if raw.count(":") != 1:
            raise ClipLoadError(
                f"--branch invalido: {raw!r}. Se espera `sucursal:cafeteria`, "
                "por ejemplo tecnoparque:c-tecno"
            )
        branch, cafeteria = (part.strip() for part in raw.split(":"))
        if not branch or not cafeteria:
            raise ClipLoadError(
                f"--branch invalido: {raw!r}. Ni la sucursal ni la cafeteria pueden ir vacias"
            )
        return cls(branch, cafeteria)

    def __repr__(self) -> str:  # pragma: no cover - solo diagnostico
        return f"BranchSpec({self.branch!r}, {self.cafeteria_id!r})"


def month_chunks(start: date, end: date) -> List[Tuple[date, date]]:
    """`start`..`end` partido en meses de calendario, inclusive en los dos extremos.

    El primer y el ultimo trozo quedan recortados al rango pedido, asi que
    `2025-10-21..2026-10-04` abre con 21..31 de octubre y cierra con 01..04 de
    octubre: ningun dia de mas, que en una carga de dinero importa mas que la
    simetria de los trozos.
    """
    if end < start:
        raise ClipLoadError(f"el rango va al reves: --from {start} no es anterior a --to {end}")

    chunks: List[Tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        if cursor.month == 12:
            next_month = date(cursor.year + 1, 1, 1)
        else:
            next_month = date(cursor.year, cursor.month + 1, 1)
        stop = min(next_month - timedelta(days=1), end)
        chunks.append((cursor, stop))
        cursor = stop + timedelta(days=1)
    return chunks


def _halve(start: date, end: date) -> Tuple[Tuple[date, date], Tuple[date, date]]:
    span = (end - start).days
    middle = start + timedelta(days=span // 2)
    return (start, middle), (middle + timedelta(days=1), end)


def fetch_rows_splitting(credentials: Any, start: date, end: date, *,
                         fetch: Callable[..., List[Dict[str, Any]]] = fetch_rows,
                         **fetch_kwargs: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """Las filas del rango, bisecando los subrangos que Clip rechaza.

    Devuelve `(filas, huecos)`. Un hueco es un dia que siguio fallando ya solo,
    con el motivo que dio la API: es lo unico que no se puede recuperar pidiendo
    menos, y es justo lo que hay que rotular en la serie.
    """
    try:
        rows = fetch(
            credentials,
            _parse_day(start.isoformat()),
            _parse_day(end.isoformat(), end_of_day=True),
            **fetch_kwargs,
        )
        return rows, []
    except ClipAuthError:
        # Partir no arregla una credencial rechazada, solo la pide 30 veces.
        raise
    except ClipApiError as exc:
        status = getattr(exc, "status", None)
        if status is not None and status not in SPLITTABLE_STATUSES:
            raise
        if start == end:
            return [], [{
                "from": start.isoformat(),
                "to": end.isoformat(),
                "reason": str(exc),
                "status": status,
            }]

    rows: List[Dict[str, Any]] = []
    gaps: List[Dict[str, str]] = []
    for half_start, half_end in _halve(start, end):
        half_rows, half_gaps = fetch_rows_splitting(
            credentials, half_start, half_end, fetch=fetch, **fetch_kwargs
        )
        rows.extend(half_rows)
        gaps.extend(half_gaps)
    return rows, _merge_gaps(gaps)


def _merge_gaps(gaps: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Dias contiguos que fallaron por lo mismo, en un solo renglon.

    Un hueco de un mes son 30 renglones identicos si no se juntan, y entonces el
    rotulo deja de leerse de un golpe.
    """
    ordered = sorted(gaps, key=lambda g: g["from"])
    merged: List[Dict[str, Any]] = []
    for gap in ordered:
        previous = merged[-1] if merged else None
        contiguous = (
            previous is not None
            and previous["reason"] == gap["reason"]
            and date.fromisoformat(previous["to"]) + timedelta(days=1) == date.fromisoformat(gap["from"])
        )
        if contiguous:
            previous["to"] = gap["to"]
            previous["days"] = (
                date.fromisoformat(previous["to"]) - date.fromisoformat(previous["from"])
            ).days + 1
        else:
            entry = dict(gap)
            entry["days"] = (
                date.fromisoformat(entry["to"]) - date.fromisoformat(entry["from"])
            ).days + 1
            merged.append(entry)
    return merged


def backfill(sales: Any, *, branches: Sequence[BranchSpec], start: date, end: date,
             commit: bool = False, tenant_id: Optional[str] = None,
             created_by: str = "clip_backfill",
             fetch: Callable[..., List[Dict[str, Any]]] = fetch_rows,
             credentials_for: Callable[[str], Any] = load_credentials,
             on_month: Optional[Callable[[Dict[str, Any]], None]] = None,
             **fetch_kwargs: Any) -> Dict[str, Any]:
    """Carga cada mes de cada sucursal y acumula el corte y los huecos.

    `on_month` se llama con el resultado de cada mes en cuanto se cierra, para
    que una corrida larga vaya dejando rastro en vez de contestar al final.
    """
    months = month_chunks(start, end)
    results: List[Dict[str, Any]] = []
    gaps: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for spec in branches:
        credentials = credentials_for(spec.branch)
        for month_start, month_end in months:
            label = month_start.strftime("%Y-%m")
            try:
                rows, month_gaps = fetch_rows_splitting(
                    credentials, month_start, month_end, fetch=fetch, **fetch_kwargs
                )
            except (ClipApiError, SalesImportError) as exc:
                errors.append({
                    "branch": spec.branch, "month": label,
                    "from": month_start.isoformat(), "to": month_end.isoformat(),
                    "error": str(exc),
                })
                continue

            loaded = load_branch(
                sales,
                branch=spec.branch,
                start=_parse_day(month_start.isoformat()),
                end=_parse_day(month_end.isoformat(), end_of_day=True),
                cafeteria_id=spec.cafeteria_id,
                tenant_id=tenant_id,
                created_by=created_by,
                commit=commit,
                rows=rows,
            )

            month_result = {
                "branch": spec.branch,
                "cafeteria_id": spec.cafeteria_id,
                "brand": loaded["brand"],
                "month": label,
                "from": month_start.isoformat(),
                "to": month_end.isoformat(),
                "api_rows": len(rows),
                "inserted": loaded["inserted"],
                "to_insert": loaded["to_insert"],
                "skipped": loaded["skipped"],
                "skipped_reasons": loaded["skipped_reasons"],
                # La lista completa, no el conteo: una fila rechazada es dinero
                # que no entro, y para decidir si importa hace falta el motivo.
                "rejected": loaded["rejected"],
                # Dos totales distintos a proposito. `gross_total` es lo que
                # entraria ahora; `corte_gross` es la venta del periodo salga de
                # donde salga, y es el que tiene que cuadrar contra
                # `clip_api corte`. Reimportar un mes ya cargado deja el primero
                # en cero y el segundo intacto: confundirlos hace leer un mes
                # bueno como un mes vacio.
                "gross_total": loaded["gross_total"],
                "corte_gross": round(sum(d["gross"] for d in loaded["by_business_date"]), 2),
                "days_with_sales": len(loaded["by_business_date"]),
                "gaps": month_gaps,
            }
            results.append(month_result)
            for gap in month_gaps:
                gaps.append({**gap, "branch": spec.branch, "month": label})
            if on_month is not None:
                on_month(month_result)

    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "committed": bool(commit),
        "months": results,
        "by_brand": _totals_by_brand(results),
        # Rotulados a proposito: sin esta lista, un mes que la API no entrego se
        # lee en el tablero como un mes sin ventas.
        "gaps": _merge_gaps_by_branch(gaps),
        "errors": errors,
        "totals": {
            "api_rows": sum(r["api_rows"] for r in results),
            "inserted": sum(r["inserted"] for r in results),
            "to_insert": sum(r["to_insert"] for r in results),
            "skipped": sum(r["skipped"] for r in results),
            "rejected": sum(len(r["rejected"]) for r in results),
            "gross_total": round(sum(r["gross_total"] for r in results), 2),
            "corte_gross": round(sum(r["corte_gross"] for r in results), 2),
        },
    }


def _merge_gaps_by_branch(gaps: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    by_branch: Dict[str, List[Mapping[str, Any]]] = {}
    for gap in gaps:
        by_branch.setdefault(gap["branch"], []).append(gap)
    out: List[Dict[str, Any]] = []
    for branch in sorted(by_branch):
        for merged in _merge_gaps(by_branch[branch]):
            out.append({**merged, "branch": branch})
    return out


def _totals_by_brand(results: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Total por marca. Nunca un consolidado: son dos vehiculos con socios distintos."""
    by_brand: Dict[str, Dict[str, Any]] = {}
    for row in results:
        entry = by_brand.setdefault(row["brand"], {
            "brand": row["brand"], "api_rows": 0, "inserted": 0, "to_insert": 0,
            "gross_total": 0.0, "corte_gross": 0.0,
        })
        entry["api_rows"] += row["api_rows"]
        entry["inserted"] += row["inserted"]
        entry["to_insert"] += row["to_insert"]
        entry["gross_total"] = round(entry["gross_total"] + row["gross_total"], 2)
        entry["corte_gross"] = round(entry["corte_gross"] + row["corte_gross"], 2)
    return [by_brand[brand] for brand in sorted(by_brand)]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="clip_backfill",
        description="Carga historica de Clip mes por mes. En seco por default.",
    )
    parser.add_argument("--branch", action="append", required=True, dest="branches",
                        metavar="SUCURSAL:CAFETERIA",
                        help="repetible: tecnoparque:c-tecno sji:c-sji")
    parser.add_argument("--from", dest="start", required=True)
    parser.add_argument("--to", dest="end", required=True)
    parser.add_argument("--tenant", default=None)
    parser.add_argument("--db", default=None, help="base destino (default: $DB_NAME)")
    parser.add_argument("--mongo-url", default=None)
    parser.add_argument("--commit", action="store_true",
                        help="escribir de verdad; sin esto solo enseña el plan")
    parser.add_argument("--progress", action="store_true",
                        help="imprimir un renglon por mes a stderr mientras carga")
    parser.add_argument("--json-out", default=None, metavar="RUTA",
                        help="guardar el resultado en un archivo JSON limpio (sin el aviso final)")

    args = parser.parse_args(argv)

    def progress(month: Dict[str, Any]) -> None:
        # `to_insert`, no `inserted`: en seco lo insertado es siempre 0 y el
        # renglon de avance se leeria como que el mes no trae nada.
        print(
            f"  {month['branch']:12s} {month['month']}  "
            f"api={month['api_rows']:5d} nuevas={month['to_insert']:5d} "
            f"saltadas={month['skipped']:5d} corte={month['corte_gross']:12,.2f}"
            + (f"  HUECOS={len(month['gaps'])}" if month["gaps"] else ""),
            file=sys.stderr, flush=True,
        )

    try:
        specs = [BranchSpec.parse(raw) for raw in args.branches]
        sales = open_sales_collection(args.mongo_url, args.db)
        result = backfill(
            sales,
            branches=specs,
            start=datetime.fromisoformat(args.start).date(),
            end=datetime.fromisoformat(args.end).date(),
            tenant_id=args.tenant,
            commit=args.commit,
            on_month=progress if args.progress else None,
        )
    except (ClipLoadError, ClipApiError, SalesImportError) as exc:
        print(f"ERROR: {exc}")
        return 1
    except ValueError as exc:
        print(f"ERROR: fecha invalida ({exc})")
        return 1

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, ensure_ascii=False)
        print(f"resultado en {args.json_out}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    if not args.commit:
        print("\n(en seco: no se escribio nada. Agrega --commit para cargar)")
    if result["gaps"]:
        print(f"\nOJO: {len(result['gaps'])} hueco(s) que la API no entrego. "
              "Hay que rotularlos en la serie, no dejarlos como mes sin ventas.")
    return 2 if result["errors"] else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
