"""Falsificadores del productor de manifiestos de corpus.

HUELLA-TEST-MANIFIESTO-CORPUS-20261026
"""

import importlib.util
import json
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

_spec = importlib.util.spec_from_file_location(
    "manifiesto_corpus_20261026",
    os.path.join(RAIZ, "manifiesto_corpus_20261026.py"))
MAN = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MAN)

CORPUS_DURABLE = os.path.expanduser(
    "~/Library/Caches/ast-channel-router/vllm_omni.json")
SERIALIZADOR_LEGADO = "json.dumps(ensure_ascii=False, indent=1, sort_keys=True)"
PROV = {"comando": "cmd", "fuente_checkout": "/tmp/x", "fuente_commit": "abc",
        "python": "3.12.13", "medido_en_utc": "2026-10-27T00:45:21Z"}


def _corpus(modalidades=("requerida",), nodos=(3, 4)):
    """Corpus v2 minimo: b.py importa a.py, con las modalidades pedidas."""
    return {
        "esquema": "ingesta_ast/v2",
        "paquete": "pkg",
        "huella": "HUELLA-SINTETICA",
        "raiz": "/x/pkg",
        "raiz_rel": "pkg",
        "locus": "L",
        "archivos": [
            {"rel": "a.py", "locus": "L", "sha256": "0" * 64, "bytes": 1,
             "nodos": nodos[0], "puntos_ciegos": {}},
            {"rel": "b.py", "locus": "L", "sha256": "0" * 64, "bytes": 1,
             "nodos": nodos[1], "puntos_ciegos": {}},
        ],
        "nodos": [],
        "imports": [{"rel": "b.py", "modulo": "pkg.a", "modalidad": m}
                    for m in modalidades],
        "n_archivos": 2,
        "n_imports": len(modalidades),
        "n_nodos": sum(nodos),
        "n_imports_cond": 0,
        "n_ilegibles": 0,
        "ilegibles": [],
        "raices_declaradas": ["/x/pkg"],
        "raices_ingeridas": [{"raiz": "/x/pkg", "locus": "L"}],
        "raices_omitidas": [],
    }


def _escribir_corpus(ruta, corpus, indent=1):
    texto = json.dumps(corpus, ensure_ascii=False, indent=indent,
                       sort_keys=True) + "\n"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)
    return ruta


def test_deriva_las_celdas_del_corpus(tmp_path):
    corpus = _corpus()
    ruta = _escribir_corpus(str(tmp_path / "pkg.json"), corpus)
    man = MAN.derivar(ruta, ("a.py",), proveniencia=PROV)

    assert man["paquete"] == "pkg"
    assert man["n_archivos"] == 2
    assert man["n_imports"] == 1
    assert man["n_nodos"] == 7
    assert man["modalidades"] == {"requerida": 1}
    assert man["bytes"] == os.path.getsize(ruta)
    assert len(man["sha256"]) == 64
    assert man["impacto_a"] == {"objetivo": "a.py", "runtime": 1,
                                "solo_type_checking": 0}


def test_impacto_separa_type_checking_del_runtime(tmp_path):
    corpus = _corpus(modalidades=("requerida", "type_checking"))
    ruta = _escribir_corpus(str(tmp_path / "pkg.json"), corpus)
    man = MAN.derivar(ruta, ("a.py",), proveniencia=PROV)

    assert man["impacto_a"]["runtime"] == 1
    assert man["impacto_a"]["solo_type_checking"] == 0
    assert man["modalidades"] == {"requerida": 1, "type_checking": 1}


def test_rechaza_arista_sin_modalidad(tmp_path):
    corpus = _corpus()
    del corpus["imports"][0]["modalidad"]
    ruta = _escribir_corpus(str(tmp_path / "pkg.json"), corpus)

    with pytest.raises(MAN.CorpusInvalido) as e:
        MAN.derivar(ruta, proveniencia=PROV)
    assert "sin modalidad valida" in str(e.value)


def test_rechaza_corpus_que_se_contradice(tmp_path):
    corpus = _corpus()
    corpus["n_imports"] = 7
    ruta = _escribir_corpus(str(tmp_path / "pkg.json"), corpus)

    with pytest.raises(MAN.CorpusInvalido) as e:
        MAN.derivar(ruta, proveniencia=PROV)
    assert "se contradice" in str(e.value)


def test_detecta_corpus_irreproducible(tmp_path):
    corpus = _corpus()
    ruta = _escribir_corpus(str(tmp_path / "pkg.json"), corpus, indent=2)

    with pytest.raises(MAN.CorpusIrreproducible) as e:
        MAN.derivar(ruta, proveniencia=PROV)
    assert "no se reproduce" in str(e.value)


def test_exige_proveniencia_sin_manifiesto_previo(tmp_path):
    ruta = _escribir_corpus(str(tmp_path / "pkg.json"), _corpus())

    with pytest.raises(MAN.CorpusInvalido) as e:
        MAN.derivar(ruta)
    assert "proveniencia no derivable" in str(e.value)


def test_hereda_proveniencia_del_manifiesto_previo(tmp_path):
    ruta = _escribir_corpus(str(tmp_path / "pkg.json"), _corpus())
    MAN.escribir(ruta, MAN.derivar(ruta, ("a.py",), proveniencia=PROV))

    man = MAN.derivar(ruta, ("a.py",))
    assert {c: man[c] for c in PROV} == PROV


def test_comprobar_nombra_solo_la_celda_desfasada(tmp_path):
    ruta = _escribir_corpus(str(tmp_path / "pkg.json"), _corpus())
    man = MAN.derivar(ruta, ("a.py",), proveniencia=PROV)
    MAN.escribir(ruta, man)

    previo = dict(man, n_archivos=99)
    assert MAN.comprobar(man, previo) == [("n_archivos", 99, 2)]


def test_serializador_declarado_sin_lf_es_un_desfase(tmp_path):
    """El corpus termina en LF: declararlo sin el byte deja la firma muda."""
    ruta = _escribir_corpus(str(tmp_path / "pkg.json"), _corpus())
    man = MAN.derivar(ruta, proveniencia=PROV)
    previo = dict(man, serializador=SERIALIZADOR_LEGADO)

    desfases = MAN.comprobar(man, previo)
    assert [c[0] for c in desfases] == ["serializador"]
    assert desfases[0][2] == SERIALIZADOR_LEGADO + " + '\\n'"


def test_escribir_y_comprobar_es_idempotente(tmp_path):
    ruta = _escribir_corpus(str(tmp_path / "pkg.json"), _corpus())
    man = MAN.derivar(ruta, ("a.py",), proveniencia=PROV)
    destino = MAN.escribir(ruta, man)
    primera = open(destino, "rb").read()
    MAN.escribir(ruta, MAN.derivar(ruta, ("a.py",), proveniencia=PROV))

    assert open(destino, "rb").read() == primera
    assert MAN.main([ruta, "--comprobar"]) == 0


@pytest.mark.skipif(not os.path.exists(CORPUS_DURABLE),
                    reason="corpus durable no presente en esta maquina")
def test_el_manifiesto_durable_coincide_con_su_corpus():
    """Contra el objeto real: 19 celdas medidas, cero desfases."""
    man = MAN.derivar(CORPUS_DURABLE)
    with open(MAN.ruta_manifiesto(CORPUS_DURABLE), encoding="utf-8") as f:
        previo = json.load(f)

    assert MAN.comprobar(man, previo) == []
    assert man["sha256"] == previo["sha256"]
    assert man["impacto_platforms_init"]["runtime"] == 743
    assert man["impacto_platforms_init"]["solo_type_checking"] == 63
    assert man["serializador"].endswith("+ '\\n'")
