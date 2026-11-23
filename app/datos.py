"""Carga de los artefactos que publica el pipeline (data/publicado). La app nunca reentrena."""
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import pandas as pd

PUBLICADO = Path(__file__).resolve().parent.parent / "data" / "publicado"

ESTADOS = {True: "Tensionado", False: "Sin tensión"}

# Nombres con los que la gente busca una provincia y que no están en el nombre oficial del INE
OTROS_NOMBRES = {
    "01": "Álava Araba", "03": "Alicante", "07": "Baleares Mallorca Menorca Ibiza", "12": "Castellón",
    "15": "La Coruña Coruña", "17": "Gerona", "20": "Guipúzcoa", "25": "Lérida", "32": "Orense",
    "33": "Oviedo", "35": "Gran Canaria", "38": "Tenerife", "39": "Santander", "46": "Valencia",
    "48": "Vizcaya Bilbao", "31": "Pamplona", "26": "Logroño",
}


def legible(nombre: str) -> str:
    """«Balears, Illes» -> «Illes Balears»; «Hospitalet de Llobregat, L'» -> «L'Hospitalet de Llobregat».

    El INE pone el artículo al final para ordenar alfabéticamente; en pantalla se lee mejor delante.
    """
    if not isinstance(nombre, str):
        return nombre
    partes = []
    for trozo in nombre.split("/"):
        m = re.match(r"^(.*?),\s*(\S+)$", trozo.strip())
        if m:
            base, articulo = m.groups()
            trozo = f"{articulo}{'' if articulo.endswith(chr(39)) else ' '}{base}"
        partes.append(trozo)
    return "/".join(partes)


def sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def opciones_busqueda(nombres: dict[str, str], otros: dict[str, str] | None = None) -> list[dict]:
    """Opciones de un desplegable que también se encuentran sin tildes y por otros nombres."""
    otros = otros or {}
    return [{"label": n, "value": c, "search": f"{n} {sin_tildes(n)} {otros.get(c, '')} {sin_tildes(otros.get(c, ''))}"}
            for c, n in sorted(nombres.items(), key=lambda x: sin_tildes(x[1]))]


def _leer_json(nombre: str) -> dict:
    ruta = PUBLICADO / nombre
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def _con_nombres_legibles(df: pd.DataFrame) -> pd.DataFrame:
    for columna in ("provincia", "municipio"):
        if columna in df:
            df[columna] = df[columna].map(legible)
    return df


def _panel(nombre: str) -> pd.DataFrame:
    df = _con_nombres_legibles(pd.read_parquet(PUBLICADO / nombre))
    df["trimestre"] = pd.PeriodIndex(df["trimestre"], freq="Q")
    df["etiqueta"] = df["trimestre"].astype(str).str.replace("Q", " T", regex=False)
    df["estado"] = df["tensionado"].map(ESTADOS)
    return df


@lru_cache(maxsize=1)
def cargar() -> dict:
    provincias = _panel("panel_provincias.parquet")
    municipios = _panel("panel_municipios.parquet")
    return {
        "provincias": provincias,
        "municipios": municipios,
        "pred_provincias": _con_nombres_legibles(pd.read_parquet(PUBLICADO / "predicciones_provincias.parquet")),
        "pred_municipios": _con_nombres_legibles(pd.read_parquet(PUBLICADO / "predicciones_municipios.parquet")),
        "prueba_provincias": pd.read_parquet(PUBLICADO / "prueba_provincias.parquet"),
        "prueba_municipios": pd.read_parquet(PUBLICADO / "prueba_municipios.parquet"),
        "modelo": _leer_json("modelo.json"),
        "calidad": _leer_json("calidad.json"),
        "geojson": _leer_json("provincias.geojson"),
    }
