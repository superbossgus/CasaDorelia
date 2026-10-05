"""
Cliente de la API de transacciones de Clip (via credenciales, no via export).

Modulo puro: no toca Mongo, no importa FastAPI y **nunca** escribe la credencial
en un log, en un error ni en un repr. Entrega filas con la misma forma que
`clip_import.parse_sales`, para que `sales_import.plan_import` las cargue por
`POST /api/sales/import` sin cambiar nada del otro lado.

Contrato de la API, verificado contra developer.clip.mx (2026-10-01):

- `GET https://api-gw.payclip.com/payments`
- `GET https://api-gw.payclip.com/settlements[/{id}]` (depositos): se lee bien
  con la misma llave de comercio; ver `probe_deposits`. (Una version anterior de
  este archivo decia "401 para esta cuenta": era un bug nuestro, no un alcance
  faltante.)
- **No hay detalle por transaccion.** Probado el 2026-10-04 con un folio real:
  `GET /payments/{receipt_no}` -> 500, `GET /transactions/{id}` -> 403
  `Forbidden`, `GET /payment/{id}` -> 403 pidiendo firma AWS. El renglon de la
  lista **es** el registro completo que ve la llave de comercio; no hay una
  vista mas detallada atras donde pudiera venir el metodo de pago real.
- **No se vale descubrir rutas por barrido en este gateway.** `403
  {"message":"Forbidden"}` es la respuesta a **cualquier** ruta desconocida:
  medido el 2026-10-04, `/a/b/c/d/e` contesta exactamente lo mismo que
  `/webhooks` o `/reports`. Un barrido sin ese control positivo deja una lista
  de 403 que se lee como "estas rutas existen pero falta alcance", y es falso.
  Lo que si discrimina son los otros dos sabores:

  - `401 {"message":"Unauthorized"}` -> el prefijo **si** esta ruteado y el
    servicio de atras rechazo la credencial (`/settlements/...`).
  - `403` pidiendo `Credential`/`Signature` -> ruta real de **otro** esquema de
    auth, el de firma AWS con el que entra la app de Clip (`/subscriptions`,
    `/merchants/me`, y la ruta de efectivo).

  Con ese criterio, la superficie que la llave de comercio alcanza son
  `/payments*` y `/settlements*`, y ninguno tiene dimension de efectivo.
- Autenticacion: `Authorization: Basic base64(API_KEY:SECRET_KEY)`. El panel de
  Clip entrega las dos piezas al crear la credencial y **el secret key solo se
  puede ver una vez**; si se pierde hay que generar otra.
- Parametros: `from`, `to` (ISO-8601, obligatorios), `status` (`paid` |
  `cancelled`), `last4`, `limit` (1..100, default 20), `pagination_token`.
- La ventana `from`..`to` **no puede exceder un mes de calendario** (la doc
  dice "720 horas", y eso es falso en febrero: ver `MAX_AGE` arriba de
  `split_window`) y no se pueden consultar transacciones de mas de un ano de
  antiguedad. Por eso `split_window` parte el rango solicitado en ventanas
  validas y pagina cada una; el que llama pide "del 21/09 a hoy" y no se entera.
- La paginacion devuelve `meta.pagination_token`.

Decisiones que cambian el dinero reportado (y por que):

1. **La propina NO es venta.** La respuesta trae `amount` (monto del consumo),
   `tip` y `total = amount + tip`. Se carga `amount` como `gross_amount` y la
   propina viaja aparte en `tip`. Usar `total` infla la venta con dinero que es
   del personal, y ademas le calcularia IVA a la propina.
2. **El monto de Clip ya trae IVA.** Aqui no se desglosa: eso lo hace
   `sales_import.normalize_row` con `split_tax`. Este modulo no vuelve a sumar
   impuesto nunca.
3. **No todo lo que no es debito/credito es tarjeta.** Clip mete en
   `payment_method: "OTHER"` dos cosas distintas y las distingue por el emisor
   de la tarjeta (ver `_payment_method`):

   - **vales de despensa/restaurante** (`card.issuer` = PLUXEE MEXICO, EDENRED,
     TOKA, TODITO...), que son dinero cobrado pero con otro reparto y otra
     comision que una tarjeta bancaria; y
   - **cobros sin tarjeta** (`card.brand: "XX"`, `last4: "0000"`, sin emisor),
     que no se pueden nombrar desde la API.

   Hasta BOS-119 los tres caian en `"tarjeta"` por el `return` final. En
   Tecnoparque eso son $25,214 de vales de un año reportados como tarjeta.

   La propia doc de Clip dice que `OTHER` es "la tarjeta no es de debito ni
   credito, **por ejemplo, tarjeta de vales y pago en efectivo**". O sea que el
   esquema **admite** efectivo en este cajon; lo que no pasa es que llegue (ver
   el punto 5). Por eso `_payment_method` no le dice efectivo a un renglon sin
   tarjeta: el cajon da para las dos cosas y el dato no las distingue.

4. **Un `status` vacio es una cancelacion.** No es "no se sabe": la API siempre
   manda el campo y `?status=cancelled` devuelve justo esos renglones (ver
   `_status`). `classify_status("")` dice `"paid"` porque en el export del panel
   una columna ausente si significa cobrada; aqui significa lo contrario, y sin
   la rama una cancelacion entra como venta.

5. **El efectivo de la app no viaja por esta API.** Cerrado el 2026-10-04 con
   un censo de la taxonomia completa, no con una muestra: **2,329 cobros** en
   360 dias de las dos sucursales, agrupados por
   `(payment_method, sub_type, card.brand, card.issuer, status)`.
   **Cero** rotulados efectivo.

   Lo que cierra la pregunta es *que* son los unicos dos renglones sin tarjeta
   del año. Los dos traen `sub_type: "CONSUMER"`, `card.brand: "XX"`,
   `last4: "0000"` **y `status: ""`** — o sea, por el punto 4, los dos son
   **cancelaciones**, no efectivo. Una cancelacion llega sin identidad de
   tarjeta, y eso explica la forma sin tener que inventarle efectivo. Con eso el
   cajon "sin tarjeta" queda en 0 renglones cobrados en un año.

   Y no es que no haya llegado: es que **no cabe**. Son dos afirmaciones
   distintas, y la segunda se midio aparte (ver `summarize_schema` y
   `probe_method_filter`, `python clip_api.py schema`):

   - El esquema que manda la API son **19 rutas, las mismas 19 en las 2,332
     transacciones** del año. `payment_method` toma exactamente tres valores:
     `CREDIT`, `DEBIT`, `OTHER`. Ninguna ruta, en ningun renglon, nombra
     efectivo — barrido de texto sobre el JSON completo, no sobre los campos
     que se nos ocurrieron.
   - `card.brand` y `card.last4` vienen en **2,332 de 2,332**. Las dos unicas
     excepciones son exactamente los dos folios que Clip devuelve bajo
     `?status=cancelled`, y `paid + cancelled == total` sin residuo: no hay un
     tercer cajon donde esconder el efectivo.
   - `payment_method` **no es un filtro**: se ignora (un valor absurdo devuelve
     las mismas filas que `CASH`), mientras `status=ZZZZ` si contesta 400. O sea
     que la API valida lo que conoce, y no conoce el efectivo ni para pedirlo.

   Y cuadra con la realidad que reporta Gustavo: 6 a 20 cobros en efectivo por
   dia por sucursal, y el 30/08 hubo 5 en SJI; ese dia la API entrega **2**
   renglones de SJI (un cobro con tarjeta de $5.00 y una cancelacion de $5.00).

   No es una limitante de la credencial: la **documentacion de Clip** lo dice.
   La guia de conciliacion (`developer.clip.mx/docs/conciliacion-de-transaccio
   nes-apis-1`) pone el recibo de un cobro en efectivo en la app, el panel, los
   reportes descargables y el correo de confirmacion — y en ningun endpoint.
   La ruta de efectivo del gateway contesta pidiendo firma AWS (el esquema con
   el que entra la app), no la llave de comercio.

   Consecuencia que hay que decir siempre: el total de este camino es un
   **piso**, y el faltante **no es chico**. La cobertura la declara
   `sales_import.CASH_COVERAGE["clip_api"]`; aqui no se simula.

   **Cerrado por decision, no por respuesta de Clip** (2026-10-04, BOS-151).
   Faltaba un paso que ningun agente puede dar: preguntarle a soporte si la
   cuenta puede habilitar un alcance de efectivo, porque Clip verifica la
   propiedad del comercio y eso sale del buzon del titular. Gustavo decidio
   **no** mandar esa consulta, asi que la pregunta queda cerrada con lo medido
   arriba. La distincion importa para quien lea esto despues: Clip **no**
   contesto "no existe" — no se le pregunto. Lo que sostiene el cierre es la
   medicion de este modulo (19 rutas, tres valores de `payment_method`, el
   filtro que se ignora, los depositos todos con tarjeta), no una declaracion
   del proveedor. Si alguien quiere reabrirlo, el mensaje ya esta escrito en la
   tarjeta y no hay que volver a medir nada.

   Por eso el veredicto sigue **calculandose** y no esta escrito a mano: el dia
   que Clip empiece a mandar efectivo, `efectivo_en_la_api` se vuelve `true`
   solo y este parrafo queda viejo. Un cierre por decision no es un hecho
   tecnico permanente. Mientras tanto la unica fuente del efectivo es el corte
   de caja de la app propia (`backend/cash_cut.py` y `RUNBOOK-efectivo.md`, en
   la rama de la app), que es exactamente el camino que si se construyo.

Uso rapido (la credencial se lee del entorno, nunca de un argumento):
    python clip_api.py probe --branch sji
    python clip_api.py pull --branch sji --from 2026-09-21 --to 2026-10-01
    python clip_api.py census --branch sji --days 360   # ?ya llega efectivo?
    python clip_api.py schema --branch sji --days 360   # ?cabe el efectivo?
    python clip_api.py deposits --branch sji            # ?y en los depositos?
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

from clip_import import classify_status, normalize_payment_method

API_BASE = "https://api-gw.payclip.com"
PAYMENTS_PATH = "/payments"

# Encabezados que no son autenticacion pero sin los que no se entra.
#
# El gateway de Clip tiene un WAF que bloquea por firma de cliente: sin
# `User-Agent` propio, urllib se anuncia como `Python-urllib/3.11` y la
# respuesta es `403 "The site owner has blocked access based on your browser's
# signature"`. Ese 403 **no** es un problema de credencial ni de alcance, pero
# se parece a uno; medirlo como tal es como se inventa un hallazgo falso. Por
# eso los encabezados base viven aqui y los usan todas las rutas.
BASE_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "casa-dorelia-ingesta/1.0",
}

# Limites que impone Clip, no nosotros.
#
# El limite real de la ventana es **un mes de calendario**, no las "720 horas"
# que dice la documentacion. Medido contra la API el 2026-10-04 (BOS-119):
#
#     from 2026-01-06 22:08 -> to 2026-02-06 22:08  (31 dias) -> 200
#     from 2026-01-06 22:08 -> to 2026-02-07 22:08             -> 400
#     from 2026-02-06 22:08 -> to 2026-03-06 22:08  (28 dias) -> 200
#     from 2026-02-06 22:08 -> to 2026-03-06 23:08             -> 400
#
# O sea: `to <= from + 1 mes`, con el mismo dia y la misma hora. Un delta fijo
# de 720 h es mas largo que un mes de calendario **solo cuando la ventana
# arranca en febrero**, y ahi la API contesta 400 y tumba el jalon completo.
# Es una mina que explota una vez al ano, justo en el backfill de un año de
# dinero; por eso aqui se avanza por mes de calendario y no por un timedelta.
MAX_AGE = timedelta(days=365)
MAX_LIMIT = 100
DEFAULT_LIMIT = 100

# Estados que acepta el parametro `status` de la API.
API_STATUSES = ("paid", "cancelled")

# Cuantas paginas se permiten por ventana antes de declarar que la paginacion
# esta girando en falso. 100 x 100 = 10,000 transacciones por ventana de 30
# dias; una cafeteria no hace eso, asi que pasar de aqui es un bug, no volumen.
MAX_PAGES_PER_WINDOW = 100

RETRY_STATUSES = (429, 500, 502, 503, 504)

# (status_code, body_bytes)
Transport = Callable[[str, Mapping[str, str]], Tuple[int, bytes]]


class ClipApiError(RuntimeError):
    """Falla al hablar con la API de Clip. El mensaje nunca trae la credencial."""

    def __init__(self, message: str, status: Optional[int] = None) -> None:
        super().__init__(message)
        self.status = status


class ClipAuthError(ClipApiError):
    """401/403: la credencial no sirve (no existe, se revoco o es de otra cuenta)."""


class ClipRateLimitError(ClipApiError):
    """429 persistente despues de los reintentos."""


# --------------------------------------------------------------------------
# Credenciales
# --------------------------------------------------------------------------

def branch_slug(branch: str) -> str:
    """`"Casa Dorelia SJI"` -> `"CASA_DORELIA_SJI"`, para armar el nombre de la variable."""
    slug = re.sub(r"[^0-9A-Za-z]+", "_", (branch or "").strip()).strip("_")
    if not slug:
        raise ClipApiError("la sucursal es obligatoria para resolver la credencial")
    return slug.upper()


def credential_env_names(branch: str) -> Tuple[str, str]:
    """Nombres de las variables de entorno que debe traer el secreto de la sucursal."""
    slug = branch_slug(branch)
    return f"CLIP_API_KEY_{slug}", f"CLIP_SECRET_KEY_{slug}"


@dataclass(frozen=True)
class ClipCredentials:
    """Par api_key/secret_key de UNA cuenta de Clip.

    Cada sucursal (Tecnoparque y SJI) es una cuenta distinta en el panel, asi
    que es un objeto por sucursal: una credencial no ve las ventas de la otra.
    """

    branch: str
    api_key: str
    secret_key: str

    def auth_header(self) -> str:
        token = base64.b64encode(f"{self.api_key}:{self.secret_key}".encode("utf-8")).decode("ascii")
        return f"Basic {token}"

    def fingerprint(self) -> str:
        """Identificador seguro para logs: ultimos 4 del api_key, nada del secreto."""
        tail = self.api_key[-4:] if len(self.api_key) >= 4 else "?"
        return f"...{tail}"

    # Un `print(creds)` o un traceback no deben filtrar el secreto.
    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"ClipCredentials(branch={self.branch!r}, api_key='***{self.fingerprint()}', secret_key='***')"

    __str__ = __repr__


def load_credentials(branch: str, env: Optional[Mapping[str, str]] = None) -> ClipCredentials:
    """Lee la credencial de la sucursal del entorno.

    Busca primero `CLIP_API_KEY_<SUCURSAL>` / `CLIP_SECRET_KEY_<SUCURSAL>` y cae
    a `CLIP_API_KEY` / `CLIP_SECRET_KEY` para una instalacion de una sola cuenta.

    Si falta, el error dice **que variables** faltan (nombres, jamas valores)
    para que el que configura sepa exactamente que cargar en el secreto.
    """
    env = os.environ if env is None else env
    key_name, secret_name = credential_env_names(branch)

    api_key = (env.get(key_name) or "").strip()
    secret_key = (env.get(secret_name) or "").strip()

    fallback_used = False
    if not api_key and not secret_key:
        api_key = (env.get("CLIP_API_KEY") or "").strip()
        secret_key = (env.get("CLIP_SECRET_KEY") or "").strip()
        fallback_used = True

    missing = []
    if not api_key:
        missing.append("CLIP_API_KEY" if fallback_used else key_name)
    if not secret_key:
        missing.append("CLIP_SECRET_KEY" if fallback_used else secret_name)
    if missing:
        raise ClipAuthError(
            "falta la credencial de Clip para la sucursal "
            f"{branch!r}: no hay valor en {' ni en '.join(missing)}. "
            f"Cargala como secreto de Paperclip con esos nombres ({key_name} / {secret_name})."
        )

    return ClipCredentials(branch=branch, api_key=api_key, secret_key=secret_key)


# --------------------------------------------------------------------------
# Ventanas de consulta
# --------------------------------------------------------------------------

def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        # Sin offset se entiende hora local del negocio, igual que en
        # `sales_import.parse_occurred_at`, para no correr el dia 6 horas.
        from sales_import import BUSINESS_TZ

        value = value.replace(tzinfo=BUSINESS_TZ)
    return value.astimezone(timezone.utc)


def add_one_month(value: datetime) -> datetime:
    """`value` mas un mes de calendario, que es el salto que acepta Clip.

    Si el dia no existe en el mes siguiente (31 de enero -> febrero), se recorta
    al ultimo dia de ese mes. Recortar es lo seguro: una ventana mas corta
    siempre se puede pedir, una mas larga la API la rechaza con 400.
    """
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    # Ultimo dia del mes destino, sin usar calendar: el dia 28 existe siempre.
    day = value.day
    while day > 28:
        try:
            return value.replace(year=year, month=month, day=day)
        except ValueError:
            day -= 1
    return value.replace(year=year, month=month, day=day)


def split_window(start: datetime, end: datetime, *,
                 now: Optional[datetime] = None) -> List[Tuple[datetime, datetime]]:
    """Parte `start`..`end` en ventanas que Clip acepta (<= 1 mes cada una).

    Valida los dos limites de la API antes de gastar una llamada: el rango tiene
    que ir hacia adelante y no puede empezar hace mas de un ano.
    """
    start_utc = _as_utc(start)
    end_utc = _as_utc(end)
    now_utc = _as_utc(now) if now is not None else datetime.now(timezone.utc)

    if end_utc <= start_utc:
        raise ClipApiError(
            f"el rango va al reves: `from`={start_utc.isoformat()} no es anterior a "
            f"`to`={end_utc.isoformat()}"
        )
    if start_utc < now_utc - MAX_AGE:
        raise ClipApiError(
            "la API de Clip no devuelve transacciones de mas de un ano de antiguedad; "
            f"`from`={start_utc.date().isoformat()} ya quedo fuera. "
            "Para dias mas viejos hay que usar el export del panel (clip_import.py)."
        )

    windows: List[Tuple[datetime, datetime]] = []
    cursor = start_utc
    while cursor < end_utc:
        stop = min(add_one_month(cursor), end_utc)
        windows.append((cursor, stop))
        cursor = stop
    return windows


def _iso(value: datetime) -> str:
    """ISO-8601 con `Z`, que es la forma que trae la documentacion de Clip."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


# --------------------------------------------------------------------------
# Transporte HTTP
# --------------------------------------------------------------------------

def _urllib_transport(url: str, headers: Mapping[str, str], *,
                      timeout: float = 30.0) -> Tuple[int, bytes]:
    """Transporte por omision, con stdlib: el backend no necesita otra dependencia."""
    request = urllib.request.Request(url, headers=dict(headers), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.getcode(), response.read()
    except urllib.error.HTTPError as exc:  # el cuerpo del error trae el motivo real
        return exc.code, exc.read() or b""
    except urllib.error.URLError as exc:
        raise ClipApiError(f"no se pudo conectar con la API de Clip: {exc.reason}") from exc


def _request_page(url: str, credentials: ClipCredentials, *,
                  transport: Transport,
                  max_retries: int = 3,
                  sleep: Callable[[float], None] = time.sleep,
                  backoff: float = 1.0) -> Dict[str, Any]:
    """Una pagina, con reintento en 429/5xx. Traduce el status a un error con nombre."""
    headers = {**BASE_HEADERS, "Authorization": credentials.auth_header()}

    attempt = 0
    while True:
        status, body = transport(url, headers)

        if status == 200:
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except (ValueError, UnicodeDecodeError) as exc:
                raise ClipApiError(f"la API de Clip devolvio 200 con un cuerpo que no es JSON: {exc}") from exc
            if not isinstance(payload, dict):
                raise ClipApiError(
                    f"la API de Clip devolvio 200 con un {type(payload).__name__} en la raiz, se esperaba un objeto"
                )
            return payload

        if status in (401, 403):
            raise ClipAuthError(
                f"Clip rechazo la credencial de {credentials.branch} (api_key {credentials.fingerprint()}) "
                f"con {status}. La credencial no existe, se revoco, o es de otra cuenta. "
                "Hay que generar otra en el panel de desarrolladores y recargar el secreto.",
                status=status,
            )

        if status in RETRY_STATUSES and attempt < max_retries:
            attempt += 1
            sleep(backoff * (2 ** (attempt - 1)))
            continue

        detail = _error_detail(body)
        if status == 429:
            raise ClipRateLimitError(
                f"Clip sigue limitando la tasa despues de {max_retries} reintentos{detail}",
                status=status,
            )
        raise ClipApiError(f"la API de Clip respondio {status}{detail}", status=status)


def _error_detail(body: bytes) -> str:
    """Motivo legible del cuerpo de error, acotado para no volcar una pagina entera."""
    try:
        text = body.decode("utf-8", errors="replace").strip()
    except Exception:  # pragma: no cover - decode con errors="replace" no lanza
        return ""
    if not text:
        return ""
    try:
        parsed = json.loads(text)
    except ValueError:
        return f": {text[:200]}"
    if isinstance(parsed, dict):
        for field_name in ("message", "error", "detail", "description"):
            value = parsed.get(field_name)
            if isinstance(value, str) and value.strip():
                return f": {value.strip()[:200]}"
    return f": {text[:200]}"


def build_payments_url(start: datetime, end: datetime, *,
                       status: Optional[str] = None,
                       limit: int = DEFAULT_LIMIT,
                       pagination_token: Optional[str] = None,
                       base_url: str = API_BASE) -> str:
    if status is not None and status not in API_STATUSES:
        raise ClipApiError(
            f"`status` invalido: {status!r}. La API solo acepta {' o '.join(API_STATUSES)}."
        )
    if not 1 <= limit <= MAX_LIMIT:
        raise ClipApiError(f"`limit` debe estar entre 1 y {MAX_LIMIT}, llego {limit}")

    params: List[Tuple[str, str]] = [
        ("from", _iso(start)),
        ("to", _iso(end)),
        ("limit", str(limit)),
    ]
    if status:
        params.append(("status", status))
    if pagination_token:
        params.append(("pagination_token", pagination_token))
    return f"{base_url.rstrip('/')}{PAYMENTS_PATH}?{urllib.parse.urlencode(params)}"


def _page_items(payload: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Las transacciones de una pagina, sin depender de un solo nombre de llave."""
    for key in ("payments", "data", "transactions", "items", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    raise ClipApiError(
        "la respuesta de Clip no trae lista de transacciones; llaves vistas: "
        + ", ".join(sorted(payload.keys()))
    )


def _next_token(payload: Mapping[str, Any]) -> Optional[str]:
    meta = payload.get("meta")
    if isinstance(meta, Mapping):
        token = meta.get("pagination_token")
        if isinstance(token, str) and token.strip():
            return token.strip()
    token = payload.get("pagination_token")
    if isinstance(token, str) and token.strip():
        return token.strip()
    return None


def iter_payments(credentials: ClipCredentials, start: datetime, end: datetime, *,
                  status: Optional[str] = None,
                  limit: int = DEFAULT_LIMIT,
                  transport: Optional[Transport] = None,
                  sleep: Callable[[float], None] = time.sleep,
                  max_retries: int = 3,
                  now: Optional[datetime] = None,
                  base_url: str = API_BASE) -> Iterator[Dict[str, Any]]:
    """Transacciones crudas del rango, partiendo ventanas y paginando."""
    transport = _urllib_transport if transport is None else transport

    for window_start, window_end in split_window(start, end, now=now):
        token: Optional[str] = None
        seen_tokens = set()
        for _ in range(MAX_PAGES_PER_WINDOW):
            url = build_payments_url(
                window_start, window_end,
                status=status, limit=limit, pagination_token=token, base_url=base_url,
            )
            payload = _request_page(
                url, credentials,
                transport=transport, sleep=sleep, max_retries=max_retries,
            )
            for item in _page_items(payload):
                yield item

            token = _next_token(payload)
            if not token:
                break
            if token in seen_tokens:
                # Mejor cortar que entregar la misma pagina para siempre: una
                # ingesta que gira en falso duplicaria o colgaria el corte.
                raise ClipApiError(
                    "la paginacion de Clip repitio el mismo `pagination_token`; "
                    f"se corto la ventana {window_start.date().isoformat()}..{window_end.date().isoformat()}"
                )
            seen_tokens.add(token)
        else:
            raise ClipApiError(
                f"la ventana {window_start.date().isoformat()}..{window_end.date().isoformat()} "
                f"paso de {MAX_PAGES_PER_WINDOW} paginas; se corto para no girar en falso"
            )


# --------------------------------------------------------------------------
# Mapeo a la fila que consume el importador
# --------------------------------------------------------------------------

def _number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _gross_amount(payment: Mapping[str, Any]) -> float:
    """Monto del consumo, SIN propina.

    `amount` es el consumo y `total` lo trae con propina. Si falta `amount` se
    reconstruye como `total - tip`; si tampoco hay con que, es mejor fallar que
    cargar una venta inflada con dinero del personal.
    """
    amount = _number(payment.get("amount"))
    if amount is not None:
        return amount

    total = _number(payment.get("total"))
    tip = _number(payment.get("tip")) or 0.0
    if total is not None:
        return round(total - tip, 2)

    raise ClipApiError(
        "una transaccion de Clip llego sin `amount` ni `total`"
        + (f" (receipt_no {payment.get('receipt_no')})" if payment.get("receipt_no") else "")
    )


def _status(payment: Mapping[str, Any]) -> str:
    """Estado del cobro. **`status` vacio significa cancelada**, no cobrada.

    Verificado contra la API el 2026-10-04: `?status=cancelled` devuelve
    exactamente los renglones cuyo `status` llega como cadena vacia, y
    `?status=paid` los omite. La API siempre manda el campo, asi que vacio no es
    "no se sabe": es el estado.

    Esta rama existe porque `classify_status("")` devuelve `"paid"`, y con razon:
    en el export del panel una columna de estado ausente si significa cobrada.
    En la API significa lo contrario. Sin esto, una cancelacion entra como venta
    — paso con el cobro cancelado de $108 del 21/09 en Tecnoparque, que estuvo
    cargado como venta hasta BOS-119.
    """
    raw = payment.get("status")
    if raw is None or not str(raw).strip():
        return "reversed"
    return classify_status(raw)


def _card_info(payment: Mapping[str, Any]) -> Dict[str, Optional[str]]:
    """`card` como tres cadenas limpias, exista o no el objeto."""
    card = payment.get("card") if isinstance(payment.get("card"), Mapping) else {}
    brand = (_text(card.get("brand")) or "").upper() or None
    return {
        "brand": brand,
        "issuer": _text(card.get("issuer")),
        "last4": _text(card.get("last4")),
    }


def _has_card_identity(info: Mapping[str, Optional[str]]) -> bool:
    """?Hay una tarjeta real detras de este cobro?

    Clip rellena los tres campos aunque no haya plastico: una marca `XX` con
    `last4` `0000` y sin emisor es el relleno, no una tarjeta.
    """
    if info.get("issuer"):
        return True
    brand = info.get("brand")
    if brand and brand != "XX":
        return True
    return info.get("last4") not in (None, "", "0000")


def _payment_method(payment: Mapping[str, Any]) -> str:
    """Vocabulario de `SaleBase.payment_method` a partir de lo que trae la API.

    -> `"tarjeta"` | `"vales"` | `"otro"` | `"efectivo"` | `"transferencia"`.

    El orden importa y es el de la confianza en la fuente:

    1. Si Clip **lo dice con palabras** (`payment_method`/`sub_type` que se
       normaliza a efectivo o transferencia), se le cree. Hoy no manda ninguno
       de los dos, y esta rama es justamente la que hace que el dia que empiece
       a mandar efectivo entre rotulado solo, sin tocar codigo.
    2. `DEBIT`/`CREDIT` es tarjeta bancaria.
    3. `OTHER` **con emisor** es vale (Pluxee, Edenred, Toka, Todito...). No es
       tarjeta: el reparto y la comision son otros, y mezclarlo en "tarjeta"
       esconde ~12% del dinero de Tecnoparque.
    4. `OTHER` **sin tarjeta identificable** es `"otro"`, no efectivo. Decirle
       efectivo seria inventar: la API no lo nombra y es lo que esta en consulta
       en BOS-119. `"otro"` se ve en el tablero y se puede confirmar; "tarjeta"
       se hubiera quedado escondido para siempre.
    """
    for candidate in (payment.get("payment_method"), payment.get("sub_type")):
        if not candidate:
            continue
        method = normalize_payment_method(candidate)
        if method in ("efectivo", "transferencia"):
            return method

    raw = (_text(payment.get("payment_method")) or "").upper()
    if raw in ("DEBIT", "CREDIT"):
        return "tarjeta"

    info = _card_info(payment)
    if raw == "OTHER" and info["issuer"]:
        return "vales"
    if _has_card_identity(info):
        return "tarjeta"
    return "otro"


def map_payment(payment: Mapping[str, Any], *, branch: str, index: int = 0) -> Dict[str, Any]:
    """Una transaccion de la API -> fila para `sales_import.normalize_row`.

    La fila queda con las mismas llaves que produce `clip_import.parse_sales`,
    asi que el importador no distingue si el dato vino del export o de la API
    (solo lo marca en `source`).
    """
    if not isinstance(payment, Mapping):
        raise ClipApiError(f"la transaccion {index} no es un objeto, es {type(payment).__name__}")

    receipt_no = _text(payment.get("receipt_no"))
    transaction_id = _text(payment.get("id")) or _text(payment.get("transaction_id")) or receipt_no

    occurred_at = _text(payment.get("created_at")) or _text(payment.get("paid_at"))
    if not occurred_at:
        raise ClipApiError(
            "una transaccion de Clip llego sin `created_at`"
            + (f" (receipt_no {receipt_no})" if receipt_no else "")
        )

    info = _card_info(payment)
    # El emisor entra a `notes` desde BOS-119: es lo unico que dice *que* vale
    # fue (Pluxee, Edenred...), y sin el un renglon de vales es indistinguible
    # de una tarjeta bancaria una vez cargado.
    notes_bits = [bit for bit in (
        _text(payment.get("sub_type")),
        info["brand"],
        info["issuer"],
        f"****{info['last4']}" if info["last4"] else None,
    ) if bit]

    return {
        "occurred_at": occurred_at,
        "gross_amount": _gross_amount(payment),
        "status": _status(payment),
        "payment_method": _payment_method(payment),
        "transaction_id": transaction_id,
        "receipt_no": receipt_no,
        "branch": branch,
        "tip": _number(payment.get("tip")),
        "fee": _number(payment.get("fee")) if payment.get("fee") is not None
               else _number(payment.get("commission")),
        "notes": " ".join(notes_bits) or None,
        "source_row": index,
    }


def fetch_rows(credentials: ClipCredentials, start: datetime, end: datetime,
               **kwargs: Any) -> List[Dict[str, Any]]:
    """Filas listas para `plan_import`, en orden de llegada."""
    return [
        map_payment(payment, branch=credentials.branch, index=index)
        for index, payment in enumerate(iter_payments(credentials, start, end, **kwargs))
    ]


def summarize_corte(rows: Sequence[Mapping[str, Any]], *, branch: str) -> Dict[str, Any]:
    """Corte por dia de operacion, sin escribir nada y sin tocar Mongo.

    Es la vista que se aprueba ANTES de cargar: pasa las filas por el mismo
    `plan_import` que hara la carga, asi que el total de aqui es exactamente el
    que se insertaria (IVA desglosado, propinas fuera, devoluciones fuera).

    El dia es el dia local del negocio (`business_date`, UTC-6), no el dia UTC:
    una venta de las 18:08 de CDMX llega de Clip como `00:08Z` del dia
    siguiente, y agruparla por UTC la correria de dia.
    """
    from sales_import import SOURCE_CLIP_API, plan_import  # import tardio: evita ciclo

    plan = plan_import(list(rows), cafeteria_id=f"corte-{branch}", source=SOURCE_CLIP_API)
    summary = plan.summary()

    por_dia: Dict[str, Dict[str, Any]] = {}
    for doc in plan.documents:
        dia = por_dia.setdefault(
            doc["business_date"], {"date": doc["business_date"], "transactions": 0, "gross": 0.0}
        )
        dia["transactions"] += 1
        dia["gross"] = round(dia["gross"] + doc["total"], 2)

    return {
        "branch": branch,
        "transactions": summary["to_insert"],
        "skipped": summary["skipped"],
        "skipped_reasons": summary["skipped_reasons"],
        "rejected": summary["rejected"],
        "gross_total": summary["gross_total"],
        "subtotal_total": summary["subtotal_total"],
        "tax_total": summary["tax_total"],
        "gross_by_payment_method": summary["gross_by_payment_method"],
        # Las propinas se reportan aparte a proposito: son del personal, no son
        # venta, y nunca entran al total que se carga.
        "tips_excluded": round(sum(float(r.get("tip") or 0.0) for r in rows), 2),
        "cash_coverage": summary["cash_coverage"],
        "by_business_date": [por_dia[dia] for dia in sorted(por_dia)],
    }


def summarize_census(payments: Iterable[Mapping[str, Any]], *,
                     branch: str) -> Dict[str, Any]:
    """Censo de la taxonomia cruda que entrega la API. No carga nada.

    Existe para contestar con dato, y no con memoria, la unica pregunta que se
    repite en esta tarea: **?ya llega el efectivo?** (BOS-119). Agrupa por
    `(payment_method, sub_type, card.brand, card.issuer, status)`, que es la
    tupla donde apareceria si Clip empezara a mandarlo.

    `efectivo_en_la_api` es el veredicto, y sale de contar renglones: el dia que
    sea `true`, el efectivo ya viene y hay que cargarlo. Mientras sea `false`,
    el total de este camino es un **piso**.

    Tambien saca aparte los renglones **sin tarjeta identificable**, que son los
    unicos candidatos a efectivo. Ojo con el `status`: medido en 360 dias, los
    dos que existen son cancelaciones (`status` vacio), no efectivo.
    """
    buckets: Dict[Tuple[str, ...], Dict[str, Any]] = {}
    sin_tarjeta: List[Dict[str, Any]] = []
    por_metodo: Dict[str, Dict[str, Any]] = {}
    total = 0

    for payment in payments:
        total += 1
        info = _card_info(payment)
        method = _payment_method(payment)
        status = _status(payment)
        amount = _gross_amount(payment)

        key = (
            (_text(payment.get("payment_method")) or "(vacio)").upper(),
            _text(payment.get("sub_type")) or "(vacio)",
            info["brand"] or "(vacio)",
            info["issuer"] or "(vacio)",
            status,
            method,
        )
        bucket = buckets.setdefault(key, {
            "payment_method_api": key[0],
            "sub_type": key[1],
            "card_brand": key[2],
            "card_issuer": key[3],
            "status": status,
            "payment_method": method,
            "transactions": 0,
            "gross_amount": 0.0,
        })
        bucket["transactions"] += 1
        bucket["gross_amount"] = round(bucket["gross_amount"] + amount, 2)

        # Solo lo cobrado suma: una cancelacion no es venta (ver `_status`).
        if status == "paid":
            agg = por_metodo.setdefault(method, {"transactions": 0, "gross_amount": 0.0})
            agg["transactions"] += 1
            agg["gross_amount"] = round(agg["gross_amount"] + amount, 2)

        if not _has_card_identity(info):
            sin_tarjeta.append({
                "receipt_no": _text(payment.get("receipt_no")),
                "occurred_at": _text(payment.get("created_at")),
                "gross_amount": amount,
                "status": status,
                "sub_type": _text(payment.get("sub_type")),
                "payment_method": method,
            })

    efectivo = por_metodo.get("efectivo", {}).get("transactions", 0)
    return {
        "branch": branch,
        "transactions": total,
        "by_taxonomy": sorted(buckets.values(),
                              key=lambda b: (-b["transactions"], b["payment_method_api"])),
        "gross_by_payment_method": por_metodo,
        "rows_without_card": sin_tarjeta,
        "efectivo_en_la_api": efectivo > 0,
        "note": (
            "efectivo_en_la_api: false -> el total de este camino es un piso. "
            "Los renglones sin tarjeta con `status` vacio son cancelaciones, no efectivo."
        ) if efectivo == 0 else (
            "efectivo_en_la_api: true -> Clip ya manda efectivo; hay que cargarlo y "
            "dejar de llamarle piso al total."
        ),
    }


# --------------------------------------------------------------------------
# Esquema: que campos EXISTEN, no solo que valores trajeron
# --------------------------------------------------------------------------
#
# El censo agrupa por la tupla donde **esperamos** ver el efectivo. Eso contesta
# "no llego", pero no contesta "no cabe": si Clip rotulara el efectivo en un
# campo que el censo no mira, el censo diria cero igual. Son dos afirmaciones
# distintas y solo la segunda cierra la pregunta.
#
# Por eso aqui no se agrupa por campos elegidos a mano: se recorre **todo** el
# arbol de cada transaccion y se levanta el inventario de rutas que la API
# manda, con los valores que toma cada una. Medido el 2026-10-04 (BOS-151) en
# las dos cuentas, 360 dias, 2,332 transacciones: **19 rutas, las mismas 19 en
# todas**, y `payment_method` toma exactamente tres valores (`CREDIT`, `DEBIT`,
# `OTHER`). No hay campo donde quepa un cobro en efectivo.

# Cuantos valores distintos se guardan por campo antes de darlo por abierto.
MAX_DISTINCT_VALUES = 12

# Etiquetas que delatarian un cobro en efectivo, en cualquier campo de cualquier
# superficie (transacciones o depositos).
CASH_LABELS = ("cash", "efectivo", "contado")


def _new_field_slot() -> Dict[str, Any]:
    return {"present": 0, "nulls": 0, "values": set(),
            "open_set": False, "container": False}


def _walk_fields(value: Any, path: str, fields: Dict[str, Dict[str, Any]]) -> None:
    """Registra cada ruta del arbol y los valores que toma (hasta cerrar el set)."""
    if isinstance(value, Mapping):
        if path:
            # Un contenedor no tiene valores propios. Reportarle `values: []`
            # se leeria como "nunca trajo nada", que es un cero inventado.
            fields.setdefault(path, _new_field_slot())["container"] = True
        for key, item in value.items():
            child = f"{path}.{key}" if path else str(key)
            fields.setdefault(child, _new_field_slot())["present"] += 1
            _walk_fields(item, child, fields)
        return

    if isinstance(value, (list, tuple)):
        if path:
            fields.setdefault(path, _new_field_slot())["container"] = True
        for item in value:
            _walk_fields(item, f"{path}[]", fields)
        return

    if not path:
        return

    slot = fields.setdefault(path, _new_field_slot())
    if value is None:
        slot["nulls"] += 1
        return
    if slot["open_set"]:
        return
    text = str(value)
    # Un campo con valores largos (montos, ids, correos) no se enumera: lo que
    # importa de el es que existe, no la lista.
    if len(text) > 32 or len(slot["values"]) >= MAX_DISTINCT_VALUES:
        slot["open_set"] = True
        slot["values"] = set()
        return
    slot["values"].add(text)


def _mentions_cash(payment: Mapping[str, Any]) -> bool:
    """?Alguna parte del JSON de esta transaccion dice efectivo, en cualquier campo?

    Barrido de texto sobre la transaccion completa, no sobre los campos que se
    nos ocurrieron. Es la unica forma de decir "no aparece en ningun lado" sin
    haber elegido primero donde mirar.
    """
    blob = json.dumps(payment, ensure_ascii=False).lower()
    return any(label in blob for label in CASH_LABELS)


def summarize_schema(payments: Iterable[Mapping[str, Any]], *,
                     branch: str) -> Dict[str, Any]:
    """Inventario del esquema que entrega `/payments`, campo por campo.

    Contesta la version fuerte de la pregunta de BOS-151: no "?llego efectivo?"
    sino "?existe algun campo donde pudiera llegar?". Reporta aparte:

    - `fields`: toda ruta que la API mando, con `present`, `nulls` y los valores
      que toma cuando son pocos. Si cambia el esquema, cambia esta lista.
    - `card_identity`: cuantas transacciones llegan **sin** marca ni ultimos 4.
      Esos son los unicos candidatos a efectivo.
    - `cardless_receipts` / `mentions_cash`: los renglones concretos, por folio,
      para que el que lea pueda ir a verlos uno por uno.

    `efectivo_en_el_esquema` es el veredicto, y es `true` solo si algo nombra
    efectivo. No se infiere de un conteo en cero: un cero puede ser un dia sin
    efectivo, pero un esquema sin campo es estructural.
    """
    fields: Dict[str, Dict[str, Any]] = {}
    total = 0
    sin_tarjeta: List[str] = []
    menciona: List[str] = []
    metodos: Dict[str, int] = {}

    for payment in payments:
        total += 1
        _walk_fields(payment, "", fields)

        metodo = (_text(payment.get("payment_method")) or "(vacio)").upper()
        metodos[metodo] = metodos.get(metodo, 0) + 1

        folio = _text(payment.get("receipt_no")) or f"(sin folio #{total})"
        if not _has_card_identity(_card_info(payment)):
            sin_tarjeta.append(folio)
        if _mentions_cash(payment):
            menciona.append(folio)

    return {
        "branch": branch,
        "transactions": total,
        "fields": [
            {
                "path": path,
                "present": slot["present"],
                "nulls": slot["nulls"],
                "container": slot["container"],
                "values": None if (slot["open_set"] or slot["container"])
                else sorted(slot["values"]),
            }
            for path, slot in sorted(fields.items())
        ],
        "payment_method_values": dict(sorted(metodos.items(), key=lambda kv: -kv[1])),
        "card_identity": {
            "with_card": total - len(sin_tarjeta),
            "without_card": len(sin_tarjeta),
        },
        "cardless_receipts": sin_tarjeta,
        "mentions_cash": menciona,
        "efectivo_en_el_esquema": bool(menciona),
        "note": (
            "efectivo_en_el_esquema: false -> ninguna de las rutas del esquema "
            "nombra efectivo, en ningun renglon. Los renglones sin tarjeta hay "
            "que cruzarlos con ?status=cancelled antes de llamarles efectivo."
        ) if not menciona else (
            "efectivo_en_el_esquema: true -> hay renglones que nombran efectivo; "
            "revisar `mentions_cash` y cargarlos."
        ),
    }


# Parametros que se le prueban al endpoint para ver si el filtro existe.
#
# Esto necesita un control o no mide nada: si `payment_method=CASH` contesta
# 200, puede ser que el filtro exista y no haya efectivo, **o** que el
# parametro se ignore. Se distinguen mandando ademas un valor absurdo
# (`_CONTROL_NONSENSE`) y un parametro que si se sabe validado (`status`):
#
#     payment_method=CASH           -> 200, 36 filas
#     payment_method=ZZZZZ_CONTROL  -> 200, 36 filas   <- mismas filas: se ignora
#     status=ZZZZ                   -> 400 payclip.bad.request  <- si valida
#
# O sea: la API valida lo que conoce, y `payment_method` no es un filtro. No hay
# cajon de efectivo que pedirle.
_CONTROL_NONSENSE = "ZZZZZ_CONTROL"


def probe_method_filter(credentials: ClipCredentials, *,
                        days: int = 7,
                        transport: Optional[Transport] = None,
                        now: Optional[datetime] = None) -> Dict[str, Any]:
    """?Se le puede *pedir* a `/payments` el efectivo con un filtro?

    Devuelve el resultado de cada intento y un veredicto. `filtro_existe` solo
    es `true` si el valor absurdo se rechaza y el bueno no: si los dos pasan,
    el parametro se esta ignorando y el 200 no significa nada.
    """
    transport = _urllib_transport if transport is None else transport
    end = (now or datetime.now(timezone.utc)) - timedelta(hours=6)
    start = end - timedelta(days=max(1, days))

    headers = dict(BASE_HEADERS)
    headers["Authorization"] = credentials.auth_header()

    intentos: List[Dict[str, Any]] = []
    for param, value in (
        ("payment_method", "CASH"),
        ("payment_method", _CONTROL_NONSENSE),
        ("status", "ZZZZ"),
    ):
        params = [("from", _iso(start)), ("to", _iso(end)),
                  ("limit", str(DEFAULT_LIMIT)), (param, value)]
        url = f"{API_BASE.rstrip('/')}{PAYMENTS_PATH}?{urllib.parse.urlencode(params)}"
        status_code, body = transport(url, headers)
        filas: Optional[int] = None
        if status_code == 200:
            try:
                filas = len(_page_items(json.loads(body.decode("utf-8"))))
            except (ValueError, ClipApiError):
                filas = None
        intentos.append({"param": param, "value": value,
                         "http_status": status_code, "rows": filas})

    por_valor = {(i["param"], i["value"]): i for i in intentos}
    cash = por_valor[("payment_method", "CASH")]
    control = por_valor[("payment_method", _CONTROL_NONSENSE)]
    valida = por_valor[("status", "ZZZZ")]

    ignorado = (cash["http_status"] == 200 and control["http_status"] == 200
                and cash["rows"] == control["rows"])
    return {
        "branch": credentials.branch,
        "window": {"from": _iso(start), "to": _iso(end)},
        "attempts": intentos,
        "api_valida_parametros": valida["http_status"] == 400,
        "filtro_payment_method_existe": not ignorado,
        "note": (
            "El parametro `payment_method` se ignora: el valor bueno y el absurdo "
            "devuelven las mismas filas, mientras `status=ZZZZ` si contesta 400. "
            "No hay filtro con el que pedirle efectivo a este endpoint."
        ) if ignorado else (
            "El filtro `payment_method` si se valida; vale la pena pedirle efectivo "
            "y medir el resultado."
        ),
    }


# --------------------------------------------------------------------------
# Depositos (la otra superficie que trae `payment_method`)
# --------------------------------------------------------------------------
#
# `/payments` no es el unico endpoint que rotula el metodo de pago: el reporte
# desglosado de depositos tambien trae `payment_method` por transaccion. El
# censo nunca lo midio, asi que mientras no se pruebe, "la API no da efectivo"
# era una afirmacion sobre UNA ruta, no sobre la cuenta.
#
# Medido el 2026-10-04 (BOS-151) **se lee bien**, en las dos sucursales. El
# heartbeat anterior reporto `401` en los cinco rellenos de credencial y
# concluyo que la cuenta no tiene alcance de depositos: era falso, y eran tres
# bugs nuestros disfrazados de respuesta de Clip (ver `deposit_auth_schemes`,
# `build_settlements_url` y `settlement_detail_url`). Corregidos:
#
#     GET /payments      Basic -> 200   (82 cobros en 20 dias, control positivo)
#     GET /settlements   Basic -> 200   (SJI: 6 depositos, 38 transacciones)
#
# Las 38 transacciones del desglose llegan **todas con tarjeta** (marca y
# ultimos 4), asi que tampoco hay efectivo ahi — y estructuralmente no puede
# haberlo: un deposito es dinero que Clip disperso, y el efectivo nunca lo toca.
# Eso ya es una medicion. Aun asi este comando sigue reportando `acceso` aparte
# de `efectivo_en_depositos`, porque el dia que vuelva un 401 hay que publicarlo
# como "no puedes ver", no como cero.

SETTLEMENTS_PATH = "/settlements"

# Clip solo deja 90 dias de antiguedad en el resumen de depositos.
MAX_DEPOSIT_AGE = timedelta(days=90)


def _business_date(value: datetime) -> date:
    """La fecha de calendario del negocio, no la de UTC.

    `/settlements` valida `to` contra **su** dia, no contra UTC. Despues de las
    18:00 de CDMX, `_as_utc(now).date()` ya es el dia siguiente y Clip contesta
    `400 "[to] date should be before or equals current date"`. Pasó de verdad el
    2026-10-04 y se veia igual que un rango mal pedido.
    """
    from sales_import import BUSINESS_TZ

    if value.tzinfo is None:
        value = value.replace(tzinfo=BUSINESS_TZ)
    return value.astimezone(BUSINESS_TZ).date()


def build_settlements_url(start: datetime, end: datetime, *,
                          base_url: str = API_BASE) -> str:
    """Resumen de depositos. A diferencia de `/payments`, aqui van fechas sin hora."""
    if end < start:
        raise ClipApiError(
            f"rango invertido: `to` ({end.date()}) es anterior a `from` ({start.date()})"
        )
    params = [
        ("from", _business_date(start).isoformat()),
        ("to", _business_date(end).isoformat()),
    ]
    return f"{base_url.rstrip('/')}{SETTLEMENTS_PATH}?{urllib.parse.urlencode(params)}"


def deposit_auth_schemes(credentials: ClipCredentials) -> List[Tuple[str, Dict[str, str]]]:
    """Los encabezados plausibles, en orden.

    La doc de depositos pide `x-api-key` mientras que `/payments` acepta Basic;
    probar los dos es lo que separa "ruta equivocada" de "esquema equivocado".

    Y "probar `x-api-key`" no es una sola cosa. La pagina de autenticacion
    (`developer.clip.mx/reference/token-de-autenticacion`) define el *token*
    como la cadena completa `Basic base64(API_KEY:SECRET_KEY)` y dice que ese
    token "puede ser ingresado en el campo **x-api-key** o **authorization**".
    O sea: en `x-api-key` va el token entero, con la palabra `Basic` incluida.
    La primera version de este probe mandaba ahi el api_key pelon (un UUID),
    que no es el token — asi que su 401 no probaba falta de alcance, probaba un
    encabezado mal armado. Van los tres rellenos posibles para que el 401, si
    sigue, sea del alcance y no nuestro.
    """
    token = credentials.auth_header()               # "Basic <base64>"
    base64_only = token.split(" ", 1)[1]            # el base64 sin la palabra
    return [
        ("basic", {"Authorization": token}),
        ("x-api-key-token", {"x-api-key": token}),
        ("x-api-key-base64", {"x-api-key": base64_only}),
        ("x-api-key-apikey", {"x-api-key": credentials.api_key}),
        ("x-api-key+basic", {
            "x-api-key": token,
            "Authorization": token,
        }),
    ]


def settlement_detail_url(item: Mapping[str, Any], *,
                          base_url: str = API_BASE) -> Optional[str]:
    """La ruta del desglose de UN deposito, tomada de `links.self.href`.

    El `settlement_report_id` que trae el resumen (`OV6QJWWWH`) **no** sirve en
    la ruta de detalle: Clip contesta
    `400 {"error_code":"V01","description":"settlement_id Invalid pattern"}`
    porque ahi espera el UUID que viene en `links.self.href`. Son dos
    identificadores distintos para el mismo deposito, y armar la URL con el
    legible da un 400 que se lee igual que "no hay desglose".
    """
    links = item.get("links")
    href: Optional[str] = None
    if isinstance(links, Mapping):
        self_link = links.get("self")
        if isinstance(self_link, Mapping):
            href = _text(self_link.get("href")) or None
        elif isinstance(self_link, str):
            href = _text(self_link) or None
    if href:
        if href.startswith("http://") or href.startswith("https://"):
            return href
        return f"{base_url.rstrip('/')}/{href.lstrip('/')}"

    # Sin `links` queda el id legible, que probablemente de 400. Se intenta
    # igual para que el fallo quede registrado como intento, no como silencio.
    report_id = _text(item.get("settlement_report_id"))
    if not report_id:
        return None
    return (
        f"{base_url.rstrip('/')}{SETTLEMENTS_PATH}/"
        f"{urllib.parse.quote(report_id, safe='')}"
    )


def _deposit_rows(detail: Mapping[str, Any]) -> Iterator[Dict[str, Any]]:
    """Las transacciones de un desglose, sin apostar a un solo nombre de llave.

    Un `details` por dia puede anidar las transacciones del dia; de ahi el
    segundo nivel.
    """
    for key in ("details", "transactions", "payments", "data", "items"):
        value = detail.get(key)
        if not isinstance(value, list):
            continue
        for row in value:
            if not isinstance(row, Mapping):
                continue
            nested = next(
                (row[inner] for inner in ("transactions", "payments", "details", "items")
                 if isinstance(row.get(inner), list)),
                None,
            )
            if nested is None:
                yield dict(row)
            else:
                for sub in nested:
                    if isinstance(sub, Mapping):
                        yield dict(sub)
        return
    inner_settlement = detail.get("settlement")
    if isinstance(inner_settlement, Mapping):
        yield from _deposit_rows(inner_settlement)


def probe_deposits(credentials: ClipCredentials, *,
                   days: int = 90,
                   transport: Transport = _urllib_transport,
                   now: Optional[datetime] = None) -> Dict[str, Any]:
    """Contesta dos cosas distintas: si podemos leer depositos, y si traen efectivo.

    Un 401 **no** se cuenta como "no hay efectivo": se reporta como falta de
    acceso, con el esquema de autenticacion que se probo. Por eso esta funcion
    no lanza en 401 — el 401 es justamente el resultado que hay que publicar.
    """
    end = _as_utc(now or datetime.now(timezone.utc))
    start = end - min(timedelta(days=max(1, days)), MAX_DEPOSIT_AGE)
    url = build_settlements_url(start, end)

    intentos: List[Dict[str, Any]] = []
    aceptado: Optional[Tuple[str, Dict[str, str], Dict[str, Any]]] = None
    for scheme, headers in deposit_auth_schemes(credentials):
        status, body = transport(url, {**BASE_HEADERS, **headers})
        intentos.append({"auth": scheme, "status": status,
                         "detail": _error_detail(body).lstrip(": ") or None})
        if status == 200:
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except (ValueError, UnicodeDecodeError) as exc:
                raise ClipApiError(
                    f"el resumen de depositos devolvio 200 con un cuerpo que no es JSON: {exc}"
                ) from exc
            if isinstance(payload, Mapping):
                aceptado = (scheme, headers, dict(payload))
                break

    base = {
        "branch": credentials.branch,
        # Las fechas que de verdad viajaron en la URL, en dia de CDMX. Reportar
        # el dia de UTC aqui es como se esconde un `to` en el futuro.
        "window": {"from": _business_date(start).isoformat(),
                   "to": _business_date(end).isoformat()},
        "attempts": intentos,
    }

    if aceptado is None:
        return {
            **base,
            "acceso": False,
            "efectivo_en_depositos": None,
            "note": (
                "Ningun relleno de credencial entro a /settlements. Mira `attempts` "
                "antes de concluir falta de alcance: un 400 habla del rango (la "
                "credencial ya paso), un 401 de la credencial, un 403 del WAF. "
                "`efectivo_en_depositos: null` es a proposito: no se puede afirmar "
                "que no hay efectivo en un reporte que no se pudo leer."
            ),
        }

    scheme, headers, payload = aceptado
    settlements = payload.get("settlements")
    settlements = settlements if isinstance(settlements, list) else []

    metodos: Dict[str, int] = {}
    transacciones = 0
    leidos = 0
    fallidos: List[Dict[str, Any]] = []
    for item in settlements:
        if not isinstance(item, Mapping):
            continue
        report_id = _text(item.get("settlement_report_id")) or "(sin id)"
        detail_url = settlement_detail_url(item)
        if not detail_url:
            fallidos.append({"settlement_report_id": report_id,
                             "status": "sin links.self.href ni id"})
            continue
        status, body = transport(detail_url, {**BASE_HEADERS, **headers})
        if status != 200:
            fallidos.append({"settlement_report_id": report_id, "status": status})
            continue
        try:
            detail = json.loads(body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            fallidos.append({"settlement_report_id": report_id, "status": "cuerpo no JSON"})
            continue
        if not isinstance(detail, Mapping):
            fallidos.append({"settlement_report_id": report_id, "status": "raiz no es objeto"})
            continue
        leidos += 1
        for row in _deposit_rows(detail):
            transacciones += 1
            label = (_text(row.get("payment_method")) or "(vacio)").upper()
            metodos[label] = metodos.get(label, 0) + 1

    efectivo = sum(n for label, n in metodos.items()
                   if any(hint in label.lower() for hint in CASH_LABELS))
    return {
        **base,
        "acceso": True,
        "auth": scheme,
        "deposits": len(settlements),
        "deposits_read": leidos,
        "deposits_failed": fallidos,
        "transactions": transacciones,
        "by_payment_method": dict(sorted(metodos.items(), key=lambda kv: (-kv[1], kv[0]))),
        # Sin una sola transaccion leida no hay nada que clasificar. Un `false`
        # aqui seria el mismo error que contar un 401 como cero: afirmar sobre un
        # reporte vacio. `null` es el unico valor honesto.
        "efectivo_en_depositos": (efectivo > 0) if transacciones else None,
        "note": (
            "efectivo_en_depositos: null -> la ventana entro (200) pero no trajo "
            "ninguna transaccion que clasificar. Hay acceso; lo que falta es un "
            "periodo con depositos. No es un cero medido."
        ) if not transacciones else (
            "efectivo_en_depositos: false -> el reporte de depositos tampoco trae "
            "efectivo, que es lo esperado: Clip no deposita dinero que nunca toco."
        ) if efectivo == 0 else (
            "efectivo_en_depositos: true -> hay efectivo en el desglose de depositos; "
            "ese es el camino de carga y el corte deja de ser la unica fuente."
        ),
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _parse_day(value: str, *, end_of_day: bool = False) -> datetime:
    """`2026-09-21` o ISO completo. Sin hora, se toma el dia completo del negocio."""
    raw = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ClipApiError(f"fecha invalida: {value!r} (se espera 2026-09-21 o ISO-8601)") from exc
    if len(value.strip()) == 10 and end_of_day:
        parsed = parsed + timedelta(days=1) - timedelta(seconds=1)
    return parsed


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="clip_api",
        description="Lee ventas de la API de Clip. La credencial se toma del entorno.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    probe = sub.add_parser("probe", help="valida la credencial con una consulta corta")
    probe.add_argument("--branch", required=True, help="sucursal (p. ej. sji o tecnoparque)")
    probe.add_argument("--hours", type=int, default=24, help="ventana a consultar (default 24 h)")

    pull = sub.add_parser("pull", help="baja las transacciones de un rango")
    pull.add_argument("--branch", required=True)
    pull.add_argument("--from", dest="start", required=True)
    pull.add_argument("--to", dest="end", required=True)
    pull.add_argument("--status", choices=API_STATUSES, default=None)
    pull.add_argument("--json", dest="json_out", help="archivo donde dejar las filas")

    corte = sub.add_parser("corte", help="corte por dia de operacion, sin escribir nada")
    corte.add_argument("--branch", required=True)
    corte.add_argument("--from", dest="start", required=True)
    corte.add_argument("--to", dest="end", required=True)

    census = sub.add_parser(
        "census",
        help="censo de la taxonomia cruda: contesta si ya llega efectivo (BOS-119)",
    )
    census.add_argument("--branch", required=True)
    census.add_argument("--days", type=int, default=360,
                        help="cuantos dias hacia atras (default 360; el tope de Clip es un ano)")

    schema = sub.add_parser(
        "schema",
        help="inventario del esquema de /payments: ?existe campo donde quepa el efectivo? (BOS-151)",
    )
    schema.add_argument("--branch", required=True)
    schema.add_argument("--days", type=int, default=360,
                        help="cuantos dias hacia atras (default 360; el tope de Clip es un ano)")

    deposits = sub.add_parser(
        "deposits",
        help="prueba si la cuenta puede leer el reporte de depositos, y si trae efectivo (BOS-151)",
    )
    deposits.add_argument("--branch", required=True)
    deposits.add_argument("--days", type=int, default=90,
                          help="cuantos dias hacia atras (default 90, que es el tope de Clip)")

    args = parser.parse_args(argv)

    try:
        credentials = load_credentials(args.branch)
    except ClipApiError as exc:
        print(f"ERROR: {exc}")
        return 2

    try:
        if args.command == "probe":
            end = datetime.now(timezone.utc)
            start = end - timedelta(hours=max(1, args.hours))
            rows = fetch_rows(credentials, start, end)
            print(json.dumps({
                "branch": credentials.branch,
                "api_key": f"***{credentials.fingerprint()}",
                "window": {"from": _iso(start), "to": _iso(end)},
                "transactions": len(rows),
                "gross_amount": round(sum(r["gross_amount"] for r in rows if r["status"] == "paid"), 2),
                "note": "La API no incluye efectivo; el corte queda corto por diseno.",
            }, indent=2, ensure_ascii=False))
            return 0

        if args.command == "census":
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=max(1, args.days))
            print(json.dumps(
                summarize_census(iter_payments(credentials, start, end),
                                 branch=credentials.branch),
                indent=2, ensure_ascii=False))
            return 0

        if args.command == "schema":
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=max(1, args.days))
            report = summarize_schema(iter_payments(credentials, start, end),
                                      branch=credentials.branch)

            # El cruce que cierra la pregunta: los unicos renglones sin tarjeta
            # tienen que ser los mismos que Clip devuelve bajo
            # `?status=cancelled`. Si coinciden, no son efectivo: son
            # cancelaciones, y lo dice la API con su propio filtro. Si NO
            # coinciden, quedo un renglon sin explicar y hay que ir a verlo.
            canceladas = {
                _text(p.get("receipt_no"))
                for p in iter_payments(credentials, start, end, status="cancelled")
            }
            sin_tarjeta = set(report["cardless_receipts"])
            report["cancelled_receipts"] = len(canceladas)
            report["cardless_not_cancelled"] = sorted(sin_tarjeta - canceladas)
            report["cardless_explained_by_cancellation"] = not (sin_tarjeta - canceladas)

            report["payment_method_filter"] = probe_method_filter(credentials)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0

        if args.command == "deposits":
            print(json.dumps(probe_deposits(credentials, days=args.days),
                             indent=2, ensure_ascii=False))
            return 0

        if args.command == "corte":
            rows = fetch_rows(
                credentials,
                _parse_day(args.start),
                _parse_day(args.end, end_of_day=True),
            )
            print(json.dumps(summarize_corte(rows, branch=credentials.branch),
                             indent=2, ensure_ascii=False))
            return 0

        rows = fetch_rows(
            credentials,
            _parse_day(args.start),
            _parse_day(args.end, end_of_day=True),
            status=args.status,
        )
        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as handle:
                json.dump(rows, handle, indent=2, ensure_ascii=False)
            print(f"{len(rows)} transacciones -> {args.json_out}")
        else:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    except ClipApiError as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
