"""Un CORS que el navegador va a rechazar — o que abre el API — no arranca.

Lo que se fija aqui es la frontera de quien puede llamar al API **con la sesion
del usuario** (BOS-105). Se leia asi:

    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(',')

con `allow_credentials=True`. `CORS_ORIGINS` no estaba definida en ningun `.env`
ni en el runbook, asi que `'*'` era el valor que corria.

El detalle que vuelve esto una falla real y no una advertencia de estilo esta
medido en `test_starlette_refleja_el_origen_con_asterisco_y_credenciales`:
Starlette **no** responde `Access-Control-Allow-Origin: *` cuando
`allow_credentials=True`. Refleja el `Origin` de la peticion si trae cookie, y lo
refleja siempre en el preflight. Es decir, `*` no se traduce en "API de lectura
publica" — se traduce en "cualquier sitio que visite un usuario puede actuar como
ese usuario". Y esta app manda una cookie `SameSite=None; Secure` en
`google_auth`, que es exactamente la credencial que viajaria.

Esa prueba existe porque el supuesto es de una libreria de terceros: si una
version futura de Starlette cambiara el comportamiento, es mejor enterarse por
una prueba que explica el porque que por una revision de seguridad.
"""
import os
import re
import subprocess
import sys

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app_config import (  # noqa: E402
    ConfigError,
    cors_origins,
    require_setting,
)

PROD = "https://app.casadorelia.mx"
DEV = "http://localhost:3000"


# --------------------------------------------------------------------------
# 1. La lista valida pasa, y pasa normalizada
# --------------------------------------------------------------------------

def test_una_lista_valida_se_acepta():
    assert cors_origins(env={"CORS_ORIGINS": f"{PROD},{DEV}"}) == [PROD, DEV]


def test_se_toleran_los_espacios_alrededor_de_la_coma():
    # Separar con `, ` es lo natural al escribir un `.env` a mano; que eso
    # cambiara el significado seria una trampa.
    assert cors_origins(env={"CORS_ORIGINS": f" {PROD} ,  {DEV} "}) == [PROD, DEV]


def test_un_solo_origen_tambien_es_una_lista():
    assert cors_origins(env={"CORS_ORIGINS": PROD}) == [PROD]


def test_el_host_y_el_esquema_se_bajan_a_minusculas():
    # El navegador manda `Origin` en minusculas y Starlette compara la cadena
    # completa. Sin normalizar, una mayuscula en el `.env` da un origen que no
    # empata con nada y se lee como "el CORS no funciona".
    assert cors_origins(env={"CORS_ORIGINS": "HTTPS://App.CasaDorelia.MX"}) == [PROD]


def test_el_repetido_no_truena_pero_no_se_duplica():
    assert cors_origins(env={"CORS_ORIGINS": f"{PROD},{PROD}"}) == [PROD]


def test_el_puerto_que_no_es_el_del_esquema_se_conserva():
    assert cors_origins(env={"CORS_ORIGINS": "https://app.ejemplo.mx:8443"}) == [
        "https://app.ejemplo.mx:8443"
    ]


@pytest.mark.parametrize("loopback", [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://[::1]:3000",
])
def test_http_se_acepta_contra_la_maquina_local(loopback):
    # El frontend de desarrollo se sirve en claro; prohibirlo obligaria a cada
    # quien a inventarse un certificado local o a desactivar la validacion.
    assert cors_origins(env={"CORS_ORIGINS": loopback}) == [loopback]


# --------------------------------------------------------------------------
# 2. `*` con credenciales no arranca
# --------------------------------------------------------------------------

def test_asterisco_no_arranca():
    with pytest.raises(ConfigError) as err:
        cors_origins(env={"CORS_ORIGINS": "*"})
    mensaje = str(err.value)
    # El error tiene que explicar el porque: aparece en el arranque de un
    # deploy, donde nadie esta leyendo este archivo.
    assert "allow_credentials" in mensaje
    assert "Origin" in mensaje


def test_asterisco_escondido_en_la_lista_tampoco_arranca():
    # El "arreglo" tentador es dejar `*` al final por si acaso. Eso anula la
    # lista entera: Starlette activa `allow_all_origins` con una sola entrada.
    with pytest.raises(ConfigError):
        cors_origins(env={"CORS_ORIGINS": f"{PROD},*"})


# --------------------------------------------------------------------------
# 3. La entrada mal formada no arranca
# --------------------------------------------------------------------------

@pytest.mark.parametrize("entrada,porque", [
    ("app.casadorelia.mx", "sin esquema"),
    ("https://app.casadorelia.mx/", "con barra final"),
    ("https://app.casadorelia.mx/admin", "con ruta"),
    ("https://app.casadorelia.mx?x=1", "con query"),
    ("https://app.casadorelia.mx#x", "con fragmento"),
    ("https://user:pass@app.casadorelia.mx", "con credenciales en la URL"),
    ("ftp://app.casadorelia.mx", "esquema que no es http(s)"),
    ("https://*.casadorelia.mx", "comodin en el host"),
    ("https://app.casadorelia.mx:443", "puerto implicito de https"),
    ("http://localhost:80", "puerto implicito de http"),
    ("https://app.casadorelia.mx:no", "puerto que no es numero"),
    ("https://", "sin host"),
    ("http://app.casadorelia.mx", "http en un host que no es local"),
])
def test_entrada_mal_formada_no_arranca(entrada, porque):
    with pytest.raises(ConfigError) as err:
        cors_origins(env={"CORS_ORIGINS": entrada})
    # El mensaje tiene que citar la entrada culpable: la lista puede traer
    # varias y "CORS_ORIGINS invalido" no dice cual corregir.
    assert entrada in str(err.value), porque


def test_la_entrada_culpable_se_senala_dentro_de_una_lista_buena():
    with pytest.raises(ConfigError) as err:
        cors_origins(env={"CORS_ORIGINS": f"{PROD},https://otro.mx/,{DEV}"})
    assert "https://otro.mx/" in str(err.value)


@pytest.mark.parametrize("lista", [
    f"{PROD},",
    f",{PROD}",
    f"{PROD},,{DEV}",
    f"{PROD}, ,{DEV}",
])
def test_una_coma_de_sobra_no_arranca(lista):
    # `'a,'.split(',')` da `['a', '']`, y `''` en la lista de Starlette es una
    # entrada que no empata con nada. Se rechaza en vez de ignorarla: esta lista
    # es la frontera de seguridad del API.
    with pytest.raises(ConfigError):
        cors_origins(env={"CORS_ORIGINS": lista})


# --------------------------------------------------------------------------
# 4. La variable que falta no arranca (el patron de BOS-103)
# --------------------------------------------------------------------------

def test_sin_variable_no_arranca():
    with pytest.raises(ConfigError) as err:
        cors_origins(env={})
    assert "CORS_ORIGINS" in str(err.value)
    assert "backend/.env" in str(err.value)


@pytest.mark.parametrize("vacio", ["", "   ", "\n", "\t"])
def test_en_blanco_cuenta_como_ausente(vacio):
    with pytest.raises(ConfigError):
        cors_origins(env={"CORS_ORIGINS": vacio})


def test_cors_origins_lee_el_entorno_real_por_omision(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", PROD)
    assert cors_origins() == [PROD]
    monkeypatch.delenv("CORS_ORIGINS")
    with pytest.raises(ConfigError):
        cors_origins()


def test_require_setting_no_exige_largo_de_secreto():
    # La razon de que exista en vez de reusar `require_secret`: una lista de
    # origenes corta es legitima, una llave de firma corta no.
    assert require_setting("OTRO", env={"OTRO": "x"}) == "x"
    with pytest.raises(ConfigError):
        require_setting("OTRO", env={})


# --------------------------------------------------------------------------
# 5. El proceso muere de verdad
# --------------------------------------------------------------------------

def _correr_en_proceso_aparte(valor):
    """Pide los origenes en un interprete limpio y devuelve el resultado.

    Igual que en `test_app_config`: lo que se mide es el **codigo de salida**.
    Que la excepcion aparezca dentro de la prueba no demuestra que el arranque
    de la app se caiga.
    """
    env = {k: v for k, v in os.environ.items() if k != "CORS_ORIGINS"}
    if valor is not None:
        env["CORS_ORIGINS"] = valor
    return subprocess.run(
        [sys.executable, "-c", "import app_config; app_config.cors_origins()"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("valor", [None, "*", "app.casadorelia.mx"])
def test_el_proceso_se_cae_con_un_cors_invalido(valor):
    resultado = _correr_en_proceso_aparte(valor)
    assert resultado.returncode != 0
    assert "ConfigError" in resultado.stderr


def test_el_proceso_arranca_con_una_lista_valida():
    # La contraparte: si la prueba de arriba pasara por cualquier otra razon (un
    # ImportError, por ejemplo), esta tambien fallaria.
    resultado = _correr_en_proceso_aparte(PROD)
    assert resultado.returncode == 0, resultado.stderr


# --------------------------------------------------------------------------
# 6. `server.py` no puede volver a tener un respaldo
# --------------------------------------------------------------------------

def _fuente_del_server():
    with open(os.path.join(BACKEND_DIR, "server.py"), encoding="utf-8") as fh:
        return fh.read()


def test_server_toma_los_origenes_del_modulo_que_levanta():
    fuente = _fuente_del_server()
    asignaciones = re.findall(r"^CORS_ORIGINS\s*=\s*(.+)$", fuente, flags=re.MULTILINE)
    assert asignaciones == ["cors_origins()"], (
        "CORS_ORIGINS debe salir de app_config.cors_origins(), que levanta "
        f"cuando falta o no sirve. Se encontro: {asignaciones}"
    )


def test_server_no_tiene_default_para_cors_origins():
    fuente = _fuente_del_server()
    con_respaldo = re.search(r"""environ\.get\(\s*['"]CORS_ORIGINS['"]\s*,""", fuente)
    assert con_respaldo is None, (
        "CORS_ORIGINS volvio a tener un valor de respaldo en el codigo. Lo que "
        "lo hace grave es que el respaldo natural es `'*'`, que con "
        "`allow_credentials=True` abre el API a cualquier sitio (BOS-105)."
    )


def test_server_no_refleja_el_origen_de_la_peticion():
    """El "arreglo" que hay que impedir: quitarse el error reflejando el Origin.

    `allow_origin_regex` con un patron ancho, o pasar el `Origin` de la peticion
    a `allow_origins`, hace que el navegador deje de quejarse **y** abre
    exactamente el agujero que esta tarea viene a cerrar. No tiene por que
    aparecer nunca en este archivo.
    """
    fuente = _fuente_del_server()
    assert "allow_origin_regex" not in fuente, (
        "allow_origin_regex no se usa aqui a proposito: un patron ancho vuelve "
        "a aceptar cualquier origen con credenciales. Enumera los origenes "
        "(BOS-105)."
    )


# --------------------------------------------------------------------------
# 7. Lo que Starlette hace de verdad con `*` + credenciales
# --------------------------------------------------------------------------

def _app_con_cors(origenes):
    from starlette.applications import Starlette
    from starlette.middleware.cors import CORSMiddleware
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    async def ping(request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/ping", ping)])
    app.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_origins=origenes,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return TestClient(app)


def test_la_lista_validada_autoriza_al_frontend_y_niega_al_resto():
    """La prueba de que la normalizacion sirve, no solo de que no truena.

    Un parser que acepta `HTTPS://App.MX` y lo guarda tal cual pasa todas las
    pruebas de arriba y **no autoriza a nadie**, porque Starlette compara contra
    el `Origin` en minusculas que manda el navegador. Esto lo monta de verdad.
    """
    pytest.importorskip("starlette")
    pytest.importorskip("httpx")

    cliente = _app_con_cors(cors_origins(env={"CORS_ORIGINS": "HTTPS://App.CasaDorelia.MX"}))

    permitido = cliente.get("/ping", headers={"Origin": PROD, "Cookie": "session_token=x"})
    assert permitido.headers["access-control-allow-origin"] == PROD
    assert permitido.headers["access-control-allow-credentials"] == "true"

    # El que no esta en la lista no recibe la cabecera, asi que el navegador
    # descarta la respuesta: es el comportamiento que `*` se estaba saltando.
    ajeno = cliente.get(
        "/ping",
        headers={"Origin": "https://sitio-de-un-tercero.example", "Cookie": "session_token=x"},
    )
    assert "access-control-allow-origin" not in ajeno.headers


def test_starlette_refleja_el_origen_con_asterisco_y_credenciales():
    """La medicion que justifica que `*` sea un error y no una advertencia.

    Se esperaria que con `allow_origins=['*']` Starlette respondiera
    `Access-Control-Allow-Origin: *` y que el navegador descartara la respuesta
    por traer credenciales — molesto, pero no explotable. No es lo que pasa:
    cuando la peticion trae cookie, Starlette **refleja** el origen, y en el
    preflight lo refleja siempre. El navegador acepta eso, porque es una
    respuesta de origen especifico perfectamente valida.
    """
    starlette = pytest.importorskip("starlette")
    pytest.importorskip("httpx")  # TestClient lo necesita

    cliente = _app_con_cors(["*"])
    atacante = "https://sitio-de-un-tercero.example"

    # Con cookie: el origen del atacante vuelve reflejado y autorizado a leer la
    # respuesta. Esta app manda `session_token` como cookie `SameSite=None`, asi
    # que la cookie **va** en esa peticion.
    con_cookie = cliente.get(
        "/ping", headers={"Origin": atacante, "Cookie": "session_token=x"}
    )
    assert con_cookie.headers["access-control-allow-origin"] == atacante, (
        f"Starlette {starlette.__version__} ya no refleja el origen; revisa si "
        f"el razonamiento de BOS-105 sigue aplicando"
    )
    assert con_cookie.headers["access-control-allow-credentials"] == "true"

    # En el preflight no hace falta ni la cookie.
    preflight = cliente.options(
        "/ping",
        headers={
            "Origin": atacante,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert preflight.headers["access-control-allow-origin"] == atacante
    assert preflight.headers["access-control-allow-credentials"] == "true"
