"""Etapa 1 · Ingesta: descarga cada fuente y la deja en formato largo (una fila por dato).

Cada función devuelve un DataFrame con columnas homogéneas y lo más cerca posible de la fuente:
los nombres de territorio se dejan tal cual. Unificar los códigos es trabajo de normalizacion.py.
"""
import logging
from datetime import datetime

import pandas as pd

from src import config
from src.descargas import ErrorINE, descargar_fichero, ine

log = logging.getLogger(__name__)


# --- API del INE ---------------------------------------------------------------------------

def _series_ine(tabla: int, refrescar: bool = False, **filtros) -> pd.DataFrame:
    """Descarga una tabla del INE y la pasa a formato largo con los metadatos de cada serie.

    Devuelve una fila por (serie, periodo) con: codigo_serie, nombre, fecha, anio, periodo,
    valor y una columna por cada variable de la serie (Provincias, Municipios...), con su código
    INE en la columna «<variable>_codigo».
    """
    try:
        series = ine("DATOS_TABLA", tabla, refrescar=refrescar, tip="AM", **filtros)
    except ErrorINE as e:
        # Las tablas grandes (Madrid, Barcelona...) superan el límite de volumen de la API:
        # se piden año a año y se juntan.
        log.info("Tabla %s: %s. La pido año a año.", tabla, e)
        series = {}
        for anio in range(2015, datetime.now().year + 1):
            try:
                trozo = ine("DATOS_TABLA", tabla, refrescar=refrescar, tip="AM",
                            date=f"{anio}0101:{anio}1231", **filtros)
            except ErrorINE:
                continue
            for s in trozo:
                if s["COD"] in series:
                    series[s["COD"]]["Data"].extend(s["Data"])
                else:
                    series[s["COD"]] = s
        series = list(series.values())
    filas = []
    for serie in series:
        meta = {}
        for m in serie.get("MetaData", []):
            meta[m["T3_Variable"]] = m["Nombre"]
            meta[f"{m['T3_Variable']}_codigo"] = m.get("Codigo") or ""
        for dato in serie.get("Data", []):
            filas.append({
                "codigo_serie": serie["COD"],
                "nombre": serie["Nombre"].strip(),
                "fecha": pd.to_datetime(dato["Fecha"], unit="ms", utc=True).tz_convert("Europe/Madrid").tz_localize(None),
                "anio": dato["Anyo"],
                "valor": dato["Valor"],
                **meta,
            })
    return pd.DataFrame(filas)


def _trimestral(df: pd.DataFrame, claves: list[str], agregacion: str) -> pd.DataFrame:
    """Agrega una serie mensual a trimestres, descartando los trimestres incompletos.

    Un trimestre con uno o dos meses publicados daría una media o una suma engañosa.
    """
    df = df.assign(trimestre=df["fecha"].dt.to_period("Q"))
    agrupado = df.groupby(claves + ["trimestre"])["valor"].agg([agregacion, "count"]).reset_index()
    return agrupado[agrupado["count"] == 3].drop(columns="count").rename(columns={agregacion: "valor"})


def renta_atlas(refrescar: bool = False) -> pd.DataFrame:
    """Renta neta media por hogar (Atlas de renta, INE): provincias y municipios, anual."""
    tablas = ine("TABLAS_OPERACION", config.OPERACION_ATLAS, refrescar=refrescar)
    renta = [t for t in tablas if t["Nombre"].startswith("Indicadores de renta media")]
    partes = []
    for tabla in renta:
        df = _series_ine(tabla["Id"], refrescar=refrescar, tv="482:284052")   # renta neta media por hogar
        if df.empty:
            continue
        if "Provincias" in df.columns and "Municipios" not in df.columns:
            df = df[df["Provincias"].notna() & df["Provincias_codigo"].fillna("").ne("")]
            partes.append(pd.DataFrame({"nivel": "provincia", "codigo": df["Provincias_codigo"],
                                        "territorio": df["Provincias"], "anio": df["anio"],
                                        "renta_hogar": df["valor"]}))
        elif "Municipios" in df.columns:
            df = df[df["Municipios"].notna()]
            partes.append(pd.DataFrame({"nivel": "municipio", "codigo": df["Municipios_codigo"],
                                        "territorio": df["Municipios"], "anio": df["anio"],
                                        "renta_hogar": df["valor"]}))
    return pd.concat(partes, ignore_index=True)


def poblacion_atlas(refrescar: bool = False) -> pd.DataFrame:
    """Población por provincia y municipio (indicadores demográficos del Atlas), anual."""
    tablas = ine("TABLAS_OPERACION", config.OPERACION_ATLAS, refrescar=refrescar)
    demo = [t for t in tablas if t["Nombre"].startswith("Indicadores demogr")]
    partes = []
    for tabla in demo:
        df = _series_ine(tabla["Id"], refrescar=refrescar, tv="260:17338")    # población
        if df.empty:
            continue
        for nivel, columna in (("provincia", "Provincias"), ("municipio", "Municipios")):
            if columna in df.columns:
                sub = df[df[columna].notna() & (df[f"{columna}_codigo"] != "")]
                partes.append(pd.DataFrame({"nivel": nivel, "codigo": sub[f"{columna}_codigo"],
                                            "anio": sub["anio"], "poblacion": sub["valor"]}))
    return pd.concat(partes, ignore_index=True).drop_duplicates(["nivel", "codigo", "anio"])


def ipc_provincial(refrescar: bool = False) -> pd.DataFrame:
    """IPC general por provincia, media trimestral del índice mensual."""
    df = _series_ine(config.TABLA_IPC_PROVINCIAL, refrescar=refrescar, tv=["762:304092", "3:83"])
    df = df[df["Provincias"].notna()]
    return (_trimestral(df, ["Provincias_codigo"], "mean")
            .rename(columns={"Provincias_codigo": "cod_prov", "valor": "ipc"}))


def ipva_provincial(refrescar: bool = False) -> pd.DataFrame:
    """Índice de precios de la vivienda en alquiler por provincia (anual)."""
    df = _series_ine(config.TABLA_IPVA_PROVINCIAL, refrescar=refrescar)
    df = df[df["Provincias"].notna() & (df["Tipo de dato"] == "Índice")]
    if "Tipo de vivienda" in df:
        df = df[df["Tipo de vivienda"].isna()]              # la serie «Total» no lleva tipo
    return (df.groupby(["Provincias_codigo", "anio"], as_index=False)["valor"].mean()
              .rename(columns={"Provincias_codigo": "cod_prov", "valor": "indice_alquiler"}))


def compraventas_provincial(refrescar: bool = False) -> pd.DataFrame:
    """Compraventas de viviendas (todas) por provincia, suma trimestral."""
    df = _series_ine(config.TABLA_COMPRAVENTAS, refrescar=refrescar, tv="345:16463")   # «General»
    df = df[df["Provincias"].notna()]
    if "Régimen de la vivienda" in df:
        df = df[df["Régimen de la vivienda"].isna()]
    return (_trimestral(df, ["Provincias_codigo"], "sum")
            .rename(columns={"Provincias_codigo": "cod_prov", "valor": "compraventas"}))


def gastos_vivienda(refrescar: bool = False) -> pd.DataFrame:
    """Gasto medio anual por hogar en suministros y gastos de la vivienda, por comunidad autónoma.

    Suma las clases de la Encuesta de Presupuestos Familiares listadas en config: agua, basuras,
    electricidad, gas, otros combustibles, gastos de comunidad y seguro del hogar.
    """
    df = _series_ine(config.TABLA_GASTOS_HOGAR, refrescar=refrescar, tv="57:8858")   # gasto medio por hogar
    df = df[df["Comunidades y Ciudades Autónomas"].notna() & df["Clases COICOP/EPF"].isin(config.CLASES_GASTOS_VIVIENDA)]
    encontradas = set(df["Clases COICOP/EPF"])
    faltan = set(config.CLASES_GASTOS_VIVIENDA) - encontradas
    if faltan:
        log.warning("Clases de gasto que no aparecen en la EPF: %s", sorted(faltan))
    return (df.groupby(["Comunidades y Ciudades Autónomas_codigo", "anio"], as_index=False)["valor"].sum()
              .rename(columns={"Comunidades y Ciudades Autónomas_codigo": "cod_ccaa", "valor": "gastos_vivienda"}))


def tipo_interes(refrescar: bool = False) -> pd.DataFrame:
    """Tipo de interés medio de las hipotecas sobre viviendas (nacional), media trimestral."""
    partes = []
    for tabla in config.TABLAS_TIPO_INTERES:
        df = _series_ine(tabla, refrescar=refrescar)
        df = df[(df["Naturaleza de la finca"] == "Viviendas") & (df["Tipo de interés"] == "Total")]
        partes.append(df[["fecha", "valor"]])
    df = pd.concat(partes).drop_duplicates("fecha", keep="last").sort_values("fecha")
    return _trimestral(df, [], "mean").rename(columns={"valor": "tipo_interes"})


# --- Ministerio de Vivienda (MIVAU) --------------------------------------------------------

def _trimestre_de_cabecera(anio, trimestre_txt) -> pd.Period | None:
    try:
        return pd.Period(year=int(str(anio).replace("Año", "").strip()),
                         quarter=int(str(trimestre_txt).strip()[0]), freq="Q")
    except (ValueError, TypeError):
        return None


def precios_provincias(refrescar: bool = False) -> pd.DataFrame:
    """Valor tasado medio de la vivienda libre (€/m²) por provincia y CCAA, trimestral desde 1995.

    Cada hoja del Excel trae cuatro años en columnas: una fila de cabecera con «Año XXXX» y
    otra con el trimestre (1º, 2º...). Se recorre cada hoja reconstruyendo el trimestre de cada
    columna.
    """
    fichero = descargar_fichero(config.MIVAU_PROVINCIAS, "mivau/valor_tasado_provincias.xls", refrescar)
    filas = []
    for _, hoja in pd.read_excel(fichero, sheet_name=None, header=None).items():
        es_cabecera = hoja.apply(lambda f: f.astype(str).str.match(r"^Año \d{4}").any(), axis=1)
        fila_anio = hoja.index[es_cabecera][0]
        fila_trim = fila_anio + 2
        columnas, anio = {}, None
        for c in hoja.columns[2:]:
            if str(hoja.at[fila_anio, c]).startswith("Año"):
                anio = hoja.at[fila_anio, c]
            periodo = _trimestre_de_cabecera(anio, hoja.at[fila_trim, c]) if anio else None
            if periodo is not None:
                columnas[c] = periodo
        for i in range(fila_trim + 1, len(hoja)):
            nombre = hoja.at[i, 1]
            if not isinstance(nombre, str) or nombre.startswith("n.r"):
                continue
            # Las provincias vienen sangradas con espacios a la derecha; las CCAA no
            for c, periodo in columnas.items():
                filas.append({"territorio_fuente": nombre, "trimestre": periodo,
                              "precio_m2": pd.to_numeric(hoja.at[i, c], errors="coerce")})
    return pd.DataFrame(filas)


def precios_municipios(refrescar: bool = False) -> pd.DataFrame:
    """Valor tasado medio (€/m²) y número de tasaciones de los municipios de más de 25.000 hab.

    Una hoja por trimestre (desde 2005). La provincia solo aparece en el primer municipio de
    cada bloque, así que se rellena hacia abajo; normalizacion.py comprueba después que cada
    municipio pertenece de verdad a esa provincia.
    """
    fichero = descargar_fichero(config.MIVAU_MUNICIPIOS, "mivau/valor_tasado_municipios.xls", refrescar)
    filas = []
    for nombre_hoja, hoja in pd.read_excel(fichero, sheet_name=None, header=None).items():
        etiqueta = nombre_hoja.strip().upper()                   # «T2A2026»
        try:
            periodo = pd.Period(year=int(etiqueta[3:7]), quarter=int(etiqueta[1]), freq="Q")
        except ValueError:
            log.warning("Hoja sin trimestre reconocible: %r", nombre_hoja)
            continue
        cabecera = hoja.index[hoja.apply(lambda f: f.astype(str).str.strip().eq("Municipio").any(), axis=1)]
        if len(cabecera) == 0:
            continue
        cabecera = cabecera[0]
        col_mun = hoja.columns[hoja.loc[cabecera].astype(str).str.strip().eq("Municipio")][0]
        col_prov = col_mun - 1
        totales = [c for c in hoja.columns if c > col_mun
                   and any(str(hoja.at[f, c]).strip() == "Total" for f in range(cabecera, cabecera + 3))]
        if len(totales) < 2:
            log.warning("Hoja %s: no encuentro las columnas «Total»", nombre_hoja)
            continue
        col_precio, col_tasaciones = totales[0], totales[1]
        provincia = None
        for i in range(cabecera + 1, len(hoja)):
            if isinstance(hoja.at[i, col_prov], str) and hoja.at[i, col_prov].strip():
                provincia = hoja.at[i, col_prov].strip()
            municipio = hoja.at[i, col_mun]
            if not isinstance(municipio, str) or not municipio.strip() or provincia is None:
                continue
            filas.append({"provincia_fuente": provincia, "municipio_fuente": municipio.strip(),
                          "trimestre": periodo,
                          "precio_m2": pd.to_numeric(hoja.at[i, col_precio], errors="coerce"),
                          "tasaciones": pd.to_numeric(hoja.at[i, col_tasaciones], errors="coerce")})
    return pd.DataFrame(filas)


def geojson_provincias(refrescar: bool = False):
    return descargar_fichero(config.GEOJSON_PROVINCIAS, "geo/provincias.geojson", refrescar)


def ingerir_todo(refrescar: bool = False) -> dict[str, pd.DataFrame]:
    """Descarga todas las fuentes y guarda cada tabla en data/interim/ingesta_<nombre>.parquet."""
    config.INTERIM.mkdir(parents=True, exist_ok=True)
    fuentes = {
        "renta": renta_atlas, "poblacion": poblacion_atlas, "ipc": ipc_provincial,
        "alquiler": ipva_provincial, "compraventas": compraventas_provincial,
        "tipo_interes": tipo_interes, "gastos_vivienda": gastos_vivienda,
        "precios_provincias": precios_provincias,
        "precios_municipios": precios_municipios,
    }
    tablas = {}
    for nombre, funcion in fuentes.items():
        inicio = datetime.now()
        tablas[nombre] = funcion(refrescar)
        log.info("Ingesta %-18s %7d filas (%.1f s)", nombre, len(tablas[nombre]),
                 (datetime.now() - inicio).total_seconds())
    geojson_provincias(refrescar)
    return tablas
