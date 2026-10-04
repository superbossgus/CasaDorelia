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
   (`c-tecno`). Cada una tiene su renglon, su color y su tarjeta. La suma de las
   dos solo aparece rotulada como suma de control.
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

### Correrlo

    python backend/dashboard.py --db casa_dorelia
    python backend/dashboard.py --db casa_dorelia --out C:/tmp/ventas.html

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


def build_model(sales: Iterable[Mapping[str, Any]], *, title: str,
                today: Optional[str] = None, now: Optional[datetime] = None,
                db_name: Optional[str] = None) -> Dict[str, Any]:
    """Arma el modelo completo del tablero. Pura: recibe documentos, no una conexion.

    Devuelve ya listo lo que la pagina dibuja, incluida la lista de limites del
    dato. Que los limites se *calculen* (y no se escriban a mano en el HTML) es
    lo que impide que el tablero siga diciendo "sin utilidad" el dia que si haya
    costos, o que se calle el efectivo el dia que entre venta de caja.
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
        payment_methods[sale.get("payment_method") or "sin-metodo"] += 1

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
        "control_sum": {
            "gross": _round2(sum(b["totals"]["gross"] for b in brand_models)),
            "tickets": sum(b["totals"]["tickets"] for b in brand_models),
        },
        "quality": {"checks": checks},
        "limits": {
            # Calculados, no escritos a mano: el dia que el dato cambie, el
            # rotulo cambia con el.
            "cash_excluded": sorted(payment_methods) == ["tarjeta"],
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
    parser.add_argument("--title", default="Ventas con tarjeta",
                        help="titulo del tablero")
    parser.add_argument("--json", action="store_true",
                        help="imprime el modelo en JSON en vez de escribir el HTML")

    args = parser.parse_args(argv)

    try:
        sales = open_sales_collection(args.mongo_url, args.db)
        db_name = args.db or os.environ.get("DB_NAME")
        model = build_model(sales.find({}, {"_id": 0}), title=args.title,
                            db_name=db_name)
    except DashboardError as exc:
        print(f"ERROR: {exc}")
        return 1

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
    print("  Piso, no venta del dia: el efectivo no pasa por la API de Clip.")

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
    if (L.cash_excluded) {
      items.push(["No dice la venta del dia. ",
        "Todo lo cargado es cobro con tarjeta via la API de Clip, que no entrega " +
        "efectivo. Cada monto es un piso: la venta real es ese numero mas la caja."]);
    } else {
      items.push(["Metodos de pago cargados. ",
        Object.keys(L.payment_methods).join(", ") +
        ". Revisa si el efectivo ya entra completo antes de leer un total como venta."]);
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
    items.push(["No hay un total de las dos marcas. ",
      "Esta base guarda dos negocios con repartos distintos. La suma de control " +
      "del historico es " + MXN.format(M.control_sum.gross) + " en " +
      NUM.format(M.control_sum.tickets) + " cobros, y es solo eso: una suma de " +
      "control, no «la venta» de ninguna de las dos."]);
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

  function renderHeader() {
    document.getElementById("title").textContent = M.title;
    var span = M.days.length
      ? shortDay(M.days[0]) + " a " + shortDay(M.days[M.days.length - 1])
      : "sin dias";
    document.getElementById("subtitle").textContent =
      span + " · " + NUM.format(M.rows_counted) + " cobros · generado " +
      M.generated_at_label + (M.db_name ? " · base " + M.db_name : "");

    var note = document.getElementById("floor-note");
    note.textContent = "";
    note.appendChild(el("strong", null, "Todo lo de aqui es cobro con tarjeta, no la venta del dia. "));
    note.appendChild(el("span", null,
      "El efectivo no pasa por la API de Clip, asi que cada cifra es un piso. " +
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
