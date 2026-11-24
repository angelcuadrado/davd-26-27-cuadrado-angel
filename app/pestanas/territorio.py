"""Pestaña «Ficha territorial»: series de una provincia o municipio, comparación y calculadora."""
import pandas as pd
from dash import Input, Output, callback, dash_table, dcc, html

from app import graficos as g
from app.comun import (
    ESTILO_TABLA,
    MUN,
    NOMBRES_PROV,
    PRIMERO,
    PROV,
    TIPO_ACTUAL,
    ULTIMO,
    D,
    en_pestana,
    estado_chip,
    etiqueta,
    euros,
    grafico,
    pct,
    puntos,
    tarjeta,
)
from app.datos import OTROS_NOMBRES, opciones_busqueda
from src import config
from src.indicadores import esfuerzo as calcular_esfuerzo


def layout():
    return html.Div([
        html.Div([
            html.Div([html.Label("Provincia", className="etiqueta-control"),
                      dcc.Dropdown(id="provincia", value="28", clearable=False,
                                   options=opciones_busqueda(NOMBRES_PROV, OTROS_NOMBRES))],
                     className="selector"),
            html.Div([html.Label("Municipio (más de 25.000 habitantes)", className="etiqueta-control"),
                      dcc.Dropdown(id="municipio", placeholder="Toda la provincia")], className="selector"),
            html.Div([html.Label("Comparar con (hasta dos provincias)", className="etiqueta-control"),
                      dcc.Dropdown(id="comparar", multi=True, placeholder="Ninguna",
                                   options=opciones_busqueda(NOMBRES_PROV, OTROS_NOMBRES))],
                     className="selector"),
        ], className="controles"),
        html.Div(id="tarjetas-territorio", className="fila-tarjetas"),
        html.Div([
            html.Div([html.H3("Esfuerzo de compra"),
                      html.P("Línea discontinua: años con la renta todavía sin publicar (estimada).", className="nota"),
                      grafico("serie-esfuerzo")], className="columna-mitad tarjeta-grafico"),
            html.Div([html.H3("Compra, alquiler e IPC: crecimiento acumulado a cinco años"),
                      html.P("Criterio 2: la compra o el alquiler deben crecer más de 3 puntos por encima del IPC.",
                             className="nota"),
                      grafico("serie-precio")], className="columna-mitad tarjeta-grafico"),
        ], className="fila-graficos"),
        html.Div([
            html.Div([
                html.H3("Calculadora: ¿y si cambian las condiciones?"),
                html.P("Recalcula el esfuerzo del último trimestre con tus supuestos.", className="nota"),
                html.Div([
                    html.Label("Superficie (m²)"),
                    dcc.Slider(id="calc-superficie", min=40, max=150, step=5, value=config.SUPERFICIE_M2,
                                                              marks={m: str(m) for m in (40, 70, 90, 120, 150)}),
                    html.Label("Financiación (% del valor)"),
                    dcc.Slider(id="calc-financiacion", min=50, max=100, step=5, value=int(config.FINANCIACION * 100),
                                                                        marks={m: f"{m} %" for m in (50, 60, 70, 80, 90, 100)}),
                    html.Label("Plazo (años)"), dcc.Slider(id="calc-plazo", min=10, max=40, step=1, value=config.PLAZO_ANIOS,
                                                           marks={m: str(m) for m in (10, 20, 25, 30, 40)}),
                    html.Label("Tipo de interés (%)"), dcc.Slider(id="calc-tipo", min=0.5, max=7, step=0.05, value=TIPO_ACTUAL,
                                                                  marks={m: f"{m} %" for m in (1, 2, 3, 4, 5, 6, 7)}),
                ], className="calculadora"),
                grafico("calc-resultado"),
                html.P(id="calc-texto", className="explicacion"),
            ], className="columna-mitad tarjeta-grafico"),
            html.Div([html.H3("¿Comprar o alquilar?"),
                      html.P("El criterio 1 se cumple si cualquiera de las dos cargas supera el 30 %. El alquiler "
                             "(SERPAVI) es el de los contratos en vigor, no el de los anuncios.", className="nota"),
                      grafico("serie-compra-alquiler"),
                      html.H3("Diferencial de precios"), grafico("serie-diferencial"),
                      html.H3("Últimos trimestres"), html.Div(id="tabla-territorio")],
                     className="columna-mitad tarjeta-grafico"),
        ], className="fila-graficos"),
    ])


@callback(Output("municipio", "options"), Output("municipio", "value"), Input("provincia", "value"))
def municipios_de_provincia(provincia):
    d = MUN[(MUN["cod_prov"] == provincia) & (MUN["trimestre"] == ULTIMO)].sort_values("municipio")
    return opciones_busqueda(dict(zip(d["cod_mun"], d["municipio"], strict=True))), None


def _es_cierto(valor) -> bool:
    """True solo si el valor es verdadero y no falta (pd.NA o NaN cuentan como falso)."""
    return bool(valor) if pd.notna(valor) else False


def _territorio(provincia, municipio):
    if municipio:
        serie = MUN[MUN["cod_mun"] == municipio].sort_values("trimestre")
        return serie, serie["municipio"].iloc[0], D["pred_municipios"].set_index("cod_mun"), municipio
    serie = PROV[PROV["cod_prov"] == provincia].sort_values("trimestre")
    return serie, NOMBRES_PROV.get(provincia, provincia), D["pred_provincias"].set_index("cod_prov"), provincia


@callback(Output("tarjetas-territorio", "children"), Output("serie-esfuerzo", "figure"),
              Output("serie-precio", "figure"), Output("serie-diferencial", "figure"),
              Output("serie-compra-alquiler", "figure"),
              Output("tabla-territorio", "children"),
              Input("provincia", "value"), Input("municipio", "value"), Input("comparar", "value"),
              Input("pestanas", "value"))
@en_pestana("territorio")
def actualizar_territorio(provincia, municipio, comparar):
    serie, nombre, pred, codigo = _territorio(provincia, municipio)
    hoy = serie.dropna(subset=["esfuerzo"]).iloc[-1]
    p = pred.loc[codigo] if codigo in pred.index else None
    tarjetas = [
        tarjeta("Situación legal hoy", estado_chip(hoy["tensionado"]), f"{nombre} · {etiqueta(hoy['trimestre'])}", "destacada"),
        tarjeta("Esfuerzo de compra", pct(hoy["esfuerzo"]),
                f"hipoteca {pct(hoy['esfuerzo_hipoteca'])} + gastos {pct(hoy['esfuerzo'] - hoy['esfuerzo_hipoteca'])}"
                + (" · renta estimada" if hoy["renta_estimada"] else "")),
        tarjeta("Precio − IPC (5 años)", puntos(hoy["diferencial"]),
                f"alquiler − IPC: {puntos(hoy['diferencial_alquiler'])} · umbral: +3"),
        tarjeta("Esfuerzo de alquiler", pct(hoy["esfuerzo_alquiler"]),
                f"alquiler mediano {euros(hoy['alquiler_mes'])}/mes"
                + (" (est.)" if _es_cierto(hoy["alquiler_estimado"]) else "")),
        tarjeta("Valor tasado", f"{euros(hoy['precio_m2'])}/m²", f"renta del hogar: {euros(hoy['renta_hogar'])}"),
        tarjeta("Probabilidad en dos años", pct(p["probabilidad"], 0) if p is not None else "—",
                p["escenario"] if p is not None else ""),
    ]
    series = {nombre: serie}
    if municipio:
        series[NOMBRES_PROV[provincia]] = PROV[PROV["cod_prov"] == provincia]
    for otra in (comparar or [])[:2]:                    # como mucho cuatro líneas en el gráfico
        if otra != provincia or municipio:
            series.setdefault(NOMBRES_PROV[otra], PROV[PROV["cod_prov"] == otra])
    series = {k: v[v["trimestre"] >= PRIMERO] for k, v in series.items()}
    desde = serie[serie["trimestre"] >= PRIMERO - 20]
    tabla = serie.dropna(subset=["esfuerzo"]).tail(8).iloc[::-1]
    filas = [{"Trimestre": etiqueta(r.trimestre), "€/m²": euros(r.precio_m2), "Renta hogar": euros(r.renta_hogar)
              + (" (est.)" if r.renta_estimada else ""), "Tipo": f"{r.tipo_interes:.2f} %".replace(".", ","),
              "Gastos/año": euros(r.gastos_vivienda), "Alquiler/mes": euros(r.alquiler_mes),
              "Esfuerzo compra": pct(r.esfuerzo), "Esfuerzo alquiler": pct(r.esfuerzo_alquiler),
              "Precio − IPC": puntos(r.diferencial), "Estado": r.estado or "—"}
             for r in tabla.itertuples()]
    return (tarjetas, g.serie_esfuerzo(series), g.serie_precio_ipc(desde, nombre), g.serie_diferencial(desde),
            g.serie_compra_alquiler(serie[serie["trimestre"] >= PRIMERO]),
            dash_table.DataTable(filas, [{"name": c, "id": c} for c in filas[0]], **{**ESTILO_TABLA, "page_size": 8}))


@callback(Output("calc-resultado", "figure"), Output("calc-texto", "children"),
              Input("provincia", "value"), Input("municipio", "value"), Input("calc-superficie", "value"),
              Input("calc-financiacion", "value"), Input("calc-plazo", "value"), Input("calc-tipo", "value"),
              Input("pestanas", "value"))
@en_pestana("territorio")
def calculadora(provincia, municipio, superficie, financiacion, plazo, tipo):
    serie, nombre, _, _ = _territorio(provincia, municipio)
    hoy = serie.dropna(subset=["esfuerzo"]).iloc[-1]
    hipoteca = float(calcular_esfuerzo(hoy["precio_m2"], hoy["renta_hogar"], tipo, superficie, financiacion / 100, plazo))
    gastos = hoy["gastos_vivienda"]
    valor = hipoteca + gastos / hoy["renta_hogar"]
    precio = hoy["precio_m2"] * superficie
    cuota = hipoteca * hoy["renta_hogar"] / 12
    texto = [f"En {nombre}, una vivienda de {superficie} m² cuesta unos ", html.B(euros(precio)),
             f". Con un préstamo del {financiacion} % a {plazo} años al " + f"{tipo:.2f} %".replace(".", ","),
             " la cuota sería de ", html.B(f"{euros(cuota)} al mes"), ", más unos ", html.B(f"{euros(gastos / 12)} al mes"),
             " de gastos y suministros: el ", html.B(pct(valor)), " de la renta media del hogar. ",
             "La diferencia frente al cálculo oficial de la ficha aparece en puntos."]
    return g.indicador_esfuerzo(valor, hoy["esfuerzo"]), texto
