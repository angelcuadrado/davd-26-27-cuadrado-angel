# Mapa del esfuerzo de acceso a la vivienda en España

**App en línea: <https://esfuerzo-vivienda.onrender.com/>**

Cuadro de mando interactivo que cruza el precio de la vivienda con la renta de los hogares a escala
territorial, aplica el criterio legal de **zona de mercado residencial tensionado** y predice qué
territorios lo cumplirán en los próximos dos años.

> Proyecto de la asignatura **Desarrollo de Aplicaciones para la Visualización de Datos** (DAVD),
> curso 2026-2027. Ángel Cuadrado Serrano.

---

## Descripción

El debate sobre la vivienda en España se hace con cifras agregadas —el precio medio nacional, la
subida interanual— que ocultan lo que de verdad importa: **cuánto esfuerzo supone la vivienda para una
familia concreta en su municipio concreto**.

La [Ley 12/2023, por el derecho a la vivienda](https://www.boe.es/eli/es/l/2023/05/24/12) puso número
a ese problema. Su **artículo 18.3** permite declarar *zona de mercado residencial tensionado* cuando
se cumple **uno** de estos dos criterios:

| Criterio | Umbral |
| --- | --- |
| Carga del coste de la vivienda | Supera el **30 %** de la renta media de los hogares |
| Crecimiento acumulado del precio | Más de **3 puntos por encima del IPC** en los cinco años precedentes |

La declaración activa límites a la actualización de las rentas de alquiler y obligaciones para los
grandes tenedores, así que la pregunta tiene consecuencias económicas reales.

Hay portales que publican precios y el INE difunde sus índices, pero **no existe una herramienta
pública que cruce precio con renta a escala municipal, aplique el criterio legal y lo proyecte hacia
delante**. Eso es lo que hace esta aplicación.

## Objetivos

1. **Calcular el índice de esfuerzo** de acceso a la vivienda por territorio y trimestre, a partir de
   fuentes oficiales y con la metodología documentada y reproducible.
2. **Evaluar los dos criterios del artículo 18.3** sobre toda la serie histórica, de modo que se pueda
   ver qué territorios los cumplen hoy y cuáles los cumplieron en el pasado.
3. **Predecir el tensionamiento** a dos años con un modelo de clasificación entrenado sobre etiquetas
   derivadas del propio criterio legal.
4. **Publicar un cuadro de mando** accesible en una URL pública, con mapa, series temporales, rankings
   y el informe de calidad de los datos a la vista.
5. **Documentar las limitaciones** de las fuentes en la propia interfaz, en lugar de ocultarlas.

## Qué dicen los datos (2026 T2)

- **41 de las 52 provincias** cumplen hoy algún criterio del art. 18.3, casi todas por el **criterio de
  precios**: el valor tasado lleva cinco años creciendo muy por encima del IPC.
- Por **esfuerzo** (hipoteca más gastos y suministros, como dice la ley) superan el 30 % **cinco
  provincias**: Málaga (36 %), Baleares (35 %), Madrid (34 %), Gipuzkoa (31 %) y Barcelona (30 %). Los
  gastos de la vivienda suman entre 4 y 6 puntos de esfuerzo según la comunidad.
- Entre los municipios de más de 25.000 habitantes, 74 superan el 30 %; encabezan **Santa Eulària des
  Riu (52 %), Calvià, Marbella, Fuengirola y Benidorm**, todos por encima del 43 %.
- **Alquilar** (alquiler mediano de SERPAVI más los mismos gastos) no supera el 30 % en ningún sitio: el
  máximo es Málaga entre las provincias (28 %) y Fuengirola entre los municipios (29 %). Ojo: SERPAVI
  recoge los contratos en vigor declarados en el IRPF, muchos antiguos y más baratos que los anuncios de
  hoy, así que infravalora el esfuerzo de quien busca piso ahora.
- La referencia de **persistencia** («dentro de dos años estará como hoy») es muy difícil de batir: el
  modelo provincial elegido acierta algo más en sus avisos (precisión 67 % frente a 64 %) pero detecta
  algo menos (recall 70 % frente a 75 %). Detalle y lectura en la pestaña *Predicción* de la app.

## Fuentes de datos

Todas públicas, gratuitas y oficiales. Cada descarga queda registrada en `data/raw/manifiesto.json`
(URL, fecha, tamaño y huella SHA-256).

| Fuente | Qué se usa | Acceso | Frecuencia |
| --- | --- | --- | --- |
| [API JSON del INE](https://www.ine.es/dyngs/DAB/index.htm?cid=1099) | IPC provincial (tabla 76141), índice de precios de vivienda en alquiler (59058), compraventas de viviendas (6150), tipo de interés de las hipotecas sobre vivienda (24457, 24460) | REST, sin clave | Mensual / anual |
| [Atlas de Distribución de Renta de los Hogares](https://www.ine.es/dyngs/INEbase/operacion.htm?c=Estadistica_C&cid=1254736177088) | Renta neta media por hogar y población, por provincia y municipio, 2015–2024 | Misma API (108 tablas) | Anual (≈2 años de desfase) |
| [Ministerio de Vivienda — boletín estadístico](https://boletinestadistico.transportes.gob.es/2?orden=35000000) | Valor tasado medio de la vivienda libre (€/m²): 52 provincias desde 1995 y 306 municipios de más de 25.000 habitantes desde 2005 | Descarga de Excel | Trimestral |
| [Encuesta de Presupuestos Familiares (INE)](https://www.ine.es/dyngs/INEbase/operacion.htm?c=Estadistica_C&cid=1254736176806) | Gasto medio por hogar en agua, basuras, electricidad, gas y otros combustibles, gastos de comunidad y seguro del hogar, por comunidad autónoma (tabla 73993), 2016–2025 | Misma API | Anual |
| [SERPAVI — Ministerio de Vivienda](https://www.mivau.gob.es/vivienda/alquila-bien-es-tu-derecho/serpavi) | Alquiler mensual mediano (€/mes) de los contratos de vivienda habitual declarados en el IRPF, por provincia y municipio, 2011–2024 | Descarga de Excel (71 MB) | Anual |
| [click_that_hood](https://github.com/codeforgermany/click_that_hood) | Contorno de las provincias con su código INE | GeoJSON | — |

**Cambio respecto a la propuesta.** El precio en euros sale del valor tasado del Ministerio de Vivienda,
no del IPV del INE: el IPV es un índice (no da euros, que hacen falta para calcular la cuota) y solo se
publica por comunidad autónoma. SERPAVI no tiene API, pero publica un Excel con toda la serie: se descarga
y se lee como las demás fuentes.

### Limitaciones, declaradas también en la app

- El Atlas de renta llega hasta **2024**. Para 2025–2026 la renta se proyecta con el crecimiento medio de
  los tres últimos años de cada territorio (acotado entre −2 % y +6 %); los gráficos lo marcan con línea
  discontinua y **el modelo no se entrena con etiquetas calculadas con renta estimada**.
- Los **gastos y suministros** son el gasto medio por hogar de la comunidad autónoma: la Encuesta de
  Presupuestos Familiares no baja a provincia ni municipio. Empieza en 2016 (2015 toma ese valor).
- **SERPAVI** mide los alquileres en vigor, no los precios de oferta; llega hasta 2024 (2025–2026 se
  proyectan como la renta) y en País Vasco y Navarra (régimen foral) solo tiene datos desde 2021–2024.
- El Ministerio solo publica valor tasado de municipios de **más de 25.000 habitantes**.
- El índice de alquiler del INE no cubre **País Vasco ni Navarra**; el modelo imputa la mediana.

## Arquitectura

```
┌───────────┐   ┌───────────────┐   ┌────────────┐   ┌─────────────────┐   ┌────────────┐
│  Ingesta  │ → │ Normalización │ → │ Validación │ → │ Cálculo + modelo│ → │ Publicación│ → Dash
└───────────┘   └───────────────┘   └────────────┘   └─────────────────┘   └────────────┘
 API INE          nombres → códigos   reglas con       esfuerzo, criterios   data/publicado
 Excel MIVAU      INE, erratas        motivo, informe  art. 18.3, modelo     (parquet, json)
```

| Etapa | Módulo | Qué hace |
| --- | --- | --- |
| **Ingesta** | `src/descargas.py`, `src/ingesta.py` | Cliente de la API del INE con caché en disco, reintentos con espera exponencial y manifiesto de descargas. Las tablas que superan el límite de volumen de la API se piden año a año. Lectura de los Excel del Ministerio reconstruyendo el trimestre de cada columna. |
| **Normalización** | `src/normalizacion.py` | El Ministerio da nombres, no códigos. Se traducen a códigos INE con una forma canónica (sin tildes, artículo delante, nombres bilingües), alias y búsqueda por parecido. Empareja los **306** municipios y corrige erratas de la fuente («Córdaba», «Valladodid») y **8 municipios listados bajo otra provincia** (Almuñécar aparece en Córdoba). |
| **Validación** | `src/validacion.py` | Reglas explícitas de nulos, rangos, duplicados y número mínimo de tasaciones. Las filas que fallan se apartan con su motivo (`data/publicado/filas_rechazadas.csv`) y se resume todo en `calidad.json`, visible en la app. |
| **Cálculo** | `src/indicadores.py` | Esfuerzo ((cuota de un préstamo francés + gastos y suministros) / renta), crecimiento a cinco años frente al IPC y estado legal. Los desfases se buscan por fecha, no por posición, para que un trimestre que falta no desplace la comparación. |
| **Modelo** | `src/modelo.py` | Ver abajo. |
| **Orquestación** | `src/pipeline.py` | Ejecuta todo y publica en `data/publicado/` lo que lee la app: la app **no** descarga ni reentrena al arrancar. |

### Modelo

**Clasificación binaria**: ¿cumplirá el territorio algún criterio dentro de ocho trimestres?

- **Etiqueta**: el estado legal calculado hacia atrás con la misma regla; no es una definición propia.
- **Variables** (15): esfuerzo de compra y su distancia al umbral, esfuerzo de alquiler, diferencial precio−IPC, sus cambios en un año,
  crecimiento del precio y de la renta, tipo de interés y su cambio, nivel de precio, estado actual,
  compraventas por 1.000 habitantes y su variación, y variación del alquiler. Los municipios reciben las
  variables de mercado de su provincia.
- **Modelos**: regresión logística regularizada (interpretable), bosque aleatorio y gradient boosting,
  todos dentro de un `Pipeline` (imputación y escalado ajustados solo con el entrenamiento).
- **Validación temporal**: entrenamiento con 2015–2020, prueba con 2021–2022 (cuyas etiquetas son
  2023–2024, las últimas con renta publicada). Dentro del entrenamiento, ventana creciente por años para
  elegir modelo y **umbral de decisión** (el que maximiza F2), sin tocar la prueba.
- **Métrica principal: recall** de la clase tensionada, con F2 para no premiar avisar de todo.
- **Referencias**: clase mayoritaria y **persistencia** («dentro de dos años estará como hoy»), que es la
  difícil de batir porque el criterio de precios mira cinco años atrás.

| Provincias, periodo de prueba | Recall | Precisión | AUC |
| --- | --- | --- | --- |
| Referencia: persistencia | 75 % | 64 % | — |
| Regresión logística | 29 % | 94 % | 0,93 |
| **Bosque aleatorio (elegido)** | 70 % | **67 %** | 0,94 |
| Gradient boosting | 63 % | 58 % | 0,92 |

El modelo se elige por F2 en la validación temporal, no en la prueba; en la prueba no supera el recall
de la persistencia, y así se cuenta en la app. A nivel municipal el 64 % de los casos de prueba ya están
tensionados, así que predecir siempre «tensión» acierta mucho; ahí la AUC (≈0,84) es la medida justa. El notebook
[`notebooks/exploracion_y_modelo.ipynb`](notebooks/exploracion_y_modelo.ipynb) recoge el análisis.

## El cuadro de mando

| Pestaña | Qué enseña |
| --- | --- |
| **Cómo leerlo** | Qué es una zona tensionada, los dos criterios con un ejemplo real calculado con los datos de Madrid, glosario de todos los términos y guía de uso. |
| **Mapa** | Coropleta de provincias para cinco indicadores (esfuerzo de compra, esfuerzo de alquiler, diferencial, situación legal y probabilidad a dos años), con selector de trimestre desde 2015 y ranking. Pulsar una provincia abre su ficha. |
| **Ficha territorial** | Provincia o municipio, comparable con hasta dos provincias más: evolución del esfuerzo (con la renta estimada en discontinua), comprar frente a alquilar, precio frente a IPC, diferencial, tabla de los últimos trimestres y una **calculadora** para cambiar superficie, financiación, plazo y tipo de interés. |
| **Municipios** | Los 306 municipios en el plano de los dos criterios y una tabla ordenable y filtrable. |
| **Predicción** | Modelos frente a referencias, matriz de confusión, importancia de variables y territorios que entrarían en tensión. |
| **Datos y método** | Cálculo, limitaciones, informe de calidad, municipios corregidos en la normalización, fuentes y descarga del panel en CSV. |

Paleta accesible para daltonismo (Okabe-Ito) en orden fijo, escala secuencial de un solo tono para
magnitudes y divergente para el diferencial, un único eje Y por gráfico y tablas detrás de los gráficos.

## Estructura del repositorio

```
.
├── src/                 Pipeline por etapas
│   ├── config.py        Rutas, fuentes, supuestos y umbrales (todo lo decidible, en un sitio)
│   ├── descargas.py     Cliente del INE y descargas con caché y manifiesto
│   ├── ingesta.py       Lectura de cada fuente a formato largo
│   ├── normalizacion.py Nombres → códigos INE
│   ├── validacion.py    Reglas de calidad e informe
│   ├── indicadores.py   Esfuerzo y criterios del art. 18.3
│   ├── modelo.py        Variables, etiquetas, validación temporal y selección
│   └── pipeline.py      Orquestación y publicación
├── app/                 Cuadro de mando en Dash (app.py, datos.py, graficos.py, assets/)
├── tests/               Pruebas de normalización, indicadores y validación (pytest)
├── notebooks/           Exploración y selección de modelo (ejecutado)
├── data/publicado/      Artefactos que lee la app (versionados para desplegar sin red)
├── data/raw, interim/   Descargas y tablas intermedias (no versionadas)
├── render.yaml          Despliegue en Render
└── requirements.txt     Dependencias con versión fijada
```

## Puesta en marcha

```bash
git clone https://github.com/angelcuadrado/davd-26-27-cuadrado-angel.git
cd davd-26-27-cuadrado-angel

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

python -m src.pipeline           # descarga (≈4 min la primera vez), normaliza, valida y entrena
python -m pytest                 # pruebas (también en GitHub Actions en cada push)
python app/app.py                # http://127.0.0.1:8050/
```

`python -m src.pipeline --refrescar` vuelve a descargar todas las fuentes; sin esa opción usa la caché.
La app funciona sin ejecutar el pipeline, porque `data/publicado/` ya viene en el repositorio.

## Despliegue

Render, plan gratuito, con el `render.yaml` del repositorio: *New → Blueprint* y elegir este repositorio.
La app arranca con `gunicorn app.app:server --workers 1 --threads 4` y lee `data/publicado/`, así que
no necesita red ni reentrenar. Con los 0,1 CPU del plan gratuito, cada pestaña se calcula solo cuando
está a la vista, los resultados se guardan en memoria y las respuestas van comprimidas.

**Aplicación desplegada: <https://esfuerzo-vivienda.onrender.com/>**

Plan gratuito de Render: si nadie la visita en un rato se duerme, y la primera carga tarda unos 50 segundos.

## Plan de trabajo

| Fase | Contenido | Estado |
| --- | --- | --- |
| 0 | Propuesta y repositorio | Hecho (5 oct.) |
| 1 | Ingesta desde la API del INE y el Ministerio, normalización de códigos territoriales | Hecho |
| 2 | Validación, informe de calidad y cálculo del índice de esfuerzo | Hecho |
| 3 | Cuadro de mando con mapa, series, rankings y calculadora | Hecho |
| 4 | Modelo de clasificación, validación temporal e integración en la app | Hecho |
| 5 | Despliegue en Render, documentación y preparación de la exposición | Desplegada; exposición en preparación |

**Siguientes pasos**: precios de oferta de alquiler (no solo contratos en vigor) para medir el esfuerzo
de quien entra ahora en el mercado, y actualización automática trimestral.

## Licencia y atribución

Código bajo licencia MIT.

Los datos proceden del **Instituto Nacional de Estadística** y del **Ministerio de Vivienda y Agenda
Urbana**. Este proyecto no está asociado a ninguno de los dos organismos; se limita a reutilizar sus
datos públicos citando la fuente.
