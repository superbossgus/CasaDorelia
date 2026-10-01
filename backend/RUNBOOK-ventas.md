# Runbook: ventas de Clip a la base

Como se carga la venta con tarjeta de Casa Dorelia, y que **no** incluye.

## Configuracion (una vez por maquina)

`server.py` exige `MONGO_URL` y `DB_NAME`; sin ellas no arranca. Van en
`backend/.env`, que **no se versiona** (`.gitignore` cubre `.env`, `.env.*` y
`*.env`, asi que tampoco se puede dejar un `.env.example` — por eso se documenta
aqui):

```
MONGO_URL=mongodb://127.0.0.1:27017
DB_NAME=casa_dorelia
```

Las credenciales de Clip **no van en el `.env`**. Viven en el almacen de
secretos de Paperclip y llegan al entorno del run que las necesita:
`CLIP_API_KEY_SJI`, `CLIP_SECRET_KEY_SJI`, `CLIP_API_KEY_TECNOPARQUE`,
`CLIP_SECRET_KEY_TECNOPARQUE`. Una credencial por sucursal: la de SJI **no** ve
las ventas de Tecnoparque.

### Bases que hay en el mongod local y cual es la buena

| Base | Que es |
|---|---|
| `casa_dorelia` | **Dinero real.** Es la que apunta el `.env`. |
| `casa_dorelia_local` | Demo sembrada (Dore Central / Norte / Sur, direcciones inventadas). |
| `casa_dorelia_bos73_check` | Fixture de pruebas de BOS-73. |

Nunca cargar venta real en las dos ultimas.

## Sucursales

```
python backend/branches_init.py --db casa_dorelia            # en seco
python backend/branches_init.py --db casa_dorelia --commit   # escribe
```

Idempotente: se puede correr siempre. Tambien es la via de corregir el nombre o
el domicilio de una sucursal — se edita `CASA_DORELIA_BRANCHES` y se vuelve a
correr. Las ventas ya cargadas no se mueven, porque cuelgan del `id` (`c-sji`,
`c-tecno`), que nunca cambia.

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
- **Que sucursales son.** Las lee de `CASA_DORELIA_BRANCHES`, con su
  `--cafeteria`. Una tercera sucursal entra sola el dia que se abra.

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
