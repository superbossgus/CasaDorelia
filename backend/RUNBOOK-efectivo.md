# El efectivo: de donde sale y como se captura

## Por que existe este documento

La carga de Clip (`clip_daily.py`, BOS-119) trae **solo** lo que cobro la
terminal. El efectivo que la app de Clip registra **no viaja por su API**, y eso
ya no es una sospecha:

- **Censo de la taxonomia completa**: 2,329 cobros de 360 dias de las dos
  sucursales, agrupados por `(payment_method, sub_type, marca, emisor, status)`.
  **Cero** rotulados efectivo. Reproducible:
  `python backend/clip_api.py census --branch tecnoparque --days 360`
  (el campo a leer es `efectivo_en_la_api`; **se calcula**, asi que el dia que
  Clip empiece a mandarlo el veredicto cambia solo).
- **La doc de Clip dice lo mismo**: su guia de conciliacion pone el recibo del
  cobro en efectivo en la app, el panel, los reportes descargables y el correo —
  en ningun endpoint. Y la referencia publica de APIs (Checkout, PinPad,
  Refunds, Transactions, Deposits) no tiene nada de efectivo.

Consecuencia operativa: **un dia sin corte de caja tiene una cifra que es piso,
no la venta del dia.** Dos piezas, dos fuentes:

| Pieza | Fuente | Entra sola |
|---|---|---|
| Tarjeta y vales | API de Clip (`clip_daily.py`, 07:45 y 19:45 CDMX) | si |
| Efectivo | corte de caja capturado en el app | no: alguien lo cuenta |

## Como se captura (pantalla)

`Corte de Caja` en el menu, o la ruta `corte-caja` del app. La abre tambien el
**cajero**: es quien cierra el cajon.

Se capturan los tres numeros que **se pueden contar**:

| Campo | Que es |
|---|---|
| `fondo_inicial` | con cuanto abrio la caja (lo propone el corte anterior) |
| `efectivo_contado` | todo lo que hay en el cajon al cerrar, **incluido el fondo** |
| `retiros` | lo que salio del cajon en el dia (depositos, pagos, traslados) |

La venta en efectivo **no se captura**: la deriva el servidor.

    ventas_efectivo = efectivo_contado + retiros - fondo_inicial

Opcionales: `tickets_efectivo` (cuantos cobros) y `notas`.

### Lo que la pantalla no te va a dejar hacer

- **Guardar un efectivo negativo.** Significa que falta un retiro o que el fondo
  esta mal. Guardarlo restaria venta de un dia que si vendio.
- **Guardar un dedazo de ceros.** `115600` en vez de `1156.00` choca con un tope
  de cordura de $200,000 por corte.
- **Capturar dos veces el mismo turno.** La segunda captura te ofrece
  **corregir** la primera. Lo impide tambien un indice unico de
  `(tenant_id, cafeteria_id, business_date, turno)`, que es lo que corta la
  carrera entre dos capturas simultaneas.
- **Mover un corte de dia, sucursal, turno o marca.** Eso se arregla capturando
  el corte correcto, no editando el guardado.
- **Corregir sin decir por que**, y solo admin/gerente: el monto anterior, quien
  y el motivo quedan en `revisions`.

### Un corte en cero SI se captura

Es el caso que mas se olvida y el mas util: `$0.00` de efectivo es un cero
**medido**, y eso vuelve **citable** el bruto con tarjeta de ese dia. Un dia sin
corte es un hueco. No es lo mismo.

## Como se lee

Desde el app:

- `GET /api/cash-cuts?cafeteria_id=&start_date=&end_date=` — los cortes, con el
  resumen **por marca** ya hecho (la pantalla no suma marcas por su cuenta: Casa
  Dorelia y Le Pain Dore tienen repartos distintos).
- `GET /api/cash-cuts/prefill?cafeteria_id=&business_date=` — que proponer antes
  de contar, si ya hay corte de ese dia, y el bruto con tarjeta del dia.

Sin levantar el app (solo lectura, no escribe en Mongo):

    python backend/cash_cut.py --db casa_dorelia
    python backend/cash_cut.py --db casa_dorelia --date 2026-10-04
    python backend/cash_cut.py --db casa_dorelia --from 2026-10-01 --to 2026-10-31

## La diferencia contra el sistema (y por que casi siempre sale vacia)

`diferencia` solo se calcula cuando el app **ya tiene** venta en efectivo
capturada de ese dia (punto de venta). Hoy la sucursal no lo usa, asi que sale
`None` con el motivo escrito. Restar contra cero reportaria un faltante del
tamaño de todo el efectivo del dia, y eso acusa a alguien de algo que no paso.

## Lo que todavia falta

- ~~**El tablero de ventas aun no publica este efectivo.**~~ Entro en BOS-149:
  `dashboard.py` recibe los cortes (`cash_cut.read_cuts`), publica el total del
  dia por marca (`tarjeta + efectivo`) y calcula el rotulo de piso **por dia y
  por marca** — un dia con corte deja de decirlo, uno sin corte lo sigue
  diciendo. `publish_dashboard.py` los lee de la misma base sin bandera. Lo que
  no cambia: la grafica se queda en tarjeta (una linea mitad tarjeta y mitad
  total daria un escalon el dia del primer corte que se leeria como un salto de
  venta), y el total del rango tampoco mezcla dias con y sin corte.
- ~~**El flujo end-to-end no esta probado con la app levantada.**~~ Se probo en
  BOS-150: los nueve pasos del plan contra `uvicorn server:app` con un mongod
  real y login real de cuatro roles. Quedo como probe re-corrible
  (`backend/tests/probe_cash_cut_api.py`, 29 comprobaciones) y saco dos
  defectos, los dos ya corregidos: el prefill no miraba el `turno` (una
  sucursal de dos turnos no podia capturar el segundo, con el dia rotulado como
  completo) y `GET /cash-cuts` no revalidaba el `cafeteria_id` del query (un
  cajero leia el efectivo de la otra marca).
- **La pantalla no se ha usado en un telefono de verdad.** Lo verificado es que
  compila, que los ocho campos de dinero declaran teclado numerico
  (`inputMode` decimal/numeric, confirmado en el bundle) y que el derivado sale
  en `text-4xl`. Falta la prueba en el mostrador, que es donde se usa.

### Como levantar esto para probarlo

Dos trampas del entorno, las dos documentadas porque cuestan una tarde:

1. `server.py` importa `emergentintegrations`, que es un paquete **privado** y
   no esta en PyPI: `pip install` no lo resuelve y el modulo no se puede ni
   importar. Para probar se levanta con un stub local fuera del arbol del repo.
   Quitarle esa dependencia es BOS-69.
2. `EmailStr` rechaza los dominios de uso especial (`.test`, `.example`), asi
   que un usuario de prueba con esos correos hace que el login conteste **422**
   y no 401. Los fixtures del probe usan un dominio normal a proposito.

El procedimiento completo esta en el docstring de
`backend/tests/probe_cash_cut_api.py`.

## Si Clip algun dia si entrega el efectivo

No hay que reescribir nada de esto: el veredicto `efectivo_en_la_api` del censo
se calcula, y el corte de caja seguiria sirviendo para cuadrar contra la caja
fisica, que es algo que ninguna API da.
