"""Los secretos que la app exige para arrancar: un solo lugar, y que truene.

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

El modulo es puro a proposito — sin Mongo, sin FastAPI, sin red — igual que
`business_day` o `brands`. Asi la prueba de "sin `JWT_SECRET` no arranca" corre
sin instalar el backend completo, que es justo lo que hace que el supuesto
quede fijado y no solo documentado.
"""
from __future__ import annotations

import os
from typing import Mapping, Optional

# Minimo de **caracteres** de una llave de firma. Es un piso de longitud, no una
# medida de entropia: `"x" * 32` lo pasa. Sirve para atajar la llave escrita a
# mano y de paso la de un `.env` copiado a medias, no para juzgar que tan
# aleatoria es. El numero sale de HS256, que usa la llave tal cual como material
# del HMAC: por debajo del tamaño del hash (256 bits = 32 bytes) no hay forma de
# darle al algoritmo toda la entropia que puede aprovechar. 32 es el piso, no la
# recomendacion: `secrets.token_urlsafe(48)` da 64 caracteres y es lo que se
# documenta en `backend/CONFIG.md`.
MIN_SECRET_LENGTH = 32


class ConfigError(RuntimeError):
    """Falta un secreto obligatorio, o el que hay no sirve para firmar."""


def require_secret(
    name: str,
    env: Optional[Mapping[str, str]] = None,
    min_length: int = MIN_SECRET_LENGTH,
) -> str:
    """Devuelve el secreto `name` del entorno, o levanta `ConfigError`.

    Se usa en el nivel de modulo de `server.py`, donde una excepcion equivale a
    "la app no arranca". Eso es lo deseado: es preferible un arranque fallido y
    ruidoso a una app viva firmando con una llave que no es secreta.

    Un valor en blanco cuenta como ausente: `JWT_SECRET=` en un `.env` es el
    error tipico de copiar la plantilla sin llenarla, y aceptarlo seria el mismo
    silencio que se vino a quitar.
    """
    source = os.environ if env is None else env
    raw = source.get(name)

    if raw is None or not raw.strip():
        raise ConfigError(
            f"Falta la variable de entorno {name}. Es obligatoria: la app no "
            f"arranca sin ella y no tiene valor de respaldo a proposito "
            f"(BOS-103). Ponla en backend/.env o en el entorno del proceso; "
            f"backend/CONFIG.md explica como generarla."
        )

    value = raw.strip()
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
