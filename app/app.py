"""Cuadro de mando: mapa del esfuerzo de acceso a la vivienda en España.

    python app/app.py                  # desarrollo: http://127.0.0.1:8050/
    gunicorn app.app:server            # producción (Render)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # para «python app/app.py»

from functools import lru_cache, wraps

import pandas as pd
from dash import Dash, Input, Output, dash_table, dcc, html, no_update
from dash.exceptions import PreventUpdate

from app import graficos as g
from app.datos import cargar
from src import config
from src.indicadores import esfuerzo as calcular_esfuerzo

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


# --- Pestañas ------------------------------------------------------------------------------

def pestana_guia():
    """Explicación de la app para quien la abre por primera vez, con un ejemplo real (Madrid)."""
    m = PROV[(PROV["cod_prov"] == "28") & (PROV["trimestre"] == ULTIMO)].iloc[0]
    precio = m["precio_m2"] * config.SUPERFICIE_M2
    cuota = m["esfuerzo_hipoteca"] * m["renta_hogar"] / 12
    resumen = D["modelo"].get("provincias", {})
    metricas = resumen.get("metricas", {})
    elegido = resumen.get("elegido", "")
    modelo_m, pers_m = metricas.get(elegido, {}), metricas.get("Referencia: persistencia", {})

    def termino(nombre, definicion):
        return html.Div([html.Dt(nombre), html.Dd(definicion)], className="termino")

    return html.Div([
        html.Div([
            html.Div([
                html.H3("¿Qué es una zona tensionada?"),
                dcc.Markdown(f"""
La **Ley 12/2023, por el derecho a la vivienda**, permite declarar una *zona de mercado residencial tensionado*
cuando acceder a una vivienda se ha vuelto especialmente difícil. La declaración la hace la comunidad autónoma y
tiene efectos reales: limita la subida de los alquileres y obliga a los grandes propietarios.

El **artículo 18.3** fija dos criterios objetivos. Basta con cumplir **uno**:

1. **Esfuerzo:** pagar la hipoteca **o** el alquiler, más los gastos y suministros básicos, supera el **30 % de la
   renta** media de los hogares.
2. **Precios:** en los **cinco años** anteriores, el precio de la vivienda ha subido al menos **3 puntos más que
   el IPC**.

Esta app calcula los dos criterios para las **52 provincias** y los **{MUN['cod_mun'].nunique()} municipios** de más
de 25.000 habitantes, trimestre a trimestre desde 2015, y estima cuáles estarán tensionados dentro de dos años.
""", link_target="_blank"),
            ], className="columna-mitad tarjeta-grafico"),
            html.Div([
                html.H3(f"Un ejemplo con datos reales: Madrid, {etiqueta(ULTIMO)}"),
                dcc.Markdown(f"""
**Criterio 1 · Esfuerzo de compra**

- Una vivienda de {config.SUPERFICIE_M2} m² a {euros(m['precio_m2'])}/m² (valor tasado medio) cuesta **{euros(precio)}**.
- Hipoteca del {config.FINANCIACION * 100:.0f} % a {config.PLAZO_ANIOS} años al {f"{m['tipo_interes']:.2f}".replace(".", ",")} % →
  cuota de **{euros(cuota)} al mes**.
- Gastos y suministros (agua, luz, gas, comunidad, seguro): **{euros(m['gastos_vivienda'] / 12)} al mes**.
- Renta neta media de un hogar madrileño: **{euros(m['renta_hogar'])} al año** (estimada: el Atlas llega a {ANIO_RENTA}).
- Esfuerzo = (cuota + gastos) × 12 ÷ renta = **{pct(m['esfuerzo'])}** →
  {"**supera** el 30 %" if m['esfuerzo'] > 0.30 else "no llega al 30 %"}.
- Si alquila: {euros(m['alquiler_mes'])} al mes más los mismos gastos → **{pct(m['esfuerzo_alquiler'])}**.

**Criterio 2 · Precios frente a IPC**

- En cinco años el valor tasado ha subido un **{f"{m['crec_precio_5a']:.1f}".replace(".", ",")} %** y el IPC un
  **{f"{m['crec_ipc_5a']:.1f}".replace(".", ",")} %**.
- Diferencial = **{puntos(m['diferencial'])}** → {"**supera** los 3 puntos" if m['diferencial'] > 3 else "no llega a 3 puntos"}.

**Resultado:** {"cumple al menos un criterio: es **zona tensionada**." if m['tensionado'] else "no cumple ninguno."}
"""),
            ], className="columna-mitad tarjeta-grafico"),
        ], className="fila-graficos"),
        html.Div([
            html.H3("Glosario"),
            html.Dl([
                termino("Valor tasado (€/m²)",
                        "Precio por metro cuadrado que fijan las tasadoras para conceder hipotecas. Lo publica cada "
                        "trimestre el Ministerio de Vivienda. Es la serie oficial más larga y homogénea, aunque no es "
                        "exactamente el precio de cierre de la compraventa."),
                termino("Renta neta media por hogar",
                        "Ingresos anuales de un hogar después de impuestos, según el Atlas de renta del INE (declaraciones "
                        "fiscales). Se publica con unos dos años de retraso."),
                termino("Renta o alquiler estimados",
                        "Los años que la fuente aún no ha publicado se proyectan con el crecimiento medio de los tres "
                        "últimos años. En los gráficos aparecen con línea discontinua y el modelo no se entrena con ellos."),
                termino("Gastos y suministros",
                        "Lo que paga al año un hogar medio de la comunidad autónoma por agua, basuras, electricidad, gas "
                        "y otros combustibles, comunidad de vecinos y seguro del hogar (Encuesta de Presupuestos "
                        "Familiares del INE)."),
                termino("Esfuerzo de compra",
                        f"(Cuota anual de la hipoteca + gastos) ÷ renta del hogar. La hipoteca es la de una vivienda tipo de "
                        f"{config.SUPERFICIE_M2} m² financiada al {config.FINANCIACION * 100:.0f} % a {config.PLAZO_ANIOS} años al "
                        "tipo medio de las hipotecas de ese trimestre."),
                termino("Esfuerzo de alquiler",
                        "(Alquiler anual + gastos) ÷ renta del hogar. El alquiler es el mediano de SERPAVI: el de los "
                        "contratos en vigor declarados en el IRPF, no el de los anuncios, por eso suele ser más bajo."),
                termino("IPC",
                        "Índice de Precios de Consumo de la provincia (INE): mide cuánto sube el coste de la vida en general."),
                termino("Diferencial precio − IPC",
                        "Cuántos puntos ha subido el precio de la vivienda en cinco años por encima del IPC. Si la "
                        "vivienda sube un 30 % y el IPC un 15 %, el diferencial es +15 puntos."),
                termino("Tensionado",
                        "Cumple al menos uno de los dos criterios del art. 18.3. Es un cálculo con datos públicos: la "
                        "declaración oficial la tiene que pedir la comunidad autónoma."),
                termino("Probabilidad a dos años",
                        "Lo que estima el modelo de que el territorio esté tensionado ocho trimestres después del último "
                        "dato. Con ella se forman cuatro escenarios: seguirá tensionado, entrará en tensión, saldrá de la "
                        "tensión o seguirá sin tensión."),
                termino("Persistencia",
                        "La referencia con la que se compara el modelo: suponer que dentro de dos años todo estará igual "
                        "que hoy. Es difícil de batir porque el criterio de precios mira cinco años atrás y cambia despacio."),
                termino("Recall y precisión",
                        f"De los territorios que acabaron tensionados, cuántos avisó el modelo (recall); de los avisos que "
                        f"dio, cuántos acertó (precisión). En la prueba, el modelo elegido tiene un recall de "
                        f"{pct(modelo_m.get('recall'), 0)} y una precisión de {pct(modelo_m.get('precision'), 0)}; la "
                        f"persistencia, {pct(pers_m.get('recall'), 0)} y {pct(pers_m.get('precision'), 0)}."),
                termino("AUC",
                        "Mide si el modelo ordena bien los territorios de más a menos riesgo, sin depender del umbral de "
                        "decisión. 0,5 es azar y 1 es perfecto."),
            ], className="glosario"),
        ], className="tarjeta-grafico"),
        html.Div([
            html.H3("Cómo usar cada pestaña"),
            dcc.Markdown("""
- **Mapa** — elige el indicador y mueve el trimestre para ver cómo ha cambiado España desde 2015. Pulsa una provincia
  para abrir su ficha. A la derecha, las provincias con el valor más alto.
- **Ficha territorial** — una provincia o un municipio en detalle: su evolución, comprar frente a alquilar, y una
  calculadora para probar otros supuestos (metros, entrada, plazo, tipo de interés). Puedes compararla con otras dos
  provincias.
- **Municipios** — cada punto es un municipio: a la derecha de la línea vertical cumple el criterio de precios; por
  encima de la horizontal, el de esfuerzo. Debajo, la tabla completa con filtros.
- **Predicción** — qué tal funciona el modelo frente a las referencias, qué variables pesan más y qué territorios
  entrarían en tensión.
- **Datos y método** — fuentes, cálculos, limitaciones e informe de calidad de los datos.
"""),
        ], className="tarjeta-grafico"),
    ])


def pestana_mapa():
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
            html.Div([grafico("mapa"), html.P("Pulsa una provincia para ver su ficha. Canarias aparece desplazada para que el mapa se lea mejor.", className="nota")],
                     className="columna-ancha tarjeta-grafico"),
            html.Div([html.H3(id="titulo-ranking"), grafico("ranking")], className="columna-estrecha tarjeta-grafico"),
        ], className="fila-graficos"),
    ])


def pestana_territorio():
    return html.Div([
        html.Div([
            html.Div([html.Label("Provincia", className="etiqueta-control"),
                      dcc.Dropdown(id="provincia", value="28", clearable=False,
                                   options=[{"label": n, "value": c} for c, n in sorted(NOMBRES_PROV.items(), key=lambda x: x[1])])],
                     className="selector"),
            html.Div([html.Label("Municipio (más de 25.000 habitantes)", className="etiqueta-control"),
                      dcc.Dropdown(id="municipio", placeholder="Toda la provincia")], className="selector"),
            html.Div([html.Label("Comparar con (hasta dos provincias)", className="etiqueta-control"),
                      dcc.Dropdown(id="comparar", multi=True, placeholder="Ninguna",
                                   options=[{"label": n, "value": c} for c, n in sorted(NOMBRES_PROV.items(), key=lambda x: x[1])])],
                     className="selector"),
        ], className="controles"),
        html.Div(id="tarjetas-territorio", className="fila-tarjetas"),
        html.Div([
            html.Div([html.H3("Esfuerzo de compra"),
                      html.P("Línea discontinua: años con la renta todavía sin publicar (estimada).", className="nota"),
                      grafico("serie-esfuerzo")], className="columna-mitad tarjeta-grafico"),
            html.Div([html.H3("Precio frente a IPC: crecimiento acumulado a cinco años"),
                      html.P("Criterio 2: el precio debe crecer más de 3 puntos por encima del IPC.", className="nota"),
                      grafico("serie-precio")], className="columna-mitad tarjeta-grafico"),
        ], className="fila-graficos"),
        html.Div([
            html.Div([
                html.H3("Calculadora: ¿y si cambian las condiciones?"),
                html.P("Recalcula el esfuerzo del último trimestre con tus supuestos.", className="nota"),
                html.Div([
                    html.Label("Superficie (m²)"), dcc.Slider(id="calc-superficie", min=40, max=150, step=5, value=config.SUPERFICIE_M2,
                                                              marks={m: str(m) for m in (40, 70, 90, 120, 150)}),
                    html.Label("Financiación (% del valor)"), dcc.Slider(id="calc-financiacion", min=50, max=100, step=5, value=int(config.FINANCIACION * 100),
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


def pestana_municipios():
    ultimo = MUN[MUN["trimestre"] == ULTIMO]
    return html.Div([
        html.P(["Los ", html.B(f"{len(ultimo)} municipios"), " de más de 25.000 habitantes con valor tasado publicado, ",
                f"en {etiqueta(ULTIMO)}. Cada punto es un municipio: las líneas marcan los dos umbrales legales."],
               className="explicacion"),
        html.Div([
            html.Div([html.Label("Provincia", className="etiqueta-control"),
                      dcc.Dropdown(id="mun-provincia", multi=True, placeholder="Todas",
                                   options=[{"label": n, "value": c} for c, n in sorted(NOMBRES_PROV.items(), key=lambda x: x[1])])],
                     className="selector"),
            html.Div([html.Label("Previsión a dos años", className="etiqueta-control"),
                      dcc.Dropdown(id="mun-escenario", multi=True, placeholder="Todas",
                                   options=["Seguirá tensionado", "Entrará en tensión", "Saldrá de la tensión", "Seguirá sin tensión"])],
                     className="selector"),
        ], className="controles"),
        html.Div(grafico("dispersion"), className="tarjeta-grafico"),
        html.Div(id="tabla-municipios", className="tarjeta-grafico"),
    ])


def pestana_prediccion():
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
                      html.P("Importancia por permutación en el periodo de prueba: cuánto empeora la capacidad de ordenar (AUC) si se desordena esa variable.",
                             className="nota")], className="columna-mitad tarjeta-grafico"),
            html.Div([html.H3("Territorios que entrarían en tensión"), html.Div(id="tabla-entraran")],
                     className="columna-mitad tarjeta-grafico"),
        ], className="fila-graficos"),
        html.Div(id="tabla-metricas", className="tarjeta-grafico"),
    ])


def pestana_metodo():
    cal = D["calidad"]
    val = cal.get("validacion", {})
    norm = cal.get("normalizacion", {})
    filas = [{"Tabla": k, "Desde": v["desde"], "Hasta": v["hasta"], "Filas": v["filas"], "Válidas": v["validas"],
              "Rechazadas": v["rechazadas"], "Cobertura": f"{v['cobertura_pct']} %" if "cobertura_pct" in v else "—",
              "Motivos": "; ".join(f"{m}: {n}" for m, n in v["rechazadas_por_regla"].items()) or "—"}
             for k, v in val.items()]
    corregidos = [{"Provincia en la fuente": r["provincia_fuente"], "Municipio en la fuente": r["municipio_fuente"],
                   "Asignado a": MUN.loc[MUN["cod_mun"] == r["cod_mun"], "municipio"].head(1).squeeze() or r["cod_mun"],
                   "Provincia real": NOMBRES_PROV.get(r["cod_mun"][:2], "")}
                  for r in norm.get("municipios_en_otra_provincia", [])]
    return html.Div([
        html.Div([
            html.Div([
                html.H3("Cómo se calcula"),
                dcc.Markdown(f"""
**Criterio 1 · Esfuerzo.** Cuota anual de la hipoteca de una vivienda de **{config.SUPERFICIE_M2} m²** al valor
tasado medio del trimestre, financiada al **{config.FINANCIACION * 100:.0f} %** a **{config.PLAZO_ANIOS} años** al tipo medio
de las hipotecas sobre vivienda, **más los gastos y suministros básicos** (agua, basuras, electricidad, gas y otros
combustibles, gastos de comunidad y seguro del hogar: gasto medio por hogar de la comunidad autónoma según la
Encuesta de Presupuestos Familiares), todo dividido entre la **renta neta media por hogar**. La ley dice «hipoteca
**o** alquiler», así que se calcula también la carga de alquilar (alquiler mensual mediano de SERPAVI por doce, más
los mismos gastos) y el criterio se cumple si **cualquiera de las dos** supera el **30 %**.

**Criterio 2 · Precios.** Crecimiento acumulado del valor tasado en los cinco años anteriores menos el crecimiento
del IPC de la provincia en el mismo periodo. Se cumple si la diferencia supera **3 puntos**.

Un territorio está **tensionado** si cumple al menos uno de los dos, como dice el
[artículo 18.3 de la Ley 12/2023](https://www.boe.es/eli/es/l/2023/05/24/12).

**Modelo.** Clasificación: ¿estará tensionado dentro de {config.HORIZONTE_TRIMESTRES} trimestres? Etiquetas reales
calculadas hacia atrás con el mismo criterio; validación temporal (entrenar con el pasado, evaluar con el futuro);
métrica principal el recall de la clase tensionada.
""", link_target="_blank"),
            ], className="columna-mitad tarjeta-grafico"),
            html.Div([
                html.H3("Limitaciones, a la vista"),
                dcc.Markdown(f"""
- **La renta va con retraso.** El Atlas de renta llega hasta **{ANIO_RENTA}**. Para los años posteriores se proyecta
  con el crecimiento medio de los tres últimos años de cada territorio, y los gráficos lo marcan con línea discontinua.
  El modelo **no** se entrena con esas etiquetas estimadas.
- **Los gastos son una media de la comunidad autónoma.** La Encuesta de Presupuestos Familiares no baja a provincia
  ni a municipio, y empieza en 2016: 2015 toma el valor de 2016 y 2026 el de 2025.
- **Valor tasado, no precio de cierre.** Es la serie oficial más larga y homogénea por provincia y municipio.
- **El alquiler de SERPAVI es el de los contratos en vigor**, declarados en el IRPF, no el precio que encuentra hoy
  quien busca piso: muchos contratos son antiguos y más baratos, así que el esfuerzo de alquilar sale por debajo del
  real para quien entra ahora en el mercado. Llega hasta 2024 (2025-2026 se proyectan, como la renta) y en País Vasco
  y Navarra (régimen foral) solo hay datos desde 2021-2024.
- **Municipios de más de 25.000 habitantes**: el Ministerio no publica valor tasado de los demás.
- El índice de alquiler del INE no cubre **País Vasco ni Navarra** (régimen foral); el modelo imputa ese hueco.
""", link_target="_blank"),
            ], className="columna-mitad tarjeta-grafico"),
        ], className="fila-graficos"),
        html.Div([
            html.H3("Informe de calidad de los datos"),
            html.P(f"Generado el {cal.get('generado', '—')[:10]} a partir de {cal.get('fuentes', {}).get('descargas', '—')} "
                   f"descargas oficiales ({cal.get('fuentes', {}).get('megabytes', '—')} MB). Las filas que no pasan una "
                   "regla no se borran: se apartan con su motivo.", className="nota"),
            dash_table.DataTable(filas, [{"name": c, "id": c} for c in filas[0]] if filas else [], **ESTILO_TABLA),
        ], className="tarjeta-grafico"),
        html.Div([
            html.H3("Normalización de territorios"),
            html.P(f"El Ministerio publica nombres, no códigos. Se han emparejado {norm.get('municipios_emparejados', '—')} de "
                   f"{norm.get('municipios_fuente_ministerio', '—')} municipios con su código INE. Estos aparecían bajo una "
                   "provincia equivocada o mal escrita en la fuente y se han corregido:", className="nota"),
            dash_table.DataTable(corregidos, [{"name": c, "id": c} for c in corregidos[0]] if corregidos else [], **ESTILO_TABLA),
        ], className="tarjeta-grafico"),
        html.Div([
            html.H3("Fuentes"),
            dcc.Markdown("""
- **INE, API JSON** — Atlas de distribución de renta de los hogares; IPC provincial; índice de precios de vivienda
  en alquiler; estadística de transmisiones de derechos de la propiedad; estadística de hipotecas; Encuesta de
  Presupuestos Familiares (gastos y suministros de la vivienda).
- **SERPAVI**, Ministerio de Vivienda — alquiler mensual mediano por provincia y municipio (2011-2024).
- **Ministerio de Vivienda y Agenda Urbana** — valor tasado medio de la vivienda libre por provincias y por municipios
  de más de 25.000 habitantes (boletín estadístico).
- **Mapa de provincias** — Code for Germany, *click_that_hood* (datos abiertos).

Este proyecto no está asociado a estos organismos: reutiliza sus datos públicos citando la fuente.
""", link_target="_blank"),
            html.Button("Descargar el panel provincial (CSV)", id="boton-descarga", className="boton"),
            dcc.Download(id="descarga"),
        ], className="tarjeta-grafico"),
    ])


ESTILO_TABLA = dict(
    style_table={"overflowX": "auto"}, page_size=12, sort_action="native",
    style_header={"backgroundColor": "#f3f1ec", "fontWeight": "600", "border": "none", "color": g.TINTA},
    style_cell={"fontFamily": "Inter, system-ui, sans-serif", "fontSize": 13, "padding": "6px 10px",
                "border": "none", "borderBottom": "1px solid #ece9e2", "textAlign": "left", "color": g.TINTA,
                "whiteSpace": "normal", "height": "auto", "maxWidth": 340},
)

# --- App -----------------------------------------------------------------------------------

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


app = Dash(__name__, title="Esfuerzo de acceso a la vivienda", suppress_callback_exceptions=True, compress=True,
           meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"},
                      {"name": "description", "content": "Cuadro de mando que cruza precio de la vivienda y renta de los hogares y aplica el criterio legal de zona tensionada."}])
server = app.server

app.layout = html.Div([
    html.Header([
        html.Div([
            html.H1("Mapa del esfuerzo de acceso a la vivienda"),
            html.P(["Precio de la vivienda frente a renta de los hogares y criterio legal de ",
                    html.B("zona tensionada"), " (art. 18.3 de la Ley 12/2023), con previsión a dos años."]),
        ]),
        html.Div([html.Span(f"Precios hasta {etiqueta(ULTIMO)}", className="chip"),
                  html.Span(f"Renta publicada hasta {ANIO_RENTA}", className="chip")], className="chips"),
    ], className="cabecera"),
    dcc.Tabs(id="pestanas", value="mapa", className="pestanas", children=[
        dcc.Tab(label="Cómo leerlo", value="guia", children=pestana_guia()),
        dcc.Tab(label="Mapa", value="mapa", children=pestana_mapa()),
        dcc.Tab(label="Ficha territorial", value="territorio", children=pestana_territorio()),
        dcc.Tab(label="Municipios", value="municipios", children=pestana_municipios()),
        dcc.Tab(label="Predicción", value="prediccion", children=pestana_prediccion()),
        dcc.Tab(label="Datos y método", value="metodo", children=pestana_metodo()),
    ]),
    html.Footer(["Ángel Cuadrado Serrano · Desarrollo de Aplicaciones para la Visualización de Datos · ICAI 2026-2027 · ",
                 html.A("Código en GitHub", href="https://github.com/angelcuadrado/davd-26-27-cuadrado-angel", target="_blank")]),
], className="contenedor")


# --- Callbacks: mapa -----------------------------------------------------------------------

def _datos_mapa(indicador: str, trimestre: pd.Period) -> pd.DataFrame:
    if indicador == "probabilidad":
        d = D["pred_provincias"].copy()
        d["estado"] = d["tensionado"].map({True: "Tensionado", False: "Sin tensión"})
        d["hover"] = ("Probabilidad en dos años: " + d["probabilidad"].map(pct) + "<br>Previsión: " + d["escenario"])
        return d
    d = PROV[PROV["trimestre"] == trimestre].copy()
    d["hover"] = ("Esfuerzo de compra: " + d["esfuerzo"].map(pct) + "<br>Esfuerzo de alquiler: "
                  + d["esfuerzo_alquiler"].map(pct) + "<br>Precio − IPC (5 años): " + d["diferencial"].map(puntos)
                  + "<br>" + d["estado"].fillna("Sin dato") + "<br>Valor tasado: " + d["precio_m2"].map(euros) + "/m²")
    return d


@app.callback(Output("mapa", "figure"), Output("ranking", "figure"), Output("titulo-ranking", "children"),
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
        tarjeta("Por precios (> IPC + 3)", str(int(actual["criterio_precio"].sum())), "criterio 2"),
        tarjeta("Esfuerzo mediano", pct(actual["esfuerzo"].median()), "de las 52 provincias"),
        tarjeta("Tensionadas en dos años", f"{int(pred['prediccion'].sum())} de {len(pred)}",
                f"previsión para {etiqueta(ULTIMO + config.HORIZONTE_TRIMESTRES)}"),
    ]
    texto_trimestre = ("Trimestre: el último disponible (la previsión se hace desde hoy)" if indicador == "probabilidad"
                       else f"Trimestre: {etiqueta(trimestre)}")
    return (g.mapa(d, D["geojson"], indicador, provincia), g.ranking(d, columna_ranking, "provincia"), titulo,
            tarjetas, texto_trimestre, g.INDICADORES[indicador]["explicacion"], indicador == "probabilidad")


@app.callback(Output("provincia", "value"), Output("pestanas", "value"),
              Input("mapa", "clickData"), prevent_initial_call=True)
def clic_en_mapa(clic):
    if not clic or not clic.get("points"):
        return no_update, no_update
    return clic["points"][0]["location"], "territorio"


# --- Callbacks: ficha territorial ----------------------------------------------------------

@app.callback(Output("municipio", "options"), Output("municipio", "value"), Input("provincia", "value"))
def municipios_de_provincia(provincia):
    d = MUN[(MUN["cod_prov"] == provincia) & (MUN["trimestre"] == ULTIMO)].sort_values("municipio")
    return [{"label": r.municipio, "value": r.cod_mun} for r in d.itertuples()], None


def _territorio(provincia, municipio):
    if municipio:
        serie = MUN[MUN["cod_mun"] == municipio].sort_values("trimestre")
        return serie, serie["municipio"].iloc[0], D["pred_municipios"].set_index("cod_mun"), municipio
    serie = PROV[PROV["cod_prov"] == provincia].sort_values("trimestre")
    return serie, NOMBRES_PROV.get(provincia, provincia), D["pred_provincias"].set_index("cod_prov"), provincia


@app.callback(Output("tarjetas-territorio", "children"), Output("serie-esfuerzo", "figure"),
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
        tarjeta("Precio − IPC (5 años)", puntos(hoy["diferencial"]), "umbral: +3 puntos"),
        tarjeta("Esfuerzo de alquiler", pct(hoy["esfuerzo_alquiler"]),
                f"alquiler mediano {euros(hoy['alquiler_mes'])}/mes" + (" (est.)" if hoy["alquiler_estimado"] == True else "")),
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


@app.callback(Output("calc-resultado", "figure"), Output("calc-texto", "children"),
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


# --- Callbacks: municipios -----------------------------------------------------------------

@app.callback(Output("dispersion", "figure"), Output("tabla-municipios", "children"),
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
              "Renta hogar (€)": round(r.renta_hogar), "Alquiler (€/mes)": None if pd.isna(r.alquiler_mes) else round(r.alquiler_mes),
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


# --- Callbacks: predicción -----------------------------------------------------------------

def lectura(nivel: str, elegido: str, metricas: dict, resumen: dict) -> list:
    """Lectura honesta del resultado frente a las referencias."""
    m, pers = metricas[elegido], metricas["Referencia: persistencia"]
    texto = [html.B("Cómo leerlo. "),
             f"La referencia difícil es la persistencia («dentro de dos años estará como hoy»): el criterio de precios mira "
             f"cinco años hacia atrás y el estado tiene mucha inercia. "]
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


@app.callback(Output("resumen-modelo", "children"), Output("lectura-modelo", "children"),
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


@app.callback(Output("descarga", "data"), Input("boton-descarga", "n_clicks"), prevent_initial_call=True)
def descargar(_):
    columnas = ["cod_prov", "provincia", "etiqueta", "precio_m2", "renta_hogar", "renta_estimada", "tipo_interes",
                "esfuerzo", "crec_precio_5a", "crec_ipc_5a", "diferencial", "criterio_esfuerzo", "criterio_precio", "tensionado"]
    d = PROV[PROV["trimestre"] >= PRIMERO][columnas].rename(columns={"etiqueta": "trimestre"})
    return dcc.send_data_frame(d.to_csv, "esfuerzo_vivienda_provincias.csv", index=False, sep=";", decimal=",")


if __name__ == "__main__":
    app.run(debug=True)
