"""El corte del app cuadra con el corte de Clip, peso por peso (BOS-97).

Las ocho ventas de abajo son las reales de `casa_dorelia` que caian en el dia
equivocado: todas se cobraron despues de las 18:00 de CDMX, asi que Clip las
sella con el dia UTC siguiente. Son las que hacian que el app inventara $185.40
de venta el sabado 26/09 (Tecnoparque cerrado) y que "ventas del mes" de octubre
abriera en $240.00 cuando octubre todavia no vendia nada.

La prueba pasa las mismas filas por los dos caminos:

- el corte que se aprueba antes de cargar (`clip_api.summarize_corte`), y
- el agrupado por dia que muestra el app (`business_day.daily_totals`, el mismo
  que arma `sales_trend` en `/dashboard/stats`).

Si los dos no dan identico, uno de los dos esta cortando por el dia equivocado.
Sin Mongo y sin red: las filas se construyen en memoria.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backfill_business_date import plan_backfill  # noqa: E402
from business_day import (  # noqa: E402
    BusinessDayError,
    as_corte,
    business_date,
    business_window,
    daily_totals,
    day_start_utc,
    month_start,
    recent_days,
    sale_business_date,
    stamp_business_date,
    to_business_date,
)
from clip_api import map_payment, summarize_corte  # noqa: E402
from sales_import import SOURCE_CLIP_API, plan_import  # noqa: E402

# Las ocho ventas desfasadas, tal como quedaron cargadas: instante UTC que manda
# Clip, monto y sucursal. El dia de operacion es el de la columna de la derecha.
#   (created_at UTC,              monto,  sucursal, dia de operacion)
VENTAS_DESFASADAS = [
    ("2026-09-22T02:12:58.000Z", 90.0, "tecno", "2026-09-21"),
    ("2026-09-22T02:42:54.000Z", 30.0, "tecno", "2026-09-21"),
    ("2026-09-23T00:25:47.000Z", 39.0, "tecno", "2026-09-22"),
    ("2026-09-24T00:55:46.000Z", 53.1, "tecno", "2026-09-23"),
    ("2026-09-26T01:20:22.000Z", 88.2, "tecno", "2026-09-25"),
    ("2026-09-26T01:28:40.000Z", 97.2, "tecno", "2026-09-25"),
    ("2026-09-30T00:34:26.000Z", 65.0, "tecno", "2026-09-29"),
    ("2026-10-01T00:08:46.000Z", 240.0, "sji", "2026-09-30"),
]


def filas(branch):
    """Filas de la API de Clip para una sucursal, como las baja `fetch_rows`."""
    pagos = [
        {
            "receipt_no": f"R{index:03d}",
            "id": f"txn_{index:03d}",
            "created_at": occurred_at,
            "status": "paid",
            "amount": amount,
            "tip": 0.0,
            "total": amount,
            "payment_method": "CREDIT",
            "card": {"brand": "VISA", "last4": "4242"},
            "currency": "MXN",
        }
        for index, (occurred_at, amount, sucursal, _dia) in enumerate(VENTAS_DESFASADAS)
        if sucursal == branch
    ]
    return [map_payment(p, branch=branch, index=i) for i, p in enumerate(pagos)]


def ventas(branch):
    """Los documentos que quedan en `sales` tras cargar esa sucursal."""
    return plan_import(filas(branch), cafeteria_id=f"corte-{branch}",
                       source=SOURCE_CLIP_API).documents


def corte_por_dia_utc(docs):
    """El agrupado VIEJO: por el dia UTC de `created_at`. Solo como testigo."""
    por_dia = {}
    for doc in docs:
        dia = por_dia.setdefault(doc["created_at"][:10],
                                 {"date": doc["created_at"][:10], "transactions": 0, "gross": 0.0})
        dia["transactions"] += 1
        dia["gross"] = round(dia["gross"] + doc["total"], 2)
    return [por_dia[dia] for dia in sorted(por_dia)]


# --------------------------------------------------------------------------
# La condicion de exito: los dos cortes dan lo mismo
# --------------------------------------------------------------------------

@pytest.mark.parametrize("branch", ["tecno", "sji"])
def test_el_corte_del_app_cuadra_peso_por_peso_con_el_de_clip(branch):
    del_app = as_corte(daily_totals(ventas(branch)))
    de_clip = summarize_corte(filas(branch), branch=branch)["by_business_date"]

    assert del_app == de_clip


def test_el_corte_del_app_reparte_las_ocho_ventas_en_su_dia_real():
    assert as_corte(daily_totals(ventas("tecno"))) == [
        {"date": "2026-09-21", "transactions": 2, "gross": 120.0},
        {"date": "2026-09-22", "transactions": 1, "gross": 39.0},
        {"date": "2026-09-23", "transactions": 1, "gross": 53.1},
        {"date": "2026-09-25", "transactions": 2, "gross": 185.4},
        {"date": "2026-09-29", "transactions": 1, "gross": 65.0},
    ]
    assert as_corte(daily_totals(ventas("sji"))) == [
        {"date": "2026-09-30", "transactions": 1, "gross": 240.0},
    ]


def test_el_sabado_cerrado_sale_en_cero():
    """26/09: Tecnoparque no abrio. El app no puede reportar venta ese dia."""
    semana = daily_totals(ventas("tecno"), recent_days(7, "2026-09-27"))
    sabado = next(dia for dia in semana if dia["date"] == "2026-09-26")

    assert sabado["transactions"] == 0
    assert sabado["gross"] == 0.0


def test_cortar_por_utc_es_lo_que_inventaba_la_venta_del_sabado():
    """El testigo del defecto: con el agrupado viejo el sabado valia $185.40.

    Son los dos cobros del viernes 25 despues de las 19:00. Si esta prueba
    empieza a fallar es que alguien volvio a cortar por `created_at`.
    """
    viejo = {dia["date"]: dia["gross"] for dia in corte_por_dia_utc(ventas("tecno"))}
    nuevo = {dia["date"]: dia["gross"] for dia in as_corte(daily_totals(ventas("tecno")))}

    assert viejo["2026-09-26"] == 185.4
    assert "2026-09-26" not in nuevo
    assert nuevo["2026-09-25"] == 185.4


def test_ventas_del_mes_de_octubre_no_arranca_con_dinero_de_septiembre():
    """La venta mas grande de SJI es del 30/09 aunque Clip la selle `01/10Z`."""
    venta = ventas("sji")[0]
    octubre = business_window(start=month_start("2026-10-01"))["business_date"]

    assert venta["created_at"][:10] == "2026-10-01"  # el dia UTC que confundia
    assert venta["business_date"] == "2026-09-30"
    assert venta["business_date"] < octubre["$gte"]  # queda fuera de octubre


# --------------------------------------------------------------------------
# La ventana de los reportes
# --------------------------------------------------------------------------

def test_la_ventana_cierra_el_dia_completo():
    """El detalle del tipo: sobre `YYYY-MM-DD` el limite superior es el dia.

    Con el `...T23:59:59` de antes, comparado contra cadenas de diez caracteres,
    el ultimo dia del rango se quedaba fuera entero.
    """
    ventana = business_window("2026-09-21", "2026-09-30")["business_date"]
    assert ventana == {"$gte": "2026-09-21", "$lte": "2026-09-30"}

    dias = [v["business_date"] for v in ventas("tecno") + ventas("sji")]
    dentro = [d for d in dias if ventana["$gte"] <= d <= ventana["$lte"]]
    assert len(dentro) == len(dias)  # ninguna de las ocho se cae del rango


def test_la_ventana_acepta_lo_que_mandan_las_pantallas():
    """`2026-10-01T00:00:00Z` de una pantalla vieja es el 30/09 del negocio."""
    assert business_window("2026-10-01T00:00:00Z")["business_date"] == {"$gte": "2026-09-30"}
    assert business_window("2026-09-21")["business_date"] == {"$gte": "2026-09-21"}
    assert business_window() == {}


def test_una_fecha_ilegible_se_dice_en_vez_de_adivinarse():
    with pytest.raises(BusinessDayError):
        to_business_date("el martes pasado")


def test_el_dia_de_operacion_empieza_a_las_06z():
    """Para las colecciones que no guardan `business_date` (pedidos, compras)."""
    assert day_start_utc("2026-09-26").isoformat() == "2026-09-26T06:00:00+00:00"


def test_la_hora_frontera_cae_del_lado_correcto():
    assert business_date(_utc("2026-09-26T05:59:59Z")) == "2026-09-25"
    assert business_date(_utc("2026-09-26T06:00:00Z")) == "2026-09-26"


def _utc(text):
    from datetime import datetime

    return datetime.fromisoformat(text.replace("Z", "+00:00"))


# --------------------------------------------------------------------------
# Que toda venta nazca sellada, y el backfill de las que no
# --------------------------------------------------------------------------

def test_la_venta_importada_nace_sellada():
    assert all(v.get("business_date") for v in ventas("tecno"))


def test_sellar_una_venta_capturada_a_mano():
    """Lo que hace `create_sale` y el POS antes de insertar."""
    venta = stamp_business_date({"total": 90.0, "created_at": "2026-09-22T02:12:58+00:00"})
    assert venta["business_date"] == "2026-09-21"


def test_una_venta_sin_sellar_se_reporta_por_su_dia_de_operacion():
    """Red de seguridad: si el backfill no la alcanzo, no se cae del reporte."""
    sin_sellar = [{"total": 90.0, "profit": 10.0, "created_at": "2026-09-22T02:12:58+00:00"}]
    assert sale_business_date(sin_sellar[0]) == "2026-09-21"
    assert as_corte(daily_totals(sin_sellar)) == [
        {"date": "2026-09-21", "transactions": 1, "gross": 90.0},
    ]


def test_el_backfill_deriva_el_dia_y_separa_las_ventas_sin_fecha():
    por_sellar, sin_fecha = plan_backfill([
        {"id": "s1", "_id": 1, "created_at": "2026-09-22T02:12:58+00:00"},
        {"id": "s2", "_id": 2, "created_at": "2026-09-30T18:00:00+00:00"},
        {"id": "roto", "_id": 3, "created_at": None},
    ])

    assert [(row["id"], row["business_date"]) for row in por_sellar] == [
        ("s1", "2026-09-21"),
        ("s2", "2026-09-30"),
    ]
    # Una venta sin fecha se reporta, no se le inventa un dia.
    assert [row["id"] for row in sin_fecha] == ["roto"]


def test_el_backfill_no_vuelve_a_mover_lo_ya_sellado():
    ya = {"id": "s1", "_id": 1, "business_date": "2026-09-21",
          "created_at": "2026-09-22T02:12:58+00:00"}
    por_sellar, _ = plan_backfill([ya])

    assert por_sellar[0]["business_date"] == "2026-09-21"  # respeta el sello, no el UTC
