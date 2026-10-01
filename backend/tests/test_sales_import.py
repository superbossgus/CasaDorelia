"""
Pruebas de la carga de ventas de Clip (`backend/sales_import.py`).

Unitarias: no necesitan backend corriendo ni Mongo. Cubren los cuatro defectos
de `create_sale` que esta carga tiene que evitar (IVA duplicado, fecha sellada
por el servidor, doble descuento de inventario, falta de idempotencia) y las
dos reglas de BOS-71 sobre el efectivo y la conciliacion.

    python -m pytest backend/tests/test_sales_import.py -q
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sales_import import (  # noqa: E402
    BUSINESS_TZ,
    SOURCE_CLIP_API,
    SOURCE_CLIP_EXPORT,
    SalesImportError,
    build_sale_document,
    business_date,
    normalize_row,
    parse_occurred_at,
    plan_import,
    reconcile_with_manual,
)

CAFETERIA = "caf-sji"


def row(**overrides):
    base = {
        "occurred_at": "2026-09-28T14:30:00",
        "gross_amount": 116.0,
        "payment_method": "Tarjeta de crédito",
        "status": "Aprobada",
        "transaction_id": "TX-001",
    }
    base.update(overrides)
    return base


def plan(rows, **kwargs):
    kwargs.setdefault("cafeteria_id", CAFETERIA)
    kwargs.setdefault("source", SOURCE_CLIP_EXPORT)
    return plan_import(rows, **kwargs)


# ---------------------------------------------------------------- fechas ---

def test_fecha_sin_offset_se_lee_como_hora_local_del_negocio():
    # Defecto #2 de create_sale: sellaba la fecha con now(). Aqui manda el dato.
    dt = parse_occurred_at("2026-09-28T14:30:00")
    assert dt == datetime(2026, 9, 28, 20, 30, tzinfo=timezone.utc)
    assert dt.astimezone(BUSINESS_TZ).hour == 14


def test_fecha_con_offset_se_respeta():
    assert parse_occurred_at("2026-09-28T20:30:00Z") == datetime(
        2026, 9, 28, 20, 30, tzinfo=timezone.utc
    )
    assert parse_occurred_at("2026-09-28T14:30:00-06:00") == datetime(
        2026, 9, 28, 20, 30, tzinfo=timezone.utc
    )


def test_dia_de_operacion_es_local_no_utc():
    # 19:00 local del 28 es 01:00 UTC del 29: el corte del dia debe decir 28.
    assert business_date(parse_occurred_at("2026-09-28T19:00:00")) == "2026-09-28"


def test_fecha_faltante_o_basura_se_rechaza():
    with pytest.raises(SalesImportError):
        parse_occurred_at(None)
    with pytest.raises(SalesImportError):
        parse_occurred_at("28/09/2026")


def test_la_venta_se_fecha_cuando_ocurrio_no_cuando_se_cargo():
    carga = datetime(2026, 10, 15, 3, 0, tzinfo=timezone.utc)
    doc = plan([row()], imported_at=carga).documents[0]
    assert doc["created_at"].startswith("2026-09-28T20:30:00")
    assert doc["business_date"] == "2026-09-28"
    assert doc["imported_at"] == carga.isoformat()


# ------------------------------------------------------------------ IVA ---

def test_el_iva_se_desglosa_no_se_vuelve_a_sumar():
    # Defecto #1: create_sale hacia total = subtotal * 1.16 sobre un monto que
    # ya traia IVA. El total cargado tiene que ser exactamente el de Clip.
    doc = plan([row(gross_amount=116.0)]).documents[0]
    assert doc["total"] == 116.0
    assert doc["subtotal"] == 100.0
    assert doc["tax"] == 16.0
    assert round(doc["subtotal"] + doc["tax"], 2) == doc["total"]


def test_los_totales_del_resumen_suman_el_bruto_de_clip():
    p = plan([row(transaction_id="A", gross_amount=116.0),
              row(transaction_id="B", gross_amount=58.0)])
    resumen = p.summary()
    assert resumen["gross_total"] == 174.0
    assert round(resumen["subtotal_total"] + resumen["tax_total"], 2) == 174.0


def test_monto_no_positivo_o_no_numerico_se_rechaza_con_motivo():
    p = plan([row(gross_amount=0), row(transaction_id="B", gross_amount="n/a")])
    assert p.documents == []
    assert len(p.rejected) == 2
    assert all("gross_amount" in r["reason"] for r in p.rejected)


# ----------------------------------------------------------- inventario ---

def test_las_ventas_importadas_no_mueven_inventario():
    # Defecto #3: la venta ya salio del inventario en el POS de Clip.
    doc = plan([row()]).documents[0]
    assert doc["inventory_applied"] is False
    assert plan([row()]).summary()["inventory_applied"] is False


def test_sin_costo_conocido_no_se_inventa_utilidad():
    doc = plan([row()]).documents[0]
    assert doc["cost_known"] is False
    assert doc["cost_total"] == 0.0
    assert doc["profit"] == 0.0


def test_con_costo_unitario_si_se_calcula_utilidad():
    doc = plan([row(unit_cost=20.0, quantity=2, gross_amount=232.0)]).documents[0]
    assert doc["cost_known"] is True
    assert doc["cost_total"] == 40.0
    assert doc["profit"] == round(doc["subtotal"] - 40.0, 2)


# --------------------------------------------------------- idempotencia ---

def test_reimportar_el_mismo_archivo_no_duplica():
    # Defecto #4: sin unicidad, el reintento duplicaba la venta.
    primera = plan([row()])
    claves = {d["dedup_key"] for d in primera.documents}
    segunda = plan([row()], existing_keys=claves)
    assert segunda.documents == []
    assert segunda.skipped[0]["reason"] == "ya_importada"


def test_una_fila_repetida_dentro_del_mismo_lote_entra_una_sola_vez():
    p = plan([row(), row()])
    assert len(p.documents) == 1
    assert p.skipped[0]["reason"] == "repetida_en_el_lote"


def test_sin_id_de_transaccion_la_clave_sale_del_folio_y_luego_del_hash():
    con_folio = plan([row(transaction_id=None, receipt_no="F-77")]).documents[0]
    assert con_folio["dedup_key"] == "folio:F-77"

    sin_nada = plan([row(transaction_id=None, receipt_no=None, branch="SJI")]).documents[0]
    assert sin_nada["dedup_key"].startswith("hash:")
    # El hash es estable: el mismo renglon da la misma clave.
    otra_vez = plan([row(transaction_id=None, receipt_no=None, branch="SJI")]).documents[0]
    assert otra_vez["dedup_key"] == sin_nada["dedup_key"]


def test_una_venta_de_otro_monto_no_colisiona_con_el_hash():
    a = plan([row(transaction_id=None, receipt_no=None, gross_amount=116.0)]).documents[0]
    b = plan([row(transaction_id=None, receipt_no=None, gross_amount=117.0)]).documents[0]
    assert a["dedup_key"] != b["dedup_key"]


# --------------------------------------------------------------- estados ---

def test_las_devoluciones_no_se_cargan_como_venta():
    p = plan([row(status="Devolución"), row(transaction_id="B", status="Aprobada")])
    assert len(p.documents) == 1
    assert p.skipped[0]["reason"] == "no_cobrada:reversed"


def test_un_estado_desconocido_no_entra_al_total():
    p = plan([row(status="En revisión")])
    assert p.documents == []
    assert p.skipped[0]["reason"] == "no_cobrada:unknown"


def test_sin_columna_de_estado_se_asume_cobrada():
    assert len(plan([row(status=None)]).documents) == 1


# --------------------------------------------------------------- efectivo ---

def test_la_api_de_clip_declara_que_no_trae_efectivo():
    resumen = plan([row()], source=SOURCE_CLIP_API).summary()
    assert resumen["cash_coverage"]["includes_cash"] is False
    assert "efectivo" in resumen["cash_coverage"]["note"].lower()


def test_el_export_declara_si_trajo_efectivo_o_no():
    solo_tarjeta = plan([row()]).summary()
    assert solo_tarjeta["cash_coverage"]["includes_cash"] is False

    con_efectivo = plan([row(), row(transaction_id="B", payment_method="Efectivo")]).summary()
    assert con_efectivo["cash_coverage"]["includes_cash"] is True
    assert con_efectivo["gross_by_payment_method"]["efectivo"] == 116.0


# ----------------------------------------------------------- conciliacion ---

def manual_sale(total, when="2026-09-28T14:00:00-06:00", method="tarjeta", **extra):
    doc = {"created_at": when, "total": total, "payment_method": method}
    doc.update(extra)
    return doc


def test_conciliacion_marca_match_dentro_de_la_tolerancia():
    docs = plan([row(gross_amount=116.0)]).documents
    [fila] = reconcile_with_manual(docs, [manual_sale(116.0)])
    assert fila["status"] == "match"
    assert fila["difference"] == 0.0


def test_conciliacion_señala_la_diferencia_sin_tocar_la_captura_manual():
    docs = plan([row(gross_amount=116.0)]).documents
    captura = [manual_sale(90.0)]
    antes = [dict(s) for s in captura]
    [fila] = reconcile_with_manual(docs, captura)
    assert fila["status"] == "difiere"
    assert fila["difference"] == 26.0
    assert captura == antes  # no sobrescribe nada


def test_el_efectivo_capturado_a_mano_no_entra_a_la_conciliacion():
    docs = plan([row(gross_amount=116.0)]).documents
    [fila] = reconcile_with_manual(
        docs, [manual_sale(116.0), manual_sale(500.0, method="Efectivo")]
    )
    assert fila["status"] == "match"
    assert fila["manual_card_total"] == 116.0


def test_una_venta_ya_importada_no_se_cuenta_como_captura_manual():
    docs = plan([row(gross_amount=116.0)]).documents
    [fila] = reconcile_with_manual(
        docs, [manual_sale(116.0, source=SOURCE_CLIP_EXPORT)]
    )
    assert fila["status"] == "solo_importado"
    assert fila["manual_card_count"] == 0


def test_un_dia_sin_captura_manual_y_uno_sin_venta_de_clip():
    docs = plan([row(gross_amount=116.0)]).documents
    filas = reconcile_with_manual(
        docs, [manual_sale(300.0, when="2026-09-29T10:00:00-06:00")]
    )
    por_dia = {f["business_date"]: f["status"] for f in filas}
    assert por_dia == {"2026-09-28": "solo_importado", "2026-09-29": "solo_manual"}


def test_only_days_recorta_los_dias_de_relleno_de_la_ventana():
    docs = plan([row(gross_amount=116.0)]).documents
    filas = reconcile_with_manual(
        docs,
        [manual_sale(300.0, when="2026-09-27T10:00:00-06:00")],
        only_days=["2026-09-28"],
    )
    assert [f["business_date"] for f in filas] == ["2026-09-28"]


def test_el_resumen_cuenta_los_dias_que_no_cuadran():
    p = plan([row(gross_amount=116.0)])
    p.reconciliation = reconcile_with_manual(p.documents, [manual_sale(90.0)])
    assert p.summary()["reconciliation_flags"] == 1


# ------------------------------------------------------------- contrato ---

def test_un_origen_que_no_es_carga_se_rechaza():
    with pytest.raises(SalesImportError):
        plan([row()], source="manual")
    with pytest.raises(SalesImportError):
        build_sale_document(normalize_row(row()), cafeteria_id=CAFETERIA, source="manual")


def test_falta_de_cafeteria_se_rechaza():
    with pytest.raises(SalesImportError):
        plan_import([row()], cafeteria_id="", source=SOURCE_CLIP_EXPORT)


def test_el_documento_trae_lo_que_el_app_necesita_para_distinguir_el_origen():
    doc = plan([row()], tenant_id="t-1", created_by="u-1").documents[0]
    assert doc["source"] == SOURCE_CLIP_EXPORT
    assert doc["tenant_id"] == "t-1"
    assert doc["created_by"] == "u-1"
    assert doc["cafeteria_id"] == CAFETERIA
    assert doc["clip_transaction_id"] == "TX-001"
    for campo in ("id", "items", "subtotal", "tax", "total", "cost_total",
                  "profit", "payment_method", "created_at"):
        assert campo in doc, campo


def test_una_fila_que_no_es_objeto_se_rechaza_sin_tirar_la_carga():
    p = plan(["esto no es una fila", row()])
    assert len(p.documents) == 1
    assert len(p.rejected) == 1


def test_el_estado_ya_clasificado_de_clip_import_se_respeta():
    # `ClipSale.to_json()` entrega "paid"/"reversed"/"unknown"; si se volviera a
    # clasificar, un "reversed" caeria en "unknown" y el motivo del salto
    # mentiria sobre por que no se cargo la venta.
    assert normalize_row(row(status="reversed"))["status"] == "reversed"
    assert normalize_row(row(status="paid"))["status"] == "paid"
    assert normalize_row(row(status="unknown"))["status"] == "unknown"


def test_la_salida_de_clip_import_se_carga_tal_cual():
    # El puente real: lo que produce el lector del export entra sin traducir.
    from clip_import import ClipSale, split_tax

    subtotal, tax = split_tax(232.0)
    venta = ClipSale(
        dedup_key="clip:TX-9",
        occurred_at=datetime(2026, 9, 28, 14, 30),
        gross_amount=232.0,
        subtotal=subtotal,
        tax=tax,
        payment_method="tarjeta",
        status="paid",
        transaction_id="TX-9",
        receipt_no="F-9",
        branch="SJI",
        product_name="Latte",
        quantity=2,
        source_row=3,
    )
    p = plan([venta.to_json()])
    assert len(p.documents) == 1
    doc = p.documents[0]
    assert doc["dedup_key"] == "clip:TX-9"
    assert doc["total"] == 232.0
    assert doc["business_date"] == "2026-09-28"
    assert doc["items"][0]["product_name"] == "Latte"
    assert doc["items"][0]["quantity"] == 2


def test_una_devolucion_que_viene_de_clip_import_se_salta_por_devolucion():
    p = plan([row(status="reversed")])
    assert p.skipped[0]["reason"] == "no_cobrada:reversed"


def test_el_resumen_lista_los_dias_y_los_motivos_de_lo_saltado():
    p = plan([
        row(transaction_id="A"),
        row(transaction_id="B", occurred_at="2026-09-29T09:00:00"),
        row(transaction_id="C", status="Cancelada"),
    ])
    resumen = p.summary()
    assert resumen["business_dates"] == ["2026-09-28", "2026-09-29"]
    assert resumen["to_insert"] == 2
    assert resumen["skipped_reasons"] == {"no_cobrada:reversed": 1}
