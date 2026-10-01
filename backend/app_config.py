"""La configuracion que la app exige para arrancar: un solo lugar, y que truene.

El problema que resuelve (BOS-103): `JWT_SECRET` se leia asi

    JWT_SECRET = os.environ.get('JWT_SECRET', '<literal en el codigo>')

y el repositorio es publico. Eso hace dos daños a la vez. El obvio es que la
llave era publica. El que lo vuelve real es que **ese respaldo era el que se
usaba**: `.get()` con default no truena, asi que faltando la variable la app
arrancaba igual y firmaba con la llave publicada sin avisarle a nadie.

HS256 es simetrico: la misma llave que verifica un token lo **emite**. Con la
llave en la mano se fabrica la sesion de cualquier usuario, incluido un
administrador de tenant. No es un secreto de lectura, es la autoridad de firma.

De ahi la regla: un secreto que falta tira el arranque, como ya lo hacian
`MONGO_URL` y `DB_NAME` con `os.environ[...]`. Nunca se degrada a un valor
escrito en el codigo.

La regla se generalizo en BOS-105: no solo los secretos: **toda** variable que
la app necesita para arrancar bien entra por aqui. `CORS_ORIGINS` se leia con el
mismo `.get()` con respaldo, y su respaldo era `'*'`.

El modulo es puro a proposito — sin Mongo, sin FastAPI, sin red — igual que
`business_day` o `brands`. Asi la prueba de "sin `JWT_SECRET` no arranca" corre
sin instalar el backend completo, que es justo lo que hace que el supuesto
quede fijado y no solo documentado.
"""
from __future__ import annotations

import os
from typing import List, Mapping, Optional
from urllib.parse import urlsplit

# Minimo de caracteres de una llave de firma. HS256 usa la llave tal cual como
# material del HMAC, asi que una mas corta que el hash (256 bits = 32 bytes)
# aporta menos entropia de la que el algoritmo puede aprovechar y entra en rango
# de diccionario. 32 es el piso, no la recomendacion: `secrets.token_urlsafe(48)`
# da 64 caracteres y es lo que se documenta en el runbook.
MIN_SECRET_LENGTH = 32


class ConfigError(RuntimeError):
    """Falta configuracion obligatoria, o la que hay no sirve."""


def require_setting(name: str, env: Optional[Mapping[str, str]] = None) -> str:
    """Devuelve la variable `name` del entorno, o levanta `ConfigError`.

    La hermana de `require_secret` **sin** el minimo de longitud. Existe porque
    no toda configuracion obligatoria es una llave: `CORS_ORIGINS` es una lista
    de origenes, y exigirle 32 caracteres seria una regla inventada. Lo que
    comparten — y lo unico que importa — es que faltando truenan en vez de
    caerse a un respaldo que nadie eligio.

    Un valor en blanco cuenta como ausente: `CORS_ORIGINS=` en un `.env` es el
    error tipico de copiar la plantilla sin llenarla, y aceptarlo seria el mismo
    silencio que se vino a quitar.
    """
    source = os.environ if env is None else env
    raw = source.get(name)

    if raw is None or not raw.strip():
        raise ConfigError(
            f"Falta la variable de entorno {name}. Es obligatoria: la app no "
            f"arranca sin ella y no tiene valor de respaldo a proposito "
            f"(BOS-103). Ponla en backend/.env o en el entorno del proceso; el "
            f"runbook explica como llenarla."
        )

    return raw.strip()


def require_secret(
    name: str,
    env: Optional[Mapping[str, str]] = None,
    min_length: int = MIN_SECRET_LENGTH,
) -> str:
    """Devuelve el secreto `name` del entorno, o levanta `ConfigError`.

    Se usa en el nivel de modulo de `server.py`, donde una excepcion equivale a
    "la app no arranca". Eso es lo deseado: es preferible un arranque fallido y
    ruidoso a una app viva firmando con una llave que no es secreta.
    """
    value = require_setting(name, env=env)

    if len(value) < min_length:
        raise ConfigError(
            f"{name} tiene {len(value)} caracteres y se exigen al menos "
            f"{min_length}. Genera una llave nueva con "
            f"`python -c \"import secrets; print(secrets.token_urlsafe(48))\"` "
            f"en vez de acortar el minimo."
        )

    return value


def jwt_secret(env: Optional[Mapping[str, str]] = None) -> str:
    """La llave con la que se firman **todas** las sesiones de la app.

    Firma las cuatro superficies de `server.py`: `login`, `register_tenant`,
    `login_loyalty_customer` y `login_partner`. Una sola llave para las cuatro,
    asi que rotarla invalida toda sesion emitida con la anterior — efecto
    buscado cuando la anterior quedo expuesta.
    """
    return require_secret("JWT_SECRET", env=env)


# --------------------------------------------------------------------------
# CORS (BOS-105)
# --------------------------------------------------------------------------

# `http://` se acepta solo contra la maquina local. El navegador no lo prohibe,
# pero la cookie de sesion de esta app sale `secure`, asi que un origen en claro
# que no sea de desarrollo no la recibiria igual, y pedirla por ahi solo sirve
# para filtrarla. `::1` llega sin corchetes desde `urlsplit().hostname`.
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

# Puertos que el navegador **nunca** manda en `Origin`: son los implicitos del
# esquema. `https://app.ejemplo.mx:443` no empata jamas con el `Origin` real
# (`https://app.ejemplo.mx`), porque Starlette compara la cadena completa.
DEFAULT_PORTS = {"http": 80, "https": 443}


def _validate_origin(entry: str, raw: str) -> str:
    """Normaliza un origen de la lista, o levanta `ConfigError` diciendo por que.

    Un "origen" en CORS es esquema + host + puerto, y nada mas. Starlette compara
    el `Origin` de la peticion con estas cadenas **tal cual**, asi que cualquier
    cosa de sobra (una barra final, una ruta, un puerto implicito) no es un
    detalle cosmetico: produce una entrada que no puede empatar con ninguna
    peticion real y se lee como "el CORS no funciona".
    """
    def mal(motivo: str, arregla: str) -> ConfigError:
        return ConfigError(
            f"CORS_ORIGINS tiene una entrada invalida: {entry!r}. {motivo} "
            f"{arregla} Un origen es esquema + host (+ puerto si no es el del "
            f"esquema), por ejemplo `https://app.ejemplo.mx` o "
            f"`http://localhost:3000`. Valor completo recibido: {raw!r}."
        )

    if entry == "*":
        raise ConfigError(
            "CORS_ORIGINS no puede ser `*`: esta app manda credenciales "
            "(`allow_credentials=True`, y la sesion de Google sale en una cookie "
            "`SameSite=None; Secure`). Starlette no emite `*` en ese caso — "
            "**refleja el `Origin` que le llega**, asi que cualquier sitio que "
            "visite un usuario podria llamar al API con la sesion de esa "
            "persona. Pon la lista exacta de origenes del frontend, separados "
            "por coma (BOS-105)."
        )

    if "://" not in entry:
        raise mal("Le falta el esquema.", "Escribe `https://` adelante.")

    partes = urlsplit(entry)

    if partes.scheme not in DEFAULT_PORTS:
        raise mal(
            f"El esquema {partes.scheme!r} no sirve como origen.",
            "Usa `http` o `https`.",
        )

    if partes.path == "/":
        raise mal(
            "Termina en barra.",
            "Quitala: el `Origin` que manda el navegador no la trae.",
        )
    if partes.path:
        raise mal("Trae una ruta.", "Deja solo el host.")
    if partes.query or partes.fragment:
        raise mal("Trae query o fragmento.", "Deja solo esquema y host.")
    if "@" in partes.netloc:
        raise mal("Trae usuario o contraseña.", "Deja solo el host.")

    try:
        puerto = partes.port
    except ValueError:
        raise mal("El puerto no es un numero.", "Corrigelo o quitalo.") from None

    host = partes.hostname
    if not host:
        raise mal("No tiene host.", "Agregalo.")
    if "*" in host:
        raise mal(
            "El host trae comodin.",
            "Starlette compara la cadena completa, no la expande: enumera los "
            "origenes uno por uno.",
        )

    if puerto == DEFAULT_PORTS[partes.scheme]:
        raise mal(
            f"Declara el puerto {puerto}, que es el implicito de "
            f"{partes.scheme}.",
            "Quitalo: el navegador lo omite en `Origin` y asi esta entrada no "
            "empataria con nada.",
        )

    if partes.scheme == "http" and host not in LOOPBACK_HOSTS:
        raise mal(
            "Pide `http` en un host que no es la maquina local.",
            "Usa `https`: la cookie de sesion de esta app sale `Secure` y no "
            "viajaria por ahi, asi que el origen en claro solo expone el API.",
        )

    # El navegador manda el `Origin` con esquema y host en minusculas; el puerto
    # tal cual. Normalizar aqui evita que un `HTTPS://App.Ejemplo.MX` del `.env`
    # no empate nunca por una mayuscula.
    autoridad = host if puerto is None else f"{host}:{puerto}"
    if ":" in host:  # IPv6 literal, vuelve a necesitar corchetes
        autoridad = f"[{host}]" if puerto is None else f"[{host}]:{puerto}"
    return f"{partes.scheme}://{autoridad}"


def cors_origins(env: Optional[Mapping[str, str]] = None) -> List[str]:
    """Los origenes que pueden llamar al API con credenciales.

    Sin respaldo, igual que `JWT_SECRET`. El respaldo anterior era `'*'`, y
    `CORS_ORIGINS` no estaba definida en ningun `.env` ni en el runbook, asi que
    **ese** era el valor efectivo de produccion sin que nadie lo hubiera elegido
    (BOS-105, mismo patron que BOS-103).

    Que `*` sea un error y no una advertencia es el punto de la funcion: con
    `allow_credentials=True`, Starlette 0.37 no responde `*` — refleja el
    `Origin` de la peticion cuando trae cookie, y lo refleja siempre en el
    preflight. Es decir, `*` aqui no es "abierto a lectura publica", es
    "cualquier sitio puede actuar como el usuario que lo visita".
    """
    raw = require_setting("CORS_ORIGINS", env=env)

    origenes: List[str] = []
    for crudo in raw.split(","):
        entry = crudo.strip()
        if not entry:
            raise ConfigError(
                f"CORS_ORIGINS trae una entrada vacia (una coma de sobra, o dos "
                f"seguidas). Se rechaza en vez de ignorarla porque la lista es "
                f"la frontera de seguridad del API y una lista mal escrita a "
                f"medias es peor que ninguna. Valor recibido: {raw!r}."
            )
        normalizado = _validate_origin(entry, raw)
        if normalizado not in origenes:  # repetido: inofensivo, no vale trueno
            origenes.append(normalizado)

    return origenes

