#!/usr/bin/env python3
# HUELLA-TEST-INGESTA-ILEGIBLES-20261025
"""Banco must-fail: el archivo que no parsea se declara, no se suprime.

Nace rojo contra `ingesta_ast_20261019.py` @ 44301d4 (pre-fix): ese objeto no
emitia `n_ilegibles`, no publicaba la lista `ilegibles` y dejaba el registro
del archivo ilegible sin la clave `nodos`, de modo que un archivo perdido y un
archivo con cero nodos eran indistinguibles desde el JSON.
"""

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import ingesta_ast_20261019 as ING

BUENO = "def f():\n    return 1\n"
PY2 = "print 'hola'\n"
VACIO = ""


def _corpus(tmp_path, archivos):
    paquete = os.path.join(str(tmp_path), "paquete")
    os.makedirs(paquete)
    for nombre, texto in archivos.items():
        with open(os.path.join(paquete, nombre), "w", encoding="utf-8") as f:
            f.write(texto)
    return ING.ingerir_paquete("paquete", base=str(tmp_path))


def _por_rel(corpus, rel):
    return [a for a in corpus["archivos"] if a["rel"] == rel][0]


def test_el_ilegible_se_declara_y_se_cuenta(tmp_path):
    c = _corpus(tmp_path, {"bueno.py": BUENO, "py2.py": PY2})
    assert c["n_archivos"] == 2
    assert c["n_ilegibles"] == 1
    assert [i["rel"] for i in c["ilegibles"]] == ["py2.py"]
    assert c["ilegibles"][0]["linea"] == 1
    assert c["ilegibles"][0]["motivo"]


def test_el_ilegible_no_disfraza_cero_nodos(tmp_path):
    c = _corpus(tmp_path, {"bueno.py": BUENO, "vacio.py": VACIO, "py2.py": PY2})
    ilegible = _por_rel(c, "py2.py")
    assert ilegible["nodos"] is None
    assert ilegible["ilegible"] == "SyntaxError"
    assert _por_rel(c, "vacio.py")["nodos"] == 0
    assert _por_rel(c, "bueno.py")["nodos"] == 1


def test_el_denominador_cuenta_el_disco_no_lo_parseado(tmp_path):
    c = _corpus(tmp_path, {"bueno.py": BUENO, "vacio.py": VACIO, "py2.py": PY2})
    assert c["n_archivos"] == len(c["archivos"]) == 3
    parseados = [a for a in c["archivos"] if a["nodos"] is not None]
    assert c["n_archivos"] == c["n_ilegibles"] + len(parseados)
    assert c["n_nodos"] == 1


def test_control_positivo_sin_ilegibles(tmp_path):
    c = _corpus(tmp_path, {"bueno.py": BUENO})
    assert c["n_ilegibles"] == 0
    assert c["ilegibles"] == []
    assert c["n_archivos"] == 1
