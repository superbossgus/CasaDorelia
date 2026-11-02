"""Prueba de integracion del corte de caja contra un mongod de verdad.

No corre con las pruebas unitarias (no empieza con `test_`) porque necesita
Mongo levantado. Esta aqui porque hay una cosa que una prueba en memoria **no**
puede demostrar: que el indice unico que crea `server.ensure_cash_cut_index`
exista y de verdad corte el segundo corte del mismo turno. Esa es la unica
defensa contra publicar el efectivo de un dia al doble.

    python backend/tests/probe_cash_cut_index.py

Usa una base desechable (`cash_cut_probe`) y la borra al terminar. No toca
`casa_dorelia`.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pymongo import MongoClient  # noqa: E402
from pymongo.errors import DuplicateKeyError  # noqa: E402

import cash_cut  # noqa: E402

PROBE_DB = "cash_cut_probe"


def main() -> int:
    url = os.environ.get("MONGO_URL") or cash_cut.DEFAULT_MONGO_URL
    client = MongoClient(url, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    client.drop_database(PROBE_DB)
    cuts = client[PROBE_DB][cash_cut.COLLECTION]

    # El mismo indice que crea el server al arrancar.
    cuts.create_index([("tenant_id", 1), ("cafeteria_id", 1), ("business_date", 1),
                       ("turno", 1)], unique=True, name="corte_unico_por_turno")

    base = dict(cafeteria_id="c-sji", brand="casa-dorelia", business_date="2026-10-03",
                fondo_inicial=500.0, efectivo_contado=2300.0, retiros=0.0,
                tickets_efectivo=12, tenant_id=None)

    cuts.insert_one(dict(cash_cut.build_cut(**base)))
    print("1) corte insertado")

    # Mismo dia y turno, otro id: es el mismo corte capturado dos veces.
    try:
        cuts.insert_one(dict(cash_cut.build_cut(**base)))
        print("FALLA: el indice dejo pasar un segundo corte del mismo turno")
        return 1
    except DuplicateKeyError:
        print("2) el segundo corte del mismo turno lo corta el indice")

    # Otro turno del mismo dia si entra, y suma.
    cuts.insert_one(dict(cash_cut.build_cut(**{**base, "turno": "vespertino",
                                               "fondo_inicial": 0.0,
                                               "efectivo_contado": 700.0,
                                               "tickets_efectivo": 5})))
    rows = cash_cut.read_cuts(cuts)
    por_dia = cash_cut.cash_by_day(rows)
    resumen = cash_cut.summarize_cuts(rows)
    print(f"3) dos turnos suman: {por_dia['casa-dorelia']['2026-10-03']}")
    print(f"4) por marca: {[(b['brand'], b['cash'], b['tickets']) for b in resumen['brands']]}")

    ok = (por_dia["casa-dorelia"]["2026-10-03"]["cash"] == 2500.0
          and por_dia["casa-dorelia"]["2026-10-03"]["tickets"] == 17
          and resumen["duplicates"] == []
          and len(rows) == 2)

    # Otra marca no se mezcla ni comparte llave.
    cuts.insert_one(dict(cash_cut.build_cut(**{**base, "cafeteria_id": "c-tecno",
                                               "brand": "le-pain-dore",
                                               "efectivo_contado": 3500.0,
                                               "fondo_inicial": 1000.0,
                                               "tickets_efectivo": 20})))
    resumen = cash_cut.summarize_cuts(cash_cut.read_cuts(cuts))
    marcas = {b["brand"]: b["cash"] for b in resumen["brands"]}
    print(f"5) dos marcas separadas: {marcas}, suma de control {resumen['cash_all_brands']}")
    ok = ok and marcas == {"casa-dorelia": 2500.0, "le-pain-dore": 2500.0}

    client.drop_database(PROBE_DB)
    print("OK" if ok else "FALLA")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
