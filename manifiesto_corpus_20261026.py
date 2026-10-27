#!/usr/bin/env python3
"""Deriva el manifiesto hermano de un corpus de ingesta AST.

HUELLA-MANIFIESTO-CORPUS-POR-MEDICION-20261026

El manifiesto no se escribe a mano: cada celda de medicion se deriva del
archivo de corpus, y la proveniencia (comando, checkout, commit, interprete,
hora) se hereda del manifiesto previo o se declara explicitamente.

    python manifiesto_corpus_20261026.py CORPUS.json --objetivo platforms/__init__.py
    python manifiesto_corpus_20261026.py CORPUS.json --comprobar

Sin `--comprobar` escribe el manifiesto hermano de forma atomica. Con
`--comprobar` no escribe nada: compara celda por celda contra el manifiesto
existente y devuelve RC 1 nombrando cada desfase.

Codigos de retorno:
    0   manifiesto escrito, o comprobacion limpia
    1   desfase entre el manifiesto declarado y la medicion
    20  uso incorrecto o argumentos insuficientes
    33  el corpus no es reproducible con el serializador declarado
    34  el corpus no cumple el esquema que el manifiesto contrata
"""

import argparse
import collections
import hashlib
import json
import os
import sys

ESQUEMA = "ingesta_ast/v2"
SERIALIZADOR = "json.dumps(ensure_ascii=False, indent=1, sort_keys=True) + '\\n'"
SUFIJO_MANIFIESTO = ".manifest.json"
MODALIDADES = ("requerida", "type_checking", "runtime_data", "except_import")
PROVENIENCIA = ("comando", "fuente_checkout", "fuente_commit", "python",
                "medido_en_utc")


class CorpusInvalido(Exception):
    """El corpus no cumple el esquema que el manifiesto contrata."""


class CorpusIrreproducible(Exception):
    """La huella no es reconstruible con el serializador declarado."""


def ruta_manifiesto(ruta_corpus):
    base = ruta_corpus[:-5] if ruta_corpus.endswith(".json") else ruta_corpus
    return base + SUFIJO_MANIFIESTO


def _slug_objetivo(rel):
    partes = [p for p in rel.replace("\\", "/").split("/") if p]
    if partes and partes[-1].endswith(".py"):
        partes[-1] = partes[-1][:-3]
    partes = ["init" if p == "__init__" else p for p in partes]
    return "_".join(partes)


def _verificar_serializador(corpus, raw):
    """Reproduce los bytes y exige que la huella declarada sea la medida."""
    cuerpo = json.dumps(corpus, ensure_ascii=False, indent=1, sort_keys=True)
    medido = (cuerpo + "\n").encode("utf-8")
    sha_medido = hashlib.sha256(medido).hexdigest()
    sha_archivo = hashlib.sha256(raw).hexdigest()
    if sha_medido != sha_archivo:
        raise CorpusIrreproducible(
            "el corpus no se reproduce con %s: %d bytes declarados frente a "
            "%d reconstruidos (sha %s frente a %s). Publicar la huella sin el "
            "serializador exacto deja una firma irreproducible."
            % (SERIALIZADOR, len(raw), len(medido), sha_archivo[:16],
               sha_medido[:16]))


def _campos_medidos(corpus):
    """Deriva las celdas que el corpus contiene; falla cerrado si no cuadran."""
    if corpus.get("esquema") != ESQUEMA:
        raise CorpusInvalido("esquema %r, se contrata %r"
                             % (corpus.get("esquema"), ESQUEMA))
    archivos = corpus.get("archivos")
    imports = corpus.get("imports")
    if not isinstance(archivos, list) or not isinstance(imports, list):
        raise CorpusInvalido("faltan 'archivos' o 'imports'")

    modalidades = collections.Counter()
    for i, arista in enumerate(imports):
        modalidad = arista.get("modalidad")
        if modalidad not in MODALIDADES:
            raise CorpusInvalido(
                "arista %d sin modalidad valida: %r (se contrata una de %s)"
                % (i, modalidad, ", ".join(MODALIDADES)))
        modalidades[modalidad] += 1

    nodos = sum(a.get("nodos") or 0 for a in archivos if isinstance(a, dict))
    medidos = {
        "esquema": corpus["esquema"],
        "paquete": corpus.get("paquete"),
        "huella_ingesta": corpus.get("huella"),
        "n_archivos": len(archivos),
        "n_imports": len(imports),
        "n_nodos": nodos,
        "modalidades": dict(sorted(modalidades.items())),
        "raices_ingeridas": len(corpus.get("raices_ingeridas") or ()),
        "raices_omitidas": len(corpus.get("raices_omitidas") or ()),
        "serializador": SERIALIZADOR,
    }
    for celda in ("n_archivos", "n_imports", "n_nodos"):
        declarado = corpus.get(celda)
        if declarado is not None and declarado != medidos[celda]:
            raise CorpusInvalido(
                "%s declara %r y se mide %r: el corpus se contradice a si mismo"
                % (celda, declarado, medidos[celda]))
    return medidos


def _impacto(corpus, objetivos):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import extractor_ast

    celdas = {}
    for objetivo in objetivos:
        resultado = extractor_ast.impacto_importaciones(corpus, objetivo)
        celdas["impacto_" + _slug_objetivo(objetivo)] = {
            "objetivo": objetivo,
            "runtime": len(resultado["runtime"]),
            "solo_type_checking": len(resultado["solo_type_checking"]),
        }
    return celdas


def derivar(ruta_corpus, objetivos=(), paquete=None, proveniencia=None):
    """Devuelve el manifiesto completo: medido, heredado y verificado."""
    with open(ruta_corpus, "rb") as f:
        raw = f.read()
    corpus = json.loads(raw)
    _verificar_serializador(corpus, raw)

    manifiesto = _campos_medidos(corpus)
    if paquete is not None and paquete != manifiesto["paquete"]:
        raise CorpusInvalido("el corpus declara el paquete %r, se buscaba %r"
                             % (manifiesto["paquete"], paquete))

    previo = {}
    ruta_man = ruta_manifiesto(ruta_corpus)
    if os.path.exists(ruta_man):
        with open(ruta_man, "r", encoding="utf-8") as f:
            previo = json.load(f)

    if not objetivos:
        objetivos = tuple(previo.get("objetivos") or ())
    manifiesto.update(_impacto(corpus, objetivos))
    manifiesto["objetivos"] = list(objetivos)

    heredado = dict(proveniencia or {})
    for clave in PROVENIENCIA:
        if clave not in heredado and clave in previo:
            heredado[clave] = previo[clave]
    faltan = [c for c in PROVENIENCIA if c not in heredado]
    if faltan:
        raise CorpusInvalido(
            "proveniencia no derivable del corpus y sin manifiesto previo: %s. "
            "Declararla con --prov clave=valor." % ", ".join(faltan))
    manifiesto.update({c: heredado[c] for c in PROVENIENCIA})

    manifiesto["bytes"] = len(raw)
    manifiesto["sha256"] = hashlib.sha256(raw).hexdigest()
    return manifiesto


def escribir(ruta_corpus, manifiesto):
    ruta_man = ruta_manifiesto(ruta_corpus)
    temporal = ruta_man + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        f.write(json.dumps(manifiesto, ensure_ascii=False, indent=2,
                           sort_keys=True) + "\n")
    os.replace(temporal, ruta_man)
    return ruta_man


def comprobar(manifiesto, previo):
    """Devuelve la lista de desfases; vacia si el manifiesto coincide."""
    desfases = []
    for clave in sorted(set(manifiesto) | set(previo)):
        medido = manifiesto.get(clave, "<ausente en la medicion>")
        declarado = previo.get(clave, "<ausente en el manifiesto>")
        if medido != declarado:
            desfases.append((clave, declarado, medido))
    return desfases


def _proveniencia(pares):
    salida = {}
    for par in pares or ():
        if "=" not in par:
            raise SystemExit("--prov espera clave=valor, se recibio %r" % par)
        clave, valor = par.split("=", 1)
        if clave not in PROVENIENCIA:
            raise SystemExit("--prov no admite %r (si %s)"
                             % (clave, ", ".join(PROVENIENCIA)))
        salida[clave] = valor
    return salida


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("corpus", help="ruta del corpus JSON")
    parser.add_argument("--objetivo", action="append", default=None,
                        help="objetivo relativo cuyo impacto se publica")
    parser.add_argument("--paquete", default=None,
                        help="paquete esperado; se verifica contra el corpus")
    parser.add_argument("--prov", action="append", default=None,
                        help="proveniencia clave=valor (solo si no hay previo)")
    parser.add_argument("--comprobar", action="store_true",
                        help="no escribe: mide y compara con el manifiesto")
    args = parser.parse_args(argv)

    if not os.path.exists(args.corpus):
        print("CORPUS AUSENTE: %s" % args.corpus, file=sys.stderr)
        return 20
    try:
        manifiesto = derivar(args.corpus, tuple(args.objetivo or ()),
                             args.paquete, _proveniencia(args.prov))
    except CorpusIrreproducible as e:
        print("IRREPRODUCIBLE: %s" % e, file=sys.stderr)
        return 33
    except CorpusInvalido as e:
        print("CORPUS INVALIDO: %s" % e, file=sys.stderr)
        return 34

    ruta_man = ruta_manifiesto(args.corpus)
    if args.comprobar:
        if not os.path.exists(ruta_man):
            print("MANIFIESTO AUSENTE: %s" % ruta_man, file=sys.stderr)
            return 1
        with open(ruta_man, "r", encoding="utf-8") as f:
            previo = json.load(f)
        desfases = comprobar(manifiesto, previo)
        for clave, declarado, medido in desfases:
            print("DESFASE %s: manifiesto=%r medido=%r"
                  % (clave, declarado, medido))
        if desfases:
            print("%d celdas desfasadas en %s" % (len(desfases), ruta_man),
                  file=sys.stderr)
            return 1
        print("MANIFIESTO COINCIDE: %d celdas medidas, sha256 %s"
              % (len(manifiesto), manifiesto["sha256"][:16]))
        return 0

    ruta = escribir(args.corpus, manifiesto)
    print("MANIFIESTO ESCRITO: %s" % ruta)
    print("  paquete   : %s" % manifiesto["paquete"])
    print("  sha256    : %s" % manifiesto["sha256"])
    print("  bytes     : %d" % manifiesto["bytes"])
    print("  archivos  : %d" % manifiesto["n_archivos"])
    print("  imports   : %d" % manifiesto["n_imports"])
    print("  nodos     : %d" % manifiesto["n_nodos"])
    print("  modalidades: %s" % json.dumps(manifiesto["modalidades"],
                                           sort_keys=True))
    for clave in sorted(k for k in manifiesto if k.startswith("impacto_")):
        print("  %-10s: runtime=%d solo_type_checking=%d"
              % (clave, manifiesto[clave]["runtime"],
                 manifiesto[clave]["solo_type_checking"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
