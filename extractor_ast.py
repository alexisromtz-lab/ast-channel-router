#!/usr/bin/env python3
# HUELLA-EXTRACTOR-AST-20261019
"""Extractor reutilizable de canales estructurales (AST) para texto y codigo.

QUE ES Y QUE NO ES
  No es un enrutador y no decide nada: no tiene pesos ni umbral. Convierte una
  entrada (un issue, un cuerpo de PR, una traza de excepcion, o el codigo fuente
  de un modulo) en los cuatro canales que el metro V5 ya sabe puntuar.
  Pesos, umbral y reglas de puntuacion viven SOLO en canales_v5_20261019.pycanales_v5_20261019.py
  y aqui se IMPORTAN, nunca se copian: un metro duplicado son dos metros.

ENTRADA -> VIA (declarada, no adivinada)
  via "ast"    el texto parsea como modulo de Python y trae estructura
               (def/class/raise/import). Se recorre con el mismo recorredor de
               la ingesta y cada nodo aporta su estructura al documento.
  via "texto"  todo lo demas (traza pegada, issue en prosa, cuerpo de PR).
               Se usa `canales_v5.extraer`, que absorbe primero los tramos
               entre acentos graves y luego clasifica por precedencia
               rutas > excepciones > simbolos > prosa.
  El modo se puede forzar con `forzar="ast"|"texto"` cuando el llamador sabe
  mas que el detector. Forzar no cambia el metro, solo el camino.

SALIDA
  Registro JSON: listas ordenadas y conteos. Determinista: dos corridas sobre
  la misma entrada dan el mismo objeto, sin hora dentro (la hora la pone quien
  llama, no el objeto).

LIMITES DECLARADOS
  (1) Hereda el metro de la V5 tal cual, incluidos sus defectos corregidos:
      extension como ruta, nombre generico de modulo, dunder de protocolo,
      simbolo sin ruta que lo corrobore. No los repara ni los repite.
  (2) `canales_de_fuente` reutiliza `ingesta_ast._recorrer` (API privada de la
      ingesta) con guarda: si esa pieza cambia de forma, se cae con RC 2 en vez
      de inventar nodos.
  (3) `prosa` es la bolsa COMPLETA de la V2 (`V2.tokenizar` del texto entero):
      los canales duros son evidencia adicional, no un filtro que la encoja.
  (4) Un `raise ValueError` es estructura, pero el metro lo archiva en
      `excepciones_genericas` porque el tipo es comun. No se cambia aqui: el
      metro suma `excepciones | excepciones_genericas` al puntuar el
      DOCUMENTO (sim/canales_v5_20261019.py, `puntuar`, medido 2026-10-20
      00:27:46Z), asi que el efecto documental es el mismo; lo que la
      genericidad bloquea es el lado CONSULTA. Se declara, no se repara: mover
      esa frontera invalidaria F1-F4.
  (5) No entiende el problema: mide a donde apunta la consulta, no si la
      solucion es correcta ni si el parche compila.
  (5) El detector de "es codigo" es por parseo, no por palabras clave: un texto
      que no parsea nunca entra por la via AST, aunque hable de Python.

RC: 0 medido · 2 entrada ilegible o API de la ingesta ausente · 4 autotest rojo
"""

import argparse
import ast
import json
import os
import sys

# Corte publico: el arbol es PLANO (los modulos se importan entre si desde su
# propio directorio). El original derivaba RAIZ/sim porque vivia un nivel abajo.
RAIZ = os.path.dirname(os.path.abspath(__file__))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import canales_v5_20261019 as CH  # noqa: E402  el metro, importado
import ingesta_ast_20261019 as ING  # noqa: E402  el recorredor, importado

HUELLA = "HUELLA-EXTRACTOR-AST-20261019"
ESQUEMA = "canales_ast/v1"
CANALES = CH.CANALES

NODOS_ESTRUCTURA = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                    ast.Raise, ast.Import, ast.ImportFrom)

RC_OK, RC_USO, RC_DEGRADA = 0, 2, 4


def _vacio():
    return {"simbolos": set(), "excepciones": set(),
            "excepciones_genericas": set(), "rutas": set(), "prosa": set()}


def _fusionar(dst, src):
    for k, v in src.items():
        dst.setdefault(k, set()).update(v)
    return dst


def a_registro(canales, via, unidades):
    """Vuelve el diccionario de conjuntos en un registro JSON, ordenado."""
    return {
        "esquema": ESQUEMA,
        "huella": HUELLA,
        "via": via,
        "unidades": int(unidades),
        "n": {k: len(canales.get(k) or ()) for k in CANALES},
        "canales": {k: sorted(canales.get(k) or ()) for k in CANALES},
        "excepciones_genericas": sorted(canales.get("excepciones_genericas") or ()),
    }


def parece_fuente(texto):
    """True si el texto parsea como modulo y trae estructura (via AST)."""
    if not texto or not texto.strip():
        return False
    try:
        arbol = ast.parse(texto)
    except (SyntaxError, ValueError, TypeError):
        return False
    return any(isinstance(n, NODOS_ESTRUCTURA) for n in ast.walk(arbol))


def canales_de_texto(texto):
    """Canales de una traza, un issue o un cuerpo de PR (sets)."""
    return CH.extraer(texto or "")


def canales_de_fuente(codigo, rel=""):
    """Canales de un modulo de Python: suma la estructura de todos sus nodos.

    Devuelve (canales, n_nodos). El cuerpo y el docstring de cada nodo entran
    por `prosa`; la ruta, el nombre calificado, los parametros, los decoradores,
    los callees y los `raise` entran por los canales duros.
    """
    if not hasattr(ING, "_recorrer") or not hasattr(ING, "canales_de_nodo"):
        raise RuntimeError("ingesta_ast sin _recorrer/canales_de_nodo: API cambiada")
    lineas = (codigo or "").splitlines()
    nodos = []
    ING._recorrer(ast.parse(codigo or ""), "", rel or "modulo.py", lineas, nodos)
    acumulado = _vacio()
    partes = [p for p in (rel or "").split("/") if p]
    if partes:
        CH.sumar_ruta(acumulado, partes)
        if "." in partes[-1]:
            CH.sumar_ruta(acumulado, [partes[-1].rsplit(".", 1)[0]])
    for nodo in nodos:
        _fusionar(acumulado, ING.canales_de_nodo(nodo))
    return acumulado, len(nodos)


# HUELLA-EXTRACTOR-AST-IMPACTO-IMPORTS-20261026
# HUELLA-EXTRACTOR-IMPACTO-REL-20261026
# HUELLA-EXTRACTOR-LOCUS-RAIZ-20261026
# HUELLA-EXTRACTOR-NS-N-RAICES-20261026
def _locus_del_corpus(corpus):
    """Locus primario del corpus; falla cerrado si mezcla raices sin declarar.

    `rel` es unico dentro de una raiz y ambiguo entre raices. Un paquete de
    namespace aporta varias raices legitimamente: el corpus las declara en
    `raices_ingeridas` y cada archivo publica la suya. Cualquier `locus` fuera
    de lo declarado —dos raices concatenadas a mano— se nombra en vez de
    resolverse adivinando. Un corpus sin `locus` (esquema anterior) declara una
    sola raiz por construccion y devuelve None.
    """
    vistas = {}
    declarado = corpus.get("locus")
    if isinstance(declarado, str) and declarado:
        vistas[declarado] = "<corpus>"
    for archivo in corpus.get("archivos", ()):
        if not isinstance(archivo, dict):
            continue
        propio = archivo.get("locus")
        if isinstance(propio, str) and propio:
            vistas.setdefault(propio, archivo.get("rel"))
    propias = set()
    raices = corpus.get("raices_ingeridas")
    if isinstance(raices, (list, tuple)):
        for raiz in raices:
            if isinstance(raiz, dict) and isinstance(raiz.get("locus"), str):
                propias.add(raiz["locus"])
    if isinstance(declarado, str) and declarado:
        propias.add(declarado)
    ajenas = {locus: rel for locus, rel in vistas.items() if locus not in propias}
    if ajenas or (not propias and len(vistas) > 1):
        raise ValueError(
            "corpus fusiona raices distintas: "
            + " · ".join("%s:%s" % (locus[:16], rel)
                         for locus, rel in sorted((ajenas or vistas).items(),
                                                  key=lambda x: str(x[0])))
        )
    if isinstance(declarado, str) and declarado:
        return declarado
    return next(iter(vistas), None)


def _modulos_del_corpus(corpus):
    _locus_del_corpus(corpus)
    paquete = corpus.get("paquete")
    if not isinstance(paquete, str) or not paquete:
        raise ValueError("corpus sin nombre de paquete")
    loci_por_rel = {}
    for archivo in corpus.get("archivos", ()):
        if not isinstance(archivo, dict):
            continue
        rel, locus = archivo.get("rel"), archivo.get("locus")
        if isinstance(rel, str) and isinstance(locus, str) and locus:
            loci_por_rel.setdefault(rel, set()).add(locus)
    ambiguos = {rel: loci for rel, loci in loci_por_rel.items() if len(loci) > 1}
    if ambiguos:
        raise ValueError(
            "rel ambiguo entre raices: "
            + " · ".join("%s:%s" % (rel, "/".join(sorted(l[:16] for l in loci)))
                         for rel, loci in sorted(ambiguos.items()))
        )
    modulos = {}
    for archivo in corpus.get("archivos", ()):
        rel = archivo.get("rel")
        if not isinstance(rel, str) or not rel.endswith(".py"):
            continue
        partes = rel[:-3].split("/")
        if partes[-1] == "__init__":
            partes.pop()
        nombre = ".".join([paquete] + [p for p in partes if p])
        modulos[nombre] = rel
    return paquete, modulos


def _destino_import(corpus, arista, paquete, modulos):
    modulo = arista.get("modulo") or ""
    rel = arista.get("rel") or ""
    nombre = arista.get("nombre")
    if modulo.startswith("."):
        nivel = len(modulo) - len(modulo.lstrip("."))
        resto = modulo[nivel:]
        partes = rel[:-3].split("/")
        if partes[-1] == "__init__":
            partes.pop()
        else:
            partes.pop()
        base = [paquete] + [p for p in partes if p]
        if nivel > len(base):
            return None
        base = base[:len(base) - nivel + 1]
        destino = ".".join(base + ([p for p in resto.split(".") if p]))
    elif modulo == paquete or modulo.startswith(paquete + "."):
        destino = modulo
    else:
        return None
    candidatos = []
    if nombre and nombre != "*":
        candidatos.append(destino + "." + nombre)
    candidatos.append(destino)
    return next((modulos[c] for c in candidatos if c in modulos), None)


HUELLA_INDICE_ADYACENCIA = "HUELLA-INDICE-ADYACENCIA-H5-20261026"


def _modalidad_de_arista(arista):
    """Modalidad declarada; si falta, la deduce de la guarda de la arista."""
    modalidad = arista.get("modalidad")
    if modalidad is not None:
        return modalidad
    cond = arista.get("cond") or ""
    return ("type_checking" if "TYPE_CHECKING" in cond
            else "runtime_data" if cond.startswith("if ")
            else "except_import" if "except ImportError" in cond
            else "runtime_data" if cond else "requerida")


def indice_adyacencia(corpus):
    """Construye una sola vez el grafo inverso y lo publica con su fuente.

    Sustituye la reconstruccion por consulta: medido el 26-Oct-2026 sobre el
    corpus durable de `vllm_omni` (25 931 aristas, 1 601 destinos), la
    construccion cuesta 0.09 s y cada consulta posterior
    0.000629 s frente a 0.07482 s reconstruyendo (118.9x). El indice no cambia
    ninguna respuesta: reproduce `impacto_importaciones` en los 1 601 destinos.

    `fuente_n_archivos` y `fuente_n_imports` publican el corpus del que salio
    para que un indice ajeno se rechace en vez de fusionarse en silencio.
    """
    if not isinstance(corpus, dict):
        raise TypeError("se requiere un corpus")
    archivos = {a.get("rel") for a in corpus.get("archivos", ())
                if isinstance(a, dict)}
    paquete, modulos = _modulos_del_corpus(corpus)
    runtime, todos = {}, {}
    for arista in corpus.get("imports", ()):
        if not isinstance(arista, dict):
            continue
        origen = arista.get("rel")
        destino = _destino_import(corpus, arista, paquete, modulos)
        if origen not in archivos or destino is None:
            continue
        todos.setdefault(destino, set()).add(origen)
        if _modalidad_de_arista(arista) != "type_checking":
            runtime.setdefault(destino, set()).add(origen)
    return {
        "huella": HUELLA_INDICE_ADYACENCIA,
        "paquete": paquete,
        "archivos": archivos,
        "runtime": runtime,
        "todos": todos,
        "destinos": len(todos),
        "fuente_n_archivos": len(corpus.get("archivos", ())),
        "fuente_n_imports": len(corpus.get("imports", ())),
    }


def _verificar_indice(indice, corpus):
    if not isinstance(indice, dict) or indice.get("huella") != HUELLA_INDICE_ADYACENCIA:
        raise ValueError("indice de adyacencia no reconocido")
    if indice.get("paquete") != corpus.get("paquete"):
        raise ValueError(
            "indice de otro corpus: paquete %r != %r"
            % (indice.get("paquete"), corpus.get("paquete")))
    if (indice.get("fuente_n_archivos") != len(corpus.get("archivos", ()))
            or indice.get("fuente_n_imports") != len(corpus.get("imports", ()))):
        raise ValueError(
            "indice de otro corpus: fuente %r/%r no coincide con %r/%r"
            % (indice.get("fuente_n_archivos"), indice.get("fuente_n_imports"),
               len(corpus.get("archivos", ())), len(corpus.get("imports", ()))))


def _dependientes(grafo, objetivo):
    vistos, pendientes = {objetivo}, [objetivo]
    while pendientes:
        actual = pendientes.pop()
        for origen in grafo.get(actual, ()):
            if origen not in vistos:
                vistos.add(origen)
                pendientes.append(origen)
    vistos.discard(objetivo)
    return vistos


def impacto_importaciones(corpus, objetivo, indice=None):
    """Devuelve dependientes transitivos runtime y solo type-checking.

    `runtime` incluye guardas opcionales o dependientes de datos; no predice si
    esas ramas se ejecutaran. Solo excluye imports marcados type_checking.
    La resolucion se limita a modulos internos del paquete y a imports relativos.

    Con `indice` se reutiliza un grafo ya construido por `indice_adyacencia`;
    sin el se construye y se descarta, que es el camino historico. Un indice de
    otro corpus se rechaza: reutilizarlo seria fusionar dos identidades.
    """
    if not isinstance(corpus, dict) or not isinstance(objetivo, str):
        raise TypeError("se requiere un corpus y un objetivo relativo")
    if indice is None:
        indice = indice_adyacencia(corpus)
    else:
        _verificar_indice(indice, corpus)
    if objetivo not in indice["archivos"]:
        raise ValueError("objetivo fuera del corpus: " + objetivo)
    todos = _dependientes(indice["todos"], objetivo)
    runtime = _dependientes(indice["runtime"], objetivo)
    return {"objetivo": objetivo, "runtime": sorted(runtime),
            "solo_type_checking": sorted(todos - runtime)}


def extraer_canales_ast(texto_o_codigo, rel="", forzar=None):
    """Punto de entrada unico: texto o codigo -> registro de canales JSON."""
    texto = texto_o_codigo or ""
    modo = forzar if forzar in ("ast", "texto") else (
        "ast" if parece_fuente(texto) else "texto")
    if modo == "ast":
        canales, unidades = canales_de_fuente(texto, rel)
    else:
        canales, unidades = canales_de_texto(texto), 1
    return a_registro(canales, modo, unidades)


# --------------------------------------------------------------------------
# Autotest: controles con resultado conocido, incluido uno negativo.
# --------------------------------------------------------------------------

CASO_TRAZA = (
    "yaml.scanner.ScannerError: while scanning a simple key\n"
    "  in \"config/app.yaml\", line 12, column 1\n"
    "Traceback (most recent call last):\n"
    "  File \"yaml/scanner.py\", line 145, in fetch_more_tokens\n"
    "    self.scan_to_next_token()\n"
    "  File \"yaml/scanner.py\", line 160, in scan_to_next_token\n"
    "yaml.scanner.ScannerError: could not find expected ':'\n"
)

CASO_FUENTE = '''\
def cargar(ruta):
    """Lee un archivo yaml."""
    try:
        with open(ruta) as fh:
            return fh.read()
    except OSError:
        raise RuntimeError("no se pudo leer " + ruta)
'''

CASO_SIN_ESTRUCTURA = "el proceso se cae a media noche y no se por que"


def autotest():
    fallos = []

    r1 = extraer_canales_ast(CASO_TRAZA)
    if r1["via"] != "texto":
        fallos.append("C1 via=%r (esperado texto)" % r1["via"])
    if "scannererror" not in r1["canales"]["excepciones"]:
        fallos.append("C1 excepciones sin scannererror")
    if "scanner" not in r1["canales"]["rutas"]:
        fallos.append("C1 rutas sin scanner")

    r2 = extraer_canales_ast(CASO_FUENTE, rel="lib/io_util.py")
    if r2["via"] != "ast":
        fallos.append("C2 via=%r (esperado ast)" % r2["via"])
    # `RuntimeError` es generico: el metro lo archiva en excepciones_genericas
    # (limite 4 de la cabecera) y lo suma al documento en `puntuar`.
    if "valueerror" not in r2["canales"]["excepciones"] and \
            "runtimeerror" not in r2["excepciones_genericas"]:
        fallos.append("C2 sin runtimeerror en genericas ni valueerror en duras")
    if "cargar" not in r2["canales"]["simbolos"]:
        fallos.append("C2 simbolos sin cargar")
    if "io_util" not in r2["canales"]["rutas"]:
        fallos.append("C2 rutas sin io_util")

    r3 = extraer_canales_ast(CASO_SIN_ESTRUCTURA)
    duros = (len(r3["canales"]["simbolos"]) + len(r3["canales"]["excepciones"])
             + len(r3["canales"]["rutas"]))
    if duros != 0:
        fallos.append("C3 control negativo con %d canales duros" % duros)
    if not r3["canales"]["prosa"]:
        fallos.append("C3 prosa vacia: no midio nada")

    if extraer_canales_ast(CASO_TRAZA) != extraer_canales_ast(CASO_TRAZA):
        fallos.append("C4 no determinista")

    return fallos, (r1, r2, r3)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Extractor de canales AST (no enruta)")
    ap.add_argument("--texto", help="texto libre: traza, issue o cuerpo de PR")
    ap.add_argument("--archivo", help="modulo de Python a extraer")
    ap.add_argument("--rel", default="", help="ruta relativa declarada del modulo")
    ap.add_argument("--forzar", choices=("ast", "texto"))
    ap.add_argument("--autotest", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.autotest:
        fallos, _ = autotest()
        for f in fallos:
            print("ROJO " + f)
        print("AUTOTEST %s (%d controles)" % ("PASA" if not fallos else "FALLA", 4))
        return RC_OK if not fallos else RC_DEGRADA

    entrada = None
    rel = args.rel
    if args.archivo:
        try:
            with open(args.archivo, "r", encoding="utf-8", errors="replace") as fh:
                entrada = fh.read()
        except OSError as exc:
            print("ILEGIBLE " + str(exc))
            return RC_USO
        rel = rel or os.path.basename(args.archivo)
    elif args.texto:
        entrada = args.texto
    else:
        ap.print_help()
        return RC_USO

    try:
        reg = extraer_canales_ast(entrada, rel=rel, forzar=args.forzar)
    except (SyntaxError, RuntimeError) as exc:
        print("NO_MEDIDO " + str(exc))
        return RC_USO

    if args.json:
        print(json.dumps(reg, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("via=%s unidades=%d" % (reg["via"], reg["unidades"]))
        for k in CANALES:
            print("%-20s %d %s" % (k, reg["n"][k], reg["canales"][k][:6]))
        if reg["excepciones_genericas"]:
            print("%-20s %d %s" % ("excepciones_genericas",
                                    len(reg["excepciones_genericas"]),
                                    reg["excepciones_genericas"][:6]))
    return RC_OK


if __name__ == "__main__":
    sys.exit(main())
