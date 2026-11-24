"""Pestaña «Datos y método»: cálculo, limitaciones, informe de calidad, fuentes y descarga."""
from dash import Input, Output, callback, dash_table, dcc, html

from app.comun import ANIO_RENTA, ESTILO_TABLA, MUN, NOMBRES_PROV, PRIMERO, PROV, D
from src import config


def layout():
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

**Criterio 2 · Precios.** Crecimiento acumulado en los cinco años anteriores menos el crecimiento del IPC de la
provincia en el mismo periodo. Se calcula para la compra (valor tasado) y para el alquiler (SERPAVI), porque la ley
dice «precio de compra **o** alquiler»: se cumple si **cualquiera de los dos** supera los **3 puntos**.

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


@callback(Output("descarga", "data"), Input("boton-descarga", "n_clicks"), prevent_initial_call=True)
def descargar(_):
    columnas = ["cod_prov", "provincia", "etiqueta", "precio_m2", "renta_hogar", "renta_estimada", "tipo_interes",
                "esfuerzo", "crec_precio_5a", "crec_ipc_5a", "diferencial", "criterio_esfuerzo", "criterio_precio", "tensionado"]
    d = PROV[PROV["trimestre"] >= PRIMERO][columnas].rename(columns={"etiqueta": "trimestre"})
    return dcc.send_data_frame(d.to_csv, "esfuerzo_vivienda_provincias.csv", index=False, sep=";", decimal=",")
