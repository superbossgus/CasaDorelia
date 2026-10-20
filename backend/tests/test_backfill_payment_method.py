"""El re-etiquetado de metodo de pago no puede mover dinero ni llaves (BOS-119).

Sin Mongo y sin red: la coleccion es un doble que apunta las escrituras, y las
filas "de Clip" se inyectan por el parametro `fetch`.

    python -m pytest backend/tests/test_backfill_payment_method.py -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backfill_payment_method import (  # noqa: E402
    MUTABLE_FIELDS,
    plan_relabel,
    relabel_all,
    relabel_branch,
)
from clip_api import map_payment  # noqa: E402


def stored(dedup_key, *, method="tarjeta", notes="NFC_EMV_SIGNATURE MC ****0579",
           total=164.0, day="2026-09-30"):
    return {"_id": "oid-" + dedup_key, "dedup_key": dedup_key, "payment_method": method,
            "notes": notes, "total": total, "business_date": day}


class FakeResult:
    def __init__(self, n):
        self.modified_count = n


class FakeSales:
    """Coleccion de mentiras: devuelve lo que se le dio y guarda lo que se escribio."""

    def __init__(self, docs):
        self.docs = list(docs)
        self.writes = []

    def find(self, query, projection=None):
        branch = query.get("clip_branch")
        return [d for d in self.docs
                if branch is None or d.get("clip_branch", branch) == branch]

    def bulk_write(self, operations, ordered=True):
        self.writes.extend(operations)
        return FakeResult(len(operations))


def api_row(receipt, **overrides):
    """Una fila ya mapeada, como la entrega `clip_api.fetch_rows`."""
    base = {
        "receipt_no": receipt, "id": receipt,
        "created_at": "2026-09-30T20:45:24Z",
        "status": "paid", "amount": "164.00", "tip": "0.00", "total": "164.00",
        "payment_method": "CREDIT", "sub_type": "NFC_EMV_SIGNATURE",
        "card": {"brand": "MC", "issuer": None, "last4": "0579"},
    }
    base.update(overrides)
    return map_payment(base, branch="tecnoparque")


# --------------------------------------------------------------------------
# Que decide cambiar
# --------------------------------------------------------------------------

def test_un_vale_cargado_como_tarjeta_se_re_etiqueta():
    fresh = {"clip:PMZ": api_row("PMZ", payment_method="OTHER", sub_type="EMV_SIGNATURE",
                                 card={"brand": "CR", "issuer": "PLUXEE MEXICO",
                                       "last4": "3702"})}
    plan = plan_relabel([stored("clip:PMZ")], fresh)

    assert len(plan["to_update"]) == 1
    cambio = plan["to_update"][0]
    assert cambio["from"]["payment_method"] == "tarjeta"
    assert cambio["to"]["payment_method"] == "vales"
    assert "PLUXEE MEXICO" in cambio["to"]["notes"]


def test_una_tarjeta_bien_etiquetada_no_se_toca():
    fresh = {"clip:PBp": api_row("PBp")}
    plan = plan_relabel([stored("clip:PBp")], fresh)

    assert plan["to_update"] == []
    assert plan["unchanged"] == ["clip:PBp"]


def test_lo_que_la_api_ya_no_entrega_se_reporta_y_se_deja_quieto():
    """Una ventana que quedo fuera del rango no es razon para borrar un rotulo."""
    plan = plan_relabel([stored("clip:VIEJO")], {})

    assert plan["to_update"] == []
    assert plan["missing_in_api"] == ["clip:VIEJO"]


def test_solo_toca_rotulos_y_nunca_dinero_ni_llaves():
    fresh = {"clip:PKV": api_row("PKV", payment_method="OTHER", sub_type="CONSUMER",
                                 amount="108.00", total="108.00",
                                 card={"brand": "XX", "issuer": None, "last4": "0000"})}
    plan = plan_relabel([stored("clip:PKV", total=108.0)], fresh)

    escrito = plan["to_update"][0]["to"]
    assert set(escrito) <= set(MUTABLE_FIELDS)
    for prohibido in ("dedup_key", "id", "total", "subtotal", "tax", "business_date",
                      "created_at", "brand", "cafeteria_id"):
        assert prohibido not in escrito


# --------------------------------------------------------------------------
# Que escribe, y que no escribe en seco
# --------------------------------------------------------------------------

def _fetch(rows):
    def fetch(credentials, start, end, **kwargs):
        return rows
    return fetch


def test_en_seco_no_escribe_nada(monkeypatch):
    monkeypatch.setenv("CLIP_API_KEY_TECNOPARQUE", "k" * 8)
    monkeypatch.setenv("CLIP_SECRET_KEY_TECNOPARQUE", "s" * 8)
    sales = FakeSales([stored("clip:PMZ")])

    summary = relabel_branch(
        sales, branch="tecnoparque", cafeteria_id="c-tecno", commit=False,
        fetch=_fetch([api_row("PMZ", payment_method="OTHER", sub_type="EMV_SIGNATURE",
                              card={"brand": "CR", "issuer": "EDENRED", "last4": "2791"})]),
    )

    assert summary["to_update"] == 1
    assert summary["updated"] == 0
    assert sales.writes == []
    assert summary["method_changed"] == 1 and summary["notes_only"] == 0
    assert summary["by_method"]["tarjeta -> vales"] == {"rows": 1, "gross": 164.0}


def test_un_cambio_de_notas_no_se_cuenta_como_cobro_mal_etiquetado():
    """Reponer el emisor no mueve dinero de cajon; el resumen lo separa.

    Si las dos cosas se contaran juntas, "118 renglones tocados" se leeria como
    118 cobros mal cobrados, cuando los mal etiquetados eran 9.
    """
    fresh = {"clip:PBp": api_row("PBp", card={"brand": "MC", "issuer": "BBVA",
                                              "last4": "0579"})}
    plan = plan_relabel([stored("clip:PBp")], fresh)

    cambio = plan["to_update"][0]
    assert "payment_method" not in cambio["to"]
    assert "BBVA" in cambio["to"]["notes"]


def test_con_commit_escribe_una_vez_por_renglon(monkeypatch):
    monkeypatch.setenv("CLIP_API_KEY_TECNOPARQUE", "k" * 8)
    monkeypatch.setenv("CLIP_SECRET_KEY_TECNOPARQUE", "s" * 8)
    sales = FakeSales([stored("clip:PMZ"), stored("clip:PBp")])

    summary = relabel_branch(
        sales, branch="tecnoparque", cafeteria_id="c-tecno", commit=True,
        fetch=_fetch([
            api_row("PMZ", payment_method="OTHER", sub_type="EMV_SIGNATURE",
                    card={"brand": "CR", "issuer": "EDENRED", "last4": "2791"}),
            api_row("PBp"),
        ]),
    )

    assert summary["to_update"] == 1 and summary["updated"] == 1
    assert len(sales.writes) == 1


def test_un_cobro_que_falta_en_la_base_se_reporta_no_se_inserta(monkeypatch):
    monkeypatch.setenv("CLIP_API_KEY_TECNOPARQUE", "k" * 8)
    monkeypatch.setenv("CLIP_SECRET_KEY_TECNOPARQUE", "s" * 8)
    sales = FakeSales([stored("clip:PBp")])

    summary = relabel_branch(
        sales, branch="tecnoparque", cafeteria_id="c-tecno", commit=True,
        fetch=_fetch([api_row("PBp"), api_row("NUEVO")]),
    )

    assert summary["missing_in_db"] == ["clip:NUEVO"]
    assert sales.writes == []


def test_una_sucursal_sin_ventas_no_le_pide_nada_a_clip():
    """Sin renglones no hay rango que pedir, y no hay credencial que exigir."""
    summary = relabel_branch(FakeSales([]), branch="sji", cafeteria_id="c-sji")

    assert summary["stored"] == 0 and summary["to_update"] == 0


def test_una_credencial_muerta_no_detiene_a_la_otra_sucursal(monkeypatch):
    monkeypatch.delenv("CLIP_API_KEY_SJI", raising=False)
    monkeypatch.delenv("CLIP_SECRET_KEY_SJI", raising=False)
    monkeypatch.delenv("CLIP_API_KEY", raising=False)
    monkeypatch.delenv("CLIP_SECRET_KEY", raising=False)
    monkeypatch.setenv("CLIP_API_KEY_TECNOPARQUE", "k" * 8)
    monkeypatch.setenv("CLIP_SECRET_KEY_TECNOPARQUE", "s" * 8)

    sales = FakeSales([
        dict(stored("clip:SJI1"), clip_branch="sji"),
        dict(stored("clip:PMZ"), clip_branch="tecnoparque"),
    ])
    summary = relabel_all(
        sales, commit=False,
        fetch=_fetch([api_row("PMZ", payment_method="OTHER", sub_type="EMV_SIGNATURE",
                              card={"brand": "CR", "issuer": "EDENRED", "last4": "2791"})]),
    )

    assert summary["ok"] is False
    assert "sji" in summary["failed"]
    assert summary["to_update_total"] == 1  # Tecnoparque si se planeo


def test_sin_dia_de_operacion_manda_al_backfill_que_corresponde(monkeypatch):
    monkeypatch.setenv("CLIP_API_KEY_TECNOPARQUE", "k" * 8)
    monkeypatch.setenv("CLIP_SECRET_KEY_TECNOPARQUE", "s" * 8)
    sales = FakeSales([{"_id": "x", "dedup_key": "clip:A", "payment_method": "tarjeta",
                        "total": 10.0}])

    with pytest.raises(Exception, match="backfill_business_date"):
        relabel_branch(sales, branch="tecnoparque", cafeteria_id="c-tecno")
