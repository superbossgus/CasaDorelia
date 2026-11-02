"""
Carga de ventas de Clip a la coleccion `sales`, sin los defectos de `create_sale`.

Modulo puro: no toca Mongo, no importa FastAPI. Recibe filas ya normalizadas
(las que produce `clip_import.parse_sales`, o las que produzca el cliente de la
API de Clip cuando haya credencial) y devuelve los documentos listos para
insertar, mas un resumen que se puede enseñar ANTES de escribir (`dry_run`).

Cuatro cosas que `create_sale` (server.py) hace mal para una carga de Clip y que
aqui estan resueltas:

1. **IVA duplicado.** `create_sale` suma 16% sobre el subtotal recibido. El monto
   de Clip YA trae IVA, asi que aqui se desglosa con `clip_import.split_tax` y
   nunca se vuelve a sumar impuesto.
2. **Fecha sellada por el servidor.** `create_sale` usa `now()`. Aqui la fecha es
   `occurred_at`, obligatoria, y ademas se guarda `business_date` para que el
   corte por dia no dependa de a que hora se corrio la carga.
3. **Doble descuento de inventario.** Una venta cobrada en el POS de Clip ya
   salio del inventario fisico. Las ventas importadas no mueven inventario
   (`inventory_applied: False`).
4. **Sin idempotencia.** Aqui cada venta trae `dedup_key` estable
   (`clip_import.build_dedup_key`); reimportar el mismo archivo no duplica.

Dos cosas mas que el plan de BOS-71 pide explicitamente:

- **El efectivo no viene en la API de Clip.** Cada resumen declara su cobertura
  (`cash_coverage`) para que la pantalla lo diga en vez de enseñar un total
  corto pero verosimil, que es el peor tipo de error.
- **Conciliar sin sobrescribir.** `reconcile_with_manual` compara contra lo
  capturado a mano por dia y SEÑALA diferencias; nunca modifica ni borra.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from business_day import BUSINESS_TZ, business_date
from clip_import import IVA_RATE, build_dedup_key, classify_status, normalize_payment_method, split_tax

# `BUSINESS_TZ` y `business_date` viven en `business_day`: el huso del negocio
# se declara una sola vez y lo comparten la carga, el corte de Clip y los
# reportes del app. Se importan aqui (y siguen siendo `sales_import.BUSINESS_TZ`
# para quien ya los pedia asi) en vez de volver a escribir el offset.

SOURCE_MANUAL = "manual"
SOURCE_CLIP_EXPORT = "clip_export"
SOURCE_CLIP_API = "clip_api"
IMPORT_SOURCES = (SOURCE_CLIP_EXPORT, SOURCE_CLIP_API)

# Que tanto del dinero del dia cubre cada origen. Se guarda en el resumen para
# que la interfaz no tenga que adivinarlo.
CASH_COVERAGE = {
    SOURCE_CLIP_API: {
        "includes_cash": False,
        "note": (
            "La API de Clip entrega lo que cobro la terminal: tarjeta bancaria y "
            "vales (Pluxee, Edenred...). El efectivo que la app de Clip si "
            "registra NO viaja por esta API (medido el 2026-10-04: 1,912 cobros "
            "en 360 dias, cero rotulados efectivo), asi que este total es un "
            "piso. Para traer efectivo hay que usar el export del panel."
        ),
    },
    SOURCE_CLIP_EXPORT: {
        "includes_cash": None,  # depende de si el export trae renglones de efectivo
        "note": (
            "El export del panel de Clip puede incluir efectivo. Revisa el desglose "
            "por metodo de pago antes de dar el total por completo."
        ),
    },
}


# Vocabulario de estado que ya usa `clip_import.classify_status`.
CANONICAL_STATUSES = ("paid", "reversed", "unknown")


class SalesImportError(ValueError):
    """Error de forma en una fila de carga."""


# --------------------------------------------------------------------------
# Normalizacion de una fila
# --------------------------------------------------------------------------

def parse_occurred_at(value: Any) -> datetime:
    """Interpreta la fecha-hora de la venta y la devuelve en UTC.

    Acepta `datetime` o cadena ISO-8601. Una cadena **sin** offset se entiende
    como hora local del negocio (UTC-6), que es como la escriben tanto el export
    del panel como la captura manual.
    """
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip():
        raw = value.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise SalesImportError(f"`occurred_at` no es una fecha ISO-8601: {value!r}") from exc
    else:
        raise SalesImportError("`occurred_at` es obligatorio en una venta importada")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BUSINESS_TZ)
    return dt.astimezone(timezone.utc)


def _positive_amount(value: Any, field_name: str) -> float:
    try:
        amount = float(value)
    except (TypeError, ValueError) as exc:
        raise SalesImportError(f"`{field_name}` no es un numero: {value!r}") from exc
    if amount <= 0:
        raise SalesImportError(f"`{field_name}` debe ser mayor que cero, llego {amount}")
    return round(amount, 2)


def normalize_row(raw: Dict[str, Any], index: int = 0, *,
                  iva_rate: float = IVA_RATE) -> Dict[str, Any]:
    """Valida una fila de carga y la deja lista para armar el documento.

    Lanza `SalesImportError` con un mensaje que dice exactamente que falto; el
    que llama decide si rechaza la fila o aborta la carga completa.
    """
    if not isinstance(raw, dict):
        raise SalesImportError(f"la fila {index} no es un objeto")

    occurred_at = parse_occurred_at(raw.get("occurred_at"))
    gross = _positive_amount(raw.get("gross_amount"), "gross_amount")
    subtotal, tax = split_tax(gross, iva_rate)

    # `clip_import` ya entrega el estado clasificado ("paid"/"reversed"/
    # "unknown"); cualquier otra cosa viene cruda del archivo o de la API y hay
    # que clasificarla. Sin clasificar, un "reversed" se leeria como "unknown".
    status = raw.get("status")
    if status in CANONICAL_STATUSES:
        status = str(status)
    elif status is None:
        status = "paid"
    else:
        status = classify_status(status)

    payment_method = raw.get("payment_method")
    payment_method = normalize_payment_method(payment_method) if payment_method else "tarjeta"

    transaction_id = _clean(raw.get("transaction_id")) or _clean(raw.get("clip_transaction_id"))
    receipt_no = _clean(raw.get("receipt_no"))
    branch = _clean(raw.get("branch"))

    dedup_key = _clean(raw.get("dedup_key")) or build_dedup_key(
        transaction_id, receipt_no, occurred_at, gross, branch
    )

    return {
        "dedup_key": dedup_key,
        "occurred_at": occurred_at,
        "business_date": business_date(occurred_at),
        "gross_amount": gross,
        "subtotal": subtotal,
        "tax": tax,
        "status": status,
        "payment_method": payment_method,
        "transaction_id": transaction_id,
        "receipt_no": receipt_no,
        "branch": branch,
        "tip": _optional_float(raw.get("tip")),
        "fee": _optional_float(raw.get("fee")),
        "product_name": _clean(raw.get("product_name")),
        "product_id": _clean(raw.get("product_id")),
        "quantity": _optional_int(raw.get("quantity")),
        "unit_cost": _optional_float(raw.get("unit_cost")),
        "notes": _clean(raw.get("notes")),
        "source_row": raw.get("source_row", index),
    }


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# Documento de venta
# --------------------------------------------------------------------------

def build_sale_document(row: Dict[str, Any], *, cafeteria_id: str, source: str,
                        tenant_id: Optional[str] = None,
                        brand: Optional[str] = None,
                        created_by: Optional[str] = None,
                        imported_at: Optional[datetime] = None) -> Dict[str, Any]:
    """Arma el documento que se inserta en `sales` para una venta importada.

    `created_at` es la fecha REAL de la venta (no la de la carga), en UTC, y
    `business_date` es el dia de operacion en hora local: los reportes del app
    cortan por `business_date`, no por `created_at`, porque una venta de las
    19:00 de CDMX se sella como el dia UTC siguiente. La fecha de la carga
    queda en `imported_at`, que es dato de auditoria, no de negocio.

    `brand` es la marca dueña del dinero (`brands.py`). Se sella en la venta, no
    solo en la sucursal, para que el corte por marca sea una consulta a `sales` y
    no un `$lookup`; y queda `None` si quien llama no la supo, porque una marca
    adivinada es peor que una marca ausente: la ausente se ve en el reporte.
    """
    if source not in IMPORT_SOURCES:
        raise SalesImportError(f"origen desconocido para una carga: {source!r}")

    quantity = row.get("quantity") or 1
    unit_cost = row.get("unit_cost")
    cost_total = round(unit_cost * quantity, 2) if unit_cost is not None else 0.0
    cost_known = unit_cost is not None

    item = {
        "product_id": row.get("product_id"),
        "product_name": row.get("product_name") or "Venta Clip (sin desglose)",
        "quantity": quantity,
        "unit_price": round(row["subtotal"] / quantity, 2) if quantity else row["subtotal"],
        "subtotal": row["subtotal"],
        "cost": cost_total,
    }

    return {
        "id": str(uuid.uuid4()),
        "cafeteria_id": cafeteria_id,
        "tenant_id": tenant_id,
        "brand": brand,
        "items": [item],
        # Montos: el bruto de Clip ya traia IVA, aqui solo se desglosa.
        "subtotal": row["subtotal"],
        "tax": row["tax"],
        "total": row["gross_amount"],
        "cost_total": cost_total,
        # Sin costo conocido no se inventa margen: se deja en 0 y se marca
        # `cost_known: False` para que la pantalla no presuma utilidad falsa.
        "profit": round(row["subtotal"] - cost_total, 2) if cost_known else 0.0,
        "cost_known": cost_known,
        "payment_method": row["payment_method"],
        "clip_transaction_id": row.get("transaction_id"),
        "notes": row.get("notes"),
        "created_by": created_by,
        "created_at": row["occurred_at"].isoformat(),
        # Trazabilidad de la carga.
        "source": source,
        "dedup_key": row["dedup_key"],
        "business_date": row["business_date"],
        "receipt_no": row.get("receipt_no"),
        "clip_tip": row.get("tip"),
        "clip_fee": row.get("fee"),
        "clip_branch": row.get("branch"),
        "inventory_applied": False,
        "imported_at": (imported_at or datetime.now(timezone.utc)).isoformat(),
    }


# --------------------------------------------------------------------------
# Plan de carga
# --------------------------------------------------------------------------

@dataclass
class ImportPlan:
    """Que se insertaria, que se salta y por que. Es lo que devuelve `dry_run`."""
    source: str
    cafeteria_id: str
    documents: List[Dict[str, Any]] = field(default_factory=list)
    skipped: List[Dict[str, Any]] = field(default_factory=list)
    rejected: List[Dict[str, Any]] = field(default_factory=list)
    reconciliation: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def gross_total(self) -> float:
        return round(sum(d["total"] for d in self.documents), 2)

    def summary(self) -> Dict[str, Any]:
        by_method: Dict[str, float] = {}
        for doc in self.documents:
            by_method[doc["payment_method"]] = round(
                by_method.get(doc["payment_method"], 0.0) + doc["total"], 2
            )
        days = sorted({d["business_date"] for d in self.documents})
        coverage = dict(CASH_COVERAGE[self.source])
        if self.source in IMPORT_SOURCES:
            # Se *mide* sobre lo cargado, no se declara por origen. La API de
            # Clip hoy no manda efectivo, pero si algun dia lo manda (o si la
            # terminal lo empieza a rotular), el resumen tiene que dejar de
            # decir que falta: un "no incluye efectivo" escrito a mano se vuelve
            # mentira sin que nadie lo note.
            coverage["includes_cash"] = "efectivo" in by_method
        return {
            "source": self.source,
            "cafeteria_id": self.cafeteria_id,
            "to_insert": len(self.documents),
            "skipped": len(self.skipped),
            "rejected": len(self.rejected),
            "skipped_reasons": _count_by(self.skipped, "reason"),
            "gross_total": self.gross_total,
            "subtotal_total": round(sum(d["subtotal"] for d in self.documents), 2),
            "tax_total": round(sum(d["tax"] for d in self.documents), 2),
            "gross_by_payment_method": by_method,
            "business_dates": days,
            "cost_known_count": sum(1 for d in self.documents if d["cost_known"]),
            "inventory_applied": False,
            "cash_coverage": coverage,
            "reconciliation_flags": sum(
                1 for r in self.reconciliation if r["status"] != "match"
            ),
        }


def _count_by(items: Sequence[Dict[str, Any]], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for item in items:
        out[item.get(key, "?")] = out.get(item.get(key, "?"), 0) + 1
    return out


def plan_import(rows: Iterable[Dict[str, Any]], *, cafeteria_id: str, source: str,
                existing_keys: Iterable[str] = (),
                tenant_id: Optional[str] = None,
                brand: Optional[str] = None,
                created_by: Optional[str] = None,
                imported_at: Optional[datetime] = None,
                iva_rate: float = IVA_RATE) -> ImportPlan:
    """Decide que filas se insertan. No escribe nada.

    Se salta (no rechaza) lo que ya existe por `dedup_key`, lo repetido dentro
    del mismo lote y lo que no es una venta cobrada (devoluciones, rechazos).
    Rechaza solo lo que no se puede interpretar, diciendo por que.
    """
    if not cafeteria_id:
        raise SalesImportError("`cafeteria_id` es obligatorio")
    if source not in IMPORT_SOURCES:
        raise SalesImportError(f"origen desconocido para una carga: {source!r}")

    plan = ImportPlan(source=source, cafeteria_id=cafeteria_id)
    already = set(existing_keys)
    seen_in_batch: set[str] = set()

    for index, raw in enumerate(rows):
        try:
            row = normalize_row(raw, index, iva_rate=iva_rate)
        except SalesImportError as exc:
            plan.rejected.append({"row": index, "reason": str(exc), "raw": _preview(raw)})
            continue

        if row["status"] != "paid":
            plan.skipped.append({
                "row": index,
                "dedup_key": row["dedup_key"],
                "reason": f"no_cobrada:{row['status']}",
                "gross_amount": row["gross_amount"],
            })
            continue
        if row["dedup_key"] in already:
            plan.skipped.append({
                "row": index,
                "dedup_key": row["dedup_key"],
                "reason": "ya_importada",
                "gross_amount": row["gross_amount"],
            })
            continue
        if row["dedup_key"] in seen_in_batch:
            plan.skipped.append({
                "row": index,
                "dedup_key": row["dedup_key"],
                "reason": "repetida_en_el_lote",
                "gross_amount": row["gross_amount"],
            })
            continue

        seen_in_batch.add(row["dedup_key"])
        plan.documents.append(build_sale_document(
            row,
            cafeteria_id=cafeteria_id,
            source=source,
            tenant_id=tenant_id,
            brand=brand,
            created_by=created_by,
            imported_at=imported_at,
        ))

    return plan


def _preview(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {"value": repr(raw)[:120]}
    keep = ("occurred_at", "gross_amount", "transaction_id", "receipt_no", "status")
    return {k: raw.get(k) for k in keep if k in raw}


# --------------------------------------------------------------------------
# Conciliacion contra lo capturado a mano
# --------------------------------------------------------------------------

def reconcile_with_manual(documents: Sequence[Dict[str, Any]],
                          manual_sales: Iterable[Dict[str, Any]],
                          *, tolerance: float = 1.0,
                          only_days: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
    """Compara por dia lo que viene de Clip contra lo capturado a mano.

    Devuelve un renglon por dia con la diferencia y una etiqueta. **No modifica
    ni borra nada**: la captura manual es la version de un humano y se respeta;
    lo unico que hacemos es señalar donde no cuadra.

    `status`:
      - `match`            la diferencia cabe en la tolerancia
      - `solo_importado`   ese dia no tiene captura manual con tarjeta
      - `solo_manual`      hay captura manual con tarjeta y Clip no trajo nada
      - `difiere`          ambos tienen monto y no cuadran

    `only_days` limita el reporte a esos dias de operacion: la consulta que
    trae la captura manual abre la ventana un dia de cada lado (UTC vs local) y
    sin este filtro apareceria un `solo_manual` de relleno en los extremos.
    """
    wanted = set(only_days) if only_days is not None else None
    imported: Dict[str, Dict[str, Any]] = {}
    for doc in documents:
        day = doc.get("business_date") or business_date(parse_occurred_at(doc["created_at"]))
        bucket = imported.setdefault(day, {"total": 0.0, "count": 0})
        bucket["total"] = round(bucket["total"] + doc["total"], 2)
        bucket["count"] += 1

    manual: Dict[str, Dict[str, Any]] = {}
    for sale in manual_sales:
        if sale.get("source") in IMPORT_SOURCES:
            continue  # ya es una venta importada, no es captura manual
        method = normalize_payment_method(sale.get("payment_method") or "")
        if method == "efectivo":
            continue  # el efectivo nunca viene de Clip; compararlo seria ruido
        try:
            day = sale.get("business_date") or business_date(parse_occurred_at(sale.get("created_at")))
        except SalesImportError:
            continue
        bucket = manual.setdefault(day, {"total": 0.0, "count": 0})
        bucket["total"] = round(bucket["total"] + float(sale.get("total") or 0.0), 2)
        bucket["count"] += 1

    out: List[Dict[str, Any]] = []
    for day in sorted(set(imported) | set(manual)):
        if wanted is not None and day not in wanted:
            continue
        imp = imported.get(day, {"total": 0.0, "count": 0})
        man = manual.get(day, {"total": 0.0, "count": 0})
        difference = round(imp["total"] - man["total"], 2)
        if man["count"] == 0:
            status = "solo_importado"
        elif imp["count"] == 0:
            status = "solo_manual"
        elif abs(difference) <= tolerance:
            status = "match"
        else:
            status = "difiere"
        out.append({
            "business_date": day,
            "imported_total": imp["total"],
            "imported_count": imp["count"],
            "manual_card_total": man["total"],
            "manual_card_count": man["count"],
            "difference": difference,
            "status": status,
        })
    return out
