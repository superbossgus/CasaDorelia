"""El tablero de ventas no puede mentir de las cuatro formas conocidas.

Estas pruebas no cuidan pixeles: cuidan que el tablero siga sin poder hacer las
cuatro cosas por las que una cifra de este negocio se lee mal.

1. **Un total consolidado.** Las dos marcas de `casa_dorelia` tienen repartos
   distintos (ver `test_brands.py`). La suma de dinero de las dos no existe en
   ninguna parte del modelo: ni con ese nombre, ni rotulada como "suma de
   control". Un campo que vive en el JSON acaba dibujado por el siguiente que
   toque la plantilla, asi que la prueba busca el *valor*, no el nombre.
2. **Un cero que en realidad es un hueco.** Antes del primer dia de una marca no
   hay dato; un dia que ya paso sin cobro si es un cero; y el dia en curso
   **todavia no es nada**. Los tres se ven distinto, porque dibujar el dia de
   hoy en cero desploma la linea y se lee como un derrumbe a las 07:45.
3. **Una cifra de ayer presentada como cerrada cuando no lo esta** — o, al
   reves, una duda arrastrada un segundo dia cuando el catch-up de la mañana ya
   la resolvio.
4. **Una utilidad de cero.** Clip no entrega costo, asi que `profit` es 0 en
   todas las ventas cargadas. El tablero tiene que *saber* que no sabe.

Sin Mongo: `build_model` recibe documentos, no una conexion.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dashboard import (  # noqa: E402
    MORNING_CATCHUP_LOCAL,
    SNAPSHOT_LOCAL,
    DashboardError,
    build_model,
    day_states,
    load_apertura,
    render_html,
)


def sale(day, total, *, brand="casa-dorelia", at=None, **extra):
    """Una venta de Clip como la deja `clip_load`, con lo minimo que se lee."""
    doc = {
        "business_date": day,
        "created_at": at or (day + "T18:00:00+00:00"),
        "total": total,
        "brand": brand,
        "cafeteria_id": "c-sji" if brand == "casa-dorelia" else "c-tecno",
        "source": "clip_api",
        "payment_method": "tarjeta",
        "cost_known": False,
        "cost_total": 0.0,
        "clip_fee": None,
        "items": [{"product_id": None, "product_name": "Venta Clip (sin desglose)"}],
    }
    doc.update(extra)
    return doc


def model(rows, *, today="2026-10-04", hour=12, minute=0, cortes=None):
    """Modelo armado en un instante fijo. La hora decide si ayer ya se confirmo.

    `cortes=None` es el default a proposito: es "no se preguntaron los cortes",
    y deja el tablero como estaba antes de BOS-149. `cortes=[]` es "se
    preguntaron y no hay ninguno", que si rotula cada dia como `sin corte`.
    """
    from datetime import datetime, timezone

    from business_day import BUSINESS_TZ

    now = datetime.fromisoformat(today + "T00:00:00").replace(
        hour=hour, minute=minute, tzinfo=BUSINESS_TZ).astimezone(timezone.utc)
    return build_model(rows, title="t", today=today, now=now, db_name="prueba",
                       cortes=cortes)


def series_of(m, brand):
    found = [b for b in m["brands"] if b["brand"] == brand]
    assert found, f"la marca {brand} desaparecio del modelo"
    return {p["date"]: p for p in found[0]["series"]}


# --------------------------------------------------------------------------
# 1. Nunca un total consolidado
# --------------------------------------------------------------------------

def test_cada_marca_tiene_su_renglon_y_su_color():
    m = model([sale("2026-10-01", 100.0, brand="casa-dorelia"),
               sale("2026-10-01", 300.0, brand="le-pain-dore")])

    assert [b["brand"] for b in m["brands"]] == ["casa-dorelia", "le-pain-dore"]
    assert m["brands"][0]["totals"]["gross"] == 100.0
    assert m["brands"][1]["totals"]["gross"] == 300.0
    # El color se asigna por slug ordenado, no por cuanto vendio cada una:
    # filtrar una marca no puede repintar a la que queda.
    assert m["brands"][0]["color"] != m["brands"][1]["color"]


def test_la_suma_de_dinero_de_las_dos_marcas_no_existe_en_el_modelo():
    m = model([sale("2026-10-01", 100.0, brand="casa-dorelia"),
               sale("2026-10-01", 300.0, brand="le-pain-dore")])

    # Se busca el valor, no el nombre: 400.0 no puede aparecer en ningun campo,
    # ni como `control_sum`, ni como `total`, ni dentro de una cadena del HTML.
    # Un rotulo ("suma de control") no protege nada el dia que alguien lo pinte.
    def numeros(node):
        if isinstance(node, dict):
            for value in node.values():
                yield from numeros(value)
        elif isinstance(node, list):
            for value in node:
                yield from numeros(value)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            yield float(node)

    assert 400.0 not in set(numeros(m))
    assert "control_sum" not in m
    assert "total" not in m
    assert "gross" not in m
    # Lo unico que si cruza marcas es un conteo de renglones: no son pesos.
    assert m["rows_counted"] == 2


def test_una_venta_sin_marca_cae_en_sin_marca_en_vez_de_desaparecer():
    m = model([sale("2026-10-01", 100.0, brand=None)])

    assert [b["brand"] for b in m["brands"]] == ["sin-marca"]
    assert m["quality"]["checks"][0]["id"] == "brand"
    assert m["quality"]["checks"][0]["count"] == 1
    assert m["quality"]["checks"][0]["status"] == "critical"


# --------------------------------------------------------------------------
# 2. Hueco, cero y dia en curso son tres cosas distintas
# --------------------------------------------------------------------------

def test_antes_del_primer_dia_de_la_marca_hay_hueco_no_cero():
    m = model([sale("2026-10-01", 100.0, brand="le-pain-dore"),
               sale("2026-10-03", 200.0, brand="casa-dorelia")],
              today="2026-10-04")

    cd = series_of(m, "casa-dorelia")
    # Casa Dorelia no operaba el 1 de octubre: eso es sin dato.
    assert cd["2026-10-01"]["gross"] is None
    assert cd["2026-10-03"]["gross"] == 200.0


def test_un_dia_que_paso_sin_cobro_es_un_cero_explicito():
    m = model([sale("2026-10-01", 100.0), sale("2026-10-03", 200.0)],
              today="2026-10-04")

    cd = series_of(m, "casa-dorelia")
    # El 2 cae dentro de la ventana de la marca y ya paso: es un cero medido.
    assert cd["2026-10-02"]["gross"] == 0.0
    assert cd["2026-10-02"]["tickets"] == 0


def test_el_dia_en_curso_sin_cobro_es_hueco_no_un_cero_que_desploma_la_linea():
    m = model([sale("2026-10-03", 200.0)], today="2026-10-04", hour=7, minute=50)

    cd = series_of(m, "casa-dorelia")
    assert m["day_states"]["2026-10-04"] == "en_curso"
    # A las 07:50 las sucursales no han abierto. Un 0.0 aqui se grafica como
    # caida a cero; tiene que ser `None` para que la linea se corte.
    assert cd["2026-10-04"]["gross"] is None
    assert cd["2026-10-04"]["tickets"] is None


def test_el_dia_en_curso_con_cobro_si_trae_su_cifra():
    m = model([sale("2026-10-03", 200.0), sale("2026-10-04", 150.0)],
              today="2026-10-04", hour=20)

    cd = series_of(m, "casa-dorelia")
    assert cd["2026-10-04"]["gross"] == 150.0
    assert m["day_states"]["2026-10-04"] == "en_curso"


# --------------------------------------------------------------------------
# 3. El cierre de ayer: dudar una vez, no dos
# --------------------------------------------------------------------------

def _states(last_capture, *, today="2026-10-04", now_minutes=12 * 60):
    axis = ["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04"]
    return day_states(axis=axis, last_capture=last_capture, today=today,
                      now_minutes=now_minutes,
                      has_sales={d: True for d in axis})


def test_una_venta_pegada_a_la_foto_de_las_1945_deja_el_dia_sin_confirmar():
    # 19:39 locales: seis minutos antes de la foto. Pudo haber cobro despues.
    states = _states({"2026-10-03": 19 * 60 + 39}, now_minutes=7 * 60)
    assert states["2026-10-03"] == "no_confirmado"


def test_una_venta_lejos_de_la_foto_cierra_el_dia():
    states = _states({"2026-10-03": 18 * 60 + 54}, now_minutes=7 * 60)
    assert states["2026-10-03"] == "cerrado"


def test_el_catch_up_de_la_mañana_confirma_el_dia_de_ayer():
    # Mismo dato de 19:39, pero ya corrieron las 07:45: esa corrida volvio a
    # pedir el dia completo. Arrastrar la duda seria desconfiar de una cifra
    # ya verificada.
    states = _states({"2026-10-03": 19 * 60 + 39}, now_minutes=8 * 60)
    assert states["2026-10-03"] == "cerrado"


def test_la_duda_no_se_arrastra_un_segundo_dia():
    states = _states({"2026-10-02": 19 * 60 + 44, "2026-10-03": 19 * 60 + 44},
                     now_minutes=7 * 60)
    assert states["2026-10-03"] == "no_confirmado"   # ayer
    assert states["2026-10-02"] == "cerrado"          # antier: ya lo confirmaron


def test_un_dia_sin_ninguna_venta_se_distingue_de_un_dia_cerrado():
    axis = ["2026-10-02", "2026-10-03", "2026-10-04"]
    states = day_states(axis=axis, last_capture={}, today="2026-10-04",
                        now_minutes=12 * 60,
                        has_sales={"2026-10-03": True})
    assert states["2026-10-02"] == "sin_cobro"
    assert states["2026-10-03"] == "cerrado"


# --------------------------------------------------------------------------
# 4. Lo que el tablero sabe que no sabe
# --------------------------------------------------------------------------

def test_sin_costo_en_ninguna_venta_el_margen_queda_marcado_como_desconocido():
    m = model([sale("2026-10-03", 200.0)])
    assert m["limits"]["margin_unknown"] is True
    assert m["limits"]["cost_known_rows"] == 0


def test_el_dia_que_si_haya_costo_el_rotulo_cambia_solo():
    # El limite se calcula, no se escribe a mano en el HTML: si entra venta del
    # punto de venta con costo, el tablero deja de decir "sin margen".
    m = model([sale("2026-10-03", 200.0, cost_known=True, cost_total=80.0,
                    source="pos")])
    assert m["limits"]["margin_unknown"] is False


def test_solo_tarjeta_marca_el_total_como_piso():
    """Sin cortes, el piso se rotula igual: lo que cambia es que ya se pregunto.

    `consulted: False` es "no se leyeron los cortes" y `all_missing: True` es
    "se leyeron y no hay ninguno". Los dos son piso, pero solo el segundo se
    arregla capturando un corte, asi que la pagina los dice distinto.
    """
    m = model([sale("2026-10-03", 200.0)])
    assert m["limits"]["cash"]["consulted"] is False
    assert m["limits"]["cash"]["all_missing"] is True

    preguntado = model([sale("2026-10-03", 200.0)], cortes=[])
    assert preguntado["limits"]["cash"]["consulted"] is True
    assert preguntado["limits"]["cash"]["all_missing"] is True

    # Un renglon de venta con efectivo (punto de venta, no Clip) ya mete el
    # efectivo en el bruto. Se cuenta, pero no completa ningun dia por si solo:
    # lo que vuelve citable un dia es el corte del cajon.
    pos = model([sale("2026-10-03", 200.0),
                 sale("2026-10-03", 50.0, payment_method="efectivo")])
    assert pos["limits"]["cash"]["pos_rows"] == 1


def test_un_metodo_nuevo_no_hace_pasar_el_total_por_venta_completa():
    """Un metodo de cobro nuevo no completa el dia. Solo el corte lo completa.

    Antes de BOS-119 esto se preguntaba al reves ("el unico metodo es tarjeta"),
    asi que al separar los vales de la tarjeta el tablero dejaba de decir que el
    total es un piso — sin que nadie escribiera ese cambio. El dinero seguia
    igual de incompleto, y desde BOS-149 lo que mueve el rotulo es el corte del
    cajon, no el catalogo de metodos.
    """
    m = model([sale("2026-10-03", 200.0),
               sale("2026-10-03", 115.0, payment_method="vales"),
               sale("2026-10-03", 108.0, payment_method="otro")], cortes=[])
    assert m["limits"]["cash"]["all_missing"] is True
    assert m["limits"]["cash"]["days_covered"] == 0
    assert m["limits"]["payment_methods"] == {"tarjeta": 1, "vales": 1, "otro": 1}


def test_los_pesos_por_metodo_viven_en_la_marca_y_no_cruzados():
    """El desglose por metodo es por marca: un monto global sumaria las dos."""
    m = model([sale("2026-10-03", 200.0, brand="casa-dorelia"),
               sale("2026-10-03", 115.0, brand="casa-dorelia", payment_method="vales"),
               sale("2026-10-03", 300.0, brand="le-pain-dore")])

    por_marca = {b["brand"]: b["by_method"] for b in m["brands"]}
    assert por_marca["casa-dorelia"]["tarjeta"] == {"gross": 200.0, "tickets": 1}
    assert por_marca["casa-dorelia"]["vales"] == {"gross": 115.0, "tickets": 1}
    assert por_marca["le-pain-dore"]["tarjeta"] == {"gross": 300.0, "tickets": 1}
    # 500.0 (las dos tarjetas juntas) no existe en ninguna parte del modelo.
    assert "gross_by_payment_method" not in m["limits"]
    assert 500.0 not in {v for v in _numeros(m)}


def _numeros(node):
    if isinstance(node, dict):
        for value in node.values():
            yield from _numeros(value)
    elif isinstance(node, list):
        for value in node:
            yield from _numeros(value)
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        yield float(node)


def test_comision_y_costo_solo_se_reclaman_a_los_renglones_de_clip():
    # Una venta del punto de venta si puede traer costo de verdad; reclamarselo
    # dejaria el control en rojo para siempre y nadie volveria a mirarlo.
    m = model([sale("2026-10-03", 200.0, source="pos", cost_total=90.0),
               sale("2026-10-03", 100.0, clip_fee=3.5)])
    checks = {c["id"]: c["count"] for c in m["quality"]["checks"]}
    assert checks["clip_cost"] == 0     # la del punto de venta no cuenta
    assert checks["clip_fee"] == 1      # la de Clip con comision inventada, si


# --------------------------------------------------------------------------
# El dia de operacion es UTC-6, nunca UTC
# --------------------------------------------------------------------------

def test_una_venta_de_las_1808_locales_no_se_va_al_dia_siguiente():
    # 00:08Z del 4 de octubre son las 18:08 del 3 en CDMX. Cortar por dia UTC
    # moveria esta venta de dia y descuadraria el corte.
    m = model([sale(None, 164.0, at="2026-10-04T00:08:00+00:00",
                    business_date=None)],
              today="2026-10-04")
    cd = series_of(m, "casa-dorelia")
    assert cd["2026-10-03"]["gross"] == 164.0
    assert cd["2026-10-04"]["gross"] is None


def test_la_hora_del_tablero_es_local_no_utc():
    m = model([sale("2026-10-03", 164.0, at="2026-10-04T00:08:00+00:00")],
              today="2026-10-04")
    hours = {h["hour"]: h["tickets"] for h in m["brands"][0]["hours"]}
    assert hours[18] == 1
    assert hours[0] == 0


# --------------------------------------------------------------------------
# La pagina
# --------------------------------------------------------------------------

def test_sin_ventas_legibles_falla_diciendo_que_falta():
    with pytest.raises(DashboardError) as exc:
        model([])
    assert "no hay ventas" in str(exc.value)


def test_el_html_es_autocontenido_y_no_pide_nada_por_red():
    # Se abre con doble clic, desde un USB o sin internet. Lo que se vigila es
    # cualquier cosa que *traiga* algo de afuera; el namespace de SVG lleva una
    # URL en el texto y no descarga nada, por eso se descuenta antes de buscar.
    html = render_html(model([sale("2026-10-03", 200.0)]))
    html = html.replace("http://www.w3.org/2000/svg", "")
    for remote in ("http://", "https://", "//cdn", "src=", "@import",
                   "fetch(", "XMLHttpRequest", "@font-face"):
        assert remote not in html, f"el tablero dejo de ser autocontenido: {remote}"


def test_el_json_embebido_no_puede_cerrar_la_etiqueta_script():
    # Un nombre capturado a mano puede traer `</script>`; si se cuela, la
    # pagina se parte a la mitad.
    html = render_html(model([sale("2026-10-03", 200.0,
                                   brand="</script><img onerror=x>")]))
    assert "</script><img" not in html
    assert "\\u003c/script>" in html or "\\u003c" in html


# --------------------------------------------------------------------------
# 5. El panel de apertura: un conteo escrito a mano que no se puede desfasar
# --------------------------------------------------------------------------

APERTURA = {
    "title": "Apertura SJI",
    "source": {"label": "hoja", "url": "https://drive.google.com/file/d/X/view",
               "modified_at": "2026-09-27T04:41:54Z",
               "rows": 4, "delivered": 2, "pending": 2},
    "blockers": [{"ref": "#27", "title": "Materia prima"},
                 {"ref": "Anexo J", "title": "Permisos", "off_sheet": True}],
    "pending_rows": [{"ref": "#27", "title": "Materia prima"},
                     {"ref": "#9", "title": "Tapete"}],
}


def apertura_file(tmp_path, **cambios):
    data = json.loads(json.dumps(APERTURA))
    for key, value in cambios.items():
        if key == "source":
            data["source"].update(value)
        else:
            data[key] = value
    path = tmp_path / "apertura.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_el_panel_de_apertura_calcula_la_antiguedad_del_corte(tmp_path):
    from datetime import datetime, timezone

    # El panel no puede decir "al dia" porque alguien lo escribio una vez: la
    # antiguedad sale de la fecha del corte contra el dia de generacion.
    a = load_apertura(apertura_file(tmp_path),
                      now=datetime(2026, 10, 4, 18, 0, tzinfo=timezone.utc))
    assert a["source"]["stale_days"] == 8
    assert a["source"]["modified_label"] == "26/09/2026"


def test_un_corte_que_no_cuadra_con_el_total_de_la_hoja_no_se_dibuja(tmp_path):
    # 2 + 2 == 4 pasa; 2 + 2 == 9 es un conteo viejo, y un numero viejo arriba
    # del tablero es peor que no tener el panel.
    with pytest.raises(DashboardError) as exc:
        load_apertura(apertura_file(tmp_path, source={"rows": 9}))
    assert "no cuadra" in str(exc.value)


def test_no_se_puede_recortar_la_lista_y_dejar_el_numero(tmp_path):
    with pytest.raises(DashboardError) as exc:
        load_apertura(apertura_file(tmp_path,
                                    pending_rows=[{"ref": "#27", "title": "x"}]))
    assert "1 renglones" in str(exc.value)


def test_un_bloqueante_que_ya_no_esta_pendiente_en_la_hoja_truena(tmp_path):
    # Si la hoja ya marco #27 como entregado y nadie lo saco de los
    # bloqueantes, el tablero lo diria abierto para siempre.
    with pytest.raises(DashboardError) as exc:
        load_apertura(apertura_file(tmp_path,
                                    pending_rows=[{"ref": "#9", "title": "Tapete"},
                                                  {"ref": "#10", "title": "Toldo"}]))
    assert "#27" in str(exc.value)


def test_el_anexo_del_contrato_no_es_renglon_de_la_hoja_y_eso_se_declara(tmp_path):
    # `Anexo J` no esta en los pendientes de la hoja y no truena, porque viene
    # con `off_sheet`. Sin esa bandera tendria que tronar igual que #27.
    a = load_apertura(apertura_file(tmp_path))
    assert [b["ref"] for b in a["blockers"]] == ["#27", "Anexo J"]

    roto = json.loads(json.dumps(APERTURA))
    roto["blockers"][1].pop("off_sheet")
    path = tmp_path / "roto.json"
    path.write_text(json.dumps(roto), encoding="utf-8")
    with pytest.raises(DashboardError):
        load_apertura(str(path))


def test_sin_archivo_de_apertura_la_tarjeta_no_existe_en_vez_de_salir_vacia():
    # Una tarjeta en blanco se lee como "ya no falta nada".
    m = model([sale("2026-10-03", 200.0)])
    assert m["apertura"] is None
    html = render_html(m)
    assert 'id="apertura-card" hidden' in html


# --- El responsable por renglon (BOS-165) -----------------------------------
#
# El nombre es la variable que predice el cierre: en el corte del 04/10/2026 los
# 19 renglones de la hoja con responsable con nombre estaban los 19 `Entregado`,
# y los 19 sin nombre seguian abiertos salvo uno. Lo que estos casos protegen no
# es que el nombre se dibuje —eso se ve— sino que **no se pueda dibujar a secas**
# cuando el dueño es un supuesto.

def test_un_renglon_sin_nombre_dice_sin_responsable_y_no_un_guion(tmp_path):
    # "No sabemos quien" es un dato, y es justo el grupo que no se cierra. Un
    # guion o un vacio se leen como que falto llenar la celda.
    a = load_apertura(apertura_file(tmp_path))
    tapete = [p for p in a["pending_rows"] if p["ref"] == "#9"][0]
    assert tapete["owner_label"] == "sin responsable"
    assert tapete["owner_named"] is False
    assert "owner_flag" not in tapete


def test_un_nombre_sin_declarar_confirmacion_no_se_dibuja(tmp_path):
    # Esta es la regla que importa mas que el campo. Un nombre a secas insinua
    # que el renglon tiene dueño aceptado, y quien lee el tablero es el dueño del
    # negocio: ahi un supuesto publicado como hecho es peor que no poner nombre.
    with pytest.raises(DashboardError) as exc:
        load_apertura(apertura_file(
            tmp_path, blockers=[{"ref": "#27", "title": "Materia prima",
                                 "owner": "Said Nuñez"},
                                {"ref": "Anexo J", "title": "Permisos",
                                 "off_sheet": True}]))
    assert "owner_confirmed" in str(exc.value)
    assert "#27" in str(exc.value)


def test_declarar_confirmado_exige_decir_donde_consta(tmp_path):
    # Una confirmacion sin cita no se puede auditar, y este rotulo solo se cae
    # cuando el dueño habla. Sin `owner_confirmed_ref` cualquiera podria apagar
    # el «sin confirmar» editando un booleano.
    with pytest.raises(DashboardError) as exc:
        load_apertura(apertura_file(
            tmp_path, blockers=[{"ref": "#27", "title": "Materia prima",
                                 "owner": "Said Nuñez", "owner_confirmed": True},
                                {"ref": "Anexo J", "title": "Permisos",
                                 "off_sheet": True}]))
    assert "owner_confirmed_ref" in str(exc.value)

    # Con la cita si pasa, y entonces el renglon deja de rotular el supuesto.
    a = load_apertura(apertura_file(
        tmp_path, blockers=[{"ref": "#27", "title": "Materia prima",
                             "owner": "Said Nuñez", "owner_confirmed": True,
                             "owner_confirmed_ref": "BOS-111 comentario 8e0cb33d"},
                            {"ref": "Anexo J", "title": "Permisos",
                             "off_sheet": True}]))
    assert a["blockers"][0]["owner_label"] == "Said Nuñez"
    assert "owner_flag" not in a["blockers"][0]


def test_un_dueño_supuesto_se_dibuja_con_su_rotulo_a_la_vista(tmp_path):
    a = load_apertura(apertura_file(
        tmp_path, blockers=[{"ref": "#27", "title": "Materia prima",
                             "owner": "Said Nuñez", "owner_confirmed": False,
                             "owner_note": "autoriza el gasto: Gustavo Jiménez"},
                            {"ref": "Anexo J", "title": "Permisos",
                             "off_sheet": True}]))
    blocker = a["blockers"][0]
    assert blocker["owner_label"] == "Said Nuñez"
    assert blocker["owner_flag"] == "sin confirmar"

    # Y llega a la pagina. Ojo con lo que esto prueba: el modelo viaja embebido,
    # asi que "esta el nombre en el HTML" tambien seria cierto si el renderizador
    # lo ignorara. Lo que se afirma aqui es el cableado —el renglon lee los tres
    # campos— y que el rotulo sea **texto del renglon** y no un `title=`, o sea
    # un tooltip que nadie va a abrir.
    html = render_html(dict(model([sale("2026-10-03", 200.0)]), apertura=a))
    assert "Said Nuñez" in html
    assert "autoriza el gasto: Gustavo Jiménez" in html
    for campo in ("item.owner_label", "item.owner_flag", "item.owner_note"):
        assert campo in html, f"el renglon dejo de leer {campo}"
    # El rotulo se agrega como hijo con texto (`el(...)` pone `textContent`), no
    # como atributo: el renglon del panel no setea ningun `.title`. (En otras
    # partes de la pagina si hay tooltips —la columna de efectivo tiene uno—, asi
    # que el control va sobre esta funcion y no sobre el HTML entero.)
    assert 'el("span", "unconf", item.owner_flag)' in html
    renglon = html.split("function row(item, isBlocker) {")[1].split("\n    }")[0]
    assert ".title =" not in renglon and "title:" not in renglon


def test_el_mismo_renglon_no_puede_terminar_con_dos_dueños(tmp_path):
    # El mismo `ref` es el mismo renglon de la hoja. El nombre se escribe una vez
    # —en el bloqueante— y el pendiente homonimo lo hereda, porque duplicarlo a
    # mano es como se llega a que #27 diga «Said Nuñez» arriba y «sin
    # responsable» abajo el dia que alguien edite solo uno de los dos.
    a = load_apertura(apertura_file(
        tmp_path, blockers=[{"ref": "#27", "title": "Materia prima",
                             "owner": "Said Nuñez", "owner_confirmed": False},
                            {"ref": "Anexo J", "title": "Permisos",
                             "off_sheet": True}]))
    gemelo = [p for p in a["pending_rows"] if p["ref"] == "#27"][0]
    assert gemelo["owner_label"] == "Said Nuñez"
    assert gemelo["owner_flag"] == "sin confirmar"


def test_el_vencimiento_se_calcula_de_la_fecha_no_se_escribe(tmp_path):
    # Mismo principio que la antiguedad del corte: un «vencido desde el 25/09»
    # escrito a mano sobrevive a que la fecha cambie, y entonces el tablero
    # afirma un vencimiento que ya no es el que dice el dato.
    a = load_apertura(apertura_file(
        tmp_path, pending_rows=[{"ref": "#27", "title": "Materia prima"},
                                {"ref": "#7", "title": "Botes de basura",
                                 "overdue_since": "2026-09-25"}]))
    bote = [p for p in a["pending_rows"] if p["ref"] == "#7"][0]
    assert bote["overdue_label"] == "vencido desde el 25/09"

    with pytest.raises(DashboardError) as exc:
        load_apertura(apertura_file(
            tmp_path, pending_rows=[{"ref": "#27", "title": "Materia prima"},
                                    {"ref": "#7", "title": "Botes",
                                     "overdue_since": "el jueves"}]))
    assert "overdue_since" in str(exc.value)


def test_el_conteo_de_responsables_se_cuenta_sobre_lo_dibujado(tmp_path):
    # El panel no repite los pendientes que ya salen como bloqueantes, asi que el
    # conteo tiene que ser sobre los renglones dibujados. Sobre los de la hoja
    # diria que faltan nombres en renglones que la lista no muestra.
    a = load_apertura(apertura_file(
        tmp_path, blockers=[{"ref": "#27", "title": "Materia prima",
                             "owner": "Said Nuñez", "owner_confirmed": False},
                            {"ref": "Anexo J", "title": "Permisos",
                             "off_sheet": True}]))
    refs = {str(b["ref"]) for b in a["blockers"]}
    dibujados = a["blockers"] + [p for p in a["pending_rows"]
                                 if str(p["ref"]) not in refs]
    # 2 bloqueantes + 1 pendiente (#9); #27 no se repite.
    assert len(dibujados) == 3
    assert sum(1 for r in dibujados if r["owner_named"]) == 1
    # El rotulo del conteo lo arma la pagina con estos campos, no con un numero
    # escrito en el JSON.
    html = render_html(dict(model([sale("2026-10-03", 200.0)]), apertura=a))
    assert "renglones abiertos con responsable con nombre" in html


def test_el_panel_no_rompe_el_autocontenido_de_la_pagina(tmp_path):
    from datetime import datetime, timezone

    a = load_apertura(apertura_file(tmp_path),
                      now=datetime(2026, 10, 4, 18, 0, tzinfo=timezone.utc))
    m = model([sale("2026-10-03", 200.0)])
    m = dict(m, apertura=a)
    html = render_html(m)
    # La hoja si es un enlace de salida (el panel dice de donde sale el numero),
    # pero la pagina sigue sin *traer* nada: ningun recurso se descarga.
    assert "drive.google.com" in html
    for remote in ("src=", "@import", "fetch(", "XMLHttpRequest", "@font-face",
                   "//cdn"):
        assert remote not in html, f"el tablero dejo de ser autocontenido: {remote}"


# --------------------------------------------------------------------------
# 6. Un panel que no cuadra no se lleva el tablero entero (BOS-144)
# --------------------------------------------------------------------------
#
# El republicado automatico corre despues de cada carga de Clip. Ahi la
# alternativa a un panel desfasado **no** es "ningun tablero": es el tablero de
# ayer, que es el que ya esta publicado. Tumbar la republicacion para proteger un
# conteo de pendientes cambiaria un dato viejo rotulado por un dato viejo sin
# rotular, que es la averia que BOS-144 viene a cerrar.

def test_a_mano_un_panel_que_no_cuadra_sigue_tronando(tmp_path):
    # La forma estricta no se relaja: quien corre el comando a proposito quiere
    # enterarse de que el JSON se desfaso, no publicar sin panel.
    with pytest.raises(DashboardError):
        load_apertura(apertura_file(tmp_path, source={"rows": 9}))


def test_el_republicado_se_queda_sin_panel_pero_no_sin_tablero(tmp_path):
    from dashboard import load_apertura_degrading

    apertura, error = load_apertura_degrading(
        apertura_file(tmp_path, source={"rows": 9}))
    assert apertura is None
    assert "no cuadra" in error

    m = model([sale("2026-10-03", 200.0)])
    m = dict(m, apertura=None, apertura_error=error)
    html = render_html(m)
    # La venta sigue publicada...
    assert series_of(m, "casa-dorelia")["2026-10-03"]["gross"] == 200.0
    # ...y la razon de que falte el panel viaja en la pagina, no en un log que
    # nadie abre. Sin esto la tarjeta desaparece y el tablero queda identico al
    # de un dia sin bloqueantes: "ya no falta nada" es la lectura mas cara.
    assert "no cuadra" in html


def test_sin_archivo_de_apertura_no_hay_error_que_reportar():
    from dashboard import load_apertura_degrading

    # Nadie pidio panel: los dos campos nulos. Es distinto de "se pidio y fallo",
    # y la pagina los dibuja distinto (tarjeta oculta vs tarjeta con la razon).
    assert load_apertura_degrading(None) == (None, None)
    m = model([sale("2026-10-03", 200.0)])
    assert m["apertura"] is None and m["apertura_error"] is None
    assert 'id="apertura-card" hidden' in render_html(m)


def test_el_error_del_panel_no_se_publica_si_el_panel_si_salio(tmp_path):
    from datetime import datetime, timezone

    # Un `apertura_error` colgado junto a un panel bueno diria que falta algo que
    # esta ahi. El modelo lo descarta en vez de dibujar los dos.
    a = load_apertura(apertura_file(tmp_path),
                      now=datetime(2026, 10, 4, 18, 0, tzinfo=timezone.utc))
    m = build_model([sale("2026-10-03", 200.0)], title="t", today="2026-10-04",
                    apertura=a, apertura_error="algo que ya no aplica")
    assert m["apertura"] is not None
    assert m["apertura_error"] is None


# --------------------------------------------------------------------------
# 7. La pagina dice su propia edad al abrirla, no al generarla (BOS-144)
# --------------------------------------------------------------------------

def test_el_umbral_de_vejez_sale_del_hueco_entre_republicaciones():
    from dashboard import STALE_AFTER_HOURS

    # 07:45 y 19:45: el hueco mas largo entre republicaciones es de 12 h, asi que
    # el umbral tiene que estar arriba de 12 (si no, un tablero sano se declara
    # viejo cada tarde) y lo bastante cerca para que una republicacion perdida se
    # note el mismo dia. No es un numero de gusto.
    assert _minutos(SNAPSHOT_LOCAL) - _minutos(MORNING_CATCHUP_LOCAL) == 12 * 60
    assert 12 < STALE_AFTER_HOURS <= 24


def _minutos(hhmm):
    hora, minuto = hhmm.split(":")
    return int(hora) * 60 + int(minuto)


def test_la_pagina_lleva_lo_necesario_para_calcular_su_edad_sola():
    m = model([sale("2026-10-03", 200.0)])
    html = render_html(m)

    # El calculo es del lado del lector: `generated_at` es absoluto y con huso,
    # para que la resta contra `Date.now()` no dependa de la zona del navegador.
    assert m["generated_at"].endswith("-06:00")
    assert m["config"]["stale_after_hours"] == 13
    # Y el aviso nace oculto: un tablero recien generado no se acusa de viejo.
    assert 'id="stale-note" hidden' in html
    assert "stale_after_hours" in html


# --------------------------------------------------------------------------
# 8. Una sucursal cerrada no vendio cero (BOS-147, BOS-148)
# --------------------------------------------------------------------------
#
# Un dia sin cobro dentro de la ventana de la marca es un cero *medido*, y eso
# solo es correcto si la sucursal estuvo abierta. Tecnoparque no cobro del 5/08
# al 20/09/2026 ni del 21/04 al 10/05, asi que el tablero estaba afirmando que
# abrio y vendio $0 — 67 veces, una por dia. Estas pruebas cuidan que la ventana
# convierta esos ceros en huecos **y** que no pueda hacer tres cosas: tapar
# venta, morirse en silencio, y solaparse consigo misma.

CIERRES = {
    "source": "BOS-147, Jefatura de Tecnoparque",
    "windows": [{"brand": "le-pain-dore", "from": "2026-09-28", "to": "2026-09-30",
                 "note": "no opero"}],
}


def cierres_file(tmp_path, data=None, name="cierres.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data if data is not None else CIERRES),
                    encoding="utf-8")
    return str(path)


def con_cierres(rows, windows, *, today="2026-10-04", source="prueba"):
    from datetime import datetime, timezone

    from business_day import BUSINESS_TZ

    now = datetime.fromisoformat(today + "T00:00:00").replace(
        hour=12, tzinfo=BUSINESS_TZ).astimezone(timezone.utc)
    cierres = {"source": source, "windows": [
        {"label": "sin operacion", "note": None,
         "days": 1, **w} for w in windows]}
    return build_model(rows, title="t", today=today, now=now,
                       db_name="prueba", cierres=cierres)


def test_un_dia_declarado_sin_operacion_es_hueco_no_un_cero_medido():
    m = con_cierres(
        [sale("2026-09-27", 500.0, brand="le-pain-dore"),
         sale("2026-10-01", 300.0, brand="le-pain-dore")],
        [{"brand": "le-pain-dore", "from": "2026-09-28", "to": "2026-09-30"}])

    lp = series_of(m, "le-pain-dore")
    # Los tres dias del cierre: hueco con rotulo, no un cero que se grafica como
    # derrumbe y se lee como "abrio y no vendio nada".
    for day in ("2026-09-28", "2026-09-29", "2026-09-30"):
        assert lp[day]["gross"] is None, day
        assert lp[day]["tickets"] is None, day
        assert lp[day]["closed"] == "sin operacion", day
    # El dia de antes y el de despues no se tocan.
    assert lp["2026-09-27"]["gross"] == 500.0
    assert lp["2026-10-01"]["gross"] == 300.0
    # Y el estado del eje lo dice con todas sus letras, como ya decia "en curso".
    assert m["day_states"]["2026-09-29"] == "sin_operacion"


def test_la_ventana_no_puede_tapar_un_dia_que_si_cobro():
    """El cobro gana. Un archivo de configuracion no puede borrar venta.

    Es el control que importa: si alguien se equivoca de fechas, lo caro no es
    que falte el rotulo, es que desaparezcan pesos del tablero sin dejar rastro.
    """
    m = con_cierres(
        [sale("2026-09-27", 500.0, brand="le-pain-dore"),
         sale("2026-09-29", 120.0, brand="le-pain-dore")],
        [{"brand": "le-pain-dore", "from": "2026-09-28", "to": "2026-09-30"}])

    lp = series_of(m, "le-pain-dore")
    assert lp["2026-09-29"]["gross"] == 120.0          # el cobro se dibuja
    assert "closed" not in lp["2026-09-29"]
    assert lp["2026-09-28"]["gross"] is None           # el resto sigue en hueco
    # ...y la contradiccion no se queda callada: sale en los controles del dato.
    conflicts = m["cierres"]["conflicts"]
    assert [c["date"] for c in conflicts] == ["2026-09-29"]
    assert conflicts[0]["gross"] == 120.0
    checks = {c["id"]: c for c in m["quality"]["checks"]}
    assert checks["cierres"]["count"] == 1
    assert checks["cierres"]["status"] == "critical"
    # El dia tiene cobro, asi que el eje no puede llamarlo sin operacion.
    assert m["day_states"]["2026-09-29"] == "cerrado"


def test_una_ventana_con_la_marca_mal_escrita_no_se_muere_en_silencio():
    # Un slug equivocado no tapa nada, y "no hacer nada" es exactamente como se
    # deja de notar que la ventana dejo de servir.
    m = con_cierres([sale("2026-10-01", 300.0, brand="le-pain-dore")],
                    [{"brand": "le-pain-doree", "from": "2026-09-28",
                      "to": "2026-09-30"}])

    assert [w["brand"] for w in m["cierres"]["unknown_brands"]] == ["le-pain-doree"]
    checks = {c["id"]: c for c in m["quality"]["checks"]}
    assert checks["cierres"]["count"] == 1
    assert "le-pain-doree" in render_html(m)


def test_la_marca_cerrada_no_cierra_a_la_otra():
    """La columna de estado es una sola para todo el eje, asi que solo puede
    decir "sin operacion" cuando no opero nadie. Con Tecnoparque cerrada y SJI
    vendiendo, el renglon es el de SJI y el rotulo va en la celda de Tecnoparque.
    """
    m = con_cierres(
        [sale("2026-09-27", 500.0, brand="le-pain-dore"),
         sale("2026-09-27", 100.0, brand="casa-dorelia"),
         sale("2026-09-29", 200.0, brand="casa-dorelia")],
        [{"brand": "le-pain-dore", "from": "2026-09-28", "to": "2026-09-30"}])

    assert series_of(m, "le-pain-dore")["2026-09-29"]["closed"] == "sin operacion"
    assert series_of(m, "casa-dorelia")["2026-09-29"]["gross"] == 200.0
    # SJI vendio ese dia: el eje no puede declararlo sin operacion.
    assert m["day_states"]["2026-09-29"] == "cerrado"
    # Y el 28, con las dos sin cobro pero solo una declarada cerrada, sigue
    # siendo un cero medido para SJI.
    assert series_of(m, "casa-dorelia")["2026-09-28"]["gross"] == 0.0
    assert m["day_states"]["2026-09-28"] == "sin_cobro"


def test_las_ventanas_de_la_marca_viven_en_su_renglon_y_no_en_uno_global():
    m = con_cierres(
        [sale("2026-09-27", 500.0, brand="le-pain-dore"),
         sale("2026-09-27", 100.0, brand="casa-dorelia")],
        [{"brand": "le-pain-dore", "from": "2026-09-28", "to": "2026-09-30"}])

    por_marca = {b["brand"]: b["no_operacion"] for b in m["brands"]}
    assert por_marca["casa-dorelia"] == []
    assert len(por_marca["le-pain-dore"]) == 1


# ---- los controles del archivo ------------------------------------------

def test_el_archivo_de_cierres_exige_marca_y_fechas(tmp_path):
    from dashboard import load_cierres

    # Sin marca la ventana aplicaria a todo el tablero, que es lo contrario de
    # lo que se declaro.
    with pytest.raises(DashboardError) as exc:
        load_cierres(cierres_file(tmp_path, {
            "source": "x",
            "windows": [{"from": "2026-08-05", "to": "2026-09-20"}]}))
    assert "`brand`" in str(exc.value)

    with pytest.raises(DashboardError) as exc:
        load_cierres(cierres_file(tmp_path, {
            "source": "x", "windows": [{"brand": "le-pain-dore", "from": "2026-08-05"}]}))
    assert "`to`" in str(exc.value)


def test_una_ventana_invertida_truena_en_vez_de_no_marcar_nada(tmp_path):
    from dashboard import load_cierres

    # `from > to` no cubre ni un dia, y un archivo que no hace nada se ve igual
    # que uno que funciona.
    with pytest.raises(DashboardError) as exc:
        load_cierres(cierres_file(tmp_path, {
            "source": "x",
            "windows": [{"brand": "le-pain-dore", "from": "2026-09-20",
                         "to": "2026-08-05"}]}))
    assert "invertida" in str(exc.value)


def test_dos_ventanas_de_la_misma_marca_no_se_pueden_solapar(tmp_path):
    from dashboard import load_cierres

    with pytest.raises(DashboardError) as exc:
        load_cierres(cierres_file(tmp_path, {
            "source": "x",
            "windows": [{"brand": "le-pain-dore", "from": "2026-08-05", "to": "2026-09-20"},
                        {"brand": "le-pain-dore", "from": "2026-09-01", "to": "2026-09-25"}]}))
    assert "se solapan" in str(exc.value)

    # Dos marcas distintas en las mismas fechas si: son dos sucursales.
    ok = load_cierres(cierres_file(tmp_path, {
        "source": "x",
        "windows": [{"brand": "le-pain-dore", "from": "2026-08-05", "to": "2026-09-20"},
                    {"brand": "casa-dorelia", "from": "2026-08-05", "to": "2026-09-20"}]}))
    assert len(ok["windows"]) == 2


def test_los_dias_de_la_ventana_se_cuentan_no_se_escriben(tmp_path):
    from dashboard import load_cierres

    # 5/08 a 20/09 son 47 dias naturales. Un conteo escrito a mano en el JSON se
    # desfasa en cuanto alguien mueve un extremo.
    c = load_cierres(cierres_file(tmp_path, {
        "source": "x",
        "windows": [{"brand": "le-pain-dore", "from": "2026-08-05", "to": "2026-09-20",
                     "days": 3}]}))
    assert c["windows"][0]["days"] == 47
    assert c["windows"][0]["label"] == "sin operacion"


def test_el_archivo_real_declara_los_dos_cierres_de_tecnoparque():
    from dashboard import load_cierres

    # El archivo que se publica, validado por las mismas reglas. Las fechas son
    # la determinacion de BOS-147: no se derivan del dato, asi que si alguien las
    # cambia tiene que cambiar esta prueba con ellas.
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "cierres-casa-dorelia.json")
    c = load_cierres(path)
    assert "BOS-147" in c["source"]
    assert [(w["brand"], w["from"], w["to"], w["days"]) for w in c["windows"]] == [
        ("le-pain-dore", "2026-04-21", "2026-05-10", 20),
        ("le-pain-dore", "2026-08-05", "2026-09-20", 47),
    ]


# ---- degradar sin esconder ----------------------------------------------

def test_a_mano_un_archivo_de_cierres_roto_sigue_tronando(tmp_path):
    from dashboard import load_cierres

    with pytest.raises(DashboardError):
        load_cierres(cierres_file(tmp_path, {"source": "x", "windows": []}))


def test_el_republicado_se_queda_sin_ventanas_pero_lo_dice_en_la_pagina(tmp_path):
    from dashboard import load_cierres_degrading

    cierres, error = load_cierres_degrading(
        cierres_file(tmp_path, {"source": "x", "windows": []}))
    assert cierres is None
    assert "ni una sola ventana" in error

    # Degradar aqui cuesta mas que con el panel de apertura: sin ventanas vuelven
    # los ceros falsos. Asi que la razon tiene que viajar **en la pagina**, junto
    # a los ceros que la ventana iba a rotular, no solo en la consola.
    m = model([sale("2026-10-02", 200.0), sale("2026-10-03", 300.0)])
    m = dict(m, cierres=None, cierres_error=error)
    assert "ni una sola ventana" in render_html(m)


def test_sin_archivo_de_cierres_no_hay_error_que_reportar():
    from dashboard import load_cierres_degrading

    assert load_cierres_degrading(None) == (None, None)
    m = model([sale("2026-10-03", 200.0)])
    assert m["cierres"] is None and m["cierres_error"] is None


def test_el_error_de_los_cierres_no_se_publica_si_las_ventanas_si_salieron():
    m = con_cierres([sale("2026-10-01", 300.0, brand="le-pain-dore")],
                    [{"brand": "le-pain-dore", "from": "2026-09-28",
                      "to": "2026-09-30"}])
    assert m["cierres"] is not None
    assert m["cierres_error"] is None


def test_la_fuente_del_cierre_viaja_hasta_la_pagina():
    # Un hueco sin dueño es indistinguible de un hueco inventado, y este es el
    # unico limite del tablero que no sale del dato sino de una determinacion.
    m = con_cierres([sale("2026-09-27", 500.0, brand="le-pain-dore"),
                     sale("2026-10-01", 300.0, brand="le-pain-dore")],
                    [{"brand": "le-pain-dore", "from": "2026-09-28",
                      "to": "2026-09-30"}],
                    source="BOS-147, Jefatura de Tecnoparque")
    assert "BOS-147, Jefatura de Tecnoparque" in render_html(m)


# --------------------------------------------------------------------------
# 9. El rotulo de piso se mueve en las dos direcciones (BOS-149)
# --------------------------------------------------------------------------
#
# El efectivo no viaja por la API de Clip: lo captura la sucursal al cerrar
# (`cash_cut.py`, BOS-119). Mientras eso no se dibujaba aqui, el tablero
# rotulaba piso los 365 dias del eje — tambien los que ya tenian corte — y ese
# rotulo estaba *escrito*, no calculado.
#
# Estas pruebas fijan las dos direcciones, porque las dos se rompen distinto:
# un dia con corte que siga diciendo piso esconde venta ya contada, y un dia
# sin corte que deje de decirlo publica un piso como si fuera la venta. La
# segunda es la mas cara, y la que mas facil se cuela: basta que el de al lado
# tenga corte.


def corte(day, cash, *, brand="casa-dorelia", turno="completo", **extra):
    """Un corte de caja como lo deja `cash_cut.build_cut`, con lo que se lee.

    Se arma a mano (igual que `sale`) para que la prueba no dependa de la fecha
    real: `build_cut` calcula `captured_late` contra el dia de hoy, y entonces
    el mismo caso cambiaria de resultado segun el dia en que corran las
    pruebas. Que esta forma siga siendo la del documento real lo cuida
    `test_la_forma_del_corte_es_la_que_de_verdad_guarda_cash_cut`.
    """
    doc = {
        "id": f"{brand}-{day}-{turno}",
        "cafeteria_id": "c-sji" if brand == "casa-dorelia" else "c-tecno",
        "brand": brand,
        "business_date": day,
        "turno": turno,
        "ventas_efectivo": cash,
        "tickets_efectivo": None,
        "payment_method": "efectivo",
        "source": "corte_caja",
        "captured_late": False,
        "revisions": [],
    }
    doc.update(extra)
    return doc


def test_la_forma_del_corte_es_la_que_de_verdad_guarda_cash_cut():
    """Control positivo: si el documento real cambia, estas pruebas lo dicen.

    Sin esto, `corte()` podria quedarse con un campo que `cash_cut` ya no
    escribe y las nueve pruebas de abajo seguirian en verde contra un documento
    que no existe — la forma mas callada de perder una prueba.
    """
    import cash_cut

    real = cash_cut.build_cut(cafeteria_id="c-sji", brand="casa-dorelia",
                              business_date="2026-10-03", fondo_inicial=500.0,
                              efectivo_contado=1700.0, retiros=0)
    for campo in ("brand", "business_date", "turno", "ventas_efectivo",
                  "cafeteria_id", "captured_late", "revisions"):
        assert campo in real, campo
    assert real["ventas_efectivo"] == 1200.0


def test_un_dia_con_corte_publica_el_total_y_deja_de_decir_piso():
    m = model([sale("2026-10-03", 800.0)],
              cortes=[corte("2026-10-03", 1200.0)])

    dia = series_of(m, "casa-dorelia")["2026-10-03"]
    assert dia["gross"] == 800.0            # la tarjeta sigue siendo la tarjeta
    assert dia["cash"] == 1200.0            # y el efectivo del corte esta
    assert dia["gross_total"] == 2000.0     # el total del dia, publicado
    assert dia["cash_state"] == "con_corte"
    assert m["limits"]["cash"]["days_covered"] == 1
    assert m["limits"]["cash"]["all_missing"] is False


def test_el_dia_de_al_lado_sin_corte_sigue_siendo_piso():
    """Las dos direcciones en el mismo tablero. Es el caso que importa.

    Un dia con corte deja de ser piso y el de al lado **no**: el rotulo es por
    dia, no un booleano para todo el eje. Con un solo flag global, el primer
    corte capturado habria dejado de rotular piso los otros 364 dias.
    """
    m = model([sale("2026-10-02", 500.0), sale("2026-10-03", 800.0)],
              cortes=[corte("2026-10-03", 1200.0)])

    dias = series_of(m, "casa-dorelia")
    assert dias["2026-10-03"]["gross_total"] == 2000.0
    assert dias["2026-10-03"]["cash_state"] == "con_corte"
    # El de al lado: hueco en el efectivo (no un cero) y sin total.
    assert dias["2026-10-02"]["cash"] is None
    assert dias["2026-10-02"]["cash_state"] == "sin_corte"
    assert dias["2026-10-02"]["gross_total"] is None
    assert dias["2026-10-02"]["gross"] == 500.0      # su piso sigue a la vista
    assert m["limits"]["cash"]["days_covered"] == 1
    assert m["limits"]["cash"]["days_missing"] >= 1
    assert m["limits"]["cash"]["none_missing"] is False


def test_un_corte_en_cero_no_es_un_hueco():
    """`ventas_efectivo: 0.0` es un cero medido, y es lo que cita el dia.

    Es la trampa del modulo: tratar el cero como "no hay dato" borraria justo
    la informacion que vuelve completo ese dia — la sucursal abrio y no cobro
    efectivo, asi que su bruto con tarjeta **ya es** la venta del dia.
    """
    m = model([sale("2026-10-03", 800.0)], cortes=[corte("2026-10-03", 0.0)])

    dia = series_of(m, "casa-dorelia")["2026-10-03"]
    assert dia["cash"] == 0.0
    assert dia["cash_state"] == "con_corte"      # no "sin_corte"
    assert dia["gross_total"] == 800.0           # citable, no piso
    assert m["limits"]["cash"]["days_covered"] == 1


def test_el_corte_de_una_marca_no_completa_el_dia_de_la_otra():
    """Dos sucursales, dos cajones. Un corte nunca cruza la marca."""
    m = model([sale("2026-10-03", 800.0, brand="casa-dorelia"),
               sale("2026-10-03", 300.0, brand="le-pain-dore")],
              cortes=[corte("2026-10-03", 1200.0, brand="casa-dorelia")])

    cd = series_of(m, "casa-dorelia")["2026-10-03"]
    lp = series_of(m, "le-pain-dore")["2026-10-03"]
    assert cd["gross_total"] == 2000.0
    assert lp["cash"] is None
    assert lp["cash_state"] == "sin_corte"
    assert lp["gross_total"] is None
    # Y el efectivo de las dos marcas no se suma en ninguna parte del modelo:
    # 1200.0 es de una sola, y un 1500.0 (300 + 1200) seria un reparto cruzado.
    assert 1500.0 not in set(_numeros(m))


def test_los_turnos_del_mismo_dia_suman_y_los_duplicados_no():
    """Dos turnos son dos cajones; dos cortes del mismo turno son uno mal."""
    m = model([sale("2026-10-03", 800.0)],
              cortes=[corte("2026-10-03", 700.0, turno="matutino"),
                      corte("2026-10-03", 500.0, turno="vespertino")])
    assert series_of(m, "casa-dorelia")["2026-10-03"]["gross_total"] == 2000.0
    assert m["cortes"]["duplicates"] == []

    # El mismo turno dos veces: el indice unico lo impide al guardar, pero una
    # base sin indice si puede tenerlo y sumarlo duplica la venta del dia.
    doble = model([sale("2026-10-03", 800.0)],
                  cortes=[corte("2026-10-03", 700.0, turno="matutino"),
                          corte("2026-10-03", 700.0, turno="matutino")])
    assert len(doble["cortes"]["duplicates"]) == 1
    checks = {c["id"]: c for c in doble["quality"]["checks"]}
    assert checks["cortes"]["count"] == 1
    assert checks["cortes"]["status"] == "critical"


def test_un_corte_tarde_o_corregido_se_marca_en_su_dia():
    """Ese numero se recordo o se corrigio: cuenta igual, no se cita igual."""
    m = model([sale("2026-10-03", 800.0), sale("2026-10-02", 400.0)],
              cortes=[corte("2026-10-03", 1200.0, captured_late=True),
                      corte("2026-10-02", 900.0,
                            revisions=[{"reason": "faltaba un retiro"}])])

    dias = series_of(m, "casa-dorelia")
    assert dias["2026-10-03"]["cash_late"] is True
    assert "cash_revised" not in dias["2026-10-03"]
    assert dias["2026-10-02"]["cash_revised"] is True
    assert "cash_late" not in dias["2026-10-02"]
    # El dinero entra igual: marcar no es descartar.
    assert dias["2026-10-03"]["gross_total"] == 2000.0
    assert m["limits"]["cash"]["late_cuts"] == 1
    assert m["limits"]["cash"]["revised_cuts"] == 1
    assert "tarde" in render_html(m)


def test_el_efectivo_que_ya_estaba_en_el_bruto_no_se_cuenta_dos_veces():
    """Un renglon de venta en efectivo + un corte del mismo dia = un peso doble.

    Hoy no pasa (la sucursal no usa el punto de venta), y por eso mismo tiene
    que estar probado: el dia que se use, nadie se va a acordar de esta resta.
    Gana el bruto, que tiene el cobro renglon por renglon.
    """
    m = model([sale("2026-10-03", 800.0),
               sale("2026-10-03", 300.0, payment_method="efectivo")],
              cortes=[corte("2026-10-03", 300.0)])

    dia = series_of(m, "casa-dorelia")["2026-10-03"]
    assert dia["gross"] == 1100.0          # el bruto ya traia el efectivo
    assert dia["gross_total"] is None      # no se le suma el corte encima
    assert dia["cash_state"] == "doble"
    assert 1400.0 not in set(_numeros(m))  # el total con el peso duplicado
    assert len(m["cortes"]["double_counted"]) == 1
    checks = {c["id"]: c for c in m["quality"]["checks"]}
    assert checks["cortes"]["count"] == 1


def test_el_total_citable_es_el_de_los_dias_con_corte_y_solo_esos():
    """Sumar el efectivo que haya contra el bruto de todo el rango da una cifra
    mitad completa y mitad piso: no se puede citar ni como una cosa ni como la
    otra, y la tabla no tiene donde decirlo."""
    m = model([sale("2026-10-02", 500.0), sale("2026-10-03", 800.0)],
              cortes=[corte("2026-10-03", 1200.0)])

    totales = m["brands"][0]["totals"]
    assert totales["gross"] == 1300.0            # la tarjeta de los dos dias
    assert totales["con_corte"]["days"] == 1
    assert totales["con_corte"]["total"] == 2000.0   # solo el dia con corte
    assert totales["con_corte"]["first_day"] == "2026-10-03"
    # 2500.0 (los 1300 de tarjeta + los 1200 de efectivo de un solo dia) es
    # justo la cifra mitad piso que no puede existir en el modelo.
    assert 2500.0 not in set(_numeros(m))


def test_no_preguntar_los_cortes_no_es_lo_mismo_que_no_tener_ninguno():
    """Los dos salen en piso, pero solo uno se arregla capturando un corte."""
    sin_preguntar = model([sale("2026-10-03", 800.0)])
    assert sin_preguntar["cortes"] is None
    assert sin_preguntar["limits"]["cash"]["consulted"] is False
    # Sin preguntar, la celda no dice "sin corte": no se sabe.
    assert "cash_state" not in series_of(sin_preguntar, "casa-dorelia")["2026-10-03"]

    preguntado = model([sale("2026-10-03", 800.0)], cortes=[])
    assert preguntado["cortes"]["cuts"] == 0
    assert preguntado["limits"]["cash"]["consulted"] is True
    assert series_of(preguntado, "casa-dorelia")["2026-10-03"]["cash_state"] == "sin_corte"


def test_un_corte_que_no_se_pudo_leer_no_se_publica_como_que_no_hay():
    """"Falta el efectivo" y "no pude preguntar por el efectivo" no son lo mismo.

    Las dos dibujan piso, asi que sin publicar la razon se verian iguales — y
    una se arregla capturando mientras la otra se arregla levantando Mongo.
    """
    m = model([sale("2026-10-03", 800.0)])
    m = dict(m, cortes=None, cortes_error="falta `DB_NAME` (o --db)")
    assert "no se pudieron leer los cortes" in render_html(m).lower()

    # Y al reves: con cortes leidos, el error no se publica.
    ok = model([sale("2026-10-03", 800.0)], cortes=[corte("2026-10-03", 10.0)])
    assert ok["cortes_error"] is None


def test_el_total_del_dia_viaja_hasta_la_pagina():
    m = model([sale("2026-10-02", 500.0), sale("2026-10-03", 800.0)],
              cortes=[corte("2026-10-03", 1200.0)])
    html = render_html(m)

    # El total del dia con corte y el rotulo del dia sin corte, los dos en la
    # pagina: el modelo puede tenerlos y la plantilla no dibujarlos.
    assert "2000.0" in html
    assert "sin corte" in html
    assert "con corte" in html


def test_un_corte_en_un_dia_declarado_sin_operacion_sale_a_los_controles():
    """Las dos cosas no pueden ser ciertas, y el dinero no se borra."""
    from datetime import datetime, timezone

    from business_day import BUSINESS_TZ

    now = datetime.fromisoformat("2026-10-04T00:00:00").replace(
        hour=12, tzinfo=BUSINESS_TZ).astimezone(timezone.utc)
    cierres = {"source": "prueba", "windows": [
        {"brand": "le-pain-dore", "from": "2026-09-28", "to": "2026-09-30",
         "label": "sin operacion", "note": None, "days": 3}]}
    m = build_model([sale("2026-09-27", 500.0, brand="le-pain-dore"),
                     sale("2026-10-01", 300.0, brand="le-pain-dore")],
                    title="t", today="2026-10-04", now=now, db_name="prueba",
                    cierres=cierres,
                    cortes=[corte("2026-09-29", 400.0, brand="le-pain-dore")])

    dia = series_of(m, "le-pain-dore")["2026-09-29"]
    assert dia["closed"] == "sin operacion"
    assert dia["cash"] == 400.0        # el dinero se dibuja igual
    assert dia["gross_total"] is None  # no hay tarjeta con que totalizar
    assert len(m["cortes"]["on_closed_days"]) == 1
    checks = {c["id"]: c for c in m["quality"]["checks"]}
    assert checks["cortes"]["count"] == 1


def test_el_rotulo_de_los_controles_cuenta_su_propia_lista():
    # Decia "los cinco"; al entrar el sexto control el texto se quedo mintiendo
    # sobre su propia lista. Ahora el numero sale del modelo.
    m = model([sale("2026-10-03", 200.0)])
    assert len(m["quality"]["checks"]) == 7
    assert "Los cinco deben estar en cero" not in render_html(m)
