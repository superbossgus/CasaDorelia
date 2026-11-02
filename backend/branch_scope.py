"""La sucursal por la que filtra una consulta, revalidada contra el token.

El defecto que origina este modulo (BOS-150, ruta `GET /api/cash-cuts`): las
rutas recibian `cafeteria_id` por query y lo metian al filtro **sin compararlo**
con el `cafeteria_id` del token. La lista se acotaba sola **solo cuando el
parametro venia vacio**, asi que un cajero de Tecnoparque que pidiera
`?cafeteria_id=c-sji` leia los numeros de Casa Dorelia — que es otra marca, con
otro reparto de socios (ver `brands.py`).

La regla vive aqui, una vez, porque el patron estaba en 13 rutas (BOS-152) y la
numero 14 se habria olvidado. Vive **fuera** de `server.py` para que se pueda
probar sin Mongo ni backend levantado: `server.py` no se puede ni importar en
una caja sin `motor`.
"""
from typing import Optional

from fastapi import HTTPException

# Los roles con sucursal propia. Son los valores de `UserRole` en `server.py`
# (`gerente` / `cajero`); `admin` y `superadmin` leen cualquier sucursal a
# proposito, porque el dueño es el mismo en las dos marcas.
BRANCH_SCOPED_ROLES = ("gerente", "cajero")

DEFAULT_DETAIL = "Solo puedes consultar los datos de tu sucursal"


def scoped_cafeteria(
    cafeteria_id: Optional[str],
    current_user: Optional[dict],
    detail: Optional[str] = None,
) -> Optional[str]:
    """La sucursal por la que hay que filtrar, o `None` para "todas".

    - Rol con sucursal propia (`gerente`, `cajero`): **siempre** su sucursal. Si
      pide otra explicitamente, 403; no se le devuelve la suya en silencio,
      porque entonces la pantalla rotularia los numeros de SJI como si fueran de
      Tecnoparque.
    - `admin` / `superadmin`: lo que pidan, y sin `cafeteria_id` ven todas.
    - Un rol con sucursal pero con el campo vacio en el token cae en el caso del
      admin. Es deliberado: hoy `cafeteria_id` llega `None` para los usuarios
      sin sucursal asignada y cerrarlo aqui los dejaria sin leer nada.

    `detail` solo cambia el texto del 403 (capturar / ver / consultar).
    """
    user = current_user or {}
    own = user.get("cafeteria_id")
    if user.get("role") in BRANCH_SCOPED_ROLES and own:
        if cafeteria_id and cafeteria_id != own:
            raise HTTPException(status_code=403, detail=detail or DEFAULT_DETAIL)
        return own
    return cafeteria_id or None


def scoped_query(
    cafeteria_id: Optional[str],
    current_user: Optional[dict],
    tenant_filter: Optional[dict] = None,
    detail: Optional[str] = None,
) -> dict:
    """El filtro de alcance completo: cuenta (tenant) + sucursal.

    Las dos cosas van juntas a proposito. Varias rutas tenian el filtro de
    sucursal pero **no** el de tenant (`/inventory`, `/purchases`,
    `/ingredient-inventory/alerts`): hoy `tenant_id` esta en `None` para las dos
    sucursales (modo legacy, ver `branches_init.py`) y no hay fuga, pero el dia
    que haya dos cuentas en la base eso cruzaria empresas, no solo sucursales.
    """
    scope = dict(tenant_filter or {})
    branch = scoped_cafeteria(cafeteria_id, current_user, detail=detail)
    if branch:
        scope["cafeteria_id"] = branch
    return scope
