# Mapa del esfuerzo de acceso a la vivienda en España

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

## Fuentes de datos

Todas públicas, gratuitas y oficiales.

| Fuente | Contenido | Acceso | Frecuencia |
| --- | --- | --- | --- |
| [API JSON del INE](https://www.ine.es/dyngs/DAB/index.htm?cid=1099) | Índice de Precios de Vivienda (IPV), Índice de Referencia de Arrendamientos (IRAV), transmisiones de propiedad, hipotecas | REST, sin clave | Mensual / trimestral |
| [Atlas de Distribución de Renta de los Hogares](https://www.ine.es/dyngs/INEbase/operacion.htm?c=Estadistica_C&cid=1254736177088) | Renta media y mediana por hogar, a nivel de municipio y sección censal, desde 2015 | Misma API | Anual (≈2 años de desfase) |
| [SERPAVI](https://www.mivau.gob.es/vivienda/alquila-bien-es-tu-derecho/serpavi) — Ministerio de Vivienda | Precios de referencia del alquiler por municipio | Descarga de ficheros | Anual |

El INE es la **capa viva**: se consulta en cada actualización y permite el consumo continuo de datos.
Atlas y SERPAVI son **capas de referencia** que se refrescan cuando publican nueva edición.

### Limitaciones conocidas

- El Atlas de renta publica con unos **dos años de desfase**. El esfuerzo del trimestre corriente es
  una estimación, y la aplicación lo señala explícitamente.
- **SERPAVI no ofrece API**: esa capa se actualiza manualmente por edición.
- Los códigos de municipio no son homogéneos entre fuentes. La normalización es la etapa más delicada
  del pipeline y tiene sus propias pruebas.

## Arquitectura

```
┌───────────┐   ┌───────────────┐   ┌────────────┐   ┌─────────────────┐
│  Ingesta  │ → │ Normalización │ → │ Validación │ → │ Cálculo + modelo│ → Dash
└───────────┘   └───────────────┘   └────────────┘   └─────────────────┘
  API INE         códigos INE         reglas de        índice esfuerzo
  SERPAVI         serie temporal      calidad          clasificador
```

| Etapa | Qué hace |
| --- | --- |
| **Ingesta** | Cliente de la API del INE con caché en disco, reintentos y control de versión de cada descarga |
| **Normalización** | Unifica códigos INE de provincia y municipio entre las tres fuentes y alinea series trimestrales con anuales |
| **Validación** | Reglas explícitas de tipos, rangos, nulos y cobertura. Las filas que no pasan se separan con su motivo y se publica un informe de calidad en JSON |
| **Cálculo y modelo** | Construye el índice de esfuerzo, evalúa los criterios del art. 18.3 y entrena el modelo. Artefactos serializados para que la app no reentrene al arrancar |

### Modelo

**Clasificación binaria**: dado el histórico de un territorio, ¿cumplirá alguno de los dos criterios de
tensionamiento en el horizonte de dos años?

- **Variable objetivo**: el criterio legal, calculable hacia atrás sobre toda la serie. No es una
  definición propia, lo que la hace defendible y proporciona etiquetas reales.
- **Features**: nivel y variación de renta, evolución del IPV y del IRAV, diferencial acumulado frente
  al IPC, intensidad de compraventas e hipotecas por habitante, variables territoriales.
- **Modelos**: regresión logística regularizada como referencia interpretable, frente a un ensamblado
  de árboles.
- **Validación temporal**, no aleatoria: entrenar con el pasado y evaluar con el futuro, para evitar
  fuga de información entre periodos contiguos.
- **Métrica principal: recall** sobre la clase tensionada. Dejar de avisar de un territorio que sí se
  tensiona es un error mucho más costoso que una falsa alarma.

## Estructura del repositorio

```
.
├── src/              Pipeline por etapas (ingesta, normalización, validación, modelo)
├── app/              Cuadro de mando en Dash
├── notebooks/        Exploración y selección de modelo
├── data/             Artefactos generados (no versionados)
├── requirements.txt
└── README.md
```

## Puesta en marcha

```bash
git clone https://github.com/<usuario>/davd-26-27-cuadrado-angel.git
cd davd-26-27-cuadrado-angel

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m src.pipeline           # descarga, normaliza, valida y entrena
python app/app.py                # http://127.0.0.1:8050/
```

## Plan de trabajo

| Fase | Contenido | Fecha |
| --- | --- | --- |
| 1 | Ingesta desde la API del INE y normalización de códigos territoriales | Octubre |
| 2 | Validación, informe de calidad y cálculo del índice de esfuerzo | Octubre |
| 3 | Cuadro de mando con mapa, series y rankings | Noviembre |
| 4 | Modelo de clasificación, validación temporal e integración en la app | Noviembre |
| 5 | Despliegue en Render, documentación y preparación de la exposición | Noviembre – diciembre |

## Despliegue

Aplicación desplegada en Render: _(pendiente)_

## Licencia y atribución

Código bajo licencia MIT.

Los datos proceden del **Instituto Nacional de Estadística** y del **Ministerio de Vivienda y Agenda
Urbana**. Este proyecto no está asociado a ninguno de los dos organismos; se limita a reutilizar sus
datos públicos citando la fuente.
