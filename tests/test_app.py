"""Pruebas de humo de la app: cada pestaña genera sus figuras y tablas con los datos publicados.

Llaman a las funciones de los callbacks directamente (sin navegador), así que detectan una
pestaña rota antes de desplegar.
"""
import plotly.graph_objects as go
import pytest
from dash.exceptions import PreventUpdate

from app.app import app
from app.comun import NOMBRES_PROV, TRIMESTRES
from app.datos import legible, opciones_busqueda
from app.pestanas import guia, mapa, metodo, municipios, prediccion, territorio


def test_la_app_monta_las_seis_pestanas():
    pestanas = app.layout.children[1]
    assert [t.value for t in pestanas.children] == ["guia", "mapa", "territorio", "municipios", "prediccion", "metodo"]


@pytest.mark.parametrize("pagina", [guia, mapa, territorio, municipios, prediccion, metodo])
def test_cada_pestana_tiene_maquetacion(pagina):
    assert pagina.layout() is not None


@pytest.mark.parametrize("indicador", ["esfuerzo", "esfuerzo_alquiler", "diferencial", "estado", "probabilidad"])
def test_mapa_para_cada_indicador(indicador):
    figura, ranking, titulo, tarjetas, *_ = mapa.actualizar_mapa.__wrapped__(indicador, len(TRIMESTRES) - 1, "28")
    assert isinstance(figura, go.Figure) and isinstance(ranking, go.Figure)
    assert len(figura.data) == 2                         # provincias + contorno de la seleccionada
    assert len(tarjetas) == 5 and titulo


def test_mapa_en_el_primer_trimestre():
    figura, *_ = mapa.actualizar_mapa.__wrapped__("esfuerzo", 0, None)
    assert len(figura.data[0].locations) == 52


def test_clic_en_el_mapa_abre_la_ficha():
    assert mapa.clic_en_mapa({"points": [{"location": "29"}]}) == ("29", "territorio")


def test_los_callbacks_no_trabajan_fuera_de_su_pestana():
    with pytest.raises(PreventUpdate):
        mapa.actualizar_mapa("esfuerzo", 0, "28", "territorio")
    with pytest.raises(PreventUpdate):
        territorio.actualizar_territorio("28", None, None, "mapa")


@pytest.mark.parametrize("provincia, municipio, comparar", [
    ("28", None, None),                  # provincia
    ("29", "29069", ["08", "07"]),       # municipio (Marbella) comparado con dos provincias
    ("20", None, None),                  # Gipuzkoa: alquiler de SERPAVI solo desde 2022
])
def test_ficha_territorial(provincia, municipio, comparar):
    tarjetas, esfuerzo, precio, diferencial, compra_alquiler, tabla = territorio.actualizar_territorio.__wrapped__(
        provincia, municipio, tuple(comparar) if comparar else None)
    assert len(tarjetas) == 6
    assert all(isinstance(f, go.Figure) for f in (esfuerzo, precio, diferencial, compra_alquiler))
    assert len(precio.data) == 3                         # compra, alquiler e IPC
    assert tabla.data


def test_calculadora_coincide_con_la_ficha_con_los_supuestos_oficiales():
    figura, texto = territorio.calculadora.__wrapped__("28", None, 90, 80, 25, territorio.TIPO_ACTUAL)
    indicador = figura.data[0]
    # Mismo esfuerzo que la ficha salvo el redondeo del tipo de partida (2,95 % frente a 2,9467 %)
    assert indicador.value == pytest.approx(indicador.delta.reference, abs=0.05)
    assert "Madrid" in texto[0]


def test_municipios_con_y_sin_filtros():
    figura, tabla = municipios.actualizar_municipios.__wrapped__(None, None, None)
    assert len(tabla.data) > 250
    figura, tabla = municipios.actualizar_municipios.__wrapped__(("07",), None, None)
    assert {fila["Provincia"] for fila in tabla.data} == {"Illes Balears"}
    figura, tabla = municipios.actualizar_municipios.__wrapped__(("07",), ("No existe",), None)
    assert tabla is None                                 # sin resultados: mensaje, no error


@pytest.mark.parametrize("nivel", ["provincias", "municipios"])
def test_prediccion(nivel):
    salida = prediccion.actualizar_modelo.__wrapped__(nivel)
    assert isinstance(salida[2], go.Figure) and isinstance(salida[3], go.Figure)


def test_nombres_legibles_y_busqueda_en_castellano():
    assert legible("Balears, Illes") == "Illes Balears"
    assert legible("Hospitalet de Llobregat, L'") == "L'Hospitalet de Llobregat"
    assert "Illes Balears" in NOMBRES_PROV.values()
    baleares = next(o for o in opciones_busqueda(NOMBRES_PROV, {"07": "Baleares"}) if o["value"] == "07")
    assert "baleares" in baleares["search"].lower()
