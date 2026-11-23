import numpy as np
import pandas as pd
import pytest

from src.indicadores import criterios, cuota_mensual, esfuerzo, renta_trimestral


def test_cuota_mensual_coincide_con_la_formula_francesa():
    # 100.000 € al 3 % a 25 años: 474,21 € al mes (cualquier simulador bancario)
    assert cuota_mensual(100_000, 3.0, 25) == pytest.approx(474.21, abs=0.01)


def test_cuota_sin_interes_es_capital_entre_meses():
    assert cuota_mensual(120_000, 0.0, 10) == pytest.approx(1_000)


def test_esfuerzo_es_cuota_anual_entre_renta():
    # 2.000 €/m² · 90 m² · 80 % = 144.000 € de préstamo
    esperado = cuota_mensual(144_000, 3.0, 25) * 12 / 40_000
    assert esfuerzo(2_000, 40_000, 3.0) == pytest.approx(esperado)


def _panel(precios, ipc, renta=30_000, tipo=3.0):
    trimestres = pd.period_range("2015Q1", periods=len(precios), freq="Q")
    return pd.DataFrame({"cod": "01", "trimestre": trimestres, "precio_m2": precios, "ipc": ipc,
                         "renta_hogar": renta, "tipo_interes": tipo})


def test_criterio_de_precios_compara_cinco_anios_con_el_ipc():
    n = 21
    precios = np.linspace(1_000, 1_200, n)        # +20 % en cinco años
    ipc = np.linspace(100, 110, n)                # +10 %
    p = criterios(_panel(precios, ipc), "cod")
    ultimo = p.iloc[-1]
    assert ultimo["crec_precio_5a"] == pytest.approx(20)
    assert ultimo["diferencial"] == pytest.approx(10)
    assert bool(ultimo["criterio_precio"]) and bool(ultimo["tensionado"])
    assert p["diferencial"].iloc[:-1].isna().all()     # sin cinco años de historia no hay dato


def test_no_tensionado_si_no_cumple_ninguno():
    n = 21
    p = criterios(_panel(np.full(n, 1_000.0), np.linspace(100, 110, n)), "cod")
    ultimo = p.iloc[-1]
    assert not ultimo["criterio_esfuerzo"] and not ultimo["criterio_precio"]
    assert not ultimo["tensionado"]


def test_hueco_en_la_serie_no_se_confunde_con_cinco_anios():
    p = _panel(np.linspace(1_000, 1_500, 22), np.linspace(100, 110, 22)).drop(index=1)   # falta 2015 T2
    p = criterios(p, "cod").set_index("trimestre")
    # 2020 T1 se compara con 2015 T1 (existe); 2020 T2 necesitaría 2015 T2, que falta
    assert p.loc[pd.Period("2020Q1", freq="Q"), "diferencial"] == pytest.approx(
        100 * (p.loc[pd.Period("2020Q1", freq="Q"), "precio_m2"] / 1_000 - 1) - 100 * (p.loc[pd.Period("2020Q1", freq="Q"), "ipc"] / 100 - 1))
    assert np.isnan(p.loc[pd.Period("2020Q2", freq="Q"), "diferencial"])


def test_renta_se_estima_tras_el_ultimo_anio_publicado():
    renta = pd.DataFrame({"cod": "01", "anio": [2020, 2021, 2022, 2023], "renta_hogar": [100.0, 102.0, 104.0, 106.0]})
    r = renta_trimestral(renta, "cod", pd.Period("2025Q4", freq="Q"))
    assert not r.loc[r["anio"] == 2023, "renta_estimada"].any()
    assert r.loc[r["anio"] == 2025, "renta_estimada"].all()
    crecimiento = (106 / 100) ** (1 / 3) - 1
    assert r.loc[r["anio"] == 2025, "renta_hogar"].iloc[0] == pytest.approx(106 * (1 + crecimiento) ** 2)


def test_gastos_de_la_vivienda_se_suman_al_esfuerzo():
    n = 21
    sin_gastos = criterios(_panel(np.full(n, 1_500.0), np.linspace(100, 110, n)), "cod").iloc[-1]
    con_gastos = criterios(_panel(np.full(n, 1_500.0), np.linspace(100, 110, n)).assign(gastos_vivienda=3_000.0),
                           "cod").iloc[-1]
    assert con_gastos["esfuerzo_hipoteca"] == pytest.approx(sin_gastos["esfuerzo"])
    assert con_gastos["esfuerzo"] == pytest.approx(sin_gastos["esfuerzo"] + 3_000 / 30_000)    # +10 puntos


def test_criterio_de_esfuerzo_vale_con_hipoteca_o_con_alquiler():
    n = 21
    panel = _panel(np.full(n, 1_000.0), np.linspace(100, 110, n), renta=30_000).assign(gastos_vivienda=2_000.0)
    barato = criterios(panel.assign(alquiler_mes=400.0), "cod").iloc[-1]
    caro = criterios(panel.assign(alquiler_mes=700.0), "cod").iloc[-1]
    assert barato["esfuerzo_alquiler"] == pytest.approx((12 * 400 + 2_000) / 30_000)
    assert barato["esfuerzo"] < 0.30 and not barato["criterio_esfuerzo"]
    assert caro["esfuerzo_alquiler"] > 0.30 and caro["criterio_esfuerzo"]      # la compra no llega; el alquiler sí
