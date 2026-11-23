"""Etapa 3 · Validación: reglas explícitas de calidad sobre cada tabla normalizada.

Cada regla dice qué filas son válidas. Las que no pasan se separan con su motivo (no se
borran en silencio) y todo se resume en un informe de calidad en JSON que la app enseña.
"""
from dataclasses import dataclass
from typing import Callable

import pandas as pd

MIN_TASACIONES = 20        # con menos tasaciones en un trimestre, el precio municipal es ruido


@dataclass
class Regla:
    tabla: str
    nombre: str
    valida: Callable[[pd.DataFrame], pd.Series]     # True = la fila cumple


def _entre(columna, minimo, maximo):
    return lambda df: df[columna].between(minimo, maximo)


def _no_nulo(columna):
    return lambda df: df[columna].notna()


REGLAS = [
    Regla("precios_prov", "precio €/m² informado", _no_nulo("precio_m2")),
    Regla("precios_prov", "precio entre 200 y 15.000 €/m²", _entre("precio_m2", 200, 15_000)),
    Regla("precios_mun", "precio €/m² informado", _no_nulo("precio_m2")),
    Regla("precios_mun", "precio entre 200 y 15.000 €/m²", _entre("precio_m2", 200, 15_000)),
    Regla("precios_mun", f"al menos {MIN_TASACIONES} tasaciones en el trimestre",
          lambda df: df["tasaciones"].fillna(0) >= MIN_TASACIONES),
    Regla("renta_prov", "renta informada (el INE la oculta si hay pocos hogares)", _no_nulo("renta_hogar")),
    Regla("renta_prov", "renta entre 5.000 y 250.000 €", _entre("renta_hogar", 5_000, 250_000)),
    Regla("renta_mun", "renta informada (el INE la oculta si hay pocos hogares)", _no_nulo("renta_hogar")),
    Regla("renta_mun", "renta entre 5.000 y 250.000 €", _entre("renta_hogar", 5_000, 250_000)),
    Regla("poblacion_prov", "población informada", _no_nulo("poblacion")),
    Regla("poblacion_prov", "población positiva", lambda df: df["poblacion"] > 0),
    Regla("poblacion_mun", "población informada", _no_nulo("poblacion")),
    Regla("poblacion_mun", "población positiva", lambda df: df["poblacion"] > 0),
    Regla("ipc", "índice positivo", lambda df: df["ipc"] > 0),
    Regla("alquiler", "índice positivo", lambda df: df["indice_alquiler"] > 0),
    Regla("compraventas", "número no negativo", lambda df: df["compraventas"] >= 0),
    Regla("tipo_interes", "tipo entre 0 % y 15 %", _entre("tipo_interes", 0, 15)),
    Regla("gastos_vivienda", "gasto anual entre 300 y 10.000 €", _entre("gastos_vivienda", 300, 10_000)),
    Regla("alquiler_prov", "alquiler entre 100 y 5.000 €/mes", _entre("alquiler_mes", 100, 5_000)),
    Regla("alquiler_mun", "alquiler entre 100 y 5.000 €/mes", _entre("alquiler_mes", 100, 5_000)),
]

CLAVES = {
    "precios_prov": ["cod_prov", "trimestre"], "precios_mun": ["cod_mun", "trimestre"],
    "renta_prov": ["cod_prov", "anio"], "renta_mun": ["cod_mun", "anio"],
    "poblacion_prov": ["cod_prov", "anio"], "poblacion_mun": ["cod_mun", "anio"],
    "ipc": ["cod_prov", "trimestre"], "alquiler": ["cod_prov", "anio"],
    "compraventas": ["cod_prov", "trimestre"], "tipo_interes": ["trimestre"],
    "gastos_vivienda": ["cod_ccaa", "anio"],
    "alquiler_prov": ["cod_prov", "anio"], "alquiler_mun": ["cod_mun", "anio"],
}


def _periodo(df: pd.DataFrame) -> tuple[str, str]:
    columna = "trimestre" if "trimestre" in df else "anio"
    return str(df[columna].min()), str(df[columna].max())


def _cobertura(df: pd.DataFrame, claves: list[str]) -> dict:
    """Qué parte de la rejilla territorio × periodo tiene dato."""
    if len(claves) < 2:
        return {}
    territorio, periodo = claves
    esperadas = df[territorio].nunique() * df[periodo].nunique()
    return {"territorios": int(df[territorio].nunique()),
            "periodos": int(df[periodo].nunique()),
            "cobertura_pct": round(100 * len(df) / esperadas, 1) if esperadas else 0.0}


def validar(tablas: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, dict]:
    """Aplica las reglas. Devuelve (tablas válidas, filas rechazadas con motivo, informe)."""
    validas, rechazadas, informe = {}, [], {}
    for nombre, df in tablas.items():
        if nombre not in CLAVES:
            validas[nombre] = df
            continue
        claves = CLAVES[nombre]
        motivo = pd.Series("", index=df.index)
        duplicada = df.duplicated(claves, keep="first")
        motivo[duplicada] = "clave duplicada"
        por_regla = {"clave duplicada": int(duplicada.sum())}
        for regla in (r for r in REGLAS if r.tabla == nombre):
            falla = ~regla.valida(df).fillna(False) & motivo.eq("")
            motivo[falla] = regla.nombre
            por_regla[regla.nombre] = int(falla.sum())
        ok = motivo.eq("")
        validas[nombre] = df[ok].reset_index(drop=True)
        if (~ok).any():
            malas = df[~ok].copy()
            malas.insert(0, "motivo", motivo[~ok])
            malas.insert(0, "tabla", nombre)
            rechazadas.append(malas.astype({c: "string" for c in malas.columns if c not in ("tabla", "motivo")}))
        desde, hasta = _periodo(df)
        informe[nombre] = {
            "filas": int(len(df)), "validas": int(ok.sum()), "rechazadas": int((~ok).sum()),
            "rechazadas_por_regla": {k: v for k, v in por_regla.items() if v},
            "desde": desde, "hasta": hasta,
            **_cobertura(validas[nombre], claves),
        }
    rechazadas = pd.concat(rechazadas, ignore_index=True) if rechazadas else pd.DataFrame()
    return validas, rechazadas, informe
