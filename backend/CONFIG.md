# Configuracion del backend

Las variables de entorno que el backend necesita. Se leen de `backend/.env`
(via `load_dotenv`) o del entorno del proceso; da igual cual de los dos.

`backend/.env` **no se versiona** — `.gitignore` lo cubre con `*.env`. Los
valores reales viven en el almacen de secretos, no en el repositorio.

## Obligatorias

Las tres tiran el arranque si faltan. Eso es a proposito: es preferible un
proceso que muere con un mensaje claro a uno vivo con una configuracion que
nadie eligio.

| Variable | Que es | Ejemplo |
|---|---|---|
| `MONGO_URL` | Cadena de conexion de MongoDB | `mongodb://localhost:27017` |
| `DB_NAME` | Base de datos a usar | `casa_dorelia` |
| `JWT_SECRET` | Llave con la que se firman **todas** las sesiones | ver abajo |

### `JWT_SECRET`

Generala asi, y pegala en `backend/.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Tres cosas que conviene saber antes de tocarla:

- **Minimo 32 caracteres.** La app rechaza una mas corta. HS256 usa la llave tal
  cual como material del HMAC, asi que por debajo del tamaño del hash (256 bits)
  no hay forma de darle toda la entropia que puede aprovechar. El comando de
  arriba da 64 caracteres.
- **Rotarla invalida toda sesion vigente.** Es una sola llave para las cuatro
  superficies de sesion (`login`, `register_tenant`, `login_loyalty_customer`,
  `login_partner`), y HS256 es simetrico: la misma llave que verifica un token lo
  emite. Al cambiarla, todo token firmado con la anterior deja de valer y la
  gente vuelve a entrar. Eso es lo deseado cuando la anterior quedo expuesta.
- **No hay valor de respaldo, y no hay que ponerle uno.** Hasta BOS-103 se leia
  con `os.environ.get('JWT_SECRET', '<literal>')`, con el literal en este
  repositorio, que es publico. Como `.get()` no truena, ese literal era el valor
  que de hecho se usaba. Hay pruebas en `backend/tests/test_app_config.py` que
  fallan si alguien le vuelve a poner default.

## Si el proceso muere al arrancar

```
ConfigError: Falta la variable de entorno JWT_SECRET...
```

No es un bug: es la guarda de arriba haciendo su trabajo. Significa que
`JWT_SECRET` no llego a **ese** entorno. En un deploy el sintoma es un traceback
en el arranque, no un mensaje de configuracion, asi que vale anotarlo: revisa que
el binding del secreto este aplicado en ese entorno antes de buscar en otro lado.
Lo mismo aplica a `MONGO_URL` y `DB_NAME`, que fallan con `KeyError`.

## Opcionales

Integraciones que se apagan solas si no estan configuradas (Twilio, Resend,
Stripe, Google OAuth). No hacen falta para levantar el backend.
