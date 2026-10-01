"""Asegura las sucursales reales en la base destino, sin tocar lo que ya existe.

Para que existe: la carga de ventas (`clip_load.py`) escribe en `sales` con un
`cafeteria_id`, y ese id tiene que corresponder a un documento real de
`cafeterias` o la app muestra "Desconocida" en todos los reportes. Las bases de
demo que habia en la maquina traian sucursales inventadas (Dore Central / Norte
/ Sur), asi que la base de dinero real se levanta desde aqui y queda por escrito
cual es cada sucursal.

    # ver que haria, sin escribir (default)
    python backend/branches_init.py --db casa_dorelia

    # crear/actualizar de verdad
    python backend/branches_init.py --db casa_dorelia --commit

Es **idempotente**: corre las veces que quieras. Busca por `id`, que es estable
y lo elige este archivo (no un uuid aleatorio), justo para que una segunda
corrida reconozca la sucursal en lugar de duplicarla.

### Por que `tenant_id` queda en `None`

`server.py` trata a un usuario sin `tenant_id` como "legacy" y le devuelve un
filtro vacio (`get_tenant_filter`), o sea que ve todas las sucursales. Casa
Dorelia es **un** negocio con varias sucursales, no varios negocios, asi que el
modo legacy es el que corresponde. Y hay una razon practica: un tenant nuevo
nace con `max_branches: 1` (plan de prueba), de modo que `POST /api/cafeterias`
rechazaria la segunda sucursal con 403. Crear el tenant hoy seria pagar ese
costo sin necesitarlo.

No es un camino de ida: el dia que el grupo meta varias empresas en la misma
base, un `update_many` siembra `tenant_id` en `cafeterias` y en `sales`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEFAULT_MONGO_URL = "mongodb://127.0.0.1:27017"

# Las sucursales reales de Casa Dorelia / Big E Stores.
#
# `id` es el que ya usan los comandos de carga (`--cafeteria c-sji`) y los
# fixtures de pruebas; se mantiene estable a proposito.
#
# `address` esta a nivel colonia porque es lo que esta confirmado. El domicilio
# exacto lo tiene que dar Gustavo o la jefatura de cada sucursal; se corrige con
# otra corrida de este mismo script y no afecta a las ventas ya cargadas, que
# cuelgan del `id`.
CASA_DORELIA_BRANCHES: List[Dict[str, Any]] = [
    {
        "id": "c-sji",
        "name": "Casa Dorelia San Jose Insurgentes",
        "address": "San Jose Insurgentes, Benito Juarez, CDMX",
        "phone": None,
        "is_active": True,
        # Sucursal en Clip de la que salen sus ventas con tarjeta.
        "clip_branch": "sji",
    },
    {
        "id": "c-tecno",
        "name": "Casa Dorelia Tecnoparque",
        "address": "Tecnoparque, Azcapotzalco, CDMX",
        "phone": None,
        "is_active": True,
        "clip_branch": "tecnoparque",
    },
]

# Campos que una segunda corrida puede corregir. `id` y `created_at` no estan:
# el primero es la llave y el segundo es historia, no configuracion.
UPDATABLE = ("name", "address", "phone", "is_active", "clip_branch")


class BranchInitError(RuntimeError):
    """Algo impide sembrar las sucursales. Siempre dice que falta."""


def ensure_branches(cafeterias: Any, branches: Sequence[Mapping[str, Any]], *,
                    tenant_id: Optional[str] = None, commit: bool = False,
                    now: Optional[datetime] = None) -> Dict[str, Any]:
    """Crea las que falten y corrige las que cambiaron. No borra nada.

    Devuelve el detalle por sucursal para que la salida sirva de evidencia:
    `created`, `updated` (con los campos que cambiaron) o `unchanged`.
    """
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    tenant_filter = {"tenant_id": tenant_id} if tenant_id else {}

    detail: List[Dict[str, Any]] = []
    for spec in branches:
        existing = cafeterias.find_one({**tenant_filter, "id": spec["id"]}, {"_id": 0})

        if existing is None:
            doc = {**spec, "tenant_id": tenant_id, "created_at": stamp}
            if commit:
                cafeterias.insert_one(dict(doc))
            detail.append({"id": spec["id"], "action": "created", "name": spec["name"]})
            continue

        changes = {f: spec[f] for f in UPDATABLE
                   if f in spec and existing.get(f) != spec[f]}
        if not changes:
            detail.append({"id": spec["id"], "action": "unchanged", "name": spec["name"]})
            continue

        if commit:
            cafeterias.update_one({**tenant_filter, "id": spec["id"]}, {"$set": changes})
        detail.append({"id": spec["id"], "action": "updated", "name": spec["name"],
                       "changes": changes})

    return {
        "committed": bool(commit),
        "created": sum(1 for d in detail if d["action"] == "created"),
        "updated": sum(1 for d in detail if d["action"] == "updated"),
        "unchanged": sum(1 for d in detail if d["action"] == "unchanged"),
        "branches": detail,
    }


def open_cafeterias_collection(mongo_url: Optional[str] = None,
                               db_name: Optional[str] = None):
    """Coleccion `cafeterias`, con un mensaje util cuando falta configuracion."""
    try:
        from pymongo import MongoClient
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise BranchInitError("falta el driver de Mongo: pip install pymongo") from exc

    url = mongo_url or os.environ.get("MONGO_URL") or DEFAULT_MONGO_URL
    name = db_name or os.environ.get("DB_NAME")
    if not name:
        raise BranchInitError(
            "falta `DB_NAME` (o --db): no se adivina en que base se crean las sucursales"
        )
    client = MongoClient(url, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")  # falla aqui, no a medio insert
    return client[name].cafeterias


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="branches_init",
        description="Asegura las sucursales reales en la base. En seco por default.",
    )
    parser.add_argument("--db", default=None, help="base destino (default: $DB_NAME)")
    parser.add_argument("--mongo-url", default=None, help="default: $MONGO_URL o localhost")
    parser.add_argument("--tenant", default=None,
                        help="`tenant_id`, solo si la base es multi-empresa")
    parser.add_argument("--commit", action="store_true",
                        help="escribir de verdad; sin esto solo enseña el plan")

    args = parser.parse_args(argv)

    try:
        cafeterias = open_cafeterias_collection(args.mongo_url, args.db)
        result = ensure_branches(cafeterias, CASA_DORELIA_BRANCHES,
                                 tenant_id=args.tenant, commit=args.commit)
    except BranchInitError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not args.commit:
        print("\n(en seco: no se escribio nada. Agrega --commit para crearlas)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
