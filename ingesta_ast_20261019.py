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
  Las declaraciones anidadas en un bloque (`if`/`try`/`for`/`while`/`with`) se
  ingieren igual que las del cuerpo del modulo, y cada nodo acredita solo sus
  propios canales: no hereda los `raise`/`call` de una def interna.
  Un archivo que no parsea NO se suprime: `n_archivos` cuenta el disco, el
  archivo queda en `archivos` con `nodos: None` e `ilegible: SyntaxError`, y
  se publica en `n_ilegibles` / `ilegibles` con linea y motivo. Asi el
  descarte es un numero medido y no un silencio.
  El grafo de simbolos es la lista de aristas `nodo -> callee` y
  `nodo -> excepcion`; el banco de consultas del eval se DERIVA de las aristas
  `raises`, no de prosa escrita a mano.
  El grafo de importaciones se emite como arista del corpus (`imports`), no
  como campo del nodo: medido 26-Oct-2026 sobre el corpus declarado, 5 150 de
  5 657 imports (91%) viven a nivel modulo y no tienen nodo al que colgarse, y
  56 de los condicionales estan en ese estrato. Un campo por nodo publicaria
  el 9% del objeto. Cada arista lleva `qual` (la declaracion que la encierra,
  o None a nivel modulo), `cond` (la guarda `if <test>` o `except <tipos>` que
  la hace condicional, o None) y la terna `modulo`/`nombre`/`asname`. `n_imports`
  y `n_imports_cond` publican el denominador, para que el descarte sea un numero
  medido y no un silencio.
  Cada entrada de `archivos` publica `puntos_ciegos`: señales sintacticas para
  `__getattr__` de modulo, `importlib.import_module` y `globals()[...]`. Un
  archivo parseado sin esos patrones lleva `[]`; uno ilegible lleva `None`.
  Son indicadores de posible resolucion dinamica, no destinos resueltos ni un
  veredicto de comportamiento en runtime.
  El paquete no se busca en una ruta clavada: se pregunta a `importlib` donde
  vive el paquete QUE CORRE EN ESTE INTERPRETE (`resolver_raiz`). Si el nombre
  no resuelve, la causa se nombra (`AUSENTE` · `NO_ES_PAQUETE` ·
  `RUTA_EXPLICITA_AUSENTE`) y no se confunde con un paquete que si existe pero
  no rinde nodos (`SIN_NODOS` · `SIN_NODOS_ILEGIBLES`). Cada causa tiene su RC.

POR QUE ES DETERMINISTA
  Se recorre con os.walk ordenado, se ordena por (rel, linea, qual) y no se
  escribe hora dentro del objeto. Dos corridas dan el mismo JSON byte a byte;
  el eval lo verifica comparando dos corridas.

QUE NO HACE
  No resuelve imports ni atributos dinamicos: `puntos_ciegos` solo declara
  patrones observables en el AST; no afirma a que modulo o simbolo apuntan.
  `calls` es el nombre tal como aparece (`yaml.error.X` se guarda como `X` y
  como `yaml.error.X`). No hay inferencia de tipos.
  La guarda de una arista de import se lee del cuerpo de `if` y de `try` (y de
  `try*` cuando el interprete lo tiene: en 3.10 un `except*` no parsea, asi que
  no hay nada que medir); un import en `else`/`finally`/`except` se publica con
  `cond: None` (tambien se ejecuta condicionalmente, pero no por la guarda que
  aqui se mide), y no hay transitividad: la arista dice que A importa B, no si
  B se puede importar.
  Para lenguajes que no son Python no hay AST aqui: se declara `soportado:
  False` en vez de inventar simbolos con una regex que se haria pasar por AST.
  No adivina rutas de instalacion: resuelve contra `sys.path` del interprete
  que lo corre, asi que un paquete instalado en OTRO interprete no se ve (se
  declara `AUSENTE`, no se busca a ciegas en el disco). Un modulo suelto (un
  `.py`, no un paquete) no se puede recorrer: se declara `NO_ES_PAQUETE`.

LOCUS DE RAIZ
  La identidad de un archivo es el par (locus, rel): `rel` es la ruta relativa
  a la raiz ingerida y `locus` es el sha256 de la raiz ABSOLUTA resuelta con
  `realpath`. Dos paquetes homonimos en raices distintas —o dos copias del
  mismo paquete— publican el mismo `paquete` y los mismos `rel`; solo el
  `locus` los distingue. El sobre publica el `locus` de la raiz primaria y cada
  entrada de `archivos` repite el de SU raiz, para que un corpus que concatene
  raices sin declararlas sea detectable (el consumidor lo rechaza) en vez de
  silencioso. `raiz` es la ruta absoluta resuelta; `raiz_rel` es la relativa al
  checkout de la herramienta y es informativa: cambia si el corpus viaja a otra
  maquina. Un corpus sin `locus` (esquema anterior) sigue siendo legible: la
  ausencia no es ambigua porque ese corpus declara una sola raiz.

RAICES DE NAMESPACE
  Un paquete de namespace puede vivir en varias entradas de `sys.path`. La
  ingesta recorre TODAS las raices declaradas —cada una con su propio `locus`—
  y las publica en `raices_ingeridas` (raiz, locus y n_archivos por raiz);
  `raices_declaradas` conserva todas las rutas. `raices_omitidas` queda vacia
  para un namespace bien formado: solo nombra una raiz declarada que dejo de
  ser directorio entre la resolucion y el recorrido. Un `rel` presente en dos
  raices no se resuelve adivinando: el consumidor falla cerrado con `rel
  ambiguo entre raices`. Con `base` explicito hay una sola raiz.

Uso:
    python3 ingesta_ast_20261019.py --paquete json
    python3 ingesta_ast_20261019.py --paquete json --json
    python3 ingesta_ast_20261019.py --paquete _pytest --site /ruta/site-packages
RC: 0 ok (publicando `n_ilegibles` cuando los hay)
    2 paquete no ingerible (AUSENTE · NO_ES_PAQUETE · RUTA_EXPLICITA_AUSENTE)
    3 paquete ingerible sin nodos (SIN_NODOS · SIN_NODOS_ILEGIBLES)
"""

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import sys

# Corte publico: arbol PLANO; el original vivia un nivel abajo (RAIZ/sim).
HUELLA = "HUELLA-INGESTA-AST-20261019"
RAIZ = os.path.dirname(os.path.abspath(__file__))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import canales_v5_20261019 as CH  # noqa: E402  los canales, importados

# HUELLA-INGESTA-AST-SITE-20261025
def resolver_raiz(paquete, base=None):
    """Directorio del paquete a ingerir, o (None, causa) si no lo hay.

    `base` explicito conserva la semantica de ruta: la raiz es base/paquete.
    Con base=None no se adivina ninguna ruta: se pregunta a `importlib` donde
    vive el paquete en el interprete activo. Cada fallo se nombra en vez de
    devolver un None mudo.
    """
    if base is not None:
        raiz = os.path.join(base, paquete)
        if not os.path.isdir(raiz):
            return None, "RUTA_EXPLICITA_AUSENTE"
        return raiz, None
    try:
        spec = importlib.util.find_spec(paquete)
    except (ImportError, ValueError):
        return None, "IMPORT_NO_RESUELVE"
    if spec is None:
        return None, "AUSENTE"
    for loc in list(spec.submodule_search_locations or []):
        if os.path.isdir(loc):
            return loc, None
    return None, "NO_ES_PAQUETE"


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


# HUELLA-INGESTA-AST-BLOQUES-20261025
# HUELLA-INGESTA-AST-ILEGIBLES-20261025
# HUELLA-INGESTA-AST-IMPORTS-20261026
# HUELLA-INGESTA-AST-TRYSTAR-20261026
# HUELLA-INGESTA-AST-MODALIDAD-20261026
DECLARABLES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
# `try*` existe desde 3.11 y el corte publico declara >=3.8: se nombra sin romper 3.10.
TIPOS_TRY = (ast.Try, ast.TryStar) if hasattr(ast, "TryStar") else (ast.Try,)


def _declaraciones(nodo):
    """Defs y clases de cualquier bloque (if/try/for/while/with), sin entrar en ellos.

    `nodo.body` solo expone los hijos directos: un `def` bajo un
    `if sys.platform == ...` o bajo un `try/except` de respaldo desaparecia sin
    dejar rastro (medido 25-Oct-2026: 3 de 3 perdidas). Aqui se desciende por
    los bloques y se corta en cada declaracion, que se recorre por su rama.
    """
    for hijo in ast.iter_child_nodes(nodo):
        if isinstance(hijo, DECLARABLES):
            yield hijo
        else:
            yield from _declaraciones(hijo)


def _walk_propio(nodo):
    """Descendientes de `nodo` sin cruzar el limite de una declaracion anidada.

    `ast.walk` entra en las defs internas y acredita sus `raise`/`call` tambien
    al nodo externo: la misma excepcion contaba dos veces (medido 25-Oct-2026).
    """
    pila = [nodo]
    while pila:
        actual = pila.pop()
        yield actual
        for hijo in ast.iter_child_nodes(actual):
            if not isinstance(hijo, DECLARABLES):
                pila.append(hijo)


def _padres(arbol):
    """Mapa hijo -> (padre, campo) para poder subir la cadena de guardas."""
    mapa = {}
    for nodo in ast.walk(arbol):
        for campo, valor in ast.iter_fields(nodo):
            if isinstance(valor, list):
                for h in valor:
                    if isinstance(h, ast.AST):
                        mapa[h] = (nodo, campo)
            elif isinstance(valor, ast.AST):
                mapa[valor] = (nodo, campo)
    return mapa


def _aliases_type_checking(arbol):
    nombres, modulos = set(), set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module in (
                "typing", "typing_extensions"):
            nombres.update(a.asname or a.name for a in nodo.names
                           if a.name == "TYPE_CHECKING")
        elif isinstance(nodo, ast.Import):
            modulos.update(a.asname or a.name.split(".", 1)[0]
                           for a in nodo.names
                           if a.name in ("typing", "typing_extensions"))
    return nombres, modulos


def _es_type_checking(test, nombres, modulos):
    if isinstance(test, ast.Name):
        return test.id in nombres
    return (isinstance(test, ast.Attribute)
            and test.attr == "TYPE_CHECKING"
            and isinstance(test.value, ast.Name)
            and test.value.id in modulos)


def _modalidad_import(guardas):
    if any(tipo == "type_checking" for tipo, _ in guardas):
        return "type_checking"
    if any(tipo == "if" for tipo, _ in guardas):
        return "runtime_data"
    if any(tipo == "except_import" for tipo, _ in guardas):
        return "except_import"
    return "runtime_data" if guardas else "requerida"


# HUELLA-INGESTA-AST-MODALIDAD-IMPL-20261026
def _aristas_import(arbol, rel):
    """Aristas de importacion con declaracion, guarda y modalidad."""
    padres = _padres(arbol)
    nombres_tc, modulos_tc = _aliases_type_checking(arbol)
    aristas = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.Import, ast.ImportFrom)):
            continue
        qual, guardas = None, []
        actual = nodo
        while actual in padres:
            padre, campo = padres[actual]
            if isinstance(padre, DECLARABLES) and campo == "body":
                qual = padre.name if qual is None else padre.name + "." + qual
            elif isinstance(padre, ast.If) and campo == "body":
                texto = "if " + ast.unparse(padre.test)
                tipo = ("type_checking" if _es_type_checking(
                    padre.test, nombres_tc, modulos_tc) else "if")
                guardas.append((tipo, texto))
            elif isinstance(padre, TIPOS_TRY) and campo == "body":
                tipos = sorted({ast.unparse(h.type) for h in padre.handlers
                                if h.type is not None})
                if tipos:
                    texto = "except " + "/".join(tipos)
                    tipo = ("except_import" if any("ImportError" in t
                                                   for t in tipos)
                            else "except")
                    guardas.append((tipo, texto))
            actual = padre
        guardas.reverse()
        cond = " / ".join(texto for _, texto in guardas) or None
        modalidad = _modalidad_import(guardas)
        if isinstance(nodo, ast.Import):
            for a in nodo.names:
                aristas.append({"rel": rel, "qual": qual, "modulo": a.name,
                                "nombre": None, "asname": a.asname,
                                "cond": cond, "modalidad": modalidad,
                                "linea": nodo.lineno})
        else:
            modulo = "." * getattr(nodo, "level", 0) + (nodo.module or "")
            for a in nodo.names:
                aristas.append({"rel": rel, "qual": qual, "modulo": modulo,
                                "nombre": a.name, "asname": a.asname,
                                "cond": cond, "modalidad": modalidad,
                                "linea": nodo.lineno})
    return aristas


# HUELLA-INGESTA-AST-PUNTOS-CIEGOS-20261026
def _puntos_ciegos(arbol):
    """Marca patrones dinamicos visibles sin inferir su destino en runtime."""
    puntos = set()
    alias_importlib = {"importlib"}
    alias_import_module = set()

    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                if alias.name == "importlib" or (
                    alias.name.startswith("importlib.") and alias.asname is None
                ):
                    alias_importlib.add(alias.asname or "importlib")
        elif isinstance(nodo, ast.ImportFrom) and nodo.module == "importlib":
            for alias in nodo.names:
                if alias.name == "import_module":
                    alias_import_module.add(alias.asname or alias.name)

    if any(
        isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef))
        and nodo.name == "__getattr__"
        for nodo in _declaraciones(arbol)
    ):
        puntos.add("__getattr__")

    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Call):
            funcion = nodo.func
            if (
                isinstance(funcion, ast.Attribute)
                and funcion.attr == "import_module"
                and isinstance(funcion.value, ast.Name)
                and funcion.value.id in alias_importlib
            ) or (
                isinstance(funcion, ast.Name)
                and funcion.id in alias_import_module
            ):
                puntos.add("importlib.import_module")
        elif isinstance(nodo, ast.Subscript):
            valor = nodo.value
            if (
                isinstance(valor, ast.Call)
                and isinstance(valor.func, ast.Name)
                and valor.func.id == "globals"
            ):
                puntos.add("globals()[...]")

    orden = ("__getattr__", "importlib.import_module", "globals()[...]")
    return [punto for punto in orden if punto in puntos]


def _recorrer(nodo, prefijo, rel, lineas, salida):
    for hijo in _declaraciones(nodo):
        if isinstance(hijo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            qual = prefijo + hijo.name
            if isinstance(hijo, ast.ClassDef):
                _recorrer(hijo, qual + ".", rel, lineas, salida)
                continue
            raises, catches, calls = [], [], set()
            for m in _walk_propio(hijo):
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


# HUELLA-LOCUS-CORPUS-RAIZ-RESUELTA-20261026
# HUELLA-RAICES-OMITIDAS-DECLARADAS-20261026
# HUELLA-CORPUS-LOCUS-VLLM-OMNI-20261026
def _raices_declaradas(paquete):
    """Todas las raices que el interprete declara para el paquete.

    Un paquete de namespace puede vivir en varias entradas de `sys.path`.
    Desde H4 el corpus las ingiere TODAS, cada una con su propio `locus`; esta
    funcion publica la lista para que el sobre la declare antes de recorrerla.
    `raices_omitidas` solo puede dispararse si una raiz deja de ser directorio
    entre `find_spec` y el recorrido.
    """
    try:
        spec = importlib.util.find_spec(paquete)
    except (ImportError, ValueError):
        return []
    if spec is None:
        return []
    return [os.path.realpath(loc)
            for loc in list(spec.submodule_search_locations or ())
            if os.path.isdir(loc)]


# HUELLA-NS-RECORRE-N-RAICES-20261026
def _ingerir_raiz(raiz, locus, archivos, nodos, ilegibles, imports):
    """Recorre UNA raiz y acumula sus archivos, nodos e importaciones.

    `rel` se mide contra la raiz recorrida y `locus` es el de esa raiz: la
    identidad (locus, rel) no se hereda del sobre, porque un paquete de
    namespace puede aportar varias raices al mismo corpus.
    """
    antes = len(archivos)
    for r, dirs, ficheros in os.walk(raiz):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "__pycache__")
        for nombre in sorted(ficheros):
            if not nombre.endswith(".py"):
                continue
            ruta = os.path.join(r, nombre)
            rel = os.path.relpath(ruta, raiz).replace(os.sep, "/")
            with open(ruta, "rb") as f:
                datos = f.read()
            archivos.append({"rel": rel, "locus": locus,
                             "sha256": hashlib.sha256(datos).hexdigest(),
                             "bytes": len(datos), "puntos_ciegos": None})
            texto = datos.decode("utf-8", "replace")
            try:
                arbol = ast.parse(texto)
            except SyntaxError as e:
                archivos[-1]["nodos"] = None
                archivos[-1]["ilegible"] = "SyntaxError"
                ilegibles.append({"rel": rel, "linea": e.lineno,
                                  "motivo": str(e.msg)[:120]})
                continue
            archivos[-1]["puntos_ciegos"] = _puntos_ciegos(arbol)
            lineas = texto.splitlines()
            antes_nodos = len(nodos)
            _recorrer(arbol, "", rel, lineas, nodos)
            archivos[-1]["nodos"] = len(nodos) - antes_nodos
            imports.extend(_aristas_import(arbol, rel))
    return len(archivos) - antes


def ingerir_paquete(paquete, base=None):
    raiz, _ = resolver_raiz(paquete, base)
    if raiz is None:
        return None
    raiz_abs = os.path.realpath(raiz)
    locus = hashlib.sha256(raiz_abs.encode("utf-8")).hexdigest()
    declaradas = _raices_declaradas(paquete) if base is None else [raiz_abs]
    ingeridas = [raiz_abs] + [r for r in declaradas
                              if r != raiz_abs and os.path.isdir(r)]
    omitidas = [r for r in declaradas if r not in ingeridas]
    archivos, nodos, ilegibles, imports = [], [], [], []
    raices = []
    for raiz_i in ingeridas:
        locus_i = hashlib.sha256(raiz_i.encode("utf-8")).hexdigest()
        raices.append({"raiz": raiz_i, "locus": locus_i, "n_archivos":
                       _ingerir_raiz(raiz_i, locus_i, archivos, nodos,
                                     ilegibles, imports)})
    nodos.sort(key=lambda n: (n["rel"], n["linea"], n["qual"]))
    imports.sort(key=lambda a: (a["rel"], a["linea"], a["modulo"], a["nombre"] or ""))
    return {"esquema": "ingesta_ast/v2", "huella": HUELLA, "paquete": paquete,
            "raiz": raiz_abs, "raiz_rel": os.path.relpath(raiz, RAIZ),
            "locus": locus, "raices_declaradas": declaradas,
            "raices_ingeridas": raices,
            "raices_omitidas": omitidas, "n_archivos": len(archivos),
            "n_ilegibles": len(ilegibles), "ilegibles": ilegibles,
            "n_nodos": len(nodos), "n_imports": len(imports),
            "n_imports_cond": sum(1 for a in imports if a["cond"]),
            "archivos": archivos, "nodos": nodos, "imports": imports}


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
    ap.add_argument("--site", default=None,
                    help="directorio que CONTIENE el paquete; por defecto se resuelve con importlib")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    corpus = ingerir_paquete(a.paquete, a.site)
    if not corpus:
        _, causa = resolver_raiz(a.paquete, a.site)
        print("ERROR: paquete no ingerible (%s): %s"
              % (causa or "DESAPARECIO_TRAS_RESOLVER", a.paquete), file=sys.stderr)
        return 2
    if not corpus["n_nodos"]:
        entero = bool(corpus["n_archivos"]) and corpus["n_ilegibles"] == corpus["n_archivos"]
        print("ERROR: %s: %s  archivos=%d ilegibles=%d"
              % ("SIN_NODOS_ILEGIBLES" if entero else "SIN_NODOS", a.paquete,
                 corpus["n_archivos"], corpus["n_ilegibles"]), file=sys.stderr)
        return 3
    if a.json:
        print(json.dumps(corpus, ensure_ascii=False, indent=1, sort_keys=True))
        return 0
    con_raise = [n for n in corpus["nodos"] if n["raises"]]
    print("PAQUETE %s  archivos=%d nodos=%d ilegibles=%d con_raise=%d raise_sites=%d"
          % (corpus["paquete"], corpus["n_archivos"], corpus["n_nodos"],
             corpus["n_ilegibles"], len(con_raise),
             sum(len(n["raises"]) for n in con_raise)))
    print("ARISTAS nodo->callee=%d  nodo->excepcion=%d"
          % (sum(len(n["calls"]) for n in corpus["nodos"]),
             sum(len(n["raises"]) for n in corpus["nodos"])))
    print("IMPORTS total=%d condicionales=%d"
          % (corpus["n_imports"], corpus["n_imports_cond"]))
    for n in con_raise[:5]:
        print("  %-52s raises=%s" % (clave_de_nodo(n),
                                     ",".join(sorted({r["exc"] for r in n["raises"]}))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
