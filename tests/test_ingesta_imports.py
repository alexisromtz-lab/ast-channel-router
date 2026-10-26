# HUELLA-TEST-INGESTA-IMPORTS-20261026
# HUELLA-TEST-INGESTA-IMPORTS-DET-20261026
# HUELLA-TEST-INGESTA-TRYSTAR-20261026
# HUELLA-TEST-INGESTA-MODALIDAD-20261026
# HUELLA-TEST-INGESTA-IMPACTO-20261026
# HUELLA-TEST-INGESTA-MODALIDAD-FIX-20261026
# HUELLA-TEST-INGESTA-PUNTOS-CIEGOS-20261026
"""Banco must-fail del grafo de importaciones.

El defecto medido: el corpus no tenia NINGUNA arista de importacion — el
esquema del nodo era `['calls','catches','dec','doc','fin','linea','params',
'qual','raises','rel','seg']` y el sobre no tenia campo de imports. La unica
dependencia modelada era `calls`, y `calls` solo ve nombres invocados, nunca
lo que el archivo necesita para poder importarse.

Censo 26-Oct-2026 sobre el corpus declarado (954 `.py`, 952 parseados):
5 657 imports, 5 150 a nivel modulo y 507 dentro de una declaracion; 236
bajo guarda (`if` o `try`), de los cuales 56 estan a nivel modulo y ninguno
usa `sys.platform` en este corpus. Ese censo es la razon del esquema: la
arista vive en el sobre (`imports`), con `qual: None` en el estrato sin nodo,
porque un campo por nodo describiria solo el 9% del objeto.

Cada prueba de aqui nombra UNA arista y UNA guarda. Falla si la arista no
existe, si pierde el `qual`, si inventa una condicion donde no la hay, o si
los conteos dejan de cuadrar con la lista publicada.
"""

import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import ingesta_ast_20261019 as ING
import extractor_ast as EXT


def _paquete(tmp_path, nombre, **ficheros):
    d = tmp_path / nombre
    d.mkdir(parents=True, exist_ok=True)
    (d / "__init__.py").write_text(ficheros.pop("__init__", ""), encoding="utf-8")
    for nombre_fichero, codigo in ficheros.items():
        (d / (nombre_fichero + ".py")).write_text(codigo, encoding="utf-8")
    return nombre


def _aristas(tmp_path, nombre):
    corpus = ING.ingerir_paquete(nombre, base=str(tmp_path))
    assert corpus is not None
    return corpus, corpus["imports"]


def test_import_bajo_if_de_plataforma_declara_la_condicion(tmp_path):
    codigo = ('import sys\n'
              'if sys.platform == "win32":\n'
              '    import winreg\n')
    nombre = _paquete(tmp_path, "plat_20261026", __init__=codigo)
    _, aristas = _aristas(tmp_path, nombre)
    winreg = [a for a in aristas if a["modulo"] == "winreg"]
    assert len(winreg) == 1
    assert winreg[0]["qual"] is None
    assert winreg[0]["cond"] == "if sys.platform == 'win32'"
    assert winreg[0]["linea"] == 3


def test_import_bajo_try_importerror_declara_la_condicion(tmp_path):
    codigo = ('try:\n'
              '    import unsloth\n'
              'except ImportError:\n'
              '    unsloth = None\n')
    nombre = _paquete(tmp_path, "resp_20261026", __init__=codigo)
    _, aristas = _aristas(tmp_path, nombre)
    unsloth = [a for a in aristas if a["modulo"] == "unsloth"]
    assert len(unsloth) == 1
    assert unsloth[0]["cond"] == "except ImportError"
    assert unsloth[0]["qual"] is None


def test_import_dentro_de_una_def_lleva_el_qual_de_la_declaracion(tmp_path):
    codigo = ('class C:\n'
              '    def m(self):\n'
              '        import locale\n')
    nombre = _paquete(tmp_path, "qual_20261026", __init__=codigo)
    _, aristas = _aristas(tmp_path, nombre)
    locale_ = [a for a in aristas if a["modulo"] == "locale"]
    assert len(locale_) == 1
    assert locale_[0]["qual"] == "C.m"
    assert locale_[0]["cond"] is None


def test_import_sin_guarda_no_inventa_condicion(tmp_path):
    codigo = "import os\nfrom json import dumps\n"
    nombre = _paquete(tmp_path, "plano_20261026", __init__=codigo)
    _, aristas = _aristas(tmp_path, nombre)
    assert [a["modulo"] for a in aristas] == ["os", "json"]
    assert all(a["cond"] is None for a in aristas)
    assert [a["nombre"] for a in aristas] == [None, "dumps"]


def test_guardas_anidadas_se_publican_de_la_externa_a_la_interna(tmp_path):
    codigo = ('import sys\n'
              'if sys.version_info < (3, 11):\n'
              '    try:\n'
              '        import exceptiongroup\n'
              '    except ImportError:\n'
              '        exceptiongroup = None\n')
    nombre = _paquete(tmp_path, "anid_20261026", __init__=codigo)
    _, aristas = _aristas(tmp_path, nombre)
    eg = [a for a in aristas if a["modulo"] == "exceptiongroup"]
    assert len(eg) == 1
    assert eg[0]["cond"] == ("if sys.version_info < (3, 11) / "
                             "except ImportError")


def test_import_relativo_conserva_los_puntos(tmp_path):
    codigo = "from . import hermano\nfrom ..paquete import cosa\n"
    nombre = _paquete(tmp_path, "rel_20261026", __init__=codigo)
    _, aristas = _aristas(tmp_path, nombre)
    assert [a["modulo"] for a in aristas] == [".", "..paquete"]
    assert [a["nombre"] for a in aristas] == ["hermano", "cosa"]


def test_los_conteos_cuadran_con_la_lista_publicada(tmp_path):
    codigo = ('import os\n'
              'try:\n'
              '    import colorama\n'
              'except ImportError:\n'
              '    colorama = None\n'
              'def f():\n'
              '    import json\n')
    nombre = _paquete(tmp_path, "cuenta_20261026", __init__=codigo)
    corpus, aristas = _aristas(tmp_path, nombre)
    assert corpus["n_imports"] == len(aristas) == 3
    assert corpus["n_imports_cond"] == 1 == sum(1 for a in aristas if a["cond"])


def test_archivo_ilegible_no_aporta_aristas_y_se_declara(tmp_path):
    nombre = _paquete(tmp_path, "mixto_20261026",
                      __init__="import os\n",
                      roto="import sys\ndef f(:\n")
    corpus, aristas = _aristas(tmp_path, nombre)
    assert corpus["n_ilegibles"] == 1
    assert corpus["ilegibles"][0]["rel"] == "roto.py"
    assert all(a["rel"] == "__init__.py" for a in aristas)
    assert [a["modulo"] for a in aristas] == ["os"]
    archivos = {a["rel"]: a for a in corpus["archivos"]}
    assert archivos["__init__.py"]["puntos_ciegos"] == []
    assert archivos["roto.py"]["puntos_ciegos"] is None


# HUELLA-TEST-INGESTA-PUNTOS-CIEGOS-CASOS-20261026
def test_puntos_ciegos_dinamicos_se_declaran_por_archivo(tmp_path):
    codigo = (
        "import importlib as il\n"
        "from importlib import import_module as cargar\n"
        "if True:\n"
        "    def __getattr__(nombre):\n"
        "        return il.import_module(nombre)\n"
        "def por_nombre(nombre):\n"
        "    cargar(nombre)\n"
        "    return globals()[nombre]\n"
    )
    nombre = _paquete(
        tmp_path, "dinamico_20261026", __init__=codigo, limpio="valor = 1\n"
    )
    corpus = ING.ingerir_paquete(nombre, base=str(tmp_path))
    archivos = {a["rel"]: a for a in corpus["archivos"]}
    assert corpus["esquema"] == "ingesta_ast/v2"
    assert archivos["__init__.py"]["puntos_ciegos"] == [
        "__getattr__", "importlib.import_module", "globals()[...]"
    ]
    assert archivos["limpio.py"]["puntos_ciegos"] == []


def test_imports_es_determinista(tmp_path):
    codigo = ('import sys\n'
              'if sys.platform == "win32":\n'
              '    import winreg\n'
              'try:\n'
              '    import colorama\n'
              'except ImportError:\n'
              '    colorama = None\n')
    nombre = _paquete(tmp_path, "det_20261026", __init__=codigo)
    corpus, aristas = _aristas(tmp_path, nombre)
    # el conteo va antes de comparar: dos corridas vacias tambien son iguales
    assert len(aristas) == 3
    assert corpus["n_imports_cond"] == 2
    a = json.dumps(ING.ingerir_paquete(nombre, base=str(tmp_path)),
                   sort_keys=True)
    b = json.dumps(ING.ingerir_paquete(nombre, base=str(tmp_path)),
                   sort_keys=True)
    assert a == b


@pytest.mark.skipif(sys.version_info < (3, 11),
                    reason="except* no existe antes de 3.11")
def test_import_bajo_except_estrella_lleva_cond(tmp_path):
    codigo = ('try:\n'
              '    import colorama\n'
              'except* ImportError:\n'
              '    colorama = None\n')
    nombre = _paquete(tmp_path, "estrella_20261026", __init__=codigo)
    corpus, aristas = _aristas(tmp_path, nombre)
    assert len(aristas) == 1
    # `try*` no es `Try`: sin TIPOS_TRY la arista se publicaba sin guarda
    assert aristas[0]["cond"] == "except ImportError"
    assert corpus["n_imports_cond"] == 1


# HUELLA-TEST-INGESTA-MODALIDAD-STRINGS-20261026
def test_modalidad_presente_en_todas_las_aristas(tmp_path):
    codigo = ('from typing import TYPE_CHECKING\n'
              'if TYPE_CHECKING:\n'
              '    import os\n'
              'try:\n'
              '    import colorama\n'
              'except ImportError:\n'
              '    colorama = None\n'
              'import json\n')
    nombre = _paquete(tmp_path, "modalidad_20261026", __init__=codigo)
    _, aristas = _aristas(tmp_path, nombre)
    modalidades = {a["modulo"]: a["modalidad"] for a in aristas}
    assert set(modalidades.values()) <= {
        "requerida", "type_checking", "runtime_data", "except_import"}
    assert modalidades == {
        "typing": "requerida", "os": "type_checking",
        "colorama": "except_import", "json": "requerida"}


def test_type_checking_no_cuenta_como_impacto_runtime(tmp_path):
    paquete = "impacto_20261026"
    nombre = _paquete(
        tmp_path, paquete,
        a=('from typing import TYPE_CHECKING\n'
           'if TYPE_CHECKING:\n'
           '    from . import b\n'),
        b="VALUE = 1\n",
        c=f"import {paquete}.a\n",
    )
    corpus, _ = _aristas(tmp_path, nombre)
    impacto = EXT.impacto_importaciones(corpus, "b.py")
    assert impacto["runtime"] == []
    assert impacto["solo_type_checking"] == ["a.py", "c.py"]
