# Runbook: ventas de Clip a la base

Como se carga la venta con tarjeta de las cafeterias del grupo, y que **no**
incluye.

> **Esta base guarda dos marcas, no una.** `c-sji` es Casa Dorelia (Big E Stores)
> y `c-tecno` es Le Pain Dore (Grupo Viter, S.A. de C.V.), con contratos y socios
> distintos. **Nunca publiques el total consolidado como venta de una marca**: el
> 84% de los pesos cargados son de Le Pain Dore. El corte correcto es
> [por marca](#venta-por-marca). Detalle en `brands.py` y BOS-90 / BOS-101.

## Configuracion (una vez por maquina)

`server.py` exige `MONGO_URL`, `DB_NAME`, `JWT_SECRET` y `CORS_ORIGINS`; sin
cualquiera de las cuatro no arranca. Van en `backend/.env`, que **no se
versiona** (`.gitignore` cubre `.env`, `.env.*` y `*.env`, asi que tampoco se
puede dejar un `.env.example` — por eso se documenta aqui):

```
MONGO_URL=mongodb://127.0.0.1:27017
DB_NAME=casa_dorelia
JWT_SECRET=<64 caracteres, generados; ver abajo>
CORS_ORIGINS=http://localhost:3000
```

### `JWT_SECRET`: la llave de firma de las sesiones

Es la llave HS256 con la que se firman **todas** las sesiones de la app —
`login`, `register_tenant`, `login_loyalty_customer` y `login_partner`. HS256 es
simetrico, asi que no es un secreto de lectura: quien tiene la llave **emite**
sesiones, incluida la de un administrador de tenant.

Se genera, no se inventa:

```
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`app_config.require_secret` exige 32 **caracteres** como minimo y trata un valor
en blanco como ausente, que es el error tipico de copiar la plantilla de arriba
sin llenarla. Ojo con lo que mide ese minimo: es un piso de longitud, no de
entropia — `"x" * 32` lo pasa. Sirve para atajar la llave escrita a mano, no para
juzgar que tan aleatoria es. El numero sale de HS256, que usa la llave tal cual
como material del HMAC: por debajo del tamaño del hash (256 bits) no hay forma de
darle al algoritmo toda la entropia que puede aprovechar. Usa el comando de
arriba y el punto es irrelevante: da 64 caracteres aleatorios.

**No tiene valor de respaldo, a proposito.** Hasta BOS-103 se leia con
`os.environ.get('JWT_SECRET', '<literal>')`: el literal estaba en el codigo, el
repositorio es publico, y como `.get()` no truena *ese* era el que firmaba en
realidad — la app arrancaba sin la variable y nadie se enteraba. Ahora un
secreto que falta tira el arranque, igual que `MONGO_URL`. Si alguien vuelve a
ponerle default, truena `backend/tests/test_app_config.py`.

La llave de los entornos del grupo vive en el almacen de secretos de Paperclip
(secreto `JWT_SECRET`, inyectado como `env.JWT_SECRET`), no en el repositorio ni
en un comentario de tarea. **Rotarla invalida toda sesion emitida con la
anterior** — eso es lo que se busca cuando la anterior quedo expuesta, y es
gratis mientras la app no este desplegada.

**Si el proceso muere al arrancar con `ConfigError: Falta la variable de entorno
JWT_SECRET`, no es un bug:** es esta guarda haciendo su trabajo, y significa que
el secreto no llego a *ese* entorno. En un deploy el sintoma es un traceback en el
arranque, no un mensaje de configuracion, asi que vale anotarlo antes de buscar en
otro lado: revisa que el binding `env.JWT_SECRET` este aplicado ahi. El mismo
razonamiento, en la forma corta y sin el contexto de ventas, esta en
[`CONFIG.md`](CONFIG.md), que es la referencia de variables de entorno del backend
y la que existe tambien en `main`.

### `CORS_ORIGINS`: quien puede llamar al API con la sesion del usuario

La lista exacta de origenes del frontend, separados por coma. Un origen es
**esquema + host (+ puerto si no es el del esquema)** y nada mas:

```
CORS_ORIGINS=http://localhost:3000                       # desarrollo
CORS_ORIGINS=https://app.casadorelia.mx                  # un deploy
CORS_ORIGINS=https://app.casadorelia.mx,http://localhost:3000
```

El valor de desarrollo es `http://localhost:3000` porque el frontend se sirve con
`craco start` (puerto 3000 por omision). El valor del deploy se llena el dia que
exista el dominio; hoy no hay uno (el deploy de Emergent esta apagado).

**No puede ser `*`, y eso es un error de arranque, no una advertencia.** Se
esperaria que con `*` el navegador descartara la respuesta por traer
credenciales — molesto pero inofensivo. No es lo que pasa: con
`allow_credentials=True`, Starlette **refleja** el `Origin` de la peticion
cuando trae cookie, y lo refleja siempre en el preflight. Esta app manda
`session_token` como cookie `SameSite=None; Secure` en `google_auth`, asi que con
`*` cualquier sitio que visitara un usuario podria llamar a este API **como ese
usuario**. Esta medido en
`backend/tests/test_cors_origins.py::test_starlette_refleja_el_origen_con_asterisco_y_credenciales`.

El arranque rechaza, diciendo cual entrada y por que:

| Se rechaza | Por que |
|---|---|
| `*` | Con credenciales no es "API publico", es suplantacion (arriba). |
| `app.casadorelia.mx` | Sin esquema no es un origen. |
| `https://app.casadorelia.mx/` | El `Origin` del navegador no trae barra final; esa entrada no empata con nada. |
| `https://app.casadorelia.mx/admin` | Un origen no lleva ruta. CORS no es por ruta. |
| `https://app.casadorelia.mx:443` | Puerto implicito: el navegador lo omite, asi que no empataria. |
| `https://*.casadorelia.mx` | Starlette compara la cadena completa, no expande comodines. Enumera los subdominios. |
| `http://app.casadorelia.mx` | `http` solo contra `localhost` / `127.0.0.1` / `[::1]`. La cookie sale `Secure` y no viajaria por ahi de todos modos. |
| `https://a.mx,,https://b.mx` | Coma de sobra: `split(',')` dejaria una entrada vacia. |

Mayusculas y entradas repetidas se normalizan en vez de truenar
(`HTTPS://App.MX` → `https://app.mx`).

**Lo que no hay que hacer para quitarse un error de CORS:** poner
`allow_origin_regex` con un patron ancho, o reflejar el `Origin` de la peticion.
Las dos cosas callan al navegador y reabren el agujero completo. Hay una prueba
que falla si `allow_origin_regex` aparece en `server.py`. Si el frontend se
mudo, la respuesta es agregar su origen a esta lista. Razonamiento en
`app_config.py` y BOS-105.

Las credenciales de Clip **no van en el `.env`**. Viven en el almacen de
secretos de Paperclip y llegan al entorno del run que las necesita:
`CLIP_API_KEY_SJI`, `CLIP_SECRET_KEY_SJI`, `CLIP_API_KEY_TECNOPARQUE`,
`CLIP_SECRET_KEY_TECNOPARQUE`. Una credencial por sucursal: la de SJI **no** ve
las ventas de Tecnoparque.

### Bases que hay en el mongod local y cual es la buena

| Base | Que es |
|---|---|
| `casa_dorelia` | **Dinero real.** Es la que apunta el `.env`. Guarda las dos marcas. |
| `casa_dorelia_local` | Demo sembrada (Dore Central / Norte / Sur, direcciones inventadas). |
| `casa_dorelia_bos73_check` | Fixture de pruebas de BOS-73. |

Nunca cargar venta real en las dos ultimas.

## Sucursales

```
python backend/branches_init.py --db casa_dorelia            # en seco
python backend/branches_init.py --db casa_dorelia --commit   # escribe
```

Idempotente: se puede correr siempre. Tambien es la via de corregir el nombre, la
marca o el domicilio de una sucursal — se edita `GROUP_BRANCHES` y se vuelve a
correr. Las ventas ya cargadas no se mueven, porque cuelgan del `id` (`c-sji`,
`c-tecno`), que nunca cambia.

| `id` | Nombre | `brand` | Vehiculo |
|---|---|---|---|
| `c-sji` | Casa Dorelia San Jose Insurgentes | `casa-dorelia` | Big E Stores |
| `c-tecno` | Le Pain Dore Tecnoparque | `le-pain-dore` | Grupo Viter, S.A. de C.V. |

## Venta por marca

```
python backend/brands.py --db casa_dorelia --date 2026-09-30   # un dia
python backend/brands.py --db casa_dorelia                     # historico
```

Devuelve un renglon por marca, cada uno con su vehiculo (quien reparte ese
dinero). El total general viene como `gross_all_brands`, nombrado asi a proposito:
**no es la venta de ninguna de las dos marcas**, es la suma de dos repartos
distintos. Lo mismo por API, para la app:

```
GET /api/reports/sales-by-brand?date=2026-09-30
```

Una venta sin `brand` no se cae del reporte: cae en el renglon `sin-marca` y se
cuenta en `unlabeled_sales`. Si ves ese renglon, corre el backfill:

```
python backend/backfill_brand.py --dry-run   # dice que sellaria
python backend/backfill_brand.py             # sella
```

Solo agrega `brand` donde falta, por `_id`, derivandola de la sucursal de la
venta. **No toca `id` ni `dedup_key`**, asi que no puede romper la idempotencia
de la carga. Tambien corre solo al arrancar el server, igual que el de
`business_date`: una venta capturada por una version anterior se quedaria fuera
del corte por marca para siempre.

> **Ojo en esta maquina:** ese CLI (y el de `backfill_business_date.py`) necesita
> `motor` y `python-dotenv`, que **no estan instalados** en el mongod local —
> estan en `requirements.txt`, pero el entorno de esta maquina solo tiene
> `pymongo`. Hasta que se instalen, el backfill corre por el arranque del server,
> o envolviendo la coleccion de `pymongo` en la forma async que espera
> `backfill()`. El de BOS-101 se aplico asi.

### Por que `brand` y no `tenant_id`

En `server.py` un tenant es la **cuenta SaaS** (plan, `max_branches`, logo,
facturacion), no una marca. Separar las marcas con `tenant_id` rompe el cupo de
sucursales, esconde `c-tecno` de quien hoy lee todo (Gustavo, que es dueño de las
dos y las quiere ver juntas pero separadas por renglon) y haria que
`branches_init` no reconociera la sucursal y la duplicara. El razonamiento
completo esta en `brands.py`.

## Corte del dia (solo lectura, no escribe)

```
python backend/clip_api.py corte --branch tecnoparque --from 2026-10-01 --to 2026-10-01
```

Sale del mismo `plan_import` que hace la carga, asi que el total que se lee aqui
es identico al que se insertaria.

## Carga

```
# en seco (default): enseña el plan y el corte, no escribe
python backend/clip_load.py --branch sji --from 2026-09-21 --to 2026-10-01 \
    --cafeteria c-sji --db casa_dorelia

# escribe
python backend/clip_load.py --branch sji --from 2026-09-21 --to 2026-10-01 \
    --cafeteria c-sji --db casa_dorelia --commit
```

Mapeo sucursal de Clip → cafeteria en la base:

| `--branch` | `--cafeteria` |
|---|---|
| `sji` | `c-sji` |
| `tecnoparque` | `c-tecno` |

### Carga diaria (la que corre sola)

Nadie tiene que correr lo anterior a mano para el corte del dia. Eso lo hace:

```
python backend/clip_daily.py --db casa_dorelia --catch-up 1 --commit
```

Un comando para **todas** las sucursales, sin fechas. Resuelve las dos cosas
donde es facil equivocarse al armar un disparo programado:

- **Que dia es "hoy".** Lo calcula con `business_day.BUSINESS_TZ` (UTC-6), no con
  UTC. El disparo de la tarde cae a las `01:45Z`, que en UTC ya es el dia
  siguiente: con `utcnow().date()` pediria un dia que apenas empieza y el corte
  de las 20:00 CDMX saldria en cero.
- **Que sucursales son.** Las lee de `GROUP_BRANCHES`, con su `--cafeteria` y su
  `brand`. Una tercera sucursal entra sola el dia que se abra.

`--catch-up 1` recarga tambien el dia anterior, y no es de sobra: la corrida de
la tarde ve hasta las 19:45 locales, asi que la venta de 19:45 a cerrar solo la
puede recoger la corrida de la mañana siguiente. Sin eso esas horas no se
cargarian nunca.

Una sucursal que falla no detiene a la otra (son cuentas distintas, y la falla
tipica — una credencial revocada — es de una sola). El codigo de salida es 1 si
alguna fallo, y `db_rows` dice cuantos renglones quedaron en la base: **cero con
`ok: true` significa "no cobro con tarjeta ese dia", que es distinto de "no
corrio"**.

Quien lo dispara: la rutina de Paperclip *Carga de ventas de Clip a casa_dorelia*
(`03f5e143`), con dos horarios en `America/Mexico_City` — `45 7 * * *` y
`45 19 * * *`, 15 min antes de cada corte del reporte de apertura (`0 8` y
`0 20`, misma zona). Estan separados a proposito: dos fuentes de despertar en el
mismo minuto se pelean el lock del run y una de las dos se pierde.
`concurrencyPolicy` es `always_enqueue`, no `coalesce_if_active`, porque con
coalescencia una corrida de la mañana que siguiera abierta se **comeria** la
carga de la tarde — justo la falla que esto viene a arreglar.

Para recuperar un dia suelto que se quedo sin cargar:

```
python backend/clip_daily.py --db casa_dorelia --date 2026-09-29 --commit
```

**Reimportar el mismo rango es seguro.** La idempotencia cuelga de `dedup_key`
(`clip:<id de transaccion>`). Ojo con un detalle no obvio: las filas de la API
de Clip llegan **sin** `dedup_key` — la deriva el importador — asi que la
primera consulta a la base sale siempre vacia para este origen y *toda* la
proteccion depende de la segunda consulta de `plan_against_db`. Hay una prueba
que fija ese supuesto; si alguien quita la segunda consulta por "redundante", la
prueba truena en lugar de duplicar ventas en silencio.

## Lo que este camino NO hace

- **No trae efectivo.** La API de Clip solo entrega cobros con tarjeta. El total
  cargado siempre es menor a la venta real de la sucursal, por diseño.
- **No mueve inventario.** La venta ya salio por el POS de Clip; descontarla otra
  vez la contaria doble. Los documentos quedan con `inventory_applied: false`.
- **No vuelve a sumar IVA.** El monto de Clip ya viene con IVA incluido; el
  importador solo lo desglosa (`bruto / 1.16`).
- **No cuenta la propina como venta.** Clip entrega `amount` (consumo), `tip` y
  `total`. Se carga `amount`: la propina es del personal.
- **No hay catalogo por API.** Clip no tiene endpoint de catalogo; el export del
  panel es la unica via (`python backend/clip_import.py catalog <x.xlsx> --diff <y.xlsx>`).

## Limites conocidos

- El mongod es local a la maquina. **El dia que la app se despliegue hace falta
  una base accesible desde internet** (Atlas u otra). No es camino de ida: la
  base se copia.
- Los reportes de la app agrupan por `created_at` en **UTC**, no por el dia de
  operacion (UTC-6) con el que se guarda `business_date`. Sobre el historico
  cargado eso desfasa 8 de 65 ventas. Pendiente en BOS-97.
