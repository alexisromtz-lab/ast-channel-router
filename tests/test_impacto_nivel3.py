import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import ingesta_ast_20261019 as ING
import extractor_ast as EXT


def test_impacto_importaciones_nivel3_pytest_20261026():
    corpus = ING.ingerir_paquete("_pytest")
    assert corpus is not None

    impacto = EXT.impacto_importaciones(corpus, "_io/terminalwriter.py")

    assert set(impacto) == {"objetivo", "runtime", "solo_type_checking"}
    assert impacto["objetivo"] == "_io/terminalwriter.py"
    assert impacto["runtime"]
    assert impacto["solo_type_checking"]
    assert set(impacto["runtime"]).isdisjoint(impacto["solo_type_checking"])
