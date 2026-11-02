"""Sacar cancelaciones no puede convertirse en borrar ventas (BOS-119).

Sin Mongo y sin red: la coleccion es un doble y las filas de Clip se inyectan.

    python -m pytest backend/tests/test_purge_cancelled.py -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from clip_api import ClipApiError, map_payment  # noqa: E402
from purge_cancelled import plan_purge, purge_all, purge_branch  # noqa: E402


def stored(receipt, *, total=108.0, day="2026-09-21", brand="le-pain-dore",
           branch="tecnoparque"):
    return {"_id": "oid-" + receipt, "dedup_key": f"clip:{receipt}",
            "receipt_no": receipt, "total": total, "business_date": day,
            "brand": brand, "payment_method": "otro", "clip_branch": branch}


class FakeResult:
    def __init__(self, n):
        self.deleted_count = n


class FakeSales:
    def __init__(self, docs):
        self.docs = list(docs)
        self.deletes = []

    def find(self, query, projection=None):
        branch = query.get("clip_branch")
        return [d for d in self.docs
                if branch is None or d.get("clip_branch", branch) == branch]

    def bulk_write(self, operations, ordered=True):
        self.deletes.extend(operations)
        return FakeResult(len(operations))


def api_row(receipt, *, status="", amount="108.00"):
    return map_payment({
        "receipt_no": receipt, "id": receipt,
        "created_at": "2026-09-21T15:35:18Z",
        "status": status, "amount": amount, "tip": "0.00", "total": amount,
        "payment_method": "OTHER", "sub_type": "CONSUMER",
        "card": {"brand": "XX", "issuer": None, "last4": "0000"},
    }, branch="tecnoparque")


def _fetch(rows):
    def fetch(credentials, start, end, **kwargs):
        # El script tiene que pedir explicitamente las canceladas: si pidiera
        # todas y filtrara por su cuenta, borraria por su propio criterio.
        assert kwargs.get("status") == "cancelled", kwargs
        return rows
    return fetch


def test_solo_saca_los_folios_que_clip_declara_cancelados():
    rows = plan_purge([stored("PKV"), stored("PBp", total=164.0)], ["clip:PKV"])

    assert [r["receipt_no"] for r in rows] == ["PKV"]
    assert rows[0]["total"] == 108.0


def test_un_folio_cancelado_que_no_esta_en_la_base_no_hace_nada():
    assert plan_purge([stored("PBp")], ["clip:OTRO"]) == []


def test_en_seco_no_borra_y_dice_que_borraria(monkeypatch):
    monkeypatch.setenv("CLIP_API_KEY_TECNOPARQUE", "k" * 8)
    monkeypatch.setenv("CLIP_SECRET_KEY_TECNOPARQUE", "s" * 8)
    sales = FakeSales([stored("PKV"), stored("PBp", total=164.0)])

    summary = purge_branch(sales, branch="tecnoparque", cafeteria_id="c-tecno",
                           commit=False, fetch=_fetch([api_row("PKV")]))

    assert summary["cancelled_in_db"] == 1
    assert summary["deleted"] == 0
    assert sales.deletes == []
    assert summary["gross_removed"] == 108.0
    # El renglon viaja en el resumen: lo que se borra se puede reconstruir.
    assert summary["rows"][0]["receipt_no"] == "PKV"


def test_con_commit_borra_solo_ese_renglon(monkeypatch):
    monkeypatch.setenv("CLIP_API_KEY_TECNOPARQUE", "k" * 8)
    monkeypatch.setenv("CLIP_SECRET_KEY_TECNOPARQUE", "s" * 8)
    sales = FakeSales([stored("PKV"), stored("PBp", total=164.0)])

    summary = purge_branch(sales, branch="tecnoparque", cafeteria_id="c-tecno",
                           commit=True, fetch=_fetch([api_row("PKV")]))

    assert summary["deleted"] == 1
    assert len(sales.deletes) == 1


def test_sin_canceladas_en_clip_no_borra_nada(monkeypatch):
    monkeypatch.setenv("CLIP_API_KEY_TECNOPARQUE", "k" * 8)
    monkeypatch.setenv("CLIP_SECRET_KEY_TECNOPARQUE", "s" * 8)
    sales = FakeSales([stored("PBp", total=164.0)])

    summary = purge_branch(sales, branch="tecnoparque", cafeteria_id="c-tecno",
                           commit=True, fetch=_fetch([]))

    assert summary["cancelled_in_db"] == 0 and sales.deletes == []


def test_una_ventana_que_la_api_rechaza_se_parte_en_vez_de_tumbar_la_sucursal(monkeypatch):
    """Con 13 meses cargados, una ventana de 30 dias cae en el tramo roto (BOS-145).

    Antes la consulta entera fallaba y Tecnoparque dejaba de poder purgarse.
    """
    monkeypatch.setenv("CLIP_API_KEY_TECNOPARQUE", "k" * 8)
    monkeypatch.setenv("CLIP_SECRET_KEY_TECNOPARQUE", "s" * 8)
    sales = FakeSales([stored("PKV", day="2025-10-21"), stored("PBp", total=164.0, day="2026-10-04")])

    def fetch(credentials, start, end, **kwargs):
        assert kwargs.get("status") == "cancelled", kwargs
        if (end.date() - start.date()).days > 40:
            raise ClipApiError("payclip.bad.request", status=400)
        return [api_row("PKV")]

    summary = purge_branch(sales, branch="tecnoparque", cafeteria_id="c-tecno",
                           commit=True, fetch=fetch)

    assert summary["unchecked"] == []
    assert summary["deleted"] == 1


def test_un_dia_que_la_api_nunca_entrega_queda_rotulado_y_marca_la_purga_incompleta(monkeypatch):
    """Un dia sin leer no es un dia sin cancelaciones: `ok` tiene que caerse."""
    monkeypatch.setenv("CLIP_API_KEY_TECNOPARQUE", "k" * 8)
    monkeypatch.setenv("CLIP_SECRET_KEY_TECNOPARQUE", "s" * 8)
    for name in ("CLIP_API_KEY_SJI", "CLIP_SECRET_KEY_SJI",
                 "CLIP_API_KEY", "CLIP_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    sales = FakeSales([stored("PKV", day="2026-02-20"), stored("PBp", total=164.0, day="2026-02-21")])

    def fetch(credentials, start, end, **kwargs):
        raise ClipApiError("payclip.bad.request", status=400)

    summary = purge_all(sales,
                        branches=[{"id": "c-tecno", "clip_branch": "tecnoparque"}],
                        commit=True, fetch=fetch)

    assert summary["ok"] is False
    assert summary["unchecked_days_total"] == 2
    assert summary["unchecked"][0]["branch"] == "tecnoparque"
    # Y no borro nada apoyandose en una lectura que no ocurrio.
    assert summary["deleted_total"] == 0 and sales.deletes == []


def test_una_credencial_muerta_no_detiene_a_la_otra_sucursal(monkeypatch):
    for name in ("CLIP_API_KEY_SJI", "CLIP_SECRET_KEY_SJI",
                 "CLIP_API_KEY", "CLIP_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CLIP_API_KEY_TECNOPARQUE", "k" * 8)
    monkeypatch.setenv("CLIP_SECRET_KEY_TECNOPARQUE", "s" * 8)

    sales = FakeSales([stored("SJI1", branch="sji", brand="casa-dorelia"),
                       stored("PKV")])
    summary = purge_all(sales, commit=False, fetch=_fetch([api_row("PKV")]))

    assert summary["ok"] is False and "sji" in summary["failed"]
    assert summary["cancelled_in_db_total"] == 1
