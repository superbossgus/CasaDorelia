"""Dia de operacion del negocio: una sola fuente del huso horario.

El problema que resuelve: `created_at` se sella en UTC y CDMX es UTC-6, asi que
**toda venta despues de las 18:00 locales cae en el dia UTC siguiente**. Para
una cafeteria que cierra de noche eso no es un caso raro, es todos los dias:
cortar por dia UTC inventa venta en dias cerrados y arranca "ventas del mes"
con dinero del mes anterior.

El dia de operacion vive en el campo `business_date` (`YYYY-MM-DD`, hora local)
de cada venta. Este modulo es el **unico** lugar donde se decide cual es ese
dia; `sales_import`, `clip_api` y los reportes de `server.py` lo importan de
aqui en vez de volver a escribir el offset.

Ojo con el tipo: `business_date` es una cadena `YYYY-MM-DD` y `created_at` es
ISO con hora. Comparar cadenas `YYYY-MM-DD` con `$gte`/`$lte` funciona y ordena
bien, pero el limite superior de una ventana ya NO puede ser `...T23:59:59`:
sobre dias se cierra con el dia mismo (`$lte: "2026-09-30"`), que incluye el dia
completo. `business_window()` existe para no equivocarse en eso.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

# Mexico dejo de aplicar horario de verano en octubre de 2022, asi que la zona
# del negocio es UTC-6 todo el año. Se usa un offset fijo a proposito: evita
# depender de `tzdata` (que en Windows no viene con Python) y es determinista.
BUSINESS_TZ = timezone(timedelta(hours=-6), name="America/Mexico_City")


class BusinessDayError(ValueError):
    """Una fecha que no se puede leer como dia de operacion."""


# --------------------------------------------------------------------------
# De fecha-hora a dia de operacion
# --------------------------------------------------------------------------

def business_date(moment: datetime) -> str:
    """Dia de operacion (`YYYY-MM-DD`) de un instante.

    Un `datetime` sin zona se entiende como hora local del negocio, que es la
    convencion del export del panel y de la captura manual.
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=BUSINESS_TZ)
    return moment.astimezone(BUSINESS_TZ).date().isoformat()


def to_business_date(value: Any) -> Optional[str]:
    """Normaliza a dia de operacion lo que llegue por la API o del documento.

    Acepta `None` (devuelve `None`), `datetime`, `date`, un dia suelto
    (`"2026-09-30"`) o un ISO-8601 completo. **Sin** offset se lee como hora
    local; **con** offset se convierte a hora del negocio antes de cortar.

    Es lo que vuelve seguro recibir `start_date=2026-10-01T00:00:00Z` de una
    pantalla vieja: se convierte, no se trunca a los primeros 10 caracteres.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return business_date(value)
    if isinstance(value, date):
        return value.isoformat()

    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BusinessDayError(f"no es una fecha ISO-8601: {value!r}") from exc
    if parsed.tzinfo is None:
        # Un dia suelto o una hora sin offset ya vienen en hora del negocio.
        return parsed.date().isoformat()
    return business_date(parsed)


def sale_business_date(sale: Mapping[str, Any]) -> Optional[str]:
    """Dia de operacion de un documento de `sales`.

    Usa `business_date` si el documento lo trae y si no lo deriva de
    `created_at`. La derivacion es una red de seguridad para ventas que el
    backfill todavia no toco; el camino bueno es que toda venta nazca sellada
    (ver `stamp_business_date`).
    """
    stamped = sale.get("business_date")
    if stamped:
        return str(stamped)[:10]
    try:
        return to_business_date(sale.get("created_at"))
    except BusinessDayError:
        return None


def stamp_business_date(sale: Dict[str, Any]) -> Dict[str, Any]:
    """Sella `business_date` en un documento de venta a partir de `created_at`.

    Muta y devuelve el mismo diccionario, para poder usarlo en linea justo
    antes de insertar.
    """
    day = sale_business_date(sale)
    if day:
        sale["business_date"] = day
    return sale


# --------------------------------------------------------------------------
# Dias y ventanas
# --------------------------------------------------------------------------

def today(now: Optional[datetime] = None) -> str:
    """Dia de operacion en curso. `now` se inyecta en las pruebas."""
    return business_date(now or datetime.now(timezone.utc))


def month_start(day: Optional[str] = None) -> str:
    """Primer dia del mes de operacion (`YYYY-MM-01`)."""
    return f"{(day or today())[:7]}-01"


def recent_days(count: int, end_day: Optional[str] = None) -> List[str]:
    """Los ultimos `count` dias de operacion, del mas viejo al mas nuevo."""
    if count <= 0:
        return []
    end = date.fromisoformat(end_day or today())
    return [(end - timedelta(days=offset)).isoformat() for offset in range(count - 1, -1, -1)]


def day_start_utc(day: Optional[str] = None) -> datetime:
    """Instante UTC en que empieza un dia de operacion (00:00 local).

    Para colecciones que NO guardan `business_date` y se siguen filtrando por
    `created_at` (los pedidos del POS, por ejemplo): el corte del dia sigue
    siendo el del negocio, solo que expresado como instante. Sin esto, "hoy"
    en el POS empezaria a las 18:00 locales del dia anterior.
    """
    start = date.fromisoformat(day or today())
    return datetime(start.year, start.month, start.day, tzinfo=BUSINESS_TZ).astimezone(timezone.utc)


def business_window(start: Any = None, end: Any = None,
                    field: str = "business_date") -> Dict[str, Any]:
    """Filtro de Mongo por dia de operacion, listo para mezclar en un query.

    Devuelve `{}` cuando no hay extremos, para poder hacer `{**query,
    **business_window(...)}` sin condicionales. El extremo superior se cierra
    con `$lte` sobre el dia, que incluye el dia completo: no hay que inventar
    un `T23:59:59` que con cadenas `YYYY-MM-DD` dejaria el dia fuera.
    """
    bounds: Dict[str, str] = {}
    first = to_business_date(start)
    last = to_business_date(end)
    if first:
        bounds["$gte"] = first
    if last:
        bounds["$lte"] = last
    return {field: bounds} if bounds else {}


# --------------------------------------------------------------------------
# Corte por dia
# --------------------------------------------------------------------------

def daily_totals(sales: Iterable[Mapping[str, Any]],
                 days: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
    """Corte por dia de operacion de documentos de `sales`.

    Con `days` se fija el eje: los dias sin venta salen en cero y en orden, que
    es lo que necesita una grafica de tendencia. Sin `days` salen solo los dias
    con movimiento, ordenados.
    """
    buckets: Dict[str, Dict[str, Any]] = {}
    wanted = set(days) if days is not None else None

    for sale in sales:
        day = sale_business_date(sale)
        if day is None or (wanted is not None and day not in wanted):
            continue
        bucket = buckets.setdefault(day, _empty_day(day))
        bucket["transactions"] += 1
        bucket["gross"] = round(bucket["gross"] + float(sale.get("total") or 0.0), 2)
        bucket["profit"] = round(bucket["profit"] + float(sale.get("profit") or 0.0), 2)

    axis = list(days) if days is not None else sorted(buckets)
    return [buckets.get(day, _empty_day(day)) for day in axis]


def as_corte(totals: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Proyecta `daily_totals` a la forma de `clip_api.summarize_corte`.

    Sirve para comparar peso por peso lo que muestra el app contra el corte que
    se aprueba antes de cargar: si las dos listas no son identicas, una de las
    dos esta cortando por el dia equivocado.
    """
    return [{"date": row["date"], "transactions": row["transactions"], "gross": row["gross"]}
            for row in totals]


def _empty_day(day: str) -> Dict[str, Any]:
    return {"date": day, "transactions": 0, "gross": 0.0, "profit": 0.0}
