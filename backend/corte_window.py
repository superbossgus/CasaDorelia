"""Decide si un corte puede publicar la cifra de un dia como **total** o solo como parcial.

Para que existe: el reporte de apertura (BOS-38) tiene tres cortes al dia (08:00,
15:00 y 20:00 CDMX) y la carga de Clip tiene dos slots (07:45 y 19:45, BOS-99).
Hasta hoy el corte de las 08:00 escribia «no observable» para la venta del dia en
curso y eso salia bien **por accidente**: a las 07:45 la sucursal no habia cobrado
todavia, asi que no habia renglones y no habia nada que publicar. El accidente se
esta acabando — la apertura de SJI se adelanto de 12:52 (30/09/2026) a 08:25
(06/10/2026) — y el dia que un cobro caiga antes de las 07:45 ese mismo corte va a
encontrar renglones y va a publicar **una cifra de los primeros minutos del dia
como si fuera la venta del dia**. Eso es peor que no publicar nada: «no
observable» es honesto, un numero truncado no.

### La regla, y por que no es una hora de apertura

La tentacion es comparar contra el record de apertura ("si el primer cobro es
despues de las 07:45 no hay problema"). Ese numero **caduca**: el record de 09:16
duro cinco dias y lo rompio el 08:25 del 06/10. La regla de aqui no lo usa. Es
estructural y no puede caducar:

> Una cifra del dia `D` solo es citable como total si **alguna carga pidio `D`
> despues de que `D` cerro**. Una carga que corre a las 07:45 —o a las 19:45— esta
> parada *dentro* de `D`: por definicion no vio el resto del dia, exista o no un
> cobro temprano.

De ahi sale, sin ninguna hora de apertura, que el unico corte que puede hablar de
un dia cerrado es el de las **08:00 del dia siguiente** (su carga de las 07:45
vuelve a pedir el dia anterior completo con `--catch-up 1`). Los cortes de las
08:00, 15:00 y 20:00 del propio dia solo pueden publicar parciales.

### Rotular, no rellenar

Un parcial se publica **con su hora de corte** y sin completar lo que falta. Este
modulo no estima, no proyecta y no anualiza: devuelve el estado, la hora hasta la
que la cifra responde, y cuanto dia quedo afuera.

### Cinco estados, y por que el conteo de renglones no basta

`clasificar_dia` no acepta "cuantos renglones hay" como unica evidencia, porque un
dia sin cobros **no escribe renglones**: la ausencia de filas se ve igual que un
cargador muerto. La corrida se cita aparte (`carga_at`, del registro de la
corrida) y la falta de esa cita es un estado propio, no un supuesto:

| estado | que significa | citable como total |
|---|---|---|
| `sin_evidencia` | cero renglones y nadie cito la corrida del cargador: no se puede distinguir «no cobro» de «no corrio» | no |
| `sin_carga` | la corrida citada es anterior al inicio del dia: ninguna carga alcanzo ese dia | no |
| `sin_cifra` | la carga alcanzo el dia y no trajo renglones: «no observable todavia» | no (no hay cifra) |
| `parcial` | hay renglones, pero la cobertura termina antes de que cerrara el dia | no, **rotulado parcial + hora** |
| `final` | la cobertura llega al cierre del dia: bruto del dia con tarjeta | si |

`final` con cero renglones es un cero **medido** (dia cerrado o sin cobro con
tarjeta), no un hueco: eso es lo que lo separa de `sin_cifra`.

### Que eje NO mide

Solo el reloj: si la cifra responde por el dia completo. **No** dice si la cifra
incluye efectivo — ese es otro eje, y vive en `cash_cut.py` / `dashboard.py`. Una
cifra `final` sigue siendo *piso* mientras no haya corte de caja. Los dos rotulos
son independientes y los dos tienen que ir en el reporte.

### Correrlo

    # lo que el corte de las 08:00 necesita: ayer (cerrado) y hoy (en curso)
    python backend/corte_window.py --db casa_dorelia --branch sji \
        --carga-at 2026-10-07T13:45:57+00:00

    # un dia suelto, en JSON para pegarlo en el reporte
    python backend/corte_window.py --db casa_dorelia --branch sji --day 2026-10-06 --json

Solo lee: no escribe una sola linea en Mongo.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from branches_init import GROUP_BRANCHES
from business_day import BUSINESS_TZ, business_date

DEFAULT_MONGO_URL = "mongodb://127.0.0.1:27017"

# Los dos slots de la rutina de carga (`03f5e143`, BOS-99), en hora del negocio.
# Viven aqui como documentacion de por que la regla da lo que da; el calculo NO
# los usa — usa la hora real de la corrida que le citan, para que el dia que la
# rutina cambie de horario la regla siga siendo cierta sin tocar este archivo.
LOAD_SLOTS_LOCAL = ("07:45", "19:45")

# Cuantos dias de operacion hacia atras pide la corrida de la mañana
# (`clip_daily.py --catch-up 1`). Es lo que permite que la carga de las 07:45
# cierre el dia anterior. Si una corrida citada es mas vieja que esto respecto al
# dia preguntado, esa corrida **no pidio** ese dia y no puede cerrarlo.
CATCHUP_DAYS = 1

SIN_EVIDENCIA = "sin_evidencia"
SIN_CARGA = "sin_carga"
SIN_CIFRA = "sin_cifra"
PARCIAL = "parcial"
FINAL = "final"

CITABLE_COMO_TOTAL = (FINAL,)


class CorteWindowError(ValueError):
    """Algo impide clasificar la cifra. Siempre dice que falta."""


# --------------------------------------------------------------------------
# Instantes y dias
# --------------------------------------------------------------------------

def _as_aware(value: Any, *, what: str) -> Optional[datetime]:
    """Normaliza a `datetime` con zona. Sin offset se lee como hora del negocio.

    Acepta el ISO con `Z` y el ISO con `+00:00` que es el que escribe
    `sales_import.build_sale_document` en `imported_at`.
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
        except ValueError as exc:
            raise CorteWindowError(f"{what} no es una fecha ISO-8601: {value!r}") from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=BUSINESS_TZ)
    return moment


def day_bounds(day: str) -> tuple:
    """Inicio y fin de un dia de operacion, como instantes con zona.

    El fin es **exclusivo** (00:00 del dia siguiente) a proposito: la pregunta no
    es "¿la carga corrio a las 23:59:59?" sino "¿la carga corrio cuando el dia ya
    no podia crecer?", y el unico instante que garantiza eso es el arranque del
    dia siguiente.
    """
    try:
        first = date.fromisoformat(day)
    except (TypeError, ValueError) as exc:
        raise CorteWindowError(f"no es un dia de operacion `YYYY-MM-DD`: {day!r}") from exc
    start = datetime(first.year, first.month, first.day, tzinfo=BUSINESS_TZ)
    return start, start + timedelta(days=1)


def local_hhmm(moment: datetime) -> str:
    """`HH:MM` en hora del negocio. Es el rotulo que ve quien lee el reporte."""
    return moment.astimezone(BUSINESS_TZ).strftime("%H:%M")


def _spanish_gap(delta: timedelta) -> str:
    """"5 h 15 min" — lo que del dia quedo afuera de la cobertura.

    Redondea **hacia arriba**. Es un hueco, no un saldo: truncar los segundos
    reportaria menos dia sin medir del que de verdad quedo sin medir, y el sesgo
    de un rotulo de incertidumbre tiene que ir del lado de la duda.
    """
    minutes = max(0, -(-int(delta.total_seconds()) // 60))
    hours, rest = divmod(minutes, 60)
    if hours and rest:
        return f"{hours} h {rest} min"
    if hours:
        return f"{hours} h"
    return f"{rest} min"


def _money(value: Optional[float]) -> str:
    return "—" if value is None else f"${value:,.2f}"


# --------------------------------------------------------------------------
# La regla
# --------------------------------------------------------------------------

def clasificar_dia(*, day: str, renglones: int = 0, bruto: Optional[float] = None,
                   carga_at: Any = None, ultimo_imported_at: Any = None,
                   catchup_days: int = CATCHUP_DAYS,
                   etiqueta: Optional[str] = None) -> Dict[str, Any]:
    """Estado de la cifra de `day`: ¿hasta que hora responde, y es citable como total?

    - `renglones` / `bruto`: lo que hay en la base para ese dia y esa sucursal.
    - `carga_at`: instante de la corrida del cargador, **del registro de la
      corrida** (la tarea de la rutina). Es la evidencia buena: una corrida que
      inserta cero no deja rastro en `sales`, asi que la ausencia de renglones
      nunca prueba que la carga no corrio.
    - `ultimo_imported_at`: `max(imported_at)` de los renglones de ese dia. Es una
      **cota inferior** de la cobertura: prueba que algo se escribio a esa hora,
      no que no haya corrido nada despues.

    Nunca estima ni completa el dia: devuelve el estado, la hora de corte y el
    hueco que queda afuera.
    """
    start, end = day_bounds(day)
    corrida = _as_aware(carga_at, what="`carga_at`")
    escrito = _as_aware(ultimo_imported_at, what="`ultimo_imported_at`")

    # Una corrida solo puede cerrar los dias que pidio. La de la mañana pide el
    # dia en curso y `catchup_days` hacia atras; mas viejo que eso, esa corrida no
    # habla de este dia y se descarta como evidencia de cobertura.
    fuera_de_alcance = False
    if corrida is not None:
        mas_viejo = (date.fromisoformat(business_date(corrida))
                     - timedelta(days=max(0, catchup_days))).isoformat()
        if day < mas_viejo:
            fuera_de_alcance = True
            corrida = None

    # La cobertura es el instante mas tardio que se puede probar. `escrito` cuenta
    # porque un renglon escrito a las 01:46Z prueba que una carga estaba viva
    # entonces, aunque nadie haya citado la corrida.
    cobertura = max([m for m in (corrida, escrito) if m is not None], default=None)

    if cobertura is None:
        estado = SIN_EVIDENCIA
    elif cobertura >= end:
        estado = FINAL
    elif cobertura < start:
        # La unica corrida que se conoce es anterior al dia: ninguna carga lo
        # alcanzo. Con `renglones > 0` esto no puede pasar (un renglon del dia se
        # escribio despues de que el dia empezo), asi que esto es siempre el caso
        # "cero renglones y el cargador no llego".
        estado = SIN_CARGA
    elif renglones > 0:
        estado = PARCIAL
    else:
        estado = SIN_CIFRA

    corte_local = local_hhmm(cobertura) if cobertura is not None else None
    falta = (end - cobertura) if (cobertura is not None and cobertura < end) else timedelta(0)

    out: Dict[str, Any] = {
        "business_date": day,
        "etiqueta": etiqueta,
        "estado": estado,
        "citable_como_total": estado in CITABLE_COMO_TOTAL,
        "renglones": renglones,
        "bruto": bruto,
        "cobertura_hasta": cobertura.isoformat() if cobertura is not None else None,
        "cobertura_hasta_local": corte_local,
        "cierra_el_dia": end.isoformat(),
        "falta_del_dia": _spanish_gap(falta) if falta else None,
        "corrida_citada": corrida.isoformat() if corrida is not None else None,
        "corrida_fuera_de_alcance": fuera_de_alcance,
        # Siempre: la API de Clip no entrega efectivo. Este eje no lo resuelve.
        "incluye_efectivo": False,
    }
    out["rotulo"] = rotulo(out)
    return out


def rotulo(verdict: Mapping[str, Any]) -> str:
    """La frase que va al reporte, en es-MX. Nunca dice «venta del dia» en un parcial."""
    estado = verdict["estado"]
    day = verdict["business_date"]
    quien = verdict.get("etiqueta") or "la sucursal"
    corte = verdict.get("cobertura_hasta_local")
    falta = verdict.get("falta_del_dia")
    monto = _money(verdict.get("bruto"))
    renglones = verdict.get("renglones") or 0

    if estado == FINAL:
        cuerpo = (f"FINAL — {day} de {quien}: {monto} con tarjeta en {renglones} cobro(s). "
                  f"Citable como bruto del dia: una carga pidio el dia despues de que cerro "
                  f"(cobertura hasta {corte} CDMX).")
    elif estado == PARCIAL:
        cuerpo = (f"PARCIAL — {day} de {quien}: {monto} con tarjeta en {renglones} cobro(s) "
                  f"**cortados a las {corte} CDMX**. No es la venta del dia: la carga que los "
                  f"trajo corrio dentro del dia y quedan {falta} de servicio sin medir.")
    elif estado == SIN_CIFRA:
        cuerpo = (f"SIN CIFRA — {day} de {quien}: la carga corrio ({corte} CDMX) y no encontro "
                  f"cobros del dia en curso. No observable todavia; faltan {falta} del dia.")
    elif estado == SIN_CARGA:
        cuerpo = (f"SIN CARGA — {day} de {quien}: la corrida mas reciente que se conoce es de "
                  f"antes de que empezara el dia ({corte} CDMX). No hay cifra porque no corrio "
                  f"la carga, no porque no se haya cobrado.")
    else:
        cuerpo = (f"SIN EVIDENCIA — {day} de {quien}: cero renglones y sin citar la corrida del "
                  f"cargador. Cero renglones no distingue «no cobro» de «no corrio»: hay que "
                  f"citar la corrida (`--carga-at` / la tarea de la rutina) antes de publicar.")

    return cuerpo + " El monto es piso: la API de Clip no entrega efectivo."


# --------------------------------------------------------------------------
# Lectura de la base (lo unico que toca Mongo)
# --------------------------------------------------------------------------

def leer_dia(sales: Any, *, day: str, clip_branch: str,
             cafeteria_id: Optional[str] = None) -> Dict[str, Any]:
    """Renglones, bruto y `max(imported_at)` de un dia y una sucursal.

    Filtra por `clip_branch` (`sji` / `tecnoparque`), que es el separador de
    **sucursal**. `brand` no sirve para esto: separa las dos marcas
    (`casa-dorelia` / `le-pain-dore`) y filtrar por ahi devuelve cero renglones en
    silencio, que se lee exactamente igual que «no cobro».

    `cafeteria_id` no filtra: se cuenta aparte como **control**. Si los dos
    conteos no coinciden hay renglones sin `clip_branch` (carga vieja) y el
    resultado lo dice en vez de publicar un conteo corto.
    """
    rows = list(sales.find({"clip_branch": clip_branch, "business_date": day}))
    bruto = round(sum(float(r.get("total") or 0.0) for r in rows), 2)
    imports = [_as_aware(r.get("imported_at"), what="`imported_at`") for r in rows]
    ultimo = max([m for m in imports if m is not None], default=None)

    control: Optional[int] = None
    if cafeteria_id:
        counter = getattr(sales, "count_documents", None)
        if counter is not None:
            control = counter({"cafeteria_id": cafeteria_id, "business_date": day})

    return {
        "renglones": len(rows),
        "bruto": bruto if rows else 0.0,
        "ultimo_imported_at": ultimo.isoformat() if ultimo is not None else None,
        "control_por_cafeteria": control,
        "descuadre_de_control": control is not None and control != len(rows),
    }


def dias_del_corte(*, now: Optional[datetime] = None, count: int = 2) -> List[str]:
    """Los dias que un corte tiene que rotular: el en curso y los previos.

    `count=2` es lo que necesita el corte de las 08:00 — ayer (que su carga de las
    07:45 acaba de cerrar) y hoy (que apenas empieza).
    """
    if count <= 0:
        return []
    hoy = date.fromisoformat(business_date(now or datetime.now(timezone.utc)))
    return [(hoy - timedelta(days=back)).isoformat() for back in range(count - 1, -1, -1)]


def correr(sales: Any, *, clip_branch: str, days: Sequence[str],
           carga_at: Any = None, cafeteria_id: Optional[str] = None,
           etiqueta: Optional[str] = None) -> Dict[str, Any]:
    """Clasifica varios dias de una sucursal. Es lo que imprime la linea de comandos."""
    out: List[Dict[str, Any]] = []
    for day in days:
        leido = leer_dia(sales, day=day, clip_branch=clip_branch, cafeteria_id=cafeteria_id)
        verdict = clasificar_dia(
            day=day,
            renglones=leido["renglones"],
            bruto=leido["bruto"],
            carga_at=carga_at,
            ultimo_imported_at=leido["ultimo_imported_at"],
            etiqueta=etiqueta,
        )
        verdict["control_por_cafeteria"] = leido["control_por_cafeteria"]
        verdict["descuadre_de_control"] = leido["descuadre_de_control"]
        out.append(verdict)
    return {
        "clip_branch": clip_branch,
        "cafeteria_id": cafeteria_id,
        "corrida_citada": str(carga_at) if carga_at is not None else None,
        "dias": out,
        # El corte solo puede hablar de un dia cerrado si algun dia salio `final`.
        "dias_citables": [d["business_date"] for d in out if d["citable_como_total"]],
    }


# --------------------------------------------------------------------------
# Linea de comandos
# --------------------------------------------------------------------------

def _branch_meta(clip_branch: str) -> Dict[str, Any]:
    for branch in GROUP_BRANCHES:
        if branch.get("clip_branch") == clip_branch:
            return branch
    raise CorteWindowError(
        f"sucursal de Clip desconocida: {clip_branch!r}. "
        f"Las que hay: {', '.join(str(b.get('clip_branch')) for b in GROUP_BRANCHES)}"
    )


def open_sales_collection(mongo_url: Optional[str] = None, db_name: Optional[str] = None) -> Any:
    try:
        from pymongo import MongoClient
    except ImportError as exc:  # pragma: no cover - depende de la maquina
        raise CorteWindowError("falta `pymongo`: pip install pymongo") from exc
    url = mongo_url or os.environ.get("MONGO_URL") or DEFAULT_MONGO_URL
    name = db_name or os.environ.get("DB_NAME")
    if not name:
        raise CorteWindowError("falta la base: usa --db o define DB_NAME")
    return MongoClient(url, serverSelectionTimeoutMS=5000)[name]["sales"]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="corte_window",
        description="¿La cifra de este dia es citable como total, o es un parcial? Solo lee.",
    )
    parser.add_argument("--branch", default="sji", help="sucursal de Clip (sji / tecnoparque)")
    parser.add_argument("--day", default=None, help="un dia de operacion concreto (default: hoy y ayer)")
    parser.add_argument("--days", type=int, default=2, metavar="N",
                        help="cuantos dias rotular, terminando en hoy (default 2; ignorado con --day)")
    parser.add_argument("--carga-at", default=None,
                        help="instante ISO de la corrida del cargador, del registro de la corrida")
    parser.add_argument("--db", default=None, help="base destino (default: $DB_NAME)")
    parser.add_argument("--mongo-url", default=None, help="default: $MONGO_URL o localhost")
    parser.add_argument("--json", action="store_true", help="salida en JSON, para pegarla al reporte")

    args = parser.parse_args(argv)

    try:
        meta = _branch_meta(args.branch)
        days = [args.day] if args.day else dias_del_corte(count=args.days)
        sales = open_sales_collection(args.mongo_url, args.db)
        result = correr(sales, clip_branch=args.branch, days=days, carga_at=args.carga_at,
                        cafeteria_id=meta.get("id"), etiqueta=meta.get("name"))
    except CorteWindowError as exc:
        print(f"ERROR: {exc}")
        return 1

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for verdict in result["dias"]:
            print(verdict["rotulo"])
            if verdict["descuadre_de_control"]:
                print(f"  CONTROL: {verdict['control_por_cafeteria']} renglones por "
                      f"`cafeteria_id` contra {verdict['renglones']} por `clip_branch`. "
                      f"Hay carga vieja sin `clip_branch`; el conteo de arriba va corto.")
        if not result["dias_citables"]:
            print("\nNingun dia de esta ventana es citable como total. "
                  "El unico corte que puede cerrar un dia es el de las 08:00 del dia siguiente.")

    # Codigo 2 cuando no se pudo decidir por falta de evidencia: el corte tiene que
    # citar la corrida en lugar de publicar un supuesto.
    if any(d["estado"] == SIN_EVIDENCIA for d in result["dias"]):
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
