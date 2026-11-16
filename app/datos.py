"""Carga de los artefactos que publica el pipeline (data/publicado). La app nunca reentrena."""
import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

PUBLICADO = Path(__file__).resolve().parent.parent / "data" / "publicado"

ESTADOS = {True: "Tensionado", False: "Sin tensión"}


def _leer_json(nombre: str) -> dict:
    ruta = PUBLICADO / nombre
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def _panel(nombre: str) -> pd.DataFrame:
    df = pd.read_parquet(PUBLICADO / nombre)
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
        "pred_provincias": pd.read_parquet(PUBLICADO / "predicciones_provincias.parquet"),
        "pred_municipios": pd.read_parquet(PUBLICADO / "predicciones_municipios.parquet"),
        "prueba_provincias": pd.read_parquet(PUBLICADO / "prueba_provincias.parquet"),
        "prueba_municipios": pd.read_parquet(PUBLICADO / "prueba_municipios.parquet"),
        "modelo": _leer_json("modelo.json"),
        "calidad": _leer_json("calidad.json"),
        "geojson": _leer_json("provincias.geojson"),
    }
