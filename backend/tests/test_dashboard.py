"""El tablero de ventas no puede mentir de las cuatro formas conocidas.

Estas pruebas no cuidan pixeles: cuidan que el tablero siga sin poder hacer las
cuatro cosas por las que una cifra de este negocio se lee mal.

1. **Un total consolidado.** Las dos marcas de `casa_dorelia` tienen repartos
   distintos (ver `test_brands.py`). La suma solo existe con el nombre
   `control_sum`; no hay ningun campo que se llame "total" y se pueda pegar en
   un reporte como "la venta".
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


def model(rows, *, today="2026-10-04", hour=12, minute=0):
    """Modelo armado en un instante fijo. La hora decide si ayer ya se confirmo."""
    from datetime import datetime, timezone

    from business_day import BUSINESS_TZ

    now = datetime.fromisoformat(today + "T00:00:00").replace(
        hour=hour, minute=minute, tzinfo=BUSINESS_TZ).astimezone(timezone.utc)
    return build_model(rows, title="t", today=today, now=now, db_name="prueba")


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


def test_la_suma_de_las_dos_solo_existe_como_suma_de_control():
    m = model([sale("2026-10-01", 100.0, brand="casa-dorelia"),
               sale("2026-10-01", 300.0, brand="le-pain-dore")])

    assert m["control_sum"]["gross"] == 400.0
    # Lo que protege el nombre: que no haya un campo pegable como "la venta".
    assert "total" not in m
    assert "gross" not in m


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
    m = model([sale("2026-10-03", 200.0)])
    assert m["limits"]["cash_excluded"] is True

    mixed = model([sale("2026-10-03", 200.0),
                   sale("2026-10-03", 50.0, payment_method="efectivo")])
    assert mixed["limits"]["cash_excluded"] is False


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
