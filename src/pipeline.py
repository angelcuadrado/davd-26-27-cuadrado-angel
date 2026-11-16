"""Pipeline completo: ingesta → normalización → validación → indicadores → modelo → publicación.

Uso:
    python -m src.pipeline              # usa la caché de data/raw si existe
    python -m src.pipeline --refrescar  # vuelve a descargar todas las fuentes

Escribe en data/publicado/ todo lo que necesita la app, para que esta arranque sin red y sin
reentrenar: paneles, predicciones, métricas del modelo, informe de calidad y mapa.
"""
import argparse
import json
import logging
import warnings
from datetime import datetime, timezone

import joblib
import pandas as pd

from src import config
from src.descargas import MANIFIESTO
from src.indicadores import panel_municipal, panel_provincial
from src.ingesta import geojson_provincias, ingerir_todo
from src.modelo import contexto_provincial, entrenar
from src.normalizacion import normalizar
from src.validacion import validar

log = logging.getLogger("pipeline")

COLUMNAS_PANEL = ["trimestre", "precio_m2", "renta_hogar", "renta_estimada", "tipo_interes", "ipc",
                  "esfuerzo", "crec_precio_5a", "crec_ipc_5a", "diferencial",
                  "criterio_esfuerzo", "criterio_precio", "tensionado"]
CANARIAS = {"35", "38"}
DESPLAZAMIENTO_CANARIAS = (6.5, 7.0)        # grados de longitud y latitud
COLUMNAS_PREDICCION = ["probabilidad", "prediccion", "escenario", "tensionado", "esfuerzo",
                       "diferencial", "precio_m2", "renta_hogar"]


def _a_texto(df: pd.DataFrame) -> pd.DataFrame:
    """Los Period de pandas no van a parquet: se guardan como texto «2026Q2»."""
    return df.assign(**{c: df[c].astype(str) for c in df.columns if isinstance(df[c].dtype, pd.PeriodDtype)})


def _simplificar_geojson(origen, destino, decimales: int = 3, paso: int = 2) -> None:
    """Reduce el mapa de provincias (1,4 MB) para que la app cargue rápido.

    Redondea coordenadas (3 decimales ≈ 100 m) y se queda con uno de cada `paso` vértices en
    los anillos largos; los pequeños (islas, Ceuta, Melilla) se dejan enteros.
    """
    geo = json.loads(origen.read_text(encoding="utf-8"))

    def limpiar(puntos):
        limpios = []
        for x, y in puntos:
            punto = [round(x, decimales), round(y, decimales)]
            if not limpios or limpios[-1] != punto:
                limpios.append(punto)
        if limpios and limpios[0] != limpios[-1]:
            limpios.append(limpios[0])                  # un anillo GeoJSON debe cerrarse
        return limpios

    def anillo(puntos):
        simplificado = limpiar(puntos[::paso] + [puntos[-1]]) if len(puntos) > 40 else []
        if len(simplificado) >= 4:
            return simplificado
        completo = limpiar(puntos)
        return completo if len(completo) >= 4 else None  # islote que desaparece al redondear

    def poligono(anillos):
        exterior, *huecos = [anillo(a) for a in anillos]
        return [exterior, *[h for h in huecos if h]] if exterior else None

    for f in geo["features"]:
        g = f["geometry"]
        poligonos = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        if f["properties"]["cod_prov"] in CANARIAS:
            # Como en los mapas oficiales, Canarias se acerca a la península (si no, el encuadre
            # incluye 1.000 km de océano y la península sale diminuta)
            dx, dy = DESPLAZAMIENTO_CANARIAS
            poligonos = [[[[x + dx, y + dy] for x, y in a] for a in p] for p in poligonos]
        g["type"] = "MultiPolygon"
        g["coordinates"] = [p for p in (poligono(a) for a in poligonos) if p]
        f["properties"] = {"cod_prov": f["properties"]["cod_prov"], "nombre": f["properties"]["name"]}
        f["id"] = f["properties"]["cod_prov"]
    destino.write_text(json.dumps(geo, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


def _publicar_modelo(resultado: dict, nivel: str, clave: str) -> dict:
    pred = resultado["predicciones"]
    columnas = [clave] + [c for c in ("cod_prov", "municipio", "provincia") if c in pred and c != clave]
    pred = pred[columnas + COLUMNAS_PREDICCION].sort_values("probabilidad", ascending=False)
    pred.to_parquet(config.PUBLICADO / f"predicciones_{nivel}.parquet", index=False)
    prueba = _a_texto(resultado["prueba"][[clave, "trimestre", "y", "probabilidad", "prediccion", "tensionado_hoy"]])
    prueba.to_parquet(config.PUBLICADO / f"prueba_{nivel}.parquet", index=False)
    joblib.dump(resultado["modelo"], config.PUBLICADO / f"modelo_{nivel}.joblib")
    return {
        "elegido": resultado["elegido"],
        "resumen": resultado["resumen"],
        "metricas": resultado["metricas"],
        "importancias": resultado["importancias"].round(4).to_dict("records"),
        "coeficientes": resultado["coeficientes"].round(4).to_dict("records"),
    }


def ejecutar(refrescar: bool = False, con_modelo: bool = True) -> None:
    inicio = datetime.now()
    config.INTERIM.mkdir(parents=True, exist_ok=True)
    config.PUBLICADO.mkdir(parents=True, exist_ok=True)

    log.info("1/5 Ingesta")
    brutas = ingerir_todo(refrescar)
    log.info("2/5 Normalización de códigos territoriales")
    normalizadas, informe_normalizacion = normalizar(brutas)
    log.info("3/5 Validación")
    validas, rechazadas, informe_validacion = validar(normalizadas)
    for nombre, df in validas.items():
        _a_texto(df).to_parquet(config.INTERIM / f"{nombre}.parquet", index=False)
    if not rechazadas.empty:
        # Se publican las filas apartadas que afectan al estudio (no las de los miles de municipios
        # pequeños sin precio, cuya renta el INE oculta por secreto estadístico)
        estudiados = set(validas["precios_mun"]["cod_mun"])
        relevantes = ~rechazadas["tabla"].isin(["renta_mun", "poblacion_mun"]) | rechazadas["cod_mun"].isin(estudiados)
        rechazadas[relevantes].dropna(axis=1, how="all").to_csv(
            config.PUBLICADO / "filas_rechazadas.csv", index=False)

    log.info("4/5 Índice de esfuerzo y criterios del art. 18.3")
    provincias = panel_provincial(validas)
    municipios = panel_municipal(validas)
    _a_texto(provincias[["cod_prov", "provincia", *COLUMNAS_PANEL, "compraventas", "poblacion", "var_alquiler"]]) \
        .to_parquet(config.PUBLICADO / "panel_provincias.parquet", index=False)
    _a_texto(municipios[["cod_mun", "municipio", "cod_prov", "provincia", *COLUMNAS_PANEL, "tasaciones", "poblacion"]]) \
        .to_parquet(config.PUBLICADO / "panel_municipios.parquet", index=False)

    modelo = {}
    if con_modelo:
        log.info("5/5 Modelo de clasificación a dos años")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            modelo["provincias"] = _publicar_modelo(entrenar(provincias, "cod_prov"), "provincias", "cod_prov")
            modelo["municipios"] = _publicar_modelo(entrenar(municipios, "cod_mun", contexto_provincial(provincias)),
                                                    "municipios", "cod_mun")
        (config.PUBLICADO / "modelo.json").write_text(json.dumps(modelo, indent=1, ensure_ascii=False), encoding="utf-8")

    _simplificar_geojson(geojson_provincias(), config.PUBLICADO / "provincias.geojson")

    fuentes = json.loads(MANIFIESTO.read_text(encoding="utf-8")) if MANIFIESTO.exists() else {}
    calidad = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ultimo_trimestre_precios": str(provincias["trimestre"].max()),
        "ultimo_anio_renta": int(validas["renta_prov"]["anio"].max()),
        "supuestos": {
            "superficie_m2": config.SUPERFICIE_M2, "financiacion": config.FINANCIACION,
            "plazo_anios": config.PLAZO_ANIOS, "umbral_esfuerzo": config.UMBRAL_ESFUERZO,
            "umbral_diferencial": config.UMBRAL_DIFERENCIAL,
            "ventana_trimestres": config.VENTANA_TRIMESTRES,
            "horizonte_trimestres": config.HORIZONTE_TRIMESTRES,
        },
        "validacion": informe_validacion,
        "normalizacion": informe_normalizacion,
        "fuentes": {
            "descargas": len(fuentes),
            "primera": min((f["descargado"] for f in fuentes.values()), default=None),
            "ultima": max((f["descargado"] for f in fuentes.values()), default=None),
            "megabytes": round(sum(f["bytes"] for f in fuentes.values()) / 1e6, 1),
        },
    }
    (config.PUBLICADO / "calidad.json").write_text(json.dumps(calidad, indent=1, ensure_ascii=False), encoding="utf-8")
    log.info("Hecho en %.0f s. Artefactos en %s", (datetime.now() - inicio).total_seconds(), config.PUBLICADO)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refrescar", action="store_true", help="volver a descargar todas las fuentes")
    parser.add_argument("--sin-modelo", action="store_true", help="no reentrenar el modelo")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s", datefmt="%H:%M:%S")
    ejecutar(refrescar=args.refrescar, con_modelo=not args.sin_modelo)
