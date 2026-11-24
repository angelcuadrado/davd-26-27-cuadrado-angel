"""Pestaña «Mapa»: coropleta de provincias, ranking y tarjetas del trimestre elegido."""
import pandas as pd
from dash import Input, Output, callback, dcc, html, no_update

from app import graficos as g
from app.comun import PROV, TRIMESTRES, ULTIMO, D, en_pestana, etiqueta, euros, grafico, pct, puntos, tarjeta
from src import config


def layout():
    marcas = {i: str(t.year) for i, t in enumerate(TRIMESTRES) if t.quarter == 1 and t.year % 2 == 1}
    return html.Div([
        html.Div(id="tarjetas-mapa", className="fila-tarjetas"),
        html.Div([
            html.Div([
                html.Label("Indicador", className="etiqueta-control"),
                dcc.RadioItems(id="indicador", value="esfuerzo", inline=True, className="radio",
                               options=[{"label": v["titulo"], "value": k} for k, v in g.INDICADORES.items()]),
            ]),
            html.Div([
                html.Label(id="etiqueta-trimestre", className="etiqueta-control"),
                dcc.Slider(id="trimestre", min=0, max=len(TRIMESTRES) - 1, step=1, value=len(TRIMESTRES) - 1,
                           marks=marcas, included=False, updatemode="mouseup", allow_direct_input=False),
            ], className="control-trimestre"),
        ], className="controles"),
        html.P(id="explicacion-indicador", className="explicacion"),
        html.Div([
            html.Div([grafico("mapa"),
                      html.P("Pulsa una provincia para ver su ficha. Canarias aparece desplazada para que el mapa "
                             "se lea mejor.", className="nota")],
                     className="columna-ancha tarjeta-grafico"),
            html.Div([html.H3(id="titulo-ranking"), grafico("ranking")], className="columna-estrecha tarjeta-grafico"),
        ], className="fila-graficos"),
    ])


def _datos_mapa(indicador: str, trimestre: pd.Period) -> pd.DataFrame:
    if indicador == "probabilidad":
        d = D["pred_provincias"].copy()
        d["estado"] = d["tensionado"].map({True: "Tensionado", False: "Sin tensión"})
        d["hover"] = ("Probabilidad en dos años: " + d["probabilidad"].map(pct) + "<br>Previsión: " + d["escenario"])
        return d
    d = PROV[PROV["trimestre"] == trimestre].copy()
    d["hover"] = ("Esfuerzo de compra: " + d["esfuerzo"].map(pct) + "<br>Esfuerzo de alquiler: "
                  + d["esfuerzo_alquiler"].map(pct) + "<br>Precio − IPC (5 años): " + d["diferencial"].map(puntos)
                  + "<br>Alquiler − IPC (5 años): " + d["diferencial_alquiler"].map(puntos)
                  + "<br>" + d["estado"].fillna("Sin dato") + "<br>Valor tasado: " + d["precio_m2"].map(euros) + "/m²")
    return d


@callback(Output("mapa", "figure"), Output("ranking", "figure"), Output("titulo-ranking", "children"),
              Output("tarjetas-mapa", "children"), Output("etiqueta-trimestre", "children"),
              Output("explicacion-indicador", "children"), Output("trimestre", "disabled"),
              Input("indicador", "value"), Input("trimestre", "value"), Input("provincia", "value"),
              Input("pestanas", "value"))
@en_pestana("mapa")
def actualizar_mapa(indicador, posicion, provincia):
    trimestre = TRIMESTRES[posicion]
    d = _datos_mapa(indicador, trimestre)
    columna_ranking = "esfuerzo" if indicador == "estado" else indicador
    titulo = f"Provincias con más {g.INDICADORES[columna_ranking]['titulo'].lower()}"
    actual = PROV[PROV["trimestre"] == trimestre]
    n = actual["tensionado"].notna().sum()
    pred = D["pred_provincias"]
    tarjetas = [
        tarjeta("Provincias tensionadas", f"{int(actual['tensionado'].sum())} de {n}", etiqueta(trimestre), "destacada"),
        tarjeta("Por esfuerzo (> 30 %)", str(int(actual["criterio_esfuerzo"].sum())), "criterio 1: comprar o alquilar"),
        tarjeta("Por precios (> IPC + 3)", str(int(actual["criterio_precio"].sum())), "criterio 2: compra o alquiler"),
        tarjeta("Esfuerzo mediano", pct(actual["esfuerzo"].median()), "de las 52 provincias"),
        tarjeta("Tensionadas en dos años", f"{int(pred['prediccion'].sum())} de {len(pred)}",
                f"{etiqueta(ULTIMO + config.HORIZONTE_TRIMESTRES)}: entrarían "
                f"{int((pred['escenario'] == 'Entrará en tensión').sum())} y saldrían "
                f"{int((pred['escenario'] == 'Saldrá de la tensión').sum())}"),
    ]
    texto_trimestre = ("Trimestre: el último disponible (la previsión se hace desde hoy)" if indicador == "probabilidad"
                       else f"Trimestre: {etiqueta(trimestre)}")
    return (g.mapa(d, D["geojson"], indicador, provincia), g.ranking(d, columna_ranking, "provincia"), titulo,
            tarjetas, texto_trimestre, g.INDICADORES[indicador]["explicacion"], indicador == "probabilidad")


@callback(Output("provincia", "value"), Output("pestanas", "value"),
              Input("mapa", "clickData"), prevent_initial_call=True)
def clic_en_mapa(clic):
    if not clic or not clic.get("points"):
        return no_update, no_update
    return clic["points"][0]["location"], "territorio"
