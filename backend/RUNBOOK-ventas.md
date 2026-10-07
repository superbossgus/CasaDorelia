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

## Tablero de ventas (un HTML que se abre con doble clic)

```
python backend/dashboard.py --db casa_dorelia --out C:/tmp/ventas.html
```

Escribe una pagina **autocontenida**: sin CDN, sin servidor, sin `npm`. Se abre
sin red y se puede mandar por WhatsApp. Trae, por marca y por dia de operacion,
el bruto con tarjeta, el numero de cobros y el ticket promedio; mas la hora a la
que cobran, la tabla completa y los controles del dato. Solo lee: no escribe una
linea en Mongo.

Lo que **no** puede hacer, por diseño y con pruebas que lo sostienen
(`backend/tests/test_dashboard.py`):

- publicar un total de las dos marcas como "la venta" — la suma solo existe con
  el nombre `control_sum`, igual que `gross_all_brands` en `brands.py`;
- llamar "venta" al cobro con tarjeta — una cifra sin corte de caja va rotulada
  como piso, porque el efectivo no pasa por la API de Clip. El rotulo se
  **calcula por dia y por marca**: con el corte del dia la celda publica el
  total (tarjeta + efectivo) y deja de decir piso; sin el, lo sigue diciendo
  aunque el dia de al lado si tenga corte;
- dibujar utilidad cuando no la sabe — las ventas de Clip entran con
  `cost_known: false`, asi que una grafica de margen daria cero y se leeria como
  perder todo el margen. El rotulo se **calcula**: el dia que entre venta con
  costo, deja solo de decirlo;
- confundir un cero con un hueco — antes del primer dia de una marca la linea se
  corta, un dia que ya paso sin cobro es un cero, y el dia en curso sin cobro es
  hueco otra vez (a las 07:45 no hay nada que graficar, y una linea que se
  desploma a cero se lee como un derrumbe).

El estado de cada dia sale del dato, no de una nota: `cerrado`, `en curso`, o
`cierre no confirmado` cuando la ultima venta capturada cayo a menos de 30
minutos de la foto de las 19:45. Esa duda dura **un** dia: el catch-up de las
07:45 vuelve a pedir el dia completo y lo confirma.

Para cuadrarlo contra el otro camino de codigo (deben dar identico):

```
python backend/brands.py --db casa_dorelia
```

Sale con codigo 1 si algun control del dato quedo en rojo, para que un cron se
entere sin que alguien tenga que leer el HTML.

### Republicar el tablero (el enlace que abre Gustavo)

El tablero es un HTML generado, o sea una **foto**: no se mueve solo. El enlace
publicado en la tarjeta de BOS-143 es un work product `artifact`, y lo que lo
mantiene al dia es este comando, que corre despues de cada carga de Clip:

```
python backend/publish_dashboard.py --db casa_dorelia \
    --apertura backend/apertura-sji.json \
    --cierres backend/cierres-casa-dorelia.json \
    --issue d79395ba-11be-4c90-a607-db79c74c639e \
    --work-product 853436f7-9720-4a68-8dfa-ddc8c4cfcdf6
```

**`--cierres` no es opcional de facto.** Sin ese archivo, los dias en que una
sucursal no opero se dibujan como ceros *medidos*, o sea que el tablero afirma
que abrio y vendio $0 — 67 veces en el caso de Tecnoparque. Ver la seccion
*Dias sin operacion* abajo.

Tres pasos: regenera el HTML, lo sube como adjunto, y **repunta el work product
al adjunto nuevo**. El tercero es el que importa. Sin el, cada corrida deja un
adjunto mas y el enlace publicado sigue siendo el primero: a los 15 dias habria
30 adjuntos y la cifra que alguien abre seguiria siendo la del `04/10`. El
comando confirma el `attachmentId` que el servidor echa de vuelta, porque un
`PATCH` que contesta 200 y deja el work product apuntando al adjunto viejo es
indistinguible de uno bueno — y es la forma silenciosa de publicar en falso.

**Va aparte de `clip_daily.py` a proposito.** El cargador toca dinero; un tablero
que no se pudo publicar no debe poder cambiar el codigo de salida de una carga
que si entro, porque ese codigo es lo que decide si el corte de las 08:00 confia
en la cifra del dia. Son dos invocaciones: la segunda ya no puede alterar el
resultado de la primera. En la rutina, **lee y reporta el resultado de la carga
antes** de republicar; no encadenes las dos con `&&` ni leas un solo
`$LASTEXITCODE` al final.

Si la republicacion se cae (`exit 1` con la causa en una linea), el enlace sigue
abriendo el tablero anterior. Eso no es silencioso: la pagina calcula su propia
edad al abrirse y, pasadas `STALE_AFTER_HOURS` (13 h, que es el hueco de 12 h
entre las dos republicaciones mas margen), pone arriba de todo *«Este tablero se
genero hace N horas. No es la venta de hoy.»*. Esa cuenta es la unica defensa que
sigue en pie cuando lo que fallo es justamente lo que debia actualizarla.

Si el panel de apertura no cuadra (`load_apertura` es estricto: los conteos de
`apertura-sji.json` tienen que cuadrar con la hoja), el republicado **no** se
cae: publica la venta fresca sin panel y dibuja la razon en la tarjeta. Tumbar la
republicacion ahi dejaria publicado el tablero de ayer, que es peor: cambiaria un
dato viejo rotulado por un dato viejo sin rotular. A mano sigue tronando — quien
corre `dashboard.py` a proposito quiere enterarse del desfase, y para el otro
comportamiento esta `--apertura-optional`.

Para ver que saldria sin publicar nada: `--dry-run`.

## Dias sin operacion (por que un cero no siempre es un cero)

La regla base del tablero es: antes del primer dia de una marca no hay dato
(hueco); **dentro** de su ventana, un dia pasado sin cobro es un cero medido. Esa
segunda mitad solo es verdadera si la sucursal estuvo abierta. Tecnoparque no
cobro del **5/08 al 20/09/2026** (47 dias) ni del **21/04 al 10/05** (20 dias), y
con la regla base sola el tablero publicaba 67 ceros: estaba afirmando, una vez
por dia, que la sucursal abrio y no vendio nada.

Esas ventanas viven en `backend/cierres-casa-dorelia.json`, no en el codigo ni en
la plantilla, porque "esta sucursal no opero" es un dato operativo con dueño y
fecha (la determinacion es de la Jefatura de Tecnoparque, BOS-147). `load_cierres`
lo valida antes de dibujarlo: marca y fechas obligatorias, `from <= to`, y dos
ventanas de la misma marca no se pueden solapar.

Tres cosas que una ventana **no** puede hacer, y las tres estan en codigo, no en
este documento:

1. **No puede esconder dinero.** Si un dia declarado sin operacion trae cobros,
   gana el cobro: se dibuja su cifra y el dia sale en el control
   *«Ventanas sin operacion que el dato contradice»*. Un archivo editado a mano
   no debe poder borrar venta.
2. **No puede fallar en silencio.** Una ventana con el slug de marca mal escrito
   no tapa nada — y "no hacer nada" es como se deja de notar. Entra al mismo
   control.
3. **No cierra a la otra marca.** La columna de estado del eje solo dice
   *«sin operacion»* cuando no opero ninguna marca abierta; con una cerrada y la
   otra vendiendo, el rotulo va en la celda de la cerrada.

Si el archivo no se puede leer, el republicado **no** se cae (misma razon que el
panel de apertura) pero la pagina publica la causa junto a los ceros que la
ventana iba a rotular. A mano sigue tronando; `--cierres-optional` es el otro
comportamiento.

Para que el rotulo cambie de texto (cuando se sepa el motivo del cierre) se edita
`label`/`note` del JSON. Las fechas no se tocan: son la determinacion.

## Pruebas de terminal (no son venta)

Un cobro de prueba de terminal entra de Clip como cobrado, porque lo fue: alguien
paso una tarjeta propia para ver si la terminal funcionaba. Ninguna consulta lo
distingue de una venta, asi que no hay nada que automatizar: se decide por
renglon y se borra por `dedup_key`.

```
python backend/purge_test_charges.py --db casa_dorelia --key clip:PFsJEAov
python backend/purge_test_charges.py --db casa_dorelia --key clip:PFsJEAov --commit
```

Imprime el renglon completo antes de borrarlo (incluido `notes`, que es donde
Clip deja los ultimos cuatro de la tarjeta). Dos topes: **rechaza** cualquier
renglon de `--max-total` o mas (default $50, porque una prueba no cuesta eso) y
**reporta** cualquier llave que no encuentre, porque "ya se purgo" y "esta mal
escrita" se ven igual y las dos necesitan que alguien mire.

El efecto de dejar una prueba no es el monto: el $0.01 del 26/08 partia el hueco
de 47 dias de Tecnoparque en dos (21 + 25) y pintaba ese dia como un dia con
venta de un centavo. Borrado en BOS-148.

## Cifra parcial contra total del dia (lo que un corte puede y no puede citar)

El reporte de apertura tiene tres cortes (08:00, 15:00 y 20:00 CDMX) y la carga
tiene tres slots, cada uno 15 min antes. Ningun corte puede citar la cifra del dia
en curso como «venta del dia», y la razon **no** es una hora de apertura:

> Una cifra del dia `D` solo es citable como total si **alguna carga pidio `D`
> despues de que `D` cerro**. Una carga que corre a las 07:45 —o a las 14:45, o a
> las 19:45— esta parada *dentro* de `D`: por definicion no vio el resto del dia,
> exista o no un cobro temprano.

De ahi sale, sin ninguna hora de apertura, que **el unico corte que puede hablar de
un dia cerrado es el de las 08:00 del dia siguiente** (su carga de las 07:45 vuelve
a pedir el dia anterior completo con `--catch-up 1`).

Hay que decirlo como condicion estructural y no como un umbral de apertura porque
el umbral **caduca**: hasta el 05/10/2026 la defensa de hecho era que SJI nunca
cobraba antes de las 07:45 (record 09:16, que duro cinco dias), y el 06/10 abrio a
las 08:25. El colchon paso de 1 h 31 min a 40 min. El dia que un cobro caiga antes
de las 07:45, un corte que confie en el umbral publica los primeros minutos del dia
como venta del dia — y un numero truncado sin rotulo es peor que no tener numero.

Quien decide es un comando, no la memoria de quien escribe el reporte:

```
# lo que el corte de las 08:00 necesita: ayer (ya cerrado) y hoy (en curso)
python backend/corte_window.py --db casa_dorelia --branch sji \
    --carga-at 2026-10-07T13:45:57+00:00
```

`--carga-at` es el instante de la corrida del cargador, **del registro de la
corrida** (la tarea que creo la rutina `03f5e143`), no de la base. Es obligatorio
en la practica por una razon que se ve igual a un cargador muerto: una corrida que
inserta cero renglones **no deja rastro en `sales`**, asi que `max(imported_at)`
prueba el ultimo *insert*, nunca la ultima corrida. Sin citar la corrida, un dia
sin cobros y un cargador caido son indistinguibles — y el comando lo dice (estado
`sin_evidencia`, codigo de salida 2) en lugar de elegir uno.

Los cinco estados y lo que cada uno autoriza:

| estado | que significa | se publica como |
|---|---|---|
| `sin_evidencia` | cero renglones y sin citar la corrida | nada: hay que citar la corrida |
| `sin_carga` | la corrida citada es anterior al inicio del dia | «no corrio la carga», con la corrida nombrada |
| `sin_cifra` | la carga alcanzo el dia y no trajo cobros | «no observable todavia» |
| `parcial` | hay cobros, la cobertura termina antes del cierre | la cifra **con su hora de corte** y lo que falta del dia |
| `final` | una carga pidio el dia despues de que cerro | bruto del dia con tarjeta |

`final` con cero renglones es un cero **medido** (dia cerrado, o cero con tarjeta),
no un hueco: es lo que lo separa de `sin_cifra`.

Dos cosas que este comando **no** hace, a proposito:

- **No estima ni completa el dia.** Rotula. Un parcial sale con su hora de corte y
  con cuanto dia quedo sin medir; no proyecta el resto.
- **No habla de efectivo.** Eso es otro eje (`cash_cut.py`): una cifra `final`
  sigue siendo *piso* mientras no haya corte de caja. Los dos rotulos van juntos en
  el reporte y ninguno sustituye al otro.

La sucursal se separa por `clip_branch` (`sji` / `tecnoparque`). `brand` **no**
separa sucursales — separa las dos marcas (`casa-dorelia` / `le-pain-dore`) — y
filtrar por ahi devuelve cero renglones en silencio, que se lee exactamente igual
que «no cobro». El conteo por `cafeteria_id` va como control: si no coincide, hay
carga vieja sin `clip_branch` y la salida lo dice en vez de publicar un conteo
corto.

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

## Donde esta el efectivo (medido, no supuesto)

Gustavo lo dijo en BOS-119: los cobros en efectivo **si** se registran en Clip y
se ven en la app. La pregunta era si viajan por la API. Cerrado el
**2026-10-04** con un censo de la taxonomia **completa** (no una muestra): 360
dias de las dos sucursales, deduplicado por folio, agrupado por
`(payment_method, sub_type, card.brand, card.issuer, status)`. **2,329 cobros**:

| | cobros | pesos |
|---|---|---|
| tarjeta bancaria (`DEBIT`/`CREDIT`) | 2,039 | $219,824.11 |
| vales (`OTHER` con emisor: Pluxee, Edenred, Toka, Todito, Scotiabank) | 288 | $32,372.10 |
| cancelaciones (`status` vacio — **no son venta**) | 2 | $113.00 |
| sin tarjeta y **cobrados** | **0** | **$0.00** |
| **rotulados efectivo** | **0** | **$0.00** |

(Montos de consumo, sin propina.) Reproducible con un comando, que es el punto:
el dia que Clip empiece a mandar efectivo, el veredicto cambia solo.

```
python backend/clip_api.py census --branch sji --days 360
python backend/clip_api.py census --branch tecnoparque --days 360
```

El campo que hay que leer es **`efectivo_en_la_api`**. Mientras sea `false`, el
total de este camino es un piso; el dia que sea `true`, hay que cargar el
efectivo y dejar de rotular piso. `rows_without_card` saca aparte los unicos
candidatos a efectivo, con su `status` al lado.

Dos cosas salen de ahi:

1. **El efectivo de la app no viaja por la API de pagos.** Confirmado por
   Gustavo el mismo dia: el **30/08 hubo 5 cobros en efectivo en SJI**, y ese
   dia la API entrega **2** renglones (un cobro con tarjeta de $5.00 y una
   cancelacion de $5.00). Ninguno es efectivo. Y el volumen que falta no es
   anecdotico: reporta **6 a 20 cobros en efectivo al dia por sucursal**.

   De paso cayo el misterio de los dos renglones sin tarjeta: **eran
   cancelaciones**. `?status=cancelled` devuelve exactamente los renglones cuyo
   `status` llega vacio, y el de $108.00 del 21/09 Gustavo lo reconocio como
   "cancelacion de pago con tarjeta". Estaban cargados como venta porque
   `classify_status("")` dice `"paid"`; ver abajo.

   El censo lo cierra sin dejar duda: los **dos** renglones sin tarjeta del año
   traen la misma firma —`sub_type: "CONSUMER"`, marca `XX`, `last4` `0000`, y
   `status` **vacio**—, o sea que una cancelacion llega sin identidad de
   tarjeta. Eso explica la forma sin tener que suponerle efectivo, y deja el
   cajon "sin tarjeta y cobrado" en **cero renglones en 360 dias**.

   Y no es una limitante de nuestra credencial: lo dice la **documentacion de
   Clip**. La [guia de conciliacion](https://developer.clip.mx/docs/conciliacion-de-transacciones-apis-1)
   pone el recibo de un cobro en efectivo en la app, el panel, los reportes
   descargables y el correo de confirmacion — y en **ningun** endpoint. La doc
   de transacciones ademas dice que `OTHER` es "la tarjeta no es de debito ni
   credito, por ejemplo, tarjeta de vales **y pago en efectivo**": el esquema
   admite efectivo en ese cajon, pero en un año no llego ni uno.
2. **La coleccion de efectivo existe, pero no para esta llave.** `GET /cash`
   (y `/cash/payments`, `/cash/register`) contestan `403` con
   *"Authorization header requires 'Credential' parameter"* — el gateway pide
   firma AWS, que es como entra la app, no la llave de comercio. Una ruta que no
   existe contesta `403 Forbidden` pelado (`/pos`, `/money-in`), asi que la
   diferencia dice que la ruta esta ahi y que nos falta el esquema de auth, no
   que el dato no exista. Levantar eso no es configuracion: es otro producto.

### Una cancelacion no es una venta (y estuvo cargada como una)

La API manda `status: ""` en un cobro cancelado. `classify_status("")` devuelve
`"paid"` — correcto para el export del panel, donde una columna de estado
ausente si significa cobrada, y exactamente al reves para la API. Resultado: la
cancelacion de $108.00 del 21/09 entro como venta de Le Pain Dore.

Arreglado en `clip_api._status` (vacio = `reversed`, y `plan_import` salta todo
lo que no este `paid`). Para sacar las que ya entraron:

```
python backend/purge_cancelled.py --db casa_dorelia          # en seco
python backend/purge_cancelled.py --db casa_dorelia --commit
```

Pide a Clip las canceladas con su propio filtro (`?status=cancelled`) y borra
solo los folios que Clip declara cancelados, imprimiendo cada renglon antes.
Corrido el 2026-10-04: 1 renglon fuera ($108.00), `sales` de 118 a 117, y Le
Pain Dore de $8,931.15 a $8,823.15. Es el unico script de esta cadena que
borra, porque un cobro cancelado no es una venta mal etiquetada: no es venta.

### Como traer el efectivo, en orden de preferencia de Gustavo

El camino listo es el **export del panel** (`dashboard.clip.mx > Ventas >
Descargar`), que tiene columna de metodo de pago: `clip_import.py` ya la lee y
`normalize_payment_method` ya mapea "efectivo". Con un archivo, cargar el
efectivo es un comando.

Pero Gustavo pidio (BOS-119, 04/10) **no** empezar por pedirle archivos: que se
siga buscando por API/app. **Ese camino ya se agoto y quedo cerrado**, y no por
falta de intentos sino por contrato: el censo de 2,329 cobros da cero efectivo,
y la propia guia de conciliacion de Clip pone el recibo del efectivo en la app,
el panel, los reportes y el correo — en ningun endpoint. Insistir mas en la API
de pagos es buscar donde el proveedor ya dijo que no esta.

Los tres caminos que quedan, de menos a mas costo:

1. **Credencial del panel como secreto de Paperclip.** El panel es una
   aplicacion web con su propia API, y ahi si vive el efectivo. Requiere que
   Gustavo cargue usuario/contrasena (o la sesion) como secreto — **jamas en un
   comentario ni en el codigo** — y aprobacion explicita, porque toca
   credenciales de pagos.
2. **Pedirle a Clip el alcance.** La llave de comercio cubre pagos de terminal.
   Que la cuenta pueda leer el efectivo por API es una pregunta para soporte /
   el panel de desarrolladores, no un parametro que falte.
3. **Captura del corte de caja en la app propia.** Una pantalla de cierre por
   turno, que ademas sirve para cuadrar contra la caja fisica. Es el unico
   camino que no depende de Clip, y el mas trabajo.

Mientras un dia no tenga corte de caja, su total de este camino es un **piso**.
El tablero lo dice y lo *calcula*, y desde BOS-149 lo calcula **por dia y por
marca** (`limits.cash` y el `cash_state` de cada punto de la serie): un dia con
corte deja de ser piso y el de al lado sigue siendolo. Antes era un solo
booleano para todo el eje (`limits.cash_excluded`), asi que rotulaba piso
tambien los dias que ya tenian corte — y el primer corte capturado habria
dejado de rotular piso los otros 364.

Por dia *y por marca* porque un corte de Casa Dorelia no completa el dia de Le
Pain Dore: son dos sucursales con dos cajones. La publicacion
(`publish_dashboard.py`) lee `cash_cuts` de la misma base sin que haya que
pedirlo; `--sin-cortes` es lo que hay que escribir para volver al piso.

### Re-etiquetar lo ya cargado

Las ventas cargadas antes de BOS-119 quedaron todas como `tarjeta`, vales
incluidos. Para re-etiquetarlas con la misma funcion que usa la carga:

```
python backend/backfill_payment_method.py --db casa_dorelia --dry-run
python backend/backfill_payment_method.py --db casa_dorelia --commit
```

Solo escribe `payment_method` y `notes`, nunca dinero ni llaves, y es
idempotente (la segunda corrida da `to_update: 0`). Corrido el 2026-10-04:
9 renglones cambiaron de cajon en Tecnoparque ($958.10 de vales y $108.00 de
`otro`, antes contados como tarjeta) y 118 reponen el emisor en `notes`.

## Lo que este camino NO hace

- **No trae efectivo.** La API de Clip entrega lo que cobro la terminal (tarjeta
  y vales); el efectivo de la app no pasa por ahi (medido arriba). El total
  cargado siempre es menor a la venta real de la sucursal, y el que lo completa
  es el corte de caja (`cash_cut.py`), no esta carga. El tablero ya suma los
  dos por dia y por marca (BOS-149); el dia sin corte se queda en piso.
- **No mueve inventario.** La venta ya salio por el POS de Clip; descontarla otra
  vez la contaria doble. Los documentos quedan con `inventory_applied: false`.
- **No vuelve a sumar IVA.** El monto de Clip ya viene con IVA incluido; el
  importador solo lo desglosa (`bruto / 1.16`).
- **No cuenta la propina como venta.** Clip entrega `amount` (consumo), `tip` y
  `total`. Se carga `amount`: la propina es del personal.
- **No hay catalogo por API.** Clip no tiene endpoint de catalogo; el export del
  panel es la unica via (`python backend/clip_import.py catalog <x.xlsx> --diff <y.xlsx>`).

## Limites conocidos

- **La ventana maxima de la API es un mes de calendario, no "720 horas".** La
  doc de Clip dice 720 h y eso es falso en febrero. Medido el 2026-10-04
  (BOS-119), con el mismo dia y la misma hora:

  | `from` | `to` | dias | respuesta |
  |---|---|---|---|
  | 2026-01-06 22:08 | 2026-02-06 22:08 | 31 | `200` |
  | 2026-01-06 22:08 | 2026-02-07 22:08 | 32 | `400` |
  | 2026-02-06 22:08 | 2026-03-06 22:08 | 28 | `200` |
  | 2026-02-06 22:08 | 2026-03-06 **23:08** | 28 h+1 | `400` |

  O sea `to <= from + 1 mes`. Un delta fijo de 720 h es **mas largo** que un mes
  de calendario solo cuando la ventana arranca en febrero, y ahi la API contesta
  `400 payclip.bad.request` y se lleva el jalon completo: una mina que explota
  una vez al año, justo en una carga de un año de dinero. `split_window` ya
  avanza por mes de calendario (`add_one_month`), con prueba de regresion.
- El mongod es local a la maquina. **El dia que la app se despliegue hace falta
  una base accesible desde internet** (Atlas u otra). No es camino de ida: la
  base se copia.
- Los reportes de la app agrupan por `created_at` en **UTC**, no por el dia de
  operacion (UTC-6) con el que se guarda `business_date`. Sobre el historico
  cargado eso desfasa 8 de 65 ventas. Pendiente en BOS-97.
