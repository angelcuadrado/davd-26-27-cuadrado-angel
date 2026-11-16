import numpy as np
import pandas as pd

from src.validacion import MIN_TASACIONES, validar


def test_filas_invalidas_se_apartan_con_su_motivo():
    trimestre = pd.Period("2026Q1", freq="Q")
    precios = pd.DataFrame({
        "cod_mun": ["1", "2", "3", "4", "4"],
        "trimestre": [trimestre] * 5,
        "precio_m2": [1_500.0, np.nan, 90_000.0, 1_800.0, 1_900.0],
        "tasaciones": [100, 100, 100, MIN_TASACIONES - 1, 100],
    })
    validas, rechazadas, informe = validar({"precios_mun": precios})

    assert validas["precios_mun"]["cod_mun"].tolist() == ["1"]
    motivos = dict(zip(rechazadas["cod_mun"], rechazadas["motivo"]))
    assert motivos["2"] == "precio €/m² informado"
    assert motivos["3"] == "precio entre 200 y 15.000 €/m²"
    assert "tasaciones" in rechazadas.loc[rechazadas["motivo"].str.contains("tasaciones"), "motivo"].iloc[0]
    assert (rechazadas["motivo"] == "clave duplicada").sum() == 1
    assert informe["precios_mun"]["rechazadas"] == 4


def test_tablas_sin_reglas_pasan_intactas():
    catalogo = pd.DataFrame({"cod_prov": ["01"], "provincia": ["Araba/Álava"]})
    validas, rechazadas, informe = validar({"provincias": catalogo})
    assert validas["provincias"].equals(catalogo)
    assert rechazadas.empty and informe == {}
