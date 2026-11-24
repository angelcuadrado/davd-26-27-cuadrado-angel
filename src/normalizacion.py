"""Etapa 2 · Normalización: un único código INE para cada territorio en todas las fuentes.

El INE identifica provincias (2 dígitos) y municipios (5 dígitos) por código. El Ministerio de
Vivienda solo da nombres, y además con su propia grafía: «Coruña (A)» frente a «Coruña, A»,
«Balears (Illes)» frente a «Balears, Illes», «Almuñecar» sin tilde... Aquí se traducen esos
nombres a códigos INE, y se deja constancia de cada emparejamiento y de cada nombre sin pareja.
"""
import difflib
import re
import unicodedata

import pandas as pd

# Comunidades uniprovinciales: el Ministerio solo publica la fila de la comunidad
ALIAS_PROVINCIAS = {
    "asturias principado de": "33",
    "cantabria": "39",
    "madrid comunidad de": "28",
    "murcia region de": "30",
    "navarra comunidad foral de": "31",
    "navarra com foral de": "31",
    "rioja la": "26",
    "tenerife": "38",                   # a veces la fila dice solo «Tenerife»
}
# Municipios cuyo nombre en el Ministerio no se parece lo bastante al oficial del INE
ALIAS_MUNICIPIOS = {
    "mahon": "mao",
    "palma de mallorca": "palma",
    "santa eulalia del rio": "santa eularia des riu",
    "san cristobal laguna": "san cristobal de la laguna",
    "santa cruz detenerife": "santa cruz de tenerife",
    "vitoria": "vitoria gasteiz",
}
ARTICULOS = {"el", "la", "los", "las", "l", "a", "o", "os", "as", "es", "els", "les", "sa", "ses"}


def clave(nombre: str) -> str:
    """Forma canónica de un nombre: sin tildes, minúsculas, sin puntuación y artículo delante.

    «Ejido (El)», «Ejido, El» y «El Ejido» dan todos «el ejido».
    """
    texto = unicodedata.normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode().lower().strip()
    texto = re.sub(r"\s+", " ", texto)
    articulo = re.match(r"^(.*?)\s*(?:\(([^)]+)\)|,\s*([^,]+))$", texto)    # «X (El)» o «X, El»
    if articulo:
        base, entre_parentesis, tras_coma = articulo.groups()
        sufijo = (entre_parentesis or tras_coma or "").strip()
        if sufijo.replace("'", "") in ARTICULOS:
            texto = f"{sufijo} {base}"
        else:
            texto = f"{base} {sufijo}"
    texto = re.sub(r"[^a-z0-9 ]", " ", texto.replace("l'", "l "))
    return re.sub(r"\s+", " ", texto).strip()


def claves_alternativas(nombre: str) -> set[str]:
    """Todas las formas con las que puede aparecer un nombre: bilingües («Alicante/Alacant»),
    con y sin artículo."""
    claves = set()
    for parte in [nombre, *re.split(r"\s*/\s*", str(nombre))]:
        k = clave(parte)
        if not k:
            continue
        claves.add(k)
        invertido = re.match(r"^(.*?)\s*(?:\(([^)]+)\)|,\s*([^,]+))$", str(parte).strip())
        if invertido:                                           # «Balears, Illes» -> «illes balears»
            base, a, b = invertido.groups()
            claves.add(clave(f"{a or b} {base}"))
        palabras = k.split()
        if len(palabras) > 1 and palabras[0] in ARTICULOS:
            claves.add(" ".join(palabras[1:]))                  # «el ejido» -> «ejido»
    return claves


# Comunidad autónoma (código INE) de cada provincia: la EPF solo se publica por comunidad
CCAA_DE_PROVINCIA = {
    **dict.fromkeys(["04", "11", "14", "18", "21", "23", "29", "41"], "01"),   # Andalucía
    **dict.fromkeys(["22", "44", "50"], "02"),                                 # Aragón
    "33": "03", "07": "04",                                                    # Asturias, Baleares
    **dict.fromkeys(["35", "38"], "05"), "39": "06",                           # Canarias, Cantabria
    **dict.fromkeys(["05", "09", "24", "34", "37", "40", "42", "47", "49"], "07"),   # Castilla y León
    **dict.fromkeys(["02", "13", "16", "19", "45"], "08"),                     # Castilla-La Mancha
    **dict.fromkeys(["08", "17", "25", "43"], "09"),                           # Cataluña
    **dict.fromkeys(["03", "12", "46"], "10"),                                 # Comunitat Valenciana
    **dict.fromkeys(["06", "10"], "11"),                                       # Extremadura
    **dict.fromkeys(["15", "27", "32", "36"], "12"),                           # Galicia
    "28": "13", "30": "14", "31": "15",                                        # Madrid, Murcia, Navarra
    **dict.fromkeys(["01", "20", "48"], "16"),                                 # País Vasco
    "26": "17", "51": "18", "52": "19",                                        # La Rioja, Ceuta, Melilla
}


def catalogo(renta: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Provincias y municipios con su código y nombre oficial, a partir del Atlas de renta."""
    provincias = (renta[renta["nivel"] == "provincia"]
                  .drop_duplicates("codigo")[["codigo", "territorio"]]
                  .rename(columns={"codigo": "cod_prov", "territorio": "provincia"})
                  .sort_values("cod_prov").reset_index(drop=True))
    municipios = (renta[renta["nivel"] == "municipio"]
                  .drop_duplicates("codigo")[["codigo", "territorio"]]
                  .rename(columns={"codigo": "cod_mun", "territorio": "municipio"}))
    municipios["cod_prov"] = municipios["cod_mun"].str[:2]
    provincias["cod_ccaa"] = provincias["cod_prov"].map(CCAA_DE_PROVINCIA)
    return provincias, municipios.sort_values("cod_mun").reset_index(drop=True)


def codificar_provincias(nombres: pd.Series, provincias: pd.DataFrame) -> pd.DataFrame:
    """Asigna código de provincia a cada nombre de la fuente. Devuelve nombre, cod_prov y método."""
    indice = {}
    for fila in provincias.itertuples():
        for k in claves_alternativas(fila.provincia):
            indice[k] = fila.cod_prov
    resultado = []
    for nombre in nombres.drop_duplicates():
        k = clave(nombre)
        if k in ALIAS_PROVINCIAS:
            resultado.append((nombre, ALIAS_PROVINCIAS[k], "alias"))
            continue
        codigo = next((indice[c] for c in claves_alternativas(nombre) if c in indice), None)
        metodo = "nombre" if codigo else "sin_pareja"
        if codigo is None and len(k) >= 5:                      # erratas: «Córdaba», «Valladodid»
            parecido = difflib.get_close_matches(k, list(indice), n=1, cutoff=0.85)
            if parecido:
                codigo, metodo = indice[parecido[0]], "parecido"
        resultado.append((nombre, codigo, metodo))
    return pd.DataFrame(resultado, columns=["nombre_fuente", "cod_prov", "metodo"])


def codificar_municipios(fuente: pd.DataFrame, municipios: pd.DataFrame,
                         provincias: pd.DataFrame) -> pd.DataFrame:
    """Asigna código INE a cada (provincia, municipio) del Ministerio.

    Orden de búsqueda: 1) nombre exacto dentro de la provincia indicada; 2) nombre exacto en
    toda España si solo hay un municipio con ese nombre (corrige filas mal asignadas de
    provincia); 3) parecido ≥ 0,88 dentro de la provincia (erratas y tildes que faltan).
    """
    cod_provincia = codificar_provincias(fuente["provincia_fuente"], provincias)
    cod_provincia = dict(zip(cod_provincia["nombre_fuente"], cod_provincia["cod_prov"], strict=True))

    por_provincia, nacional = {}, {}
    for fila in municipios.itertuples():
        for k in claves_alternativas(fila.municipio):
            por_provincia.setdefault((fila.cod_prov, k), fila.cod_mun)
            nacional.setdefault(k, set()).add(fila.cod_mun)

    resultado = []
    pares = fuente[["provincia_fuente", "municipio_fuente"]].drop_duplicates()
    for provincia, municipio in pares.itertuples(index=False):
        prov = cod_provincia.get(provincia)
        claves_mun = claves_alternativas(municipio)
        claves_mun |= {ALIAS_MUNICIPIOS[k] for k in claves_mun if k in ALIAS_MUNICIPIOS}
        codigo, metodo = None, "sin_pareja"
        for k in claves_mun:
            if (prov, k) in por_provincia:
                codigo, metodo = por_provincia[(prov, k)], "nombre"
                break
        if codigo is None:
            candidatos = set().union(*(nacional.get(k, set()) for k in claves_mun))
            if len(candidatos) == 1:
                codigo, metodo = candidatos.pop(), "nombre_otra_provincia"
        if codigo is None and prov:
            opciones = {k: c for (p, k), c in por_provincia.items() if p == prov}
            parecido = difflib.get_close_matches(clave(municipio), list(opciones), n=1, cutoff=0.88)
            if parecido:
                codigo, metodo = opciones[parecido[0]], "parecido"
        resultado.append((provincia, municipio, prov, codigo, metodo))
    return pd.DataFrame(resultado, columns=["provincia_fuente", "municipio_fuente",
                                            "cod_prov_fuente", "cod_mun", "metodo"])


def _nivel(df: pd.DataFrame, nivel: str, columna: str) -> pd.DataFrame:
    """Filas de un nivel territorial («provincia» o «municipio») con el código renombrado a cod_prov/cod_mun."""
    clave = "cod_prov" if nivel == "provincia" else "cod_mun"
    return df[df["nivel"] == nivel].rename(columns={"codigo": clave})[[clave, "anio", columna]]


def normalizar(tablas: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], dict]:
    """Devuelve las tablas con códigos INE y un informe de los emparejamientos."""
    provincias, municipios = catalogo(tablas["renta"])

    # Precios provinciales: se quedan solo las filas que son provincias (no CCAA ni total)
    mapa_prov = codificar_provincias(tablas["precios_provincias"]["territorio_fuente"], provincias)
    precios_prov = tablas["precios_provincias"].merge(
        mapa_prov, left_on="territorio_fuente", right_on="nombre_fuente", how="left")
    precios_prov = (precios_prov.dropna(subset=["cod_prov"])
                    [["cod_prov", "trimestre", "precio_m2"]]
                    .drop_duplicates(["cod_prov", "trimestre"]))

    # Precios municipales
    mapa_mun = codificar_municipios(tablas["precios_municipios"], municipios, provincias)
    precios_mun = tablas["precios_municipios"].merge(
        mapa_mun[["provincia_fuente", "municipio_fuente", "cod_mun"]],
        on=["provincia_fuente", "municipio_fuente"], how="left")
    precios_mun = (precios_mun.dropna(subset=["cod_mun"])
                   [["cod_mun", "trimestre", "precio_m2", "tasaciones"]]
                   .groupby(["cod_mun", "trimestre"], as_index=False).first())
    precios_mun["cod_prov"] = precios_mun["cod_mun"].str[:2]

    renta = tablas["renta"]
    poblacion = tablas["poblacion"]
    serpavi = tablas["alquiler_serpavi"]
    salida = {
        "provincias": provincias,
        "municipios": municipios,
        "precios_prov": precios_prov,
        "precios_mun": precios_mun,
        "renta_prov": _nivel(renta, "provincia", "renta_hogar"),
        "renta_mun": _nivel(renta, "municipio", "renta_hogar"),
        "poblacion_prov": _nivel(poblacion, "provincia", "poblacion"),
        "poblacion_mun": _nivel(poblacion, "municipio", "poblacion"),
        "ipc": tablas["ipc"], "alquiler": tablas["alquiler"], "gastos_vivienda": tablas["gastos_vivienda"],
        "alquiler_prov": _nivel(serpavi, "provincia", "alquiler_mes"),
        "alquiler_mun": _nivel(serpavi, "municipio", "alquiler_mes"),
        "compraventas": tablas["compraventas"], "tipo_interes": tablas["tipo_interes"],
    }

    sin_pareja_prov = mapa_prov[(mapa_prov["metodo"] == "sin_pareja")]["nombre_fuente"].tolist()
    informe = {
        "provincias_fuente_ministerio": int(len(mapa_prov)),
        "provincias_emparejadas": int(mapa_prov["cod_prov"].notna().sum()),
        "provincias_cubiertas": int(precios_prov["cod_prov"].nunique()),
        "filas_ministerio_no_provinciales": sin_pareja_prov,       # CCAA y total nacional
        "municipios_fuente_ministerio": int(mapa_mun[["municipio_fuente"]].drop_duplicates().shape[0]),
        "municipios_emparejados": int(mapa_mun["cod_mun"].nunique()),
        "metodos_municipios": mapa_mun.groupby("metodo")["municipio_fuente"].nunique().to_dict(),
        "municipios_en_otra_provincia": mapa_mun[mapa_mun["metodo"] == "nombre_otra_provincia"]
            [["provincia_fuente", "municipio_fuente", "cod_mun"]].drop_duplicates().to_dict("records"),
        "municipios_por_parecido": mapa_mun[mapa_mun["metodo"] == "parecido"]
            [["municipio_fuente", "cod_mun"]].drop_duplicates().to_dict("records"),
        "municipios_sin_pareja": mapa_mun[mapa_mun["cod_mun"].isna()]
            [["provincia_fuente", "municipio_fuente"]].drop_duplicates().to_dict("records"),
    }
    return salida, informe
