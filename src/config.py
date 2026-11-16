"""Rutas, fuentes y parámetros del proyecto.

Todo lo que es una decisión (umbral, supuesto de cálculo, identificador de tabla) vive aquí,
para que se pueda revisar y cambiar en un único sitio.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
RAW = DATA / "raw"                 # descargas tal cual, con su manifiesto (no versionado)
INTERIM = DATA / "interim"         # tablas limpias y normalizadas (no versionado)
PUBLICADO = DATA / "publicado"     # lo que consume la app: versionado para desplegar sin red

# --- Fuentes -------------------------------------------------------------------------------
INE_API = "https://servicios.ine.es/wstempus/js/ES"
MIVAU_BOLETIN = "https://apps.fomento.gob.es/BoletinOnline2/sedal"
MIVAU_PROVINCIAS = f"{MIVAU_BOLETIN}/35101000.XLS"     # valor tasado €/m², provincias, trimestral
MIVAU_MUNICIPIOS = f"{MIVAU_BOLETIN}/35103500.XLS"     # valor tasado €/m², municipios > 25.000 hab.
GEOJSON_PROVINCIAS = ("https://raw.githubusercontent.com/codeforgermany/click_that_hood/"
                      "main/public/data/spain-provinces.geojson")

# Tablas del INE (identificadores de la API JSON, consultados con TABLAS_OPERACION)
TABLA_IPC_PROVINCIAL = 76141       # IPC mensual: índices provinciales, general y grupos
TABLA_IPVA_PROVINCIAL = 59058      # Índice de precios de vivienda en alquiler, provincias (anual)
TABLA_COMPRAVENTAS = 6150          # ETDP: compraventa de viviendas por provincias (mensual)
TABLAS_TIPO_INTERES = [24460, 24457]   # Hipotecas: tipo de interés medio al inicio (mensual)
OPERACION_ATLAS = "ADRH"           # Atlas de distribución de renta de los hogares

# --- Supuestos del cálculo del esfuerzo ----------------------------------------------------
SUPERFICIE_M2 = 90                 # vivienda tipo
FINANCIACION = 0.80                # préstamo sobre el valor de tasación (LTV)
PLAZO_ANIOS = 25

# --- Criterios del art. 18.3 de la Ley 12/2023 --------------------------------------------
UMBRAL_ESFUERZO = 0.30             # carga de la vivienda sobre la renta media del hogar
UMBRAL_DIFERENCIAL = 3.0           # puntos de crecimiento del precio por encima del IPC
VENTANA_TRIMESTRES = 20            # "los cinco años anteriores"

# --- Modelo --------------------------------------------------------------------------------
HORIZONTE_TRIMESTRES = 8           # predecimos a dos años vista
ANIO_CORTE_TEST = 2021             # entrenar con t < 2021, evaluar con t >= 2021
SEMILLA = 42

# --- Paleta (accesible para daltonismo; mismo orden siempre) ------------------------------
CATEGORICA = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9"]
SECUENCIAL = ["#deebf7", "#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"]
TINTA = "#3d3d3a"
