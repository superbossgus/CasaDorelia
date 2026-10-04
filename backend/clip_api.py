"""
Cliente de la API de transacciones de Clip (via credenciales, no via export).

Modulo puro: no toca Mongo, no importa FastAPI y **nunca** escribe la credencial
en un log, en un error ni en un repr. Entrega filas con la misma forma que
`clip_import.parse_sales`, para que `sales_import.plan_import` las cargue por
`POST /api/sales/import` sin cambiar nada del otro lado.

Contrato de la API, verificado contra developer.clip.mx (2026-10-01):

- `GET https://api-gw.payclip.com/payments`
- Autenticacion: `Authorization: Basic base64(API_KEY:SECRET_KEY)`. El panel de
  Clip entrega las dos piezas al crear la credencial y **el secret key solo se
  puede ver una vez**; si se pierde hay que generar otra.
- Parametros: `from`, `to` (ISO-8601, obligatorios), `status` (`paid` |
  `cancelled`), `last4`, `limit` (1..100, default 20), `pagination_token`.
- La ventana `from`..`to` **no puede exceder 720 horas** (30 dias) y no se
  pueden consultar transacciones de mas de un ano de antiguedad. Por eso
  `split_window` parte el rango solicitado en ventanas validas y pagina cada
  una; el que llama pide "del 21/09 a hoy" y no se entera.
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

4. **Un `status` vacio es una cancelacion.** No es "no se sabe": la API siempre
   manda el campo y `?status=cancelled` devuelve justo esos renglones (ver
   `_status`). `classify_status("")` dice `"paid"` porque en el export del panel
   una columna ausente si significa cobrada; aqui significa lo contrario, y sin
   la rama una cancelacion entra como venta.

5. **El efectivo de la app no viaja por esta API.** Confirmado dos veces el
   2026-10-04. Medido: 1,912 cobros en 360 dias con las credenciales de las dos
   sucursales, **cero** rotulados efectivo. Y contra la realidad: Gustavo
   reporta 6 a 20 cobros en efectivo por dia por sucursal, y el 30/08 hubo 5 en
   SJI — ese dia la API entrega **2** renglones (un cobro con tarjeta y una
   cancelacion), ninguno de ellos efectivo. La app si los registra
   (`Ventas > Efectivo`), pero esa coleccion vive detras de una ruta que el
   gateway contesta pidiendo firma AWS y no acepta la llave de comercio.

   Consecuencia que hay que decir siempre: el total de este camino es un
   **piso**, y el faltante **no es chico**. La cobertura la declara
   `sales_import.CASH_COVERAGE["clip_api"]`; aqui no se simula.

Uso rapido (la credencial se lee del entorno, nunca de un argumento):
    python clip_api.py probe --branch sji
    python clip_api.py pull --branch sji --from 2026-09-21 --to 2026-10-01
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
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

from clip_import import classify_status, normalize_payment_method

API_BASE = "https://api-gw.payclip.com"
PAYMENTS_PATH = "/payments"

# Limites que impone Clip, no nosotros.
MAX_WINDOW = timedelta(hours=720)
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


def split_window(start: datetime, end: datetime, *,
                 now: Optional[datetime] = None) -> List[Tuple[datetime, datetime]]:
    """Parte `start`..`end` en ventanas que Clip acepta (<= 720 h cada una).

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
        stop = min(cursor + MAX_WINDOW, end_utc)
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
    headers = {
        "Authorization": credentials.auth_header(),
        "Accept": "application/json",
        "User-Agent": "casa-dorelia-ingesta/1.0",
    }

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
