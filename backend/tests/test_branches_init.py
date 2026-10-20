"""Sembrar las sucursales reales es idempotente y no pisa lo que ya existe.

Sin Mongo: la coleccion se sustituye por un doble que responde
`find_one`/`insert_one`/`update_one` por `id`.

Lo que de verdad protegen estas pruebas: que una segunda corrida **no** duplique
la sucursal. Si se duplicara, cada reporte de la app partiria las ventas de una
sucursal en dos renglones con el mismo nombre, y eso se ve como un error de
ventas, no como un error de catalogo.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from branches_init import (  # noqa: E402
    GROUP_BRANCHES,
    BranchInitError,
    ensure_branches,
    open_cafeterias_collection,
)
from clip_api import credential_env_names  # noqa: E402


class FakeCafeterias:
    """Coleccion de mentiras: busca y actualiza por `id`, igual que la real."""

    def __init__(self, existing=()):
        self.docs = [dict(d) for d in existing]

    def _match(self, query):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return doc
        return None

    def find_one(self, query, projection=None):
        found = self._match(query)
        return dict(found) if found else None

    def insert_one(self, doc):
        self.docs.append(dict(doc))

    def update_one(self, query, update):
        found = self._match(query)
        if found is not None:
            found.update(update["$set"])


def test_en_seco_no_escribe_nada():
    cafeterias = FakeCafeterias()

    result = ensure_branches(cafeterias, GROUP_BRANCHES)

    assert result["committed"] is False
    assert result["created"] == 2
    assert cafeterias.docs == []


def test_crea_las_dos_sucursales_reales():
    cafeterias = FakeCafeterias()

    result = ensure_branches(cafeterias, GROUP_BRANCHES, commit=True)

    assert result["created"] == 2
    assert {d["id"] for d in cafeterias.docs} == {"c-sji", "c-tecno"}
    for doc in cafeterias.docs:
        # Modo legacy a proposito: un usuario sin tenant ve todas las sucursales.
        assert doc["tenant_id"] is None
        assert doc["created_at"]


def test_segunda_corrida_no_duplica():
    cafeterias = FakeCafeterias()
    ensure_branches(cafeterias, GROUP_BRANCHES, commit=True)

    result = ensure_branches(cafeterias, GROUP_BRANCHES, commit=True)

    assert result["created"] == 0
    assert result["unchanged"] == 2
    assert len(cafeterias.docs) == 2


def test_corrige_un_campo_sin_tocar_id_ni_created_at():
    cafeterias = FakeCafeterias([{
        "id": "c-sji",
        "tenant_id": None,
        "name": "Casa Dorelia San Jose Insurgentes",
        "address": "Por confirmar",
        "phone": None,
        "is_active": True,
        "clip_branch": "sji",
        "created_at": "2026-09-01T00:00:00+00:00",
    }])

    result = ensure_branches(cafeterias, GROUP_BRANCHES, commit=True)

    assert result["updated"] == 1
    sji = cafeterias.find_one({"id": "c-sji"})
    assert sji["address"] == "San Jose Insurgentes, Benito Juarez, CDMX"
    # La historia no se reescribe y la llave que amarra las ventas no se mueve.
    assert sji["created_at"] == "2026-09-01T00:00:00+00:00"
    assert sji["id"] == "c-sji"


def test_corrige_el_nombre_y_la_marca_de_tecnoparque_ya_sembrada():
    """La migracion de BOS-101: la sucursal ya existe, mal nombrada y sin marca.

    Es el caso real, no uno hipotetico: `c-tecno` se sembro el 01/10 como "Casa
    Dorelia Tecnoparque" cuando es Le Pain Dore. Lo que tiene que pasar al volver
    a correr es que se **corrija en su lugar**, sin crear una segunda sucursal:
    las 61 ventas cargadas cuelgan de `id`, y duplicar la cafeteria partiria su
    dinero en dos renglones.
    """
    cafeterias = FakeCafeterias([{
        "id": "c-tecno",
        "tenant_id": None,
        "name": "Casa Dorelia Tecnoparque",
        "address": "Tecnoparque, Azcapotzalco, CDMX",
        "phone": None,
        "is_active": True,
        "clip_branch": "tecnoparque",
        "created_at": "2026-10-01T07:30:18.163631+00:00",
    }])

    result = ensure_branches(cafeterias, GROUP_BRANCHES, commit=True)

    tecno = cafeterias.find_one({"id": "c-tecno"})
    assert tecno["name"] == "Le Pain Dore Tecnoparque"
    assert tecno["brand"] == "le-pain-dore"
    # Se corrigio en su lugar: la llave que amarra las 61 ventas no se movio.
    assert tecno["id"] == "c-tecno"
    assert tecno["created_at"] == "2026-10-01T07:30:18.163631+00:00"
    assert len([d for d in cafeterias.docs if d["id"] == "c-tecno"]) == 1
    assert result["updated"] == 1


def test_no_borra_sucursales_que_no_declara():
    cafeterias = FakeCafeterias([{"id": "c-otra", "name": "Otra", "tenant_id": None}])

    ensure_branches(cafeterias, GROUP_BRANCHES, commit=True)

    assert cafeterias.find_one({"id": "c-otra"}) is not None
    assert len(cafeterias.docs) == 3


def test_sin_db_name_el_error_dice_que_falta(monkeypatch):
    monkeypatch.delenv("DB_NAME", raising=False)

    with pytest.raises(BranchInitError) as err:
        open_cafeterias_collection(None, None)

    assert "DB_NAME" in str(err.value)


def test_cada_sucursal_apunta_a_una_credencial_de_clip_declarada():
    """El `clip_branch` de cada sucursal tiene que cuadrar con el secreto cargado.

    Si alguien renombra una sucursal aqui y no el secreto, la carga truena con
    "falta la variable" en lugar de cargar ventas a la cafeteria equivocada.
    """
    esperados = {
        ("CLIP_API_KEY_SJI", "CLIP_SECRET_KEY_SJI"),
        ("CLIP_API_KEY_TECNOPARQUE", "CLIP_SECRET_KEY_TECNOPARQUE"),
    }

    reales = {credential_env_names(b["clip_branch"]) for b in GROUP_BRANCHES}

    assert reales == esperados
