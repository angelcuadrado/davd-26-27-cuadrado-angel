from src import descargas


def test_firma_reconoce_excel_y_rechaza_html():
    assert descargas.contenido_valido(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1resto", ".xls")
    assert descargas.contenido_valido(b"PK\x03\x04resto", ".xlsx")
    assert not descargas.contenido_valido(b"<!DOCTYPE html><html>", ".xls")
    assert descargas.contenido_valido(b"cualquier cosa", ".csv")      # sin firma conocida: se acepta


def test_pagina_html_no_sobrescribe_la_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(descargas, "RAW", tmp_path)
    monkeypatch.setattr(descargas, "MANIFIESTO", tmp_path / "manifiesto.json")
    bueno = b"\xd0\xcf\x11\xe0 excel bueno"
    (tmp_path / "datos.xls").write_bytes(bueno)
    monkeypatch.setattr(descargas, "_pedir", lambda url: b"<!DOCTYPE html> el servidor se ha mudado")

    ruta = descargas.descargar_fichero("https://ejemplo/datos.xls", "datos.xls", refrescar=True)

    assert ruta.read_bytes() == bueno
