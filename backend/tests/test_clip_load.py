"""El cargador escribe solo con `commit` y no duplica al reimportar.

Sin Mongo y sin red: la coleccion se sustituye por un doble que responde
`find`/`insert_many`, y las filas se pasan ya bajadas.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from clip_api import map_payment  # noqa: E402
from clip_load import ClipLoadError, load_branch, open_sales_collection, plan_against_db  # noqa: E402


class FakeSales:
    """Coleccion de mentiras: guarda lo insertado y contesta por `dedup_key`."""

    def __init__(self, existing=()):
        self.docs = [{"dedup_key": key} for key in existing]
        self.inserted = []
        self.queries = []

    def find(self, query, projection=None):
        self.queries.append(query)
        wanted = set(query.get("dedup_key", {}).get("$in", []))
        return [{"dedup_key": d["dedup_key"]} for d in self.docs
                if d["dedup_key"] in wanted]

    def insert_many(self, docs):
        self.inserted.extend(docs)
        self.docs.extend(docs)


def payment(**overrides):
    base = {
        "receipt_no": "ABC123",
        "id": "txn_001",
        "created_at": "2026-09-30T21:55:47.000Z",
        "status": "paid",
        "amount": 116.0,
        "tip": 0.0,
        "total": 116.0,
        "payment_method": "CREDIT",
        "card": {"brand": "VISA", "last4": "4242"},
        "currency": "MXN",
    }
    base.update(overrides)
    return base


def rows(*payments):
    return [map_payment(p, branch="sji", index=i) for i, p in enumerate(payments)]


ARGS = dict(branch="sji", start=None, end=None, cafeteria_id="c-sji")


def test_en_seco_no_escribe_nada():
    sales = FakeSales()
    result = load_branch(sales, rows=rows(payment()), commit=False, **ARGS)

    assert sales.inserted == []
    assert result["inserted"] == 0
    assert result["to_insert"] == 1
    assert result["committed"] is False


def test_con_commit_escribe_y_reporta_lo_insertado():
    sales = FakeSales()
    result = load_branch(sales, rows=rows(payment(), payment(id="txn_002", receipt_no="DEF456")),
                         commit=True, **ARGS)

    assert len(sales.inserted) == 2
    assert result["inserted"] == 2
    assert result["gross_total"] == 232.0
    # La venta se guarda con el dia de operacion, no con el dia de la carga.
    assert {d["business_date"] for d in sales.inserted} == {"2026-09-30"}
    # Y no toca inventario: la venta ya salio por el POS de Clip.
    assert all(d["inventory_applied"] is False for d in sales.inserted)


def test_reimportar_el_mismo_rango_no_duplica():
    """La segunda pasada es la que sostiene esto, no la primera.

    Las filas de la API de Clip llegan SIN `dedup_key`: la clave la deriva
    `plan_import`. Asi que la consulta de claves declaradas siempre sale vacia
    para este origen y toda la idempotencia depende de la segunda consulta.
    """
    sales = FakeSales()
    primera = load_branch(sales, rows=rows(payment()), commit=True, **ARGS)
    assert primera["inserted"] == 1

    segunda = load_branch(sales, rows=rows(payment()), commit=True, **ARGS)
    assert segunda["inserted"] == 0
    assert segunda["skipped_reasons"] == {"ya_importada": 1}
    assert len(sales.inserted) == 1  # sigue habiendo una sola venta


def test_la_clave_derivada_se_consulta_aunque_la_fila_no_traiga_dedup_key():
    fila = rows(payment())[0]
    assert "dedup_key" not in fila  # el supuesto del que cuelga la prueba anterior

    sales = FakeSales()
    plan = plan_against_db([fila], sales, cafeteria_id="c-sji")

    consultadas = [q for q in sales.queries if q.get("dedup_key", {}).get("$in")]
    assert consultadas, "nunca se consulto la base por la clave derivada"
    assert consultadas[0]["dedup_key"]["$in"] == [plan.documents[0]["dedup_key"]]


def test_el_tenant_filtra_las_dos_consultas():
    sales = FakeSales()
    plan_against_db(rows(payment()), sales, cafeteria_id="c-sji", tenant_id="t-casa")

    assert all(q.get("tenant_id") == "t-casa" for q in sales.queries)


def test_una_cancelada_no_se_escribe():
    sales = FakeSales()
    result = load_branch(sales, rows=rows(payment(status="cancelled")), commit=True, **ARGS)

    assert sales.inserted == []
    assert result["skipped_reasons"] == {"no_cobrada:reversed": 1}


def test_el_resultado_declara_que_falta_el_efectivo():
    result = load_branch(FakeSales(), rows=rows(payment()), commit=False, **ARGS)
    assert result["cash_coverage"]["includes_cash"] is False


def test_sin_db_name_dice_que_falta_en_vez_de_adivinar(monkeypatch):
    monkeypatch.delenv("DB_NAME", raising=False)
    with pytest.raises(ClipLoadError, match="DB_NAME"):
        open_sales_collection("mongodb://127.0.0.1:27017", None)


def test_un_mongod_apagado_dice_como_levantarlo(monkeypatch):
    """El error de pymongo no sirve de nada a las 19:45: tiene que decir que hacer.

    Crudo sube como `ServerSelectionTimeoutError`, que `clip_daily.main` no
    atrapa, asi que un mongod caido terminaba en traceback y el corte de las
    20:00 salia sin cifra sin explicacion (BOS-140).
    """
    def cliente_muerto(url, **kwargs):
        class Admin:
            def command(self, _):
                raise RuntimeError("No replica set members available")

        class Client:
            admin = Admin()

        return Client()

    monkeypatch.setattr("pymongo.MongoClient", cliente_muerto)
    with pytest.raises(ClipLoadError, match="Start-Service MongoDB"):
        open_sales_collection("mongodb://127.0.0.1:27017", "casa_dorelia")


def test_la_espera_cubre_la_escalera_de_reintentos_del_servicio(monkeypatch):
    """El servicio reintenta a los 5, 10 y 30 s: esperar 5 s fallaba sin razon.

    Si alguien vuelve a bajar este numero, una carga que dispara durante el
    reinicio automatico falla aunque la base vuelva sola.
    """
    visto = {}

    def espiar(url, **kwargs):
        visto.update(kwargs)

        class Client:
            class admin:
                @staticmethod
                def command(_):
                    return {"ok": 1}

            def __getitem__(self, _):
                class Db:
                    sales = object()
                return Db()

        return Client()

    monkeypatch.setattr("pymongo.MongoClient", espiar)
    open_sales_collection("mongodb://127.0.0.1:27017", "casa_dorelia")

    assert visto["serverSelectionTimeoutMS"] >= 45_000
