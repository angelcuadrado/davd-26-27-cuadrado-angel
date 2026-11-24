"""Pestaña «Municipios»: los municipios en el plano de los dos criterios y tabla filtrable."""
import pandas as pd
from dash import Input, Output, callback, dash_table, dcc, html

from app import graficos as g
from app.comun import ESTILO_TABLA, MUN, NOMBRES_PROV, ULTIMO, D, en_pestana, etiqueta, grafico
from app.datos import OTROS_NOMBRES, opciones_busqueda


def layout():
    ultimo = MUN[MUN["trimestre"] == ULTIMO]
    return html.Div([
        html.P(["Los ", html.B(f"{len(ultimo)} municipios"), " de más de 25.000 habitantes con valor tasado publicado, ",
                f"en {etiqueta(ULTIMO)}. Cada punto es un municipio: las líneas marcan los dos umbrales legales."],
               className="explicacion"),
        html.Div([
            html.Div([html.Label("Provincia", className="etiqueta-control"),
                      dcc.Dropdown(id="mun-provincia", multi=True, placeholder="Todas",
                                   options=opciones_busqueda(NOMBRES_PROV, OTROS_NOMBRES))],
                     className="selector"),
            html.Div([html.Label("Previsión a dos años", className="etiqueta-control"),
                      dcc.Dropdown(id="mun-escenario", multi=True, placeholder="Todas",
                                   options=["Seguirá tensionado", "Entrará en tensión",
                                            "Saldrá de la tensión", "Seguirá sin tensión"])],
                     className="selector"),
        ], className="controles"),
        html.Div(grafico("dispersion"), className="tarjeta-grafico"),
        html.Div(id="tabla-municipios", className="tarjeta-grafico"),
    ])


@callback(Output("dispersion", "figure"), Output("tabla-municipios", "children"),
              Input("mun-provincia", "value"), Input("mun-escenario", "value"), Input("municipio", "value"),
              Input("pestanas", "value"))
@en_pestana("municipios")
def actualizar_municipios(provincias, escenarios, destacado):
    d = MUN[MUN["trimestre"] == ULTIMO].merge(
        D["pred_municipios"][["cod_mun", "probabilidad", "escenario"]], on="cod_mun", how="left")
    if provincias:
        d = d[d["cod_prov"].isin(provincias)]
    if escenarios:
        d = d[d["escenario"].isin(escenarios)]
    d = d.dropna(subset=["esfuerzo", "diferencial"])
    if d.empty:
        return g.vacia("No hay municipios con esos filtros"), None
    filas = [{"Municipio": r.municipio, "Provincia": r.provincia, "€/m²": round(r.precio_m2),
              "Renta hogar (€)": round(r.renta_hogar),
              "Alquiler (€/mes)": None if pd.isna(r.alquiler_mes) else round(r.alquiler_mes),
              "Esfuerzo compra (%)": round(100 * r.esfuerzo, 1),
              "Esfuerzo alquiler (%)": None if pd.isna(r.esfuerzo_alquiler) else round(100 * r.esfuerzo_alquiler, 1),
              "Precio − IPC (p.)": round(r.diferencial, 1), "Estado": r.estado,
              "Prob. 2 años (%)": None if pd.isna(r.probabilidad) else round(100 * r.probabilidad),
              "Previsión": r.escenario}
             for r in d.sort_values("esfuerzo", ascending=False).itertuples()]
    tabla = dash_table.DataTable(
        filas, [{"name": c, "id": c, "type": "numeric" if isinstance(filas[0][c], (int, float)) else "text"} for c in filas[0]],
        filter_action="native", **{**ESTILO_TABLA, "page_size": 15},
        style_data_conditional=[{"if": {"filter_query": '{Estado} = "Tensionado"', "column_id": "Estado"},
                                 "color": g.BERMELLON, "fontWeight": "600"}])
    return g.dispersion_criterios(d, destacado), tabla
