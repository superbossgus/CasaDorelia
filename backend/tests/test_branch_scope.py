"""La sucursal que llega por query, revalidada contra el token (BOS-152).

El defecto que fija esto: 13 rutas metian `cafeteria_id` al filtro sin
compararlo con el del token, y se acotaban solas **solo cuando el parametro
venia vacio**. Un cajero de Tecnoparque pidiendo `?cafeteria_id=c-sji` leia los
numeros de Casa Dorelia, que es otra marca y otro reparto de socios.

Estas pruebas son del helper, no de las rutas: aqui se fija la **regla**
(quien puede pedir que sucursal, y que el filtro de tenant viaje con ella).
Que las 13 rutas la llamen de verdad lo mide `probe_cash_cut_api.py` paso 9,
contra el app levantada. Las dos cosas hacen falta: una regla correcta que una
ruta no invoque no protege nada.

Sin Mongo, sin red y sin importar `server` (que necesita `motor` y un paquete
privado de Emergent).
"""
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from branch_scope import (  # noqa: E402
    BRANCH_SCOPED_ROLES,
    scoped_cafeteria,
    scoped_query,
)

ADMIN = {"role": "admin", "cafeteria_id": None, "tenant_id": None}
GERENTE_SJI = {"role": "gerente", "cafeteria_id": "c-sji", "tenant_id": None}
CAJERO_SJI = {"role": "cajero", "cafeteria_id": "c-sji", "tenant_id": None}
CAJERO_TECNO = {"role": "cajero", "cafeteria_id": "c-tecno", "tenant_id": None}


# ---- lo que no se puede pedir ----

@pytest.mark.parametrize("user", [GERENTE_SJI, CAJERO_SJI])
def test_pedir_otra_sucursal_es_403(user):
    with pytest.raises(HTTPException) as err:
        scoped_cafeteria("c-tecno", user)
    assert err.value.status_code == 403


def test_el_403_no_se_degrada_a_devolver_la_propia():
    """Un 200 con los datos de otra sucursal es peor que un 403.

    Si al cajero de Tecnoparque que pide `c-sji` se le devolvieran en silencio
    sus propios numeros, la pantalla los rotularia como de SJI: dos marcas
    distintas bajo la misma etiqueta.
    """
    with pytest.raises(HTTPException):
        scoped_cafeteria("c-sji", CAJERO_TECNO)


def test_el_motivo_del_403_se_puede_ajustar_por_ruta():
    with pytest.raises(HTTPException) as err:
        scoped_cafeteria("c-sji", CAJERO_TECNO, detail="Solo puedes capturar el corte de tu sucursal")
    assert err.value.detail == "Solo puedes capturar el corte de tu sucursal"
    with pytest.raises(HTTPException) as err:
        scoped_cafeteria("c-sji", CAJERO_TECNO)
    assert "tu sucursal" in err.value.detail


# ---- lo que si se puede pedir ----

@pytest.mark.parametrize("user", [GERENTE_SJI, CAJERO_SJI])
def test_pedir_la_propia_pasa(user):
    assert scoped_cafeteria("c-sji", user) == "c-sji"


@pytest.mark.parametrize("user", [GERENTE_SJI, CAJERO_SJI])
def test_sin_parametro_se_acota_a_la_propia(user):
    """Este es el caso que ya funcionaba. Tiene que seguir funcionando: es la
    llamada que hacen las pantallas."""
    assert scoped_cafeteria(None, user) == "c-sji"


def test_cadena_vacia_cuenta_como_sin_parametro():
    """`?cafeteria_id=` llega como `""`, no como `None`."""
    assert scoped_cafeteria("", CAJERO_SJI) == "c-sji"
    assert scoped_cafeteria("", ADMIN) is None


def test_el_admin_pide_cualquiera():
    assert scoped_cafeteria("c-tecno", ADMIN) == "c-tecno"
    assert scoped_cafeteria("c-sji", ADMIN) == "c-sji"


def test_el_admin_sin_parametro_ve_todas():
    """`None` significa "sin filtro de sucursal". El dueño lee las dos marcas
    juntas pero separadas por renglon (ver `brands.py`)."""
    assert scoped_cafeteria(None, ADMIN) is None


def test_superadmin_tambien_pide_cualquiera():
    super_user = {"role": "superadmin", "cafeteria_id": None}
    assert scoped_cafeteria("c-sji", super_user) == "c-sji"
    assert "superadmin" not in BRANCH_SCOPED_ROLES


def test_un_rol_con_sucursal_pero_sin_asignar_no_queda_ciego():
    """Decision explicita: hoy hay usuarios con rol de sucursal y
    `cafeteria_id` vacio en el token; cerrarles el paso aqui los dejaria sin
    poder leer nada en vez de proteger algo."""
    sin_sucursal = {"role": "gerente", "cafeteria_id": None}
    assert scoped_cafeteria("c-sji", sin_sucursal) == "c-sji"
    assert scoped_cafeteria(None, sin_sucursal) is None


def test_un_token_raro_no_truena():
    assert scoped_cafeteria(None, {}) is None
    assert scoped_cafeteria("c-sji", None) == "c-sji"


# ---- el filtro completo ----

def test_el_filtro_lleva_sucursal_y_tenant():
    scope = scoped_query("c-sji", CAJERO_SJI, {"tenant_id": "t-1"})
    assert scope == {"tenant_id": "t-1", "cafeteria_id": "c-sji"}


def test_el_tenant_viaja_aunque_no_haya_sucursal():
    """Las rutas de `/inventory`, `/purchases` y `/ingredient-inventory/alerts`
    no aplicaban `tenant_filter`. Con `tenant_id` en `None` (modo legacy) no
    habia fuga; con dos cuentas en la base eso cruza empresas, no sucursales."""
    assert scoped_query(None, ADMIN, {"tenant_id": "t-1"}) == {"tenant_id": "t-1"}


def test_sin_tenant_el_filtro_es_solo_la_sucursal():
    assert scoped_query(None, CAJERO_SJI, {}) == {"cafeteria_id": "c-sji"}
    assert scoped_query(None, ADMIN, {}) == {}


def test_el_filtro_de_tenant_no_se_muta():
    """Varias rutas reusan el mismo `tenant_filter` para buscar sucursales y
    productos. Si `scoped_query` lo mutara, esas busquedas quedarian acotadas a
    una sucursal y los nombres saldrian "Desconocida"."""
    tenant_filter = {"tenant_id": "t-1"}
    scoped_query("c-sji", CAJERO_SJI, tenant_filter)
    assert tenant_filter == {"tenant_id": "t-1"}


def test_el_filtro_tambien_levanta_403():
    with pytest.raises(HTTPException) as err:
        scoped_query("c-sji", CAJERO_TECNO, {})
    assert err.value.status_code == 403
