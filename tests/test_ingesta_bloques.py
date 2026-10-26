"""Falsador de la ingesta AST: bloques y atribucion (25-Oct-2026).

Mide `_recorrer` del motor real (`ingesta_ast_20261019`), no un sustituto: si
la API cambia, el aparato cae cerrado.

Invariantes:
  1. Una declaracion dentro de un bloque (`if`/`try`/`except`/`for`/`while`/
     `with`) se ingiere igual que una del cuerpo del modulo.
  2. Dentro de una clase y bajo un bloque tambien: el `qual` conserva el
     prefijo de la clase.
  3. Sin sangrado de atribucion: el `raise` de una def interna se acredita a
     la interna y NO al nodo externo.

Antes del arreglo del 25-Oct-2026 `for hijo in nodo.body` perdia 3 de 3 y
`ast.walk` duplicaba la excepcion en los dos nodos. Los dos casos quedan aqui
como must-fail: con el `_recorrer` anterior estas pruebas enrojecen.

HUELLA-TEST-INGESTA-BLOQUES-20261025
"""

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import ingesta_ast_20261019 as ingesta  # noqa: E402


FUENTE = '''def plano():
    return 1


if sys.platform == "win32":
    def en_guard():
        raise OSError("solo windows")


try:
    def en_try():
        pass
except ImportError:
    def en_except():
        pass


class K:
    if True:
        def metodo_en_guard(self):
            pass


def externa():
    def interna():
        raise KeyError("de la interna")
    return interna
'''

QUALES = ["plano", "en_guard", "en_try", "en_except", "K.metodo_en_guard",
          "externa", "externa.interna"]


def _nodos(fuente=FUENTE):
    salida = []
    ingesta._recorrer(ast.parse(fuente), "", "sonda.py", fuente.splitlines(), salida)
    return salida


def test_declaracion_en_bloque_se_ingiere():
    quales = [n["qual"] for n in _nodos()]
    faltan = [q for q in QUALES if q not in quales]
    assert not faltan, f"declaraciones perdidas por bloque: {faltan} en {quales}"


def test_declaracion_en_bloque_conserva_linea_y_segmento():
    por_qual = {n["qual"]: n for n in _nodos()}
    guard = por_qual["en_guard"]
    assert guard["linea"] == 6, f"linea {guard['linea']} != 6"
    assert "OSError" in guard["seg"], f"segmento sin cuerpo: {guard['seg']!r}"
    assert guard["params"] == [], f"params espurios {guard['params']}"


def test_sin_sangrado_de_atribucion():
    por_qual = {n["qual"]: n for n in _nodos()}
    externa = [r["exc"] for r in por_qual["externa"]["raises"]]
    interna = [r["exc"] for r in por_qual["externa.interna"]["raises"]]
    assert interna == ["KeyError"], f"la interna no acredita su raise: {interna}"
    assert externa == [], f"la externa hereda el raise de la interna: {externa}"


def test_control_positivo_plano_sin_bloques():
    fuente = "def a():\n    raise ValueError('x')\n"
    nodos = _nodos(fuente)
    assert [n["qual"] for n in nodos] == ["a"], f"nodos {nodos}"
    assert [r["exc"] for r in nodos[0]["raises"]] == ["ValueError"], "control positivo roto"
