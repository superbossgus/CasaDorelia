"""Separar el dinero de las dos marcas que comparten la base (BOS-101).

Lo que de verdad protegen estas pruebas no es el campo `brand`: es que **nadie
pueda volver a publicar un total consolidado como venta de una sola marca**. El
84% de los pesos de `casa_dorelia` son de Le Pain Dore, con socios distintos a los
de Casa Dorelia, asi que sumarlas no es un redondeo: es mezclar dos repartos.

Por eso hay pruebas de tres cosas que parecen de adorno y no lo son:

- una venta **sin** marca aparece en `sin-marca` en vez de desaparecer (un cero
  tiene que poder distinguirse de un campo que falta);
- el backfill escribe **solo** `brand`, por `_id`, para que no haya forma de
  re-llavear las 73 ventas cargadas (`dedup_key` es la idempotencia de la carga);
- el total general se llama `gross_all_brands` y no "total", porque el nombre es
  lo unico que impide que alguien lo lea como la venta de una marca.

Sin Mongo: las colecciones se sustituyen por dobles.
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backfill_brand import MISSING_BRAND, backfill, brand_map, plan_backfill  # noqa: E402
from branches_init import GROUP_BRANCHES, brand_for  # noqa: E402
from brands import (  # noqa: E402
    BRANDS,
    CASA_DORELIA,
    LE_PAIN_DORE,
    UNKNOWN_BRAND,
    brand_name,
    brand_vehicle,
    by_brand_pipeline,
    report_by_brand,
    summarize_brand_rows,
)


def corre(coroutine):
    return asyncio.run(coroutine)


# --------------------------------------------------------------------------
# El catalogo dice de quien es cada sucursal
# --------------------------------------------------------------------------

def test_tecnoparque_es_le_pain_dore_no_casa_dorelia():
    """El error original de BOS-101, fijado para que no vuelva."""
    tecno = next(b for b in GROUP_BRANCHES if b["id"] == "c-tecno")

    assert tecno["brand"] == LE_PAIN_DORE
    assert "Casa Dorelia" not in tecno["name"]
    assert tecno["name"] == "Le Pain Dore Tecnoparque"


def test_san_jose_insurgentes_si_es_casa_dorelia():
    sji = next(b for b in GROUP_BRANCHES if b["id"] == "c-sji")

    assert sji["brand"] == CASA_DORELIA
    assert sji["name"] == "Casa Dorelia San Jose Insurgentes"


def test_cada_sucursal_declara_una_marca_del_registro():
    """Una marca que no esta en `BRANDS` se reportaria sin nombre ni vehiculo."""
    for branch in GROUP_BRANCHES:
        assert branch.get("brand"), f"{branch['id']} no declara marca"
        assert branch["brand"] in BRANDS, f"{branch['id']} declara una marca desconocida"


def test_las_dos_marcas_tienen_vehiculos_distintos():
    """Es el dato por el que no se pueden sumar: reparten a socios distintos."""
    vehiculos = {slug: entry["vehicle"] for slug, entry in BRANDS.items()}

    assert vehiculos[CASA_DORELIA] != vehiculos[LE_PAIN_DORE]
    assert vehiculos[LE_PAIN_DORE] == "Grupo Viter, S.A. de C.V."
    assert vehiculos[CASA_DORELIA] == "Big E Stores"


def test_brand_for_resuelve_la_marca_sin_que_nadie_la_teclee():
    assert brand_for("c-sji") == CASA_DORELIA
    assert brand_for("c-tecno") == LE_PAIN_DORE
    # Una sucursal que no esta en el catalogo no recibe una marca inventada.
    assert brand_for("c-que-no-existe") is None


def test_el_nombre_de_una_marca_desconocida_no_se_tapa():
    assert brand_name(CASA_DORELIA) == "Casa Dorelia"
    assert brand_name(None) == UNKNOWN_BRAND
    # Se devuelve tal cual para que se vea en el reporte y alguien lo corrija.
    assert brand_name("marca-nueva") == "marca-nueva"
    assert brand_vehicle("marca-nueva") is None


# --------------------------------------------------------------------------
# La consulta por marca
# --------------------------------------------------------------------------

class FakeSalesAgg:
    """Agrega en memoria lo que haria `$group` por `brand`, respetando `$match`."""

    def __init__(self, docs):
        self.docs = [dict(d) for d in docs]
        self.pipelines = []

    def aggregate(self, pipeline):
        self.pipelines.append(pipeline)
        rows = self.docs
        for stage in pipeline:
            if "$match" in stage:
                rows = [d for d in rows
                        if all(d.get(k) == v for k, v in stage["$match"].items())]
        buckets = {}
        for doc in rows:
            slug = doc.get("brand") or UNKNOWN_BRAND
            bucket = buckets.setdefault(slug, {"_id": slug, "sales": 0, "gross": 0.0})
            bucket["sales"] += 1
            bucket["gross"] = round(bucket["gross"] + doc["total"], 2)
        return [buckets[k] for k in sorted(buckets)]


def ventas_de_las_dos_marcas():
    """Las proporciones reales de la base: la mayoria del dinero es de Tecnoparque."""
    return [
        {"_id": 1, "cafeteria_id": "c-sji", "brand": CASA_DORELIA,
         "business_date": "2026-09-30", "total": 100.0},
        {"_id": 2, "cafeteria_id": "c-sji", "brand": CASA_DORELIA,
         "business_date": "2026-09-30", "total": 50.0},
        {"_id": 3, "cafeteria_id": "c-tecno", "brand": LE_PAIN_DORE,
         "business_date": "2026-09-30", "total": 800.0},
        {"_id": 4, "cafeteria_id": "c-tecno", "brand": LE_PAIN_DORE,
         "business_date": "2026-09-29", "total": 400.0},
    ]


def test_la_consulta_devuelve_la_venta_del_dia_por_marca():
    """El criterio de cierre de BOS-101."""
    sales = FakeSalesAgg(ventas_de_las_dos_marcas())

    reporte = report_by_brand(sales, business_date="2026-09-30")

    por_marca = {b["brand"]: b for b in reporte["brands"]}
    assert por_marca[CASA_DORELIA]["gross"] == 150.0
    assert por_marca[CASA_DORELIA]["sales"] == 2
    assert por_marca[LE_PAIN_DORE]["gross"] == 800.0
    assert por_marca[LE_PAIN_DORE]["sales"] == 1
    assert reporte["business_date"] == "2026-09-30"


def test_cada_renglon_dice_a_quien_le_toca_ese_dinero():
    sales = FakeSalesAgg(ventas_de_las_dos_marcas())

    reporte = report_by_brand(sales, business_date="2026-09-30")
    por_marca = {b["brand"]: b for b in reporte["brands"]}

    assert por_marca[LE_PAIN_DORE]["name"] == "Le Pain Dore"
    assert por_marca[LE_PAIN_DORE]["vehicle"] == "Grupo Viter, S.A. de C.V."
    assert por_marca[CASA_DORELIA]["vehicle"] == "Big E Stores"


def test_el_total_general_no_se_llama_total():
    """Nombrarlo `total` es como se publica dinero de una marca como de la otra."""
    sales = FakeSalesAgg(ventas_de_las_dos_marcas())

    reporte = report_by_brand(sales, business_date="2026-09-30")

    assert reporte["gross_all_brands"] == 950.0
    assert "total" not in reporte
    # Y sigue declarando que el efectivo no viene en la API de Clip.
    assert reporte["includes_cash"] is False


def test_una_venta_sin_marca_se_ve_en_vez_de_desaparecer():
    sales = FakeSalesAgg([
        {"_id": 1, "cafeteria_id": "c-sji", "brand": CASA_DORELIA,
         "business_date": "2026-09-30", "total": 100.0},
        {"_id": 2, "cafeteria_id": "c-otra", "business_date": "2026-09-30", "total": 70.0},
    ])

    reporte = report_by_brand(sales, business_date="2026-09-30")

    sin_marca = next(b for b in reporte["brands"] if b["brand"] == UNKNOWN_BRAND)
    assert sin_marca["gross"] == 70.0
    assert reporte["unlabeled_sales"] == 1
    # El dinero sin marca cuenta en la suma de control: no se pierde callado.
    assert reporte["gross_all_brands"] == 170.0


def test_sin_dia_la_consulta_es_del_historico():
    sales = FakeSalesAgg(ventas_de_las_dos_marcas())

    reporte = report_by_brand(sales)

    por_marca = {b["brand"]: b for b in reporte["brands"]}
    assert por_marca[LE_PAIN_DORE]["gross"] == 1200.0  # los dos dias
    assert sales.pipelines[0][0].get("$match") is None  # no hay etapa de filtro


def test_el_pipeline_agrupa_las_ventas_sin_marca_en_su_renglon():
    """`$ifNull` es lo que evita que una venta sin marca se caiga del reporte."""
    stages = by_brand_pipeline(business_date="2026-09-30")

    group = next(s["$group"] for s in stages if "$group" in s)
    assert group["_id"] == {"$ifNull": ["$brand", UNKNOWN_BRAND]}
    assert stages[0]["$match"] == {"business_date": "2026-09-30"}


def test_el_pipeline_respeta_el_aislamiento_por_tenant():
    stages = by_brand_pipeline(business_date="2026-09-30", tenant_id="t-1")

    assert stages[0]["$match"] == {"business_date": "2026-09-30", "tenant_id": "t-1"}


def test_summarize_no_inventa_renglones_cuando_no_hubo_venta():
    vacio = summarize_brand_rows([])

    assert vacio["brands"] == []
    assert vacio["gross_all_brands"] == 0.0
    assert vacio["unlabeled_sales"] == 0


# --------------------------------------------------------------------------
# El backfill de las ventas ya cargadas
# --------------------------------------------------------------------------

class FakeSalesAsync:
    """Coleccion async de mentiras: lo justo que usa `backfill`.

    Solo entiende el filtro `MISSING_BRAND` y aplica los `UpdateOne` por `_id`.
    Guarda cada operacion para que una prueba pueda revisar **que** se escribio.
    """

    def __init__(self, docs):
        self.docs = [dict(d) for d in docs]
        self.lotes = []
        self.operaciones = []

    def find(self, query, projection=None):
        assert query == MISSING_BRAND  # el backfill no debe barrer la coleccion
        return _CursorFalso([dict(d) for d in self.docs if not d.get("brand")])

    async def bulk_write(self, operaciones, ordered=True):
        self.lotes.append(len(operaciones))
        self.operaciones.extend(operaciones)
        modificados = 0
        por_id = {d["_id"]: d for d in self.docs}
        for op in operaciones:
            doc = por_id[op._filter["_id"]]
            cambio = op._doc["$set"]
            if any(doc.get(k) != v for k, v in cambio.items()):
                doc.update(cambio)
                modificados += 1
        return _ResultadoFalso(modificados)


class FakeCafeteriasAsync:
    def __init__(self, docs):
        self.docs = [dict(d) for d in docs]

    def find(self, query, projection=None):
        return _CursorFalso([dict(d) for d in self.docs])


class _CursorFalso:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length=None):
        return self._docs if length is None else self._docs[:length]


class _ResultadoFalso:
    def __init__(self, modified_count):
        self.modified_count = modified_count


CATALOGO = [
    {"id": "c-sji", "brand": CASA_DORELIA},
    {"id": "c-tecno", "brand": LE_PAIN_DORE},
]


def ventas_sin_marca():
    """Como estan las 73 de la base: con `dedup_key` y sin `brand`."""
    return [
        {"_id": 1, "id": "s1", "cafeteria_id": "c-sji", "dedup_key": "clip:AAA"},
        {"_id": 2, "id": "s2", "cafeteria_id": "c-tecno", "dedup_key": "clip:BBB"},
        {"_id": 3, "id": "s3", "cafeteria_id": "c-tecno", "dedup_key": "clip:CCC"},
    ]


def test_el_backfill_sella_la_marca_de_cada_sucursal_y_queda_idempotente():
    sales = FakeSalesAsync(ventas_sin_marca())
    cafeterias = FakeCafeteriasAsync(CATALOGO)

    primera = corre(backfill(sales, cafeterias))
    assert primera["examined"] == 3
    assert primera["stamped"] == 3
    assert primera["by_brand"] == {CASA_DORELIA: 1, LE_PAIN_DORE: 2}
    assert [d["brand"] for d in sales.docs] == [CASA_DORELIA, LE_PAIN_DORE, LE_PAIN_DORE]

    segunda = corre(backfill(sales, cafeterias))
    assert segunda["examined"] == 0  # ya no hay nada que empate el filtro
    assert segunda["stamped"] == 0


def test_el_backfill_no_toca_ni_id_ni_dedup_key():
    """La idempotencia de la carga de Clip cuelga de `dedup_key`: es intocable."""
    sales = FakeSalesAsync(ventas_sin_marca())

    corre(backfill(sales, FakeCafeteriasAsync(CATALOGO)))

    for op in sales.operaciones:
        # Se escribe un solo campo, y se localiza por `_id`, no por la llave.
        assert list(op._doc) == ["$set"]
        assert list(op._doc["$set"]) == ["brand"]
        assert list(op._filter) == ["_id"]

    assert [d["dedup_key"] for d in sales.docs] == ["clip:AAA", "clip:BBB", "clip:CCC"]
    assert [d["id"] for d in sales.docs] == ["s1", "s2", "s3"]


def test_una_venta_de_sucursal_desconocida_se_reporta_sin_marca_inventada():
    sales = FakeSalesAsync(ventas_sin_marca() + [
        {"_id": 4, "id": "s4", "cafeteria_id": "c-misteriosa", "dedup_key": "clip:DDD"},
    ])

    resumen = corre(backfill(sales, FakeCafeteriasAsync(CATALOGO)))

    assert resumen["unmapped"] == 1
    assert resumen["unmapped_cafeterias"] == ["c-misteriosa"]
    assert resumen["stamped"] == 3
    assert sales.docs[3].get("brand") is None


def test_el_backfill_en_seco_no_escribe():
    sales = FakeSalesAsync(ventas_sin_marca())

    resumen = corre(backfill(sales, FakeCafeteriasAsync(CATALOGO), dry_run=True))

    assert resumen["to_stamp"] == 3
    assert resumen["stamped"] == 0
    assert sales.lotes == []
    assert all("brand" not in d for d in sales.docs)


def test_el_backfill_parte_en_lotes_en_vez_de_una_escritura_gigante():
    sales = FakeSalesAsync(ventas_sin_marca())

    corre(backfill(sales, FakeCafeteriasAsync(CATALOGO), batch_size=2))

    assert sales.lotes == [2, 1]


def test_el_catalogo_de_la_base_manda_sobre_el_del_codigo():
    """Una correccion hecha con `branches_init --commit` gana sobre la constante."""
    mapping = corre(brand_map(FakeCafeteriasAsync([
        {"id": "c-tecno", "brand": "marca-corregida-a-mano"},
    ])))

    assert mapping["c-tecno"] == "marca-corregida-a-mano"


def test_si_el_catalogo_de_la_base_no_trae_marca_se_usa_el_del_codigo():
    """Asi el backfill sirve ANTES de volver a sembrar las sucursales."""
    mapping = corre(brand_map(FakeCafeteriasAsync([
        {"id": "c-tecno"},            # sembrada antes de que existiera el campo
        {"id": "c-sji", "brand": ""},  # sellada a medias
    ])))

    assert mapping["c-tecno"] == LE_PAIN_DORE
    assert mapping["c-sji"] == CASA_DORELIA


def test_plan_backfill_no_escribe_y_separa_lo_que_no_sabe():
    por_sellar, sin_marca = plan_backfill(
        ventas_sin_marca() + [{"_id": 9, "id": "s9", "cafeteria_id": None}],
        {"c-sji": CASA_DORELIA, "c-tecno": LE_PAIN_DORE},
    )

    assert [r["brand"] for r in por_sellar] == [CASA_DORELIA, LE_PAIN_DORE, LE_PAIN_DORE]
    assert [r["id"] for r in sin_marca] == ["s9"]
