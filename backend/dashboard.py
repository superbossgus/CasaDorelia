"""Tablero de ventas: un archivo HTML que se abre sin levantar nada.

### El problema que resuelve

La venta ya esta en `casa_dorelia.sales` (la carga de BOS-119 la mete dos veces
al dia), pero para *verla* habia que levantar el backend y el frontend. En la
practica eso significa que nadie la ve: el numero vive en un `print` de JSON
dentro del comentario de una tarea.

Este modulo rinde el mismo dato a un **HTML autocontenido**: sin CDN, sin
servidor, sin `npm`. Se abre con doble clic, funciona sin red y se puede mandar
por WhatsApp. No reemplaza al tablero del app (`/dashboard/stats`); es el que se
puede leer hoy, y el que un cron puede regenerar despues de cada carga.

### Las cuatro cosas que este tablero se niega a hacer

Son las cuatro formas de mentir con este dato, y estan codificadas, no escritas
en un comentario:

1. **No publica un total consolidado.** `casa_dorelia` guarda dos marcas con dos
   repartos distintos (ver `brands.py`): Casa Dorelia (`c-sji`) y Le Pain Dore
   (`c-tecno`). Cada una tiene su renglon, su color y su tarjeta. La suma de
   dinero de las dos no existe **ni en el modelo**: un campo que vive en el JSON
   acaba dibujado por el siguiente que toque la plantilla. Lo unico que cruza
   marcas es el conteo de renglones cargados, que no son pesos.
2. **No llama "venta" al cobro con tarjeta.** La API de Clip no entrega
   efectivo, asi que todo monto de aqui es **piso**. El rotulo va en el
   encabezado y en cada tarjeta, no en una nota al pie.
3. **No dibuja utilidad cuando no la sabe.** Las ventas de Clip entran con
   `cost_known: false`, `cost_total: 0` y `profit: 0`. Graficar eso daria una
   utilidad de cero que se lee como "perdimos todo el margen". Si ninguna venta
   trae costo, el tablero dice *no disponible* y no dibuja la grafica.
4. **No confunde "cero" con "no hay dato".** Antes del primer dia de una marca
   la linea se corta (hueco); dentro de su ventana, un dia sin cobro es un cero
   explicito. Un cero de dinero tiene que poder distinguirse de un campo que
   falta: la misma regla que `brands.py` aplica con `sin-marca`.

### El dia en curso y el dia de ayer

El eje es el **dia de operacion** (`business_date`, UTC-6), nunca el dia UTC: ver
`business_day.py`. Encima de eso, el tablero marca el estado de cada dia:

- **en curso**: el dia de hoy. Su cifra siempre esta incompleta; a las 07:45 vale
  cero por diseño, porque las sucursales no han abierto.
- **cierre no confirmado**: la ultima venta capturada cayo pegada a la foto de
  las 19:45, asi que pudo haber cobro despues que esa corrida no vio. Solo se
  marca asi **el dia anterior y solo hasta que corre el catch-up de las 07:45**,
  que vuelve a pedir el dia completo y lo confirma. No se arrastra la duda un
  segundo dia.
- **cerrado**: su cifra es citable como bruto del dia (piso, siempre piso).

### El panel de apertura

Arriba de la venta puede ir un panel con lo que *falta* para abrir: los
bloqueantes abiertos y los renglones pendientes de la hoja de seguimiento. No
sale de `sales` porque no es venta: viaja en un JSON aparte (`--apertura`) y es
opcional. Esta ahi porque el tablero es la superficie que se abre a diario, y un
conteo que vive aqui deja de depender de que alguien abra una tarjeta.
`load_apertura` lo valida antes de dibujarlo (los conteos tienen que cuadrar con
el total de la hoja) y calcula la antiguedad del corte, para que el panel no
pueda decir "al dia" porque alguien escribio eso una vez.

### La hoja es evidencia; la autoridad es la confirmacion del consejo

Quien dice que un bloqueante esta abierto **no** es la columna *Estatus* de la
hoja: es el estado de confirmacion del consejo (`authority`, la tarjeta de
bloqueantes de BOS-5). Los dos se desvian en los dos sentidos, y el error no se
delata en el titular porque los conteos pueden coincidir estando mal renglon por
renglon (BOS-202: «4 cerrados, 6 abiertos» con 4 de 10 renglones equivocados):

- la hoja marco `Entregado` **#41** (campana) y **#1** (cables sueltos) el
  27/09, pero el responsable nunca lo confirmo, asi que el consejo los sigue
  contando abiertos. Armar la lista desde la hoja los borraba del tablero —y son
  justo los dos que se cierran con una frase y sin gastar un peso.
- la hoja sigue marcando `Pendiente` **#23** (pan) y **#25** (cafe), y en cambio
  el consejo los confirmo cerrados el 21/09. Dibujarlos como pendientes pide dos
  veces algo que ya esta hecho.

De ahi las dos validaciones que sostienen el arreglo: **todo renglon que la
tarjeta cuenta abierto tiene que estar dibujado** (eso es lo que hace imposible
que #41 y #1 vuelvan a desaparecer) y **nada que la tarjeta cuente cerrado se
dibuja como abierto**. El estatus de la hoja se sigue publicando, pero como
rotulo contrastado contra su espejo (`sheet_status`, ver
`_normalize_sheet_status`): un `Entregado` que el consejo no confirmo se dibuja
con el rotulo que lo dice, no se esconde ni se da por hecho.

Con `--apertura-optional` esa validacion deja de ser fatal: el panel se cae solo
y la tarjeta publica la razon. Es para el republicado automatico, donde la
alternativa a un panel desfasado no es "ningun tablero" sino el tablero de ayer
(ver `load_apertura_degrading`).

### El responsable, y por que nunca va a secas

Cada renglon abierto dibuja **un nombre** (BOS-165). No es decoracion: en el
corte del 04/10/2026 los 19 renglones de la hoja con responsable con nombre
estaban los 19 `Entregado`, y los 19 sin nombre seguian abiertos salvo uno. El
nombre es la variable que predice el cierre, asi que el tablero —la pantalla que
se abre a diario— tiene que traerlo.

Lo que el panel **no** puede hacer es convertir un supuesto en un hecho. El dueño
de estos renglones se derivo de la hoja, no de su palabra, asi que el renglon
dice el nombre *y* dice `sin confirmar` a la vista. Un nombre solo insinua dueño
aceptado, y quien lee el tablero es el dueño del negocio: ahi un nombre sin
rotulo es peor que no poner nombre. Eso esta en el validador, no en la buena
memoria de quien edite el JSON: nombrar un renglon obliga a declarar
`owner_confirmed`, y declararlo `true` obliga a citar donde consta
(`owner_confirmed_ref`). Ver `_normalize_owner`.

### Que esta pagina no puede hacer sola

Es un HTML generado: **no se actualiza solo**. Quien lo publica tiene que volver
a generarlo despues de cada carga (eso vive en `publish_dashboard.py`, BOS-144).
Lo que si hace la pagina es delatarse: calcula su propia edad al abrirla y, si
paso de `STALE_AFTER_HOURS`, pone arriba de todo que no es la venta de hoy. Esa
cuenta es la unica defensa que sigue en pie cuando lo que fallo es justamente la
republicacion.

### Correrlo

    python backend/dashboard.py --db casa_dorelia
    python backend/dashboard.py --db casa_dorelia --out C:/tmp/ventas.html
    python backend/dashboard.py --db casa_dorelia --apertura backend/apertura-sji.json

Solo lee: no escribe una sola linea en Mongo. Necesita `python` del sistema y
`pymongo`; el resto es biblioteca estandar.

### Reutilizable para otra empresa del grupo

Nada aqui conoce a Casa Dorelia. Las marcas salen del propio dato (decoradas con
el registro de `brands.py` cuando esta ahi, y con su slug cuando no), el titulo
es un parametro y los colores se asignan por slug ordenado, no por tamaño, asi
que filtrar una marca no repinta a la otra. Cualquier negocio del grupo cuyas
ventas caigan en esta forma de documento tiene tablero con un comando.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import brands as brands_mod
import business_day

DEFAULT_MONGO_URL = "mongodb://127.0.0.1:27017"

# Las dos horas del dia que deciden si una cifra esta cerrada. Son las mismas de
# la rutina de carga (BOS-119): la foto de la tarde y el catch-up de la mañana.
SNAPSHOT_LOCAL = "19:45"
MORNING_CATCHUP_LOCAL = "07:45"

# Que tan pegada a la foto de las 19:45 tiene que estar la ultima venta para
# dudar del cierre del dia. Medido: 51 min antes => cerrado; 4 min => dudoso.
SNAPSHOT_MARGIN_MINUTES = 30

# A partir de cuantas horas de generado el tablero se declara viejo **al
# abrirlo**. Sale de las dos republicaciones (07:45 y 19:45): el hueco mas largo
# entre una y otra es de 12 h, asi que una pagina de mas de 13 h es prueba de que
# una republicacion no corrio. No es un numero de gusto: es el hueco + margen.
STALE_AFTER_HOURS = 13

# Orden fijo de la paleta categorica (slots 1 y 2 del sistema de diseño), con su
# paso para fondo oscuro. Se asigna por slug ordenado alfabeticamente, no por
# cuanto vendio cada marca: filtrar una marca no debe repintar a la que queda.
SERIES_COLORS = [
    {"light": "#2a78d6", "dark": "#3987e5"},  # slot 1 azul
    {"light": "#eb6834", "dark": "#d95926"},  # slot 2 naranja
    {"light": "#1baf7a", "dark": "#199e70"},  # slot 3 aqua
]


class DashboardError(RuntimeError):
    """Algo impide armar el tablero. Siempre dice que falta."""


# --------------------------------------------------------------------------
# Capa de datos: funciones puras sobre documentos de `sales`
# --------------------------------------------------------------------------

def _local_datetime(value: Any) -> Optional[datetime]:
    """`created_at` en hora del negocio, o `None` si no se puede leer.

    Importa el huso de `business_day` en vez de volver a escribir el offset:
    ese modulo es el unico lugar donde se decide cual es la zona del negocio.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        moment = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            moment = datetime.fromisoformat(text)
        except ValueError:
            return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=business_day.BUSINESS_TZ)
    return moment.astimezone(business_day.BUSINESS_TZ)


def _minutes(hhmm: str) -> int:
    hour, minute = hhmm.split(":")
    return int(hour) * 60 + int(minute)


def _day_axis(first: str, last: str) -> List[str]:
    """Todos los dias entre dos extremos, sin huecos en el eje."""
    start = date.fromisoformat(first)
    end = date.fromisoformat(last)
    out: List[str] = []
    while start <= end:
        out.append(start.isoformat())
        start += timedelta(days=1)
    return out


def _round2(value: float) -> float:
    return round(value + 0.0, 2)


def day_states(*, axis: Sequence[str], last_capture: Mapping[str, int],
               today: str, now_minutes: int,
               has_sales: Mapping[str, bool]) -> Dict[str, str]:
    """Estado de cada dia del eje: `en_curso`, `no_confirmado`, `cerrado`, `sin_cobro`.

    `last_capture` trae los minutos locales de la ultima venta de cada dia.
    `now_minutes` son los minutos locales del momento en que se genera, y es lo
    que decide si el catch-up de las 07:45 ya confirmo el dia de ayer.

    La duda de cierre se limita a **un** dia a proposito. El catch-up de la
    mañana vuelve a pedir el dia anterior completo; si no trajo renglones
    nuevos, el dia quedo cerrado y arrastrar la duda seria sembrar desconfianza
    sobre una cifra ya verificada.
    """
    previous = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
    catchup_ran = now_minutes >= _minutes(MORNING_CATCHUP_LOCAL)
    threshold = _minutes(SNAPSHOT_LOCAL) - SNAPSHOT_MARGIN_MINUTES

    states: Dict[str, str] = {}
    for day in axis:
        if day >= today:
            states[day] = "en_curso"
            continue
        if not has_sales.get(day):
            states[day] = "sin_cobro"
            continue
        close = last_capture.get(day)
        hedge = day == previous and not catchup_ran
        if hedge and close is not None and close >= threshold:
            states[day] = "no_confirmado"
        else:
            states[day] = "cerrado"
    return states


# Los tres rotulos del responsable. Viven aqui, en Python, y no en la plantilla
# ni en el JSON: el renderizador solo imprime el texto que le llega, asi que el
# dia que alguno cambie no hay dos copias que puedan quedar en desacuerdo.
#
# `sin responsable` es **literal** y a proposito: no un guion ni un vacio. "No
# sabemos quien" es un dato —es justo el grupo que la medicion del 04/10 muestra
# que no se cierra—, y un guion se lee como que falto llenar la celda.
OWNER_NONE_LABEL = "sin responsable"
OWNER_UNCONFIRMED_LABEL = "sin confirmar"
OWNER_FIELDS = ("owner", "owner_confirmed", "owner_confirmed_ref", "owner_note")


def _normalize_owner(row: Dict[str, Any], where: str) -> None:
    """Resuelve el rotulo de responsable de un renglon, o truena.

    Deja tres campos listos para dibujar y uno para contar:

    - `owner_label`: el nombre, o `sin responsable` cuando no hay.
    - `owner_flag`: `sin confirmar` cuando el dueño es un supuesto; ausente
      cuando esta confirmado o cuando no hay nombre.
    - `owner_note`: lo que acompaña al nombre (quien autoriza el gasto, que hay
      que confirmar). Pasa tal cual.
    - `owner_named`: si el renglon tiene nombre. El panel cuenta sobre esto en
      vez de adivinarlo del texto del rotulo.

    Y aplica la regla que importa mas que el campo: **nombrar un renglon obliga
    a declarar si el dueño lo confirmo.** Sin `owner_confirmed` truena, porque el
    default silencioso tendria que ser alguno de los dos y los dos son caros:
    `false` por omision rotularia como supuesto un dueño que si confirmo, y
    `true` por omision publicaria un supuesto mio como hecho aceptado. Declararlo
    `true` exige ademas decir donde consta: una confirmacion sin cita no se puede
    auditar, y este rotulo solo se cae cuando el dueño habla.
    """
    owner = row.get("owner")
    if owner is None:
        row["owner_label"] = OWNER_NONE_LABEL
        row["owner_named"] = False
        return
    if not isinstance(owner, str) or not owner.strip():
        raise DashboardError(
            f"{where}: `owner` tiene que ser un nombre, no {owner!r}")
    confirmed = row.get("owner_confirmed")
    if not isinstance(confirmed, bool):
        raise DashboardError(
            f"{where}: trae el nombre «{owner}» pero no declara "
            "`owner_confirmed`. Un nombre a secas se lee como dueño aceptado; "
            "si el dueño salio de la hoja y no de su palabra, va "
            "`owner_confirmed: false`")
    if confirmed and not str(row.get("owner_confirmed_ref") or "").strip():
        raise DashboardError(
            f"{where}: declara confirmado a «{owner}» sin `owner_confirmed_ref`. "
            "Una confirmacion sin cita no se puede auditar: pon donde consta "
            "(tarea, comentario o quien lo dijo)")
    row["owner_label"] = owner.strip()
    row["owner_named"] = True
    if not confirmed:
        row["owner_flag"] = OWNER_UNCONFIRMED_LABEL


def _normalize_overdue(row: Dict[str, Any], where: str) -> None:
    """Rotula el vencimiento de un renglon a partir de su fecha, no de un texto.

    El rotulo se *calcula* de `overdue_since` por la misma razon que la
    antiguedad del corte: un «vencido desde el 25/09» escrito a mano sobrevive a
    que la fecha cambie, y entonces el tablero afirma un vencimiento que ya no
    es el que dice el dato.
    """
    since = row.get("overdue_since")
    if since is None:
        return
    cut = _local_datetime(since)
    if cut is None:
        raise DashboardError(
            f"{where}: `overdue_since` no es una fecha: {since!r}")
    row["overdue_label"] = "vencido desde el " + cut.strftime("%d/%m")


# El estatus de la hoja, y sus dos rotulos. Viven aqui por la misma razon que
# los del responsable: el renderizador solo imprime, asi que no puede haber una
# segunda copia del texto que pueda quedar en desacuerdo con esta.
#
# El rotulo de `Entregado` es el que importa: dice las dos cosas a la vez —lo
# que afirma la hoja y lo que falta para creerle—, porque esconder una de las dos
# es como un renglon abierto desaparece del tablero (BOS-202).
SHEET_PENDING = "Pendiente"
SHEET_DELIVERED = "Entregado"
SHEET_LABELS = {
    SHEET_PENDING: "la hoja dice «Pendiente»",
    SHEET_DELIVERED: "la hoja dice «Entregado» · falta confirmacion del responsable",
}


def _normalize_sheet_status(blocker: Dict[str, Any], pending_refs: set,
                            have_sheet: bool) -> None:
    """Rotula el estatus en la hoja de un bloqueante, contrastado contra la hoja.

    El estatus se dibuja, pero deja de ser la autoridad: aqui es un dato de la
    *evidencia*, y el rotulo lo calcula esta funcion para que no se pueda
    escribir a mano un «Pendiente en la hoja» que la hoja ya no dice.

    Un bloqueante que no esta entre los renglones pendientes de la hoja tiene que
    declarar por que: `sheet_status: "Entregado"` (la hoja lo dio por hecho y el
    responsable no lo confirmo) u `off_sheet: true` (no es renglon de la hoja,
    como los anexos del contrato). Antes esto tronaba sin tercera opcion, y esa
    era la trampa: la unica salida era borrar el renglon del panel.

    Lo declarado se verifica contra el espejo de la hoja en los dos sentidos, asi
    que ni un `Entregado` ni un `Pendiente` escritos de mas sobreviven a que la
    hoja se mueva.
    """
    ref = str(blocker.get("ref"))
    where = f"el bloqueante {ref}"
    declared = blocker.get("sheet_status")
    if blocker.get("off_sheet"):
        if declared is not None:
            raise DashboardError(
                f"{where}: se declara `off_sheet` y ademas `sheet_status`. Un "
                "renglon que no esta en la hoja no tiene estatus en la hoja")
        return
    in_sheet = ref in pending_refs
    if declared is None:
        if in_sheet:
            declared = SHEET_PENDING
        else:
            raise DashboardError(
                f"{where}: no esta entre los renglones «{SHEET_PENDING}» de la "
                f"hoja y no declara `sheet_status`. Si la hoja ya lo marco "
                f"«{SHEET_DELIVERED}» eso se dice —el consejo lo cuenta abierto "
                "y el renglon se dibuja con ese rotulo—; si no es renglon de la "
                "hoja, va `off_sheet: true`")
    if declared not in SHEET_LABELS:
        raise DashboardError(
            f"{where}: `sheet_status` tiene que ser «{SHEET_PENDING}» o "
            f"«{SHEET_DELIVERED}», no {declared!r}")
    if have_sheet:
        if declared == SHEET_PENDING and not in_sheet:
            raise DashboardError(
                f"{where}: se declara «{SHEET_PENDING}» pero no esta entre los "
                "renglones pendientes de la hoja")
        if declared == SHEET_DELIVERED and in_sheet:
            raise DashboardError(
                f"{where}: se declara «{SHEET_DELIVERED}» pero la hoja lo sigue "
                "trayendo entre sus pendientes")
    blocker["sheet_status"] = declared
    blocker["sheet_label"] = SHEET_LABELS[declared]
    blocker["sheet_conflict"] = declared == SHEET_DELIVERED


def _load_authority(data: Mapping[str, Any]) -> Dict[str, Any]:
    """El estado de confirmacion del consejo: quien decide que sigue abierto.

    Es la tarjeta de bloqueantes (`request_checkbox_confirmation` en BOS-5): lo
    que quedo marcado esta cerrado por confirmacion, y lo que quedo sin marcar
    se cuenta abierto. Viaja declarado en el JSON porque este modulo no habla
    con el tablero de tareas —solo lee venta—, y por eso trae el mismo tipo de
    control que los conteos de la hoja: `items` tiene que cuadrar con la suma de
    abiertos y cerrados, para que no se pueda recortar media tarjeta y dejar el
    resto en pie.
    """
    if "authority" not in data:
        raise DashboardError(
            "el archivo de apertura no trae `authority`: sin el estado de "
            "confirmacion del consejo la lista volveria a armarse desde la "
            "columna Estatus de la hoja, que es evidencia y no autoridad")
    auth = dict(data["authority"])
    for key in ("label", "ref", "resolved_at", "items", "open_refs", "closed_refs"):
        if key not in auth:
            raise DashboardError(f"el archivo de apertura no trae `authority.{key}`")

    open_refs = [str(ref) for ref in auth["open_refs"]]
    closed_refs = [str(ref) for ref in auth["closed_refs"]]
    for name, refs in (("open_refs", open_refs), ("closed_refs", closed_refs)):
        if len(set(refs)) != len(refs):
            raise DashboardError(f"`authority.{name}` trae un renglon repetido")
    both = sorted(set(open_refs) & set(closed_refs))
    if both:
        raise DashboardError(
            "la tarjeta no puede contar el mismo renglon abierto y cerrado: "
            + ", ".join(both))
    if len(open_refs) + len(closed_refs) != auth["items"]:
        raise DashboardError(
            f"la tarjeta dice {auth['items']} renglones pero se declaran "
            f"{len(open_refs)} abiertos + {len(closed_refs)} cerrados")

    cut = _local_datetime(auth["resolved_at"])
    if cut is None:
        raise DashboardError(
            f"`authority.resolved_at` no es una fecha: {auth['resolved_at']}")
    # Con hora, y en local como todo el resto de la pagina. La tarjeta se
    # resolvio a las 02:43Z, que es el **20/09 a las 20:43** en CDMX: una
    # etiqueta de solo fecha dice un dia distinto segun el huso con que se lea, y
    # este panel ya convive con un reporte que cita la fecha UTC.
    auth["resolved_label"] = cut.strftime("%d/%m/%Y %H:%M")
    auth["open_refs"] = open_refs
    auth["closed_refs"] = closed_refs
    return auth


def load_apertura(path: str, *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Panel de pendientes operativos, desde un JSON aparte y con controles.

    No sale de Mongo porque no es venta: sale de la hoja de seguimiento y del
    tablero de tareas. Viaja en su propio archivo para que el modulo siga sin
    conocer a ninguna empresa en particular, y para que el dia que la hoja se
    mueva se edite un JSON de 40 renglones, no la plantilla.

    Los controles, porque un panel escrito a mano es justo el que se desfasa:

    1. `entregados + pendientes == renglones`. Un conteo que no cuadra con el
       total de la hoja esta viejo, y un numero viejo arriba del tablero es peor
       que no tenerlo.
    2. Si viene la lista de pendientes, tiene que tener tantos renglones como
       dice el conteo. Asi no se puede recortar la lista y dejar el numero.
    3. **Todo lo que la tarjeta del consejo cuenta abierto tiene que estar
       dibujado como bloqueante, y nada que cuente cerrado puede estarlo.** Esta
       es la regla que reemplazo a "cada bloqueante tiene que estar Pendiente en
       la hoja", que era la que borraba del tablero un renglon abierto en cuanto
       la hoja lo marcaba `Entregado` (BOS-202).
    4. Un bloqueante que no esta entre los pendientes de la hoja declara por que
       —`sheet_status: "Entregado"` u `off_sheet: true`— y lo declarado se
       verifica contra la hoja en los dos sentidos (ver
       `_normalize_sheet_status`).
    5. Un renglon nombrado tiene que declarar si su dueño lo confirmo, y una
       confirmacion tiene que citar donde consta (ver `_normalize_owner`).

    La antiguedad del corte y el rotulo de vencido se *calculan* contra la fecha
    del dato: el panel no puede decir "al dia" ni "vencido desde el 25/09"
    porque alguien escribio eso una vez.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise DashboardError(f"no existe el archivo de apertura: {path}") from exc
    except ValueError as exc:
        raise DashboardError(f"el archivo de apertura no es JSON valido: {exc}") from exc

    for key in ("title", "source", "blockers"):
        if key not in data:
            raise DashboardError(f"el archivo de apertura no trae `{key}`")

    source = dict(data["source"])
    for key in ("label", "modified_at", "rows", "delivered", "pending"):
        if key not in source:
            raise DashboardError(f"el archivo de apertura no trae `source.{key}`")

    if source["delivered"] + source["pending"] != source["rows"]:
        raise DashboardError(
            f"el corte de la hoja no cuadra: {source['delivered']} entregados + "
            f"{source['pending']} pendientes != {source['rows']} renglones")

    pending_rows = [dict(row) for row in (data.get("pending_rows") or [])]
    if pending_rows and len(pending_rows) != source["pending"]:
        raise DashboardError(
            f"la lista de pendientes trae {len(pending_rows)} renglones pero el "
            f"corte dice {source['pending']}")

    blockers = [dict(b) for b in data["blockers"]]
    if not blockers:
        raise DashboardError("el archivo de apertura no trae un solo bloqueante")

    # La autoridad. Las dos comparaciones van en los dos sentidos a proposito:
    # la primera es la que impide que un renglon abierto desaparezca del panel
    # (el caso #41 / #1), y la segunda la que impide volver a pedir algo que el
    # consejo ya confirmo cerrado aunque la hoja siga diciendo «Pendiente» (el
    # caso #23 / #25). Un panel que solo valide una de las dos deja el error
    # vivo en el otro sentido, y el titular no lo delata.
    authority = _load_authority(data)
    drawn = [str(b.get("ref")) for b in blockers]
    if len(set(drawn)) != len(drawn):
        raise DashboardError("la lista de bloqueantes trae un `ref` repetido")
    missing = [ref for ref in authority["open_refs"] if ref not in drawn]
    if missing:
        raise DashboardError(
            "el consejo cuenta abiertos renglones que el panel no dibuja: "
            + ", ".join(missing) + ". Son los que se borran del tablero cuando "
            "la lista se arma desde la columna Estatus de la hoja")
    extra = [ref for ref in drawn if ref not in authority["open_refs"]]
    if extra:
        raise DashboardError(
            "el panel dibuja como bloqueante lo que la tarjeta del consejo no "
            "cuenta abierto: " + ", ".join(extra))

    pending_refs = {str(row.get("ref")) for row in pending_rows}
    for blocker in blockers:
        _normalize_sheet_status(blocker, pending_refs, bool(pending_rows))

    # Cerrado por confirmacion del consejo, aunque la hoja siga diciendo
    # «Pendiente». El renglon no se dibuja como pendiente —seria pedir dos veces
    # algo ya hecho— pero tampoco se borra en silencio: el panel publica cuantos
    # y cuales son, porque esa discrepancia es un dato de la hoja.
    closed_refs = set(authority["closed_refs"])
    for row in pending_rows:
        if str(row.get("ref")) in closed_refs:
            row["board_closed"] = True
            row["board_closed_label"] = (
                "cerrado por confirmacion del consejo el "
                + authority["resolved_label"])
    authority["closed_in_sheet"] = [str(row.get("ref")) for row in pending_rows
                                    if row.get("board_closed")]

    # El mismo `ref` es el mismo renglon de la hoja, asi que el responsable se
    # escribe **una vez** —en el bloqueante— y el pendiente homonimo lo hereda.
    # Hoy el panel no dibuja esos pendientes (el renderizador quita los que ya
    # salen como bloqueantes), pero duplicar el nombre a mano es como se llega a
    # que el mismo renglon aparezca con dos dueños distintos el dia que uno de
    # los dos se edite.
    by_ref = {str(b.get("ref")): b for b in blockers}
    for row in pending_rows:
        twin = by_ref.get(str(row.get("ref")))
        if twin is None or row.get("owner") is not None:
            continue
        for field in OWNER_FIELDS:
            if field in twin:
                row[field] = twin[field]

    for blocker in blockers:
        _normalize_owner(blocker, f"el bloqueante {blocker.get('ref')}")
        _normalize_overdue(blocker, f"el bloqueante {blocker.get('ref')}")
    for row in pending_rows:
        _normalize_owner(row, f"el pendiente {row.get('ref')}")
        _normalize_overdue(row, f"el pendiente {row.get('ref')}")

    now = now or datetime.now(timezone.utc)
    cut = _local_datetime(source["modified_at"])
    if cut is None:
        raise DashboardError(f"`source.modified_at` no es una fecha: {source['modified_at']}")
    source["modified_label"] = cut.strftime("%d/%m/%Y")
    source["stale_days"] = (now.astimezone(business_day.BUSINESS_TZ).date() - cut.date()).days

    return {
        "title": data["title"],
        "hint": data.get("hint"),
        "source": source,
        "authority": authority,
        "blockers": blockers,
        "pending_rows": pending_rows,
        "pending_title": data.get("pending_title"),
        "pending_hint": data.get("pending_hint"),
    }


def load_apertura_degrading(path: Optional[str]) -> tuple:
    """`load_apertura` que devuelve su falla en vez de levantarla.

    Devuelve `(apertura, error)`: a lo mas uno de los dos es distinto de `None`.
    Sin `path` son los dos nulos — nadie pidio panel.

    Esta es la forma que usa el republicado automatico (BOS-144), y la razon es
    una sola: ahi la alternativa a un panel desfasado no es "ningun tablero", es
    **el tablero de ayer**, que es el que ya esta publicado. Dejar congelado el
    enlace para proteger un conteo de pendientes seria cambiar un dato viejo
    rotulado por un dato viejo sin rotular. A mano sigue tronando (ver `main`):
    quien corre el comando a proposito quiere enterarse de que el JSON se
    desfaso, no publicar sin panel.
    """
    if not path:
        return None, None
    try:
        return load_apertura(path), None
    except DashboardError as exc:
        return None, str(exc)


def build_model(sales: Iterable[Mapping[str, Any]], *, title: str,
                today: Optional[str] = None, now: Optional[datetime] = None,
                db_name: Optional[str] = None,
                apertura: Optional[Mapping[str, Any]] = None,
                apertura_error: Optional[str] = None) -> Dict[str, Any]:
    """Arma el modelo completo del tablero. Pura: recibe documentos, no una conexion.

    Devuelve ya listo lo que la pagina dibuja, incluida la lista de limites del
    dato. Que los limites se *calculen* (y no se escriban a mano en el HTML) es
    lo que impide que el tablero siga diciendo "sin utilidad" el dia que si haya
    costos, o que se calle el efectivo el dia que entre venta de caja.

    `apertura` es el panel de pendientes operativos (ver `load_apertura`). No
    sale de `sales` porque no es venta: viaja en su propio archivo y es opcional.

    `apertura_error` es el caso de en medio, y existe por el republicado
    automatico (BOS-144). `load_apertura` truena a proposito cuando los conteos
    del JSON ya no cuadran con la hoja, y eso es correcto a mano. Pero en la
    republicacion que corre despues de cada carga de Clip, tumbar el tablero
    entero por un panel desfasado dejaria publicada **la venta de ayer**: el
    enlace no se rompe, se congela, que es exactamente la averia que BOS-144
    viene a cerrar. Asi que ahi el panel se cae solo y su razon viaja en el
    modelo, para que la tarjeta diga por que falta en lugar de desaparecer sin
    ruido. Un panel ausente y callado se lee como "ya no falta nada".
    """
    rows = list(sales)
    now = now or datetime.now(timezone.utc)
    now_local = now.astimezone(business_day.BUSINESS_TZ)
    today = today or business_day.business_date(now)

    # Acumuladores por (marca, dia) y por (marca, hora local).
    per_day: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(lambda: defaultdict(
        lambda: {"gross": 0.0, "tickets": 0}))
    per_hour: Dict[str, Dict[int, Dict[str, float]]] = defaultdict(lambda: defaultdict(
        lambda: {"gross": 0.0, "tickets": 0}))
    last_capture: Dict[str, int] = {}
    last_capture_text: Dict[str, str] = {}
    has_sales: Dict[str, bool] = {}

    # Controles de calidad. Se cuentan en la misma pasada: son parte del dato,
    # no un reporte aparte que alguien tiene que acordarse de correr.
    unlabeled = 0
    missing_branch = 0
    clip_fee_set = 0
    clip_cost_set = 0
    cost_known = 0
    itemized = 0
    payment_methods: Dict[str, int] = defaultdict(int)
    # Pesos por metodo, **dentro de cada marca**: un vale de $230 y una tarjeta
    # de $75 pesan igual en el conteo y no en el dinero, y lo que se lee es el
    # dinero. Por marca y no global porque un monto global cruzaria las dos
    # marcas, que es justo lo que este tablero no publica (lo cuida una prueba).
    per_method: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(lambda: defaultdict(
        lambda: {"gross": 0.0, "tickets": 0}))
    sources: Dict[str, int] = defaultdict(int)
    undated = 0

    for sale in rows:
        day = business_day.sale_business_date(sale)
        if day is None:
            undated += 1
            continue

        slug = sale.get("brand") or brands_mod.UNKNOWN_BRAND
        if not sale.get("brand"):
            unlabeled += 1
        if not sale.get("cafeteria_id"):
            missing_branch += 1

        source = sale.get("source") or "sin-origen"
        sources[source] += 1
        method = sale.get("payment_method") or "sin-metodo"
        payment_methods[method] += 1

        # Estos dos controles solo tienen sentido sobre renglones de Clip: una
        # venta del punto de venta si puede traer costo y comision de verdad.
        if source == "clip_api":
            if sale.get("clip_fee") is not None:
                clip_fee_set += 1
            if float(sale.get("cost_total") or 0.0) > 0:
                clip_cost_set += 1

        if sale.get("cost_known"):
            cost_known += 1
        if any(item.get("product_id") for item in (sale.get("items") or [])):
            itemized += 1

        total = float(sale.get("total") or 0.0)
        method_bucket = per_method[slug][method]
        method_bucket["gross"] += total
        method_bucket["tickets"] += 1
        bucket = per_day[slug][day]
        bucket["gross"] += total
        bucket["tickets"] += 1
        has_sales[day] = True

        moment = _local_datetime(sale.get("created_at"))
        if moment is not None:
            hour_bucket = per_hour[slug][moment.hour]
            hour_bucket["gross"] += total
            hour_bucket["tickets"] += 1
            minutes = moment.hour * 60 + moment.minute
            if minutes > last_capture.get(day, -1):
                last_capture[day] = minutes
                last_capture_text[day] = moment.strftime("%H:%M")

    if not rows or not has_sales:
        raise DashboardError(
            "no hay ventas con `business_date` legible en esa base: "
            "revisa que sea la base correcta y que la carga haya corrido")

    days_with_data = sorted(has_sales)
    axis = _day_axis(days_with_data[0], max(days_with_data[-1], today))
    states = day_states(axis=axis, last_capture=last_capture, today=today,
                        now_minutes=now_local.hour * 60 + now_local.minute,
                        has_sales=has_sales)

    brand_slugs = sorted(per_day)
    brand_models: List[Dict[str, Any]] = []
    for index, slug in enumerate(brand_slugs):
        day_rows = per_day[slug]
        active = sorted(day_rows)
        first_day, last_day = active[0], active[-1]

        series: List[Dict[str, Any]] = []
        for day in axis:
            if day < first_day:
                # Antes del primer dia de la marca no hay dato: hueco, no cero.
                series.append({"date": day, "gross": None, "tickets": None,
                               "avg_ticket": None})
                continue
            bucket = day_rows.get(day)
            if bucket is None:
                # El dia en curso sin cobro todavia **no es un cero medido**: es
                # un dia que no ha pasado. Graficarlo en cero desploma la linea
                # y se lee como un derrumbe de la venta, cuando a las 07:45 lo
                # correcto es que no haya nada. Va como hueco; la tabla lo dice
                # con todas sus letras ("en curso"), asi que no se esconde.
                zero = None if day >= today else 0.0
                series.append({"date": day, "gross": zero,
                               "tickets": None if zero is None else 0,
                               "avg_ticket": None})
                continue
            tickets = int(bucket["tickets"])
            gross = _round2(bucket["gross"])
            series.append({
                "date": day,
                "gross": gross,
                "tickets": tickets,
                "avg_ticket": _round2(gross / tickets) if tickets else None,
            })

        total_gross = _round2(sum(float(b["gross"]) for b in day_rows.values()))
        total_tickets = int(sum(int(b["tickets"]) for b in day_rows.values()))
        hours = [
            {"hour": hour,
             "tickets": int(per_hour[slug][hour]["tickets"]),
             "gross": _round2(per_hour[slug][hour]["gross"])}
            for hour in range(24)
        ]
        color = SERIES_COLORS[index % len(SERIES_COLORS)]
        brand_models.append({
            "brand": slug,
            "name": brands_mod.brand_name(slug),
            "vehicle": brands_mod.brand_vehicle(slug),
            "color": color["light"],
            "color_dark": color["dark"],
            "first_day": first_day,
            "last_day": last_day,
            "series": series,
            "hours": hours,
            "totals": {
                "gross": total_gross,
                "tickets": total_tickets,
                "avg_ticket": _round2(total_gross / total_tickets) if total_tickets else None,
            },
            # Con que se cobro, en pesos de ESTA marca. Es lo que separa un vale
            # de una tarjeta y lo que deja ver, el dia que entre, el efectivo.
            "by_method": {
                method: {"gross": _round2(per_method[slug][method]["gross"]),
                         "tickets": int(per_method[slug][method]["tickets"])}
                for method in sorted(per_method[slug])
            },
        })

    checks = [
        {"id": "brand", "label": "Ventas sin marca", "count": unlabeled,
         "fix": "python backend/backfill_brand.py"},
        {"id": "branch", "label": "Ventas sin sucursal", "count": missing_branch,
         "fix": "revisar `branches_init.CASA_DORELIA_BRANCHES`"},
        {"id": "clip_fee", "label": "Comision de Clip inventada", "count": clip_fee_set,
         "fix": "la API de Clip no entrega comision: debe quedar nula"},
        {"id": "clip_cost", "label": "Costo inventado en venta de Clip", "count": clip_cost_set,
         "fix": "la API de Clip no entrega costo: debe quedar en cero"},
        {"id": "undated", "label": "Ventas sin dia de operacion", "count": undated,
         "fix": "python backend/backfill_business_date.py"},
    ]
    for check in checks:
        check["status"] = "good" if check["count"] == 0 else "critical"

    counted = len(rows) - undated
    return {
        "title": title,
        "db_name": db_name,
        "generated_at": now_local.isoformat(timespec="seconds"),
        "generated_at_label": now_local.strftime("%d/%m/%Y %H:%M") + " CDMX",
        "today": today,
        "days": axis,
        "day_states": states,
        "last_capture": last_capture_text,
        "brands": brand_models,
        "rows": len(rows),
        "rows_counted": counted,
        # No hay `control_sum`: ni en el modelo. Una suma de dinero entre marcas
        # no se puede publicar, y un campo que existe en el JSON acaba dibujado
        # por el siguiente que toque la plantilla. Lo unico que cruza marcas es
        # `rows_counted`, que es un conteo de renglones, no pesos.
        "apertura": dict(apertura) if apertura else None,
        # Por que falta el panel, cuando falta por una falla y no porque no se
        # pidio. `None` en los dos campos = nadie pidio panel; `apertura_error`
        # con `apertura` nulo = se pidio y se cayo, y la tarjeta lo dice.
        "apertura_error": apertura_error if apertura is None else None,
        "quality": {"checks": checks},
        "limits": {
            # Calculados, no escritos a mano: el dia que el dato cambie, el
            # rotulo cambia con el.
            # Falta el efectivo mientras no haya **un solo** renglon de
            # efectivo. Antes esto se preguntaba al reves ("el unico metodo es
            # tarjeta"), y eso convertia cualquier metodo nuevo — vales, por
            # ejemplo — en un "ya entra el efectivo" que nadie escribio.
            "cash_excluded": "efectivo" not in payment_methods,
            # Conteo de renglones, no pesos: un total en dinero aqui cruzaria
            # las dos marcas. Los pesos por metodo viven en cada marca
            # (`brands[].by_method`).
            "payment_methods": dict(sorted(payment_methods.items())),
            "sources": dict(sorted(sources.items())),
            "margin_unknown": cost_known == 0,
            "cost_known_rows": cost_known,
            "itemized_rows": itemized,
        },
        "config": {
            "snapshot_local": SNAPSHOT_LOCAL,
            "morning_catchup_local": MORNING_CATCHUP_LOCAL,
            "snapshot_margin_minutes": SNAPSHOT_MARGIN_MINUTES,
            "stale_after_hours": STALE_AFTER_HOURS,
        },
    }


# --------------------------------------------------------------------------
# Capa de presentacion
# --------------------------------------------------------------------------

def render_html(model: Mapping[str, Any]) -> str:
    """Pagina autocontenida. Sin CDN, sin fuentes remotas, sin peticiones."""
    payload = json.dumps(model, ensure_ascii=False, allow_nan=False)
    # `</script>` dentro del JSON cerraria la etiqueta antes de tiempo. Nada en
    # este dato deberia traerlo, pero un nombre de producto capturado a mano si
    # podria: se escapa siempre, no cuando se sospeche.
    payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace(
        "\u2029", "\\u2029")
    return _TEMPLATE.replace("__TITLE__", _escape(str(model["title"]))).replace(
        "__DATA__", payload)


def _escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def open_sales_collection(mongo_url: Optional[str] = None,
                          db_name: Optional[str] = None):
    """Coleccion `sales`, con un mensaje util cuando falta configuracion."""
    try:
        from pymongo import MongoClient
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise DashboardError("falta el driver de Mongo: pip install pymongo") from exc

    url = mongo_url or os.environ.get("MONGO_URL") or DEFAULT_MONGO_URL
    name = db_name or os.environ.get("DB_NAME")
    if not name:
        raise DashboardError("falta `DB_NAME` (o --db): no se adivina que base se lee")
    try:
        client = MongoClient(url, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")  # falla aqui, no a media consulta
    except Exception as exc:  # pragma: no cover - depende del entorno
        raise DashboardError(
            f"el mongod de {url} no responde ({type(exc).__name__}). "
            "Si es el local de Windows: Start-Service MongoDB") from exc
    return client[name].sales


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dashboard",
        description="Tablero de ventas en un HTML autocontenido. Solo lee, nunca escribe.",
    )
    parser.add_argument("--db", default=None, help="base a leer (default: $DB_NAME)")
    parser.add_argument("--mongo-url", default=None, help="default: $MONGO_URL o localhost")
    parser.add_argument("--out", default="dashboard-ventas.html",
                        help="archivo HTML a escribir (default: ./dashboard-ventas.html)")
    parser.add_argument("--title", default="Cobro en terminal Clip",
                        help="titulo del tablero")
    parser.add_argument("--apertura", default=None, metavar="ARCHIVO.json",
                        help="panel de pendientes de apertura (ver load_apertura); "
                             "si se omite, el tablero sale solo con la venta")
    parser.add_argument("--apertura-optional", action="store_true",
                        help="si el panel de apertura no cuadra, publicar el tablero "
                             "sin panel (y con la razon a la vista) en vez de fallar; "
                             "es lo que usa el republicado automatico")
    parser.add_argument("--json", action="store_true",
                        help="imprime el modelo en JSON en vez de escribir el HTML")

    args = parser.parse_args(argv)

    try:
        if args.apertura_optional:
            apertura, apertura_error = load_apertura_degrading(args.apertura)
        else:
            apertura = load_apertura(args.apertura) if args.apertura else None
            apertura_error = None
        sales = open_sales_collection(args.mongo_url, args.db)
        db_name = args.db or os.environ.get("DB_NAME")
        model = build_model(sales.find({}, {"_id": 0}), title=args.title,
                            db_name=db_name, apertura=apertura,
                            apertura_error=apertura_error)
    except DashboardError as exc:
        print(f"ERROR: {exc}")
        return 1
    if apertura_error:
        print(f"AVISO panel de apertura omitido: {apertura_error}")

    if args.json:
        print(json.dumps(model, indent=2, ensure_ascii=False))
        return 0

    out = os.path.abspath(args.out)
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(render_html(model))

    print(f"Tablero escrito: {out}")
    print(f"  dias: {model['days'][0]} -> {model['days'][-1]}"
          f"  ({model['rows_counted']} cobros)")
    for brand in model["brands"]:
        print(f"  {brand['name']}: ${brand['totals']['gross']:,.2f}"
              f" en {brand['totals']['tickets']} cobros")
        for method, mix in brand["by_method"].items():
            print(f"    {method}: ${mix['gross']:,.2f} en {mix['tickets']} cobros")
    if model["limits"]["cash_excluded"]:
        print("  Piso, no venta del dia: el efectivo de la app de Clip no viaja "
              "por esta API.")

    failed = [c for c in model["quality"]["checks"] if c["count"]]
    for check in failed:
        print(f"  AVISO {check['label']}: {check['count']} -> {check['fix']}")
    return 1 if failed else 0


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es-MX">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  .viz-root {
    color-scheme: light;
    --surface-1: #fcfcfb;
    --plane: #f9f9f7;
    --text-primary: #0b0b0b;
    --text-secondary: #52514e;
    --text-muted: #898781;
    --grid: #e1e0d9;
    --axis: #c3c2b7;
    --border: rgba(11,11,11,0.10);
    --good: #0ca30c;
    --warning: #fab219;
    --critical: #d03b3b;
    --mode: "light";
  }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) .viz-root {
      color-scheme: dark;
      --surface-1: #1a1a19;
      --plane: #0d0d0d;
      --text-primary: #ffffff;
      --text-secondary: #c3c2b7;
      --text-muted: #898781;
      --grid: #2c2c2a;
      --axis: #383835;
      --border: rgba(255,255,255,0.10);
      --mode: "dark";
    }
  }
  :root[data-theme="dark"] .viz-root {
    color-scheme: dark;
    --surface-1: #1a1a19;
    --plane: #0d0d0d;
    --text-primary: #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted: #898781;
    --grid: #2c2c2a;
    --axis: #383835;
    --border: rgba(255,255,255,0.10);
    --mode: "dark";
  }

  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    background: var(--plane);
    color: var(--text-primary);
    -webkit-font-smoothing: antialiased;
  }
  .viz-root { background: var(--plane); color: var(--text-primary); min-height: 100vh; }
  .wrap { max-width: 1120px; margin: 0 auto; padding: 32px 20px 64px; }

  header.page { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start;
    justify-content: space-between; margin-bottom: 8px; }
  h1 { font-size: 22px; font-weight: 650; margin: 0 0 4px; letter-spacing: -0.01em; }
  .sub { color: var(--text-secondary); font-size: 13px; margin: 0; }
  .floor-note { margin: 16px 0 24px; padding: 12px 14px; border-radius: 10px;
    border: 1px solid var(--border); background: var(--surface-1);
    color: var(--text-secondary); font-size: 13px; line-height: 1.5; }
  .floor-note strong { color: var(--text-primary); }
  /* La edad del tablero, medida al abrirlo. Un HTML generado no se actualiza
     solo: si la republicacion se cayo, este renglon es lo unico que distingue
     "la venta de hoy" de una foto de anteayer. Va arriba de todo, en color de
     alerta, porque leer una cifra vieja como si fuera de hoy es el error caro. */
  .stale-note { margin: 16px 0 0; padding: 12px 14px; border-radius: 10px;
    border: 1px solid var(--critical); background: var(--surface-1);
    color: var(--text-primary); font-size: 13px; line-height: 1.5; }
  .stale-note strong { color: var(--critical); }
  .apertura-error { color: var(--text-secondary); font-size: 13px; line-height: 1.5;
    margin: 0; }
  .apertura-error strong { color: var(--critical); }
  .apertura-error code { color: var(--text-primary); }

  button {
    font: inherit; font-size: 13px; color: var(--text-secondary);
    background: var(--surface-1); border: 1px solid var(--border);
    border-radius: 8px; padding: 7px 12px; cursor: pointer;
  }
  button:hover { color: var(--text-primary); }
  button[aria-pressed="true"] { color: var(--text-primary); font-weight: 600;
    border-color: var(--axis); }
  button:focus-visible { outline: 2px solid var(--text-primary); outline-offset: 2px; }

  .filters { display: flex; flex-wrap: wrap; gap: 20px; align-items: center;
    padding: 12px 0 20px; }
  .filters .group { display: flex; gap: 8px; align-items: center; }
  .filters .glabel { font-size: 12px; color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.04em; }
  .brand-toggle { display: inline-flex; align-items: center; gap: 7px; }
  .brand-toggle .key { width: 11px; height: 11px; border-radius: 3px; flex: none; }
  .brand-toggle[aria-pressed="false"] .key { opacity: 0.3; }

  .tiles { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    margin-bottom: 28px; }
  .tile { background: var(--surface-1); border: 1px solid var(--border);
    border-radius: 12px; padding: 18px 18px 14px; }
  .tile .head { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
  .tile .key { width: 11px; height: 11px; border-radius: 3px; flex: none; }
  .tile .name { font-size: 14px; font-weight: 600; }
  .tile .vehicle { font-size: 12px; color: var(--text-muted); margin-left: auto; }
  .tile .label { font-size: 12px; color: var(--text-secondary); margin-bottom: 2px; }
  .tile .value { font-size: 34px; font-weight: 650; letter-spacing: -0.02em;
    line-height: 1.1; }
  .tile .meta { font-size: 12px; color: var(--text-secondary); margin-top: 6px; }
  .tile .delta { font-size: 12px; margin-top: 4px; color: var(--text-secondary); }
  .tile .spark { margin-top: 12px; }

  .card { background: var(--surface-1); border: 1px solid var(--border);
    border-radius: 12px; padding: 18px; margin-bottom: 20px; }
  .card h2 { font-size: 15px; font-weight: 600; margin: 0 0 3px; }
  .card .hint { font-size: 12px; color: var(--text-muted); margin: 0 0 14px; }
  .chart { position: relative; }
  .chart svg { display: block; width: 100%; height: auto; overflow: visible; }

  .legend { display: flex; flex-wrap: wrap; gap: 16px; margin: 0 0 12px;
    font-size: 12px; color: var(--text-secondary); }
  .legend .item { display: inline-flex; align-items: center; gap: 7px; }
  .legend .swatch-line { width: 16px; height: 2px; border-radius: 1px; }
  .legend .swatch-rect { width: 11px; height: 11px; border-radius: 3px; }

  .tip { position: absolute; pointer-events: none; z-index: 5; opacity: 0;
    transition: opacity 90ms linear; background: var(--surface-1);
    border: 1px solid var(--border); border-radius: 9px; padding: 8px 10px;
    box-shadow: 0 6px 20px rgba(0,0,0,0.13); min-width: 132px; }
  .tip .when { font-size: 11px; color: var(--text-muted); margin-bottom: 5px; }
  .tip .row { display: flex; align-items: baseline; gap: 7px; font-size: 12px;
    color: var(--text-secondary); margin-top: 3px; }
  .tip .row .stroke { width: 12px; height: 2px; border-radius: 1px; flex: none; }
  .tip .row .num { font-size: 13px; font-weight: 650; color: var(--text-primary);
    font-variant-numeric: tabular-nums; margin-left: auto; }

  table { border-collapse: collapse; width: 100%; font-size: 13px; }
  caption { text-align: left; font-size: 12px; color: var(--text-muted);
    padding-bottom: 8px; }
  th, td { text-align: right; padding: 7px 10px; border-bottom: 1px solid var(--grid);
    font-variant-numeric: tabular-nums; white-space: nowrap; }
  th:first-child, td:first-child { text-align: left; font-variant-numeric: normal; }
  thead th { color: var(--text-secondary); font-weight: 600; font-size: 12px;
    border-bottom: 1px solid var(--axis); }
  tbody tr:last-child td { border-bottom: none; }
  tfoot td { font-weight: 650; border-top: 1px solid var(--axis); border-bottom: none; }
  .tbl-wrap { overflow-x: auto; }

  .state { display: inline-flex; align-items: center; gap: 5px; font-size: 12px;
    color: var(--text-secondary); }
  .state .ico { font-size: 11px; line-height: 1; }
  .nodata { color: var(--text-muted); }

  .checks { display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
  .check { display: flex; gap: 9px; align-items: flex-start; font-size: 13px; }
  .check .ico { flex: none; font-size: 13px; line-height: 1.35; }
  .check .ok { color: var(--good); }
  .check .bad { color: var(--critical); }
  .check .txt { color: var(--text-secondary); }
  .check .txt b { color: var(--text-primary); font-weight: 600; }
  .check .fix { display: block; color: var(--text-muted); font-size: 12px; margin-top: 2px; }

  /* Panel de apertura: no es venta, es la lista de lo que falta. Va arriba
     porque es lo que deja de depender de que alguien abra una tarjeta. */
  .open-head { display: flex; flex-wrap: wrap; gap: 18px 28px; align-items: baseline;
    margin-bottom: 14px; }
  .open-num { font-size: 26px; font-weight: 650; color: var(--text-primary);
    font-variant-numeric: tabular-nums; line-height: 1.1; }
  .open-num.warn { color: var(--warning); }
  .open-lab { font-size: 12px; color: var(--text-muted); margin-top: 3px; }
  .open-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
  .open-list li { display: flex; gap: 9px; align-items: flex-start; font-size: 13px;
    color: var(--text-secondary); }
  .open-list .ref { flex: none; font-variant-numeric: tabular-nums; font-weight: 650;
    color: var(--text-primary); min-width: 54px; }
  .open-list .blk .ref { color: var(--critical); }
  .open-list .what b { color: var(--text-primary); font-weight: 600; }
  .open-list .meta { display: block; color: var(--text-muted); font-size: 12px;
    margin-top: 1px; }
  /* El responsable: renglon propio, debajo de la meta. El nombre no puede
     quedar del color del texto secundario porque es lo que se busca al leer la
     lista, y `sin confirmar` no puede quedar del color del nombre porque
     entonces se leeria como parte de el. */
  .open-list .who { display: block; font-size: 12px; margin-top: 3px;
    color: var(--text-muted); }
  .open-list .who-lab { text-transform: uppercase; letter-spacing: .04em;
    font-size: 10px; margin-right: 6px; }
  .open-list .who b { color: var(--text-primary); font-weight: 600; }
  .open-list .who.nobody b { color: var(--text-muted); font-weight: 500;
    font-style: italic; }
  /* Chip, no tooltip: el rotulo tiene que estar a la vista en el renglon. Trae
     borde ademas de color para que no dependa de distinguir tonos. */
  .open-list .unconf, .open-list .late { display: inline-block; margin-left: 7px;
    padding: 0 6px; border-radius: 9px; font-size: 11px; line-height: 17px;
    border: 1px solid currentColor; }
  .open-list .unconf { color: var(--warning); }
  .open-list .late { color: var(--critical); }
  .open-list .who-note { display: block; margin-top: 1px; }
  /* Lo que dice la hoja. Renglon propio y no chip en linea, porque es una frase
     y porque el caso que importa —la hoja dice `Entregado` y el consejo lo
     cuenta abierto— tiene que leerse completo, no recortado. */
  .open-list .sheet { display: block; font-size: 12px; margin-top: 2px;
    color: var(--text-muted); }
  .open-list .sheet.conflict { color: var(--warning); }
  .open-list .sheet.done { color: var(--good); }
  .open-rest { margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--grid); }
  .open-rest h3 { font-size: 13px; font-weight: 600; margin: 0 0 3px;
    color: var(--text-primary); }
  .open-rest .hint { margin-bottom: 10px; }
  .open-head a { font-size: 13px; color: var(--text-primary); }

  ul.limits { margin: 0; padding-left: 18px; font-size: 13px; color: var(--text-secondary);
    line-height: 1.65; }
  ul.limits b { color: var(--text-primary); font-weight: 600; }
  footer.page { margin-top: 28px; font-size: 12px; color: var(--text-muted);
    line-height: 1.6; }
  code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.93em; }

  @media print { .filters, .theme { display: none; } .card { break-inside: avoid; } }
</style>
</head>
<body>
<div class="viz-root">
<div class="wrap">
  <header class="page">
    <div>
      <h1 id="title"></h1>
      <p class="sub" id="subtitle"></p>
    </div>
    <button class="theme" id="theme" type="button">Modo oscuro</button>
  </header>

  <p class="stale-note" id="stale-note" hidden></p>

  <p class="floor-note" id="floor-note"></p>

  <div class="filters" id="filters" role="group" aria-label="Filtros del tablero">
    <div class="group">
      <span class="glabel">Rango</span>
      <span id="ranges"></span>
    </div>
    <div class="group">
      <span class="glabel">Marca</span>
      <span id="brand-filters"></span>
    </div>
  </div>

  <section class="tiles" id="tiles" aria-label="Resumen por marca"></section>

  <section class="card" id="apertura-card" hidden>
    <h2 id="apertura-title"></h2>
    <p class="hint" id="apertura-hint"></p>
    <p class="apertura-error" id="apertura-error" hidden></p>
    <div class="open-head" id="apertura-head"></div>
    <ul class="open-list" id="apertura-blockers"></ul>
    <div class="open-rest" id="apertura-rest" hidden>
      <h3 id="apertura-rest-title"></h3>
      <p class="hint" id="apertura-rest-hint"></p>
      <ul class="open-list" id="apertura-pending"></ul>
    </div>
  </section>

  <section class="card">
    <h2>Cobro con tarjeta por dia</h2>
    <p class="hint" id="gross-hint"></p>
    <div class="legend" id="gross-legend"></div>
    <div class="chart" id="gross-chart"></div>
  </section>

  <section class="card">
    <h2>Ticket promedio por dia</h2>
    <p class="hint">Bruto entre numero de cobros. Es la comparacion que si aguanta
      un dia incompleto: un dia con menos horas tiene menos cobros, pero no un
      ticket mas chico.</p>
    <div class="legend" id="avg-legend"></div>
    <div class="chart" id="avg-chart"></div>
  </section>

  <section class="card">
    <h2>A que hora cobran con tarjeta</h2>
    <p class="hint">Cobros por hora local (UTC-6), acumulados en todo el rango
      seleccionado. Sirve para decidir turnos; no es venta por hora del dia de hoy.</p>
    <div class="legend" id="hour-legend"></div>
    <div class="chart" id="hour-chart"></div>
  </section>

  <section class="card">
    <h2>Tabla de datos</h2>
    <p class="hint">El tablero completo en numeros: nada de lo que dibujan las
      graficas vive solo en un tooltip.</p>
    <div class="tbl-wrap" id="day-table"></div>
  </section>

  <section class="card">
    <h2>Controles del dato</h2>
    <p class="hint">Se cuentan sobre toda la base en cada generacion, no sobre el
      rango filtrado. Los cinco deben estar en cero.</p>
    <div class="checks" id="checks"></div>
  </section>

  <section class="card">
    <h2>Que NO dice este tablero</h2>
    <ul class="limits" id="limits"></ul>
  </section>

  <footer class="page" id="footer"></footer>
</div>
</div>

<script type="application/json" id="model">__DATA__</script>
<script>
(function () {
  "use strict";

  var M = JSON.parse(document.getElementById("model").textContent);
  var root = document.documentElement;

  // ---------------------------------------------------------------- formato
  var MXN = new Intl.NumberFormat("es-MX", {
    style: "currency", currency: "MXN", minimumFractionDigits: 2
  });
  var MXN0 = new Intl.NumberFormat("es-MX", {
    style: "currency", currency: "MXN", maximumFractionDigits: 0
  });
  var NUM = new Intl.NumberFormat("es-MX");
  var MONTHS = ["ene", "feb", "mar", "abr", "may", "jun",
                "jul", "ago", "sep", "oct", "nov", "dic"];
  var WEEKDAYS = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"];

  function parseDay(iso) {
    var p = iso.split("-");
    return new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]));
  }
  function shortDay(iso) {
    var d = parseDay(iso);
    return d.getDate() + " " + MONTHS[d.getMonth()];
  }
  function longDay(iso) {
    var d = parseDay(iso);
    return WEEKDAYS[(d.getDay() + 6) % 7] + " " + d.getDate() + " " + MONTHS[d.getMonth()];
  }
  function money(v) { return v === null || v === undefined ? "—" : MXN.format(v); }

  var STATES = {
    cerrado:       { ico: "\u25CF", text: "cerrado" },
    no_confirmado: { ico: "\u25D0", text: "cierre no confirmado" },
    en_curso:      { ico: "\u25CB", text: "en curso" },
    sin_cobro:     { ico: "\u2014", text: "sin cobro con tarjeta" }
  };

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) { n.className = cls; }
    if (text !== undefined && text !== null) { n.textContent = String(text); }
    return n;
  }
  function svgEl(tag, attrs) {
    var n = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (var k in attrs) { if (attrs[k] !== null) { n.setAttribute(k, attrs[k]); } }
    return n;
  }

  // El color de cada marca se fija una vez, por slug: filtrar una marca jamas
  // repinta a la que queda.
  function dark() {
    var stamp = root.getAttribute("data-theme");
    if (stamp === "dark") { return true; }
    if (stamp === "light") { return false; }
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  function hueOf(b) { return dark() ? b.color_dark : b.color; }
  function css(name) {
    return getComputedStyle(document.querySelector(".viz-root"))
      .getPropertyValue(name).trim();
  }

  // ---------------------------------------------------------------- estado
  var RANGES = [
    { id: "7", label: "7 dias", days: 7 },
    { id: "14", label: "14 dias", days: 14 },
    { id: "all", label: "Todo", days: 0 }
  ];
  var state = {
    range: M.days.length <= 14 ? "all" : "14",
    off: {}   // slugs apagados
  };

  function visibleDays() {
    var r = RANGES.filter(function (x) { return x.id === state.range; })[0];
    if (!r || !r.days) { return M.days.slice(); }
    return M.days.slice(Math.max(0, M.days.length - r.days));
  }
  function visibleBrands() {
    return M.brands.filter(function (b) { return !state.off[b.brand]; });
  }
  function sliceSeries(brand, days) {
    var byDay = {};
    brand.series.forEach(function (p) { byDay[p.date] = p; });
    return days.map(function (d) {
      return byDay[d] || { date: d, gross: null, tickets: null, avg_ticket: null };
    });
  }

  // ---------------------------------------------------------------- escalas
  function niceTicks(max, count) {
    if (!(max > 0)) { return [0, 1]; }
    var raw = max / count;
    var mag = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10));
    var norm = raw / mag;
    var step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10) * mag;
    var out = [];
    for (var v = 0; v <= max + step * 0.001; v += step) { out.push(Number(v.toFixed(6))); }
    if (out[out.length - 1] < max) { out.push(out[out.length - 1] + step); }
    return out;
  }

  // --------------------------------------------------- grafica de lineas
  // Un solo eje siempre: las dos marcas estan en la misma unidad. Nunca dos
  // escalas en una grafica.
  function lineChart(host, opts) {
    host.textContent = "";
    var days = opts.days, series = opts.series;
    var W = Math.max(320, host.clientWidth || 640);
    var pad = { t: 14, r: 64, b: 30, l: 60 };
    var H = Math.max(210, Math.min(300, Math.round(W * 0.34)));
    var iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;

    var max = 0;
    series.forEach(function (s) {
      s.points.forEach(function (p) { if (p.value !== null && p.value > max) { max = p.value; } });
    });
    var ticks = niceTicks(max, 4);
    var top = ticks[ticks.length - 1];
    var x = function (i) {
      return days.length === 1 ? pad.l + iw / 2
        : pad.l + (iw * i) / (days.length - 1);
    };
    var y = function (v) { return pad.t + ih - (ih * v) / (top || 1); };

    var svg = svgEl("svg", {
      viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": opts.aria || opts.title || "grafica"
    });
    var ink = css("--text-muted"), grid = css("--grid"), axis = css("--axis"),
        surf = css("--surface-1");

    ticks.forEach(function (t) {
      svg.appendChild(svgEl("line", {
        x1: pad.l, x2: pad.l + iw, y1: y(t), y2: y(t),
        stroke: t === 0 ? axis : grid, "stroke-width": 1
      }));
      var lbl = svgEl("text", {
        x: pad.l - 10, y: y(t) + 4, "text-anchor": "end",
        fill: ink, "font-size": 11, "font-variant-numeric": "tabular-nums"
      });
      lbl.textContent = opts.tickFormat(t);
      svg.appendChild(lbl);
    });

    // Etiquetas del eje x: solo las que caben, nunca una por punto.
    var every = Math.max(1, Math.ceil(days.length / Math.max(2, Math.floor(iw / 58))));
    days.forEach(function (d, i) {
      if (i % every !== 0 && i !== days.length - 1) { return; }
      var t = svgEl("text", {
        x: x(i), y: H - 10, "text-anchor": "middle", fill: ink, "font-size": 11
      });
      t.textContent = shortDay(d);
      svg.appendChild(t);
    });

    // Un hueco (sin dato) corta la linea; un cero la baja a la base. No son
    // lo mismo y no se dibujan igual.
    var endLabels = [];
    series.forEach(function (s) {
      var d = "", open = false, lastIdx = -1;
      s.points.forEach(function (p, i) {
        if (p.value === null) { open = false; return; }
        d += (open ? " L " : " M ") + x(i) + " " + y(p.value);
        open = true;
        lastIdx = i;
      });
      if (d) {
        svg.appendChild(svgEl("path", {
          d: d, fill: "none", stroke: s.color, "stroke-width": 2,
          "stroke-linejoin": "round", "stroke-linecap": "round"
        }));
      }
      if (lastIdx >= 0) {
        var p = s.points[lastIdx];
        svg.appendChild(svgEl("circle", {
          cx: x(lastIdx), cy: y(p.value), r: 4.5, fill: s.color,
          stroke: surf, "stroke-width": 2
        }));
        // Etiqueta directa solo en el ultimo punto con dato, y solo si ese
        // punto esta pegado al borde derecho: una etiqueta a media grafica no
        // es una etiqueta de extremo, es ruido encima de la linea.
        if (lastIdx >= days.length - 2) {
          endLabels.push({ x: x(lastIdx) + 10, y: y(p.value) + 4,
                           text: opts.tickFormat(p.value) });
        }
      }
    });

    // Cuando las lineas convergen, las etiquetas se encimarian. Separarlas a
    // mano las despega de su linea y se lee peor que no ponerlas: en ese caso
    // se cae a la leyenda y al tooltip, que ya traen el mismo numero.
    var sortedLabels = endLabels.slice().sort(function (a, b) { return a.y - b.y; });
    var crowded = sortedLabels.some(function (lab, i) {
      return i > 0 && Math.abs(lab.y - sortedLabels[i - 1].y) < 14;
    });
    if (!crowded) {
      endLabels.forEach(function (lab) {
        var node = svgEl("text", {
          x: lab.x, y: lab.y, fill: css("--text-secondary"),
          "font-size": 11, "font-weight": 600
        });
        node.textContent = lab.text;
        svg.appendChild(node);
      });
    }

    var hair = svgEl("line", {
      x1: 0, x2: 0, y1: pad.t, y2: pad.t + ih, stroke: axis,
      "stroke-width": 1, opacity: 0
    });
    svg.appendChild(hair);
    var dots = svgEl("g", { opacity: 0 });
    svg.appendChild(dots);
    svg.appendChild(svgEl("rect", {
      x: pad.l, y: pad.t, width: Math.max(1, iw), height: ih,
      fill: "transparent", class: "hit"
    }));
    host.appendChild(svg);

    var tip = el("div", "tip");
    host.appendChild(tip);

    // La cruz encuentra la X: el lector apunta a un dia, no a una linea de 2px.
    function show(i) {
      hair.setAttribute("x1", x(i));
      hair.setAttribute("x2", x(i));
      hair.setAttribute("opacity", 1);
      dots.textContent = "";
      dots.setAttribute("opacity", 1);
      tip.textContent = "";
      var when = el("div", "when", longDay(days[i]) + " · " +
        (STATES[M.day_states[days[i]]] || STATES.cerrado).text);
      tip.appendChild(when);
      series.forEach(function (s) {
        var p = s.points[i];
        var row = el("div", "row");
        var k = el("span", "stroke");
        k.style.background = s.color;
        row.appendChild(k);
        row.appendChild(el("span", null, s.name));
        row.appendChild(el("span", "num", p.value === null ? "sin dato"
          : opts.valueFormat(p.value)));
        tip.appendChild(row);
        if (p.value !== null) {
          dots.appendChild(svgEl("circle", {
            cx: x(i), cy: y(p.value), r: 4.5, fill: s.color,
            stroke: surf, "stroke-width": 2
          }));
        }
      });
      tip.style.opacity = 1;
      var tw = tip.offsetWidth || 150;
      var left = Math.min(Math.max(4, x(i) - tw / 2), W - tw - 4);
      tip.style.left = left + "px";
      tip.style.top = Math.max(0, pad.t - 6) + "px";
    }
    function hide() {
      hair.setAttribute("opacity", 0);
      dots.setAttribute("opacity", 0);
      tip.style.opacity = 0;
    }
    function nearest(ev) {
      var box = svg.getBoundingClientRect();
      var px = ((ev.clientX - box.left) / box.width) * W;
      var i = days.length === 1 ? 0
        : Math.round(((px - pad.l) / (iw || 1)) * (days.length - 1));
      return Math.max(0, Math.min(days.length - 1, i));
    }
    svg.addEventListener("pointermove", function (ev) { show(nearest(ev)); });
    svg.addEventListener("pointerleave", hide);
    svg.addEventListener("pointerdown", function (ev) { show(nearest(ev)); });
  }

  // ------------------------------------------- grafica de columnas por hora
  function columnChart(host, opts) {
    host.textContent = "";
    var cats = opts.categories, series = opts.series;
    var W = Math.max(320, host.clientWidth || 640);
    var pad = { t: 14, r: 16, b: 30, l: 50 };
    var H = Math.max(190, Math.min(260, Math.round(W * 0.30)));
    var iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;

    var max = 0;
    series.forEach(function (s) {
      s.values.forEach(function (v) { if (v > max) { max = v; } });
    });
    var ticks = niceTicks(max, 3);
    var top = ticks[ticks.length - 1];
    var band = iw / cats.length;
    var GAP = 2;                                   // separa con superficie, no con borde
    var inner = Math.max(2, band * 0.74);
    var bw = Math.max(2, Math.min(24, (inner - GAP * (series.length - 1)) / series.length));
    var y = function (v) { return pad.t + ih - (ih * v) / (top || 1); };

    var svg = svgEl("svg", {
      viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": opts.aria || "cobros por hora"
    });
    var ink = css("--text-muted"), grid = css("--grid"), axis = css("--axis");

    ticks.forEach(function (t) {
      svg.appendChild(svgEl("line", {
        x1: pad.l, x2: pad.l + iw, y1: y(t), y2: y(t),
        stroke: t === 0 ? axis : grid, "stroke-width": 1
      }));
      var lbl = svgEl("text", {
        x: pad.l - 10, y: y(t) + 4, "text-anchor": "end", fill: ink,
        "font-size": 11, "font-variant-numeric": "tabular-nums"
      });
      lbl.textContent = NUM.format(t);
      svg.appendChild(lbl);
    });

    var tip = el("div", "tip");

    cats.forEach(function (cat, i) {
      var cx = pad.l + band * i + band / 2;
      var groupW = bw * series.length + GAP * (series.length - 1);
      if (i % (cats.length > 14 ? 2 : 1) === 0) {
        var t = svgEl("text", {
          x: cx, y: H - 10, "text-anchor": "middle", fill: ink, "font-size": 11
        });
        t.textContent = opts.catLabel(cat);
        svg.appendChild(t);
      }
      series.forEach(function (s, j) {
        var v = s.values[i];
        var bx = cx - groupW / 2 + j * (bw + GAP);
        var hitH = ih;
        var hit = svgEl("rect", {
          x: bx - 3, y: pad.t, width: bw + 6, height: hitH, fill: "transparent"
        });
        if (v > 0) {
          var h = Math.max(2, pad.t + ih - y(v));
          // Punta redondeada de 4px, cuadrada en la base.
          var r = Math.min(4, h, bw / 2);
          var p = "M " + bx + " " + (pad.t + ih) +
                  " L " + bx + " " + (y(v) + r) +
                  " Q " + bx + " " + y(v) + " " + (bx + r) + " " + y(v) +
                  " L " + (bx + bw - r) + " " + y(v) +
                  " Q " + (bx + bw) + " " + y(v) + " " + (bx + bw) + " " + (y(v) + r) +
                  " L " + (bx + bw) + " " + (pad.t + ih) + " Z";
          svg.appendChild(svgEl("path", { d: p, fill: s.color }));
        }
        // En columnas la marca es el blanco: cada barra lleva su propio tooltip.
        hit.addEventListener("pointerenter", function () {
          tip.textContent = "";
          tip.appendChild(el("div", "when", opts.catLabel(cat) + " h"));
          series.forEach(function (ss) {
            var row = el("div", "row");
            var k = el("span", "stroke");
            k.style.background = ss.color;
            row.appendChild(k);
            row.appendChild(el("span", null, ss.name));
            row.appendChild(el("span", "num", NUM.format(ss.values[i]) + " cobros"));
            tip.appendChild(row);
          });
          tip.style.opacity = 1;
          var tw = tip.offsetWidth || 150;
          tip.style.left = Math.min(Math.max(4, cx - tw / 2), W - tw - 4) + "px";
          tip.style.top = Math.max(0, pad.t - 6) + "px";
        });
        hit.addEventListener("pointerleave", function () { tip.style.opacity = 0; });
        svg.appendChild(hit);
      });
    });

    host.appendChild(svg);
    host.appendChild(tip);
  }

  function sparkline(host, points, hue) {
    host.textContent = "";
    var W = 220, H = 34, pad = 3;
    var vals = points.filter(function (v) { return v !== null; });
    var max = Math.max.apply(null, vals.concat([1]));
    var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, "aria-hidden": "true" });
    var x = function (i) {
      return points.length === 1 ? W / 2 : (W - pad * 2) * i / (points.length - 1) + pad;
    };
    var y = function (v) { return H - pad - (H - pad * 2) * v / max; };
    var d = "", open = false, last = -1;
    points.forEach(function (v, i) {
      if (v === null) { open = false; return; }
      d += (open ? " L " : " M ") + x(i) + " " + y(v);
      open = true; last = i;
    });
    if (d) {
      svg.appendChild(svgEl("path", {
        d: d, fill: "none", stroke: css("--axis"), "stroke-width": 2,
        "stroke-linecap": "round", "stroke-linejoin": "round"
      }));
    }
    if (last >= 0) {
      svg.appendChild(svgEl("circle", {
        cx: x(last), cy: y(points[last]), r: 4, fill: hue,
        stroke: css("--surface-1"), "stroke-width": 2
      }));
    }
    host.appendChild(svg);
  }

  // ---------------------------------------------------------------- render
  function renderLegend(host, brands, kind) {
    host.textContent = "";
    if (brands.length < 2) { return; }   // una sola serie: el titulo ya la nombra
    brands.forEach(function (b) {
      var item = el("span", "item");
      var sw = el("span", kind === "rect" ? "swatch-rect" : "swatch-line");
      sw.style.background = hueOf(b);
      item.appendChild(sw);
      item.appendChild(el("span", null, b.name));
      host.appendChild(item);
    });
  }

  function renderFilters() {
    var ranges = document.getElementById("ranges");
    ranges.textContent = "";
    RANGES.forEach(function (r) {
      if (r.days && r.days >= M.days.length) { return; }
      var b = el("button", null, r.label);
      b.type = "button";
      b.setAttribute("aria-pressed", state.range === r.id ? "true" : "false");
      b.addEventListener("click", function () { state.range = r.id; renderAll(); });
      ranges.appendChild(b);
    });

    var bf = document.getElementById("brand-filters");
    bf.textContent = "";
    M.brands.forEach(function (brand) {
      var on = !state.off[brand.brand];
      var b = el("button", "brand-toggle");
      b.type = "button";
      b.setAttribute("aria-pressed", on ? "true" : "false");
      var k = el("span", "key");
      k.style.background = hueOf(brand);
      b.appendChild(k);
      b.appendChild(el("span", null, brand.name));
      b.addEventListener("click", function () {
        var left = visibleBrands();
        if (on && left.length === 1) { return; }   // nunca dejar el tablero vacio
        state.off[brand.brand] = on;
        renderAll();
      });
      bf.appendChild(b);
    });
  }

  function lastClosed(brand, days) {
    var pts = sliceSeries(brand, days);
    var out = [];
    for (var i = pts.length - 1; i >= 0; i--) {
      var st = M.day_states[pts[i].date];
      if (pts[i].gross !== null && (st === "cerrado" || st === "no_confirmado")) {
        out.push(pts[i]);
        if (out.length === 2) { break; }
      }
    }
    return out;
  }

  function renderTiles(brands, days) {
    var host = document.getElementById("tiles");
    host.textContent = "";
    brands.forEach(function (brand) {
      var hue = hueOf(brand);
      var pair = lastClosed(brand, days);
      var cur = pair[0], prev = pair[1];
      var tile = el("div", "tile");

      var head = el("div", "head");
      var k = el("span", "key");
      k.style.background = hue;
      head.appendChild(k);
      head.appendChild(el("span", "name", brand.name));
      if (brand.vehicle) { head.appendChild(el("span", "vehicle", brand.vehicle)); }
      tile.appendChild(head);

      if (!cur) {
        tile.appendChild(el("div", "label", "Sin dia cerrado en el rango"));
        tile.appendChild(el("div", "value", "—"));
        host.appendChild(tile);
        return;
      }

      var st = STATES[M.day_states[cur.date]] || STATES.cerrado;
      tile.appendChild(el("div", "label",
        "Ultimo dia " + (M.day_states[cur.date] === "no_confirmado" ? "capturado" : "cerrado") +
        " · " + longDay(cur.date)));
      tile.appendChild(el("div", "value", MXN0.format(cur.gross)));
      tile.appendChild(el("div", "meta",
        NUM.format(cur.tickets) + " cobros · ticket " + money(cur.avg_ticket) +
        " · " + st.text));
      if (prev) {
        var delta = prev.gross > 0 ? (cur.gross - prev.gross) / prev.gross : null;
        var txt = delta === null ? "sin base de comparacion"
          : (delta >= 0 ? "+" : "") + (delta * 100).toFixed(1) + "% vs " + shortDay(prev.date);
        // Un dia con mas o menos horas abiertas no es una caida: el ticket
        // promedio es lo que si se compara. Va junto al delta, no aparte.
        var tdelta = (prev.avg_ticket && cur.avg_ticket)
          ? " · ticket " + ((cur.avg_ticket - prev.avg_ticket) >= 0 ? "+" : "") +
            (((cur.avg_ticket - prev.avg_ticket) / prev.avg_ticket) * 100).toFixed(1) + "%"
          : "";
        tile.appendChild(el("div", "delta", txt + tdelta));
      }
      var spark = el("div", "spark");
      tile.appendChild(spark);
      host.appendChild(tile);
      sparkline(spark, sliceSeries(brand, days.slice(-12)).map(function (p) {
        return p.gross;
      }), hue);
    });
  }

  function renderDayTable(brands, days) {
    var host = document.getElementById("day-table");
    host.textContent = "";
    var table = el("table");
    var cap = el("caption",
      null,
      "Bruto con tarjeta y numero de cobros por dia de operacion (UTC-6). " +
      "«0» es un dia que paso sin cobro con tarjeta; «—» es que no hay dato " +
      "(la marca no operaba aun, o el dia todavia no pasa).");
    table.appendChild(cap);

    var thead = el("thead");
    var hr = el("tr");
    hr.appendChild(el("th", null, "Dia"));
    hr.appendChild(el("th", null, "Estado"));
    brands.forEach(function (b) {
      hr.appendChild(el("th", null, b.name + " · bruto"));
      hr.appendChild(el("th", null, "cobros"));
      hr.appendChild(el("th", null, "ticket"));
    });
    thead.appendChild(hr);
    table.appendChild(thead);

    var sliced = brands.map(function (b) { return sliceSeries(b, days); });
    var tbody = el("tbody");
    days.slice().reverse().forEach(function (day) {
      var idx = days.indexOf(day);
      var tr = el("tr");
      tr.appendChild(el("td", null, longDay(day)));
      var st = STATES[M.day_states[day]] || STATES.cerrado;
      var td = el("td");
      var span = el("span", "state");
      span.appendChild(el("span", "ico", st.ico));
      span.appendChild(el("span", null, st.text));
      td.appendChild(span);
      tr.appendChild(td);
      var running = M.day_states[day] === "en_curso";
      sliced.forEach(function (pts) {
        var p = pts[idx];
        var c1 = el("td", p.gross === null ? "nodata" : null,
          p.gross === null && running ? "aun sin cobro" : money(p.gross));
        tr.appendChild(c1);
        tr.appendChild(el("td", p.tickets === null ? "nodata" : null,
          p.tickets === null ? "—" : NUM.format(p.tickets)));
        tr.appendChild(el("td", p.avg_ticket === null ? "nodata" : null,
          money(p.avg_ticket)));
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    var tfoot = el("tfoot");
    var fr = el("tr");
    fr.appendChild(el("td", null, "Total del rango"));
    fr.appendChild(el("td", null, ""));
    sliced.forEach(function (pts) {
      var g = 0, n = 0;
      pts.forEach(function (p) {
        if (p.gross !== null) { g += p.gross; n += p.tickets; }
      });
      fr.appendChild(el("td", null, MXN.format(g)));
      fr.appendChild(el("td", null, NUM.format(n)));
      fr.appendChild(el("td", null, n ? MXN.format(g / n) : "—"));
    });
    tfoot.appendChild(fr);
    table.appendChild(tfoot);
    host.appendChild(table);
  }

  // Panel de apertura. Se dibuja una vez (no depende de los filtros de venta)
  // y si el modelo no lo trae, la tarjeta se queda oculta en vez de aparecer
  // vacia: un panel en blanco se lee como "ya no falta nada".
  function renderApertura() {
    var A = M.apertura;
    var card = document.getElementById("apertura-card");
    // El panel se pidio y se cayo: la tarjeta aparece **con la razon**, no se
    // esconde. Esconderla dejaria un tablero identico al de un dia sin
    // bloqueantes, y "ya no falta nada" es la lectura mas cara posible.
    if (!A && M.apertura_error) {
      card.hidden = false;
      document.getElementById("apertura-title").textContent =
        "Panel de apertura: no se pudo armar";
      document.getElementById("apertura-hint").textContent =
        "La venta de abajo si esta al dia. Lo que falta es el conteo de " +
        "pendientes, y falta por esto:";
      var err = document.getElementById("apertura-error");
      err.hidden = false;
      err.textContent = "";
      err.appendChild(el("strong", null, "No dice que no falte nada: "));
      err.appendChild(el("span", null, M.apertura_error));
      return;
    }
    if (!A) { return; }
    card.hidden = false;
    document.getElementById("apertura-title").textContent = A.title;
    document.getElementById("apertura-hint").textContent = A.hint || "";

    // Los pendientes que ya salen arriba como bloqueantes no se repiten, y los
    // que el consejo confirmo cerrados no se dibujan como pendientes aunque la
    // hoja los siga marcando asi: pedir dos veces algo ya hecho cuesta lo mismo
    // que no pedirlo. Se calcula aqui, antes de los numeros de cabecera, porque
    // el conteo de responsables es sobre los renglones **dibujados**: contar los
    // 18 de la hoja diria que faltan nombres en renglones que no se muestran.
    var others = (A.pending_rows || []).filter(function (p) {
      if (p.board_closed) { return false; }
      return !A.blockers.some(function (b) { return String(b.ref) === String(p.ref); });
    });
    var shown = A.blockers.concat(others);
    var named = shown.filter(function (r) { return r.owner_named; }).length;

    function stat(host, value, label, warn) {
      var box = el("div");
      box.appendChild(el("div", "open-num" + (warn ? " warn" : ""), value));
      box.appendChild(el("div", "open-lab", label));
      host.appendChild(box);
    }
    var head = document.getElementById("apertura-head");
    head.textContent = "";
    // El rotulo nombra la autoridad, no la hoja: estos son los renglones que el
    // consejo NO confirmo cerrados. Es el conteo que el panel publica, y es el
    // que no se mueve porque alguien edite la columna Estatus.
    var AU = A.authority || {};
    stat(head, NUM.format(A.blockers.length),
      "bloqueantes abiertos: sin confirmacion del responsable", A.blockers.length > 0);
    stat(head, NUM.format((AU.closed_refs || []).length) + " de " + NUM.format(AU.items || 0),
      "cerrados por confirmacion del consejo (tarjeta del " +
      (AU.resolved_label || "") + ")", false);
    // La hoja se sigue publicando, pero rotulada como lo que es: evidencia. Su
    // conteo y el de arriba no tienen por que coincidir, y cuando coinciden no
    // prueban nada (BOS-202: el mismo titular con 4 de 10 renglones mal).
    stat(head, NUM.format(A.source.pending) + " de " + NUM.format(A.source.rows),
      "renglones «Pendiente» en la hoja (evidencia, no autoridad)", false);
    // El numero que predice el cierre: en el corte del 04/10 los 19 renglones de
    // la hoja con responsable con nombre estaban los 19 entregados, y los 19 sin
    // nombre seguian abiertos salvo uno. Se cuenta, no se escribe.
    stat(head, NUM.format(named) + " de " + NUM.format(shown.length),
      "renglones abiertos con responsable con nombre", named < shown.length);
    var dias = A.source.stale_days;
    stat(head, dias === 0 ? "hoy" : NUM.format(dias) + (dias === 1 ? " dia" : " dias"),
      "sin movimiento en la hoja (corte " + A.source.modified_label + ")", dias >= 3);

    // Fuente clickeable cuando la hay: el panel dice de donde sale el numero,
    // no pide que alguien se acuerde.
    if (A.source.url) {
      var box = el("div");
      var a = el("a", null, "abrir la hoja");
      a.href = A.source.url;
      a.target = "_blank";
      a.rel = "noopener";
      box.appendChild(a);
      box.appendChild(el("div", "open-lab", A.source.label));
      head.appendChild(box);
    }

    function row(item, isBlocker) {
      var li = el("li", isBlocker ? "blk" : null);
      li.appendChild(el("span", "ref", item.ref));
      var what = el("span", "what");
      what.appendChild(el("b", null, item.title));
      var bits = [];
      if (item.group) { bits.push(item.group); }
      if (item.priority) { bits.push("prioridad " + item.priority); }
      if (item.status) { bits.push(item.status); }
      if (item.note) { bits.push(item.note); }
      if (item.issue) { bits.push("tarea " + item.issue); }
      if (bits.length) { what.appendChild(el("span", "meta", bits.join(" · "))); }
      // Lo que dice la hoja va en su propio chip y no en la meta: cuando dice
      // `Entregado` sobre un renglon que el consejo cuenta abierto, esa sola
      // linea es la que separa «ya esta» de «falta que lo confirme Said». Es el
      // renglon que antes no se dibujaba (BOS-202).
      if (item.sheet_label) {
        what.appendChild(el("span", "sheet" + (item.sheet_conflict ? " conflict" : ""),
          item.sheet_label));
      }
      if (item.board_closed_label) {
        what.appendChild(el("span", "sheet done", item.board_closed_label));
      }
      // El responsable va en su propio renglon, no mezclado con el resto de la
      // meta: es el dato que predice el cierre y es lo que se busca al leer la
      // lista. Los rotulos los calcula `_normalize_owner`; aqui solo se
      // imprimen, para que no haya una segunda copia de los literales.
      var who = el("span", "who" + (item.owner_named ? "" : " nobody"));
      who.appendChild(el("span", "who-lab", "responsable"));
      who.appendChild(el("b", null, item.owner_label));
      // `sin confirmar` es texto a la vista, no un tooltip: el dueño salio de la
      // hoja y no de su palabra, y el rotulo es justo lo que impide que el
      // tablero lo publique como dueño aceptado.
      if (item.owner_flag) { who.appendChild(el("span", "unconf", item.owner_flag)); }
      if (item.overdue_label) {
        who.appendChild(el("span", "late", item.overdue_label));
      }
      if (item.owner_note) { who.appendChild(el("span", "who-note", item.owner_note)); }
      what.appendChild(who);
      li.appendChild(what);
      return li;
    }

    var blockers = document.getElementById("apertura-blockers");
    blockers.textContent = "";
    A.blockers.forEach(function (b) { blockers.appendChild(row(b, true)); });

    var rest = document.getElementById("apertura-rest");
    if (!others.length) { rest.hidden = true; return; }
    rest.hidden = false;
    // El conteo va en el rotulo, calculado: una lista recortada no puede
    // quedarse con un numero viejo escrito en el JSON.
    document.getElementById("apertura-rest-title").textContent =
      (A.pending_title || "El resto de los pendientes") +
      " (" + NUM.format(others.length) + ")";
    // Los que el consejo confirmo cerrados salieron de la lista, y el panel dice
    // cuales: una lista mas corta sin explicacion se lee como que la hoja
    // cambio. La frase se arma del dato, no se escribe en el JSON.
    var hint = A.pending_hint || "";
    var cerrados = (AU.closed_in_sheet || []);
    if (cerrados.length) {
      hint += (hint ? " " : "") + "No se dibujan " + NUM.format(cerrados.length) +
        " renglones que la hoja sigue marcando «Pendiente» (" + cerrados.join(", ") +
        "): el consejo los confirmo cerrados el " + (AU.resolved_label || "") + ".";
    }
    document.getElementById("apertura-rest-hint").textContent = hint;
    var list = document.getElementById("apertura-pending");
    list.textContent = "";
    others.forEach(function (p) { list.appendChild(row(p, false)); });
  }

  function renderChecks() {
    var host = document.getElementById("checks");
    host.textContent = "";
    M.quality.checks.forEach(function (c) {
      var row = el("div", "check");
      var ok = c.count === 0;
      // Icono + rotulo: el color de estado nunca carga el significado solo.
      row.appendChild(el("span", "ico " + (ok ? "ok" : "bad"), ok ? "\u2713" : "\u2717"));
      var txt = el("span", "txt");
      var b = el("b", null, c.label);
      txt.appendChild(b);
      txt.appendChild(el("span", null, ": " + NUM.format(c.count)));
      if (!ok) { txt.appendChild(el("span", "fix", c.fix)); }
      row.appendChild(txt);
      host.appendChild(row);
    });
  }

  function renderLimits() {
    var host = document.getElementById("limits");
    host.textContent = "";
    var L = M.limits;
    var items = [];
    // El desglose se arma del dato y **por marca**, porque un monto por metodo
    // sumando las dos marcas seria el total que este tablero no publica:
    // "Casa Dorelia: tarjeta $3,954.00 (36)". Si manana entra un metodo nuevo
    // aparece solo, sin que nadie edite este texto.
    var mix = M.brands.map(function (b) {
      var parts = Object.keys(b.by_method || {}).map(function (k) {
        return k + " " + money(b.by_method[k].gross) +
          " (" + NUM.format(b.by_method[k].tickets) + ")";
      }).join(", ");
      return b.name + ": " + (parts || "sin cobros");
    }).join(" · ");
    if (L.cash_excluded) {
      items.push(["No dice la venta del dia, y el faltante no es chico. ",
        "Lo cargado es lo que cobro la terminal de Clip: " + mix + ". El efectivo " +
        "que la app de Clip registra aparte NO viaja por esta API: son entre 6 y 20 " +
        "cobros al dia por sucursal que no estan aqui (confirmado con Gustavo el " +
        "04/10). Cada monto es un piso, y la venta real es ese numero mas la caja."]);
    } else {
      items.push(["Ya entra efectivo en el total. ",
        mix + ". Deja de ser un piso solo si el efectivo del dia entro completo; " +
        "un efectivo a medias es peor que ninguno, porque se lee como venta."]);
    }
    if (L.payment_methods["otro"]) {
      items.push(["Hay cobros sin metodo identificado. ",
        NUM.format(L.payment_methods["otro"]) + " cobro(s) llegaron de Clip sin " +
        "tarjeta y sin rotulo («OTHER» con marca «XX» y sin emisor), y su monto " +
        "esta en el desglose de su marca. No se les llama tarjeta ni efectivo: " +
        "hay que mirarlos en la app de Clip antes de leerlos como venta. En 360 " +
        "dias y 2,329 cobros, los dos unicos renglones de esta forma resultaron " +
        "cancelaciones — no efectivo — y las cancelaciones ya no entran."]);
    }
    if (L.margin_unknown) {
      items.push(["No dice utilidad ni margen. ",
        "Ninguna de las " + NUM.format(M.rows_counted) + " ventas trae costo " +
        "(`cost_known: false`), porque Clip entrega el cobro, no el costo de lo " +
        "vendido. Graficar la utilidad daria cero y se leeria como perder todo el margen."]);
    }
    if (!L.itemized_rows) {
      items.push(["No dice que se vendio. ",
        "Los cobros de Clip entran con un solo renglon («Venta Clip, sin desglose»), " +
        "asi que no hay producto mas vendido. Eso solo sale del punto de venta."]);
    }
    items.push(["No hay un total de las dos marcas, y no lo va a haber. ",
      "Esta base guarda " + NUM.format(M.brands.length) + " negocios con repartos " +
      "y dueños distintos (" + M.brands.map(function (b) {
        return b.name + " / " + b.vehicle;
      }).join("; ") + "). Sumarlos da una cifra que no se le puede publicar a " +
      "nadie, porque no es la venta de ninguno de los dos. Cada marca tiene su " +
      "tarjeta, su linea y su renglon en la tabla; el unico numero que cruza las " +
      "dos es el conteo de " + NUM.format(M.rows_counted) + " renglones cargados."]);
    items.push(["El dia de hoy nunca esta completo. ",
      "La carga corre a las " + M.config.morning_catchup_local + " y a las " +
      M.config.snapshot_local + " CDMX. A la primera las sucursales no han abierto, " +
      "asi que un cero de la mañana es correcto, no una carga caida."]);

    items.forEach(function (pair) {
      var li = el("li");
      li.appendChild(el("b", null, pair[0]));
      li.appendChild(el("span", null, pair[1]));
      host.appendChild(li);
    });
  }

  // La edad del tablero, medida **al abrirlo**, no al generarlo.
  //
  // Por que no basta el "generado 04/10 21:19" del subtitulo: un HTML generado
  // es una foto, y una foto no se queja de estar vieja. El dia que la
  // republicacion de BOS-144 se caiga, el enlace sigue abriendo igual de bonito
  // con la venta de anteayer, y el lector que busca "cuanto vendimos" no hace la
  // resta de fechas en la cabeza. Esta cuenta la hace la pagina: es la unica
  // defensa que sigue funcionando cuando lo que fallo es justamente lo que
  // deberia haberla actualizado.
  function renderAge() {
    var node = document.getElementById("stale-note");
    var gen = new Date(M.generated_at);
    if (isNaN(gen.getTime())) { return; }
    var hours = (Date.now() - gen.getTime()) / 3600000;
    if (!(hours >= M.config.stale_after_hours)) { return; }
    var age = hours < 48
      ? Math.round(hours) + (Math.round(hours) === 1 ? " hora" : " horas")
      : Math.floor(hours / 24) + " dias";
    node.hidden = false;
    node.textContent = "";
    node.appendChild(el("strong", null,
      "Este tablero se genero hace " + age + ". No es la venta de hoy. "));
    node.appendChild(el("span", null,
      "Se republica a las " + M.config.morning_catchup_local + " y " +
      M.config.snapshot_local + " CDMX despues de cada carga de Clip, asi que una " +
      "pagina de mas de " + M.config.stale_after_hours + " h quiere decir que una " +
      "republicacion no corrio. Las cifras de abajo son las del " +
      shortDay(M.today) + ", cerradas a esa hora: no las leas como las de hoy."));
  }

  function renderHeader() {
    document.getElementById("title").textContent = M.title;
    var span = M.days.length
      ? shortDay(M.days[0]) + " a " + shortDay(M.days[M.days.length - 1])
      : "sin dias";
    document.getElementById("subtitle").textContent =
      span + " · " + NUM.format(M.rows_counted) + " cobros · generado " +
      M.generated_at_label + (M.db_name ? " · base " + M.db_name : "");

    renderAge();

    var note = document.getElementById("floor-note");
    note.textContent = "";
    note.appendChild(el("strong", null,
      M.limits.cash_excluded
        ? "Todo lo de aqui lo cobro la terminal de Clip, no es la venta del dia. "
        : "Esto ya incluye efectivo: leelo con el desglose por metodo. "));
    note.appendChild(el("span", null,
      (M.limits.cash_excluded
        ? "Tarjeta y vales si; el efectivo que la app de Clip registra aparte no " +
          "viaja por esta API, asi que cada cifra es un piso. "
        : "") +
      "Y esta base guarda dos marcas con repartos distintos: se leen por renglon, " +
      "nunca sumadas."));

    var hint = document.getElementById("gross-hint");
    hint.textContent = "Dia de operacion en hora del negocio (UTC-6), no dia UTC: " +
      "una venta de las 18:00 locales cae en el dia UTC siguiente. " +
      "La linea baja a cero en un dia que paso sin cobro, y se corta donde no hay " +
      "dato: antes del primer dia de la marca, y en el dia en curso mientras no " +
      "entre el primer cobro. Ese hueco de hoy no es una caida, es un dia que no " +
      "ha pasado; la tabla lo marca «en curso».";
  }

  function renderAll() {
    var days = visibleDays();
    var brands = visibleBrands();
    renderFilters();
    renderTiles(brands, days);

    var grossSeries = brands.map(function (b) {
      return {
        name: b.name, color: hueOf(b),
        points: sliceSeries(b, days).map(function (p) {
          return { date: p.date, value: p.gross };
        })
      };
    });
    renderLegend(document.getElementById("gross-legend"), brands, "line");
    lineChart(document.getElementById("gross-chart"), {
      days: days, series: grossSeries,
      aria: "Cobro con tarjeta por dia de operacion, una linea por marca",
      tickFormat: function (v) { return MXN0.format(v); },
      valueFormat: function (v) { return MXN.format(v); }
    });

    var avgSeries = brands.map(function (b) {
      return {
        name: b.name, color: hueOf(b),
        points: sliceSeries(b, days).map(function (p) {
          return { date: p.date, value: p.avg_ticket };
        })
      };
    });
    renderLegend(document.getElementById("avg-legend"), brands, "line");
    lineChart(document.getElementById("avg-chart"), {
      days: days, series: avgSeries,
      aria: "Ticket promedio por dia de operacion, una linea por marca",
      tickFormat: function (v) { return MXN0.format(v); },
      valueFormat: function (v) { return MXN.format(v); }
    });

    // Las horas se recortan a las que de verdad tuvieron cobro, para no
    // dibujar 24 columnas donde 9 estan vacias.
    var hours = [];
    for (var h = 0; h < 24; h++) {
      var any = brands.some(function (b) { return b.hours[h].tickets > 0; });
      if (any) { hours.push(h); }
    }
    if (!hours.length) { hours = [12]; }
    var lo = hours[0], hi = hours[hours.length - 1];
    var cats = [];
    for (var k2 = lo; k2 <= hi; k2++) { cats.push(k2); }
    renderLegend(document.getElementById("hour-legend"), brands, "rect");
    columnChart(document.getElementById("hour-chart"), {
      categories: cats,
      series: brands.map(function (b) {
        return {
          name: b.name, color: hueOf(b),
          values: cats.map(function (h2) { return b.hours[h2].tickets; })
        };
      }),
      aria: "Cobros con tarjeta por hora local, una columna por marca",
      catLabel: function (h3) { return String(h3).padStart(2, "0"); }
    });

    renderDayTable(brands, days);
  }

  // ---------------------------------------------------------------- arranque
  renderHeader();
  renderApertura();
  renderChecks();
  renderLimits();
  renderAll();

  var themeBtn = document.getElementById("theme");
  function syncTheme() {
    themeBtn.textContent = dark() ? "Modo claro" : "Modo oscuro";
  }
  themeBtn.addEventListener("click", function () {
    root.setAttribute("data-theme", dark() ? "light" : "dark");
    syncTheme();
    renderAll();   // los pasos de color son propios de cada modo, no un volteo
  });
  syncTheme();
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
    if (!root.getAttribute("data-theme")) { syncTheme(); renderAll(); }
  });

  var pending = null;
  window.addEventListener("resize", function () {
    clearTimeout(pending);
    pending = setTimeout(renderAll, 120);
  });

  document.getElementById("footer").textContent =
    "Generado por backend/dashboard.py desde " + (M.db_name || "la base configurada") +
    ". Solo lectura: el tablero no escribe en Mongo. " +
    "La carga que lo alimenta corre a las " + M.config.morning_catchup_local +
    " y " + M.config.snapshot_local + " CDMX (BOS-119).";
}());
</script>
</body>
</html>
"""


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
