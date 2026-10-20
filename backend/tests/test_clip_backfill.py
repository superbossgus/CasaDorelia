"""La carga de un año: meses exactos, el `400` bisecado y el hueco rotulado.

Sin Mongo y sin red: la coleccion es un doble y `fetch` es una funcion que
decide por rango que contesta (o con que falla).
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from clip_api import ClipApiError, ClipAuthError, map_payment  # noqa: E402
from clip_backfill import (  # noqa: E402
    BranchSpec,
    backfill,
    fetch_rows_splitting,
    month_chunks,
)
from clip_load import ClipLoadError  # noqa: E402


class FakeSales:
    def __init__(self):
        self.docs = []
        self.inserted = []

    def find(self, query, projection=None):
        wanted = set(query.get("dedup_key", {}).get("$in", []))
        return [{"dedup_key": d["dedup_key"]} for d in self.docs if d["dedup_key"] in wanted]

    def insert_many(self, docs):
        self.inserted.extend(docs)
        self.docs.extend(docs)


def payment(day, txn, amount=116.0):
    return {
        "receipt_no": txn,
        "id": txn,
        "created_at": f"{day}T18:30:00.000Z",
        "status": "paid",
        "amount": amount,
        "tip": 0.0,
        "total": amount,
        "payment_method": "CREDIT",
        "card": {"brand": "VISA", "last4": "4242"},
        "currency": "MXN",
    }


def rows_for(*payments):
    return [map_payment(p, branch="tecnoparque", index=i) for i, p in enumerate(payments)]


# --------------------------------------------------------------------------
# month_chunks
# --------------------------------------------------------------------------

def test_meses_recortados_a_los_extremos_del_rango():
    chunks = month_chunks(date(2025, 10, 21), date(2026, 10, 4))

    assert chunks[0] == (date(2025, 10, 21), date(2025, 10, 31))
    assert chunks[-1] == (date(2026, 10, 1), date(2026, 10, 4))
    assert len(chunks) == 13


def test_los_meses_cubren_el_rango_sin_hueco_ni_traslape():
    chunks = month_chunks(date(2025, 10, 21), date(2026, 10, 4))

    assert chunks[0][0] == date(2025, 10, 21)
    for (_, previous_end), (next_start, _) in zip(chunks, chunks[1:]):
        assert (next_start - previous_end).days == 1
    assert chunks[-1][1] == date(2026, 10, 4)


def test_cruza_el_fin_de_año():
    chunks = month_chunks(date(2025, 12, 20), date(2026, 1, 5))

    assert chunks == [
        (date(2025, 12, 20), date(2025, 12, 31)),
        (date(2026, 1, 1), date(2026, 1, 5)),
    ]


def test_un_solo_dia_es_un_mes_de_un_dia():
    assert month_chunks(date(2026, 2, 14), date(2026, 2, 14)) == [
        (date(2026, 2, 14), date(2026, 2, 14))
    ]


def test_rango_al_reves_falla_antes_de_pedir_nada():
    with pytest.raises(ClipLoadError, match="al reves"):
        month_chunks(date(2026, 3, 1), date(2026, 2, 1))


# --------------------------------------------------------------------------
# BranchSpec
# --------------------------------------------------------------------------

def test_branch_spec_parte_sucursal_y_cafeteria():
    spec = BranchSpec.parse("tecnoparque:c-tecno")

    assert (spec.branch, spec.cafeteria_id) == ("tecnoparque", "c-tecno")


@pytest.mark.parametrize("raw", ["tecnoparque", "a:b:c", ":c-tecno", "tecnoparque:"])
def test_branch_spec_rechaza_lo_que_no_es_par(raw):
    with pytest.raises(ClipLoadError, match="--branch invalido"):
        BranchSpec.parse(raw)


# --------------------------------------------------------------------------
# fetch_rows_splitting
# --------------------------------------------------------------------------

def test_sin_error_no_parte_nada_y_pide_una_sola_vez():
    calls = []

    def fetch(credentials, start, end, **kwargs):
        calls.append((start.date(), end.date()))
        return rows_for(payment("2026-01-10", "t1"))

    found, gaps = fetch_rows_splitting(None, date(2026, 1, 1), date(2026, 1, 31), fetch=fetch)

    assert len(calls) == 1
    assert len(found) == 1
    assert gaps == []


def test_un_400_en_el_mes_se_resuelve_pidiendo_menos_dias():
    """La ventana completa falla, las mitades no: el mes entra igual, sin hueco."""
    calls = []

    def fetch(credentials, start, end, **kwargs):
        span = (end.date() - start.date()).days
        calls.append((start.date(), end.date()))
        if span > 15:
            raise ClipApiError("payclip.bad.request", status=400)
        return rows_for(payment(start.date().isoformat(), f"t{start.date()}"))

    found, gaps = fetch_rows_splitting(None, date(2026, 2, 14), date(2026, 3, 15), fetch=fetch)

    assert gaps == []
    assert len(found) == 2
    assert len(calls) == 3  # el mes, y sus dos mitades


def test_solo_el_dia_que_sigue_fallando_queda_como_hueco():
    """Un dia envenenado no se lleva el mes: se reporta ese dia y entra el resto."""
    roto = date(2026, 2, 20)

    def fetch(credentials, start, end, **kwargs):
        if start.date() <= roto <= end.date():
            raise ClipApiError("payclip.bad.request", status=400)
        return rows_for(payment(start.date().isoformat(), f"t{start.date()}"))

    found, gaps = fetch_rows_splitting(None, date(2026, 2, 14), date(2026, 2, 28), fetch=fetch)

    assert [(g["from"], g["to"], g["days"]) for g in gaps] == [("2026-02-20", "2026-02-20", 1)]
    assert gaps[0]["status"] == 400
    assert found, "los dias sanos del mes si entraron"


def test_los_dias_contiguos_que_fallan_se_juntan_en_un_rotulo():
    def fetch(credentials, start, end, **kwargs):
        raise ClipApiError("payclip.bad.request", status=400)

    _, gaps = fetch_rows_splitting(None, date(2026, 2, 14), date(2026, 2, 18), fetch=fetch)

    assert [(g["from"], g["to"], g["days"]) for g in gaps] == [("2026-02-14", "2026-02-18", 5)]


def test_una_credencial_rechazada_no_se_pide_treinta_veces():
    calls = []

    def fetch(credentials, start, end, **kwargs):
        calls.append(1)
        raise ClipAuthError("401", status=401)

    with pytest.raises(ClipAuthError):
        fetch_rows_splitting(None, date(2026, 2, 1), date(2026, 2, 28), fetch=fetch)

    assert len(calls) == 1


def test_un_429_no_se_parte_porque_partir_lo_empeora():
    calls = []

    def fetch(credentials, start, end, **kwargs):
        calls.append(1)
        raise ClipApiError("rate limit", status=429)

    with pytest.raises(ClipApiError):
        fetch_rows_splitting(None, date(2026, 2, 1), date(2026, 2, 28), fetch=fetch)

    assert len(calls) == 1


# --------------------------------------------------------------------------
# backfill
# --------------------------------------------------------------------------

def _fetch_one_per_month(credentials, start, end, **kwargs):
    day = start.date().isoformat()
    return rows_for(payment(day, f"txn-{credentials}-{day}"))


def test_en_seco_no_escribe_y_reporta_lo_que_entraria():
    sales = FakeSales()

    result = backfill(
        sales,
        branches=[BranchSpec("tecnoparque", "c-tecno")],
        start=date(2026, 1, 1), end=date(2026, 3, 31),
        fetch=_fetch_one_per_month,
        credentials_for=lambda branch: branch,
    )

    assert sales.inserted == []
    assert result["committed"] is False
    assert result["totals"]["inserted"] == 0
    assert result["totals"]["to_insert"] == 3
    assert [m["month"] for m in result["months"]] == ["2026-01", "2026-02", "2026-03"]


def test_con_commit_escribe_una_vez_y_reimportar_no_duplica():
    sales = FakeSales()
    args = dict(
        branches=[BranchSpec("tecnoparque", "c-tecno")],
        start=date(2026, 1, 1), end=date(2026, 2, 28),
        fetch=_fetch_one_per_month,
        credentials_for=lambda branch: branch,
        commit=True,
    )

    first = backfill(sales, **args)
    second = backfill(sales, **args)

    assert first["totals"]["inserted"] == 2
    assert second["totals"]["inserted"] == 0
    assert len(sales.docs) == 2
    assert second["months"][0]["skipped_reasons"] == {"ya_importada": 1}


def test_la_marca_sale_del_catalogo_y_el_total_va_por_marca():
    sales = FakeSales()

    result = backfill(
        sales,
        branches=[BranchSpec("tecnoparque", "c-tecno"), BranchSpec("sji", "c-sji")],
        start=date(2026, 1, 1), end=date(2026, 1, 31),
        fetch=_fetch_one_per_month,
        credentials_for=lambda branch: branch,
        commit=True,
    )

    marcas = {row["brand"]: row for row in result["by_brand"]}
    assert set(marcas) == {"le-pain-dore", "casa-dorelia"}
    # El total por marca trae las dos lecturas, para poder decir cuanto cambia
    # el tablero sin volver a sumar los meses a mano.
    assert marcas["le-pain-dore"]["to_insert"] == 1
    assert marcas["le-pain-dore"]["corte_gross"] > 0
    assert all(doc["brand"] in marcas for doc in sales.docs)
    # Dos vehiculos con socios distintos: el resultado no trae un consolidado.
    assert "total" not in result["by_brand"]


def test_el_hueco_sube_al_resultado_con_su_sucursal_y_su_mes():
    sales = FakeSales()

    def fetch(credentials, start, end, **kwargs):
        if start.date().month == 2:
            raise ClipApiError("payclip.bad.request", status=400)
        return _fetch_one_per_month(credentials, start, end, **kwargs)

    result = backfill(
        sales,
        branches=[BranchSpec("tecnoparque", "c-tecno")],
        start=date(2026, 1, 1), end=date(2026, 3, 31),
        fetch=fetch,
        credentials_for=lambda branch: branch,
    )

    assert [(g["branch"], g["from"], g["to"]) for g in result["gaps"]] == [
        ("tecnoparque", "2026-02-01", "2026-02-28")
    ]
    febrero = next(m for m in result["months"] if m["month"] == "2026-02")
    assert febrero["api_rows"] == 0
    assert febrero["gaps"], "el mes tambien lleva su propio rotulo"


def test_un_mes_que_truena_por_otra_cosa_no_detiene_los_demas():
    sales = FakeSales()

    def fetch(credentials, start, end, **kwargs):
        if start.date().month == 2:
            raise ClipApiError("rate limit", status=429)
        return _fetch_one_per_month(credentials, start, end, **kwargs)

    result = backfill(
        sales,
        branches=[BranchSpec("tecnoparque", "c-tecno")],
        start=date(2026, 1, 1), end=date(2026, 3, 31),
        fetch=fetch,
        credentials_for=lambda branch: branch,
    )

    assert [e["month"] for e in result["errors"]] == ["2026-02"]
    assert [m["month"] for m in result["months"]] == ["2026-01", "2026-03"]


def test_el_corte_del_mes_no_se_cae_al_reimportar_lo_ya_cargado():
    """`gross_total` se va a cero en la segunda pasada; `corte_gross` no.

    Es la confusion que hace leer un mes ya cargado como un mes sin ventas.
    """
    sales = FakeSales()
    args = dict(
        branches=[BranchSpec("tecnoparque", "c-tecno")],
        start=date(2026, 1, 1), end=date(2026, 1, 31),
        fetch=_fetch_one_per_month,
        credentials_for=lambda branch: branch,
        commit=True,
    )

    first = backfill(sales, **args)["months"][0]
    second = backfill(sales, **args)["months"][0]

    assert first["gross_total"] == first["corte_gross"] > 0
    assert second["gross_total"] == 0
    assert second["corte_gross"] == first["corte_gross"]


def test_una_fila_rechazada_viaja_con_su_motivo_y_se_cuenta_en_el_total():
    """El conteo no basta: para saber si el rechazo importa hace falta el motivo."""
    sales = FakeSales()

    def fetch(credentials, start, end, **kwargs):
        # Monto cero: `plan_import` lo rechaza, no lo salta.
        return rows_for(payment(start.date().isoformat(), "txn-cero", amount=0.0))

    result = backfill(
        sales,
        branches=[BranchSpec("tecnoparque", "c-tecno")],
        start=date(2026, 1, 1), end=date(2026, 1, 31),
        fetch=fetch,
        credentials_for=lambda branch: branch,
    )

    assert isinstance(result["months"][0]["rejected"], list)
    assert result["months"][0]["rejected"], "el renglon rechazado viene completo"
    assert result["totals"]["rejected"] == 1


def test_on_month_va_dejando_rastro_mes_a_mes():
    sales = FakeSales()
    vistos = []

    backfill(
        sales,
        branches=[BranchSpec("tecnoparque", "c-tecno")],
        start=date(2026, 1, 1), end=date(2026, 3, 31),
        fetch=_fetch_one_per_month,
        credentials_for=lambda branch: branch,
        on_month=vistos.append,
    )

    assert [m["month"] for m in vistos] == ["2026-01", "2026-02", "2026-03"]
