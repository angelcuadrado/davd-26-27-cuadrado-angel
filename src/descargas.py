"""Acceso a las fuentes: cliente de la API JSON del INE y descarga de ficheros.

Cada descarga se guarda en data/raw con caché en disco, reintentos y una entrada en
data/raw/manifiesto.json (URL, fecha, tamaño y huella SHA-256). Así se sabe exactamente qué
versión de cada fuente produjo los resultados, y el pipeline se puede repetir sin red.
"""
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests

from src.config import INE_API, RAW

log = logging.getLogger(__name__)
MANIFIESTO = RAW / "manifiesto.json"
CABECERAS = {"User-Agent": "davd-esfuerzo-vivienda/1.0 (proyecto academico)"}


class ErrorINE(Exception):
    """La API del INE respondió con un mensaje de estado en lugar de datos."""


def _registrar(url: str, destino: Path) -> None:
    """Anota la descarga en el manifiesto."""
    manifiesto = json.loads(MANIFIESTO.read_text(encoding="utf-8")) if MANIFIESTO.exists() else {}
    contenido = destino.read_bytes()
    manifiesto[destino.relative_to(RAW).as_posix()] = {
        "url": url,
        "descargado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bytes": len(contenido),
        "sha256": hashlib.sha256(contenido).hexdigest(),
    }
    MANIFIESTO.write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")


def _pedir(url: str, intentos: int = 4, timeout: int = 120) -> bytes:
    """GET con reintentos y espera exponencial (1, 2, 4 s...)."""
    for intento in range(intentos):
        try:
            respuesta = requests.get(url, headers=CABECERAS, timeout=timeout)
            respuesta.raise_for_status()
            return respuesta.content
        except requests.RequestException as e:
            if intento == intentos - 1:
                raise
            espera = 2 ** intento
            log.warning("Fallo al descargar %s (%s). Reintento en %d s", url, e, espera)
            time.sleep(espera)
    raise RuntimeError("inalcanzable")


FIRMAS = {
    ".xls": (b"\xd0\xcf\x11\xe0",),            # Excel 97-2003 (contenedor OLE)
    ".xlsx": (b"PK\x03\x04",),                  # Excel moderno (zip)
    ".geojson": (b"{",),
}


def contenido_valido(contenido: bytes, sufijo: str) -> bool:
    """Comprueba la firma del fichero: un servidor que cambia de sitio suele devolver una página
    HTML con código 200, y sin esta comprobación se guardaría como si fuera el Excel."""
    firmas = FIRMAS.get(sufijo.lower())
    return firmas is None or contenido.lstrip()[:8].startswith(firmas)


def descargar_fichero(url: str, destino: Path, refrescar: bool = False) -> Path:
    """Descarga un fichero a data/raw/<destino> salvo que ya esté en caché.

    Si lo descargado no tiene el formato esperado, no se toca la copia en caché: se avisa y se
    sigue con la última versión buena (o se falla si no hay ninguna).
    """
    destino = RAW / destino
    if destino.exists() and not refrescar:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    contenido = _pedir(url)
    if not contenido_valido(contenido, destino.suffix):
        if destino.exists():
            log.warning("%s no devolvió un %s válido (¿ha cambiado de dirección?). "
                        "Sigo con la copia en caché.", url, destino.suffix)
            return destino
        raise ValueError(f"{url} no devolvió un fichero {destino.suffix} válido")
    destino.write_bytes(contenido)
    _registrar(url, destino)
    log.info("Descargado %s", destino.name)
    return destino


def ine(funcion: str, entrada: str | int, refrescar: bool = False, **parametros) -> list | dict:
    """Llama a la API JSON del INE: {INE_API}/{funcion}/{entrada}?{parametros}.

    Ejemplo: ine("DATOS_TABLA", 76141, tip="AM", nult=4)
    """
    consulta = urlencode(parametros, doseq=True)
    url = f"{INE_API}/{funcion}/{entrada}" + (f"?{consulta}" if consulta else "")
    nombre = f"{funcion}_{entrada}" + (f"_{hashlib.md5(consulta.encode()).hexdigest()[:8]}" if consulta else "")
    destino = RAW / "ine" / f"{nombre}.json"
    aviso = destino.with_suffix(".estado")          # respuesta sin datos ya conocida
    if aviso.exists() and not refrescar:
        raise ErrorINE(aviso.read_text(encoding="utf-8"))
    if refrescar or not destino.exists():
        destino.parent.mkdir(parents=True, exist_ok=True)
        contenido = _pedir(url)
        respuesta = json.loads(contenido)           # falla aquí si el INE devuelve algo que no es JSON
        if isinstance(respuesta, dict) and "status" in respuesta:
            aviso.write_text(respuesta["status"], encoding="utf-8")
            raise ErrorINE(respuesta["status"])     # p. ej. «restricciones de volumen»
        destino.write_bytes(contenido)
        _registrar(url, destino)
    return json.loads(destino.read_text(encoding="utf-8"))
