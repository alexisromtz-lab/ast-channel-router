# HUELLA-TEST-INGESTA-SITE-RC-20261025
"""Banco must-fail de la resolucion del paquete y del RC con causa declarada.

El defecto medido: `SITE` estaba clavado a RAIZ/.venv/lib/pythonX.Y/site-packages
(que no existe en el repo), asi que el uso documentado `--paquete yaml` devolvia
2; y `main` devolvia 2 tanto para un paquete AUSENTE como para uno que existe y
no rinde nodos. Dos objetos distintos, un solo nombre.

Cada prueba de aqui nombra UNA causa. Falla si el RC o el mensaje la confunden
con otra, y falla si la resolucion vuelve a depender de una ruta clavada.
"""

import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import ingesta_ast_20261019 as ING


def _paquete(tmp_path, nombre, codigo):
    d = tmp_path / nombre
    d.mkdir(parents=True, exist_ok=True)
    (d / "__init__.py").write_text(codigo, encoding="utf-8")
    return d


def test_paquete_importable_se_resuelve_sin_ruta_clavada():
    corpus = ING.ingerir_paquete("json")
    raiz, causa = ING.resolver_raiz("json")
    assert causa is None
    assert raiz and (pathlib.Path(raiz) / "__init__.py").is_file()
    assert corpus is not None
    assert corpus["n_archivos"] > 0
    assert corpus["n_nodos"] > 0


def test_paquete_ausente_devuelve_2_con_causa_ausente(capsys):
    rc = ING.main(["--paquete", "paquete_que_no_existe_20261025"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "AUSENTE" in err
    assert "sin nodos" not in err


def test_modulo_suelto_se_declara_no_es_paquete(capsys):
    rc = ING.main(["--paquete", "__future__"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "NO_ES_PAQUETE" in err


def test_site_explicito_inexistente_se_declara(capsys, tmp_path):
    rc = ING.main(["--paquete", "cualquiera", "--site", str(tmp_path)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "RUTA_EXPLICITA_AUSENTE" in err


def test_paquete_sin_nodos_devuelve_3_y_no_2(capsys, tmp_path):
    _paquete(tmp_path, "vacio_20261025", "")
    rc = ING.main(["--paquete", "vacio_20261025", "--site", str(tmp_path)])
    err = capsys.readouterr().err
    assert rc == 3
    assert "SIN_NODOS" in err
    assert "ausente" not in err.lower()


def test_paquete_ilegible_entero_devuelve_3_y_publica_conteo(capsys, tmp_path):
    _paquete(tmp_path, "roto_20261025", "def f(:\n")
    rc = ING.main(["--paquete", "roto_20261025", "--site", str(tmp_path)])
    err = capsys.readouterr().err
    assert rc == 3
    assert "SIN_NODOS_ILEGIBLES" in err
    assert "ilegibles=1" in err


def test_control_positivo_site_explicito_devuelve_0(capsys, tmp_path):
    _paquete(tmp_path, "sano_20261025",
             "def f():\n    raise KeyError('x')\n")
    rc = ING.main(["--paquete", "sano_20261025", "--site", str(tmp_path),
                   "--json"])
    assert rc == 0
    corpus = json.loads(capsys.readouterr().out)
    assert corpus["n_nodos"] == 1
    assert corpus["nodos"][0]["raises"][0]["exc"] == "KeyError"
    assert corpus["n_ilegibles"] == 0
