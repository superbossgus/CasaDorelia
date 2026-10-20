"""El republicado no puede dejar el enlace viejo publicado y decir que si (BOS-144).

El tablero de BOS-143 es un HTML generado, o sea una foto. La averia que estas
pruebas cuidan **no** es que la foto salga mal: es que salga bien, se suba bien,
y el enlace que abre Gustavo siga siendo el de anteayer. Ese modo de falla es
silencioso por construccion — el HTTP contesta 200 en cada paso — asi que lo
unico que lo detecta es confirmar el `attachmentId` que el servidor echo de
vuelta.

Las cuatro cosas que se prueban aqui son las cuatro formas de publicar en falso:

1. **Subir sin repuntar.** El adjunto queda, el enlace no se mueve, y el comando
   saldria con 0 diciendo "listo". Es la peor: deja 30 adjuntos y una cifra
   congelada.
2. **Repuntar y creerle al 200.** Si el work product sigue apuntando al adjunto
   viejo, el enlace publicado no cambio aunque el PATCH haya contestado bien.
3. **Dejar escapar una excepcion.** Esto corre en un disparo programado despues
   de una carga de dinero; un traceback ahi es un mensaje que nadie lee.
4. **Mandar la llave a donde no va.** El header de autorizacion sale solo hacia
   el control plane, y jamas al cuerpo ni al texto de un error.

Sin red y sin Mongo: `urlopen` se sustituye por un doble que graba las peticiones.
"""
import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import publish_dashboard as pub  # noqa: E402
from publish_dashboard import PublishError  # noqa: E402

ATTACHMENT = "11111111-1111-1111-1111-111111111111"
WORK_PRODUCT = "22222222-2222-2222-2222-222222222222"
ISSUE = "33333333-3333-3333-3333-333333333333"


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setenv("PAPERCLIP_API_URL", "http://127.0.0.1:3100/api")
    monkeypatch.setenv("PAPERCLIP_API_KEY", "llave-de-prueba")
    monkeypatch.setenv("PAPERCLIP_COMPANY_ID", "empresa")
    monkeypatch.setenv("PAPERCLIP_RUN_ID", "run-1")


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def fake_urlopen(monkeypatch, responder):
    """Sustituye `urlopen` y graba cada peticion que sale."""
    enviadas = []

    def handler(req, *a, **kw):
        enviadas.append(req)
        return FakeResponse(json.dumps(responder(req)).encode())

    monkeypatch.setattr(pub.urllib.request, "urlopen", handler)
    return enviadas


# --------------------------------------------------------------------------
# La URL del control plane
# --------------------------------------------------------------------------

def test_la_base_se_normaliza_con_y_sin_api():
    # `PAPERCLIP_API_URL` llega de las dos formas. Pegar `/api` a una que ya lo
    # trae da un 404 que se lee como permiso faltante, y se persigue en el lugar
    # equivocado.
    assert pub.api_base("http://x:3100/api") == "http://x:3100"
    assert pub.api_base("http://x:3100/") == "http://x:3100"
    assert pub.api_base("http://x:3100") == "http://x:3100"


def test_sin_url_o_sin_llave_lo_dice_en_vez_de_intentar(monkeypatch):
    monkeypatch.delenv("PAPERCLIP_API_URL")
    with pytest.raises(PublishError) as exc:
        pub.api_base()
    assert "PAPERCLIP_API_URL" in str(exc.value)

    monkeypatch.setenv("PAPERCLIP_API_URL", "http://x/api")
    monkeypatch.delenv("PAPERCLIP_API_KEY")
    with pytest.raises(PublishError) as exc:
        pub._headers()
    assert "PAPERCLIP_API_KEY" in str(exc.value)


def test_toda_escritura_lleva_la_traza_del_run():
    # Sin este header la escritura no queda ligada al heartbeat que la hizo.
    assert pub._headers()["X-Paperclip-Run-Id"] == "run-1"


# --------------------------------------------------------------------------
# Subida del adjunto
# --------------------------------------------------------------------------

def test_el_adjunto_sube_como_multipart_con_el_html_completo(monkeypatch, tmp_path):
    html = "<!DOCTYPE html><p>tablero</p>"
    archivo = tmp_path / "dashboard-ventas.html"
    archivo.write_text(html, encoding="utf-8")

    enviadas = fake_urlopen(monkeypatch, lambda req: {"id": ATTACHMENT})
    registro = pub.upload_attachment(str(archivo), issue_id=ISSUE,
                                     company_id="empresa")

    assert registro["id"] == ATTACHMENT
    req = enviadas[0]
    assert req.method == "POST"
    assert req.full_url == (
        f"http://127.0.0.1:3100/api/companies/empresa/issues/{ISSUE}/attachments")
    cuerpo = req.data.decode()
    # El limite del multipart tiene que ir en el header *y* en el cuerpo, y el
    # tipo tiene que ser text/html: un HTML subido como octet-stream se baja en
    # vez de abrirse, y el enlace deja de ser un tablero.
    limite = req.headers["Content-type"].split("boundary=")[1]
    assert cuerpo.startswith("--" + limite)
    assert "Content-Type: text/html" in cuerpo
    assert 'filename="dashboard-ventas.html"' in cuerpo
    assert html in cuerpo


def test_el_limite_del_multipart_no_puede_aparecer_en_el_archivo(monkeypatch, tmp_path):
    # Un limite fijo que el HTML contuviera partiria el cuerpo a media subida, en
    # silencio. Por eso sale de uuid4 y no se repite entre subidas.
    archivo = tmp_path / "t.html"
    archivo.write_text("x", encoding="utf-8")
    enviadas = fake_urlopen(monkeypatch, lambda req: {"id": ATTACHMENT})
    pub.upload_attachment(str(archivo), issue_id=ISSUE, company_id="empresa")
    pub.upload_attachment(str(archivo), issue_id=ISSUE, company_id="empresa")
    limites = {r.headers["Content-type"] for r in enviadas}
    assert len(limites) == 2


def test_un_archivo_vacio_no_se_sube(monkeypatch, tmp_path):
    # Un tablero de 0 bytes abre en blanco y se lee como "no hubo venta".
    archivo = tmp_path / "vacio.html"
    archivo.write_text("", encoding="utf-8")
    fake_urlopen(monkeypatch, lambda req: {"id": ATTACHMENT})
    with pytest.raises(PublishError) as exc:
        pub.upload_attachment(str(archivo), issue_id=ISSUE, company_id="empresa")
    assert "vacio" in str(exc.value)


def test_una_subida_sin_id_no_se_toma_por_buena(monkeypatch, tmp_path):
    archivo = tmp_path / "t.html"
    archivo.write_text("x", encoding="utf-8")
    fake_urlopen(monkeypatch, lambda req: {"ok": True})
    with pytest.raises(PublishError) as exc:
        pub.upload_attachment(str(archivo), issue_id=ISSUE, company_id="empresa")
    assert "id" in str(exc.value)


# --------------------------------------------------------------------------
# Repuntar el enlace publicado: el paso que de verdad importa
# --------------------------------------------------------------------------

def test_repuntar_manda_el_attachment_nuevo_y_confirma_el_eco(monkeypatch):
    enviadas = fake_urlopen(monkeypatch, lambda req: {
        "id": WORK_PRODUCT,
        "metadata": {"attachmentId": json.loads(req.data)["metadata"]["attachmentId"]},
    })
    actualizado = pub.repoint_work_product(WORK_PRODUCT, attachment_id=ATTACHMENT,
                                          summary="regenerado hoy")

    assert actualizado["metadata"]["attachmentId"] == ATTACHMENT
    req = enviadas[0]
    assert req.method == "PATCH"
    assert req.full_url == f"http://127.0.0.1:3100/api/work-products/{WORK_PRODUCT}"
    assert json.loads(req.data)["summary"] == "regenerado hoy"


def test_un_200_que_sigue_apuntando_al_adjunto_viejo_es_una_falla(monkeypatch):
    # Este es el modo de falla que la tarea vino a cerrar. El servidor contesta
    # 200 y el enlace de la tarjeta sigue abriendo el tablero de anteayer: sin
    # revisar el eco, el comando saldria con 0 y nadie se enteraria hasta que
    # alguien note que la cifra no se mueve.
    viejo = "99999999-9999-9999-9999-999999999999"
    fake_urlopen(monkeypatch, lambda req: {"id": WORK_PRODUCT,
                                           "metadata": {"attachmentId": viejo}})
    with pytest.raises(PublishError) as exc:
        pub.repoint_work_product(WORK_PRODUCT, attachment_id=ATTACHMENT)
    mensaje = str(exc.value)
    assert viejo in mensaje and ATTACHMENT in mensaje
    assert "NO quedo actualizado" in mensaje


def test_un_error_http_dice_el_codigo_y_nunca_la_llave(monkeypatch):
    def handler(req, *a, **kw):
        raise pub.urllib.error.HTTPError(req.full_url, 403, "Forbidden", {},
                                         io.BytesIO(b'{"error":"forbidden"}'))

    monkeypatch.setattr(pub.urllib.request, "urlopen", handler)
    with pytest.raises(PublishError) as exc:
        pub.repoint_work_product(WORK_PRODUCT, attachment_id=ATTACHMENT)
    mensaje = str(exc.value)
    assert "403" in mensaje and "forbidden" in mensaje
    assert "llave-de-prueba" not in mensaje


# --------------------------------------------------------------------------
# El CLI: lo que pasa cuando el tablero se cae
# --------------------------------------------------------------------------

def modelo_falso(**extra):
    base = {
        "generated_at": "2026-10-04T21:19:00-06:00",
        "generated_at_label": "04/10/2026 21:19 CDMX",
        "rows_counted": 118,
        "days": ["2026-09-21", "2026-10-04"],
        "brands": [{"name": "Casa Dorelia",
                    "totals": {"gross": 10567.0, "tickets": 95}}],
        "apertura_error": None,
        # El alcance del efectivo sale de aqui, no de una constante: el resumen
        # del work product tiene que poder dejar de decir "piso" el dia que haya
        # cortes capturados (BOS-149).
        "limits": {"cash": {"consulted": True, "all_missing": True,
                            "days_covered": 0, "days_missing": 28,
                            "first_covered_day": None, "last_covered_day": None}},
    }
    base.update(extra)
    return base


def test_el_resumen_del_work_product_lleva_la_fecha_de_generacion():
    # El chip de la tarea se lee sin abrir el archivo: si el resumen no trae la
    # fecha, nada distingue el tablero de hoy del de la semana pasada.
    texto = pub.summarize(modelo_falso())
    assert "04/10/2026 21:19 CDMX" in texto
    assert "Casa Dorelia $10,567.00" in texto
    assert "sin total consolidado" in texto
    assert "panel de apertura omitido" not in texto


def test_el_resumen_confiesa_cuando_se_publico_sin_panel():
    texto = pub.summarize(modelo_falso(apertura_error="el corte de la hoja no cuadra"))
    assert "panel de apertura omitido (el corte de la hoja no cuadra)" in texto


def test_sin_work_product_el_comando_no_sale_con_cero(monkeypatch, tmp_path, capsys):
    # Subir el adjunto y no repuntar deja el enlace publicado en el viejo. Salir
    # con 0 ahi diria "republicado" de algo que nadie esta abriendo.
    archivo = tmp_path / "t.html"
    archivo.write_text("<p>x</p>", encoding="utf-8")
    monkeypatch.setattr(pub, "generate",
                        lambda **kw: modelo_falso(_out=str(archivo)))
    fake_urlopen(monkeypatch, lambda req: {"id": ATTACHMENT})

    assert pub.main(["--issue", ISSUE]) == 1
    salida = capsys.readouterr().out
    assert "el enlace publicado sigue siendo el viejo" in salida


def test_una_falla_al_publicar_sale_con_uno_y_sin_traceback(monkeypatch, tmp_path, capsys):
    # Esto corre despues de una carga de dinero. Un traceback en un disparo
    # programado es un mensaje que nadie lee; una causa en una linea si.
    archivo = tmp_path / "t.html"
    archivo.write_text("<p>x</p>", encoding="utf-8")
    monkeypatch.setattr(pub, "generate",
                        lambda **kw: modelo_falso(_out=str(archivo)))

    def handler(req, *a, **kw):
        raise OSError("se cayo la red a media subida")

    monkeypatch.setattr(pub.urllib.request, "urlopen", handler)
    assert pub.main(["--issue", ISSUE, "--work-product", WORK_PRODUCT]) == 1
    salida = capsys.readouterr().out
    assert "ERROR" in salida and "se cayo la red" in salida
    assert "Traceback" not in salida


def test_en_seco_genera_y_no_toca_el_control_plane(monkeypatch, tmp_path, capsys):
    archivo = tmp_path / "t.html"
    archivo.write_text("<p>x</p>", encoding="utf-8")
    monkeypatch.setattr(pub, "generate",
                        lambda **kw: modelo_falso(_out=str(archivo)))

    def handler(req, *a, **kw):  # pragma: no cover - debe no llamarse
        raise AssertionError("en seco no debe salir ninguna peticion")

    monkeypatch.setattr(pub.urllib.request, "urlopen", handler)
    assert pub.main(["--dry-run"]) == 0
    assert "en seco" in capsys.readouterr().out


def test_el_camino_completo_sube_y_repunta_en_ese_orden(monkeypatch, tmp_path):
    archivo = tmp_path / "dashboard-ventas.html"
    archivo.write_text("<p>x</p>", encoding="utf-8")
    monkeypatch.setattr(pub, "generate",
                        lambda **kw: modelo_falso(_out=str(archivo)))

    def responder(req):
        if "attachments" in req.full_url:
            return {"id": ATTACHMENT}
        return {"id": WORK_PRODUCT,
                "metadata": {"attachmentId": json.loads(req.data)["metadata"]["attachmentId"]}}

    enviadas = fake_urlopen(monkeypatch, responder)
    assert pub.main(["--issue", ISSUE, "--work-product", WORK_PRODUCT]) == 0
    # El orden importa: no se puede repuntar a un adjunto que todavia no existe.
    assert "attachments" in enviadas[0].full_url
    assert "work-products" in enviadas[1].full_url
    assert json.loads(enviadas[1].data)["metadata"]["attachmentId"] == ATTACHMENT
