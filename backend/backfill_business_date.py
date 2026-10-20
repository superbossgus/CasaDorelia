"""Sella `business_date` en las ventas que nacieron sin el.

Desde BOS-97 los reportes cortan por `business_date` (dia de operacion, UTC-6)
en vez de por `created_at` (UTC). Una venta sin `business_date` quedaria fuera
de **todos** los reportes, asi que el backfill no es cosmetico: es lo que hace
seguro el cambio de campo. Por eso corre solo al arrancar el servidor, ademas
de poderse correr a mano.

Es idempotente: solo toca documentos donde el campo falta o viene vacio, y
deriva el dia de `created_at` con el mismo `business_day.business_date` que usa
la carga de Clip. Correrlo dos veces no cambia nada la segunda vez.

Uso a mano (lee `MONGO_URL` y `DB_NAME` del `.env` del backend):

    python backfill_business_date.py --dry-run
    python backfill_business_date.py
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple

from business_day import sale_business_date

logger = logging.getLogger(__name__)

# Documentos a los que les falta el dia de operacion. `{"campo": None}` en Mongo
# empata tanto el campo ausente como el nulo; el `""` cubre un sellado a medias.
MISSING_BUSINESS_DATE = {"$or": [{"business_date": None}, {"business_date": ""}]}

# Cuantos documentos se mandan por `bulk_write`. Es para no armar una lista de
# escrituras del tamaño de la coleccion, no un limite de cuantos se arreglan.
BATCH_SIZE = 500


def plan_backfill(sales: Iterable[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Decide que sellar y que no, sin tocar la base.

    Devuelve `(por_sellar, sin_fecha)`:

    - `por_sellar`: `{"id", "business_date"}` por cada venta cuyo dia se pudo
      derivar de `created_at`.
    - `sin_fecha`: las ventas que no traen `created_at` legible. Esas se
      reportan en vez de inventarles un dia: una venta sin fecha es un dato
      roto y quien opera tiene que verlo, no que el backfill lo tape.
    """
    to_stamp: List[Dict[str, Any]] = []
    undated: List[Dict[str, Any]] = []

    for sale in sales:
        day = sale_business_date(sale)
        if day:
            to_stamp.append({"id": sale.get("id"), "_id": sale.get("_id"), "business_date": day})
        else:
            undated.append({"id": sale.get("id"), "_id": sale.get("_id"),
                            "created_at": sale.get("created_at")})

    return to_stamp, undated


async def backfill(sales_collection, *, dry_run: bool = False,
                   batch_size: int = BATCH_SIZE) -> Dict[str, Any]:
    """Aplica el plan sobre la coleccion `sales` de Mongo.

    `sales_collection` es la coleccion de motor. Devuelve el resumen de lo que
    paso, que es lo que se registra en el log al arrancar.
    """
    from pymongo import UpdateOne  # local: mantiene el modulo importable sin Mongo

    cursor = sales_collection.find(MISSING_BUSINESS_DATE, {"_id": 1, "id": 1, "created_at": 1})
    pending: List[Mapping[str, Any]] = await cursor.to_list(None)

    to_stamp, undated = plan_backfill(pending)

    stamped = 0
    if to_stamp and not dry_run:
        for start in range(0, len(to_stamp), batch_size):
            chunk = to_stamp[start:start + batch_size]
            result = await sales_collection.bulk_write(
                [UpdateOne({"_id": row["_id"]}, {"$set": {"business_date": row["business_date"]}})
                 for row in chunk],
                ordered=False,
            )
            stamped += result.modified_count

    return {
        "examined": len(pending),
        "to_stamp": len(to_stamp),
        "stamped": stamped,
        "undated": len(undated),
        "undated_ids": [row["id"] for row in undated[:20]],
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
        summary = await backfill(db.sales, dry_run=args.dry_run)
    finally:
        client.close()

    logger.info("ventas revisadas: %s", summary["examined"])
    logger.info("dia de operacion sellado: %s", summary["stamped"] if not summary["dry_run"]
                else f"{summary['to_stamp']} (en seco, no se escribio)")
    if summary["undated"]:
        logger.warning("ventas sin `created_at` legible: %s -> %s",
                       summary["undated"], summary["undated_ids"])


if __name__ == "__main__":
    asyncio.run(_main())
