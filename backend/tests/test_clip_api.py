"""
Pruebas del cliente de la API de Clip (`backend/clip_api.py`).

Unitarias y **sin red**: el transporte HTTP se inyecta, asi que se puede probar
la paginacion, el corte de ventanas de un mes, los errores de credencial y el
mapeo de montos sin credenciales reales y sin pegarle a Clip.

    python -m pytest backend/tests/test_clip_api.py -q
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clip_api import (  # noqa: E402
    MAX_PAGES_PER_WINDOW,
    ClipApiError,
    ClipAuthError,
    ClipCredentials,
    ClipRateLimitError,
    add_one_month,
    branch_slug,
    build_payments_url,
    credential_env_names,
    fetch_rows,
    iter_payments,
    load_credentials,
    map_payment,
    split_window,
    summarize_census,
    summarize_corte,
)
from sales_import import SOURCE_CLIP_API, normalize_row, plan_import  # noqa: E402

CREDS = ClipCredentials(branch="sji", api_key="aba5bd64-9608-47a8-b035-5e649390ce5b",
                        secret_key="f66b435d-1fa1-4994-02b6-0ba632ba18bd")
NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def payment(**overrides):
    base = {
        "receipt_no": "ABC123",
        "id": "txn_001",
        "created_at": "2026-09-28T20:30:00.000Z",
        "status": "paid",
        "amount": 116.0,
        "tip": 20.0,
        "total": 136.0,
        "payment_method": "CREDIT",
        "sub_type": "EMV_SIGNATURE",
        "card": {"brand": "VISA", "last4": "4242"},
        "currency": "MXN",
    }
    base.update(overrides)
    return base


class FakeTransport:
    """Devuelve respuestas programadas y guarda las URLs que se pidieron."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []
        self.headers = []

    def __call__(self, url, headers):
        self.urls.append(url)
        self.headers.append(dict(headers))
        if not self.responses:
            raise AssertionError(f"el cliente pidio una pagina de mas: {url}")
        status, payload = self.responses.pop(0)
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        return status, body


def page(items, token=None):
    body = {"payments": items}
    if token:
        body["meta"] = {"pagination_token": token}
    return 200, body


# --------------------------------------------------------------------------
# Credenciales
# --------------------------------------------------------------------------

def test_credencial_se_lee_por_sucursal():
    env = {"CLIP_API_KEY_SJI": "k-sji", "CLIP_SECRET_KEY_SJI": "s-sji",
           "CLIP_API_KEY_TECNOPARQUE": "k-tec", "CLIP_SECRET_KEY_TECNOPARQUE": "s-tec"}
    assert load_credentials("sji", env).api_key == "k-sji"
    assert load_credentials("Tecnoparque", env).api_key == "k-tec"


def test_credencial_cae_a_la_variable_generica():
    env = {"CLIP_API_KEY": "k", "CLIP_SECRET_KEY": "s"}
    creds = load_credentials("sji", env)
    assert (creds.api_key, creds.secret_key) == ("k", "s")


def test_credencial_faltante_dice_que_variables_cargar():
    with pytest.raises(ClipAuthError) as exc:
        load_credentials("Casa Dorelia SJI", {})
    message = str(exc.value)
    assert "CLIP_API_KEY_CASA_DORELIA_SJI" in message
    assert "CLIP_SECRET_KEY_CASA_DORELIA_SJI" in message


def test_secret_key_sin_api_key_no_se_da_por_valida():
    with pytest.raises(ClipAuthError):
        load_credentials("sji", {"CLIP_SECRET_KEY_SJI": "s"})


def test_nombres_de_variable_normalizan_la_sucursal():
    assert branch_slug("Casa Dorelia SJI") == "CASA_DORELIA_SJI"
    assert credential_env_names("sji") == ("CLIP_API_KEY_SJI", "CLIP_SECRET_KEY_SJI")


def test_token_basic_es_base64_de_api_key_y_secreto():
    # El ejemplo de la documentacion de Clip, para no invertir el orden del par.
    assert CREDS.auth_header() == (
        "Basic YWJhNWJkNjQtOTYwOC00N2E4LWIwMzUtNWU2NDkzOTBjZTViOmY2NmI0MzVkLTFmYTEtNDk5NC0wMmI2LTBiYTYzMmJhMThiZA=="
    )


def test_el_repr_no_filtra_la_credencial():
    texto = f"{CREDS!r} {CREDS}"
    assert CREDS.secret_key not in texto
    assert CREDS.api_key not in texto
    assert "ce5b" in texto  # solo los ultimos 4 del api_key, para poder identificarla


# --------------------------------------------------------------------------
# Ventanas y URL
# --------------------------------------------------------------------------

def test_rango_largo_se_parte_en_ventanas_de_un_mes():
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 1, tzinfo=timezone.utc)
    windows = split_window(start, end, now=NOW)
    assert len(windows) == 3
    assert windows[0][0] == start
    assert windows[-1][1] == end
    for window_start, window_end in windows:
        assert window_end <= add_one_month(window_start)
    # Sin huecos ni traslapes: el final de una es el inicio de la siguiente.
    for previous, following in zip(windows, windows[1:]):
        assert previous[1] == following[0]


def test_ninguna_ventana_pasa_de_un_mes_de_calendario_ni_en_febrero():
    """La regresion de BOS-119: 720 h es mas que un mes si se arranca en febrero.

    Con un delta fijo de 720 h, la ventana que arranca el 6 de febrero termina
    el 8 de marzo y Clip contesta 400 (medido). Eso tumbaba el jalon completo de
    un año de dinero una vez al año.
    """
    windows = split_window(datetime(2026, 2, 6, 22, 8, tzinfo=timezone.utc),
                           datetime(2026, 4, 10, 22, 8, tzinfo=timezone.utc),
                           now=datetime(2026, 4, 11, tzinfo=timezone.utc))
    assert windows[0][1] == datetime(2026, 3, 6, 22, 8, tzinfo=timezone.utc)
    for window_start, window_end in windows:
        assert window_end <= add_one_month(window_start)


def test_un_mes_mas_adelante_recorta_el_dia_que_no_existe():
    # 31 de enero + 1 mes no es el 31 de febrero: se recorta al 28.
    assert add_one_month(datetime(2026, 1, 31, 7, 0, tzinfo=timezone.utc)) == \
        datetime(2026, 2, 28, 7, 0, tzinfo=timezone.utc)
    # Y en año bisiesto, al 29.
    assert add_one_month(datetime(2028, 1, 31, tzinfo=timezone.utc)) == \
        datetime(2028, 2, 29, tzinfo=timezone.utc)
    # Diciembre cambia de año.
    assert add_one_month(datetime(2026, 12, 15, tzinfo=timezone.utc)) == \
        datetime(2027, 1, 15, tzinfo=timezone.utc)


def test_rango_corto_es_una_sola_ventana():
    windows = split_window(datetime(2026, 9, 21, tzinfo=timezone.utc),
                           datetime(2026, 10, 1, tzinfo=timezone.utc), now=NOW)
    assert len(windows) == 1


def test_rango_invertido_falla_antes_de_llamar():
    with pytest.raises(ClipApiError, match="al reves"):
        split_window(datetime(2026, 10, 1, tzinfo=timezone.utc),
                     datetime(2026, 9, 21, tzinfo=timezone.utc), now=NOW)


def test_rango_de_mas_de_un_ano_manda_al_export():
    with pytest.raises(ClipApiError, match="export del panel"):
        split_window(datetime(2024, 1, 1, tzinfo=timezone.utc),
                     datetime(2026, 10, 1, tzinfo=timezone.utc), now=NOW)


def test_fecha_sin_offset_se_entiende_hora_del_negocio():
    # 00:00 local (UTC-6) es 06:00Z: si se leyera como UTC el corte se correria
    # un dia en las ventas de la madrugada.
    windows = split_window(datetime(2026, 9, 30, 0, 0), datetime(2026, 9, 30, 23, 0), now=NOW)
    assert windows[0][0] == datetime(2026, 9, 30, 6, 0, tzinfo=timezone.utc)


def test_url_lleva_los_parametros_que_pide_clip():
    url = build_payments_url(datetime(2026, 9, 28, tzinfo=timezone.utc),
                             datetime(2026, 9, 29, tzinfo=timezone.utc),
                             status="paid", limit=100, pagination_token="tok")
    assert url.startswith("https://api-gw.payclip.com/payments?")
    assert "from=2026-09-28T00%3A00%3A00.000Z" in url
    assert "to=2026-09-29T00%3A00%3A00.000Z" in url
    assert "limit=100" in url and "status=paid" in url and "pagination_token=tok" in url


def test_limit_fuera_de_rango_falla():
    with pytest.raises(ClipApiError, match="limit"):
        build_payments_url(datetime(2026, 9, 28, tzinfo=timezone.utc),
                           datetime(2026, 9, 29, tzinfo=timezone.utc), limit=500)


def test_status_invalido_falla():
    with pytest.raises(ClipApiError, match="status"):
        build_payments_url(datetime(2026, 9, 28, tzinfo=timezone.utc),
                           datetime(2026, 9, 29, tzinfo=timezone.utc), status="refunded")


# --------------------------------------------------------------------------
# Paginacion y errores
# --------------------------------------------------------------------------

def test_pagina_hasta_que_se_acaba_el_token():
    transport = FakeTransport([
        page([payment(id="a")], token="t1"),
        page([payment(id="b")], token="t2"),
        page([payment(id="c")]),
    ])
    items = list(iter_payments(CREDS, datetime(2026, 9, 28, tzinfo=timezone.utc),
                               datetime(2026, 9, 29, tzinfo=timezone.utc),
                               transport=transport, now=NOW))
    assert [item["id"] for item in items] == ["a", "b", "c"]
    assert "pagination_token=t1" in transport.urls[1]
    assert "pagination_token=t2" in transport.urls[2]


def test_cada_ventana_arranca_su_propia_paginacion():
    transport = FakeTransport([page([payment(id="v1")]), page([payment(id="v2")])])
    items = list(iter_payments(CREDS, datetime(2026, 7, 1, tzinfo=timezone.utc),
                               datetime(2026, 8, 15, tzinfo=timezone.utc),
                               transport=transport, now=NOW))
    assert len(items) == 2
    assert len(transport.urls) == 2
    assert "pagination_token" not in transport.urls[1]


def test_token_repetido_no_gira_en_falso():
    transport = FakeTransport([page([payment()], token="t1"), page([payment()], token="t1")])
    with pytest.raises(ClipApiError, match="repitio"):
        list(iter_payments(CREDS, datetime(2026, 9, 28, tzinfo=timezone.utc),
                           datetime(2026, 9, 29, tzinfo=timezone.utc),
                           transport=transport, now=NOW))


def test_401_es_error_de_credencial_y_no_se_reintenta():
    transport = FakeTransport([(401, {"message": "invalid credentials"})])
    with pytest.raises(ClipAuthError) as exc:
        list(iter_payments(CREDS, datetime(2026, 9, 28, tzinfo=timezone.utc),
                           datetime(2026, 9, 29, tzinfo=timezone.utc),
                           transport=transport, now=NOW))
    assert exc.value.status == 401
    assert transport.urls and len(transport.urls) == 1
    # El error identifica la credencial sin exponerla.
    assert CREDS.secret_key not in str(exc.value)
    assert CREDS.api_key not in str(exc.value)


def test_500_se_reintenta_y_luego_pasa():
    dormidas = []
    transport = FakeTransport([(500, {"message": "boom"}), page([payment(id="ok")])])
    items = list(iter_payments(CREDS, datetime(2026, 9, 28, tzinfo=timezone.utc),
                               datetime(2026, 9, 29, tzinfo=timezone.utc),
                               transport=transport, now=NOW, sleep=dormidas.append))
    assert [item["id"] for item in items] == ["ok"]
    assert dormidas == [1.0]


def test_429_persistente_es_error_de_tasa():
    transport = FakeTransport([(429, {"message": "slow down"})] * 4)
    with pytest.raises(ClipRateLimitError):
        list(iter_payments(CREDS, datetime(2026, 9, 28, tzinfo=timezone.utc),
                           datetime(2026, 9, 29, tzinfo=timezone.utc),
                           transport=transport, now=NOW, sleep=lambda _s: None))


def test_error_desconocido_conserva_el_motivo():
    transport = FakeTransport([(422, {"message": "from es obligatorio"})])
    with pytest.raises(ClipApiError, match="from es obligatorio"):
        list(iter_payments(CREDS, datetime(2026, 9, 28, tzinfo=timezone.utc),
                           datetime(2026, 9, 29, tzinfo=timezone.utc),
                           transport=transport, now=NOW))


def test_respuesta_sin_lista_dice_que_llaves_vio():
    transport = FakeTransport([(200, {"unexpected": 1, "meta": {}})])
    with pytest.raises(ClipApiError, match="unexpected"):
        list(iter_payments(CREDS, datetime(2026, 9, 28, tzinfo=timezone.utc),
                           datetime(2026, 9, 29, tzinfo=timezone.utc),
                           transport=transport, now=NOW))


def test_la_credencial_viaja_en_el_encabezado_authorization():
    transport = FakeTransport([page([payment()])])
    list(iter_payments(CREDS, datetime(2026, 9, 28, tzinfo=timezone.utc),
                       datetime(2026, 9, 29, tzinfo=timezone.utc),
                       transport=transport, now=NOW))
    assert transport.headers[0]["Authorization"] == CREDS.auth_header()
    # Y nunca en la URL, que es lo que acaba en un log de acceso.
    assert CREDS.api_key not in transport.urls[0]


# --------------------------------------------------------------------------
# Mapeo
# --------------------------------------------------------------------------

def test_la_propina_no_se_cuenta_como_venta():
    row = map_payment(payment(), branch="sji")
    assert row["gross_amount"] == 116.0  # `amount`, no `total` (136)
    assert row["tip"] == 20.0


def test_sin_amount_se_reconstruye_restando_la_propina():
    raw = payment()
    del raw["amount"]
    assert map_payment(raw, branch="sji")["gross_amount"] == 116.0


def test_sin_amount_ni_total_falla_en_lugar_de_inventar():
    raw = payment()
    del raw["amount"]
    del raw["total"]
    with pytest.raises(ClipApiError, match="ABC123"):
        map_payment(raw, branch="sji")


def test_cancelada_queda_marcada_como_reversed():
    assert map_payment(payment(status="cancelled"), branch="sji")["status"] == "reversed"


def test_status_vacio_es_una_cancelacion_no_una_venta():
    """Lo que la API manda vacio, `?status=cancelled` lo devuelve.

    Verificado contra la API el 2026-10-04 y confirmado por Gustavo: el cobro de
    $108 del 21/09 en Tecnoparque, que llegaba con `status: ""`, era una
    cancelacion de pago con tarjeta — y estuvo cargado como venta.
    """
    for vacio in ("", "   ", None):
        row = map_payment(payment(status=vacio), branch="sji")
        assert row["status"] == "reversed", vacio


def test_una_cancelacion_no_entra_al_plan_de_carga():
    """La defensa de verdad: `plan_import` salta lo que no esta cobrado."""
    rows = [map_payment(payment(id="txn_ok"), branch="sji"),
            map_payment(payment(id="txn_cancelada", status=""), branch="sji")]
    plan = plan_import(rows, cafeteria_id="c-sji", source=SOURCE_CLIP_API)

    assert [d["dedup_key"] for d in plan.documents] == ["clip:txn_ok"]
    assert plan.summary()["skipped_reasons"] == {"no_cobrada:reversed": 1}


def test_metodo_de_pago_usa_el_vocabulario_del_app():
    assert map_payment(payment(), branch="sji")["payment_method"] == "tarjeta"
    raw = payment(payment_method=None, sub_type=None, card={"brand": "MASTERCARD"})
    assert map_payment(raw, branch="sji")["payment_method"] == "tarjeta"


def test_debito_y_credito_son_tarjeta():
    for raw_method in ("DEBIT", "CREDIT"):
        row = map_payment(payment(payment_method=raw_method), branch="sji")
        assert row["payment_method"] == "tarjeta"


# `OTHER` es la bolsa donde Clip mete todo lo que no es debito ni credito, y
# adentro hay cosas distintas. Antes de BOS-119 las tres caian en "tarjeta".

def test_vale_con_emisor_no_se_cuenta_como_tarjeta():
    """Pluxee/Edenred cobran de verdad, pero no son tarjeta bancaria.

    Es dinero con otro reparto y otra comision. En Tecnoparque son ~12% de los
    pesos de un año, y reportados como tarjeta nadie los puede separar.
    """
    raw = payment(payment_method="OTHER", sub_type="EMV_SIGNATURE",
                  card={"brand": "CR", "issuer": "PLUXEE MEXICO", "last4": "3702"})
    assert map_payment(raw, branch="tecnoparque")["payment_method"] == "vales"


def test_el_emisor_del_vale_queda_en_las_notas():
    """Sin el emisor, un vale cargado es indistinguible de una tarjeta."""
    raw = payment(payment_method="OTHER", sub_type="EMV_SIGNATURE",
                  card={"brand": "CR", "issuer": "EDENRED", "last4": "2791"})
    notes = map_payment(raw, branch="tecnoparque")["notes"]
    assert "EDENRED" in notes and "****2791" in notes


def test_cobro_sin_tarjeta_es_otro_y_no_se_le_llama_efectivo():
    """`XX`/`0000` sin emisor: la API no lo nombra, asi que no se adivina.

    Decirle "efectivo" inventaria un dato que esta en consulta (BOS-119), y
    decirle "tarjeta" lo esconderia para siempre. `otro` se ve en el tablero.
    """
    raw = payment(payment_method="OTHER", sub_type="CONSUMER",
                  card={"brand": "XX", "issuer": None, "last4": "0000"})
    assert map_payment(raw, branch="tecnoparque")["payment_method"] == "otro"


def test_sin_metodo_ni_tarjeta_tampoco_es_tarjeta():
    raw = payment(payment_method=None, sub_type=None, card={})
    assert map_payment(raw, branch="sji")["payment_method"] == "otro"


def test_si_clip_dice_efectivo_se_le_cree():
    """La rama que hace que el efectivo entre solo el dia que Clip lo mande.

    Hoy la API no manda ninguno (medido: 1,912 cobros en 360 dias, cero), pero
    si lo manda no hay que tocar codigo para que quede rotulado.
    """
    raw = payment(payment_method="CASH", sub_type=None, card={})
    assert map_payment(raw, branch="sji")["payment_method"] == "efectivo"
    raw = payment(payment_method="OTHER", sub_type="EFECTIVO", card={})
    assert map_payment(raw, branch="sji")["payment_method"] == "efectivo"


def test_el_id_de_clip_es_la_llave_de_dedup():
    row = map_payment(payment(), branch="sji")
    assert normalize_row(row)["dedup_key"] == "clip:txn_001"


def test_sin_id_cae_al_folio():
    raw = payment()
    del raw["id"]
    row = map_payment(raw, branch="sji")
    assert normalize_row(row)["dedup_key"] == "clip:ABC123"


def test_sin_created_at_falla():
    raw = payment()
    del raw["created_at"]
    with pytest.raises(ClipApiError, match="created_at"):
        map_payment(raw, branch="sji")


def test_notas_guardan_la_huella_de_la_tarjeta_sin_el_numero():
    notes = map_payment(payment(), branch="sji")["notes"]
    assert "VISA" in notes and "****4242" in notes
    assert "4242" in notes and "EMV_SIGNATURE" in notes


def test_fee_acepta_tambien_commission():
    assert map_payment(payment(fee=3.5), branch="sji")["fee"] == 3.5
    raw = payment()
    raw.pop("fee", None)
    raw["commission"] = 4.2
    assert map_payment(raw, branch="sji")["fee"] == 4.2


# --------------------------------------------------------------------------
# De punta a punta contra el importador
# --------------------------------------------------------------------------

def test_las_filas_de_la_api_entran_al_importador_sin_traduccion():
    transport = FakeTransport([page([
        payment(id="txn_001", amount=116.0),
        payment(id="txn_002", receipt_no="DEF456", amount=58.0, tip=0.0, total=58.0),
        payment(id="txn_003", receipt_no="GHI789", status="cancelled", amount=29.0),
    ])])
    rows = fetch_rows(CREDS, datetime(2026, 9, 28, tzinfo=timezone.utc),
                      datetime(2026, 9, 29, tzinfo=timezone.utc),
                      transport=transport, now=NOW)

    plan = plan_import(rows, cafeteria_id="caf-sji", source=SOURCE_CLIP_API)
    summary = plan.summary()

    assert len(plan.documents) == 2  # la cancelada no se carga como venta
    assert summary["skipped_reasons"] == {"no_cobrada:reversed": 1}
    # 174 = 116 + 58, el consumo sin las propinas, con IVA ya incluido.
    assert summary["gross_total"] == 174.0
    assert summary["subtotal_total"] == 150.0
    assert summary["tax_total"] == 24.0
    # Y el resumen sigue declarando que el efectivo no viene en la API.
    assert summary["cash_coverage"]["includes_cash"] is False


def test_reimportar_el_mismo_rango_no_duplica():
    raw = [payment(id="txn_001"), payment(id="txn_002", receipt_no="DEF456")]
    rows = [map_payment(item, branch="sji", index=i) for i, item in enumerate(raw)]
    primera = plan_import(rows, cafeteria_id="caf-sji", source=SOURCE_CLIP_API)
    existentes = {doc["dedup_key"] for doc in primera.documents}

    segunda = plan_import(rows, cafeteria_id="caf-sji", source=SOURCE_CLIP_API,
                          existing_keys=existentes)
    assert segunda.documents == []
    assert segunda.summary()["skipped_reasons"] == {"ya_importada": 2}


# --------------------------------------------------------------------------
# Corte por dia de operacion
# --------------------------------------------------------------------------

def test_el_corte_agrupa_por_dia_del_negocio_no_por_dia_utc():
    """Una venta de las 18:08 de CDMX llega como `00:08Z` del dia siguiente.

    Es el caso real observado en SJI el 30/09: agrupar por dia UTC la correria
    al 01/10 y dejaria el corte del 30/09 corto. El corte se hace en UTC-6.
    """
    raw = [
        payment(id="txn_dia", created_at="2026-10-01T00:08:46.000Z", amount=240.0,
                tip=0.0, total=240.0),
        payment(id="txn_tarde", created_at="2026-09-30T23:55:22.000Z", amount=116.0,
                tip=0.0, total=116.0),
        # 06:00Z del 01/10 ya es medianoche del 01/10 en CDMX: otro dia de operacion.
        payment(id="txn_otro_dia", created_at="2026-10-01T06:30:00.000Z", amount=58.0,
                tip=0.0, total=58.0),
    ]
    rows = [map_payment(item, branch="sji", index=i) for i, item in enumerate(raw)]

    corte = summarize_corte(rows, branch="sji")

    assert corte["by_business_date"] == [
        {"date": "2026-09-30", "transactions": 2, "gross": 356.0},
        {"date": "2026-10-01", "transactions": 1, "gross": 58.0},
    ]
    assert corte["gross_total"] == 414.0


def test_el_corte_deja_las_propinas_fuera_del_total_pero_las_reporta():
    raw = [payment(id="txn_001", amount=116.0, tip=20.0, total=136.0)]
    rows = [map_payment(item, branch="sji", index=0) for item in raw]

    corte = summarize_corte(rows, branch="sji")

    assert corte["gross_total"] == 116.0  # el consumo, no los 136 cobrados
    assert corte["tips_excluded"] == 20.0
    assert corte["subtotal_total"] == 100.0
    assert corte["tax_total"] == 16.0


def test_el_corte_no_cuenta_una_cancelada_y_declara_que_falta_el_efectivo():
    raw = [payment(id="txn_ok", amount=116.0, tip=0.0, total=116.0),
           payment(id="txn_mala", receipt_no="DEF456", status="cancelled", amount=29.0)]
    rows = [map_payment(item, branch="tecnoparque", index=i) for i, item in enumerate(raw)]

    corte = summarize_corte(rows, branch="tecnoparque")

    assert corte["transactions"] == 1
    assert corte["gross_total"] == 116.0
    assert corte["skipped_reasons"] == {"no_cobrada:reversed": 1}
    assert corte["cash_coverage"]["includes_cash"] is False
    assert corte["gross_by_payment_method"] == {"tarjeta": 116.0}


# --------------------------------------------------------------------------
# Censo de la taxonomia: el veredicto sobre el efectivo (BOS-119)
# --------------------------------------------------------------------------

def test_el_censo_dice_que_no_hay_efectivo_cuando_no_hay():
    censo = summarize_census([payment(), payment(receipt_no="X2", payment_method="DEBIT")],
                             branch="sji")
    assert censo["efectivo_en_la_api"] is False
    assert censo["rows_without_card"] == []
    assert "piso" in censo["note"]


def test_un_renglon_sin_tarjeta_con_status_vacio_es_cancelacion_no_efectivo():
    """La forma exacta de los dos unicos renglones sin tarjeta del año."""
    censo = summarize_census([payment(
        receipt_no="PhUFnfD5",
        status="",
        payment_method="OTHER",
        sub_type="CONSUMER",
        amount=5.0,
        tip=0.0,
        total=5.0,
        card={"brand": "XX", "issuer": None, "last4": "0000"},
    )], branch="sji")

    assert censo["efectivo_en_la_api"] is False
    assert len(censo["rows_without_card"]) == 1
    fila = censo["rows_without_card"][0]
    assert fila["status"] == "reversed"       # cancelada, no cobrada
    assert fila["payment_method"] == "otro"   # nunca "efectivo"
    # Y no suma un peso a lo cobrado.
    assert censo["gross_by_payment_method"] == {}


def test_el_dia_que_clip_mande_efectivo_el_censo_lo_grita():
    """El veredicto se **calcula**: no hay que tocar codigo para que cambie."""
    censo = summarize_census([payment(receipt_no="EF1", payment_method="CASH",
                                      card={"brand": "XX", "last4": "0000"})],
                             branch="sji")
    assert censo["efectivo_en_la_api"] is True
    assert censo["gross_by_payment_method"]["efectivo"]["transactions"] == 1
    assert "ya manda efectivo" in censo["note"]


def test_el_censo_separa_vales_de_tarjeta_y_no_cruza_estados():
    censo = summarize_census([
        payment(receipt_no="V1", payment_method="OTHER", sub_type="QPS",
                amount=100.0, tip=0.0, total=100.0,
                card={"brand": "CR", "issuer": "PLUXEE MEXICO", "last4": "1234"}),
        payment(receipt_no="T1", amount=50.0, tip=0.0, total=50.0),
        payment(receipt_no="C1", status="cancelled", amount=999.0, tip=0.0, total=999.0),
    ], branch="tecnoparque")

    assert censo["transactions"] == 3
    assert censo["gross_by_payment_method"]["vales"]["gross_amount"] == 100.0
    assert censo["gross_by_payment_method"]["tarjeta"]["gross_amount"] == 50.0
    # La cancelada aparece en la taxonomia pero no en lo cobrado.
    assert 999.0 not in [b["gross_amount"] for b in censo["gross_by_payment_method"].values()]
    assert any(b["status"] == "reversed" for b in censo["by_taxonomy"])


def test_tope_de_paginas_por_ventana():
    transport = FakeTransport([page([payment()], token=f"t{i}")
                               for i in range(MAX_PAGES_PER_WINDOW + 1)])
    with pytest.raises(ClipApiError, match="paginas"):
        list(iter_payments(CREDS, datetime(2026, 9, 28, tzinfo=timezone.utc),
                           datetime(2026, 9, 29, tzinfo=timezone.utc),
                           transport=transport, now=NOW))
