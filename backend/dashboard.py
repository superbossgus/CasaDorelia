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
   efectivo, asi que un monto sin corte de caja es **piso**. El rotulo va en el
   encabezado y en cada tarjeta, no en una nota al pie — y se calcula por dia,
   no se escribe: ver `las dos direcciones del rotulo de piso`.
3. **No dibuja utilidad cuando no la sabe.** Las ventas de Clip entran con
   `cost_known: false`, `cost_total: 0` y `profit: 0`. Graficar eso daria una
   utilidad de cero que se lee como "perdimos todo el margen". Si ninguna venta
   trae costo, el tablero dice *no disponible* y no dibuja la grafica.
4. **No confunde "cero" con "no hay dato".** Antes del primer dia de una marca
   la linea se corta (hueco); dentro de su ventana, un dia sin cobro es un cero
   explicito. Un cero de dinero tiene que poder distinguirse de un campo que
   falta: la misma regla que `brands.py` aplica con `sin-marca`.
5. **No afirma que una sucursal cerrada vendio cero.** Un dia sin cobro dentro de
   la ventana de la marca es un cero *medido*, y eso es correcto solo si la
   sucursal estuvo abierta. Si no opero, ese cero es una afirmacion falsa, y se
   repite una vez por dia: ver `load_cierres`.

### Las ventanas sin operacion

Tecnoparque no cobro del 5/08 al 20/09/2026 (47 dias) ni del 21/04 al 10/05
(20 dias). Con la regla de arriba sola, el tablero dibujaba **67 ceros medidos**:
estaba afirmando que la sucursal operaba y vendia $0 dia tras dia. La Jefatura de
Tecnoparque determino en BOS-147 que no opero, y el dato lo respalda (cero vales
en los 40 dias de venta del hueco, cuando el año corre a ~1.3 vales por dia de
venta y un vale no se puede pagar en efectivo).

Esas ventanas **no viven en la plantilla**: viajan en un JSON aparte
(`--cierres`), igual que el panel de apertura, y `load_cierres` las valida antes
de dibujarlas. Un dia dentro de una ventana pasa de `0.0` a hueco, y la tabla lo
nombra con todas sus letras (`sin operacion`), como ya dice `en curso`.

Tres cosas que la ventana **no** puede hacer:

- **No puede esconder dinero.** Si un dia declarado sin operacion trae cobros, el
  cobro gana: se dibuja su cifra y el dia entra a los controles del dato como
  contradiccion. Un archivo editado a mano no debe poder borrar venta.
- **No puede fallar en silencio.** Una ventana cuya marca no existe en la base
  (un slug mal escrito) no hace nada, que es justo como se deja de notar: tambien
  entra al control.
- **No puede solaparse con otra de la misma marca.** Dos ventanas encimadas son
  la huella de una edicion a medias.

### Las dos direcciones del rotulo de piso

El efectivo no viaja por la API de Clip: lo captura la sucursal al cerrar, en
`cash_cut.py` (BOS-119). Mientras eso no se dibujaba aqui, el tablero rotulaba
**piso** los 365 dias del eje — incluidos los que ya tenian corte — y ese rotulo
estaba escrito, no calculado: la averia que este archivo evita en los otros
cuatro puntos.

Con los cortes en la mano, el rotulo se calcula **por dia y por marca**, y se
mueve en las dos direcciones:

- un dia **con corte** deja de ser piso: su total es `tarjeta + efectivo`;
- un dia **sin corte** sigue siendolo, aunque el de al lado si tenga.

Por dia *y por marca* porque un corte de Casa Dorelia no completa el dia de Le
Pain Dore: son dos sucursales con dos cajones. Por eso el estado del efectivo
vive en la celda de cada marca y no en la columna de estado del eje, que es una
sola para las dos — la misma leccion que `closed_all` en `day_states`.

Tres cosas que el corte **no** puede hacer:

- **Un corte en cero no es un hueco.** `ventas_efectivo: 0.0` es un cero
  *medido*: ese dia la sucursal abrio y no cobro efectivo, asi que el bruto con
  tarjeta **ya es la venta completa**. Es justo lo que vuelve citable ese dia.
- **No puede contar el mismo peso dos veces.** Si el dia ya trae un renglon de
  venta con `payment_method: efectivo` (del punto de venta, no de Clip), ese
  dinero ya esta en el bruto; sumarle el corte encima lo duplicaria. El bruto
  gana y el dia sale a los controles del dato.
- **No puede sumar dos veces el mismo turno.** Dos cortes de `(sucursal, dia,
  turno)` son el mismo corte capturado dos veces; `cash_cut.duplicate_cuts` los
  encuentra y salen a los controles en vez de inflar el dia.

Un corte capturado tarde (`captured_late`) o corregido (`revisions`) se marca en
su celda: ese numero se recordo o se corrigio, no se conto al cerrar el cajon.

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

Con `--apertura-optional` esa validacion deja de ser fatal: el panel se cae solo
y la tarjeta publica la razon. Es para el republicado automatico, donde la
alternativa a un panel desfasado no es "ningun tablero" sino el tablero de ayer
(ver `load_apertura_degrading`).

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
    python backend/dashboard.py --db casa_dorelia --cierres backend/cierres-casa-dorelia.json
    python backend/dashboard.py --db casa_dorelia --sin-cortes   # solo tarjeta

Los cortes de caja se leen de la misma base (`cash_cuts`) sin que haya que
pedirlo: el default es publicar el total, y `--sin-cortes` es lo que hay que
escribir para volver al piso. Al reves — tener que acordarse de una bandera para
que entre el efectivo — es como un tablero termina publicando un piso que nadie
rotulo.

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
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import brands as brands_mod
import business_day
import cash_cut

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
               has_sales: Mapping[str, bool],
               closed_all: Optional[Mapping[str, bool]] = None) -> Dict[str, str]:
    """Estado de cada dia del eje: `en_curso`, `no_confirmado`, `cerrado`, `sin_cobro`, `sin_operacion`.

    `last_capture` trae los minutos locales de la ultima venta de cada dia.
    `now_minutes` son los minutos locales del momento en que se genera, y es lo
    que decide si el catch-up de las 07:45 ya confirmo el dia de ayer.

    La duda de cierre se limita a **un** dia a proposito. El catch-up de la
    mañana vuelve a pedir el dia anterior completo; si no trajo renglones
    nuevos, el dia quedo cerrado y arrastrar la duda seria sembrar desconfianza
    sobre una cifra ya verificada.

    `closed_all` marca los dias en que **ninguna** marca ya abierta estaba
    operando (lo calcula `build_model` con las ventanas de `load_cierres`). Esta
    columna es una sola para todo el eje, asi que solo puede decir "sin
    operacion" cuando no opero nadie: con una marca cerrada y la otra vendiendo,
    el renglon sigue siendo el de la marca que vendio y el "sin operacion" va en
    su celda. Un dia con cobros nunca es `sin_operacion`, por construccion.
    """
    previous = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
    catchup_ran = now_minutes >= _minutes(MORNING_CATCHUP_LOCAL)
    threshold = _minutes(SNAPSHOT_LOCAL) - SNAPSHOT_MARGIN_MINUTES
    closed_all = closed_all or {}

    states: Dict[str, str] = {}
    for day in axis:
        if day >= today:
            states[day] = "en_curso"
            continue
        if not has_sales.get(day):
            states[day] = "sin_operacion" if closed_all.get(day) else "sin_cobro"
            continue
        close = last_capture.get(day)
        hedge = day == previous and not catchup_ran
        if hedge and close is not None and close >= threshold:
            states[day] = "no_confirmado"
        else:
            states[day] = "cerrado"
    return states


def load_apertura(path: str, *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Panel de pendientes operativos, desde un JSON aparte y con controles.

    No sale de Mongo porque no es venta: sale de la hoja de seguimiento y del
    tablero de tareas. Viaja en su propio archivo para que el modulo siga sin
    conocer a ninguna empresa en particular, y para que el dia que la hoja se
    mueva se edite un JSON de 40 renglones, no la plantilla.

    Tres controles, porque un panel escrito a mano es justo el que se desfasa:

    1. `entregados + pendientes == renglones`. Un conteo que no cuadra con el
       total de la hoja esta viejo, y un numero viejo arriba del tablero es peor
       que no tenerlo.
    2. Si viene la lista de pendientes, tiene que tener tantos renglones como
       dice el conteo. Asi no se puede recortar la lista y dejar el numero.
    3. Cada bloqueante tiene que estar en la lista de pendientes (por `ref`), o
       traer `fuera_de_hoja: true` dicho explicitamente (el caso de los anexos
       del contrato, que no son renglones de la hoja).

    La antiguedad del corte se *calcula* contra el dia de generacion: el panel
    no puede decir "al dia" porque alguien escribio eso una vez.
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

    pending_rows = list(data.get("pending_rows") or [])
    if pending_rows and len(pending_rows) != source["pending"]:
        raise DashboardError(
            f"la lista de pendientes trae {len(pending_rows)} renglones pero el "
            f"corte dice {source['pending']}")

    blockers = [dict(b) for b in data["blockers"]]
    if not blockers:
        raise DashboardError("el archivo de apertura no trae un solo bloqueante")
    if pending_rows:
        refs = {str(row.get("ref")) for row in pending_rows}
        for blocker in blockers:
            if not blocker.get("off_sheet") and str(blocker.get("ref")) not in refs:
                raise DashboardError(
                    f"el bloqueante {blocker.get('ref')} no esta entre los "
                    "pendientes de la hoja (ni se declara `off_sheet`)")

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


def load_cierres(path: str) -> Dict[str, Any]:
    """Ventanas de **no operacion** por marca, desde un JSON aparte y con controles.

    Un dia sin cobro dentro de la ventana de una marca se dibuja como cero
    medido, y eso es correcto solo si la sucursal estuvo abierta. Cuando no
    opero, el cero es una afirmacion falsa repetida una vez por dia: 47 veces en
    el corte de Tecnoparque del 5/08 al 20/09/2026, 20 mas en el del 21/04 al
    10/05 (BOS-147). Estas ventanas convierten esos ceros en huecos.

    Viaja en su propio archivo, como `--apertura`, por la misma razon: la
    determinacion de que una sucursal no opero es un dato operativo con dueño y
    fecha, no una constante del codigo, y el dia que cambie se edita un JSON de
    diez renglones en vez de la plantilla.

    Formato:

        {
          "source": "quien lo determino y en que tarea",
          "windows": [
            {"brand": "le-pain-dore", "from": "2026-08-05", "to": "2026-09-20",
             "label": "sin operacion", "note": "por que, si se sabe"}
          ]
        }

    Cuatro controles, porque una ventana escrita a mano puede tapar venta:

    1. `brand`, `from` y `to` son obligatorios. Sin marca la ventana aplicaria a
       todo el tablero, que es lo contrario de lo que se declaro.
    2. `from <= to`, y las dos en ISO. Un rango invertido no marca nada y se ve
       igual que uno que funciona.
    3. Dos ventanas de la **misma marca** no se pueden solapar: es la huella de
       una edicion a medias, y un hueco contado dos veces esconde cual de las dos
       ediciones quedo.
    4. `label` default `sin operacion`. Es lo que la tabla imprime; el motivo
       (opcional, `note`) va aparte porque puede llegar despues sin mover fechas.

    El quinto control no puede vivir aqui, porque depende de la venta: una
    ventana que cubre dias **con** cobro, y una cuya marca no existe en la base.
    Los dos los detecta `build_model` y los publica como contradiccion.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise DashboardError(f"no existe el archivo de cierres: {path}") from exc
    except ValueError as exc:
        raise DashboardError(f"el archivo de cierres no es JSON valido: {exc}") from exc

    if not isinstance(data, Mapping):
        raise DashboardError("el archivo de cierres no es un objeto JSON")
    for key in ("source", "windows"):
        if key not in data:
            raise DashboardError(f"el archivo de cierres no trae `{key}`")

    raw = data["windows"]
    if not isinstance(raw, list) or not raw:
        raise DashboardError("el archivo de cierres no trae ni una sola ventana")

    windows: List[Dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise DashboardError(f"la ventana #{index + 1} no es un objeto")
        for key in ("brand", "from", "to"):
            if not item.get(key):
                raise DashboardError(f"la ventana #{index + 1} no trae `{key}`")
        try:
            start = date.fromisoformat(str(item["from"]))
            end = date.fromisoformat(str(item["to"]))
        except ValueError as exc:
            raise DashboardError(
                f"la ventana #{index + 1} trae una fecha ilegible: {exc}") from exc
        if start > end:
            raise DashboardError(
                f"la ventana #{index + 1} esta invertida: {item['from']} > {item['to']}")
        windows.append({
            "brand": str(item["brand"]),
            "from": start.isoformat(),
            "to": end.isoformat(),
            "label": str(item.get("label") or "sin operacion"),
            "note": item.get("note"),
            # Dias naturales, calculados: un conteo escrito a mano se desfasa en
            # cuanto alguien mueve un extremo.
            "days": (end - start).days + 1,
        })

    windows.sort(key=lambda w: (w["brand"], w["from"]))
    for previous, current in zip(windows, windows[1:]):
        if previous["brand"] == current["brand"] and current["from"] <= previous["to"]:
            raise DashboardError(
                f"dos ventanas de {current['brand']} se solapan: "
                f"{previous['from']}..{previous['to']} y {current['from']}..{current['to']}")

    return {"source": str(data["source"]), "windows": windows}


def load_cierres_degrading(path: Optional[str]) -> tuple:
    """`load_cierres` que devuelve su falla en vez de levantarla.

    Misma forma y misma razon que `load_apertura_degrading`: en el republicado
    automatico (BOS-144) tumbar el tablero por un JSON mal editado dejaria
    publicada la venta de ayer. Aqui el costo de degradar es mas alto que alla
    —sin ventanas el tablero vuelve a dibujar los ceros falsos—, asi que la razon
    viaja en el modelo y la pagina la publica junto a los ceros que la ventana
    iba a tapar. A mano sigue tronando: quien corre el comando a proposito quiere
    enterarse.
    """
    if not path:
        return None, None
    try:
        return load_cierres(path), None
    except DashboardError as exc:
        return None, str(exc)


def load_cortes_degrading(mongo_url: Optional[str] = None,
                          db_name: Optional[str] = None) -> tuple:
    """Los cortes de caja de la base, o la razon por la que no se pudieron leer.

    Mismo trato que `load_apertura_degrading` y por la misma razon: en el
    republicado automatico (BOS-144) tumbar el tablero porque la coleccion
    `cash_cuts` no respondio dejaria publicada la venta de ayer.

    Degradar aqui es **caro y silencioso**: sin cortes el tablero vuelve a
    rotular piso todos los dias, que es exactamente lo que se ve cuando de
    verdad no hay ningun corte capturado. Los dos casos se verian iguales, asi
    que la razon viaja en el modelo (`cortes_error`) y la pagina la publica
    junto a los dias que el corte iba a completar. "Falta el efectivo" y "no
    pude preguntar por el efectivo" no son la misma frase.
    """
    try:
        collection = cash_cut.open_collection(mongo_url, db_name)
        return cash_cut.read_cuts(collection, limit=100000), None
    except cash_cut.CashCutError as exc:
        return None, str(exc)
    except Exception as exc:  # pragma: no cover - red/driver/permisos
        return None, f"{type(exc).__name__}: {exc}"


def _in_windows(day: str, windows: Sequence[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    """La ventana que cubre ese dia, o `None`. Las fechas ISO comparan como texto."""
    for window in windows:
        if window["from"] <= day <= window["to"]:
            return window
    return None


def build_model(sales: Iterable[Mapping[str, Any]], *, title: str,
                today: Optional[str] = None, now: Optional[datetime] = None,
                db_name: Optional[str] = None,
                apertura: Optional[Mapping[str, Any]] = None,
                apertura_error: Optional[str] = None,
                cierres: Optional[Mapping[str, Any]] = None,
                cierres_error: Optional[str] = None,
                cortes: Optional[Iterable[Mapping[str, Any]]] = None,
                cortes_error: Optional[str] = None) -> Dict[str, Any]:
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

    `cierres` son las ventanas de no operacion por marca (ver `load_cierres`).
    Dentro de una ventana, un dia sin cobro deja de ser un cero medido y pasa a
    hueco. Lo que **no** hace es tapar venta: si el dia trae cobros gana el
    cobro, y el dia entra a los controles del dato como contradiccion. Igual una
    ventana cuya marca no aparece en la base — un slug mal escrito no hace nada,
    y "no hacer nada en silencio" es como se deja de notar que la ventana murio.

    `cortes` son los documentos de `cash_cuts` (`cash_cut.read_cuts`). Son la
    unica fuente del efectivo, porque la API de Clip no lo entrega. Con ellos el
    rotulo de piso se calcula por dia y por marca en vez de escribirse para todo
    el eje: ver la seccion del modulo. `None` no es lo mismo que `[]` —
    `None` es "no se preguntaron los cortes" y deja el tablero como estaba,
    mientras que `[]` es "se preguntaron y no hay ninguno", que si rotula cada
    dia como `sin corte`. Un tablero que no pregunto y uno que pregunto y no
    encontro nada tienen que verse distinto.

    `cortes_error` es el caso de en medio, igual que `apertura_error`: la
    coleccion no respondio y la razon se publica, porque "falta el efectivo" y
    "no pude preguntar por el efectivo" se dibujarian iguales.
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
    # `(marca, dia)` que ya traen efectivo **dentro del bruto**, por un renglon
    # de venta con `payment_method: efectivo` (punto de venta, no Clip). Es lo
    # que impide sumarle el corte encima y contar el mismo peso dos veces. Hoy
    # esta vacio —la sucursal no usa el punto de venta— y por eso mismo tiene
    # que estar: el dia que se use, nadie se va a acordar de esta resta.
    pos_cash: Dict[Tuple[str, str], Dict[str, float]] = {}

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
        if method == cash_cut.METHOD_CASH:
            pos = pos_cash.setdefault((slug, day), {"gross": 0.0, "tickets": 0})
            pos["gross"] += total
            pos["tickets"] += 1
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

    brand_slugs = sorted(per_day)
    first_days = {slug: min(per_day[slug]) for slug in brand_slugs}

    # Ventanas de no operacion, repartidas por marca. Una ventana cuya marca no
    # aparece en la base no se descarta en silencio: se cuenta, porque un slug
    # mal escrito deja de tapar los ceros falsos sin que nadie se entere.
    all_windows = list((cierres or {}).get("windows") or [])
    windows_by_brand: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    unknown_windows: List[Dict[str, Any]] = []
    for window in all_windows:
        if window["brand"] in per_day:
            windows_by_brand[window["brand"]].append(window)
        else:
            unknown_windows.append(dict(window))

    # Dias en que **ninguna** marca ya abierta estaba operando. Es lo unico que
    # la columna de estado (una sola para todo el eje) puede llamar "sin
    # operacion" sin mentir sobre la otra marca.
    closed_all: Dict[str, bool] = {}
    for day in axis:
        open_brands = [s for s in brand_slugs if first_days[s] <= day]
        closed_all[day] = bool(open_brands) and all(
            _in_windows(day, windows_by_brand[s]) for s in open_brands)

    states = day_states(axis=axis, last_capture=last_capture, today=today,
                        now_minutes=now_local.hour * 60 + now_local.minute,
                        has_sales=has_sales, closed_all=closed_all)

    # El efectivo de los cortes, agregado por marca y por dia. La agregacion no
    # se reescribe aqui: `cash_by_day` y `duplicate_cuts` ya estan probados en
    # `test_cash_cut.py`, y dos implementaciones del mismo reparto de dinero es
    # como una se queda atras.
    cuts = None if cortes is None else list(cortes)
    cash_days: Dict[str, Dict[str, Dict[str, Any]]] = (
        cash_cut.cash_by_day(cuts) if cuts else {})
    # Lo que `cash_by_day` no lleva, porque no es dinero: si ese numero se
    # recordo tarde o se corrigio. Va por `(marca, dia)` para que la celda lo
    # pueda marcar — un total citable y un total recordado no se leen igual.
    cut_marks: Dict[Tuple[str, str], Dict[str, bool]] = {}
    for cut in (cuts or []):
        cut_day = str(cut.get("business_date") or "")[:10]
        if not cut_day:
            continue
        mark = cut_marks.setdefault(
            (cut.get("brand") or brands_mod.UNKNOWN_BRAND, cut_day),
            {"late": False, "revised": False})
        if cut.get("captured_late"):
            mark["late"] = True
        if cut.get("revisions"):
            mark["revised"] = True

    # Las tres formas en que un corte puede estar mal, y ninguna se ve en la
    # grafica. Se llenan dentro del recorrido por marca, abajo.
    cash_double: List[Dict[str, Any]] = []   # el peso ya estaba en el bruto
    cash_on_closed: List[Dict[str, Any]] = []  # corte en un dia declarado cerrado
    cash_duplicates = cash_cut.duplicate_cuts(cuts) if cuts else []

    # Dias declarados sin operacion que si traen cobro. El cobro gana —este
    # tablero no puede borrar venta con un archivo de configuracion— y la
    # contradiccion sale a los controles del dato.
    conflicts: List[Dict[str, Any]] = []
    brand_models: List[Dict[str, Any]] = []
    for index, slug in enumerate(brand_slugs):
        day_rows = per_day[slug]
        active = sorted(day_rows)
        first_day, last_day = active[0], active[-1]
        brand_windows = windows_by_brand[slug]

        brand_cash = cash_days.get(slug) or {}

        def attach_cash(point: Dict[str, Any], day: str,
                        closed: Optional[Mapping[str, Any]] = None,
                        slug: str = slug,
                        first_day: str = first_day,
                        brand_cash: Mapping[str, Any] = brand_cash) -> Dict[str, Any]:
            """Pega el efectivo del corte de ESE dia y marca su estado.

            Los parametros con default amarran la marca del ciclo: sin eso, la
            funcion leeria la ultima marca para todas.
            """
            if cuts is None or day < first_day:
                # Nadie pregunto por los cortes, o el dia es de antes de que la
                # marca existiera: no hay cajon que contar ni estado que decir.
                return point
            cut = brand_cash.get(day)
            if cut is None:
                # Hueco, nunca cero: un dia sin corte no es un dia sin
                # efectivo. Y su bruto sigue siendo piso, aunque el de al lado
                # ya tenga corte.
                point["cash"] = None
                point["cash_state"] = "sin_corte"
                point["gross_total"] = None
                return point
            cash = _round2(float(cut["cash"]))
            point["cash"] = cash
            point["cash_state"] = "con_corte"
            point["cash_cuts"] = int(cut["cuts"])
            mark = cut_marks.get((slug, day)) or {}
            if mark.get("late"):
                point["cash_late"] = True
            if mark.get("revised"):
                point["cash_revised"] = True
            pos = pos_cash.get((slug, day))
            if pos:
                # El bruto ya trae efectivo (un renglon del punto de venta):
                # sumarle el corte encima contaria el mismo peso dos veces.
                # Gana el bruto, que es el que tiene el cobro renglon por
                # renglon, y la contradiccion sale a los controles del dato.
                cash_double.append({"brand": slug, "date": day, "cash": cash,
                                    "pos_gross": _round2(pos["gross"]),
                                    "pos_tickets": int(pos["tickets"])})
                point["cash_state"] = "doble"
                point["gross_total"] = None
                return point
            if closed is not None:
                cash_on_closed.append({
                    "brand": slug, "date": day, "cash": cash,
                    "window": f"{closed['from']}..{closed['to']}"})
            point["gross_total"] = (None if point["gross"] is None
                                    else _round2(point["gross"] + cash))
            return point

        series: List[Dict[str, Any]] = []
        for day in axis:
            if day < first_day:
                # Antes del primer dia de la marca no hay dato: hueco, no cero.
                series.append(attach_cash({"date": day, "gross": None,
                                           "tickets": None,
                                           "avg_ticket": None}, day))
                continue
            bucket = day_rows.get(day)
            closed = _in_windows(day, brand_windows) if day < today else None
            if bucket is None and closed is not None:
                # Declarado sin operacion: hueco rotulado, no un cero medido.
                # `closed` viaja en el punto para que la celda pueda decir por
                # que falta; un hueco callado se lee como "no hay dato todavia".
                series.append(attach_cash({"date": day, "gross": None,
                                           "tickets": None, "avg_ticket": None,
                                           "closed": closed["label"]},
                                          day, closed))
                continue
            if bucket is not None and closed is not None:
                conflicts.append({
                    "brand": slug, "date": day,
                    "tickets": int(bucket["tickets"]),
                    "gross": _round2(bucket["gross"]),
                    "window": f"{closed['from']}..{closed['to']}",
                })
            if bucket is None:
                # El dia en curso sin cobro todavia **no es un cero medido**: es
                # un dia que no ha pasado. Graficarlo en cero desploma la linea
                # y se lee como un derrumbe de la venta, cuando a las 07:45 lo
                # correcto es que no haya nada. Va como hueco; la tabla lo dice
                # con todas sus letras ("en curso"), asi que no se esconde.
                zero = None if day >= today else 0.0
                series.append(attach_cash({"date": day, "gross": zero,
                                           "tickets": None if zero is None else 0,
                                           "avg_ticket": None}, day))
                continue
            tickets = int(bucket["tickets"])
            gross = _round2(bucket["gross"])
            series.append(attach_cash({
                "date": day,
                "gross": gross,
                "tickets": tickets,
                "avg_ticket": _round2(gross / tickets) if tickets else None,
            }, day))

        total_gross = _round2(sum(float(b["gross"]) for b in day_rows.values()))
        total_tickets = int(sum(int(b["tickets"]) for b in day_rows.values()))

        # El total de los dias **con corte**, y solo de esos. Sumar el efectivo
        # que haya contra el bruto de todo el rango daria una cifra mitad
        # completa y mitad piso: la peor de las tres, porque no se puede citar
        # ni como una cosa ni como la otra y nada en la pagina lo diria. Esto si
        # se puede citar: "los N dias con corte vendieron X".
        covered = [p for p in series if p.get("cash_state") == "con_corte"
                   and p.get("gross_total") is not None]
        covered_cash = _round2(sum(float(p["cash"]) for p in covered))
        covered_gross = _round2(sum(float(p["gross"]) for p in covered))
        covered_tickets = int(sum(int(p["tickets"] or 0) for p in covered))
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
                # El unico total citable como venta y no como piso: los dias de
                # ESTA marca que si tienen corte. `days: 0` es lo normal
                # mientras no haya cortes, y se lee como lo que es.
                "con_corte": {
                    "days": len(covered),
                    "gross": covered_gross,
                    "cash": covered_cash,
                    "total": _round2(covered_gross + covered_cash),
                    "tickets": covered_tickets,
                    "first_day": covered[0]["date"] if covered else None,
                    "last_day": covered[-1]["date"] if covered else None,
                },
            },
            # Con que se cobro, en pesos de ESTA marca. Es lo que separa un vale
            # de una tarjeta y lo que deja ver, el dia que entre, el efectivo.
            "by_method": {
                method: {"gross": _round2(per_method[slug][method]["gross"]),
                         "tickets": int(per_method[slug][method]["tickets"])}
                for method in sorted(per_method[slug])
            },
            # Las ventanas declaradas de ESTA marca. Van en su renglon, no en un
            # campo global, porque una sucursal cerrada no cierra a la otra.
            "no_operacion": [dict(w) for w in brand_windows],
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
        # Las dos formas en que una ventana de no operacion puede estar mal, y
        # ninguna de las dos se ve en la grafica: un dia declarado cerrado que si
        # cobro (la ventana estaria tapando venta, asi que no se aplica) y una
        # ventana cuya marca no existe en la base (no tapa nada, en silencio).
        {"id": "cierres",
         "label": "Ventanas sin operacion que el dato contradice",
         "count": len(conflicts) + len(unknown_windows),
         "fix": "revisar las fechas y los slugs del archivo de --cierres contra "
                "la base: el cobro siempre gana"},
        # Las tres formas en que un corte puede mover dinero sin que se vea en
        # la grafica: sumar el mismo turno dos veces, sumarse encima de un
        # efectivo que ya estaba en el bruto, y aparecer en un dia que se
        # declaro sin operacion. Ninguna se nota mirando la linea.
        {"id": "cortes", "label": "Cortes de caja que el dato contradice",
         "count": len(cash_duplicates) + len(cash_double) + len(cash_on_closed),
         "fix": "revisar el indice unico de `cash_cuts` y los dias que salen "
                "listados en el modelo (`cortes`)"},
    ]
    for check in checks:
        check["status"] = "good" if check["count"] == 0 else "critical"

    # El rotulo de piso, **contado de los dias-marca** que ya se armaron arriba y
    # no escrito aparte. Contarlo de la serie es lo que garantiza que el
    # encabezado no pueda decir una cosa distinta de las celdas de la tabla: si
    # manana cambia la regla de una celda, este conteo cambia con ella.
    cash_covered = 0
    cash_missing = 0
    cash_conflict = 0
    covered_days_seen: List[str] = []
    for brand_model in brand_models:
        for point in brand_model["series"]:
            state = point.get("cash_state")
            if state == "sin_corte":
                cash_missing += 1
            elif state == "doble":
                cash_conflict += 1
            elif state == "con_corte":
                cash_covered += 1
                covered_days_seen.append(point["date"])

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
        # Las ventanas de no operacion, con su fuente y con lo que el dato les
        # contradice. La fuente va en el modelo porque un hueco rotulado sin
        # dueño es indistinguible de un hueco inventado.
        "cierres": {
            "source": (cierres or {}).get("source"),
            "windows": [dict(w) for w in all_windows],
            "conflicts": conflicts,
            "unknown_brands": unknown_windows,
        } if cierres else None,
        "cierres_error": cierres_error if cierres is None else None,
        # Los cortes de caja, con lo que el dato les contradice. `None` es "no se
        # preguntaron"; un bloque con `cuts: 0` es "se preguntaron y no hay
        # ninguno", y los dos se dibujan distinto. No hay un monto aqui: el
        # efectivo vive en la celda de cada marca, y un total de efectivo de las
        # dos cruzaria los dos repartos igual que un total de venta.
        "cortes": {
            "cuts": len(cuts),
            "late": sum(1 for c in cuts if c.get("captured_late")),
            "revised": sum(1 for c in cuts if c.get("revisions")),
            "duplicates": cash_duplicates,
            "double_counted": cash_double,
            "on_closed_days": cash_on_closed,
        } if cuts is not None else None,
        "cortes_error": cortes_error if cuts is None else None,
        "quality": {"checks": checks},
        "limits": {
            # Calculados, no escritos a mano: el dia que el dato cambie, el
            # rotulo cambia con el.
            # El estado del efectivo, **contado por dia-marca**. Dejo de ser un
            # `cash_excluded` global en BOS-149: un solo booleano para todo el
            # eje rotulaba piso los dias que ya tenian corte, y el dia que
            # entrara el primer corte habria dejado de rotular piso los otros
            # 364. El rotulo tiene que moverse en las dos direcciones, y por eso
            # aqui solo viven conteos: la frase la arma la pagina con ellos.
            "cash": {
                # "No se preguntaron los cortes" no es "no hay cortes".
                "consulted": cuts is not None,
                "days_covered": cash_covered,
                "days_missing": cash_missing,
                "days_conflict": cash_conflict,
                "all_missing": cash_covered == 0,
                "none_missing": cash_covered > 0 and cash_missing == 0,
                "first_covered_day": min(covered_days_seen) if covered_days_seen else None,
                "last_covered_day": max(covered_days_seen) if covered_days_seen else None,
                "cuts": len(cuts or []),
                "late_cuts": sum(1 for c in (cuts or []) if c.get("captured_late")),
                "revised_cuts": sum(1 for c in (cuts or []) if c.get("revisions")),
                "duplicate_cuts": len(cash_duplicates),
                # Renglones de venta que ya traian el efectivo **dentro** del
                # bruto (punto de venta, no Clip). Antes esto era todo el
                # semaforo del efectivo; hoy es un conteo mas, porque el
                # efectivo de verdad llega por el corte.
                "pos_rows": payment_methods.get(cash_cut.METHOD_CASH, 0),
            },
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
    parser.add_argument("--cierres", default=None, metavar="ARCHIVO.json",
                        help="ventanas de no operacion por marca (ver load_cierres); "
                             "sin esto, un dia pasado sin cobro dentro de la ventana "
                             "de la marca se dibuja como cero medido")
    parser.add_argument("--cierres-optional", action="store_true",
                        help="si el archivo de cierres no cuadra, publicar el tablero "
                             "sin ventanas (y con la razon a la vista) en vez de fallar")
    parser.add_argument("--sin-cortes", dest="sin_cortes", action="store_true",
                        help="no leer `cash_cuts`: el tablero sale solo con lo "
                             "que cobro la terminal y rotula piso cada dia. El "
                             "default es leerlos, porque el efectivo no viaja "
                             "por la API de Clip y un piso sin rotular se lee "
                             "como la venta del dia")
    parser.add_argument("--json", action="store_true",
                        help="imprime el modelo en JSON en vez de escribir el HTML")

    args = parser.parse_args(argv)

    try:
        if args.apertura_optional:
            apertura, apertura_error = load_apertura_degrading(args.apertura)
        else:
            apertura = load_apertura(args.apertura) if args.apertura else None
            apertura_error = None
        if args.cierres_optional:
            cierres, cierres_error = load_cierres_degrading(args.cierres)
        else:
            cierres = load_cierres(args.cierres) if args.cierres else None
            cierres_error = None
        if args.sin_cortes:
            cortes, cortes_error = None, None
        else:
            cortes, cortes_error = load_cortes_degrading(args.mongo_url, args.db)
        sales = open_sales_collection(args.mongo_url, args.db)
        db_name = args.db or os.environ.get("DB_NAME")
        model = build_model(sales.find({}, {"_id": 0}), title=args.title,
                            db_name=db_name, apertura=apertura,
                            apertura_error=apertura_error, cierres=cierres,
                            cierres_error=cierres_error, cortes=cortes,
                            cortes_error=cortes_error)
    except DashboardError as exc:
        print(f"ERROR: {exc}")
        return 1
    if apertura_error:
        print(f"AVISO panel de apertura omitido: {apertura_error}")
    if cierres_error:
        print(f"AVISO ventanas sin operacion omitidas: {cierres_error}")
    if cortes_error:
        print(f"AVISO cortes de caja no leidos: {cortes_error}"
              "\n        el tablero rotulo piso cada dia sin poder distinguir "
              "«no hay corte» de «no pude preguntar»")

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
        con_corte = brand["totals"]["con_corte"]
        if con_corte["days"]:
            print(f"    con corte ({con_corte['days']} dia(s), "
                  f"{con_corte['first_day']} a {con_corte['last_day']}): "
                  f"${con_corte['total']:,.2f} = tarjeta ${con_corte['gross']:,.2f}"
                  f" + efectivo ${con_corte['cash']:,.2f}")
    cash = model["limits"]["cash"]
    if not cash["consulted"]:
        print("  Piso, no venta del dia: no se leyeron los cortes de caja "
              "(--sin-cortes).")
    elif cash["all_missing"]:
        print("  Piso, no venta del dia: no hay ni un corte capturado, y el "
              "efectivo de la app de Clip no viaja por esta API.")
    elif cash["days_missing"]:
        print(f"  Piso en {cash['days_missing']} dia(s)-marca sin corte; "
              f"{cash['days_covered']} ya traen el total.")
    else:
        print(f"  Los {cash['days_covered']} dia(s)-marca tienen corte: el "
              "total de cada uno es tarjeta + efectivo.")
    cortes_model = model.get("cortes")
    if cortes_model:
        for dup in cortes_model["duplicates"]:
            print(f"  AVISO {dup['cuts']} cortes de ({dup['cafeteria_id']}, "
                  f"{dup['business_date']}, {dup['turno']}): eso duplica venta, "
                  "revisa el indice unico de `cash_cuts`")
        for row in cortes_model["double_counted"]:
            print(f"  AVISO el {row['date']} de {row['brand']} ya trae "
                  f"${row['pos_gross']:,.2f} de efectivo en el bruto: el corte "
                  f"de ${row['cash']:,.2f} NO se sumo encima")
        for row in cortes_model["on_closed_days"]:
            print(f"  AVISO el {row['date']} de {row['brand']} esta declarado "
                  f"sin operacion ({row['window']}) pero tiene corte por "
                  f"${row['cash']:,.2f}")
    cierres_model = model.get("cierres")
    if cierres_model:
        for window in cierres_model["windows"]:
            print(f"  {window['label']}: {window['brand']} {window['from']} "
                  f"-> {window['to']} ({window['days']} dias, hueco)")
        for conflict in cierres_model["conflicts"]:
            print(f"  AVISO el {conflict['date']} esta declarado sin operacion "
                  f"({conflict['window']}) pero {conflict['brand']} trae "
                  f"{conflict['tickets']} cobro(s) por ${conflict['gross']:,.2f}: "
                  "se dibuja el cobro, no el hueco")
        for window in cierres_model["unknown_brands"]:
            print(f"  AVISO la ventana {window['from']}..{window['to']} es de "
                  f"`{window['brand']}`, que no existe en esta base: no tapa nada")

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
  /* Un monto al que le falta el efectivo del dia. El subrayado punteado existe
     para que el numero no se pueda leer como el total: en una columna de
     cifras, la de un dia con corte y la de uno sin corte son la misma tinta. */
  .floor { border-bottom: 1px dotted var(--text-muted); }
  .floor-mark { color: var(--text-muted); font-size: 11px; }

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
    <p class="hint" id="checks-hint"></p>
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
    sin_cobro:     { ico: "\u2014", text: "sin cobro con tarjeta" },
    // Declarado sin operacion: no es un cero medido ni un dato que falta, es un
    // dia en que la sucursal no abrio. Glifo propio porque los otros cuatro ya
    // significan otra cosa.
    sin_operacion: { ico: "\u2298", text: "sin operacion" }
  };

  // El estado del **efectivo** de ese dia, por marca. Es una columna aparte de
  // la de arriba a proposito: el estado del dia es uno para todo el eje, y un
  // corte de Casa Dorelia no completa el dia de Le Pain Dore. Igual que STATES,
  // nombra el hueco con una palabra en vez de dibujar un cero.
  var CASH = {
    con_corte: { text: "con corte" },
    sin_corte: { text: "sin corte" },
    // El efectivo ya venia dentro del bruto (un renglon del punto de venta), asi
    // que el corte no se sumo encima: habria contado el mismo peso dos veces.
    doble:     { text: "ya en el bruto" }
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
      return byDay[d] ||
        { date: d, gross: null, tickets: null, avg_ticket: null, closed: null,
          cash: null, cash_state: null, gross_total: null };
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
        // Un hueco declarado dice por que esta vacio. "sin dato" sobre un cierre
        // conocido invita a suponer que la carga fallo.
        row.appendChild(el("span", "num", p.value !== null ? opts.valueFormat(p.value)
          : (p.closed || "sin dato")));
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
      // El numero grande es el total del dia cuando hay corte, y la tarjeta
      // sola cuando no. Lo que nunca pasa es que cambie de significado sin
      // decirlo: el renglon de abajo dice de que esta hecho, porque el dia que
      // entre el primer corte el numero sube y se leeria como un salto de venta.
      var completo = cur.gross_total !== null && cur.gross_total !== undefined;
      tile.appendChild(el("div", "value",
        MXN0.format(completo ? cur.gross_total : cur.gross)));
      tile.appendChild(el("div", "meta",
        NUM.format(cur.tickets) + " cobros · ticket " + money(cur.avg_ticket) +
        " · " + st.text));
      if (M.limits.cash.consulted) {
        tile.appendChild(el("div", "meta", completo
          ? "total del dia: tarjeta " + money(cur.gross) + " + efectivo " +
            money(cur.cash) + " del corte"
          : (cur.cash_state === "doble"
              ? "el efectivo de ese dia ya venia en el bruto: el corte no se sumo"
              : "piso: ese dia no tiene corte, asi que le falta el efectivo")));
      }
      if (prev) {
        // La comparacion se queda en tarjeta contra tarjeta. Un dia con corte
        // contra uno sin corte no es una subida de venta, es una subida de lo
        // que se alcanza a medir, y seria el error mas caro de esta tarjeta.
        var delta = prev.gross > 0 ? (cur.gross - prev.gross) / prev.gross : null;
        var base = M.limits.cash.days_covered ? "% en tarjeta vs " : "% vs ";
        var txt = delta === null ? "sin base de comparacion"
          : (delta >= 0 ? "+" : "") + (delta * 100).toFixed(1) + base + shortDay(prev.date);
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
    // Con cortes en la base la primera columna de cada marca deja de ser "el
    // bruto con tarjeta" y pasa a ser "el total del dia", que en los dias sin
    // corte sigue siendo solo tarjeta. Esa diferencia es la que la columna de
    // efectivo nombra dia por dia, en vez de un rotulo arriba para todos.
    var cashCol = M.limits.cash.consulted;
    var cap = el("caption",
      null,
      (cashCol
        ? "Total del dia (tarjeta + efectivo del corte) y numero de cobros con " +
          "tarjeta, por dia de operacion (UTC-6). La cifra subrayada con puntos " +
          "es un piso: ese dia no tiene corte, asi que le falta el efectivo. "
        : "Bruto con tarjeta y numero de cobros por dia de operacion (UTC-6). ") +
      "«0» es un dia que paso sin cobro con tarjeta; «—» es que no hay dato " +
      "(la marca no operaba aun, o el dia todavia no pasa); «sin operacion» es " +
      "un dia declarado cerrado, que no es lo mismo que un cero.");
    table.appendChild(cap);

    var thead = el("thead");
    var hr = el("tr");
    hr.appendChild(el("th", null, "Dia"));
    hr.appendChild(el("th", null, "Estado"));
    brands.forEach(function (b) {
      hr.appendChild(el("th", null, b.name + (cashCol ? " · total" : " · bruto")));
      if (cashCol) { hr.appendChild(el("th", null, "efectivo")); }
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
        // Tres huecos distintos en la misma celda, y cada uno dice cual es: el
        // dia que no ha pasado, el cierre declarado, y el "no hay dato" de antes
        // de que la marca existiera. Un «—» para los tres los hace iguales.
        var hueco = p.closed ? p.closed : (running ? "aun sin cobro" : null);
        // El total del dia cuando el corte ya entro; la tarjeta sola cuando no,
        // y entonces marcada como piso. El numero nunca se infla: lo que cambia
        // es de que esta hecho, y eso se lee en la celda de al lado.
        var completo = p.gross_total !== null && p.gross_total !== undefined;
        var shown = completo ? p.gross_total : p.gross;
        var floor = cashCol && !completo && p.gross !== null &&
          p.cash_state === "sin_corte";
        var c1 = el("td", p.gross === null ? "nodata" : (floor ? "floor" : null),
          p.gross === null && hueco ? hueco : money(shown));
        if (floor) { c1.title = "piso: falta el efectivo de ese dia (sin corte)"; }
        tr.appendChild(c1);
        if (cashCol) {
          // Hueco, no cero: un dia sin corte no es un dia sin efectivo. Y un
          // corte en cero si es un cero medido, que es lo que vuelve citable el
          // total de ese dia — por eso se dibuja la cifra, aunque sea 0.00.
          var lab = CASH[p.cash_state];
          var cd = el("td", p.cash === null ? "nodata" : null,
            p.cash === null ? (lab ? lab.text : "—") : money(p.cash));
          if (p.cash !== null && (p.cash_late || p.cash_revised)) {
            // Ese numero se recordo o se corrigio: no se conto al cerrar el
            // cajon. Va pegado a la cifra, no en una nota al pie.
            cd.appendChild(el("span", "floor-mark",
              p.cash_late && p.cash_revised ? " tarde, corregido"
                : (p.cash_late ? " tarde" : " corregido")));
          }
          if (p.cash !== null && p.cash_state === "doble") {
            cd.appendChild(el("span", "floor-mark", " ya en el bruto"));
          }
          tr.appendChild(cd);
        }
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
    // El total del rango se queda en **tarjeta**, a proposito, y lo dice. Sumar
    // el efectivo que haya contra el bruto de todos los dias daria una cifra
    // mitad completa y mitad piso: no se podria citar ni como una cosa ni como
    // la otra, y la columna no tiene donde decirlo. El total que si se puede
    // citar —los dias con corte— va en la tarjeta de cada marca.
    fr.appendChild(el("td", null, cashCol ? "Total del rango (tarjeta)"
                                          : "Total del rango"));
    fr.appendChild(el("td", null, ""));
    sliced.forEach(function (pts) {
      var g = 0, n = 0, c = 0, dias = 0;
      pts.forEach(function (p) {
        if (p.gross !== null) { g += p.gross; n += p.tickets; }
        if (p.cash !== null && p.cash_state === "con_corte") { c += p.cash; dias++; }
      });
      fr.appendChild(el("td", null, MXN.format(g)));
      if (cashCol) {
        fr.appendChild(el("td", dias ? null : "nodata",
          dias ? MXN.format(c) + " (" + NUM.format(dias) + " d)" : "sin corte"));
      }
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

    function stat(host, value, label, warn) {
      var box = el("div");
      box.appendChild(el("div", "open-num" + (warn ? " warn" : ""), value));
      box.appendChild(el("div", "open-lab", label));
      host.appendChild(box);
    }
    var head = document.getElementById("apertura-head");
    head.textContent = "";
    stat(head, NUM.format(A.blockers.length), "bloqueantes de apertura abiertos",
      A.blockers.length > 0);
    stat(head, NUM.format(A.source.pending) + " de " + NUM.format(A.source.rows),
      "renglones «Pendiente» en la hoja de seguimiento", false);
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
      li.appendChild(what);
      return li;
    }

    var blockers = document.getElementById("apertura-blockers");
    blockers.textContent = "";
    A.blockers.forEach(function (b) { blockers.appendChild(row(b, true)); });

    var rest = document.getElementById("apertura-rest");
    var others = (A.pending_rows || []).filter(function (p) {
      return !A.blockers.some(function (b) { return String(b.ref) === String(p.ref); });
    });
    if (!others.length) { rest.hidden = true; return; }
    rest.hidden = false;
    // El conteo va en el rotulo, calculado: una lista recortada no puede
    // quedarse con un numero viejo escrito en el JSON.
    document.getElementById("apertura-rest-title").textContent =
      (A.pending_title || "El resto de los pendientes") +
      " (" + NUM.format(others.length) + ")";
    document.getElementById("apertura-rest-hint").textContent = A.pending_hint || "";
    var list = document.getElementById("apertura-pending");
    list.textContent = "";
    others.forEach(function (p) { list.appendChild(row(p, false)); });
  }

  function renderChecks() {
    var host = document.getElementById("checks");
    host.textContent = "";
    // El conteo se cuenta, no se escribe: decia "los cinco" y el dia que entro
    // un sexto control el rotulo se quedo mintiendo sobre su propia lista.
    document.getElementById("checks-hint").textContent =
      "Se cuentan sobre toda la base en cada generacion, no sobre el rango " +
      "filtrado. Los " + NUM.format(M.quality.checks.length) +
      " deben estar en cero.";
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
    // El rotulo del efectivo sale de los conteos por dia-marca, no de un
    // booleano para todo el eje. Son cuatro frases porque son cuatro estados
    // distintos del dato, y el dia que cambie el conteo cambia la frase sola.
    var CH = L.cash;
    if (!CH.consulted) {
      items.push(["No dice la venta del dia: no se leyeron los cortes de caja. ",
        "Lo cargado es lo que cobro la terminal de Clip: " + mix + ". El efectivo " +
        "que la app de Clip registra aparte NO viaja por esta API, y este tablero " +
        "se genero sin preguntarle a `cash_cuts`, asi que cada monto es un piso."]);
    } else if (CH.all_missing) {
      items.push(["No dice la venta del dia, y el faltante no es chico. ",
        "Lo cargado es lo que cobro la terminal de Clip: " + mix + ". El efectivo " +
        "que la app de Clip registra aparte NO viaja por esta API: son entre 6 y 20 " +
        "cobros al dia por sucursal que no estan aqui (confirmado con Gustavo el " +
        "04/10). No hay ni un corte de caja capturado todavia, asi que cada monto " +
        "es un piso y la venta real es ese numero mas la caja."]);
    } else if (CH.days_missing) {
      items.push(["El total es completo en los dias con corte, y piso en los demas. ",
        NUM.format(CH.days_covered) + " dia(s)-marca tienen corte de caja (del " +
        shortDay(CH.first_covered_day) + " al " + shortDay(CH.last_covered_day) +
        ") y su total es tarjeta + efectivo contado. Los otros " +
        NUM.format(CH.days_missing) + " siguen siendo piso, y la tabla lo dice " +
        "dia por dia («sin corte», y la cifra subrayada con puntos). Por eso el " +
        "total del rango se queda en tarjeta: una suma mitad completa y mitad " +
        "piso no se puede citar."]);
    } else {
      items.push(["Todos los dias tienen corte: el total es la venta, no un piso. ",
        NUM.format(CH.days_covered) + " dia(s)-marca con corte de caja. " + mix +
        ", mas el efectivo contado de cada dia. Un dia que pierda su corte vuelve " +
        "a decir «sin corte» solo, sin que nadie edite este texto."]);
    }
    if (CH.late_cuts || CH.revised_cuts) {
      items.push(["Hay efectivo que se recordo o se corrigio. ",
        (CH.late_cuts ? NUM.format(CH.late_cuts) + " corte(s) se capturaron " +
          "dias despues del cierre, asi que ese numero salio de la memoria y no " +
          "del cajon. " : "") +
        (CH.revised_cuts ? NUM.format(CH.revised_cuts) + " corte(s) se " +
          "corrigieron despues de guardarse (el valor anterior y la razon quedan " +
          "en el documento). " : "") +
        "Las celdas afectadas van marcadas; cuenta igual que el resto, pero no se " +
        "cita igual."]);
    }
    var CO = M.cortes;
    if (CO && CO.duplicates.length) {
      items.push(["Un turno tiene mas de un corte, y eso duplica venta. ",
        CO.duplicates.map(function (d) {
          return d.cafeteria_id + " " + shortDay(d.business_date) + " turno " +
            d.turno + ": " + NUM.format(d.cuts) + " cortes";
        }).join("; ") + ". El indice unico de `cash_cuts` deberia hacerlo " +
        "imposible, asi que esto es una base sin indice o una carga a mano."]);
    }
    if (CO && CO.double_counted.length) {
      items.push(["Un dia trae el efectivo dos veces, y solo se conto una. ",
        CO.double_counted.map(function (d) {
          var b = M.brands.filter(function (x) { return x.brand === d.brand; })[0];
          return shortDay(d.date) + " " + (b ? b.name : d.brand) + ": el bruto ya " +
            "trae " + money(d.pos_gross) + " de efectivo en " +
            NUM.format(d.pos_tickets) + " cobro(s), y el corte dice " + money(d.cash);
        }).join("; ") + ". Gana el bruto, que tiene el cobro renglon por renglon: " +
        "el corte NO se sumo encima. Hay que decidir cual de las dos capturas es " +
        "la buena antes de leer esos dias."]);
    }
    if (CO && CO.on_closed_days.length) {
      items.push(["Hay corte de caja en un dia declarado sin operacion. ",
        CO.on_closed_days.map(function (d) {
          var b = M.brands.filter(function (x) { return x.brand === d.brand; })[0];
          return shortDay(d.date) + " " + (b ? b.name : d.brand) + ": " +
            money(d.cash) + " dentro de " + d.window;
        }).join("; ") + ". Las dos cosas no pueden ser ciertas: o la sucursal si " +
        "opero, o el corte es de otro dia. El efectivo se dibuja igual — un " +
        "archivo de configuracion no borra dinero."]);
    }
    if (M.cortes_error) {
      items.push(["No se pudieron leer los cortes de caja. ",
        "Los dias de abajo dicen «sin corte», pero eso no quiere decir que no " +
        "haya: quiere decir que no se pudo preguntar. Falta por esto: " +
        M.cortes_error]);
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

    // Los huecos declarados se rotulan con su fuente. Un hueco sin dueño no se
    // puede distinguir de un hueco inventado, y este es el unico limite del
    // tablero que no sale del dato sino de una determinacion operativa.
    var C = M.cierres;
    if (C && C.windows.length) {
      var spans = C.windows.map(function (w) {
        var b = M.brands.filter(function (x) { return x.brand === w.brand; })[0];
        return (b ? b.name : w.brand) + " " + shortDay(w.from) + " a " +
          shortDay(w.to) + " (" + NUM.format(w.days) + " dias)";
      }).join("; ");
      items.push(["Los dias sin operacion no son ceros, y no salen del dato. ",
        spans + ". Esos dias se dibujan como hueco por determinacion operativa (" +
        C.source + "), no porque la carga no haya traido nada: sin ese rotulo el " +
        "tablero afirmaria que la sucursal abrio y vendio $0 una vez por dia. Lo " +
        "que si sale del dato es que no falta efectivo ahi."]);
      if (C.conflicts.length) {
        items.push(["Una ventana declarada no cuadra con la venta. ",
          C.conflicts.map(function (c) {
            var b = M.brands.filter(function (x) { return x.brand === c.brand; })[0];
            return shortDay(c.date) + ": " + (b ? b.name : c.brand) + " cobro " +
              money(c.gross) + " en " + NUM.format(c.tickets) + " cobro(s) dentro de " +
              c.window;
          }).join("; ") + ". Se dibuja el cobro, no el hueco: un archivo de " +
          "configuracion no puede borrar venta. Hay que corregir las fechas."]);
      }
      if (C.unknown_brands.length) {
        items.push(["Una ventana declarada no tapa nada. ",
          C.unknown_brands.map(function (w) {
            return w.brand + " " + w.from + ".." + w.to;
          }).join("; ") + ": esa marca no existe en esta base, asi que la ventana " +
          "no se aplico. Casi siempre es un slug mal escrito."]);
      }
    } else if (M.cierres_error) {
      items.push(["Las ventanas sin operacion no se pudieron leer. ",
        "Los dias cerrados de abajo estan dibujados como ceros medidos, o sea " +
        "que el tablero esta afirmando que la sucursal abrio y vendio $0 en cada " +
        "uno. Falta por esto: " + M.cierres_error]);
    }

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

    // El rotulo de arriba de todo tambien se calcula de los conteos por
    // dia-marca. Un "no es la venta del dia" escrito para todo el eje seguia
    // siendo falso en los dias que ya tenian corte, y nadie lo habria movido.
    var CH = M.limits.cash;
    var note = document.getElementById("floor-note");
    note.textContent = "";
    if (!CH.consulted || CH.all_missing) {
      note.appendChild(el("strong", null,
        "Todo lo de aqui lo cobro la terminal de Clip, no es la venta del dia. "));
      note.appendChild(el("span", null,
        "Tarjeta y vales si; el efectivo que la app de Clip registra aparte no " +
        "viaja por esta API, y " + (CH.consulted
          ? "no hay ningun corte de caja capturado todavia"
          : "este tablero se genero sin leer los cortes de caja") +
        ", asi que cada cifra es un piso. "));
    } else if (CH.days_missing) {
      note.appendChild(el("strong", null,
        "El total es la venta del dia en " + NUM.format(CH.days_covered) +
        " dia(s)-marca, y un piso en los otros " + NUM.format(CH.days_missing) +
        ". "));
      note.appendChild(el("span", null,
        "Un dia con corte de caja trae tarjeta + efectivo contado; uno sin corte " +
        "le falta el efectivo, que no viaja por la API de Clip. La tabla dice cual " +
        "es cual, dia por dia. "));
    } else {
      note.appendChild(el("strong", null,
        "Esto ya es la venta del dia, no un piso: los " +
        NUM.format(CH.days_covered) + " dia(s)-marca tienen corte de caja. "));
      note.appendChild(el("span", null,
        "Cada total es tarjeta + efectivo contado al cerrar el cajon. "));
    }
    note.appendChild(el("span", null,
      "Y esta base guarda dos marcas con repartos distintos: se leen por renglon, " +
      "nunca sumadas."));

    var hint = document.getElementById("gross-hint");
    // La linea se queda en tarjeta incluso cuando ya hay cortes. Una linea
    // mitad tarjeta y mitad total daria un escalon el dia del primer corte que
    // se leeria como un salto de venta, y ninguna grafica tiene donde explicar
    // eso. El total por dia vive en la tabla, que si puede decirlo celda a celda.
    hint.textContent = (M.limits.cash.days_covered
      ? "La linea es el cobro con tarjeta, tambien en los dias que ya tienen " +
        "corte: mezclarla con el efectivo daria un escalon el dia del primer " +
        "corte que se leeria como un salto de venta. El total del dia esta en " +
        "la tabla. "
      : "") +
      "Dia de operacion en hora del negocio (UTC-6), no dia UTC: " +
      "una venta de las 18:00 locales cae en el dia UTC siguiente. " +
      "La linea baja a cero en un dia que paso sin cobro, y se corta donde no hay " +
      "dato: antes del primer dia de la marca, en el dia en curso mientras no " +
      "entre el primer cobro, y en los dias declarados sin operacion. Ninguno de " +
      "esos huecos es una caida de venta; la tabla dice cual es cada uno («en " +
      "curso», «sin operacion»)." +
      (M.cierres && M.cierres.windows.length
        ? " Las ventanas sin operacion vienen de " + M.cierres.source + "."
        : "");
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
          return { date: p.date, value: p.gross, closed: p.closed || null };
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
          return { date: p.date, value: p.avg_ticket, closed: p.closed || null };
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
