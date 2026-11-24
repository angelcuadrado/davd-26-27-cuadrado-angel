"""Pestaña «Predicción»: modelos frente a referencias, errores, importancias y previsión."""
from dash import Input, Output, callback, dash_table, dcc, html

from app import graficos as g
from app.comun import ESTILO_TABLA, D, en_pestana, grafico, pct, puntos, tarjeta


def layout():
    return html.Div([
        html.Div([
            html.Label("Nivel", className="etiqueta-control"),
            dcc.RadioItems(id="nivel-modelo", value="provincias", inline=True, className="radio",
                           options=[{"label": "Provincias", "value": "provincias"},
                                    {"label": "Municipios", "value": "municipios"}]),
        ], className="controles"),
        html.Div(id="resumen-modelo"),
        html.Div(id="lectura-modelo", className="aviso"),
        html.Div([
            html.Div([html.H3("¿Supera a las referencias?"),
                      html.P("Medido en trimestres que el modelo no vio al entrenar.", className="nota"),
                      grafico("comparativa")], className="columna-mitad tarjeta-grafico"),
            html.Div([html.H3("Aciertos y errores del modelo elegido"), grafico("confusion"),
                      html.P(id="texto-confusion", className="nota")], className="columna-mitad tarjeta-grafico"),
        ], className="fila-graficos"),
        html.Div([
            html.Div([html.H3("Qué variables pesan más"), grafico("importancias"),
                      html.P("Importancia por permutación en el periodo de prueba: cuánto empeora la capacidad de "
                             "ordenar (AUC) si se desordena esa variable.",
                             className="nota")], className="columna-mitad tarjeta-grafico"),
            html.Div([html.H3("Territorios que entrarían en tensión"), html.Div(id="tabla-entraran")],
                     className="columna-mitad tarjeta-grafico"),
        ], className="fila-graficos"),
        html.Div(id="tabla-metricas", className="tarjeta-grafico"),
    ])


def lectura(nivel: str, elegido: str, metricas: dict, resumen: dict) -> list:
    """Lectura honesta del resultado frente a las referencias."""
    m, pers = metricas[elegido], metricas["Referencia: persistencia"]
    texto = [html.B("Cómo leerlo. "),
             "La referencia difícil es la persistencia («dentro de dos años estará como hoy»): el criterio de precios mira "
             "cinco años hacia atrás y el estado tiene mucha inercia. "]
    if m["recall"] > pers["recall"]:
        texto.append(f"El modelo detecta el {pct(m['recall'], 0)} de los casos que acaban tensionados, frente al "
                     f"{pct(pers['recall'], 0)} de la persistencia, porque también anticipa entradas en tensión; a cambio "
                     f"da más falsas alarmas (precisión {pct(m['precision'], 0)} frente a {pct(pers['precision'], 0)}). "
                     "Como la métrica principal es el recall —no avisar de un territorio que se tensiona es el error caro—, "
                     "se prefiere el modelo.")
    else:
        texto.append(f"Aquí el modelo no mejora el recall de la persistencia ({pct(m['recall'], 0)} frente a "
                     f"{pct(pers['recall'], 0)}).")
    if resumen["positivos_prueba_pct"] > 50:
        texto.append(f" Ojo: en prueba el {resumen['positivos_prueba_pct']} % de los casos están tensionados, así que "
                     "predecir siempre «tensión» ya acierta mucho; la AUC es la medida más justa aquí.")
    return texto


@callback(Output("resumen-modelo", "children"), Output("lectura-modelo", "children"),
              Output("comparativa", "figure"), Output("confusion", "figure"),
              Output("texto-confusion", "children"), Output("importancias", "figure"),
              Output("tabla-entraran", "children"), Output("tabla-metricas", "children"),
              Input("nivel-modelo", "value"), Input("pestanas", "value"))
@en_pestana("prediccion")
def actualizar_modelo(nivel):
    info = D["modelo"].get(nivel)
    if not info:
        vacio = g.vacia("Modelo no disponible")
        return "", "", vacio, vacio, "", vacio, None, None
    r, elegido, metricas = info["resumen"], info["elegido"], info["metricas"]
    m = metricas[elegido]
    pred = D[f"pred_{nivel}"]
    conteo = pred["escenario"].value_counts()
    resumen = html.Div([
        tarjeta("Modelo elegido", elegido, "por F2 en validación temporal", "destacada"),
        tarjeta("Recall en prueba", pct(m["recall"], 0), "tensiones que detecta"),
        tarjeta("Precisión en prueba", pct(m["precision"], 0), "avisos que aciertan"),
        tarjeta("Entrarían en tensión", str(int(conteo.get("Entrará en tensión", 0))),
                f"de {len(pred)} · previsión para {r['horizonte'].replace('Q', ' T')}"),
        tarjeta("Saldrían de la tensión", str(int(conteo.get("Saldrá de la tensión", 0))), "según el modelo"),
    ], className="fila-tarjetas")
    mc = m["matriz"]
    texto = (f"Prueba: {r['filas_prueba']} territorio-trimestres de {r['periodo_prueba'].replace('Q', ' T')}. "
             f"De {mc['vp'] + mc['fn']} casos que acabaron tensionados, el modelo avisó de {mc['vp']}.")
    nombre = "municipio" if nivel == "municipios" else "provincia"
    entraran = pred[pred["escenario"] == "Entrará en tensión"].nlargest(12, "probabilidad")
    if entraran.empty:
        entraran = pred[~pred["tensionado"].astype(bool)].nlargest(12, "probabilidad")
    filas = [{"Territorio": getattr(x, nombre), "Probabilidad": pct(x.probabilidad, 0), "Esfuerzo hoy": pct(x.esfuerzo),
              "Precio − IPC hoy": puntos(x.diferencial)} for x in entraran.itertuples()]
    tabla_entraran = dash_table.DataTable(filas, [{"name": c, "id": c} for c in filas[0]], **ESTILO_TABLA) if filas else \
        html.P("Ningún territorio sin tensión hoy la alcanzaría según el modelo.", className="nota")
    tabla_m = [{"Modelo": k + (" ✓" if k == elegido else ""), "Recall": pct(v["recall"], 0), "Precisión": pct(v["precision"], 0),
                "F2": f"{v['f2']:.2f}", "Exactitud equilibrada": pct(v["exactitud_equilibrada"], 0),
                "AUC": f"{v['roc_auc']:.2f}" if "roc_auc" in v else "—",
                "F2 validación temporal": f"{v['f2_validacion_temporal']:.2f}" if "f2_validacion_temporal" in v else "—"}
               for k, v in metricas.items()]
    tabla_metricas = html.Div([
        html.H3("Todas las métricas"),
        html.P(f"Entrenamiento: {r['periodo_entrenamiento'].replace('Q', ' T')} ({r['filas_entrenamiento']} filas, "
               f"{r['positivos_entrenamiento_pct']} % tensionadas a dos años). Prueba: {r['periodo_prueba'].replace('Q', ' T')} "
               f"({r['positivos_prueba_pct']} % tensionadas).", className="nota"),
        dash_table.DataTable(tabla_m, [{"name": c, "id": c} for c in tabla_m[0]], **ESTILO_TABLA),
    ])
    return (resumen, lectura(nivel, elegido, metricas, r), g.comparativa_modelos(metricas), g.matriz_confusion(mc), texto,
            g.importancias(info["importancias"]), tabla_entraran, tabla_metricas)
