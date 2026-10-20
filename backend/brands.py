"""Las marcas del grupo que comparten esta base, y como separar su dinero.

### El problema que resuelve

`casa_dorelia` guarda las ventas de **dos negocios distintos**, no de uno con dos
sucursales:

| Sucursal | Marca | Vehiculo |
|---|---|---|
| `c-sji` (San Jose Insurgentes / Plateros 162) | Casa Dorelia | Big E Stores |
| `c-tecno` (Tecnoparque, Azcapotzalco) | Le Pain Dore | Grupo Viter, S.A. de C.V. |

Mismo grupo de control, **dos marcas, dos contratos y socios distintos** (BOS-90).
Tecnoparque tiene su propio asociado al 10% del neto y sus propios socios de
capital al 25%; sumar las dos en un total mezcla el dinero de dos repartos. Y no
es un detalle historico: el 84% de los pesos cargados son de Le Pain Dore, asi
que un total consolidado publicado como "venta de Casa Dorelia" esta mal por
mayoria (BOS-101).

### Por que `brand` y no `tenant_id`

`branches_init` proponia sembrar `tenant_id` el dia que hicieran falta varias
empresas en la misma base. Al llegar ese dia resulta que `tenant_id` es el campo
equivocado: en `server.py` un tenant es la **cuenta SaaS** del cliente, con plan,
limite de sucursales (`max_branches`), logo y facturacion. Usarlo para decir
"marca" trae tres problemas concretos:

1. Un tenant nuevo nace con `max_branches: 1`, asi que `POST /api/cafeterias`
   rechazaria con 403 la segunda sucursal de la marca.
2. `get_tenant_filter` usa `tenant_id` para **aislar** datos. Sellar
   `c-tecno` con un tenant distinto lo sacaria de la vista de quien hoy lee
   todo, que es justo Gustavo: es dueño de las dos y las quiere ver juntas,
   separadas por renglon.
3. `branches_init` busca la sucursal con el filtro de tenant. Cambiarle el
   `tenant_id` a una sucursal ya sembrada haria que la siguiente corrida no la
   reconociera y la **duplicara**.

`brand` no tiene ninguno de los tres: es una etiqueta descriptiva que nadie usa
para permisos ni para contar cupo. El dia que el grupo quiera de verdad dos
cuentas separadas, `tenant_id` sigue libre para eso y `brand` sigue siendo
cierto.

### La consulta

    python backend/brands.py --db casa_dorelia                    # historico
    python backend/brands.py --db casa_dorelia --date 2026-09-30  # un dia

Una marca sin etiqueta **no se calla**: cae en el renglon `sin-marca`, igual que
una venta sin `created_at` legible se reporta en el backfill de `business_date`.
Un cero en un reporte de dinero tiene que poder distinguirse de un campo que
falta.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEFAULT_MONGO_URL = "mongodb://127.0.0.1:27017"

CASA_DORELIA = "casa-dorelia"
LE_PAIN_DORE = "le-pain-dore"

# Marca a la que pertenece el dinero. `vehicle` es quien lo reparte: es el dato
# por el que estas dos no se pueden sumar.
BRANDS: Dict[str, Dict[str, Any]] = {
    CASA_DORELIA: {
        "name": "Casa Dorelia",
        "vehicle": "Big E Stores",
        "note": "Tomada por traspaso; documentacion corporativa de Big E Stores.",
    },
    LE_PAIN_DORE: {
        "name": "Le Pain Dore",
        "vehicle": "Grupo Viter, S.A. de C.V.",
        "note": ("Asociacion en participacion de la cafeteria CDMX Tecnoparque: "
                 "asociado con 10% del neto y socios de capital al 25%."),
    },
}

# Renglon de las ventas que no traen `brand`. No es una marca: es la señal de que
# falta correr el backfill, o de que entro una sucursal que nadie etiqueto.
UNKNOWN_BRAND = "sin-marca"


class BrandError(RuntimeError):
    """Algo impide leer la venta por marca. Siempre dice que falta."""


def brand_name(slug: Optional[str]) -> str:
    """Nombre para enseñar. Un slug desconocido se devuelve tal cual, no se tapa."""
    if not slug:
        return UNKNOWN_BRAND
    entry = BRANDS.get(slug)
    return entry["name"] if entry else slug


def brand_vehicle(slug: Optional[str]) -> Optional[str]:
    """Quien reparte ese dinero, o `None` si la marca no esta en el registro."""
    entry = BRANDS.get(slug) if slug else None
    return entry["vehicle"] if entry else None


def by_brand_pipeline(*, business_date: Optional[str] = None,
                      tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Pipeline de agregacion que suma la venta por marca.

    Se construye aqui, sin tocar Mongo, para que la use igual el CLI (pymongo) y
    el server (motor) sin reescribirla, y para que una prueba pueda revisarla.

    `$ifNull` es lo que hace que una venta sin `brand` aparezca en `sin-marca` en
    vez de desaparecer del reporte.
    """
    match: Dict[str, Any] = {}
    if business_date:
        match["business_date"] = business_date
    if tenant_id:
        match["tenant_id"] = tenant_id

    stages: List[Dict[str, Any]] = []
    if match:
        stages.append({"$match": match})
    stages.extend([
        {"$group": {
            "_id": {"$ifNull": ["$brand", UNKNOWN_BRAND]},
            "sales": {"$sum": 1},
            "gross": {"$sum": "$total"},
        }},
        {"$sort": {"_id": 1}},
    ])
    return stages


def summarize_brand_rows(rows: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """Decora la salida de `by_brand_pipeline` con nombre y vehiculo.

    Funcion pura: recibe lo que devolvio la agregacion. El total general se
    incluye **solo** como suma de control (`gross_all_brands`) y con el nombre
    diciendolo: no es "la venta de Casa Dorelia", es dinero de dos repartos.
    """
    brands: List[Dict[str, Any]] = []
    total = 0.0
    count = 0
    for row in rows:
        slug = row["_id"]
        gross = round(float(row.get("gross") or 0.0), 2)
        total += gross
        count += int(row.get("sales") or 0)
        brands.append({
            "brand": slug,
            "name": brand_name(slug),
            "vehicle": brand_vehicle(slug),
            "sales": int(row.get("sales") or 0),
            "gross": gross,
        })

    unlabeled = next((b for b in brands if b["brand"] == UNKNOWN_BRAND), None)
    return {
        "brands": brands,
        "sales_all_brands": count,
        "gross_all_brands": round(total, 2),
        "unlabeled_sales": unlabeled["sales"] if unlabeled else 0,
        # La API de Clip no entrega efectivo: este total es piso, no la venta.
        "includes_cash": False,
    }


def report_by_brand(sales: Any, *, business_date: Optional[str] = None,
                    tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Corre la consulta contra la coleccion `sales` y devuelve el corte por marca."""
    rows = list(sales.aggregate(by_brand_pipeline(business_date=business_date,
                                                  tenant_id=tenant_id)))
    out = summarize_brand_rows(rows)
    out["business_date"] = business_date or "todo el historico"
    return out


def open_sales_collection(mongo_url: Optional[str] = None, db_name: Optional[str] = None):
    """Coleccion `sales`, con un mensaje util cuando falta configuracion."""
    try:
        from pymongo import MongoClient
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise BrandError("falta el driver de Mongo: pip install pymongo") from exc

    url = mongo_url or os.environ.get("MONGO_URL") or DEFAULT_MONGO_URL
    name = db_name or os.environ.get("DB_NAME")
    if not name:
        raise BrandError("falta `DB_NAME` (o --db): no se adivina que base se lee")
    client = MongoClient(url, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")  # falla aqui, no a media consulta
    return client[name].sales


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="brands",
        description="Venta por marca. Solo lee, nunca escribe.",
    )
    parser.add_argument("--date", default=None,
                        help="dia de operacion `YYYY-MM-DD` (default: todo el historico)")
    parser.add_argument("--db", default=None, help="base a leer (default: $DB_NAME)")
    parser.add_argument("--mongo-url", default=None, help="default: $MONGO_URL o localhost")
    parser.add_argument("--tenant", default=None, help="`tenant_id`, si la base es multi-empresa")

    args = parser.parse_args(argv)

    try:
        sales = open_sales_collection(args.mongo_url, args.db)
        result = report_by_brand(sales, business_date=args.date, tenant_id=args.tenant)
    except BrandError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["unlabeled_sales"]:
        print(f"\nAVISO: {result['unlabeled_sales']} ventas sin `brand`. "
              f"Corre: python backend/backfill_brand.py")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
