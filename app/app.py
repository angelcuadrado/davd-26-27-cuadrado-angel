"""Cuadro de mando: mapa del esfuerzo de acceso a la vivienda en España.

    python app/app.py                  # desarrollo: http://127.0.0.1:8050/
    gunicorn app.app:server            # producción (Render)

Este módulo solo crea la app y monta las pestañas; cada pestaña (app/pestanas/) trae su
maquetación y sus callbacks, y app/comun.py los datos y las piezas compartidas.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # para «python app/app.py»

from dash import Dash, Input, Output, State, dcc, html  # noqa: E402

from app.comun import ANIO_RENTA, ULTIMO, etiqueta  # noqa: E402
from app.pestanas import guia, mapa, metodo, municipios, prediccion, territorio  # noqa: E402

app = Dash(__name__, title="Esfuerzo de acceso a la vivienda", suppress_callback_exceptions=True, compress=True,
           meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"},
                      {"name": "description",
                       "content": "Cuadro de mando que cruza precio de la vivienda y renta de los hogares y aplica el "
                                  "criterio legal de zona tensionada."}])
server = app.server

app.layout = html.Div([
    html.Header([
        html.Div([
            html.H1("Mapa del esfuerzo de acceso a la vivienda"),
            html.P(["Precio de la vivienda frente a renta de los hogares y criterio legal de ",
                    html.B("zona tensionada"), " (art. 18.3 de la Ley 12/2023), con previsión a dos años."]),
        ]),
        html.Div([html.Span(f"Precios hasta {etiqueta(ULTIMO)}", className="chip"),
                  html.Span(f"Renta publicada hasta {ANIO_RENTA}", className="chip"),
                  html.Button("Modo oscuro", id="boton-tema", className="boton-tema", n_clicks=0,
                              title="Cambiar entre tema claro y oscuro")], className="chips"),
        dcc.Store(id="tema", storage_type="local"),
    ], className="cabecera"),
    dcc.Tabs(id="pestanas", value="mapa", className="pestanas", children=[
        dcc.Tab(label="Cómo leerlo", value="guia", children=guia.layout()),
        dcc.Tab(label="Mapa", value="mapa", children=mapa.layout()),
        dcc.Tab(label="Ficha territorial", value="territorio", children=territorio.layout()),
        dcc.Tab(label="Municipios", value="municipios", children=municipios.layout()),
        dcc.Tab(label="Predicción", value="prediccion", children=prediccion.layout()),
        dcc.Tab(label="Datos y método", value="metodo", children=metodo.layout()),
    ]),
    html.Footer(["Ángel Cuadrado Serrano · Desarrollo de Aplicaciones para la Visualización de Datos · ICAI 2026-2027 · ",
                 html.A("Código en GitHub", href="https://github.com/angelcuadrado/davd-26-27-cuadrado-angel", target="_blank")]),
], className="contenedor")


# --- Tema claro / oscuro (en el navegador, sin pasar por el servidor) ----------------------

app.clientside_callback(
    """
    function (clics, guardado) {
        // Primera visita: el tema del sistema operativo. Después, lo último que eligió la persona.
        let tema = guardado || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'oscuro' : 'claro');
        if (clics > 0 && window.dash_clientside.callback_context.triggered.some(t => t.prop_id.startsWith('boton-tema'))) {
            tema = tema === 'oscuro' ? 'claro' : 'oscuro';
        }
        document.documentElement.dataset.tema = tema;
        return [tema, tema === 'oscuro' ? 'Modo claro' : 'Modo oscuro'];
    }
    """,
    Output("tema", "data"), Output("boton-tema", "children"),
    Input("boton-tema", "n_clicks"), State("tema", "data"),
)


if __name__ == "__main__":
    app.run(debug=True)
