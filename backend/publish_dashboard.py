"""Regenera el tablero de ventas y repunta el **mismo** enlace publicado.

### El problema que resuelve

`dashboard.py` rinde un HTML autocontenido. Eso es su virtud (se abre sin
levantar nada) y tambien su trampa: es una **foto**. El enlace que BOS-143 dejo
en la tarjeta de la tarea tenia las cifras del `04/10` y no se movia solo, asi
que a partir del dia siguiente mostraba un dia viejo — sin decirlo, porque un
HTML no se queja de estar viejo. La carga de Clip si corre dos veces al dia
(rutina `03f5e143`, 07:45 y 19:45 CDMX), asi que el dato fresco ya existia: lo
que faltaba era volver a publicarlo.

Este modulo es ese paso. Hace tres cosas, en este orden:

1. **Regenera** el HTML de `dashboard.py` contra la base.
2. **Sube** el archivo como adjunto de una tarea.
3. **Repunta** un work product `artifact` ya existente al adjunto nuevo
   (`PATCH /api/work-products/{id}`), de modo que el chip de la tarea abra
   siempre lo ultimo.

El paso 3 es la razon de que esto no sea un `subprocess` de dos lineas. Sin el,
cada republicacion deja un adjunto mas y el enlace *viejo* sigue siendo el que
esta publicado: a los 15 dias habria 30 adjuntos y el que abre Gustavo seguiria
siendo el primero. Un solo enlace estable es el entregable, no el archivo.

### Por que vive aparte de `clip_daily.py`

Podria ser un paso al final del cargador — ya corre con las variables
`PAPERCLIP_*` en la mano. No esta ahi a proposito: **`clip_daily.py` toca
dinero**. Un tablero que no se pudo publicar no debe poder cambiar el codigo de
salida de una carga de ventas que si entro, porque ese codigo es lo que el corte
de las 08:00 lee para decidir si la cifra del dia es confiable. Un `401` del
control plane o un disco lleno convertirian una carga perfecta en una carga
"fallida", y alguien saldria a recargar a mano algo que ya estaba.

Separarlo deja esa garantia en la forma del comando, no en un `try` que alguien
puede mover de lugar: son dos invocaciones, y la segunda no puede alterar el
resultado de la primera porque ya termino. Dentro de este modulo, de todos
modos, ninguna excepcion escapa de `main`: la falla se imprime con su causa y
sale con 1.

### El panel de apertura, cuando no cuadra

`load_apertura` truena a proposito si los conteos del JSON ya no cuadran con la
hoja. Correcto a mano; aqui seria contraproducente: tumbar la republicacion
dejaria publicado el tablero de **ayer**, que es exactamente la averia que esto
viene a cerrar. Asi que el panel se cae solo y su razon se dibuja en la tarjeta
(`dashboard.load_apertura_degrading`). La venta se publica fresca; lo que falta
dice por que falta.

### Correrlo

    # despues de la carga, en la rutina
    python backend/publish_dashboard.py --db casa_dorelia \
        --apertura backend/apertura-sji.json \
        --issue d79395ba-11be-4c90-a607-db79c74c639e \
        --work-product 853436f7-9720-4a68-8dfa-ddc8c4cfcdf6

    # generar sin publicar, para ver que saldria
    python backend/publish_dashboard.py --db casa_dorelia --dry-run

Necesita `PAPERCLIP_API_URL`, `PAPERCLIP_API_KEY` y `PAPERCLIP_COMPANY_ID` en el
entorno (los inyecta el run). Fuera de la biblioteca estandar solo depende de
`pymongo`, via `dashboard.py`.

### Reutilizable para otra empresa del grupo

Nada aqui conoce a Casa Dorelia: la base, el panel, la tarea y el work product
son argumentos. Cualquier tablero generado del grupo se republica con este mismo
comando cambiando los cuatro.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dashboard


class PublishError(RuntimeError):
    """No se pudo publicar. Siempre dice en que paso y por que."""


# --------------------------------------------------------------------------
# Control plane: lo minimo de la API de Paperclip, con biblioteca estandar
# --------------------------------------------------------------------------

def api_base(url: Optional[str] = None) -> str:
    """Base sin `/api` ni diagonal final.

    `PAPERCLIP_API_URL` llega a veces con `/api` y a veces sin el. Normalizarlo
    aqui evita el `//api/api/...` que devuelve un 404 que se lee como permiso
    faltante.
    """
    base = (url or os.environ.get("PAPERCLIP_API_URL") or "").strip().rstrip("/")
    if not base:
        raise PublishError("falta PAPERCLIP_API_URL: no se adivina el control plane")
    if base.endswith("/api"):
        base = base[: -len("/api")]
    return base


def _headers(*, content_type: Optional[str] = None) -> Dict[str, str]:
    key = os.environ.get("PAPERCLIP_API_KEY")
    if not key:
        raise PublishError("falta PAPERCLIP_API_KEY en el entorno de este run")
    out = {"Authorization": f"Bearer {key}"}
    # El run id es la traza de auditoria de toda escritura. Va siempre que exista.
    run_id = os.environ.get("PAPERCLIP_RUN_ID")
    if run_id:
        out["X-Paperclip-Run-Id"] = run_id
    if content_type:
        out["Content-Type"] = content_type
    return out


def _request(method: str, url: str, *, data: Optional[bytes] = None,
             content_type: Optional[str] = None) -> Any:
    req = urllib.request.Request(url, data=data,
                                 headers=_headers(content_type=content_type),
                                 method=method)
    try:
        with urllib.request.urlopen(req) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:500].decode("utf-8", "replace")
        # El cuerpo del error nunca trae la llave: solo la respuesta del server.
        raise PublishError(f"{method} {url} -> HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise PublishError(f"{method} {url} no respondio: {exc.reason}") from exc
    if not body:
        return None
    try:
        return json.loads(body)
    except ValueError as exc:
        raise PublishError(f"{method} {url} no devolvio JSON: {body[:200]!r}") from exc


def _multipart(field: str, filename: str, payload: bytes,
               content_type: str) -> Tuple[bytes, str]:
    """Cuerpo `multipart/form-data` armado a mano.

    Es ~15 renglones y evita arrastrar `requests` solo para subir un archivo a
    un comando que corre en un disparo programado. El `boundary` sale de `uuid4`
    porque tiene que no aparecer dentro del archivo: un HTML generado puede
    traer cualquier cadena corta y adivinarla romperia la subida en silencio.
    """
    boundary = "----paperclip" + uuid.uuid4().hex
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode()
    body = head + payload + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def upload_attachment(path: str, *, issue_id: str, company_id: str,
                      base: Optional[str] = None) -> Mapping[str, Any]:
    """Sube el archivo como adjunto de la tarea y devuelve el registro creado."""
    with open(path, "rb") as handle:
        payload = handle.read()
    if not payload:
        raise PublishError(f"el archivo esta vacio, no se sube: {path}")
    filename = os.path.basename(path)
    guessed = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    body, content_type = _multipart("file", filename, payload, guessed)
    url = f"{api_base(base)}/api/companies/{company_id}/issues/{issue_id}/attachments"
    created = _request("POST", url, data=body, content_type=content_type)
    attachment = created.get("attachment") if isinstance(created, dict) else None
    record = attachment if isinstance(attachment, dict) else created
    if not isinstance(record, dict) or not record.get("id"):
        raise PublishError(f"la subida no devolvio un adjunto con id: {created!r}")
    return record


def repoint_work_product(work_product_id: str, *, attachment_id: str,
                         summary: Optional[str] = None,
                         base: Optional[str] = None) -> Mapping[str, Any]:
    """Apunta un work product `artifact` al adjunto nuevo.

    Se verifica leyendo la respuesta, no asumiendo el 200: el servidor
    canonicaliza `openPath`/`contentPath`/`byteSize` desde el `attachmentId`, asi
    que si el `attachmentId` echado de vuelta no es el que mandamos, la
    republicacion **no** quedo publicada aunque el HTTP diga 200. Esa
    confirmacion es la diferencia entre "subi un archivo" y "el enlace de la
    tarjeta abre lo ultimo".
    """
    patch: Dict[str, Any] = {"metadata": {"attachmentId": attachment_id}}
    if summary:
        patch["summary"] = summary
    url = f"{api_base(base)}/api/work-products/{work_product_id}"
    updated = _request("PATCH", url, data=json.dumps(patch).encode(),
                       content_type="application/json")
    if not isinstance(updated, dict):
        raise PublishError(f"el PATCH del work product no devolvio el objeto: {updated!r}")
    got = (updated.get("metadata") or {}).get("attachmentId")
    if got != attachment_id:
        raise PublishError(
            f"el work product sigue apuntando a {got!r} y no a {attachment_id!r}: "
            "el enlace publicado NO quedo actualizado")
    return updated


# --------------------------------------------------------------------------
# Generacion
# --------------------------------------------------------------------------

def generate(*, out: str, db: Optional[str], mongo_url: Optional[str],
             apertura_path: Optional[str], title: str) -> Dict[str, Any]:
    """Escribe el HTML y devuelve el modelo con el que se escribio."""
    apertura, apertura_error = dashboard.load_apertura_degrading(apertura_path)
    sales = dashboard.open_sales_collection(mongo_url, db)
    model = dashboard.build_model(sales.find({}, {"_id": 0}), title=title,
                                  db_name=db or os.environ.get("DB_NAME"),
                                  apertura=apertura, apertura_error=apertura_error)
    target = os.path.abspath(out)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(dashboard.render_html(model))
    model = dict(model)
    model["_out"] = target
    return model


def summarize(model: Mapping[str, Any]) -> str:
    """Resumen para el work product: dice la fecha de generacion y el alcance.

    La fecha va *en el resumen* y no solo dentro del HTML porque el chip de la
    tarea se lee sin abrir el archivo. Es el mismo principio que el rotulo de
    edad dentro de la pagina: lo que no se puede leer de un vistazo se lee mal.
    """
    por_marca = ", ".join(
        f"{b['name']} ${b['totals']['gross']:,.2f}" for b in model["brands"])
    partes = [
        f"Regenerado {model['generated_at_label']} con {model['rows_counted']} cobros",
        f"dias {model['days'][0]} a {model['days'][-1]}",
        f"por marca: {por_marca}",
        "piso con tarjeta, sin efectivo y sin total consolidado",
    ]
    if model.get("apertura_error"):
        partes.append(f"panel de apertura omitido ({model['apertura_error']})")
    return ". ".join(partes) + "."


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="publish_dashboard",
        description="Regenera el tablero de ventas y repunta el enlace publicado.",
    )
    parser.add_argument("--db", default=None, help="base a leer (default: $DB_NAME)")
    parser.add_argument("--mongo-url", default=None, help="default: $MONGO_URL o localhost")
    parser.add_argument("--out", default="dashboard-ventas.html",
                        help="archivo HTML intermedio (default: ./dashboard-ventas.html)")
    # "Ventas con tarjeta" dejo de ser cierto en BOS-119: lo cargado tambien
    # trae vales. El default se queda igual que el de `dashboard.py` para que el
    # enlace publicado y el HTML a mano no se llamen distinto.
    parser.add_argument("--title", default="Cobro en terminal Clip",
                        help="titulo del tablero")
    parser.add_argument("--apertura", default=None, metavar="ARCHIVO.json",
                        help="panel de pendientes de apertura; si no cuadra, el "
                             "tablero se publica sin panel y con la razon a la vista")
    parser.add_argument("--issue", default=None,
                        help="tarea donde se sube el adjunto (default: $PAPERCLIP_TASK_ID)")
    parser.add_argument("--work-product", default=None, metavar="ID",
                        help="work product `artifact` a repuntar al adjunto nuevo; "
                             "sin esto se sube el archivo pero el enlace publicado "
                             "sigue siendo el viejo")
    parser.add_argument("--dry-run", action="store_true",
                        help="genera el HTML y no publica nada")

    args = parser.parse_args(argv)

    try:
        model = generate(out=args.out, db=args.db, mongo_url=args.mongo_url,
                         apertura_path=args.apertura, title=args.title)
    except dashboard.DashboardError as exc:
        print(f"ERROR al generar el tablero: {exc}")
        return 1

    print(f"Tablero generado: {model['_out']}")
    print(f"  generado {model['generated_at_label']}"
          f"  ({model['rows_counted']} cobros)")
    for brand in model["brands"]:
        print(f"  {brand['name']}: ${brand['totals']['gross']:,.2f}"
              f" en {brand['totals']['tickets']} cobros")
    if model.get("apertura_error"):
        print(f"  AVISO panel de apertura omitido: {model['apertura_error']}")

    if args.dry_run:
        print("\n(en seco: no se subio ni se repunto nada)")
        return 0

    issue_id = args.issue or os.environ.get("PAPERCLIP_TASK_ID")
    company_id = os.environ.get("PAPERCLIP_COMPANY_ID")
    try:
        if not issue_id:
            raise PublishError("falta --issue (o PAPERCLIP_TASK_ID): no se sabe "
                               "a que tarea subir el adjunto")
        if not company_id:
            raise PublishError("falta PAPERCLIP_COMPANY_ID en el entorno")
        attachment = upload_attachment(model["_out"], issue_id=issue_id,
                                       company_id=company_id)
        print(f"Adjunto subido: {attachment['id']}")
        if not args.work_product:
            print("AVISO: sin --work-product el enlace publicado sigue siendo el "
                  "viejo. El adjunto quedo, pero nadie lo esta abriendo.")
            return 1
        updated = repoint_work_product(args.work_product,
                                       attachment_id=attachment["id"],
                                       summary=summarize(model))
        print(f"Enlace publicado repuntado: {updated['id']}"
              f" -> /api/attachments/{attachment['id']}/content")
    except PublishError as exc:
        # La carga de ventas ya termino y su codigo de salida no se toca: este
        # comando es otra invocacion. Lo que se cae aqui es el tablero, y lo
        # dice con su causa para que no haya que adivinarla en el siguiente run.
        print(f"ERROR al publicar: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - red/disco/entorno
        # Nada escapa de aqui. Un traceback en un disparo programado es un
        # mensaje que nadie lee; una causa en una linea si se lee.
        print(f"ERROR inesperado al publicar: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
