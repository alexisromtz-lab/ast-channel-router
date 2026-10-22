#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Router V2: Jaccard con filtro de stopwords (nucleo generico).

CORTE PUBLICO. Este archivo es el CORTE PUBLICO del motor de enrutamiento:

  - Las funciones `tokenizar`, `similitud_jaccard`, `texto_de`, `enrutar` y
    `clasificar` son COPIA LITERAL del motor privado, verificada por hash de
    `inspect.getsource` contra el original (tokenizar 345ba07ee17e,
    similitud_jaccard d2d02bd1afc1, texto_de b9aaf3ad7949, enrutar
    5d3bc24f799d; STOPWORDS y CAMPOS_TEXTO iguales elemento a elemento).
  - Se retiran las piezas que NO son motor: el banco de casos con identificador
    de solucion, el barrido contra la version anterior y la ruta fija del
    catalogo. Ese material pertenece al catalogo privado y no se distribuye.

Diferencia unica respecto de la V1: se descartan los tokens de STOPWORDS, en la
consulta Y en el texto del indice (simetria). Tokenizador, campos del texto y
Jaccard se conservan sin tocar.

El umbral NO es una constante heredada: es del corpus del operador. Aqui se lee
de `ROUTER_UMBRAL` (por defecto 0.07, el valor que el motor privado usa con su
propio catalogo) y se declara en la salida para que cada corrida sea auditable.

Uso:
    python3 router_soluciones_v2.py --indice catalogo.json "el problema"
    python3 router_soluciones_v2.py --indice catalogo.json --json "..."
    ROUTER_INDICE=catalogo.json python3 router_soluciones_v2.py "..."

Formato del indice: {"soluciones": [{"id": ..., "problema": ..., "solucion": ...,
"dominio": ..., "cuando_aplicar": ...}, ...]}

RC: 0 encontrado · 3 NO_ENCONTRADO (sim < umbral) · 2 uso incorrecto
"""

import argparse
import json
import os
import re
import sys
import time

HUELLA = "HUELLA-ROUTER-V2-CORTE-PUBLICO-20261020"
UMBRAL = float(os.environ.get("ROUTER_UMBRAL", "0.07"))
RAIZ = os.path.dirname(os.path.abspath(__file__))
RUTA_INDICE = os.environ.get("ROUTER_INDICE", os.path.join(RAIZ, "catalogo.json"))

# Texto de comparacion: los MISMOS cuatro campos de la V1.
CAMPOS_TEXTO = ("problema", "solucion", "dominio", "cuando_aplicar")

STOPWORDS_ES = frozenset("""
a al algo algunos ante antes aquel aquella aqui asi aun cada como con contra cual
cuales cuando de del desde donde el ella ellas ellos en entre era eran eres es esa
esas ese eso esos esta estaba estado estan estar estas este esto estos fue fueron ha
habia han hasta hay la las le les lo los mas me mi mis mucho muchos muy nada ni no
nos nosotros nuestra nuestro o os otra otras otro otros para pero poco por porque
que quien quienes se sea segun ser si sido sin sobre son su sus tal tambien tanto te
tiene tienen toda todas todo todos tu tus un una unas uno unos y ya yo
""".split())

STOPWORDS_EN = frozenset("""
a an and are as at be been but by can could do does did for from had has have in into
is it its not of on or should than that the their them then there these they this to
was were what when which will with would you your
""".split())

STOPWORDS = STOPWORDS_ES | STOPWORDS_EN

RC_OK, RC_USO, RC_NADA = 0, 2, 3


def hora_utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def tokenizar(texto):
    """Identico a la V1 + filtro de STOPWORDS. Devuelve un conjunto."""
    return {t for t in re.findall(r"\w+", texto.lower()) if t not in STOPWORDS}


def similitud_jaccard(a, b):
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def cargar_indice(ruta=RUTA_INDICE):
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def texto_de(fila):
    return " ".join(str(fila.get(k, "")) for k in CAMPOS_TEXTO)


def enrutar(consulta, indice):
    """Lista (score, fila) ordenada desc. Mide tambien si la consulta quedo vacia."""
    t_consulta = tokenizar(consulta)
    filas = indice.get("soluciones") or []
    mejores = []
    for fila in filas:
        mejores.append((similitud_jaccard(t_consulta, tokenizar(texto_de(fila))), fila))
    mejores.sort(key=lambda x: x[0], reverse=True)
    return t_consulta, mejores


def clasificar(consulta, indice):
    t_consulta, mejores = enrutar(consulta, indice)
    if not mejores:
        return {"estado": "NO_ENCONTRADO", "motivo": "indice vacio",
                "sim": 0.0, "id": None, "fila": None, "candidatos": []}
    score, fila = mejores[0]
    if not t_consulta:
        return {"estado": "NO_ENCONTRADO", "motivo": "0 tokens de contenido",
                "sim": 0.0, "id": None, "fila": None,
                "candidatos": [(s, f.get("id")) for s, f in mejores[:3]]}
    if score < UMBRAL:
        return {"estado": "NO_ENCONTRADO",
                "motivo": "sim %.6f < umbral %.2f" % (score, UMBRAL),
                "sim": score, "id": None, "fila": None,
                "candidatos": [(s, f.get("id")) for s, f in mejores[:3]]}
    return {"estado": "ENCONTRADO", "motivo": "", "sim": score,
            "id": fila.get("id"), "fila": fila,
            "candidatos": [(s, f.get("id")) for s, f in mejores[:3]]}


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="router_soluciones_v2.py",
        description="Router V2: Jaccard con filtro de stopwords.")
    ap.add_argument("consulta", nargs="*", help="problema en lenguaje natural")
    ap.add_argument("--indice", default=None, help="ruta del catalogo JSON")
    ap.add_argument("--json", action="store_true", help="salida maquina-legible")
    args = ap.parse_args(argv)

    ruta = args.indice or RUTA_INDICE
    try:
        indice = cargar_indice(ruta)
    except (OSError, ValueError) as exc:
        print("ERROR: no se pudo leer el indice %s: %s" % (ruta, exc), file=sys.stderr)
        return RC_USO

    consulta = " ".join(args.consulta).strip()
    if not consulta and not sys.stdin.isatty():
        consulta = sys.stdin.read().strip()
    if not consulta:
        print("ERROR: falta el problema. Uso: router_soluciones_v2.py --indice "
              "<catalogo.json> \"<problema>\"", file=sys.stderr)
        return RC_USO

    r = clasificar(consulta, indice)
    if args.json:
        print(json.dumps({
            "huella": HUELLA, "hora": hora_utc(), "consulta": consulta,
            "umbral": UMBRAL, "estado": r["estado"], "motivo": r["motivo"],
            "sim": round(r["sim"], 6), "id": r["id"],
            "candidatos": [{"id": i, "sim": round(s, 6)} for s, i in r["candidatos"]],
        }, ensure_ascii=False, indent=2))
        return RC_OK if r["estado"] == "ENCONTRADO" else RC_NADA

    print("ESTADO: %s | sim=%.4f" % (r["estado"], r["sim"]))
    if r["motivo"]:
        print("MOTIVO: %s" % r["motivo"])
    if r["fila"] is not None:
        print("SOLUCION: %s - %s" % (r["id"], r["fila"].get("problema", "")))
        print("DOMINIO:  %s" % r["fila"].get("dominio", ""))
    else:
        print("CANDIDATOS (bajo el umbral, no adjudicados)")
        for s, i in r["candidatos"]:
            print("  sim=%.6f  %s" % (s, i))
    return RC_OK if r["estado"] == "ENCONTRADO" else RC_NADA


if __name__ == "__main__":
    sys.exit(main())
