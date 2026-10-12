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
    render_comment,
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


def fake_loader(calls, *, inserted=1, fails=(), skipped=0, skipped_reasons=None,
                rows_seen=None):
    def loader(sales, **kwargs):
        calls.append(kwargs)
        if kwargs["branch"] in fails:
            raise ClipAuthError(f"Clip rechazo la credencial de {kwargs['branch']} con 401")
        loaded = {"inserted": inserted, "to_insert": inserted, "skipped": skipped,
                  "skipped_reasons": skipped_reasons or {},
                  "gross_total": 100.0 * inserted}
        if rows_seen is not None:
            loaded["rows_seen"] = rows_seen
        return loaded
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


# --------------------------------------------------------------------------
# Cobros vistos: la prueba de que Clip contesto, insertara o no (BOS-232)
# --------------------------------------------------------------------------

def test_un_dia_reimportado_inserta_cero_y_AUN_ASI_prueba_que_clip_contesto():
    """El control positivo que el comentario perdia.

    `--catch-up 1` sobre un dia ya cargado inserta 0 y deja `db_rows` igual:
    identico a una corrida que nunca pregunto. Lo que los separa es que Clip
    devolvio 5 renglones y los 5 se saltaron por `ya_importada`.
    """
    result = run_daily(FakeSales(counts={("c-sji", "2026-10-01"): 5}), day="2026-10-01",
                       commit=True, branches=BRANCHES[:1],
                       loader=fake_loader([], inserted=0, skipped=5,
                                          skipped_reasons={"ya_importada": 5},
                                          rows_seen=5))

    sji = result["branches"][0]
    assert sji["inserted"] == 0           # no se escribio nada
    assert sji["seen"] == 5               # y aun asi Clip contesto con contenido
    assert sji["skipped_reasons"] == {"ya_importada": 5}
    assert result["seen_total"] == 5


def test_los_cobros_vistos_salen_de_la_frontera_de_la_api_no_de_la_suma():
    """`rows_seen` manda: lo cuenta el cargador donde llegan las filas."""
    result = run_daily(FakeSales(), day="2026-10-01", branches=BRANCHES[:1],
                       loader=fake_loader([], inserted=2, skipped=1, rows_seen=7))

    assert result["branches"][0]["seen"] == 7  # 7, no 3: hubo 4 rechazadas


def test_sin_rows_seen_los_cobros_vistos_caen_a_insertables_mas_saltados():
    """Un cargador viejo (o un doble) sigue dando una cifra legible."""
    result = run_daily(FakeSales(), day="2026-10-01", branches=BRANCHES[:1],
                       loader=fake_loader([], inserted=2, skipped=3))

    assert result["branches"][0]["seen"] == 5


def test_una_celda_que_fallo_no_reporta_CERO_cobros_vistos():
    """`None`, no 0: no se sabe cuantos habia. Un 0 mentiria."""
    result = run_daily(FakeSales(), day="2026-10-01", branches=BRANCHES,
                       loader=fake_loader([], fails=("sji",)))

    sji, tecno = result["branches"]
    assert sji["seen"] is None
    assert tecno["seen"] == 1
    assert result["seen_total"] == 1  # solo suma lo que contesto


def test_run_days_dice_con_un_booleano_que_clip_contesto_vacio():
    """El caso del 12/10: domingo cerrado + dia en curso antes de abrir."""
    result = run_days(FakeSales(), days=["2026-10-11", "2026-10-12"], commit=True,
                      branches=BRANCHES, loader=fake_loader([], inserted=0, rows_seen=0))

    assert result["seen_total"] == 0
    assert result["clip_answered_empty"] is True
    assert result["days_requested"] == ["2026-10-11", "2026-10-12"]
    assert result["ok"] is True  # contestar vacio no es una falla


def test_un_solo_cobro_en_cualquier_celda_basta_para_el_control_positivo():
    sales = FakeSales()
    result = run_days(sales, days=["2026-10-11", "2026-10-12"], branches=BRANCHES,
                      loader=fake_loader([], inserted=1, rows_seen=1))

    assert result["seen_total"] == 4
    assert result["clip_answered_empty"] is False


def test_si_NINGUNA_celda_contesto_no_se_declara_que_clip_contesto_vacio():
    """Cero por credenciales muertas no es cero medido. No se puede confundir."""
    result = run_days(FakeSales(), days=["2026-10-12"], branches=BRANCHES,
                      loader=fake_loader([], fails=("sji", "tecnoparque")))

    assert result["seen_total"] == 0
    assert result["clip_answered_empty"] is False
    assert result["failed"] == ["2026-10-12:sji", "2026-10-12:tecnoparque"]


def test_los_motivos_de_salto_se_suman_de_toda_la_corrida():
    result = run_days(FakeSales(), days=["2026-10-11", "2026-10-12"], branches=BRANCHES,
                      loader=fake_loader([], inserted=0, skipped=2,
                                         skipped_reasons={"ya_importada": 2}, rows_seen=2))

    assert result["skipped_reasons_total"] == {"ya_importada": 8}


# --------------------------------------------------------------------------
# El comentario de cierre, ya armado
# --------------------------------------------------------------------------

def test_el_comentario_trae_una_fila_por_sucursal_x_dia_con_los_cobros_vistos():
    result = run_days(FakeSales(counts={("c-sji", "2026-10-11"): 3}),
                      days=["2026-10-11", "2026-10-12"], commit=True, branches=BRANCHES,
                      loader=fake_loader([], inserted=0, skipped=3,
                                         skipped_reasons={"ya_importada": 3}, rows_seen=3))

    comentario = render_comment(result)
    filas = [l for l in comentario.splitlines() if l.startswith("| 2026-")]

    assert len(filas) == 4  # 2 dias x 2 sucursales
    assert "cobros vistos" in comentario
    assert "ya_importada 3" in comentario
    assert "2026-10-11 | sji (`c-sji`)" in filas[0]


def test_el_comentario_DICE_que_no_regreso_ni_un_renglon():
    """Criterio 2: con todo en cero, el comentario es la unica evidencia."""
    result = run_days(FakeSales(), days=["2026-10-11", "2026-10-12"], commit=True,
                      branches=BRANCHES, loader=fake_loader([], inserted=0, rows_seen=0))

    comentario = render_comment(result)
    assert "no obtuvo ni un renglon de ninguno de los dias pedidos" in comentario
    assert "unica evidencia" in comentario


def test_el_comentario_no_grita_cuando_si_hubo_cobros():
    result = run_days(FakeSales(), days=["2026-10-12"], commit=True, branches=BRANCHES,
                      loader=fake_loader([], inserted=3, rows_seen=3))

    comentario = render_comment(result)
    assert "no obtuvo ni un renglon" not in comentario
    assert "Cobros vistos en toda la corrida: 6" in comentario


def test_el_comentario_separa_la_celda_que_no_contesto_del_cero_medido():
    result = run_days(FakeSales(), days=["2026-10-12"], commit=True, branches=BRANCHES,
                      loader=fake_loader([], inserted=0, rows_seen=0, fails=("sji",)))

    comentario = render_comment(result)
    assert "**no contesto**" in comentario        # la celda de sji
    assert "2026-10-12:sji" in comentario         # con su error nombrado
    assert "401" in comentario
    assert "no obtuvo ni un renglon" not in comentario  # tecno si fue medido
