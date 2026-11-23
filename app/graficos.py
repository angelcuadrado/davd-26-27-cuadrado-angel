"""Figuras de Plotly del cuadro de mando.

Reglas de estilo del proyecto: paleta accesible en orden fijo, escala secuencial de un solo tono
para magnitudes, divergente para valores con signo, un único eje Y, barras desde cero, leyenda
siempre que haya dos series o más y texto en tinta (nunca del color de la serie).
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

AZUL, NARANJA, VERDE, BERMELLON, CELESTE = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9"
TINTA, TINTA_SUAVE, REJILLA, FONDO = "#3d3d3a", "#73726c", "#e8e6e1", "#fcfcfb"
SECUENCIAL = [[0, "#deebf7"], [0.2, "#c6dbef"], [0.4, "#9ecae1"], [0.6, "#6baed6"], [0.8, "#3182bd"], [1, "#08519c"]]
DIVERGENTE = [[0, AZUL], [0.5, "#f1efe8"], [1, BERMELLON]]          # dos polos y gris neutro
COLOR_ESTADO = {"Tensionado": BERMELLON, "Sin tensión": AZUL}

INDICADORES = {
    "esfuerzo": {"titulo": "Esfuerzo de compra", "formato": ".1%", "umbral": 0.30,
                 "explicacion": "Cuota anual de la hipoteca de una vivienda de 90 m² entre la renta neta media del hogar."},
    "diferencial": {"titulo": "Precio − IPC a cinco años", "formato": "+.1f", "umbral": 3.0, "sufijo": " p.",
                    "explicacion": "Crecimiento acumulado del precio en cinco años menos el del IPC de la provincia, en puntos."},
    "estado": {"titulo": "Situación legal hoy", "explicacion": "Tensionado si cumple al menos uno de los dos criterios del art. 18.3."},
    "probabilidad": {"titulo": "Probabilidad de tensión en dos años", "formato": ".0%", "umbral": 0.5,
                     "explicacion": "Probabilidad estimada por el modelo de que el territorio cumpla algún criterio dentro de ocho trimestres."},
}


def _base(fig: go.Figure, alto: int = 380, leyenda: bool = True) -> go.Figure:
    fig.update_layout(
        height=alto, margin=dict(l=8, r=12, t=12, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=FONDO,
        font=dict(family="Inter, system-ui, -apple-system, Segoe UI, sans-serif", size=13, color=TINTA),
        hoverlabel=dict(bgcolor="white", bordercolor=REJILLA, font=dict(color=TINTA)),
        showlegend=leyenda,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None, bgcolor="rgba(0,0,0,0)"),
        separators=",.",
    )
    fig.update_xaxes(gridcolor=REJILLA, zeroline=False, linecolor=REJILLA, tickfont=dict(color=TINTA_SUAVE))
    fig.update_yaxes(gridcolor=REJILLA, zeroline=False, linecolor=REJILLA, tickfont=dict(color=TINTA_SUAVE))
    return fig


def vacia(mensaje: str, alto: int = 300) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=mensaje, showarrow=False, font=dict(color=TINTA_SUAVE, size=14))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _base(fig, alto, leyenda=False)


# --- Mapa ----------------------------------------------------------------------------------

def mapa(datos: pd.DataFrame, geojson: dict, indicador: str, seleccion: str | None = None) -> go.Figure:
    """Coropleta de provincias. `datos` trae cod_prov, provincia y la columna del indicador."""
    info = INDICADORES[indicador]
    texto = datos["provincia"] + "<br>" + datos.get("hover", "")
    if indicador == "estado":
        codigo = datos["estado"].map({"Sin tensión": 0, "Tensionado": 1})
        escala = [[0, AZUL], [0.5, AZUL], [0.5, BERMELLON], [1, BERMELLON]]
        traza = go.Choropleth(geojson=geojson, locations=datos["cod_prov"], z=codigo, zmin=0, zmax=1,
                              colorscale=escala, text=texto, hovertemplate="%{text}<extra></extra>",
                              marker_line_color="white", marker_line_width=0.8,
                              colorbar=dict(tickvals=[0.25, 0.75], ticktext=["Sin tensión", "Tensionado"],
                                            thickness=12, len=0.5, outlinewidth=0))
    else:
        z = datos[indicador]
        if indicador == "diferencial":
            limite = float(np.nanmax(np.abs(z))) if len(z) else 1
            escala, zmin, zmax, zmid = DIVERGENTE, -limite, limite, 0
        else:
            escala, zmin, zmax, zmid = SECUENCIAL, float(np.nanmin(z)), float(np.nanmax(z)), None
        traza = go.Choropleth(geojson=geojson, locations=datos["cod_prov"], z=z, zmin=zmin, zmax=zmax, zmid=zmid,
                              colorscale=escala, text=texto, hovertemplate="%{text}<extra></extra>",
                              marker_line_color="white", marker_line_width=0.8,
                              colorbar=dict(tickformat=info.get("formato", "").replace("+", ""),
                                            ticksuffix=info.get("sufijo", ""), thickness=12, len=0.6, outlinewidth=0))
    fig = go.Figure(traza)
    if seleccion:
        fila = datos[datos["cod_prov"] == seleccion]
        fig.add_trace(go.Choropleth(geojson=geojson, locations=fila["cod_prov"], z=[1] * len(fila),
                                    colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False,
                                    marker_line_color=TINTA, marker_line_width=2.5, hoverinfo="skip"))
    fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator", bgcolor="rgba(0,0,0,0)")
    fig.update_layout(height=520, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Inter, system-ui, sans-serif", color=TINTA), dragmode=False,
                      separators=",.", clickmode="event")
    return fig


def ranking(datos: pd.DataFrame, indicador: str, nombre: str, n: int = 15) -> go.Figure:
    """Barras horizontales de los n territorios con valor más alto, con la línea del umbral."""
    info = INDICADORES[indicador]
    d = datos.dropna(subset=[indicador]).nlargest(n, indicador).iloc[::-1]
    color = d["estado"].map(COLOR_ESTADO) if "estado" in d else AZUL
    fig = go.Figure(go.Bar(
        x=d[indicador], y=d[nombre], orientation="h", marker=dict(color=color, cornerradius=4),
        customdata=d["estado"] if "estado" in d else None,
        hovertemplate="<b>%{y}</b><br>" + info["titulo"] + ": %{x:" + info["formato"] + "}"
                      + (info.get("sufijo", "")) + ("<br>%{customdata}" if "estado" in d else "") + "<extra></extra>",
    ))
    if "umbral" in info:
        fig.add_vline(x=info["umbral"], line=dict(color=TINTA, width=1.5, dash="dot"),
                      annotation_text="umbral", annotation_position="top", annotation_font_color=TINTA_SUAVE)
    fig.update_xaxes(tickformat=info["formato"].replace("+", ""), ticksuffix=info.get("sufijo", ""),
                     rangemode="tozero" if indicador != "diferencial" else "normal")
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return _base(fig, alto=max(300, 26 * len(d) + 40), leyenda=False)


# --- Series de un territorio ---------------------------------------------------------------

def serie_esfuerzo(series: dict[str, pd.DataFrame]) -> go.Figure:
    """Esfuerzo a lo largo del tiempo para uno o varios territorios, con el umbral del 30 %."""
    fig = go.Figure()
    for (nombre, df), color in zip(series.items(), [AZUL, NARANJA, VERDE, BERMELLON]):
        df = df.dropna(subset=["esfuerzo"])
        real = df[~df["renta_estimada"].astype(bool)]
        estimado = df[df["renta_estimada"].astype(bool)]
        fig.add_trace(go.Scatter(x=real["trimestre"].dt.to_timestamp(), y=real["esfuerzo"], name=nombre,
                                 mode="lines", line=dict(color=color, width=2.5), legendgroup=nombre,
                                 hovertemplate="%{y:.1%}<extra>" + nombre + "</extra>"))
        if not estimado.empty:
            puente = pd.concat([real.tail(1), estimado])
            fig.add_trace(go.Scatter(x=puente["trimestre"].dt.to_timestamp(), y=puente["esfuerzo"],
                                     name=f"{nombre} (renta estimada)", mode="lines", legendgroup=nombre,
                                     line=dict(color=color, width=2.5, dash="dot"), showlegend=False,
                                     hovertemplate="%{y:.1%} · renta estimada<extra>" + nombre + "</extra>"))
    fig.add_hline(y=0.30, line=dict(color=TINTA, width=1.5, dash="dot"), annotation_text="Umbral legal 30 %",
                  annotation_position="top left", annotation_font_color=TINTA_SUAVE)
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    fig.update_layout(hovermode="x unified")
    return _base(fig, 340)


def serie_precio_ipc(df: pd.DataFrame, nombre: str) -> go.Figure:
    """Crecimiento acumulado a cinco años del precio y del IPC (mismo eje, en %)."""
    d = df.dropna(subset=["crec_precio_5a"])
    x = d["trimestre"].dt.to_timestamp()
    fig = go.Figure([
        go.Scatter(x=x, y=d["crec_precio_5a"], name="Precio de la vivienda", mode="lines",
                   line=dict(color=BERMELLON, width=2.5), hovertemplate="%{y:+.1f} %<extra>Precio</extra>"),
        go.Scatter(x=x, y=d["crec_ipc_5a"], name="IPC de la provincia", mode="lines",
                   line=dict(color=AZUL, width=2.5), hovertemplate="%{y:+.1f} %<extra>IPC</extra>"),
    ])
    fig.update_yaxes(ticksuffix=" %", zeroline=True, zerolinecolor="#c9c7c0")
    fig.update_layout(hovermode="x unified")
    return _base(fig, 340)


def serie_diferencial(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["diferencial"])
    fig = go.Figure(go.Scatter(x=d["trimestre"].dt.to_timestamp(), y=d["diferencial"], mode="lines",
                               name="Diferencial", line=dict(color=TINTA, width=2.5),
                               hovertemplate="%{y:+.1f} puntos<extra></extra>"))
    fig.add_hline(y=3, line=dict(color=BERMELLON, width=1.5, dash="dot"), annotation_text="Umbral legal: +3 puntos",
                  annotation_position="top left", annotation_font_color=TINTA_SUAVE)
    fig.update_yaxes(ticksuffix=" p.", zeroline=True, zerolinecolor="#c9c7c0")
    return _base(fig, 260, leyenda=False)


# --- Municipios ----------------------------------------------------------------------------

def dispersion_criterios(df: pd.DataFrame, destacar: str | None = None) -> go.Figure:
    """Cada municipio según sus dos criterios: los cuadrantes muestran qué criterio cumple."""
    fig = go.Figure()
    for estado in ("Sin tensión", "Tensionado"):
        d = df[df["estado"] == estado]
        fig.add_trace(go.Scatter(
            x=d["diferencial"], y=d["esfuerzo"], mode="markers", name=estado,
            marker=dict(color=COLOR_ESTADO[estado], size=9, opacity=0.8, line=dict(color="white", width=1.5),
                        symbol="circle" if estado == "Tensionado" else "diamond"),
            customdata=np.stack([d["municipio"], d["provincia"]], axis=-1),
            hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>Esfuerzo %{y:.1%}<br>"
                          "Precio − IPC %{x:+.1f} p.<extra></extra>"))
    if destacar:
        d = df[df["cod_mun"] == destacar]
        fig.add_trace(go.Scatter(x=d["diferencial"], y=d["esfuerzo"], mode="markers+text", name="Seleccionado",
                                 text=d["municipio"], textposition="top center", textfont=dict(color=TINTA),
                                 marker=dict(size=16, color="rgba(0,0,0,0)", line=dict(color=TINTA, width=2.5)),
                                 hoverinfo="skip", showlegend=False))
    fig.add_hline(y=0.30, line=dict(color=TINTA, width=1, dash="dot"))
    fig.add_vline(x=3, line=dict(color=TINTA, width=1, dash="dot"))
    fig.add_annotation(x=1, y=1, xref="paper", yref="paper", text="Cumple los dos", showarrow=False,
                       xanchor="right", yanchor="top", font=dict(color=TINTA_SUAVE, size=12))
    fig.add_annotation(x=0, y=0, xref="paper", yref="paper", text="No cumple ninguno", showarrow=False,
                       xanchor="left", yanchor="bottom", font=dict(color=TINTA_SUAVE, size=12))
    fig.update_xaxes(title="Precio − IPC a cinco años (puntos)", ticksuffix=" p.")
    fig.update_yaxes(title="Esfuerzo de compra", tickformat=".0%")
    return _base(fig, 460)


# --- Modelo --------------------------------------------------------------------------------

def matriz_confusion(m: dict) -> go.Figure:
    z = [[m["vn"], m["fp"]], [m["fn"], m["vp"]]]
    total = sum(sum(f) for f in z) or 1
    etiquetas = [["Acierto: sin tensión", "Falsa alarma"], ["Aviso perdido", "Acierto: tensión"]]
    texto = [[f"{etiquetas[i][j]}<br><b>{z[i][j]}</b> ({z[i][j] / total:.0%})" for j in range(2)] for i in range(2)]
    fig = go.Figure(go.Heatmap(z=z, x=["Predice sin tensión", "Predice tensión"], y=["Real: sin tensión", "Real: tensión"],
                               text=texto, texttemplate="%{text}", colorscale=[[0, "#f3f1ec"], [1, "#9ecae1"]],
                               showscale=False,
                               hovertemplate="%{text}<extra></extra>", xgap=3, ygap=3,
                               textfont=dict(color=TINTA)))
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    fig.update_xaxes(side="top", gridcolor="rgba(0,0,0,0)")
    return _base(fig, 300, leyenda=False)


def importancias(registros: list[dict], n: int = 8) -> go.Figure:
    d = pd.DataFrame(registros).head(n).iloc[::-1]
    fig = go.Figure(go.Bar(x=d["importancia"], y=d["descripcion"], orientation="h",
                           marker=dict(color=AZUL, cornerradius=4),
                           error_x=dict(type="data", array=d["desviacion"], color=TINTA_SUAVE, thickness=1),
                           hovertemplate="%{y}<br>Pérdida de AUC al desordenarla: %{x:.3f}<extra></extra>"))
    fig.update_xaxes(rangemode="tozero", title="Pérdida de AUC al desordenar la variable")
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return _base(fig, 40 * len(d) + 80, leyenda=False)


def comparativa_modelos(metricas: dict) -> go.Figure:
    """Recall y precisión de cada modelo frente a las referencias (barras agrupadas)."""
    nombres = list(metricas)
    etiquetas = [n.replace("Referencia: ", "Referencia:<br>").replace(" ", "<br>", 1) if not n.startswith("Referencia")
                 else n.replace("Referencia: ", "Referencia:<br>") for n in nombres]
    fig = go.Figure([
        go.Bar(name="Recall", x=etiquetas, y=[metricas[n]["recall"] for n in nombres],
               marker=dict(color=BERMELLON, cornerradius=4), hovertemplate="%{x}<br>Recall %{y:.0%}<extra></extra>"),
        go.Bar(name="Precisión", x=etiquetas, y=[metricas[n]["precision"] for n in nombres],
               marker=dict(color=AZUL, cornerradius=4), hovertemplate="%{x}<br>Precisión %{y:.0%}<extra></extra>"),
    ])
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
    fig.update_yaxes(tickformat=".0%", range=[0, 1.05])
    fig.update_xaxes(tickangle=0, tickfont=dict(size=11))
    return _base(fig, 340)


def indicador_esfuerzo(valor: float, referencia: float | None) -> go.Figure:
    """Barra de bala: el esfuerzo de la calculadora frente al umbral y al valor oficial."""
    fig = go.Figure(go.Indicator(
        mode="number+gauge+delta", value=valor * 100, number=dict(suffix=" %", valueformat=".1f", font=dict(color=TINTA)),
        delta=dict(reference=(referencia or valor) * 100, valueformat=".1f", suffix=" p.",
                   increasing=dict(color=BERMELLON), decreasing=dict(color=AZUL)),
        gauge=dict(shape="bullet", axis=dict(range=[0, max(60, valor * 110)], ticksuffix=" %"),
                   bar=dict(color=BERMELLON if valor > 0.30 else AZUL, thickness=0.5),
                   steps=[dict(range=[0, 30], color="#eef2f6"), dict(range=[30, max(60, valor * 110)], color="#fbe9e1")],
                   threshold=dict(line=dict(color=TINTA, width=3), thickness=0.9, value=30)),
    ))
    fig.update_layout(height=110, margin=dict(l=20, r=30, t=10, b=20), paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Inter, system-ui, sans-serif", color=TINTA), separators=",.")
    return fig
