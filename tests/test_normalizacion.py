import pandas as pd
import pytest

from src.normalizacion import clave, claves_alternativas, codificar_municipios, codificar_provincias

PROVINCIAS = pd.DataFrame({
    "cod_prov": ["03", "07", "14", "15", "18", "28", "35", "38", "47"],
    "provincia": ["Alicante/Alacant", "Balears, Illes", "Córdoba", "Coruña, A", "Granada", "Madrid",
                  "Palmas, Las", "Santa Cruz de Tenerife", "Valladolid"],
})
MUNICIPIOS = pd.DataFrame({
    "cod_mun": ["04902", "18017", "07040", "14021", "47186", "07032"],
    "municipio": ["Ejido, El", "Almuñécar", "Palma", "Córdoba", "Valladolid", "Maó"],
})
MUNICIPIOS["cod_prov"] = MUNICIPIOS["cod_mun"].str[:2]


@pytest.mark.parametrize("nombre, esperado", [
    ("Ejido (El)", "el ejido"),
    ("Ejido, El", "el ejido"),
    ("Coruña (A)", "a coruna"),
    ("Hospitalet de Llobregat (L')", "l hospitalet de llobregat"),
    ("  Almería  ", "almeria"),
])
def test_clave_quita_tildes_y_coloca_el_articulo(nombre, esperado):
    assert clave(nombre) == esperado


def test_claves_alternativas_cubre_nombres_bilingues_y_orden_invertido():
    assert {"alicante", "alacant"} <= claves_alternativas("Alicante/Alacant")
    assert "illes balears" in claves_alternativas("Balears, Illes")
    assert "ejido" in claves_alternativas("Ejido (El)")


def test_provincias_del_ministerio_con_alias_y_erratas():
    nombres = pd.Series(["Balears (Illes)", "Madrid (Comunidad de)", "Córdaba", "Valladodid",
                         "Coruña (A)", "Palmas (Las)", "Andalucía", "TOTAL NACIONAL"])
    r = codificar_provincias(nombres, PROVINCIAS).set_index("nombre_fuente")["cod_prov"]
    assert r["Balears (Illes)"] == "07"
    assert r["Madrid (Comunidad de)"] == "28"
    assert r["Córdaba"] == "14"             # errata de la fuente, resuelta por parecido
    assert r["Valladodid"] == "47"
    assert r["Coruña (A)"] == "15"
    assert r["Palmas (Las)"] == "35"
    assert pd.isna(r["Andalucía"]) and pd.isna(r["TOTAL NACIONAL"])


def test_municipio_bajo_provincia_equivocada_se_reasigna():
    fuente = pd.DataFrame({"provincia_fuente": ["Córdoba"], "municipio_fuente": ["Almuñecar"]})
    r = codificar_municipios(fuente, MUNICIPIOS, PROVINCIAS).iloc[0]
    assert r["cod_mun"] == "18017"           # Almuñécar es de Granada
    assert r["metodo"] == "nombre_otra_provincia"


def test_municipios_con_nombre_distinto_usan_alias():
    fuente = pd.DataFrame({"provincia_fuente": ["ILLES BALEARS", "ILLES BALEARS"],
                           "municipio_fuente": ["Palma de Mallorca", "Mahón"]})
    r = codificar_municipios(fuente, MUNICIPIOS, PROVINCIAS)
    assert r["cod_mun"].tolist() == ["07040", "07032"]
