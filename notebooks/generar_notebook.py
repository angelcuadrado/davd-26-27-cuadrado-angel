"""Genera y ejecuta notebooks/exploracion_y_modelo.ipynb a partir de los artefactos del pipeline.

    python notebooks/generar_notebook.py

El notebook se guarda ya ejecutado, para que en GitHub se vean las tablas y los gráficos.
"""
from pathlib import Path

import nbformat
from nbclient import NotebookClient

AQUI = Path(__file__).resolve().parent
md, code = nbformat.v4.new_markdown_cell, nbformat.v4.new_code_cell

celdas = [
    md("# Exploración y selección de modelo\n\n"
       "Este notebook acompaña al pipeline (`python -m src.pipeline`) y al cuadro de mando. Lee los artefactos de "
       "`data/publicado/`, comprueba que los indicadores tienen sentido y justifica la elección del modelo."),
    code("import json\nfrom pathlib import Path\n\nimport pandas as pd\nimport plotly.express as px\n"
         "import plotly.io as pio\n\npio.renderers.default = 'notebook_connected'\n"
         "pd.set_option('display.float_format', lambda x: f'{x:,.3f}')\n"
         "PUB = Path('..') / 'data' / 'publicado'\n"
         "prov = pd.read_parquet(PUB / 'panel_provincias.parquet')\n"
         "mun = pd.read_parquet(PUB / 'panel_municipios.parquet')\n"
         "calidad = json.loads((PUB / 'calidad.json').read_text(encoding='utf-8'))\n"
         "modelo = json.loads((PUB / 'modelo.json').read_text(encoding='utf-8'))\n"
         "prov.shape, mun.shape, calidad['ultimo_trimestre_precios'], calidad['ultimo_anio_renta']"),
    md("## 1. Calidad de los datos\n\nCada tabla, cuántas filas pasan las reglas y por qué se apartan las demás."),
    code("pd.DataFrame(calidad['validacion']).T[['desde', 'hasta', 'filas', 'validas', 'rechazadas', 'cobertura_pct']]"),
    code("norm = calidad['normalizacion']\n"
         "print('Municipios emparejados:', norm['municipios_emparejados'], 'de', norm['municipios_fuente_ministerio'])\n"
         "print('Métodos:', norm['metodos_municipios'])\n"
         "pd.DataFrame(norm['municipios_en_otra_provincia'])"),
    md("## 2. El índice de esfuerzo hoy\n\nÚltimo trimestre disponible. La renta de los años sin publicar es estimada."),
    code("ultimo = prov[prov['trimestre'] == prov['trimestre'].max()]\n"
         "ultimo.sort_values('esfuerzo', ascending=False)[['provincia', 'precio_m2', 'renta_hogar', 'esfuerzo', "
         "'diferencial', 'criterio_esfuerzo', 'criterio_precio', 'tensionado']].head(10)"),
    code("fig = px.scatter(ultimo, x='diferencial', y='esfuerzo', hover_name='provincia', color='tensionado',\n"
         "                 color_discrete_map={True: '#D55E00', False: '#0072B2'},\n"
         "                 labels={'diferencial': 'Precio − IPC a cinco años (puntos)', 'esfuerzo': 'Esfuerzo'})\n"
         "fig.add_hline(y=0.30, line_dash='dot'); fig.add_vline(x=3, line_dash='dot')\n"
         "fig.update_yaxes(tickformat='.0%'); fig.update_layout(height=420, template='simple_white')"),
    md("La mayoría de provincias tensionadas lo están por el **criterio de precios** (cuadrante derecho), no por el "
       "de esfuerzo: los precios llevan cinco años creciendo bastante por encima del IPC, pero la cuota sobre la "
       "renta solo supera el 30 % en los mercados más caros."),
    md("## 3. Evolución: cuántas provincias cumplen cada criterio"),
    code("evol = (prov[prov['trimestre'] >= '2015Q1'].groupby('trimestre')[['criterio_esfuerzo', 'criterio_precio', 'tensionado']]\n"
         "        .sum().reset_index().melt('trimestre', var_name='criterio', value_name='provincias'))\n"
         "fig = px.line(evol, x='trimestre', y='provincias', color='criterio',\n"
         "              color_discrete_sequence=['#0072B2', '#E69F00', '#D55E00'])\n"
         "fig.update_layout(height=380, template='simple_white')"),
    md("## 4. Modelo: ¿supera a las referencias?\n\n"
       "Validación temporal: entrenamiento con trimestres anteriores a 2021, prueba con 2021–2022 (etiquetas de "
       "2023–2024, las últimas calculadas con renta publicada). El umbral de decisión de cada modelo se eligió en "
       "la validación temporal dentro del entrenamiento, maximizando F2."),
    code("def tabla(nivel):\n"
         "    m = pd.DataFrame(modelo[nivel]['metricas']).T.drop(columns='matriz')\n"
         "    return m[[c for c in ['recall', 'precision', 'f2', 'roc_auc', 'umbral', 'f2_validacion_temporal'] if c in m]]\n"
         "print('Provincias · elegido:', modelo['provincias']['elegido'])\ntabla('provincias')"),
    code("print('Municipios · elegido:', modelo['municipios']['elegido'])\ntabla('municipios')"),
    md("La **persistencia** (dentro de dos años estará como hoy) es una referencia exigente porque el estado legal "
       "tiene mucha inercia: el criterio de precios mira cinco años hacia atrás. Lo que aporta el modelo es "
       "detectar los cambios de estado, que la persistencia por definición nunca anticipa."),
    code("pd.DataFrame(modelo['provincias']['importancias'])[['descripcion', 'importancia', 'desviacion']].head(8)"),
    code("pd.DataFrame(modelo['provincias']['coeficientes'])[['descripcion', 'coeficiente']].head(8)"),
    md("## 5. Previsión a dos años"),
    code("pred = pd.read_parquet(PUB / 'predicciones_provincias.parquet')\n"
         "pred['escenario'].value_counts()"),
    code("pred[['provincia', 'probabilidad', 'escenario', 'esfuerzo', 'diferencial']].head(12)"),
]

nb = nbformat.v4.new_notebook(cells=celdas)
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
NotebookClient(nb, timeout=300, kernel_name="python3", resources={"metadata": {"path": str(AQUI)}}).execute()
nbformat.write(nb, AQUI / "exploracion_y_modelo.ipynb")
print("Escrito", AQUI / "exploracion_y_modelo.ipynb")
