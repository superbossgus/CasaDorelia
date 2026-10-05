"""Corte de caja: la unica fuente del efectivo, porque Clip no lo entrega.

### El problema que resuelve

La carga de Clip (`clip_daily.py`) trae **solo** lo que cobro la terminal. El
efectivo que la app de Clip si registra **no viaja por su API**: el censo de
BOS-119 reviso 2,329 cobros de 360 dias agrupados por `(payment_method,
sub_type, marca, emisor, status)` y encontro **cero** rotulados efectivo, y la
guia de conciliacion de Clip pone el recibo del cobro en efectivo en la app, el
panel, los reportes descargables y el correo — en ningun endpoint. Mientras eso
siga asi, toda cifra del tablero es un **piso**, no la venta del dia.

Este modulo es el otro lado: el corte que captura la sucursal al cerrar. No
depende de Clip, y ademas cuadra contra la caja fisica, que es algo que ninguna
API da.

### El numero no se escribe: se deriva de lo que se cuenta

Pedirle a la cajera "cuanto vendiste en efectivo" es pedirle una resta de
memoria, y esa resta es justo donde se cuelan los errores. Aqui se capturan los
tres numeros que **se pueden contar**:

    ventas_efectivo = efectivo_contado + retiros - fondo_inicial

- `fondo_inicial`: con cuanto abrio la caja.
- `efectivo_contado`: lo que hay en el cajon al cerrar (incluye el fondo).
- `retiros`: lo que salio del cajon durante el dia (depositos, pagos, traslado).

Si esa resta da negativo **no se guarda**: significa que falta un retiro o que el
fondo esta mal, y un negativo publicado restaria venta de un dia que si vendio.

### Lo que este modulo se niega a hacer

1. **No suma marcas.** `casa_dorelia` guarda Casa Dorelia (`c-sji`) y Le Pain
   Dore (`c-tecno`), dos repartos distintos (ver `brands.py`). El efectivo se
   reporta por marca; el total de las dos existe solo como suma de control y con
   el nombre diciendolo.
2. **No confunde "cero efectivo" con "no sabemos".** Un corte con
   `ventas_efectivo: 0.0` es un cero **medido**: ese dia la sucursal abrio y no
   cobro efectivo, asi que el bruto con tarjeta de ese dia **ya es la venta
   completa**, no un piso. Un dia sin corte es un hueco. Esa diferencia es el
   motivo de que el corte exista como documento y no como campo de la venta.
3. **No sobreescribe dinero en silencio.** Corregir un corte guarda el valor
   anterior, quien lo cambio y por que (`revisions`). El dia y la sucursal no se
   pueden editar: eso seria mover dinero de dia, y para eso se captura otro
   corte.
4. **No llama "faltante" a lo que no puede comparar.** La diferencia contra el
   sistema solo se calcula cuando el app **si** tiene venta de efectivo
   capturada de ese dia. Hoy no la tiene (el punto de venta no se usa en
   sucursal), asi que `diferencia` sale `None` y dice por que, en vez de reportar
   un faltante del tamaño de todo el efectivo del dia.

### Correrlo (solo lectura)

    python backend/cash_cut.py --db casa_dorelia
    python backend/cash_cut.py --db casa_dorelia --date 2026-10-04

La captura vive en el app (`POST /api/cash-cuts`), no aqui: este CLI es para
leer lo capturado y para cuadrar contra la caja sin levantar el backend.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import brands as brands_mod  # noqa: E402  (ruta inyectada arriba, igual que el resto)
import business_day  # noqa: E402

DEFAULT_MONGO_URL = "mongodb://127.0.0.1:27017"

# Nombre de la coleccion. El efectivo NO vive en `sales`: un corte es un
# agregado del dia y un renglon de `sales` es un cobro. Meterlo en `sales` como
# una venta de $1,800 arruinaria el ticket promedio y la grafica de horas, que
# son por cobro.
COLLECTION = "cash_cuts"

# El metodo y el origen con que se rotula el dinero del corte. `SOURCE_CORTE` lo
# distingue de `clip_api` y de la captura manual de una venta.
METHOD_CASH = "efectivo"
SOURCE_CORTE = "corte_caja"

TURNO_COMPLETO = "completo"
TURNOS: Tuple[str, ...] = (TURNO_COMPLETO, "matutino", "vespertino", "nocturno")

# Tope de cordura por corte. Un dia de estas sucursales corre en miles de pesos;
# un dedazo de "115600" en vez de "1156.00" publicaria un dia falso de seis
# cifras, y nadie revisa un numero que ya salio en el tablero. El tope no es una
# regla de negocio: es la red contra el dedazo, y el error lo dice asi.
MAX_AMOUNT = 200_000.0

# Un corte capturado mucho despues del dia se marca (no se rechaza): sirve para
# cargar historia, pero el tablero tiene que poder decir que ese numero se
# recordo, no se conto.
LATE_AFTER_DAYS = 2

# Longitud maxima de la nota y de la razon de una correccion.
MAX_TEXT = 500


class CashCutError(ValueError):
    """Un corte que no se puede guardar. El mensaje siempre dice que falta."""


# --------------------------------------------------------------------------
# Normalizacion y derivacion
# --------------------------------------------------------------------------

def normalize_amount(value: Any, field: str) -> float:
    """Monto de dinero valido, redondeado a centavos.

    Rechaza lo que no es numero, el negativo y el absurdo. Los tres son dedazos
    de captura; dejarlos pasar es publicar venta inventada.
    """
    if value is None or isinstance(value, bool) or isinstance(value, str):
        # `"1,156.00"` incluido: una cadena con coma se vuelve 1.0 en float() en
        # otros lenguajes y aqui truena. Mejor que la pantalla manda un numero.
        raise CashCutError(f"`{field}` tiene que ser un numero en pesos, llego {value!r}")
    try:
        amount = float(value)
    except (TypeError, ValueError) as exc:
        raise CashCutError(f"`{field}` tiene que ser un numero en pesos, llego {value!r}") from exc
    if amount != amount or amount in (float("inf"), float("-inf")):  # NaN / inf
        raise CashCutError(f"`{field}` no es un monto finito: {value!r}")
    if amount < 0:
        raise CashCutError(f"`{field}` no puede ser negativo: {amount}")
    if amount > MAX_AMOUNT:
        raise CashCutError(
            f"`{field}` = {amount:,.2f} pasa el tope de cordura de {MAX_AMOUNT:,.2f}. "
            "Revisa si sobran ceros o faltan centavos; si de verdad fue tanto, "
            "capturalo en dos turnos."
        )
    return round(amount, 2)


def normalize_tickets(value: Any) -> Optional[int]:
    """Cuantos cobros en efectivo hubo. Opcional: `None` es "no se conto"."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CashCutError(f"`tickets_efectivo` tiene que ser un entero, llego {value!r}")
    if float(value) != int(value):
        raise CashCutError(f"`tickets_efectivo` no puede tener decimales: {value!r}")
    tickets = int(value)
    if tickets < 0:
        raise CashCutError(f"`tickets_efectivo` no puede ser negativo: {tickets}")
    return tickets


def normalize_text(value: Any, field: str) -> Optional[str]:
    """Texto libre recortado, o `None`. Nunca guarda una cadena vacia."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > MAX_TEXT:
        raise CashCutError(f"`{field}` pasa de {MAX_TEXT} caracteres ({len(text)})")
    return text


def normalize_turno(value: Any) -> str:
    """Turno del corte. Varios turnos del mismo dia suman; el default es uno solo."""
    if value is None:
        return TURNO_COMPLETO
    turno = str(value).strip().lower()
    if not turno:
        return TURNO_COMPLETO
    if turno not in TURNOS:
        raise CashCutError(f"`turno` desconocido: {value!r}. Validos: {', '.join(TURNOS)}")
    return turno


def derive_cash_sales(fondo_inicial: float, efectivo_contado: float, retiros: float) -> float:
    """La venta en efectivo que implica lo contado. Puede dar negativo a proposito.

    Devolver el negativo en vez de truncarlo a cero es lo que permite que
    `build_cut` lo rechace con los tres numeros a la vista.
    """
    return round(efectivo_contado + retiros - fondo_inicial, 2)


def is_late(business_date_value: str, *, now: Optional[datetime] = None,
            late_after_days: int = LATE_AFTER_DAYS) -> bool:
    """Si el corte se captura tarde para haberse contado del cajon."""
    from datetime import date as _date

    captured_day = business_day.today(now)
    try:
        delta = _date.fromisoformat(captured_day) - _date.fromisoformat(business_date_value)
    except ValueError as exc:  # pragma: no cover - `build_cut` ya valido el dia
        raise CashCutError(f"dia de operacion ilegible: {business_date_value!r}") from exc
    return delta.days > late_after_days


# --------------------------------------------------------------------------
# El documento
# --------------------------------------------------------------------------

def cut_filter(*, cafeteria_id: str, business_date: str, turno: str = TURNO_COMPLETO,
               tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Filtro que identifica un corte. Es tambien la llave del indice unico.

    Dos cortes del mismo turno del mismo dia en la misma sucursal son el mismo
    corte capturado dos veces, y sumarlos duplicaria la venta del dia.
    """
    query: Dict[str, Any] = {
        "cafeteria_id": cafeteria_id,
        "business_date": business_date,
        "turno": turno,
    }
    if tenant_id:
        query["tenant_id"] = tenant_id
    return query


def build_cut(*, cafeteria_id: str, brand: Optional[str], business_date: Any,
              fondo_inicial: Any, efectivo_contado: Any, retiros: Any = 0,
              turno: Any = None, tickets_efectivo: Any = None, notas: Any = None,
              tenant_id: Optional[str] = None, created_by: Optional[str] = None,
              created_by_name: Optional[str] = None,
              sistema_efectivo: Any = None, sistema_tickets: Any = None,
              cut_id: Optional[str] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Arma el documento del corte, ya validado y con lo derivado calculado.

    Pura: no toca Mongo. Lo que esta funcion rechaza no llega a la base.
    """
    now = now or datetime.now(timezone.utc)

    if not cafeteria_id or not str(cafeteria_id).strip():
        raise CashCutError("falta `cafeteria_id`: un corte es de una sucursal")
    cafeteria_id = str(cafeteria_id).strip()

    if not brand or not str(brand).strip():
        # Sin marca el efectivo no se puede separar, y un efectivo mezclado es
        # peor que ninguno: entraria a un total de dos repartos (BOS-101).
        raise CashCutError(
            f"la sucursal {cafeteria_id} no tiene `brand`: sin marca el efectivo "
            "no se puede separar y no se guarda"
        )
    brand = str(brand).strip()

    try:
        day = business_day.to_business_date(business_date)
    except business_day.BusinessDayError as exc:
        raise CashCutError(f"`business_date` invalido: {exc}") from exc
    if not day:
        raise CashCutError("falta `business_date`: el corte es de un dia de operacion")
    hoy = business_day.today(now)
    if day > hoy:
        raise CashCutError(
            f"el dia de operacion {day} es futuro (hoy es {hoy}): no se puede "
            "contar un cajon que no ha cerrado"
        )

    turno_value = normalize_turno(turno)
    fondo = normalize_amount(fondo_inicial, "fondo_inicial")
    contado = normalize_amount(efectivo_contado, "efectivo_contado")
    salidas = normalize_amount(retiros, "retiros")
    cash = derive_cash_sales(fondo, contado, salidas)
    if cash < 0:
        raise CashCutError(
            f"la cuenta da efectivo negativo ({cash:,.2f}): contado {contado:,.2f} "
            f"+ retiros {salidas:,.2f} - fondo {fondo:,.2f}. Falta registrar un "
            "retiro, o el fondo inicial no es el que se dejo."
        )

    tickets = normalize_tickets(tickets_efectivo)
    if tickets is not None:
        if tickets == 0 and cash > 0:
            raise CashCutError(
                f"dice 0 cobros en efectivo y {cash:,.2f} de efectivo: una de las "
                "dos cosas esta mal"
            )
        if tickets > 0 and cash == 0:
            raise CashCutError(
                f"dice {tickets} cobro(s) en efectivo y 0.00 de efectivo: revisa el "
                "contado o el fondo"
            )

    cut: Dict[str, Any] = {
        "id": cut_id or str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "cafeteria_id": cafeteria_id,
        "brand": brand,
        "business_date": day,
        "turno": turno_value,
        "fondo_inicial": fondo,
        "efectivo_contado": contado,
        "retiros": salidas,
        "ventas_efectivo": cash,
        "tickets_efectivo": tickets,
        "ticket_promedio": round(cash / tickets, 2) if tickets else None,
        # Rotulos para que un lector de la coleccion no tenga que adivinar de
        # donde salio el dinero ni con que metodo se cobro.
        "payment_method": METHOD_CASH,
        "source": SOURCE_CORTE,
        "notas": normalize_text(notas, "notas"),
        "created_by": created_by,
        "created_by_name": created_by_name,
        "created_at": now.astimezone(timezone.utc).isoformat(),
        "captured_late": is_late(day, now=now),
        "revisions": [],
    }
    cut.update(compare_with_system(cut, sistema_efectivo=sistema_efectivo,
                                  sistema_tickets=sistema_tickets))
    return cut


def compare_with_system(cut: Mapping[str, Any], *, sistema_efectivo: Any = None,
                        sistema_tickets: Any = None) -> Dict[str, Any]:
    """Compara el corte contra la venta de efectivo que el app ya tenia.

    Devuelve los campos a pegarle al documento. `diferencia` es `None` cuando no
    hay con que comparar, y `diferencia_motivo` dice por que: hoy la sucursal no
    captura venta en el punto de venta, asi que restar daria un "faltante" del
    tamaño de todo el efectivo del dia. Un faltante inventado es peor que no
    tener el dato, porque acusa a alguien.
    """
    cash = float(cut.get("ventas_efectivo") or 0.0)
    if sistema_efectivo is None:
        return {
            "sistema_efectivo": None,
            "sistema_tickets": None,
            "comparable": False,
            "diferencia": None,
            "diferencia_motivo": ("el app no tiene venta en efectivo capturada de "
                                  "ese dia: el corte es la unica fuente"),
        }

    sistema = normalize_amount(sistema_efectivo, "sistema_efectivo")
    tickets = normalize_tickets(sistema_tickets)
    if sistema == 0 and not tickets:
        # Cero capturado no es "cuadra con cero": es que no hay con que comparar.
        return {
            "sistema_efectivo": 0.0,
            "sistema_tickets": tickets,
            "comparable": False,
            "diferencia": None,
            "diferencia_motivo": ("el app tiene 0 cobros en efectivo de ese dia: "
                                  "no hay contra que cuadrar"),
        }
    return {
        "sistema_efectivo": sistema,
        "sistema_tickets": tickets,
        "comparable": True,
        # Positivo = sobro dinero en el cajon; negativo = falto.
        "diferencia": round(cash - sistema, 2),
        "diferencia_motivo": None,
    }


# Lo que identifica al corte y por eso no se edita: cambiarlo mueve dinero de
# dia, de sucursal o de marca sin dejar un corte nuevo.
IMMUTABLE_FIELDS: Tuple[str, ...] = ("id", "cafeteria_id", "business_date", "turno",
                                     "brand", "tenant_id")

# Lo que si se puede corregir.
EDITABLE_FIELDS: Tuple[str, ...] = ("fondo_inicial", "efectivo_contado", "retiros",
                                    "tickets_efectivo", "notas")


def revise_cut(existing: Mapping[str, Any], changes: Mapping[str, Any], *,
               reason: Any, user_id: Optional[str] = None,
               user_name: Optional[str] = None,
               sistema_efectivo: Any = None, sistema_tickets: Any = None,
               now: Optional[datetime] = None) -> Dict[str, Any]:
    """Corrige un corte guardando el valor anterior, quien y por que.

    Devuelve un documento nuevo; no muta el que recibio. Sin razon no corrige:
    un monto de dinero que cambia sin motivo escrito es indistinguible de un
    fraude, y el siguiente que lo lea no tiene forma de saber cual fue.
    """
    now = now or datetime.now(timezone.utc)
    motivo = normalize_text(reason, "reason")
    if not motivo:
        raise CashCutError("para corregir un corte hace falta la razon del cambio")

    blocked = [field for field in changes if field in IMMUTABLE_FIELDS]
    if blocked:
        raise CashCutError(
            f"no se puede cambiar {', '.join(sorted(blocked))} de un corte ya "
            "guardado: captura el corte del dia o la sucursal correctos"
        )
    unknown = [field for field in changes if field not in EDITABLE_FIELDS]
    if unknown:
        raise CashCutError(f"campo(s) que no se corrigen aqui: {', '.join(sorted(unknown))}")
    if not changes:
        raise CashCutError("no llego ningun cambio")

    merged = dict(existing)
    before = {field: existing.get(field) for field in changes}
    merged.update(changes)

    rebuilt = build_cut(
        cafeteria_id=merged.get("cafeteria_id"),
        brand=merged.get("brand"),
        business_date=merged.get("business_date"),
        fondo_inicial=merged.get("fondo_inicial"),
        efectivo_contado=merged.get("efectivo_contado"),
        retiros=merged.get("retiros") or 0,
        turno=merged.get("turno"),
        tickets_efectivo=merged.get("tickets_efectivo"),
        notas=merged.get("notas"),
        tenant_id=merged.get("tenant_id"),
        created_by=existing.get("created_by"),
        created_by_name=existing.get("created_by_name"),
        sistema_efectivo=sistema_efectivo,
        sistema_tickets=sistema_tickets,
        cut_id=existing.get("id"),
        now=now,
    )
    # El corte conserva su nacimiento: quien lo capturo y cuando. La correccion
    # es un renglon mas de su historia, no un documento nuevo.
    rebuilt["created_at"] = existing.get("created_at") or rebuilt["created_at"]
    rebuilt["captured_late"] = bool(existing.get("captured_late"))
    rebuilt["revisions"] = list(existing.get("revisions") or []) + [{
        "at": now.astimezone(timezone.utc).isoformat(),
        "by": user_id,
        "by_name": user_name,
        "reason": motivo,
        "before": before,
        "after": {field: rebuilt.get(field) for field in changes},
    }]
    return rebuilt


def prefill(previous: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Lo que la pantalla puede proponer sin inventar dinero.

    Solo el fondo inicial, y solo porque el fondo con que abre la caja es el que
    quedo en el corte anterior. Lo contado y los retiros se cuentan: proponerlos
    seria sugerir un numero que nadie conto, y el default se acaba aceptando.
    """
    fondo = None
    if previous:
        fondo = previous.get("fondo_inicial")
    return {
        "fondo_inicial": round(float(fondo), 2) if fondo is not None else None,
        "fondo_inicial_origen": ("del corte anterior" if fondo is not None
                                 else "no hay corte anterior: capturalo"),
        "efectivo_contado": None,
        "retiros": None,
    }


# --------------------------------------------------------------------------
# Lectura: efectivo por marca y por dia
# --------------------------------------------------------------------------

def cash_by_day(cuts: Iterable[Mapping[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """`{marca: {dia: {cash, tickets, cuts}}}`. Varios turnos del dia suman."""
    out: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for cut in cuts:
        slug = cut.get("brand") or brands_mod.UNKNOWN_BRAND
        day = cut.get("business_date")
        if not day:
            continue
        bucket = out.setdefault(slug, {}).setdefault(
            str(day)[:10], {"cash": 0.0, "tickets": 0, "cuts": 0})
        bucket["cash"] = round(bucket["cash"] + float(cut.get("ventas_efectivo") or 0.0), 2)
        tickets = cut.get("tickets_efectivo")
        if tickets:
            bucket["tickets"] += int(tickets)
        bucket["cuts"] += 1
    return out


def covered_days(cuts: Iterable[Mapping[str, Any]], brand: Optional[str] = None) -> List[str]:
    """Dias que ya tienen corte (ordenados). Es lo que vuelve citable un total.

    Un dia de esta lista deja de ser piso: su bruto es tarjeta + efectivo
    contado. Un dia que no esta aqui sigue siendo piso, aunque el de al lado si
    tenga corte.
    """
    days = {str(cut.get("business_date"))[:10] for cut in cuts
            if cut.get("business_date") and (brand is None or cut.get("brand") == brand)}
    return sorted(days)


def duplicate_cuts(cuts: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Cortes repetidos de (sucursal, dia, turno). Deberian ser imposibles.

    El indice unico los impide al guardar, pero una base sin el indice (o una
    carga a mano) si puede tenerlos, y sumarlos duplica la venta del dia. Salen
    en los controles del dato en vez de desaparecer dentro del total.
    """
    seen: Dict[Tuple[str, str, str], int] = {}
    for cut in cuts:
        key = (str(cut.get("cafeteria_id")), str(cut.get("business_date"))[:10],
               str(cut.get("turno") or TURNO_COMPLETO))
        seen[key] = seen.get(key, 0) + 1
    return [{"cafeteria_id": key[0], "business_date": key[1], "turno": key[2], "cuts": count}
            for key, count in sorted(seen.items()) if count > 1]


def summarize_cuts(cuts: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """Efectivo capturado por marca, decorado con nombre y vehiculo.

    Igual que `brands.summarize_brand_rows`: el total de todas las marcas solo
    aparece como **suma de control** y con el nombre diciendolo. Dos marcas con
    repartos distintos no tienen un total publicable.
    """
    rows = list(cuts)
    per_brand: Dict[str, Dict[str, Any]] = {}
    for cut in rows:
        slug = cut.get("brand") or brands_mod.UNKNOWN_BRAND
        bucket = per_brand.setdefault(slug, {
            "brand": slug,
            "name": brands_mod.brand_name(slug),
            "vehicle": brands_mod.brand_vehicle(slug),
            "cash": 0.0,
            "tickets": 0,
            "cuts": 0,
            "days": set(),
        })
        bucket["cash"] = round(bucket["cash"] + float(cut.get("ventas_efectivo") or 0.0), 2)
        tickets = cut.get("tickets_efectivo")
        if tickets:
            bucket["tickets"] += int(tickets)
        bucket["cuts"] += 1
        if cut.get("business_date"):
            bucket["days"].add(str(cut["business_date"])[:10])

    brands_out: List[Dict[str, Any]] = []
    control_total = 0.0
    for slug in sorted(per_brand):
        bucket = per_brand[slug]
        days = sorted(bucket.pop("days"))
        bucket["days_covered"] = len(days)
        bucket["first_day"] = days[0] if days else None
        bucket["last_day"] = days[-1] if days else None
        control_total += bucket["cash"]
        brands_out.append(bucket)

    return {
        "brands": brands_out,
        # Suma de control: dinero de dos repartos. No es "el efectivo del grupo".
        "cash_all_brands": round(control_total, 2),
        "cuts": len(rows),
        "late_cuts": sum(1 for cut in rows if cut.get("captured_late")),
        "revised_cuts": sum(1 for cut in rows if cut.get("revisions")),
        "duplicates": duplicate_cuts(rows),
        "unlabeled_cuts": sum(1 for cut in rows if not cut.get("brand")),
    }


# --------------------------------------------------------------------------
# CLI de lectura
# --------------------------------------------------------------------------

def open_collection(mongo_url: Optional[str] = None, db_name: Optional[str] = None):
    """Coleccion `cash_cuts`, con un mensaje util cuando falta configuracion."""
    try:
        from pymongo import MongoClient
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise CashCutError("falta el driver de Mongo: pip install pymongo") from exc

    url = mongo_url or os.environ.get("MONGO_URL") or DEFAULT_MONGO_URL
    name = db_name or os.environ.get("DB_NAME")
    if not name:
        raise CashCutError("falta `DB_NAME` (o --db): no se adivina que base se lee")
    client = MongoClient(url, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")  # falla aqui, no a media consulta
    return client[name][COLLECTION]


def read_cuts(collection: Any, *, business_date: Optional[str] = None,
              start: Optional[str] = None, end: Optional[str] = None,
              cafeteria_id: Optional[str] = None,
              tenant_id: Optional[str] = None,
              limit: int = 2000) -> List[Dict[str, Any]]:
    """Cortes de la base, filtrados por dia o ventana de dias de operacion."""
    query: Dict[str, Any] = {}
    if business_date:
        query["business_date"] = business_day.to_business_date(business_date)
    else:
        query.update(business_day.business_window(start, end))
    if cafeteria_id:
        query["cafeteria_id"] = cafeteria_id
    if tenant_id:
        query["tenant_id"] = tenant_id
    cursor = collection.find(query, {"_id": 0}).sort("business_date", 1)
    return list(cursor.limit(limit) if hasattr(cursor, "limit") else cursor)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cash_cut",
        description="Efectivo declarado en los cortes de caja. Solo lee, nunca escribe.",
    )
    parser.add_argument("--date", default=None, help="dia de operacion `YYYY-MM-DD`")
    parser.add_argument("--from", dest="start", default=None, help="desde (dia de operacion)")
    parser.add_argument("--to", dest="end", default=None, help="hasta (dia de operacion)")
    parser.add_argument("--branch", dest="cafeteria_id", default=None, help="`cafeteria_id`")
    parser.add_argument("--db", default=None, help="base a leer (default: $DB_NAME)")
    parser.add_argument("--mongo-url", default=None, help="default: $MONGO_URL o localhost")
    parser.add_argument("--tenant", default=None, help="`tenant_id`, si la base es multi-empresa")

    args = parser.parse_args(argv)

    try:
        collection = open_collection(args.mongo_url, args.db)
        cuts = read_cuts(collection, business_date=args.date, start=args.start,
                         end=args.end, cafeteria_id=args.cafeteria_id,
                         tenant_id=args.tenant)
    except CashCutError as exc:
        print(f"ERROR: {exc}")
        return 1

    report = summarize_cuts(cuts)
    report["window"] = args.date or f"{args.start or 'inicio'} .. {args.end or 'hoy'}"
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not cuts:
        print("\nAVISO: no hay cortes capturados en esa ventana. Mientras no haya "
              "corte, el bruto con tarjeta de esos dias es piso, no la venta.")
    if report["duplicates"]:
        print(f"\nAVISO: {len(report['duplicates'])} (sucursal, dia, turno) con mas de "
              "un corte. Eso duplica venta: revisa el indice unico de `cash_cuts`.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
