"""El corte de las 08:00 nunca publica la cifra del dia en curso como total.

Sin Mongo y sin red: la coleccion es un doble y los instantes se inyectan.

La prueba central es la del dia que todavia no existe en la base real: un cobro
**antes** de las 07:45, que es el shape al que SJI se esta acercando (12:52 el
30/09/2026 -> 08:25 el 06/10/2026). Hoy ese dia haria que el corte de las 08:00
publicara los primeros minutos del dia como «venta del dia».
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from corte_window import (  # noqa: E402
    FINAL,
    PARCIAL,
    SIN_CARGA,
    SIN_CIFRA,
    SIN_EVIDENCIA,
    CorteWindowError,
    clasificar_dia,
    correr,
    dias_del_corte,
    leer_dia,
    main,
)

DIA = "2026-10-07"
AYER = "2026-10-06"

# Los dos slots reales de la rutina de carga, en UTC (CDMX es UTC-6).
CARGA_0745 = "2026-10-07T13:45:57+00:00"   # 07:45 CDMX del 07/10
CARGA_1945 = "2026-10-07T01:45:12+00:00"   # 19:45 CDMX del 06/10


class FakeSales:
    """Solo `find` y `count_documents`: el modulo no escribe nada."""

    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def find(self, query):
        self.queries.append(query)
        return [r for r in self.rows
                if all(r.get(k) == v for k, v in query.items())]

    def count_documents(self, query):
        return len(self.find(query))


def venta(*, day=DIA, branch="sji", cafeteria="c-sji", total=100.0,
          imported="2026-10-07T13:45:57+00:00"):
    return {"business_date": day, "clip_branch": branch, "cafeteria_id": cafeteria,
            "total": total, "imported_at": imported}


# --------------------------------------------------------------------------
# El criterio de cierre 1: un cobro antes de las 07:45 sale rotulado parcial
# --------------------------------------------------------------------------

def test_un_cobro_antes_de_las_0745_sale_parcial_con_su_hora_de_corte():
    """El shape al que SJI se acerca: cobro a las 07:20, carga a las 07:45.

    Es el dia en que la regla vieja («cero renglones a las 08:00») deja de
    proteger: hay renglones y son de los primeros minutos del dia.
    """
    verdict = clasificar_dia(day=DIA, renglones=1, bruto=85.0,
                             carga_at=CARGA_0745,
                             ultimo_imported_at=CARGA_0745,
                             etiqueta="Casa Dorelia SJI")

    assert verdict["estado"] == PARCIAL
    assert verdict["citable_como_total"] is False
    assert verdict["cobertura_hasta_local"] == "07:45"
    # Del 07:45 a las 24:00 quedan 16 h 15 min sin medir, y lo dice.
    assert verdict["falta_del_dia"] == "16 h 15 min"
    assert "PARCIAL" in verdict["rotulo"]
    assert "07:45" in verdict["rotulo"]
    assert "venta del dia" not in verdict["rotulo"].replace("No es la venta del dia", "")


def test_el_parcial_no_rellena_ni_estima_lo_que_falta():
    """Rotular, no rellenar: el bruto publicado es el medido, tal cual."""
    verdict = clasificar_dia(day=DIA, renglones=2, bruto=173.5,
                             carga_at=CARGA_0745, ultimo_imported_at=CARGA_0745)
    assert verdict["bruto"] == 173.5
    assert "$173.50" in verdict["rotulo"]


# --------------------------------------------------------------------------
# El criterio de cierre 2: sin cobros sigue siendo «no observable»
# --------------------------------------------------------------------------

def test_sin_cobros_a_las_0745_sigue_diciendo_no_observable():
    """Sin regresion: el caso que hoy funciona bien tiene que seguir igual."""
    verdict = clasificar_dia(day=DIA, renglones=0, bruto=0.0, carga_at=CARGA_0745)

    assert verdict["estado"] == SIN_CIFRA
    assert verdict["citable_como_total"] is False
    assert "No observable todavia" in verdict["rotulo"]
    assert verdict["cobertura_hasta_local"] == "07:45"


def test_cero_renglones_sin_citar_la_corrida_no_decide_nada():
    """Un dia sin cobros no escribe renglones: la ausencia de filas no es evidencia.

    Es la trampa de la que viene este estado: `max(imported_at)` solo prueba el
    ultimo *insert*, y una corrida que inserta cero no deja rastro. Sin citar la
    corrida, «no cobro» y «no corrio» son indistinguibles — y el modulo lo dice
    en vez de elegir uno.
    """
    verdict = clasificar_dia(day=DIA, renglones=0, bruto=0.0)

    assert verdict["estado"] == SIN_EVIDENCIA
    assert verdict["citable_como_total"] is False
    assert "citar la corrida" in verdict["rotulo"]


def test_una_corrida_anterior_al_dia_es_carga_faltante_no_dia_sin_venta():
    verdict = clasificar_dia(day=DIA, renglones=0, bruto=0.0,
                             carga_at="2026-10-06T23:00:00+00:00")  # 17:00 CDMX del 06/10

    assert verdict["estado"] == SIN_CARGA
    assert "no corrio" in verdict["rotulo"]


# --------------------------------------------------------------------------
# El criterio de cierre 3: la regla es estructural, no una hora de apertura
# --------------------------------------------------------------------------

@pytest.mark.parametrize("primer_cobro_local", ["07:20", "08:25", "09:16", "12:52"])
def test_el_corte_de_las_0800_nunca_cita_el_dia_en_curso_como_total(primer_cobro_local):
    """Exista o no cobro temprano, el dia en curso no es citable a las 08:00.

    La regla no mira la hora de apertura — ese numero caduca (el record de 09:16
    duro cinco dias). Mira la estructura: la carga de las 07:45 esta parada dentro
    del dia, asi que no vio el dia completo.
    """
    hubo_cobro = primer_cobro_local < "07:45"
    verdict = clasificar_dia(day=DIA, renglones=1 if hubo_cobro else 0,
                             bruto=85.0 if hubo_cobro else 0.0,
                             carga_at=CARGA_0745,
                             ultimo_imported_at=CARGA_0745 if hubo_cobro else None)

    assert verdict["citable_como_total"] is False
    assert verdict["estado"] in (PARCIAL, SIN_CIFRA)


def test_el_unico_corte_que_cierra_un_dia_es_el_de_las_0800_del_dia_siguiente():
    """La carga de las 07:45 del 07/10 si vio el 06/10 completo: ese dia es FINAL."""
    verdict = clasificar_dia(day=AYER, renglones=16, bruto=1670.0,
                             carga_at=CARGA_0745,
                             ultimo_imported_at=CARGA_1945)

    assert verdict["estado"] == FINAL
    assert verdict["citable_como_total"] is True
    assert "FINAL" in verdict["rotulo"]


def test_el_corte_de_las_2000_no_puede_cerrar_su_propio_dia():
    """Mismo mecanismo, otro grado: 19:45 tambien esta parado dentro del dia."""
    verdict = clasificar_dia(day=AYER, renglones=13, bruto=1214.0,
                             carga_at=CARGA_1945, ultimo_imported_at=CARGA_1945)

    assert verdict["estado"] == PARCIAL
    assert verdict["citable_como_total"] is False
    assert verdict["cobertura_hasta_local"] == "19:45"
    assert verdict["falta_del_dia"] == "4 h 15 min"


def test_una_corrida_que_no_pidio_el_dia_no_lo_cierra():
    """`--catch-up 1` alcanza un dia atras; dos dias atras esa corrida no lo pidio."""
    verdict = clasificar_dia(day="2026-10-04", renglones=0, bruto=0.0,
                             carga_at=CARGA_0745)

    assert verdict["corrida_fuera_de_alcance"] is True
    assert verdict["estado"] == SIN_EVIDENCIA
    assert verdict["citable_como_total"] is False


def test_un_dia_viejo_con_renglones_escritos_despues_del_cierre_si_es_final():
    """Cuando la corrida citada no alcanza, los renglones mismos prueban cobertura."""
    verdict = clasificar_dia(day="2026-10-04", renglones=9, bruto=700.0,
                             carga_at=CARGA_0745,
                             ultimo_imported_at="2026-10-05T13:45:30+00:00")

    assert verdict["estado"] == FINAL
    assert verdict["citable_como_total"] is True


def test_un_cero_medido_despues_del_cierre_es_final_no_un_hueco():
    """Domingo cerrado: cero renglones, pero el dia ya cerro y la carga lo pidio."""
    verdict = clasificar_dia(day=AYER, renglones=0, bruto=0.0, carga_at=CARGA_0745)

    assert verdict["estado"] == FINAL
    assert verdict["citable_como_total"] is True


# --------------------------------------------------------------------------
# El eje del efectivo es otro, y no se mezcla
# --------------------------------------------------------------------------

def test_hasta_un_final_sigue_siendo_piso():
    verdict = clasificar_dia(day=AYER, renglones=16, bruto=1670.0, carga_at=CARGA_0745)
    assert verdict["incluye_efectivo"] is False
    assert "piso" in verdict["rotulo"]


# --------------------------------------------------------------------------
# Lectura de la base: la sucursal se separa por `clip_branch`
# --------------------------------------------------------------------------

def test_la_sucursal_se_separa_por_clip_branch_no_por_marca():
    sales = FakeSales([
        venta(total=85.0),
        venta(branch="tecnoparque", cafeteria="c-tecno", total=500.0),
    ])
    leido = leer_dia(sales, day=DIA, clip_branch="sji", cafeteria_id="c-sji")

    assert leido["renglones"] == 1
    assert leido["bruto"] == 85.0
    assert sales.queries[0] == {"clip_branch": "sji", "business_date": DIA}
    assert "brand" not in sales.queries[0]


def test_el_conteo_por_cafeteria_es_el_control_y_delata_carga_vieja():
    """Un renglon sin `clip_branch` deja el conteo corto. Se dice, no se publica."""
    sales = FakeSales([
        venta(total=85.0),
        {"business_date": DIA, "cafeteria_id": "c-sji", "total": 40.0},  # carga vieja
    ])
    leido = leer_dia(sales, day=DIA, clip_branch="sji", cafeteria_id="c-sji")

    assert leido["renglones"] == 1
    assert leido["control_por_cafeteria"] == 2
    assert leido["descuadre_de_control"] is True


def test_el_ultimo_imported_at_sale_del_maximo_de_los_renglones():
    sales = FakeSales([
        venta(total=85.0, imported="2026-10-07T13:45:57+00:00"),
        venta(total=40.0, imported="2026-10-07T01:45:12+00:00"),
    ])
    leido = leer_dia(sales, day=DIA, clip_branch="sji")
    assert leido["ultimo_imported_at"] == "2026-10-07T13:45:57+00:00"


# --------------------------------------------------------------------------
# La ventana del corte y la linea de comandos
# --------------------------------------------------------------------------

def test_el_corte_de_las_0800_rotula_ayer_y_hoy():
    from datetime import datetime, timezone
    ahora = datetime(2026, 10, 7, 14, 0, 16, tzinfo=timezone.utc)  # 08:00 CDMX
    assert dias_del_corte(now=ahora, count=2) == [AYER, DIA]


def test_correr_rotula_cada_dia_y_lista_los_citables():
    sales = FakeSales([
        venta(day=AYER, total=1670.0, imported=CARGA_1945),
        venta(day=DIA, total=85.0, imported=CARGA_0745),
    ])
    out = correr(sales, clip_branch="sji", days=[AYER, DIA], carga_at=CARGA_0745,
                 cafeteria_id="c-sji", etiqueta="Casa Dorelia SJI")

    assert [d["estado"] for d in out["dias"]] == [FINAL, PARCIAL]
    assert out["dias_citables"] == [AYER]


def test_la_linea_de_comandos_rotula_parcial_el_cobro_de_las_0720(monkeypatch, capsys):
    """El criterio de cierre 1, de punta a punta: un cobro antes de las 07:45.

    Es el dia que la base real todavia no tiene. Forzado con ese shape, lo que
    sale a la pantalla trae el rotulo de parcial y la hora de la carga — nunca
    «venta del dia» — y ningun dia de la ventana queda citable como total.
    """
    sales = FakeSales([venta(day=DIA, total=85.0, imported=CARGA_0745)])
    monkeypatch.setattr("corte_window.open_sales_collection", lambda *a, **k: sales)

    code = main(["--branch", "sji", "--day", DIA, "--db", "casa_dorelia",
                 "--carga-at", CARGA_0745])
    salida = capsys.readouterr().out

    assert code == 0
    assert salida.startswith("PARCIAL")
    assert "$85.00" in salida and "07:45 CDMX" in salida
    assert "Ningun dia de esta ventana es citable como total" in salida


def test_la_linea_de_comandos_avisa_cuando_falta_citar_la_corrida(monkeypatch, capsys):
    sales = FakeSales([])
    monkeypatch.setattr("corte_window.open_sales_collection", lambda *a, **k: sales)

    code = main(["--branch", "sji", "--day", DIA, "--db", "casa_dorelia"])

    assert code == 2
    assert "SIN EVIDENCIA" in capsys.readouterr().out


def test_una_sucursal_desconocida_falla_con_las_que_hay(monkeypatch, capsys):
    code = main(["--branch", "polanco", "--db", "casa_dorelia"])
    assert code == 1
    assert "sji" in capsys.readouterr().out


def test_un_dia_que_no_es_una_fecha_truena_con_nombre():
    with pytest.raises(CorteWindowError):
        clasificar_dia(day="ayer")
