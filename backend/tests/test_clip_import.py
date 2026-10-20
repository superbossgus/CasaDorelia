"""
Pruebas del lector de exports de Clip (`backend/clip_import.py`).

Son unitarias y no necesitan backend corriendo ni Mongo: cada archivo de prueba
se genera en el momento con openpyxl/csv, imitando las convenciones del export
real de Clip (`Catalog_20260928025118.xlsx`, SJI 28/09, adjunto en BOS-66):
hoja `Ayuda` sin datos, encabezados en espanol en la fila 1 y una fila 2 de
instrucciones que no es un dato.

No se versionan archivos binarios de fixture a proposito (ver BOS-74).

    python -m pytest backend/tests/test_clip_import.py -q
"""
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clip_import import (  # noqa: E402
    ClipImportError,
    build_dedup_key,
    classify_status,
    describe_table,
    diff_catalog,
    normalize_header,
    normalize_payment_method,
    parse_catalog,
    parse_datetime,
    parse_money,
    parse_sales,
    split_tax,
)

CATALOG_HEADERS = [
    "ID de Producto", "Nombre del Producto", "Descripción del Producto",
    "Categoría", "Nombre de la Opción #1", "Nombre de la Variante #1",
    "Nombre de la Opción #2", "Nombre de la Variante #2", "Precio",
    "Inventario", "Alerta de Mínimo", "Código de Barras",
]
CATALOG_INSTRUCTIONS = [
    "En caso de que el producto ya exista...", "Obligatorio. Máximo de 255...",
    "Máximo de 255 caracteres", "Puedes escribir una categoría nueva",
    "En caso de tener variantes", "En caso de tener variantes",
    "En caso de tener variantes", "En caso de tener variantes",
    "Obligatorio. Escribir únicamente números", "Escribir el número de unidades",
    "Escribir el número de unidades", "Código único del producto",
]


def _catalog_row(product_id, name, category, option, variant, price,
                 inventory=10000.0):
    return [product_id, name, f"{name} rico", category, option, variant,
            None, None, price, inventory, None, None]


def write_catalog_xlsx(path: Path, rows) -> Path:
    """Escribe un libro con la misma forma que el export real de Clip."""
    import openpyxl

    workbook = openpyxl.Workbook()
    help_sheet = workbook.active
    help_sheet.title = "Ayuda"
    help_sheet["D3"] = "Importación Masiva de Productos"

    sheet = workbook.create_sheet("Productos")
    sheet.append(CATALOG_HEADERS)
    sheet.append(CATALOG_INSTRUCTIONS)
    for row in rows:
        sheet.append(row)
    workbook.save(path)
    return path


# --------------------------------------------------------------------------
# Normalizacion
# --------------------------------------------------------------------------

def test_normalize_header_quita_acentos_y_signos():
    assert normalize_header("ID de Transacción #1") == "id de transaccion 1"
    assert normalize_header("Método de pago") == "metodo de pago"
    assert normalize_header(None) == ""


@pytest.mark.parametrize("raw,expected", [
    ("$1,234.50", 1234.50),
    ("1.234,50", 1234.50),
    ("39.0", 39.0),
    (75, 75.0),
    ("(45.00)", -45.00),
    ("1,5", 1.5),
    ("2,500", 2500.0),
    ("", None),
    (None, None),
    ("n/a", None),
])
def test_parse_money(raw, expected):
    assert parse_money(raw) == expected


def test_parse_datetime_une_fecha_y_hora_de_columnas_separadas():
    assert parse_datetime("30/09/2026", "14:35") == datetime(2026, 9, 30, 14, 35)
    assert parse_datetime("2026-09-30 08:05:00") == datetime(2026, 9, 30, 8, 5)
    assert parse_datetime("30/09/2026", "2:35 p.m.") == datetime(2026, 9, 30, 14, 35)
    assert parse_datetime("sin fecha") is None


def test_normalize_payment_method_mapea_al_vocabulario_del_backend():
    assert normalize_payment_method("Efectivo") == "efectivo"
    assert normalize_payment_method("Tarjeta de crédito VISA") == "tarjeta"
    assert normalize_payment_method("Débito") == "tarjeta"
    assert normalize_payment_method("SPEI") == "transferencia"
    assert normalize_payment_method("") == "desconocido"


def test_classify_status():
    assert classify_status("Aprobada") == "paid"
    assert classify_status("Devolución") == "reversed"
    assert classify_status(None) == "paid"          # sin columna: asume cobrada
    assert classify_status("En proceso raro") == "unknown"


def test_split_tax_desglosa_sin_volver_a_sumar_iva():
    subtotal, tax = split_tax(100.0)
    assert (subtotal, tax) == (86.21, 13.79)
    assert round(subtotal + tax, 2) == 100.0


def test_build_dedup_key_prefiere_id_de_clip_luego_folio_luego_hash():
    when = datetime(2026, 9, 30, 10, 0)
    assert build_dedup_key("TX1", "F9", when, 50.0, "SJI") == "clip:TX1"
    assert build_dedup_key(None, "F9", when, 50.0, "SJI") == "folio:F9"
    solo_hash = build_dedup_key(None, None, when, 50.0, "SJI")
    assert solo_hash.startswith("hash:")
    # El hash es estable: reimportar el mismo archivo no duplica.
    assert solo_hash == build_dedup_key(None, None, when, 50.0, "sji ")
    assert solo_hash != build_dedup_key(None, None, when, 51.0, "SJI")


# --------------------------------------------------------------------------
# Ventas
# --------------------------------------------------------------------------

SALES_CSV = (
    "ID de Transacción,Fecha,Hora,Monto,Propina,Comisión,Método de pago,Estado,Sucursal\n"
    "TX-001,30/09/2026,09:12,\"$75.00\",0,2.61,Tarjeta de crédito,Aprobada,Casa Dorelia SJI\n"
    "TX-002,30/09/2026,09:40,\"$130.00\",10,0,Efectivo,Aprobada,Casa Dorelia SJI\n"
    "TX-003,30/09/2026,11:05,\"$65.00\",0,2.26,Débito,Devolución,Casa Dorelia SJI\n"
    "TX-001,30/09/2026,09:12,\"$75.00\",0,2.61,Tarjeta de crédito,Aprobada,Casa Dorelia SJI\n"
    ",30/09/2026,12:00,,0,0,Efectivo,Aprobada,Casa Dorelia SJI\n"
)


@pytest.fixture
def sales_csv(tmp_path: Path) -> Path:
    path = tmp_path / "Ventas_20260930.csv"
    path.write_text(SALES_CSV, encoding="utf-8")
    return path


def test_parse_sales_lee_montos_metodos_y_fechas(sales_csv):
    result = parse_sales(sales_csv)

    assert [s.transaction_id for s in result.sales] == [
        "TX-001", "TX-002", "TX-003", "TX-001"
    ]
    # El renglon sin monto se rechaza con su numero de fila, no se inventa.
    assert result.rejected == [{"row": 6, "reason": "monto ilegible o vacio"}]

    primera = result.sales[0]
    assert primera.occurred_at == datetime(2026, 9, 30, 9, 12)
    assert primera.gross_amount == 75.0
    assert (primera.subtotal, primera.tax) == (64.66, 10.34)
    assert primera.payment_method == "tarjeta"
    assert primera.fee == 2.61
    assert primera.branch == "Casa Dorelia SJI"
    assert primera.warnings == []


def test_parse_sales_excluye_devoluciones_del_total(sales_csv):
    result = parse_sales(sales_csv)
    summary = result.summary()

    assert summary["reversed_count"] == 1
    assert summary["paid_count"] == 3          # incluye el duplicado de TX-001
    # 75 + 130 + 75 (duplicado) = 280; la devolucion de 65 no suma.
    assert summary["gross_total"] == 280.0
    assert summary["gross_by_payment_method"] == {"tarjeta": 150.0, "efectivo": 130.0}
    assert summary["first_sale_at"] == "2026-09-30T09:12:00"
    assert summary["last_sale_at"] == "2026-09-30T09:40:00"


def test_parse_sales_dedup_por_id_de_transaccion(sales_csv):
    result = parse_sales(sales_csv)

    assert result.duplicate_keys() == ["clip:TX-001"]
    cobradas = result.deduplicated()
    assert [s.transaction_id for s in cobradas] == ["TX-001", "TX-002"]
    assert round(sum(s.gross_amount for s in cobradas), 2) == 205.0


def test_parse_sales_sin_id_ni_folio_avisa_y_deduplica_por_hash(tmp_path: Path):
    path = tmp_path / "ventas_sin_id.csv"
    path.write_text(
        "Fecha,Monto,Método de pago\n"
        "30/09/2026,50.00,Efectivo\n"
        "30/09/2026,50.00,Efectivo\n",
        encoding="utf-8",
    )
    result = parse_sales(path)

    assert all("sin id de Clip ni folio" in w for s in result.sales for w in s.warnings)
    assert len(result.duplicate_keys()) == 1
    assert len(result.deduplicated()) == 1


def test_parse_sales_monto_negativo_se_trata_como_devolucion(tmp_path: Path):
    path = tmp_path / "ventas_negativas.csv"
    path.write_text(
        "ID de Transacción,Fecha,Monto,Estado\nTX-9,30/09/2026,\"(120.00)\",Aprobada\n",
        encoding="utf-8",
    )
    venta = parse_sales(path).sales[0]

    assert venta.status == "reversed"
    assert venta.gross_amount == 120.0
    assert parse_sales(path).summary()["gross_total"] == 0.0


def test_parse_sales_sin_columna_de_monto_falla_mostrando_los_encabezados(tmp_path: Path):
    path = tmp_path / "otra_cosa.csv"
    path.write_text("Columna A,Columna B\n1,2\n", encoding="utf-8")

    with pytest.raises(ClipImportError) as exc:
        parse_sales(path)
    assert "Columna A" in str(exc.value)          # dice que vio, no adivina
    assert "SALES_HEADER_SYNONYMS" in str(exc.value)


def test_describe_table_reporta_encabezados_desconocidos(sales_csv):
    info = describe_table(sales_csv)

    assert info["looks_like"] == "sales"
    assert info["row_count"] == 5
    assert "amount" in info["sales_columns_detected"]
    assert info["sales_columns_unknown"] == []
    assert len(info["sample_rows"]) == 3


# --------------------------------------------------------------------------
# Catalogo
# --------------------------------------------------------------------------

@pytest.fixture
def catalog_xlsx(tmp_path: Path) -> Path:
    return write_catalog_xlsx(tmp_path / "Catalog_20260928025118.xlsx", [
        _catalog_row("p-1", "Espresso doble", "Bebidas a base café", None, None, 39.0),
        _catalog_row("p-2", "Mocha", "Bebidas a base café", "Tamaño", "12 oz", 65.0),
        _catalog_row("p-2", "Mocha", "Bebidas a base café", "Tamaño", "16 oz", 75.0),
        _catalog_row("p-3", "Cajetosa Dorelia", "Galletas", None, None, 30.0, 9999.0),
    ])


def test_parse_catalog_salta_hoja_de_ayuda_y_fila_de_instrucciones(catalog_xlsx):
    rows = parse_catalog(catalog_xlsx)

    assert len(rows) == 4
    assert [r.display_name for r in rows] == [
        "Espresso doble", "Mocha 12 oz", "Mocha 16 oz", "Cajetosa Dorelia"
    ]
    assert rows[0].price == 39.0
    assert rows[1].option_name == "Tamaño"
    # La fila 2 del template es ayuda: si entrara, 'Obligatorio...' seria producto.
    assert all("Obligatorio" not in r.name for r in rows)


def test_describe_table_distingue_catalogo_de_ventas(catalog_xlsx):
    info = describe_table(catalog_xlsx)

    assert info["looks_like"] == "catalog"
    assert info["sheet"] == "Productos"
    assert info["skipped_instruction_row"] is True
    assert info["row_count"] == 4


def test_diff_catalog_detecta_movimiento_de_precio(tmp_path: Path, catalog_xlsx):
    nuevo = write_catalog_xlsx(tmp_path / "Catalog_20261001.xlsx", [
        _catalog_row("p-1", "Espresso doble", "Bebidas a base café", None, None, 42.0),
        _catalog_row("p-2", "Mocha", "Bebidas a base café", "Tamaño", "12 oz", 65.0),
        _catalog_row("p-2", "Mocha", "Bebidas a base café", "Tamaño", "16 oz", 75.0),
        _catalog_row("p-4", "Concha Dorelia", "Pan", None, None, 28.0),
    ])
    resultado = diff_catalog(parse_catalog(catalog_xlsx), parse_catalog(nuevo))

    assert resultado["identical"] is False
    assert resultado["price_changes"] == [{
        "product": "Espresso doble",
        "category": "Bebidas a base café",
        "old_price": 39.0,
        "new_price": 42.0,
    }]
    assert resultado["added"] == ["Concha Dorelia"]
    assert resultado["removed"] == ["Cajetosa Dorelia"]
    assert resultado["unchanged"] == 2


def test_diff_catalog_sin_cambios_es_identico(catalog_xlsx):
    rows = parse_catalog(catalog_xlsx)
    assert diff_catalog(rows, rows)["identical"] is True
