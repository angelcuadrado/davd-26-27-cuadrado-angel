"""Datos cargados una sola vez y piezas comunes a todas las pestañas (formatos, tarjetas, tablas)."""
from functools import lru_cache, wraps

import pandas as pd
from dash import dcc, html
from dash.exceptions import PreventUpdate

from app import graficos as g
from app.datos import cargar

D = cargar()
PROV, MUN = D["provincias"], D["municipios"]
ULTIMO = PROV["trimestre"].max()
PRIMERO = pd.Period("2015Q1", freq="Q")               # el Atlas de renta empieza en 2015
TRIMESTRES = [t for t in sorted(PROV["trimestre"].unique()) if t >= PRIMERO]
ANIO_RENTA = D["calidad"].get("ultimo_anio_renta", "")
TIPO_ACTUAL = round(float(PROV.loc[PROV["trimestre"] == ULTIMO, "tipo_interes"].iloc[0]), 2)
NOMBRES_PROV = PROV.drop_duplicates("cod_prov").set_index("cod_prov")["provincia"].to_dict()


def etiqueta(trimestre: pd.Period) -> str:
    return f"{trimestre.year} T{trimestre.quarter}"


def pct(x, decimales=1):
    return "—" if pd.isna(x) else f"{100 * x:.{decimales}f} %".replace(".", ",")


def puntos(x):
    return "—" if pd.isna(x) else f"{x:+.1f}".replace(".", ",") + " p."


def euros(x):
    return "—" if pd.isna(x) else f"{x:,.0f} €".replace(",", ".")


def tarjeta(titulo, valor, nota="", clase=""):
    return html.Div([html.Div(titulo, className="tarjeta-titulo"),
                     html.Div(valor, className="tarjeta-valor"),
                     html.Div(nota, className="tarjeta-nota")], className=f"tarjeta {clase}")


def estado_chip(tensionado):
    if pd.isna(tensionado):
        return html.Span("Sin dato", className="chip")
    return html.Span("● Tensionado" if tensionado else "○ Sin tensión",
                     className="chip chip-tension" if tensionado else "chip chip-ok")


def grafico(id_, **kw):
    return dcc.Graph(id=id_, config={"displayModeBar": False, "locale": "es"}, **kw)


ESTILO_TABLA = dict(
    style_table={"overflowX": "auto"}, page_size=12, sort_action="native",
    style_header={"backgroundColor": "#f3f1ec", "fontWeight": "600", "border": "none", "color": g.TINTA},
    style_cell={"fontFamily": "Inter, system-ui, sans-serif", "fontSize": 13, "padding": "6px 10px",
                "border": "none", "borderBottom": "1px solid #ece9e2", "textAlign": "left", "color": g.TINTA,
                "whiteSpace": "normal", "height": "auto", "maxWidth": 340},
)


def en_pestana(nombre: str):
    """Calcula el callback solo cuando su pestaña está a la vista, y recuerda los resultados.

    Dash crea a la vez el contenido de todas las pestañas, así que sin esto la primera carga
    calcula las cinco. Con 0,1 CPU en el plan gratuito de Render eso se nota. El último Input del
    callback debe ser la pestaña activa.
    """
    def decorador(funcion):
        memoria = lru_cache(maxsize=256)(funcion)

        @wraps(funcion)
        def envoltura(*args):
            *entradas, activa = args
            if activa != nombre:
                raise PreventUpdate
            return memoria(*(tuple(x) if isinstance(x, list) else x for x in entradas))
        return envoltura
    return decorador
