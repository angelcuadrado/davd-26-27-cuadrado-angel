"""Etapa 4a · Índice de esfuerzo y criterios del artículo 18.3 de la Ley 12/2023.

Para cada territorio y trimestre:

- **Esfuerzo**: cuota anual de la hipoteca de una vivienda tipo (90 m² al valor tasado medio,
  financiada al 80 % a 25 años al tipo medio del trimestre) más los gastos y suministros básicos
  de la vivienda (gasto medio por hogar de la comunidad autónoma), dividido entre la renta neta
  media por hogar. Criterio 1: esfuerzo > 30 %. Se guarda también la parte de la hipoteca sola.
- **Diferencial de precios**: crecimiento acumulado del precio en los cinco años anteriores
  menos el del IPC de la provincia, en puntos. Criterio 2: diferencial > 3 puntos.

Un territorio está *tensionado* si cumple al menos uno de los dos.
"""
import numpy as np
import pandas as pd

from src import config


def cuota_mensual(capital, tipo_anual_pct, anios: int = config.PLAZO_ANIOS):
    """Cuota de un préstamo francés (cuota constante). Acepta escalares o Series."""
    i = np.asarray(tipo_anual_pct, dtype=float) / 100 / 12
    n = anios * 12
    capital = np.asarray(capital, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        cuota = np.where(i > 0, capital * i / (1 - (1 + i) ** -n), capital / n)
    return cuota


def esfuerzo(precio_m2, renta_hogar, tipo_anual_pct, superficie=config.SUPERFICIE_M2,
             financiacion=config.FINANCIACION, anios=config.PLAZO_ANIOS):
    """Cuota anual de la hipoteca / renta anual del hogar (proporción, 0,30 = 30 %)."""
    capital = np.asarray(precio_m2, dtype=float) * superficie * financiacion
    return cuota_mensual(capital, tipo_anual_pct, anios) * 12 / np.asarray(renta_hogar, dtype=float)


def renta_trimestral(renta: pd.DataFrame, clave: str, hasta: pd.Period) -> pd.DataFrame:
    """Pasa la renta anual a trimestres y estima los años que el Atlas aún no ha publicado.

    El Atlas va con unos dos años de retraso. Para los años sin dato se proyecta la última renta
    con el crecimiento anual medio de los tres últimos años del propio territorio (acotado
    entre −2 % y +6 %), y se marca la fila como estimada.
    """
    filas = []
    ultimo_anio = hasta.year
    for codigo, grupo in renta.sort_values("anio").groupby(clave):
        serie = grupo.set_index("anio")["renta_hogar"]
        ultimo = serie.index.max()
        if len(serie) >= 4:
            crecimiento = (serie.iloc[-1] / serie.iloc[-4]) ** (1 / 3) - 1
        else:
            crecimiento = 0.0
        crecimiento = float(np.clip(crecimiento, -0.02, 0.06))
        for anio in range(serie.index.min(), ultimo_anio + 1):
            estimada = anio > ultimo
            valor = serie.get(anio, serie.iloc[-1] * (1 + crecimiento) ** (anio - ultimo))
            filas.append((codigo, anio, valor, estimada))
    anual = pd.DataFrame(filas, columns=[clave, "anio", "renta_hogar", "renta_estimada"])
    trimestres = pd.DataFrame({"trimestre": pd.period_range(f"{anual['anio'].min()}Q1", hasta, freq="Q")})
    trimestres["anio"] = trimestres["trimestre"].dt.year
    return anual.merge(trimestres, on="anio")


def _ultimo_conocido(df: pd.DataFrame, clave: str, columna: str, hasta: pd.Period) -> pd.DataFrame:
    """Serie anual -> trimestral, arrastrando el último valor conocido (para población)."""
    trimestres = pd.period_range(f"{df['anio'].min()}Q1", hasta, freq="Q")
    rejilla = pd.MultiIndex.from_product([df[clave].unique(), trimestres], names=[clave, "trimestre"]).to_frame(index=False)
    rejilla["anio"] = rejilla["trimestre"].dt.year
    rejilla = rejilla.merge(df[[clave, "anio", columna]], on=[clave, "anio"], how="left")
    rejilla[columna] = rejilla.groupby(clave)[columna].ffill()
    return rejilla.drop(columns="anio")


def valor_hace(panel: pd.DataFrame, clave: str, columna: str, trimestres: int) -> pd.Series:
    """Valor de `columna` en el mismo territorio `trimestres` trimestres antes (NaN si no hay).

    Se busca por fecha, no por posición: si a un municipio le falta un trimestre, desplazar
    filas compararía con el trimestre equivocado.
    """
    serie = panel.set_index([clave, "trimestre"])[columna]
    serie = serie[~serie.index.duplicated()]
    buscado = pd.MultiIndex.from_arrays([panel[clave], panel["trimestre"] - trimestres])
    return pd.Series(serie.reindex(buscado).to_numpy(), index=panel.index)


def gastos_trimestrales(gastos: pd.DataFrame, desde: int, hasta: pd.Period) -> pd.DataFrame:
    """Gastos anuales de la vivienda por comunidad -> trimestres.

    La EPF empieza en 2016 y se publica con un año de retraso: los años sin dato toman el del
    año publicado más cercano.
    """
    trimestres = pd.period_range(f"{desde}Q1", hasta, freq="Q")
    rejilla = pd.MultiIndex.from_product([gastos["cod_ccaa"].unique(), trimestres],
                                         names=["cod_ccaa", "trimestre"]).to_frame(index=False)
    rejilla["anio"] = rejilla["trimestre"].dt.year
    rejilla = rejilla.merge(gastos, on=["cod_ccaa", "anio"], how="left")
    rejilla["gastos_vivienda"] = rejilla.groupby("cod_ccaa")["gastos_vivienda"].transform(lambda s: s.bfill().ffill())
    return rejilla.drop(columns="anio")


def criterios(panel: pd.DataFrame, clave: str) -> pd.DataFrame:
    """Añade esfuerzo, diferencial a cinco años y el estado legal a un panel."""
    panel = panel.sort_values([clave, "trimestre"]).copy()
    panel["esfuerzo_hipoteca"] = esfuerzo(panel["precio_m2"], panel["renta_hogar"], panel["tipo_interes"])
    gastos = panel["gastos_vivienda"] if "gastos_vivienda" in panel else 0.0
    panel["esfuerzo"] = panel["esfuerzo_hipoteca"] + gastos / panel["renta_hogar"]
    v = config.VENTANA_TRIMESTRES
    panel["crec_precio_5a"] = 100 * (panel["precio_m2"] / valor_hace(panel, clave, "precio_m2", v) - 1)
    panel["crec_ipc_5a"] = 100 * (panel["ipc"] / valor_hace(panel, clave, "ipc", v) - 1)
    panel["diferencial"] = panel["crec_precio_5a"] - panel["crec_ipc_5a"]
    panel["criterio_esfuerzo"] = (panel["esfuerzo"] > config.UMBRAL_ESFUERZO).where(panel["esfuerzo"].notna())
    panel["criterio_precio"] = (panel["diferencial"] > config.UMBRAL_DIFERENCIAL).where(panel["diferencial"].notna())
    ambos_conocidos = panel["criterio_esfuerzo"].notna() & panel["criterio_precio"].notna()
    panel["tensionado"] = (panel["criterio_esfuerzo"].fillna(False).astype(bool)
                           | panel["criterio_precio"].fillna(False).astype(bool)).where(ambos_conocidos)
    return panel


def panel_provincial(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Panel provincia × trimestre con precios, renta, IPC, tipo, mercado y criterios."""
    hasta = t["precios_prov"]["trimestre"].max()
    panel = t["precios_prov"].merge(t["ipc"], on=["cod_prov", "trimestre"], how="left")
    panel = panel.merge(t["tipo_interes"], on="trimestre", how="left")
    panel = panel.merge(renta_trimestral(t["renta_prov"], "cod_prov", hasta).drop(columns="anio"),
                        on=["cod_prov", "trimestre"], how="left")
    panel = panel.merge(_ultimo_conocido(t["poblacion_prov"], "cod_prov", "poblacion", hasta),
                        on=["cod_prov", "trimestre"], how="left")
    panel = panel.merge(t["compraventas"], on=["cod_prov", "trimestre"], how="left")
    alquiler = t["alquiler"].sort_values("anio").copy()
    alquiler["var_alquiler"] = 100 * alquiler.groupby("cod_prov")["indice_alquiler"].pct_change()
    panel["anio"] = panel["trimestre"].dt.year
    panel = panel.merge(alquiler[["cod_prov", "anio", "var_alquiler"]], on=["cod_prov", "anio"], how="left")
    panel = panel.drop(columns="anio").merge(t["provincias"], on="cod_prov", how="left")
    panel = panel.merge(gastos_trimestrales(t["gastos_vivienda"], 2015, hasta), on=["cod_ccaa", "trimestre"], how="left")
    return criterios(panel, "cod_prov")


def panel_municipal(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Panel municipio × trimestre (municipios de más de 25.000 habitantes)."""
    hasta = t["precios_mun"]["trimestre"].max()
    municipios = t["precios_mun"]["cod_mun"].unique()
    panel = t["precios_mun"].merge(t["ipc"], on=["cod_prov", "trimestre"], how="left")
    panel = panel.merge(t["tipo_interes"], on="trimestre", how="left")
    renta = t["renta_mun"][t["renta_mun"]["cod_mun"].isin(municipios)]
    panel = panel.merge(renta_trimestral(renta, "cod_mun", hasta).drop(columns="anio"),
                        on=["cod_mun", "trimestre"], how="left")
    poblacion = t["poblacion_mun"][t["poblacion_mun"]["cod_mun"].isin(municipios)]
    panel = panel.merge(_ultimo_conocido(poblacion, "cod_mun", "poblacion", hasta),
                        on=["cod_mun", "trimestre"], how="left")
    panel = panel.merge(t["municipios"][["cod_mun", "municipio"]], on="cod_mun", how="left")
    panel = panel.merge(t["provincias"], on="cod_prov", how="left")
    panel = panel.merge(gastos_trimestrales(t["gastos_vivienda"], 2015, hasta), on=["cod_ccaa", "trimestre"], how="left")
    return criterios(panel, "cod_mun")
