"""Falsadores del indice de adyacencia H5.

El indice no es una optimizacion optimista: es una funcion que se permite
sustituir a `impacto_importaciones` solo si reproduce su respuesta. Estos
falsadores fijan las dos mitades —paridad y rechazo del corpus ajeno— sobre un
corpus sintetico, y la paridad sobre el corpus durable cuando este existe.

La paridad completa son 1 601 destinos y cuesta 154.16 s porque la referencia
reconstruye el grafo en cada consulta; el banco mide una muestra determinista
de 62 destinos y deja la corrida completa detras de AST_PARIDAD_H5=completa.

HUELLA-H5-FALSADORES-INDICE-20261026
"""

import json
import os
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import extractor_ast as EXT

CORPUS_DURABLE = (pathlib.Path.home() / "Library" / "Caches"
                  / "ast-channel-router" / "vllm_omni.json")


def _corpus():
    """`pkg` con a <- b <- c, donde el unico salto a c es type_checking."""
    return {
        "esquema": "ingesta_ast/v2",
        "paquete": "pkg",
        "locus": "L",
        "raices_ingeridas": [{"raiz": "src", "locus": "L"}],
        "archivos": [
            {"rel": "__init__.py", "locus": "L"},
            {"rel": "a.py", "locus": "L"},
            {"rel": "b.py", "locus": "L"},
            {"rel": "c.py", "locus": "L"},
        ],
        "imports": [
            {"rel": "a.py", "modulo": "os", "nombre": None,
             "modalidad": "requerida"},
            {"rel": "b.py", "modulo": "pkg", "nombre": "a",
             "modalidad": "requerida"},
            {"rel": "c.py", "modulo": "pkg", "nombre": "b",
             "modalidad": "type_checking"},
        ],
    }


def test_el_indice_separa_la_arista_type_checking_del_impacto_runtime():
    impacto = EXT.impacto_importaciones(_corpus(), "a.py",
                                        indice=EXT.indice_adyacencia(_corpus()))
    assert impacto["runtime"] == ["b.py"]
    assert impacto["solo_type_checking"] == ["c.py"]


def test_el_indice_no_cuenta_las_aristas_externas():
    indice = EXT.indice_adyacencia(_corpus())
    assert "os" not in indice["todos"]
    assert set(indice["todos"]) == {"a.py", "b.py"}


def test_sin_indice_y_con_indice_el_resultado_es_el_mismo():
    corpus = _corpus()
    indice = EXT.indice_adyacencia(corpus)
    for objetivo in ("__init__.py", "a.py", "b.py", "c.py"):
        assert EXT.impacto_importaciones(corpus, objetivo) == \
            EXT.impacto_importaciones(corpus, objetivo, indice=indice)


def test_el_indice_publica_su_huella_y_su_fuente():
    indice = EXT.indice_adyacencia(_corpus())
    assert indice["huella"] == EXT.HUELLA_INDICE_ADYACENCIA
    assert indice["paquete"] == "pkg"
    assert indice["fuente_n_archivos"] == 4
    assert indice["fuente_n_imports"] == 3
    assert indice["destinos"] == len(indice["todos"]) == 2


def test_el_indice_es_idempotente():
    primero = EXT.indice_adyacencia(_corpus())
    segundo = EXT.indice_adyacencia(_corpus())
    assert primero["todos"] == segundo["todos"]
    assert primero["runtime"] == segundo["runtime"]


def test_indice_de_otro_corpus_se_rechaza():
    corpus = _corpus()
    ajeno = _corpus()
    ajeno["imports"].append({"rel": "c.py", "modulo": "pkg", "nombre": "a",
                             "modalidad": "requerida"})
    indice = EXT.indice_adyacencia(ajeno)
    try:
        EXT.impacto_importaciones(corpus, "a.py", indice=indice)
    except ValueError as exc:
        assert "indice de otro corpus" in str(exc)
    else:
        raise AssertionError("acepto un indice de otro corpus")


def test_indice_sin_huella_se_rechaza():
    indice = EXT.indice_adyacencia(_corpus())
    del indice["huella"]
    try:
        EXT.impacto_importaciones(_corpus(), "a.py", indice=indice)
    except ValueError as exc:
        assert "no reconocido" in str(exc)
    else:
        raise AssertionError("acepto un indice sin huella")


def test_indice_rechaza_un_objetivo_de_otro_corpus():
    indice = EXT.indice_adyacencia(_corpus())
    try:
        EXT.impacto_importaciones(_corpus(), "z.py", indice=indice)
    except ValueError as exc:
        assert "objetivo fuera del corpus" in str(exc)
    else:
        raise AssertionError("acepto un objetivo inexistente")


def _destinos_durables(muestra):
    corpus = json.loads(CORPUS_DURABLE.read_text(encoding="utf-8"))
    indice = EXT.indice_adyacencia(corpus)
    destinos = sorted(indice["todos"])
    if muestra <= 0:
        return corpus, indice, destinos
    paso = max(1, len(destinos) // muestra)
    return corpus, indice, destinos[::paso]


def test_el_indice_reproduce_el_impacto_en_una_muestra_de_destinos():
    if not CORPUS_DURABLE.is_file():
        return
    muestra = 0 if os.environ.get("AST_PARIDAD_H5") == "completa" else 62
    corpus, indice, destinos = _destinos_durables(muestra)
    assert destinos
    discrepancias = []
    for destino in destinos:
        referencia = EXT.impacto_importaciones(corpus, destino)
        obtenido = EXT.impacto_importaciones(corpus, destino, indice=indice)
        if obtenido != referencia:
            discrepancias.append(destino)
    assert discrepancias == []


def test_el_indice_reproduce_el_743_63_de_platforms_init():
    if not CORPUS_DURABLE.is_file():
        return
    corpus, indice, _ = _destinos_durables(0)
    impacto = EXT.impacto_importaciones(corpus, "platforms/__init__.py",
                                        indice=indice)
    assert len(impacto["runtime"]) == 743
    assert len(impacto["solo_type_checking"]) == 63
    assert impacto == EXT.impacto_importaciones(corpus,
                                                "platforms/__init__.py")
