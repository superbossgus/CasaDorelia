"""
Pruebas del cliente de la API de Clip (`backend/clip_api.py`).

Unitarias y **sin red**: el transporte HTTP se inyecta, asi que se puede probar
la paginacion, el corte de ventanas de 720 h, los errores de credencial y el
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
    branch_slug,
    build_payments_url,
    credential_env_names,
    fetch_rows,
    iter_payments,
    load_credentials,
    map_payment,
    split_window,
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

def test_rango_largo_se_parte_en_ventanas_de_720_horas():
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 1, tzinfo=timezone.utc)
    windows = split_window(start, end, now=NOW)
    assert len(windows) == 4
    assert windows[0][0] == start
    assert windows[-1][1] == end
    for window_start, window_end in windows:
        assert window_end - window_start <= timedelta(hours=720)
    # Sin huecos ni traslapes: el final de una es el inicio de la siguiente.
    for previous, following in zip(windows, windows[1:]):
        assert previous[1] == following[0]


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


def test_metodo_de_pago_usa_el_vocabulario_del_app():
    assert map_payment(payment(), branch="sji")["payment_method"] == "tarjeta"
    raw = payment(payment_method=None, sub_type=None, card={"brand": "MASTERCARD"})
    assert map_payment(raw, branch="sji")["payment_method"] == "tarjeta"
    raw = payment(payment_method=None, sub_type=None, card={})
    assert map_payment(raw, branch="sji")["payment_method"] == "tarjeta"


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


def test_tope_de_paginas_por_ventana():
    transport = FakeTransport([page([payment()], token=f"t{i}")
                               for i in range(MAX_PAGES_PER_WINDOW + 1)])
    with pytest.raises(ClipApiError, match="paginas"):
        list(iter_payments(CREDS, datetime(2026, 9, 28, tzinfo=timezone.utc),
                           datetime(2026, 9, 29, tzinfo=timezone.utc),
                           transport=transport, now=NOW))
