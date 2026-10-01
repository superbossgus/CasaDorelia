"""Sin `JWT_SECRET` la app no arranca, y nadie puede volver a ponerle respaldo.

Lo que se fija aqui es un supuesto de seguridad, no una funcion (BOS-103). La
falla original no fue que la llave estuviera mal: fue que **faltaba** y la app
siguio de largo firmando con un literal del repositorio, que es publico. HS256
es simetrico, asi que ese literal alcanzaba para emitir la sesion de cualquier
usuario, administrador incluido.

Por eso hay tres niveles de prueba y no uno:

1. `require_secret` / `jwt_secret` levantan `ConfigError` cuando el valor falta,
   viene en blanco o es demasiado corto para firmar.
2. El proceso **de verdad muere**: se corre un interprete aparte con el entorno
   limpio y se revisa el codigo de salida. Una prueba que solo mira la excepcion
   en memoria no distingue "levanta" de "levanta y alguien la atrapa".
3. El texto de `server.py` no vuelve a tener un default para `JWT_SECRET`. Este
   es el que importa a largo plazo: el bug se reintroduce en un segundo
   cambiando `os.environ[...]` por `.get(..., 'algo')`, y eso no lo detecta
   ninguna prueba de comportamiento porque la app arrancaria perfecto.

`server.py` no se puede importar en esta maquina (`motor` y
`emergentintegrations` no estan instalados), y es justamente por eso que la
lectura del secreto vive en `app_config`, un modulo puro.
"""
import os
import re
import subprocess
import sys

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app_config import (  # noqa: E402
    MIN_SECRET_LENGTH,
    ConfigError,
    jwt_secret,
    require_secret,
)

# Una llave valida cualquiera, de pruebas. No es la de ningun entorno real.
LLAVE_DE_PRUEBA = "x" * MIN_SECRET_LENGTH


# --------------------------------------------------------------------------
# 1. El valor que falta levanta, el que sirve pasa
# --------------------------------------------------------------------------

def test_jwt_secret_sin_variable_levanta():
    with pytest.raises(ConfigError) as err:
        jwt_secret(env={})
    # El mensaje tiene que decir que variable falta y donde ponerla: este error
    # aparece en el arranque de un deploy, donde no hay nadie leyendo el codigo.
    assert "JWT_SECRET" in str(err.value)
    assert "backend/.env" in str(err.value)


@pytest.mark.parametrize("vacio", ["", "   ", "\n", "\t"])
def test_jwt_secret_en_blanco_cuenta_como_ausente(vacio):
    # `JWT_SECRET=` en un .env a medio llenar es el error tipico. Aceptarlo
    # seria el mismo silencio que esta prueba viene a quitar.
    with pytest.raises(ConfigError):
        jwt_secret(env={"JWT_SECRET": vacio})


def test_jwt_secret_corto_levanta():
    corta = "x" * (MIN_SECRET_LENGTH - 1)
    with pytest.raises(ConfigError) as err:
        jwt_secret(env={"JWT_SECRET": corta})
    assert str(MIN_SECRET_LENGTH) in str(err.value)


def test_jwt_secret_valido_se_devuelve_sin_espacios():
    valor = jwt_secret(env={"JWT_SECRET": f"  {LLAVE_DE_PRUEBA}  "})
    assert valor == LLAVE_DE_PRUEBA


def test_require_secret_sirve_para_cualquier_nombre():
    # El modulo no es solo de JWT: el siguiente secreto obligatorio entra por la
    # misma puerta en vez de volver a inventar un `.get()` con respaldo.
    assert require_secret("OTRO", env={"OTRO": LLAVE_DE_PRUEBA}) == LLAVE_DE_PRUEBA
    with pytest.raises(ConfigError):
        require_secret("OTRO", env={})


def test_require_secret_lee_el_entorno_real_por_omision(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", LLAVE_DE_PRUEBA)
    assert jwt_secret() == LLAVE_DE_PRUEBA
    monkeypatch.delenv("JWT_SECRET")
    with pytest.raises(ConfigError):
        jwt_secret()


# --------------------------------------------------------------------------
# 2. El proceso muere de verdad
# --------------------------------------------------------------------------

def _correr_en_proceso_aparte(jwt_env_value):
    """Importa `app_config` y pide la llave en un interprete limpio.

    Se usa un proceso aparte porque lo que se quiere medir es el **codigo de
    salida**: que levante dentro de la prueba no demuestra que el arranque de la
    app se caiga.
    """
    env = {k: v for k, v in os.environ.items() if k != "JWT_SECRET"}
    if jwt_env_value is not None:
        env["JWT_SECRET"] = jwt_env_value
    # Sin .env en el camino: `app_config` no llama a `load_dotenv`, pero el
    # directorio de trabajo se fija de todos modos para que la importacion
    # resuelva igual que en `server.py`.
    return subprocess.run(
        [sys.executable, "-c", "import app_config; app_config.jwt_secret()"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def test_el_proceso_se_cae_sin_jwt_secret():
    resultado = _correr_en_proceso_aparte(None)
    assert resultado.returncode != 0
    assert "ConfigError" in resultado.stderr
    assert "JWT_SECRET" in resultado.stderr


def test_el_proceso_arranca_con_una_llave_de_verdad():
    # La contraparte: si la prueba de arriba pasara por cualquier otra razon
    # (un ImportError, por ejemplo), esta tambien fallaria.
    resultado = _correr_en_proceso_aparte(LLAVE_DE_PRUEBA)
    assert resultado.returncode == 0, resultado.stderr


# --------------------------------------------------------------------------
# 3. `server.py` no puede volver a tener un respaldo
# --------------------------------------------------------------------------

def _fuente_del_server():
    with open(os.path.join(BACKEND_DIR, "server.py"), encoding="utf-8") as fh:
        return fh.read()


def test_server_toma_la_llave_del_modulo_que_levanta():
    fuente = _fuente_del_server()
    asignaciones = [
        # Un comentario al final de la linea no cambia de donde sale la llave,
        # asi que no deberia tumbar la prueba: el siguiente que anote esa linea
        # recibiria un fallo que no explica nada. Se recorta antes de comparar.
        expresion.split("#")[0].strip()
        for expresion in re.findall(
            r"^JWT_SECRET\s*=\s*(.+)$", fuente, flags=re.MULTILINE
        )
    ]
    assert asignaciones == ["jwt_secret()"], (
        "JWT_SECRET debe salir de app_config.jwt_secret(), que levanta cuando "
        f"falta. Se encontro: {asignaciones}"
    )


def test_server_no_tiene_default_para_jwt_secret():
    fuente = _fuente_del_server()
    # Las dos formas de leer el entorno con respaldo. `os.getenv` entra en la
    # misma alternancia a proposito: es sinonimo exacto de `os.environ.get` y
    # reintroduce el bug igual, asi que una guarda que solo mire `environ.get`
    # promete en su nombre una cobertura que no tiene.
    con_respaldo = re.search(
        r"""(?:environ\.get|getenv)\(\s*['"]JWT_SECRET['"]\s*,""", fuente
    )
    assert con_respaldo is None, (
        "JWT_SECRET volvio a tener un valor de respaldo en el codigo. Un "
        "secreto que falta tiene que tirar el arranque, no caerse a un literal "
        "versionado (BOS-103)."
    )
