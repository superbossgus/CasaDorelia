"""Sella `brand` en las ventas que nacieron sin marca (BOS-101).

`casa_dorelia` guarda el dinero de dos marcas distintas del mismo grupo (Casa
Dorelia y Le Pain Dore, ver `brands.py`). Las ventas cargadas antes de que
existiera el campo no dicen de cual son, asi que **no se pueden separar por
consulta**: un total consolidado publica dinero de Le Pain Dore como venta de
Casa Dorelia, y el 84% de los pesos cargados son de la primera.

Lo que hace y lo que **no**:

- Agrega `brand` donde falta. Nada mas. No toca `id`, no toca `dedup_key`, no
  borra ni reinserta nada: la idempotencia de la carga de Clip cuelga de
  `dedup_key` y aqui no se roza. Los updates van por `_id`.
- La marca **no se adivina**: sale de la sucursal de la venta (`cafeteria_id`),
  primero del catalogo en la base (`cafeterias.brand`) y si ahi no esta, de
  `branches_init.GROUP_BRANCHES`. Una venta de una sucursal que nadie etiqueto se
  **reporta** como `unmapped` en vez de recibir una marca inventada, igual que el
  backfill de `business_date` reporta las ventas sin fecha legible.

Es idempotente: solo toca documentos donde el campo falta o viene vacio, asi que
la segunda corrida no cambia nada. Por eso corre tambien al arrancar el servidor:
`POST /api/sales` sella la marca desde BOS-101, pero una venta capturada por una
version anterior del server se quedaria fuera del corte por marca para siempre.

Uso a mano (lee `MONGO_URL` y `DB_NAME` del `.env` del backend):

    python backfill_brand.py --dry-run
    python backfill_brand.py
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from branches_init import brand_for

logger = logging.getLogger(__name__)

# Ventas sin marca. `{"campo": None}` en Mongo empata tanto el campo ausente como
# el nulo; el `""` cubre un sellado a medias.
MISSING_BRAND = {"$or": [{"brand": None}, {"brand": ""}]}

# Cuantos documentos por `bulk_write`. Es para no armar una lista de escrituras
# del tamaño de la coleccion, no un limite de cuantos se arreglan.
BATCH_SIZE = 500


def plan_backfill(sales: Iterable[Mapping[str, Any]],
                  brand_by_cafeteria: Mapping[str, Optional[str]],
                  ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Decide que sellar y que no, sin tocar la base.

    Devuelve `(por_sellar, sin_marca)`:

    - `por_sellar`: `{"_id", "id", "brand"}` por cada venta cuya sucursal si
      tiene marca conocida.
    - `sin_marca`: las ventas cuya `cafeteria_id` no esta en el catalogo, o esta
      sin marca. Esas se reportan: una venta que no se sabe de quien es tiene que
      verse, no que el backfill le ponga la marca mas probable.
    """
    to_stamp: List[Dict[str, Any]] = []
    unmapped: List[Dict[str, Any]] = []

    for sale in sales:
        cafeteria_id = sale.get("cafeteria_id")
        brand = brand_by_cafeteria.get(cafeteria_id) if cafeteria_id else None
        if brand:
            to_stamp.append({"_id": sale.get("_id"), "id": sale.get("id"), "brand": brand})
        else:
            unmapped.append({"_id": sale.get("_id"), "id": sale.get("id"),
                             "cafeteria_id": cafeteria_id})

    return to_stamp, unmapped


async def brand_map(cafeterias_collection) -> Dict[str, Optional[str]]:
    """Marca por sucursal: el catalogo de la base manda, el codigo es respaldo.

    El catalogo de la base es la version que un humano pudo corregir con
    `branches_init --commit`, asi que gana. El respaldo en codigo existe para que
    el backfill sirva **antes** de volver a sembrar las sucursales: si no, habria
    que acordarse de correr dos comandos en el orden correcto.
    """
    docs = await cafeterias_collection.find({}, {"_id": 0, "id": 1, "brand": 1}).to_list(None)
    mapping: Dict[str, Optional[str]] = {}
    for doc in docs:
        cafeteria_id = doc.get("id")
        if cafeteria_id:
            mapping[cafeteria_id] = doc.get("brand") or brand_for(cafeteria_id)
    return mapping


async def backfill(sales_collection, cafeterias_collection, *, dry_run: bool = False,
                   batch_size: int = BATCH_SIZE) -> Dict[str, Any]:
    """Aplica el plan sobre la coleccion `sales`. Devuelve el resumen para el log."""
    from pymongo import UpdateOne  # local: mantiene el modulo importable sin Mongo

    mapping = await brand_map(cafeterias_collection)

    cursor = sales_collection.find(MISSING_BRAND, {"_id": 1, "id": 1, "cafeteria_id": 1})
    pending: List[Mapping[str, Any]] = await cursor.to_list(None)

    to_stamp, unmapped = plan_backfill(pending, mapping)

    stamped = 0
    if to_stamp and not dry_run:
        for start in range(0, len(to_stamp), batch_size):
            chunk = to_stamp[start:start + batch_size]
            result = await sales_collection.bulk_write(
                # Por `_id` y con `$set` de un solo campo: ni `id` ni `dedup_key`
                # entran en la escritura, asi que no hay forma de re-llavear.
                [UpdateOne({"_id": row["_id"]}, {"$set": {"brand": row["brand"]}})
                 for row in chunk],
                ordered=False,
            )
            stamped += result.modified_count

    by_brand: Dict[str, int] = {}
    for row in to_stamp:
        by_brand[row["brand"]] = by_brand.get(row["brand"], 0) + 1

    return {
        "examined": len(pending),
        "to_stamp": len(to_stamp),
        "stamped": stamped,
        "by_brand": by_brand,
        "unmapped": len(unmapped),
        "unmapped_cafeterias": sorted({str(r["cafeteria_id"]) for r in unmapped}),
        "dry_run": dry_run,
    }


async def _main() -> None:
    from dotenv import load_dotenv
    from motor.motor_asyncio import AsyncIOMotorClient

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="dice que sellaria y no escribe nada")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_dotenv(Path(__file__).parent / ".env")

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    try:
        db = client[os.environ["DB_NAME"]]
        summary = await backfill(db.sales, db.cafeterias, dry_run=args.dry_run)
    finally:
        client.close()

    logger.info("ventas sin marca revisadas: %s", summary["examined"])
    logger.info("marca sellada: %s", summary["stamped"] if not summary["dry_run"]
                else f"{summary['to_stamp']} (en seco, no se escribio)")
    for brand, count in sorted(summary["by_brand"].items()):
        logger.info("  %s: %s", brand, count)
    if summary["unmapped"]:
        logger.warning("ventas de una sucursal sin marca en el catalogo: %s -> %s",
                       summary["unmapped"], summary["unmapped_cafeterias"])


if __name__ == "__main__":
    asyncio.run(_main())
