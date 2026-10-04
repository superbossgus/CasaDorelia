"""El disparo diario pide el dia de operacion correcto y aisla la sucursal que falla.

Sin Mongo y sin red: la coleccion es un doble y el cargador se sustituye por una
funcion que registra con que rango lo llamaron.
"""
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from clip_api import ClipAuthError  # noqa: E402
from clip_daily import (  # noqa: E402
    days_to_load,
    main,
    run_daily,
    run_days,
    target_business_date,
)

BRANCHES = [
    {"id": "c-sji", "clip_branch": "sji", "is_active": True},
    {"id": "c-tecno", "clip_branch": "tecnoparque", "is_active": True},
]


class FakeSales:
    """Solo necesita contar: la carga de verdad la hace el `loader` inyectado."""

    def __init__(self, counts=None):
        self.counts = counts or {}
        self.counted = []

    def count_documents(self, query):
        self.counted.append(query)
        return self.counts.get((query.get("cafeteria_id"), query.get("business_date")), 0)


def fake_loader(calls, *, inserted=1, fails=()):
    def loader(sales, **kwargs):
        calls.append(kwargs)
        if kwargs["branch"] in fails:
            raise ClipAuthError(f"Clip rechazo la credencial de {kwargs['branch']} con 401")
        return {"inserted": inserted, "to_insert": inserted, "skipped": 0,
                "skipped_reasons": {}, "gross_total": 100.0 * inserted}
    return loader


# --------------------------------------------------------------------------
# Que dia es "hoy"
# --------------------------------------------------------------------------

def test_el_dia_sale_del_huso_del_negocio_no_de_utc():
    """El disparo de las 01:45Z es la tarde del dia ANTERIOR en la cafeteria.

    Esta es la razon de existir del modulo: con `utcnow().date()` el corte de las
    20:00 CDMX pediria el dia que apenas empieza y saldria en cero.
    """
    las_0145z = datetime(2026, 10, 2, 1, 45, tzinfo=timezone.utc)

    assert las_0145z.date().isoformat() == "2026-10-02"      # lo que diria UTC
    assert target_business_date(las_0145z) == "2026-10-01"    # el dia que opero


def test_el_disparo_de_la_manana_cae_en_el_mismo_dia():
    las_1345z = datetime(2026, 10, 1, 13, 45, tzinfo=timezone.utc)
    assert target_business_date(las_1345z) == "2026-10-01"


def test_days_back_resta_dias_de_operacion():
    las_0145z = datetime(2026, 10, 2, 1, 45, tzinfo=timezone.utc)
    assert target_business_date(las_0145z, days_back=1) == "2026-09-30"


# --------------------------------------------------------------------------
# Que dias carga cada disparo
# --------------------------------------------------------------------------

def test_la_tarde_carga_solo_el_dia_en_curso():
    las_0145z = datetime(2026, 10, 2, 1, 45, tzinfo=timezone.utc)
    assert days_to_load(now=las_0145z) == ["2026-10-01"]


def test_la_mañana_cierra_ayer_antes_de_sembrar_hoy():
    """El hueco que cierra `--catch-up 1`.

    El disparo de la tarde corre a las 19:45 locales: la venta de 19:45 a cerrar
    no la vio. Si la mañana pidiera solo "hoy", esas horas no se cargarian nunca.
    El orden importa: ayer primero, para que el corte de las 08:00 lea un dia
    anterior ya cerrado.
    """
    las_1345z = datetime(2026, 10, 2, 13, 45, tzinfo=timezone.utc)
    assert days_to_load(catch_up=1, now=las_1345z) == ["2026-10-01", "2026-10-02"]


def test_una_fecha_explicita_manda_sobre_el_catch_up():
    assert days_to_load(date="2026-09-29", catch_up=5) == ["2026-09-29"]


def test_un_catch_up_negativo_se_rechaza():
    with pytest.raises(ValueError, match="catch-up"):
        days_to_load(catch_up=-1)


def test_run_days_recorre_los_dias_y_suma_lo_insertado():
    calls = []
    result = run_days(FakeSales(), days=["2026-09-30", "2026-10-01"], commit=True,
                      branches=BRANCHES, loader=fake_loader(calls))

    assert [c["cafeteria_id"] for c in calls] == ["c-sji", "c-tecno"] * 2
    assert [d["business_date"] for d in result["days"]] == ["2026-09-30", "2026-10-01"]
    assert result["inserted_total"] == 4
    assert result["ok"] is True


def test_run_days_nombra_el_dia_y_la_sucursal_que_fallaron():
    result = run_days(FakeSales(), days=["2026-09-30", "2026-10-01"], branches=BRANCHES,
                      loader=fake_loader([], fails=("sji",)))

    assert result["failed"] == ["2026-09-30:sji", "2026-10-01:sji"]
    assert result["ok"] is False


# --------------------------------------------------------------------------
# El rango que se le pide a Clip
# --------------------------------------------------------------------------

def test_el_rango_cubre_el_dia_local_completo():
    """`06:00Z` del dia a `05:59:59Z` del siguiente: las 24 h de operacion."""
    calls = []
    run_daily(FakeSales(), day="2026-10-01", commit=True, branches=BRANCHES,
              loader=fake_loader(calls))

    inicio = calls[0]["start"].astimezone(timezone.utc).isoformat()
    fin = calls[0]["end"].astimezone(timezone.utc).isoformat()
    assert inicio == "2026-10-01T06:00:00+00:00"
    assert fin == "2026-10-02T05:59:59+00:00"


def test_carga_todas_las_sucursales_con_su_cafeteria():
    calls = []
    run_daily(FakeSales(), day="2026-10-01", commit=True, branches=BRANCHES,
              loader=fake_loader(calls))

    assert [(c["branch"], c["cafeteria_id"]) for c in calls] == [
        ("sji", "c-sji"), ("tecnoparque", "c-tecno"),
    ]
    assert all(c["commit"] is True for c in calls)


def test_en_seco_no_pide_commit_al_cargador():
    calls = []
    result = run_daily(FakeSales(), day="2026-10-01", branches=BRANCHES,
                       loader=fake_loader(calls))

    assert all(c["commit"] is False for c in calls)
    assert result["committed"] is False


def test_una_sucursal_inactiva_se_salta():
    calls = []
    branches = [dict(BRANCHES[0], is_active=False), BRANCHES[1]]
    run_daily(FakeSales(), day="2026-10-01", branches=branches,
              loader=fake_loader(calls))

    assert [c["branch"] for c in calls] == ["tecnoparque"]


# --------------------------------------------------------------------------
# Fallas
# --------------------------------------------------------------------------

def test_una_credencial_muerta_no_cancela_la_otra_sucursal():
    calls = []
    result = run_daily(FakeSales(), day="2026-10-01", commit=True, branches=BRANCHES,
                       loader=fake_loader(calls, fails=("sji",)))

    assert [c["branch"] for c in calls] == ["sji", "tecnoparque"]
    assert result["failed_branches"] == ["sji"]
    assert result["ok"] is False

    sji, tecno = result["branches"]
    assert sji["ok"] is False and "401" in sji["error"]
    assert tecno["ok"] is True and tecno["inserted"] == 1


def test_el_error_no_filtra_la_credencial():
    def loader(sales, **kwargs):
        raise ClipAuthError("Clip rechazo la credencial de sji (api_key ...9f3a) con 401")

    result = run_daily(FakeSales(), day="2026-10-01", branches=BRANCHES[:1], loader=loader)
    assert "9f3a" in result["branches"][0]["error"]  # solo los ultimos 4, como el fingerprint
    assert "secret" not in result["branches"][0]["error"].lower()


def test_main_sale_con_1_si_alguna_sucursal_fallo(monkeypatch):
    """El disparo programado se tiene que notar, no silenciarse."""
    monkeypatch.setattr("clip_daily.open_sales_collection", lambda *a: FakeSales())
    monkeypatch.setattr("clip_daily.run_daily",
                        lambda *a, **k: {"business_date": "2026-10-01", "branches": [],
                                         "failed_branches": ["sji"]})

    assert main(["--db", "x", "--date", "2026-10-01", "--commit"]) == 1


def test_main_sale_con_0_cuando_todo_cargo(monkeypatch):
    monkeypatch.setattr("clip_daily.open_sales_collection", lambda *a: FakeSales())
    monkeypatch.setattr("clip_daily.run_daily",
                        lambda *a, **k: {"business_date": "2026-10-01", "branches": [],
                                         "failed_branches": []})

    assert main(["--db", "x", "--date", "2026-10-01", "--commit"]) == 0


# --------------------------------------------------------------------------
# Evidencia de cierre
# --------------------------------------------------------------------------

def test_reporta_cuantos_renglones_quedaron_en_la_base():
    """Cero con `ok: True` es "no cobro con tarjeta", no "no corrio"."""
    sales = FakeSales(counts={("c-sji", "2026-10-01"): 5})
    result = run_daily(sales, day="2026-10-01", commit=True, branches=BRANCHES,
                       loader=fake_loader([], inserted=5))

    sji, tecno = result["branches"]
    assert sji["db_rows"] == 5
    assert tecno["ok"] is True and tecno["db_rows"] == 0


def test_el_conteo_filtra_por_tenant_cuando_hay():
    sales = FakeSales()
    run_daily(sales, day="2026-10-01", branches=BRANCHES[:1], tenant_id="t-casa",
              loader=fake_loader([]))

    assert sales.counted[0]["tenant_id"] == "t-casa"


def test_siempre_declara_que_falta_el_efectivo():
    result = run_daily(FakeSales(), day="2026-10-01", branches=BRANCHES,
                       loader=fake_loader([]))
    assert result["includes_cash"] is False
