"""El corte de caja: que el efectivo entre sin inventar venta (BOS-119).

El efectivo no viaja por la API de Clip (censo de 2,329 cobros en 360 dias:
cero rotulados efectivo), asi que el corte que captura la sucursal es la **unica**
fuente de ese dinero. Eso lo vuelve el renglon mas facil de falsear de todo el
sistema: nadie lo puede cruzar contra un tercero.

Estas pruebas fijan las defensas que lo sostienen:

- la venta en efectivo **se deriva** de lo contado, no se escribe;
- un negativo, un dedazo de seis cifras o un dia futuro no se guardan;
- un cero de efectivo es un cero **medido** y distinto de un dia sin corte;
- corregir un corte deja rastro, y el dia/sucursal/marca no se pueden editar;
- la diferencia contra el sistema **no** se calcula cuando no hay con que
  comparar, para no publicar un faltante del tamaño de todo el efectivo;
- el efectivo nunca cruza las dos marcas de esta base.

Sin Mongo y sin red: los cortes se construyen en memoria.
"""
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cash_cut import (  # noqa: E402
    MAX_AMOUNT,
    METHOD_CASH,
    SOURCE_CORTE,
    TURNO_COMPLETO,
    CashCutError,
    build_cut,
    cash_by_day,
    compare_with_system,
    covered_days,
    cut_filter,
    derive_cash_sales,
    duplicate_cuts,
    is_late,
    normalize_amount,
    normalize_tickets,
    normalize_turno,
    prefill,
    revise_cut,
    summarize_cuts,
)

# 4 de octubre de 2026, 20:30 CDMX = 02:30Z del dia 5. El dia de operacion es el
# 4: es el mismo desfase que hace que un corte capturado al cerrar caiga en el
# dia UTC siguiente (ver `business_day`).
AHORA = datetime(2026, 10, 5, 2, 30, tzinfo=timezone.utc)
HOY = "2026-10-04"

SJI = {"cafeteria_id": "c-sji", "brand": "casa-dorelia"}
TECNO = {"cafeteria_id": "c-tecno", "brand": "le-pain-dore"}


def corte(**kwargs):
    """Un corte valido de SJI; cada prueba cambia solo lo que le importa."""
    base = dict(
        cafeteria_id=SJI["cafeteria_id"],
        brand=SJI["brand"],
        business_date=HOY,
        fondo_inicial=500.0,
        efectivo_contado=2300.0,
        retiros=0.0,
        now=AHORA,
    )
    base.update(kwargs)
    return build_cut(**base)


# --------------------------------------------------------------------------
# El numero se deriva de lo que se cuenta
# --------------------------------------------------------------------------

def test_la_venta_en_efectivo_se_deriva_de_lo_contado():
    """Contado + retiros - fondo. Nadie captura el resultado a mano."""
    assert derive_cash_sales(500.0, 2300.0, 0.0) == 1800.0
    assert derive_cash_sales(500.0, 900.0, 1200.0) == 1600.0
    cut = corte(efectivo_contado=2300.0, retiros=0.0)
    assert cut["ventas_efectivo"] == 1800.0


def test_el_retiro_no_se_pierde_de_la_venta():
    """El dinero que salio del cajon se vendio igual.

    Es el error que vuelve chico el dia: contar el cajon despues de depositar y
    reportar solo lo que quedo.
    """
    con_retiro = corte(efectivo_contado=800.0, retiros=1000.0)
    sin_retiro = corte(efectivo_contado=1800.0, retiros=0.0)
    assert con_retiro["ventas_efectivo"] == sin_retiro["ventas_efectivo"] == 1300.0


def test_un_corte_en_cero_es_un_cero_medido():
    """Cerrar sin efectivo es dato, y vuelve citable la cifra con tarjeta.

    Es la diferencia entre "ese dia no cobramos efectivo" y "no sabemos": sin
    este caso el corte en cero seria imposible de capturar y el dia se quedaria
    como piso para siempre.
    """
    cut = corte(efectivo_contado=500.0, retiros=0.0, tickets_efectivo=0)
    assert cut["ventas_efectivo"] == 0.0
    assert cut["tickets_efectivo"] == 0
    assert cut["ticket_promedio"] is None
    assert covered_days([cut]) == [HOY]


def test_el_centavo_se_redondea_pero_no_se_pierde():
    cut = corte(fondo_inicial=500.33, efectivo_contado=2300.99, retiros=0.01)
    assert cut["ventas_efectivo"] == 1800.67


# --------------------------------------------------------------------------
# Lo que no se guarda
# --------------------------------------------------------------------------

def test_efectivo_negativo_no_se_guarda():
    """Restaria venta de un dia que si vendio. El error nombra los tres numeros."""
    with pytest.raises(CashCutError) as exc:
        corte(fondo_inicial=2000.0, efectivo_contado=500.0, retiros=0.0)
    mensaje = str(exc.value)
    assert "negativo" in mensaje
    assert "2,000.00" in mensaje and "500.00" in mensaje


def test_el_dedazo_de_ceros_no_pasa():
    """`115600` en vez de `1156.00` publicaria un dia falso de seis cifras."""
    with pytest.raises(CashCutError) as exc:
        corte(efectivo_contado=MAX_AMOUNT + 1)
    assert "tope de cordura" in str(exc.value)


def test_un_dia_futuro_no_se_guarda():
    """No se puede contar un cajon que no ha cerrado."""
    with pytest.raises(CashCutError) as exc:
        corte(business_date="2026-10-05")
    assert "futuro" in str(exc.value)


def test_el_dia_de_hoy_si_se_guarda_aunque_en_utc_sea_mañana():
    """A las 20:30 CDMX el dia UTC ya es el 5, y el corte es del 4.

    Si el corte cortara por dia UTC, el corte de la noche quedaria con la fecha
    de mañana y el tablero lo pondria en un dia que no habia abierto.
    """
    assert corte(business_date=HOY)["business_date"] == HOY


def test_sin_marca_no_se_guarda():
    """Un efectivo sin marca entraria a un total de dos repartos (BOS-101)."""
    with pytest.raises(CashCutError) as exc:
        corte(brand=None)
    assert "brand" in str(exc.value)


def test_monto_que_no_es_numero_no_se_guarda():
    for valor in ["1,156.00", None, True, float("nan"), float("inf")]:
        with pytest.raises(CashCutError):
            normalize_amount(valor, "efectivo_contado")


def test_tickets_contradictorios_no_se_guardan():
    """Cero cobros con dinero, o cobros sin dinero: una de las dos esta mal."""
    with pytest.raises(CashCutError) as exc:
        corte(tickets_efectivo=0, efectivo_contado=2300.0)
    assert "0 cobros" in str(exc.value)

    with pytest.raises(CashCutError):
        corte(tickets_efectivo=3, efectivo_contado=500.0, fondo_inicial=500.0)

    with pytest.raises(CashCutError):
        normalize_tickets(2.5)
    with pytest.raises(CashCutError):
        normalize_tickets(-1)


def test_turno_desconocido_no_se_guarda():
    assert normalize_turno(None) == TURNO_COMPLETO
    assert normalize_turno(" Matutino ") == "matutino"
    with pytest.raises(CashCutError):
        normalize_turno("tercer turno")


# --------------------------------------------------------------------------
# El rotulo del dinero
# --------------------------------------------------------------------------

def test_el_corte_dice_que_es_efectivo_y_de_donde_salio():
    cut = corte()
    assert cut["payment_method"] == METHOD_CASH
    assert cut["source"] == SOURCE_CORTE
    assert cut["brand"] == "casa-dorelia"
    assert cut["turno"] == TURNO_COMPLETO
    assert cut["revisions"] == []


def test_el_ticket_promedio_sale_del_corte_no_del_cobro():
    cut = corte(tickets_efectivo=12)
    assert cut["ticket_promedio"] == 150.0


def test_un_corte_viejo_se_marca_como_capturado_tarde():
    """Cargar historia se permite, pero el numero se recordo, no se conto."""
    assert is_late("2026-10-01", now=AHORA) is True
    assert is_late("2026-10-03", now=AHORA) is False
    assert corte(business_date="2026-09-15")["captured_late"] is True
    assert corte()["captured_late"] is False


# --------------------------------------------------------------------------
# La diferencia contra el sistema
# --------------------------------------------------------------------------

def test_sin_venta_capturada_no_hay_faltante():
    """Hoy el app no captura efectivo: restar acusaria a alguien de todo el dia."""
    cut = corte()
    assert cut["comparable"] is False
    assert cut["diferencia"] is None
    assert "unica fuente" in cut["diferencia_motivo"]


def test_cero_capturado_no_es_cuadra_con_cero():
    out = compare_with_system({"ventas_efectivo": 1800.0}, sistema_efectivo=0,
                              sistema_tickets=0)
    assert out["comparable"] is False
    assert out["diferencia"] is None
    assert "0 cobros" in out["diferencia_motivo"]


def test_con_venta_capturada_la_diferencia_si_se_calcula():
    sobra = compare_with_system({"ventas_efectivo": 1800.0}, sistema_efectivo=1750.0,
                                sistema_tickets=11)
    assert sobra["comparable"] is True
    assert sobra["diferencia"] == 50.0  # sobro dinero en el cajon

    falta = compare_with_system({"ventas_efectivo": 1700.0}, sistema_efectivo=1750.0,
                                sistema_tickets=11)
    assert falta["diferencia"] == -50.0


# --------------------------------------------------------------------------
# Corregir un corte
# --------------------------------------------------------------------------

def test_corregir_deja_rastro_del_monto_anterior():
    cut = corte()
    fixed = revise_cut(cut, {"efectivo_contado": 2400.0},
                       reason="faltaba contar el billete de 100 del sobre",
                       user_id="u-1", user_name="Gustavo", now=AHORA)
    assert fixed["ventas_efectivo"] == 1900.0
    assert fixed["id"] == cut["id"]
    assert fixed["created_at"] == cut["created_at"]
    assert len(fixed["revisions"]) == 1
    revision = fixed["revisions"][0]
    assert revision["before"] == {"efectivo_contado": 2300.0}
    assert revision["after"] == {"efectivo_contado": 2400.0}
    assert revision["by"] == "u-1"
    assert "billete" in revision["reason"]
    # El corte original no se muto.
    assert cut["ventas_efectivo"] == 1800.0 and cut["revisions"] == []


def test_dos_correcciones_se_apilan():
    cut = corte()
    una = revise_cut(cut, {"retiros": 200.0}, reason="deposito al banco",
                     user_id="u-1", now=AHORA)
    dos = revise_cut(una, {"notas": "turno cubierto por Ana"},
                     reason="falto decir quien cerro", user_id="u-2", now=AHORA)
    assert len(dos["revisions"]) == 2
    assert dos["ventas_efectivo"] == 2000.0


def test_corregir_sin_razon_no_corrige():
    """Un monto que cambia sin motivo escrito no se distingue de un fraude."""
    with pytest.raises(CashCutError) as exc:
        revise_cut(corte(), {"efectivo_contado": 9000.0}, reason="  ", now=AHORA)
    assert "razon" in str(exc.value)


def test_no_se_puede_mover_un_corte_de_dia_sucursal_o_marca():
    for cambio in [{"business_date": "2026-10-03"}, {"cafeteria_id": "c-tecno"},
                   {"brand": "le-pain-dore"}, {"turno": "matutino"}]:
        with pytest.raises(CashCutError) as exc:
            revise_cut(corte(), cambio, reason="me equivoque de dia", now=AHORA)
        assert "no se puede cambiar" in str(exc.value)


def test_una_correccion_invalida_no_deja_el_corte_a_medias():
    """La validacion corre antes de escribir: el corte viejo sigue entero."""
    cut = corte()
    with pytest.raises(CashCutError):
        revise_cut(cut, {"efectivo_contado": -5.0}, reason="dedazo", now=AHORA)
    assert cut["ventas_efectivo"] == 1800.0


def test_campo_desconocido_no_se_corrige_aqui():
    with pytest.raises(CashCutError):
        revise_cut(corte(), {"ventas_efectivo": 99999.0},
                   reason="quiero otro total", now=AHORA)


# --------------------------------------------------------------------------
# Identidad, duplicados y lectura
# --------------------------------------------------------------------------

def test_el_filtro_identifica_un_solo_corte():
    assert cut_filter(cafeteria_id="c-sji", business_date=HOY) == {
        "cafeteria_id": "c-sji", "business_date": HOY, "turno": TURNO_COMPLETO}
    assert cut_filter(cafeteria_id="c-sji", business_date=HOY, turno="matutino",
                      tenant_id="t-1")["tenant_id"] == "t-1"


def test_los_turnos_del_mismo_dia_suman_y_los_duplicados_se_delatan():
    matutino = corte(turno="matutino", efectivo_contado=1200.0, tickets_efectivo=8)
    vespertino = corte(turno="vespertino", fondo_inicial=0.0, efectivo_contado=900.0,
                       tickets_efectivo=6)
    por_dia = cash_by_day([matutino, vespertino])
    assert por_dia["casa-dorelia"][HOY]["cash"] == 1600.0
    assert por_dia["casa-dorelia"][HOY]["tickets"] == 14
    assert por_dia["casa-dorelia"][HOY]["cuts"] == 2
    assert duplicate_cuts([matutino, vespertino]) == []

    # El mismo turno dos veces es el mismo corte capturado doble: sumarlo
    # duplica la venta del dia, asi que sale en los controles del dato.
    repetido = duplicate_cuts([matutino, matutino])
    assert repetido == [{"cafeteria_id": "c-sji", "business_date": HOY,
                         "turno": "matutino", "cuts": 2}]


def test_el_dia_con_corte_deja_de_ser_piso_solo_ese_dia():
    """La cobertura es por dia: el corte de ayer no vuelve citable el de hoy."""
    ayer = corte(business_date="2026-10-03")
    assert covered_days([ayer]) == ["2026-10-03"]
    assert covered_days([ayer], brand="le-pain-dore") == []


def test_el_efectivo_no_cruza_las_dos_marcas():
    """La regla de esta base: dos marcas, dos repartos, ningun total publicable."""
    sji = corte(tickets_efectivo=12)
    tecno = build_cut(cafeteria_id=TECNO["cafeteria_id"], brand=TECNO["brand"],
                      business_date=HOY, fondo_inicial=1000.0,
                      efectivo_contado=3500.0, retiros=0.0, tickets_efectivo=20,
                      now=AHORA)
    resumen = summarize_cuts([sji, tecno])

    por_marca = {row["brand"]: row for row in resumen["brands"]}
    assert por_marca["casa-dorelia"]["cash"] == 1800.0
    assert por_marca["casa-dorelia"]["name"] == "Casa Dorelia"
    assert por_marca["casa-dorelia"]["vehicle"] == "Big E Stores"
    assert por_marca["le-pain-dore"]["cash"] == 2500.0
    assert por_marca["le-pain-dore"]["vehicle"] == "Grupo Viter, S.A. de C.V."

    # El total de las dos existe, se llama suma de control y nada mas.
    assert resumen["cash_all_brands"] == 4300.0
    assert "cash" not in resumen
    assert resumen["cuts"] == 2
    assert resumen["duplicates"] == []
    assert resumen["unlabeled_cuts"] == 0


def test_el_resumen_cuenta_los_cortes_tarde_y_los_corregidos():
    viejo = corte(business_date="2026-09-20")
    corregido = revise_cut(corte(), {"retiros": 50.0}, reason="deposito", now=AHORA)
    resumen = summarize_cuts([viejo, corregido])
    assert resumen["late_cuts"] == 1
    assert resumen["revised_cuts"] == 1
    assert resumen["brands"][0]["days_covered"] == 2
    assert resumen["brands"][0]["first_day"] == "2026-09-20"
    assert resumen["brands"][0]["last_day"] == HOY


def test_el_prefill_propone_el_fondo_y_nada_mas():
    """Proponer lo contado seria sugerir un numero que nadie conto."""
    propuesta = prefill({"fondo_inicial": 500.0})
    assert propuesta["fondo_inicial"] == 500.0
    assert propuesta["efectivo_contado"] is None
    assert propuesta["retiros"] is None

    sin_anterior = prefill(None)
    assert sin_anterior["fondo_inicial"] is None
    assert "no hay corte anterior" in sin_anterior["fondo_inicial_origen"]
