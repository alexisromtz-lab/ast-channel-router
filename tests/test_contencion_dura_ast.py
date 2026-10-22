"""Aparato semantico de Nivel 6 para ast-channel-router.

Mide el motor REAL del repositorio (`canales_v5_20261019`), no una
reimplementacion: si la API cambia, el aparato cae cerrado en vez de medir
un sustituto.

Invariantes:
  1. Falla cerrada sin canales activos: masa 0 -> score 0.0.
  2. No-dilucion por contencion: el canal duro (|Q ∩ D| / |Q|) vale 1.0 igual
     con la consulta limpia que inflada con 50 tokens de ruido; la bolsa
     completa (Jaccard) si se diluye y cae bajo UMBRAL.
  3. Discriminacion estructura vs. bolsa plana: las mismas palabras sin
     canales duros no enrutan.
  4. Falsador de permutacion: canales cruzados colapsan a 0.0 mientras la
     consulta sin permutar enruta (control positivo, el falsador no es vacuo).
  5. Ingesta: la fuente se reconoce por AST y la prosa no.

HUELLA-TEST-CONTENCION-DURA-AST-20261022
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import canales_v5_20261019 as canales  # noqa: E402
import extractor_ast  # noqa: E402
import router_soluciones_v2 as v2  # noqa: E402


FUENTE = '''# src/parser.py
import ast


def compile_kernel(ruta):
    try:
        return ast.parse(open(ruta).read())
    except SyntaxError as e:
        raise RuntimeError("fallo al compilar src/parser.py") from e
'''

TRAZA = (
    "RuntimeError: TT_FATAL @ device.cpp:412: device.load_sub_device_manager "
    "fallo al montar el sub device manager; ver tests/ttnn/test_prefetcher.py"
)

RUIDO = " ".join(f"ruido{i}" for i in range(50))


def _bolsa(texto):
    return set(v2.tokenizar(texto))


def test_falla_cerrada_sin_canales_activos():
    q = canales.vacio()
    score, detalle = canales.puntuar(q, canales.extraer(FUENTE))
    assert canales.activos(q) == set(), "un canal se activo sin consulta"
    assert detalle["masa"] == 0.0, f"masa espuria {detalle['masa']}"
    assert score == 0.0, f"VIOLACION_FAIL_CLOSED: consulta vacia produjo {score}"


def test_ingesta_discrimina_fuente_de_prosa():
    por_ast = extractor_ast.extraer_canales_ast(FUENTE, rel="src/parser.py")
    por_texto = extractor_ast.extraer_canales_ast(FUENTE, forzar="texto")
    traza = extractor_ast.extraer_canales_ast(TRAZA)

    assert por_ast["via"] == "ast", por_ast["via"]
    assert traza["via"] == "texto", traza["via"]
    delta = por_ast["n"]["simbolos"] - por_texto["n"]["simbolos"]
    assert delta > 0, (
        f"la via AST no aporta simbolos sobre la via texto (delta={delta}): "
        "la estructura no se esta leyendo"
    )


def test_no_dilucion_por_contencion():
    d = canales.extraer(TRAZA)
    limpia = "device.load_sub_device_manager TT_FATAL"
    q_limpia = canales.extraer(limpia)
    q_ruidosa = canales.extraer(limpia + " " + RUIDO)

    score_limpio, det_limpio = canales.puntuar(q_limpia, d)
    score_ruidoso, det_ruidoso = canales.puntuar(q_ruidosa, d)

    assert det_limpio["por_canal"]["simbolos"] == 1.0, det_limpio["por_canal"]
    assert det_ruidoso["por_canal"]["simbolos"] == 1.0, det_ruidoso["por_canal"]
    assert score_limpio >= 0.80, f"SENAL_INSUFICIENTE: {score_limpio:.4f}"
    assert score_ruidoso >= 0.80, f"DILUCION_DETECTADA: {score_ruidoso:.4f}"

    jaccard_limpio = v2.similitud_jaccard(_bolsa(limpia), _bolsa(TRAZA))
    jaccard_ruidoso = v2.similitud_jaccard(_bolsa(limpia + " " + RUIDO), _bolsa(TRAZA))
    assert jaccard_ruidoso < jaccard_limpio, (jaccard_ruidoso, jaccard_limpio)
    assert jaccard_ruidoso < canales.UMBRAL, (
        f"el control Jaccard no se diluyo ({jaccard_ruidoso:.4f}); el contraste no prueba nada"
    )
    assert score_ruidoso > canales.UMBRAL > jaccard_ruidoso, (
        f"sin contraste: score {score_ruidoso:.4f} vs jaccard {jaccard_ruidoso:.4f}"
    )


def test_discriminacion_estructura_vs_bolsa_plana():
    consulta = "SyntaxError en compile_kernel sobre src/parser.py al compilar"
    q = canales.extraer(consulta)
    doc_ast = canales.extraer(FUENTE)
    doc_bow = canales.vacio()
    doc_bow["prosa"] = _bolsa(FUENTE) | _bolsa(consulta)

    score_ast, det_ast = canales.puntuar(q, doc_ast)
    score_bow, det_bow = canales.puntuar(q, doc_bow)

    assert score_ast > canales.UMBRAL, f"DOC_ESTRUCTURADO_RECHAZADO: {score_ast:.4f}"
    assert set(det_bow["evidencia"]) <= {"prosa"}, (
        f"la bolsa plana dio evidencia dura: {det_bow['evidencia']}"
    )
    delta = score_ast - score_bow
    assert delta >= 0.70, (
        f"CEGUERA_DE_CANAL: no discrimina estructura frente a bolsa plana (delta={delta:.4f})"
    )


def test_falsador_permutacion_de_canales():
    d = canales.extraer(FUENTE)
    control = canales.extraer("SyntaxError en compile_kernel sobre src/parser.py")
    score_control, _ = canales.puntuar(control, d)

    q_permutada = canales.vacio()
    q_permutada["simbolos"] = {"src/parser.py"}
    q_permutada["excepciones"] = {"compile_kernel"}
    q_permutada["rutas"] = {"SyntaxError"}
    q_permutada["prosa"] = {"nada_coincidente"}
    score_nulo, det_nulo = canales.puntuar(q_permutada, d)

    assert score_control > canales.UMBRAL, f"control positivo no enruta: {score_control:.4f}"
    assert det_nulo["evidencia"] == {}, f"evidencia espuria: {det_nulo['evidencia']}"
    assert score_nulo <= canales.UMBRAL, (
        f"FALSADOR_ACTIVADO: canales permutados puntuan {score_nulo:.4f}"
    )
