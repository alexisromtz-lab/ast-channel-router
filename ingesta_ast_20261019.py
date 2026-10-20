#!/usr/bin/env python3
# HUELLA-INGESTA-AST-20261019
"""Ingesta AST: de codigo real a nodos con canales duros (simbolo · ruta · excepcion).

QUE HACE
  Recorre un paquete Python instalado, parsea cada archivo con `ast` y emite un
  nodo por clase / funcion / metodo con:
    rel        ruta relativa al paquete (canal `rutas`)
    qual       nombre calificado (canal `simbolos`, el que trae la traza)
    params     parametros (canal `simbolos`)
    dec        decoradores (canal `simbolos`)
    raises     excepciones lanzadas, con linea (canal `excepciones`)
    catches    excepciones atrapadas (canal `excepciones`)
    calls      callees resueltos por nombre (arista del grafo de simbolos)
    doc, seg   docstring y fuente del nodo (canal `prosa`)
  El grafo de simbolos es la lista de aristas `nodo -> callee` y
  `nodo -> excepcion`; el banco de consultas del eval se DERIVA de las aristas
  `raises`, no de prosa escrita a mano.

POR QUE ES DETERMINISTA
  Se recorre con os.walk ordenado, se ordena por (rel, linea, qual) y no se
  escribe hora dentro del objeto. Dos corridas dan el mismo JSON byte a byte;
  el eval lo verifica comparando dos corridas.

QUE NO HACE
  No resuelve imports: `calls` es el nombre tal como aparece (`yaml.error.X`
  se guarda como `X` y como `yaml.error.X`). No hay inferencia de tipos.
  Para lenguajes que no son Python no hay AST aqui: se declara `soportado:
  False` en vez de inventar simbolos con una regex que se haria pasar por AST.

Uso:
    python3 sim/ingesta_ast_20261019.py --paquete yaml
    python3 sim/ingesta_ast_20261019.py --paquete yaml --json
RC: 0 ok · 2 paquete ausente o sin nodos
"""

import argparse
import ast
import hashlib
import json
import os
import sys

# Corte publico: arbol PLANO; el original vivia un nivel abajo (RAIZ/sim).
HUELLA = "HUELLA-INGESTA-AST-20261019"
RAIZ = os.path.dirname(os.path.abspath(__file__))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import canales_v5_20261019 as CH  # noqa: E402  los canales, importados

SITE = os.path.join(RAIZ, ".venv", "lib",
                    "python%d.%d" % sys.version_info[:2], "site-packages")


def _nombre_exc(nodo):
    if isinstance(nodo, ast.Call):
        nodo = nodo.func
    if isinstance(nodo, ast.Name):
        return nodo.id
    if isinstance(nodo, ast.Attribute):
        return nodo.attr
    return None


def _segmento(lineas, nodo):
    ini = (nodo.lineno or 1) - 1
    fin = getattr(nodo, "end_lineno", None) or nodo.lineno or 1
    return "\n".join(lineas[ini:fin])


def _recorrer(nodo, prefijo, rel, lineas, salida):
    for hijo in getattr(nodo, "body", []):
        if isinstance(hijo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            qual = prefijo + hijo.name
            if isinstance(hijo, ast.ClassDef):
                _recorrer(hijo, qual + ".", rel, lineas, salida)
                continue
            raises, catches, calls = [], [], set()
            for m in ast.walk(hijo):
                if isinstance(m, ast.Raise) and m.exc is not None:
                    nombre = _nombre_exc(m.exc)
                    if nombre:
                        raises.append({"exc": nombre, "linea": m.lineno - hijo.lineno + 1})
                elif isinstance(m, ast.ExceptHandler) and m.type is not None:
                    nombre = _nombre_exc(m.type)
                    if nombre:
                        catches.append({"exc": nombre, "linea": m.lineno - hijo.lineno + 1})
                elif isinstance(m, ast.Call):
                    f = m.func
                    if isinstance(f, ast.Name):
                        calls.add(f.id)
                    elif isinstance(f, ast.Attribute):
                        calls.add(f.attr)
            salida.append({
                "rel": rel, "qual": qual, "linea": hijo.lineno,
                "fin": getattr(hijo, "end_lineno", hijo.lineno),
                "dec": [getattr(d, "id", None) or getattr(d, "attr", None)
                        for d in hijo.decorator_list],
                "params": [a.arg for a in list(hijo.args.args) + list(hijo.args.kwonlyargs)],
                "raises": sorted(raises, key=lambda x: (x["linea"], x["exc"])),
                "catches": sorted(catches, key=lambda x: (x["linea"], x["exc"])),
                "calls": sorted(calls),
                "doc": ast.get_docstring(hijo) or "",
                "seg": _segmento(lineas, hijo),
            })
            _recorrer(hijo, qual + ".", rel, lineas, salida)


def ingerir_paquete(paquete, base=SITE):
    raiz = os.path.join(base, paquete)
    if not os.path.isdir(raiz):
        return None
    archivos, nodos = [], []
    for r, dirs, ficheros in os.walk(raiz):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "__pycache__")
        for nombre in sorted(ficheros):
            if not nombre.endswith(".py"):
                continue
            ruta = os.path.join(r, nombre)
            rel = os.path.relpath(ruta, raiz).replace(os.sep, "/")
            with open(ruta, "rb") as f:
                datos = f.read()
            archivos.append({"rel": rel,
                             "sha256": hashlib.sha256(datos).hexdigest(),
                             "bytes": len(datos)})
            try:
                arbol = ast.parse(datos.decode("utf-8", "replace"))
            except SyntaxError:
                continue
            lineas = datos.decode("utf-8", "replace").splitlines()
            antes = len(nodos)
            _recorrer(arbol, "", rel, lineas, nodos)
            archivos[-1]["nodos"] = len(nodos) - antes
    nodos.sort(key=lambda n: (n["rel"], n["linea"], n["qual"]))
    return {"esquema": "ingesta_ast/v1", "huella": HUELLA, "paquete": paquete,
            "raiz": os.path.relpath(raiz, RAIZ), "n_archivos": len(archivos),
            "n_nodos": len(nodos), "archivos": archivos, "nodos": nodos}


def canales_de_nodo(nodo):
    """Canales del lado DOCUMENTO para un nodo: estructura del AST + cuerpo."""
    base = CH.extraer((nodo.get("seg") or "") + "\n" + (nodo.get("doc") or ""))
    rel = nodo.get("rel") or ""
    partes = [p for p in rel.split("/") if p]
    CH.sumar_ruta(base, partes)
    if partes and "." in partes[-1]:
        CH.sumar_ruta(base, [partes[-1].rsplit(".", 1)[0]])
    qual = nodo.get("qual") or ""
    for p in qual.split("."):
        if p:
            norm = CH._simbolo_valido(p)
            if norm:
                base["simbolos"].add(norm)
    base["simbolos"].add(qual)
    for p in nodo.get("params") or []:
        norm = CH._simbolo_valido(p)
        if norm:
            base["simbolos"].add(norm)
    for d in nodo.get("dec") or []:
        norm = CH._simbolo_valido(d) if d else None
        if norm:
            base["simbolos"].add(norm)
    for c in nodo.get("calls") or []:
        norm = CH._simbolo_valido(c)
        if norm:
            base["simbolos"].add(norm)
    for r in nodo.get("raises") or []:
        exc = (r.get("exc") or "").lower()
        if exc:
            (base["excepciones_genericas"] if exc in CH.GENERICAS else base["excepciones"]).add(exc)
    for r in nodo.get("catches") or []:
        exc = (r.get("exc") or "").lower()
        if exc:
            (base["excepciones_genericas"] if exc in CH.GENERICAS else base["excepciones"]).add(exc)
    return base


def clave_de_nodo(nodo):
    return "%s::%s" % (nodo["rel"], nodo["qual"])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ingesta_ast_20261019.py")
    ap.add_argument("--paquete", default="yaml")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    corpus = ingerir_paquete(a.paquete)
    if not corpus or not corpus["n_nodos"]:
        print("ERROR: paquete ausente o sin nodos: %s" % a.paquete, file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(corpus, ensure_ascii=False, indent=1, sort_keys=True))
        return 0
    con_raise = [n for n in corpus["nodos"] if n["raises"]]
    print("PAQUETE %s  archivos=%d nodos=%d con_raise=%d raise_sites=%d"
          % (corpus["paquete"], corpus["n_archivos"], corpus["n_nodos"],
             len(con_raise), sum(len(n["raises"]) for n in con_raise)))
    print("ARISTAS nodo->callee=%d  nodo->excepcion=%d"
          % (sum(len(n["calls"]) for n in corpus["nodos"]),
             sum(len(n["raises"]) for n in corpus["nodos"])))
    for n in con_raise[:5]:
        print("  %-52s raises=%s" % (clave_de_nodo(n),
                                     ",".join(sorted({r["exc"] for r in n["raises"]}))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
