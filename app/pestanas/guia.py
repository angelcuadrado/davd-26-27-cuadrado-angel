"""Pestaña «Cómo leerlo»: qué es una zona tensionada, ejemplo real y glosario."""
from dash import dcc, html

from app.comun import ANIO_RENTA, MUN, PROV, ULTIMO, D, etiqueta, euros, pct, puntos
from src import config


def layout():
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
2. **Precios:** en los **cinco años** anteriores, el precio de compra **o** el alquiler ha subido al menos
   **3 puntos más que el IPC**.

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
- Diferencial de la compra = **{puntos(m['diferencial'])}** →
  {"**supera** los 3 puntos" if m['diferencial'] > 3 else "no llega a 3 puntos"}.
- El alquiler ha subido un **{f"{m['crec_alquiler_5a']:.1f}".replace(".", ",")} %**: diferencial de
  **{puntos(m['diferencial_alquiler'])}**.

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
                        f"{config.SUPERFICIE_M2} m² financiada al {config.FINANCIACION * 100:.0f} % "
                        f"a {config.PLAZO_ANIOS} años al "
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
