"""Etapa 4b · Modelo: ¿cumplirá el territorio algún criterio de tensionamiento dentro de dos años?

- Etiqueta: el estado legal (art. 18.3) del propio territorio ocho trimestres después. Solo se
  usan etiquetas calculadas con renta publicada, nunca con renta estimada.
- Validación temporal: se entrena con trimestres anteriores a 2021 y se evalúa con los
  posteriores. Para elegir modelo dentro del entrenamiento se usa una ventana que crece año a
  año (entrenar hasta el año N-1 y validar en el año N).
- Métrica principal: recall de la clase «tensionado». Para no premiar al que avisa de todo, el
  modelo se elige por F2, que pesa el recall el doble que la precisión. El umbral de decisión
  de cada modelo también se fija en la validación temporal (el que maximiza F2), no en la prueba.
- Se compara siempre con dos referencias: la clase mayoritaria y la persistencia («dentro de dos
  años estará como hoy»), que en series con mucha inercia es la referencia difícil de batir.
"""
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (balanced_accuracy_score, confusion_matrix, f1_score, fbeta_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src import config
from src.indicadores import valor_hace

VARIABLES = {
    "esfuerzo": "Esfuerzo actual (cuota / renta)",
    "margen_esfuerzo": "Distancia al umbral del 30 % (puntos)",
    "var_esfuerzo_1a": "Cambio del esfuerzo en un año (puntos)",
    "diferencial": "Precio − IPC a cinco años (puntos)",
    "var_diferencial_1a": "Cambio del diferencial en un año (puntos)",
    "crec_precio_1a": "Crecimiento del precio en un año (%)",
    "crec_renta_1a": "Crecimiento de la renta en un año (%)",
    "tipo_interes": "Tipo de interés hipotecario (%)",
    "var_tipo_1a": "Cambio del tipo en un año (puntos)",
    "log_precio": "Nivel de precio (log €/m²)",
    "tensionado_hoy": "Tensionado hoy (0/1)",
    "compraventas_1000": "Compraventas por 1.000 habitantes (último año)",
    "var_compraventas_1a": "Crecimiento de las compraventas en un año (%)",
    "var_alquiler": "Crecimiento del alquiler en el año (%)",
}

MODELOS = {
    "Regresión logística": Pipeline([
        ("imputar", SimpleImputer(strategy="median")),
        ("escalar", StandardScaler()),
        ("modelo", LogisticRegression(C=0.5, class_weight="balanced", max_iter=5000)),
    ]),
    "Bosque aleatorio": Pipeline([
        ("imputar", SimpleImputer(strategy="median")),
        ("modelo", RandomForestClassifier(n_estimators=400, min_samples_leaf=5,
                                          class_weight="balanced_subsample",
                                          random_state=config.SEMILLA, n_jobs=-1)),
    ]),
    "Gradient boosting": Pipeline([
        ("modelo", HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300,
                                                  class_weight="balanced",
                                                  random_state=config.SEMILLA)),
    ]),
}


def variables(panel: pd.DataFrame, clave: str) -> pd.DataFrame:
    """Calcula las variables explicativas de cada territorio y trimestre (solo con el pasado)."""
    p = panel.sort_values([clave, "trimestre"]).copy()

    def hace(columna, trimestres):
        return valor_hace(p, clave, columna, trimestres)

    p["margen_esfuerzo"] = 100 * (p["esfuerzo"] - config.UMBRAL_ESFUERZO)
    p["var_esfuerzo_1a"] = 100 * (p["esfuerzo"] - hace("esfuerzo", 4))
    p["var_diferencial_1a"] = p["diferencial"] - hace("diferencial", 4)
    p["crec_precio_1a"] = 100 * (p["precio_m2"] / hace("precio_m2", 4) - 1)
    p["crec_renta_1a"] = 100 * (p["renta_hogar"] / hace("renta_hogar", 4) - 1)
    p["var_tipo_1a"] = p["tipo_interes"] - hace("tipo_interes", 4)
    p["log_precio"] = np.log(p["precio_m2"])
    p["tensionado_hoy"] = p["tensionado"].astype(float)
    if "compraventas" in p:
        p["compraventas_anual"] = sum(hace("compraventas", k) for k in range(1, 4)) + p["compraventas"]
        p["compraventas_1000"] = 1000 * p["compraventas_anual"] / p["poblacion"]
        p["var_compraventas_1a"] = 100 * (p["compraventas_anual"] / hace("compraventas_anual", 4) - 1)
    for columna in VARIABLES:
        if columna not in p:
            p[columna] = np.nan
    return p


def etiquetar(p: pd.DataFrame, clave: str) -> pd.DataFrame:
    """Añade y = tensionado dentro de HORIZONTE trimestres (si la etiqueta es fiable)."""
    h = config.HORIZONTE_TRIMESTRES
    futuro = valor_hace(p.assign(tensionado=p["tensionado"].astype(float)), clave, "tensionado", -h)
    estimada = valor_hace(p.assign(renta_estimada=p["renta_estimada"].astype(float)), clave, "renta_estimada", -h)
    p["y"] = futuro.where(estimada == 0)
    return p


def _metricas(y, prediccion, probabilidad=None) -> dict:
    tn, fp, fn, tp = confusion_matrix(y, prediccion, labels=[0, 1]).ravel()
    m = {
        "recall": recall_score(y, prediccion, zero_division=0),
        "precision": precision_score(y, prediccion, zero_division=0),
        "f1": f1_score(y, prediccion, zero_division=0),
        "f2": fbeta_score(y, prediccion, beta=2, zero_division=0),
        "exactitud_equilibrada": balanced_accuracy_score(y, prediccion),
        "matriz": {"vn": int(tn), "fp": int(fp), "fn": int(fn), "vp": int(tp)},
    }
    if probabilidad is not None and len(np.unique(y)) == 2:
        m["roc_auc"] = roc_auc_score(y, probabilidad)
    return {k: (round(float(v), 3) if isinstance(v, (float, np.floating)) else v) for k, v in m.items()}


UMBRALES = np.round(np.arange(0.05, 0.96, 0.05), 2)


def _validacion_temporal(modelo, datos: pd.DataFrame, columnas: list[str]) -> dict:
    """Ventana creciente: entrena hasta el año N-1 y predice el año N, para los tres últimos años.

    Con esas probabilidades «fuera de muestra» se elige el umbral de decisión que maximiza F2.
    Así el umbral sale del entrenamiento, nunca del periodo de prueba.
    """
    anios = sorted(datos["trimestre"].dt.year.unique())
    reales, probabilidades, persistencia = [], [], []
    for anio in anios[-3:]:
        entreno = datos[datos["trimestre"].dt.year < anio]
        valido = datos[datos["trimestre"].dt.year == anio]
        if entreno["y"].nunique() < 2 or valido.empty:
            continue
        m = clone(modelo).fit(entreno[columnas], entreno["y"])
        reales.append(valido["y"].to_numpy())
        probabilidades.append(m.predict_proba(valido[columnas])[:, 1])
        persistencia.append(valido["tensionado_hoy"].astype(int).to_numpy())
    y, prob, pers = np.concatenate(reales), np.concatenate(probabilidades), np.concatenate(persistencia)
    f2 = {u: fbeta_score(y, (prob >= u).astype(int), beta=2, zero_division=0) for u in UMBRALES}
    umbral = max(f2, key=f2.get)
    return {"umbral": float(umbral), "f2": float(f2[umbral]),
            "f2_persistencia": float(fbeta_score(y, pers, beta=2, zero_division=0))}


def _escenario(hoy: pd.Series, prediccion: pd.Series) -> np.ndarray:
    hoy = hoy.astype(bool)
    return np.select([hoy & (prediccion == 1), ~hoy & (prediccion == 1), hoy & (prediccion == 0)],
                     ["Seguirá tensionado", "Entrará en tensión", "Saldrá de la tensión"], "Seguirá sin tensión")


def entrenar(panel: pd.DataFrame, clave: str, contexto: pd.DataFrame | None = None) -> dict:
    """Entrena, compara y elige el modelo. Devuelve el modelo final, métricas y predicciones.

    `contexto` añade variables de la provincia (mercado, alquiler) a cada municipio.
    """
    datos = etiquetar(variables(panel, clave), clave)
    if contexto is not None:
        datos = datos.drop(columns=[c for c in contexto if c not in ("cod_prov", "trimestre") and c in datos])
        datos = datos.merge(contexto, on=["cod_prov", "trimestre"], how="left")
    columnas = [v for v in VARIABLES if datos[v].notna().any()]
    con_etiqueta = datos.dropna(subset=["y", "esfuerzo", "diferencial"])
    con_etiqueta = con_etiqueta.assign(y=con_etiqueta["y"].astype(int))
    corte = config.ANIO_CORTE_TEST
    entreno = con_etiqueta[con_etiqueta["trimestre"].dt.year < corte]
    prueba = con_etiqueta[con_etiqueta["trimestre"].dt.year >= corte]
    X_e, y_e = entreno[columnas], entreno["y"]
    X_p, y_p = prueba[columnas], prueba["y"]

    resultados = {
        "Referencia: clase mayoritaria": _metricas(y_p, np.full(len(y_p), int(y_e.mean() >= 0.5))),
        "Referencia: persistencia": _metricas(y_p, prueba["tensionado_hoy"].astype(int)),
    }
    ajustados, validacion = {}, {}
    for nombre, modelo in MODELOS.items():
        validacion[nombre] = _validacion_temporal(modelo, entreno, columnas)
        ajustados[nombre] = clone(modelo).fit(X_e, y_e)
        probabilidad = ajustados[nombre].predict_proba(X_p)[:, 1]
        resultados[nombre] = _metricas(y_p, (probabilidad >= validacion[nombre]["umbral"]).astype(int), probabilidad)
        resultados[nombre]["umbral"] = validacion[nombre]["umbral"]
        resultados[nombre]["f2_validacion_temporal"] = round(validacion[nombre]["f2"], 3)
    resultados["Referencia: persistencia"]["f2_validacion_temporal"] = round(
        next(iter(validacion.values()))["f2_persistencia"], 3)
    elegido = max(validacion, key=lambda n: validacion[n]["f2"])
    umbral = validacion[elegido]["umbral"]

    importancia = permutation_importance(ajustados[elegido], X_p, y_p, scoring="roc_auc",
                                         n_repeats=10, random_state=config.SEMILLA)
    importancias = (pd.DataFrame({"variable": columnas, "descripcion": [VARIABLES[c] for c in columnas],
                                  "importancia": importancia.importances_mean,
                                  "desviacion": importancia.importances_std})
                    .sort_values("importancia", ascending=False))
    coeficientes = pd.DataFrame({
        "variable": columnas, "descripcion": [VARIABLES[c] for c in columnas],
        "coeficiente": ajustados["Regresión logística"].named_steps["modelo"].coef_[0],
    }).sort_values("coeficiente", key=abs, ascending=False)

    # Modelo final: el elegido, reentrenado con todas las etiquetas disponibles y su umbral
    final = clone(MODELOS[elegido]).fit(con_etiqueta[columnas], con_etiqueta["y"])
    final.umbral_ = umbral
    final.columnas_ = columnas
    ultimo = datos["trimestre"].max()
    actual = datos[(datos["trimestre"] == ultimo) & datos["esfuerzo"].notna() & datos["diferencial"].notna()].copy()
    actual["probabilidad"] = final.predict_proba(actual[columnas])[:, 1]
    actual["prediccion"] = (actual["probabilidad"] >= umbral).astype(int)
    actual["escenario"] = _escenario(actual["tensionado"], actual["prediccion"])

    # Predicciones del periodo de prueba, para enseñar aciertos y errores en la app
    probabilidad = ajustados[elegido].predict_proba(X_p)[:, 1]
    prueba = prueba.assign(probabilidad=probabilidad, prediccion=(probabilidad >= umbral).astype(int))
    return {
        "modelo": final,
        "elegido": elegido,
        "metricas": resultados,
        "importancias": importancias,
        "coeficientes": coeficientes,
        "predicciones": actual,
        "prueba": prueba,
        "resumen": {
            "nivel": clave,
            "umbral": umbral,
            "variables": columnas,
            "trimestre_prediccion": str(ultimo),
            "horizonte": str(ultimo + config.HORIZONTE_TRIMESTRES),
            "filas_entrenamiento": int(len(entreno)),
            "filas_prueba": int(len(prueba)),
            "periodo_entrenamiento": f"{entreno['trimestre'].min()} – {entreno['trimestre'].max()}",
            "periodo_prueba": f"{prueba['trimestre'].min()} – {prueba['trimestre'].max()}",
            "positivos_entrenamiento_pct": round(100 * float(y_e.mean()), 1),
            "positivos_prueba_pct": round(100 * float(y_p.mean()), 1),
        },
    }


def contexto_provincial(panel_provincias: pd.DataFrame) -> pd.DataFrame:
    """Variables de mercado de cada provincia y trimestre, para añadirlas a sus municipios."""
    p = variables(panel_provincias, "cod_prov")
    return p[["cod_prov", "trimestre", "compraventas_1000", "var_compraventas_1a", "var_alquiler"]]
