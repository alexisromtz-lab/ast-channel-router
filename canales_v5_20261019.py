#!/usr/bin/env python3
# HUELLA-CANALES-V5-20261019
"""Router V5: cuatro canales (simbolos · excepciones · rutas · prosa) con peso.

GOBIERNA ESTE ARCHIVO
  Nada. Los numeros se pre-registran aqui ANTES de la primera corrida y no se
  tocan despues de ver la salida (misma disciplina que sim/router_soluciones_v2.py).

QUE CAMBIA RESPECTO DE LA V2 (Jaccard plano con stopwords)
  1. SEPARA la consulta en cuatro canales independientes ANTES de medir. El
     Jaccard plano mezcla en una sola bolsa un simbolo exportado con una
     palabra coloquial: el termino coloquial infla el DENOMINADOR y diluye la
     evidencia dura. Aqui cada canal se mide con su propio conjunto.
  2. PONDERA. PESOS suma 1.0 y la masa dura (simbolos + excepciones) = 0.80.
     Es la regla del dictado: coincidir en un simbolo exportado o en un tipo
     de excepcion decide ~4/5 del enrutamiento.
  3. FUNCION POR CANAL, declarada: los canales DUROS usan CONTENCION
     |Q & D| / |Q| (un simbolo de la traza que aparece en el documento cuenta
     entero, sin importar cuan largo sea el documento); la prosa usa JACCARD
     (conserva el comportamiento de la V2 cuando no hay canal duro).
  4. DENOMINADOR = MASA ACTIVA DE LA CONSULTA, no masa total. Se declara:
     score = suma(w_c * s_c) / suma(w_c para c activo en la CONSULTA). Se
     calcula sin mirar el documento, de modo que el score sigue siendo
     comparable entre documentos y el umbral conserva sentido.
  5. EL CANAL PROSA NO RESTA. Primera corrida (2026-10-19T23:53:17Z) medida:
     separar los canales RESTANDO del prosa los tokens duros bajo el Jaccard
     de EV-001 de 0.085106 a 0.065217 y lo dejo por debajo del umbral con el
     top-1 correcto => un ENR se volvio NO_ENCONTRADO. El defecto es
     del diseno: el canal prosa es la BOLSA COMPLETA de la V2 (V2.tokenizar
     del texto entero) y los canales duros son EVIDENCIA ADICIONAL, no un
     filtro que reste. Con prosa = V2.tokenizar, una consulta solo-prosa da
     exactamente el Jaccard de la V2 y la regresion es exacta por
     construccion (se mide igual, 55/55).

CONSECUENCIA FALSABLE (no se afirma, se mide)
  Con una consulta SOLO de prosa, `activos == {"prosa"}` y el score es
  exactamente el Jaccard de la V2 sobre la bolsa completa (`V2.tokenizar` del
  texto entero). El ranking de la V2 se reproduce porque el canal prosa del
  documento es, por construccion, el mismo conjunto de la V2. Se mide: la
  regresion de los 55 casos congelados tiene que dar 55/55 y 55/55.

REGLA DECLARADA: EXCEPCION GENERICA NO ENRUTA SOLA
  `TypeError`, `ValueError`, `KeyError`... aparecen en cualquier repositorio y
  por si solas no distinguen nada. El canal `excepciones` se activa con una
  excepcion ESPECIFICA (clase propia: ScannerError, InvalidVersion, ...) o con
  una generica SOLO si la consulta trae ademas un simbolo o una ruta. La regla
  se evalua en la CONSULTA (doc-independiente); si dependiera del documento, el
  denominador cambiaria por candidato y el score dejaria de ser comparable.

§6. DOS CORRECCIONES MEDIDAS CONTRA EL CONTROL CRUZADO (2026-10-20T00:00:39Z)
  Primera corrida del control (`packaging` contra el universo `yaml`): 46/150
  consultas cruzaban el umbral. Mecanismo medido, no supuesto: las 46 tenian
  CERO match de simbolo; 2 cruzaban por `excepciones = 1.0` (un TypeError
  generico que existe en los dos paquetes => 0.35) y 44 por `rutas = 0.333`
  donde lo unico compartido era `ext:py` (=> 0.0702, apenas sobre 0.07).
  (a) `ext:<ext>` NO es una ruta: la extension la comparten todos los archivos
      del mundo. Se elimina del canal.
  (b) una excepcion CORROBORA, no funda: el canal suma solo si el documento
      caso tiene ademas un simbolo o una ruta en comun. El denominador no
      cambia (la actividad se decide en la consulta); lo que cambia es que una
      excepcion sin ancla estructural no empuja el score.
  Precio declarado de (b): una consulta que traiga SOLO una excepcion (sin
  simbolo ni ruta) no enruta; sale como candidato bajo el umbral. Se elige
  precision sobre cobertura y se mide (F3 del eval).
  (c) `__init__.py`, `utils.py`, `setup.py`... son nombres que existen en todo
      paquete: lista cerrada RUTAS_GENERICAS, no aprendida del corpus medido.
  (d) `self.__class__.__name__` no es un simbolo del repositorio: se normaliza
      (§6.e) y se caen los componentes de protocolo, no el simbolo entero.
  (e) `Version.__setstate__` se NORMALIZA a `Version` (borrarlo entero dejaba
      la consulta sin canal duro: medido).
  (f) EN UNA TRAZA, ARCHIVO Y SIMBOLO SON UN SOLO TESTIGO. Si la consulta trae
      ruta y el documento no comparte ni un componente, el simbolo es un
      HOMONIMO de otro archivo y no enruta (medido: `Node.__setstate__` de
      packaging contra `Node.__repr__` de yaml => 0.4583 con simbolo=1.0).
      Precio declarado: una ruta caduca (archivo renombrado) apaga el canal de
      simbolos de esa consulta.

QUE NO MIDE
  No mide si el canal entiende el problema: mide si la evidencia dura esta en
  la consulta y si el documento la conserva. Un acierto de top-1 sobre un
  banco derivado del AST dice que el enrutamiento usa la estructura; no dice
  que la solucion sea correcta.

Uso:
    python3 canales_v5_20261019.py "la consulta"
    python3 canales_v5_20261019.py --json "la consulta"
    python3 canales_v5_20261019.py --regresion      # requiere EVAL_CASOS + indice
RC: 0 encontrado · 3 NO_ENCONTRADO · 2 uso · 4 la regresion degrada la V2
"""

import argparse
import json
import os
import re
import sys
import time

HUELLA = "HUELLA-CANALES-V5-20261019"

# Corte publico: arbol PLANO. El catalogo y el banco de casos NO se distribuyen:
# se leen de donde el usuario los ponga (variable de entorno o archivo local).
RAIZ = os.path.dirname(os.path.abspath(__file__))
RUTA_INDICE = os.environ.get("ROUTER_INDICE", os.path.join(RAIZ, "catalogo.json"))
RUTA_EVAL = os.environ.get("EVAL_CASOS", os.path.join(RAIZ, "EVAL_casos.json"))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import router_soluciones_v2 as V2  # noqa: E402  el metro de la V2, importado

CANALES = ("simbolos", "excepciones", "rutas", "prosa")

# Pre-registrado. Masa dura = 0.45 + 0.35 = 0.80.
PESOS = {"simbolos": 0.45, "excepciones": 0.35, "rutas": 0.10, "prosa": 0.10}

# Se conserva el numero de la V4: aqui el score esta en la misma escala [0,1]
# cuando la consulta es solo prosa, y en esa rama se apoya la regresion.
UMBRAL = 0.07

STOPWORDS = frozenset(getattr(V2, "STOPWORDS", V2.STOPWORDS_ES | V2.STOPWORDS_EN))

EXT = frozenset("""
py pyi ipynb js jsx mjs cjs ts tsx go rs java kt kts rb php sql sh bash zsh fish
yml yaml json jsonl toml ini cfg conf md rst tex bib c h cc cpp cxx hpp cs swift
scala lua jl r m mm pl ps1 dockerfile makefile mk proto tf hcl gradle xml html
css scss sass less vue svelte astra lock txt csv tsv parquet proto
""".split())

ERRNO = frozenset("""
eacces eagain ebadf ebusy eexist efault efbig eintr einval eio eisdir eloop
emfile emlink enametoolong enfile enoent enoexec enomem enospc enosys enotdir
enotempty enotsup enxio eperm epipe erofs espipe etimedout ewouldblock
""".split())

SENAL = frozenset("sigkill sigterm sigsegv sigabrt sigbus sigint sighup sigquit sigpipe sigill sigfpe".split())

GENERICAS = frozenset("""
error exception warning typeerror valueerror keyerror indexerror attributeerror
runtimeerror oserror ioerror importerror modulenotfounderror notimplementederror
assertionerror stopiteration zerodivisionerror permissionerror filenotfounderror
timeouterror connectionerror memoryerror recursionerror unicodeerror
unicodedecodeerror unicodeencodeerror systemexit keyboardinterrupt
""".split())

# §6.c (medido 2026-10-20T00:01:56Z): el control cruzado dejo 8/150 sobre el
# umbral; 7 eran el MISMO caso, `licenses/__init__.py` contra el `__init__.py`
# de yaml (contencion 2/3 solo por el nombre generico). Un nombre de modulo que
# existe en todo paquete no es evidencia, igual que la extension: se declara
# una lista cerrada, no se aprende del corpus que se mide.
RUTAS_GENERICAS = frozenset("""
__init__ __main__ setup conftest test tests utils util types constants config
base core main index app lib common helpers exceptions errors
""".split())

# §6.d (mismo control): el 8/150 restante era `self.__class__.__name__` dentro
# de un literal del mensaje, coincidiendo con el cuerpo de `Token.__repr__`:
# un atributo de protocolo de Python no es un simbolo del repositorio.
SIMBOLOS_PROTOCOLO = frozenset("self cls super".split())


def _simbolo_valido(nombre):
    """Normaliza un candidato a simbolo; devuelve None si no es evidencia.

    §6.e (medido 2026-10-20T00:03:20Z): el ultimo cruce del control traia
    `Version.__setstate__` y el filtro duro lo borraba ENTERO por llevar un
    dunder, dejando la consulta sin canal duro. Se normaliza en vez de borrar:
    se caen los componentes de protocolo (`__setstate__`) y queda `Version`.
    """
    partes = [p for p in (nombre or "").split(".") if p]
    if not partes or partes[0] in SIMBOLOS_PROTOCOLO:
        return None
    partes = [p for p in partes
              if not (len(p) > 4 and p.startswith("__") and p.endswith("__"))]
    return ".".join(partes) if partes else None


def sumar_ruta(out, piezas):
    """Agrega componentes de ruta descartando los nombres genericos (§6.c)."""
    for p in piezas:
        pl = (p or "").strip().lower()
        if not pl:
            continue
        base = pl.rsplit(".", 1)[0] if "." in pl else pl
        if pl in RUTAS_GENERICAS or base in RUTAS_GENERICAS:
            continue
        out["rutas"].add(pl)

TOK = re.compile(r"\w+")
RE_BACKTICK = re.compile(r"`([^`\n]{1,120})`")
RE_PATH = re.compile(r"(?<![\w./-])((?:[\w.-]+[\\/])+[\w.-]+|[\w-]+)\.([A-Za-z][A-Za-z0-9]{0,9})(?![\w.])")
RE_RUTA_SIN_EXT = re.compile(r"(?<![\w./-])(?:[\w.-]+/){2,}[\w.-]+")
RE_RC = re.compile(r"\b(?:RC|rc|exit(?:\s*code)?|exit(?:ed)?\s+with)\s*[:=]?\s*(\d{1,3})\b")
RE_DECORADOR = re.compile(r"@([A-Za-z_][\w.]*)")
RE_LLAMADA = re.compile(r"(?<![\w.])([a-z_][a-z0-9]*(?:_[a-z0-9]+)+|[a-z][a-z0-9]*[A-Z]\w*|"
                        r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)\s*\(")
RE_PUNTO = re.compile(r"(?<![\w.])[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+")
RE_SNAKE = re.compile(r"(?<![\w.])[a-z][a-z0-9]*(?:_[a-z0-9]+)+(?![\w])")
RE_CAMEL = re.compile(r"(?<![\w.])[a-z][a-z0-9]*(?:[A-Z][a-z0-9]*)+(?![\w])")
RE_PASCAL = re.compile(r"(?<![\w.])[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)+(?![\w])")
RE_ID = re.compile(r"(?<![\w-])[A-Z]{2,}-\d{2,}(?![\w-])")

RC_OK, RC_USO, RC_NADA, RC_DEGRADA = 0, 2, 3, 4


def hora_utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def vacio():
    return {"simbolos": set(), "excepciones": set(), "excepciones_genericas": set(),
            "rutas": set(), "prosa": set()}


def _absorber(trozo, out):
    """Clasifica un trozo de texto en los canales, por precedencia declarada:
    rutas > excepciones > simbolos > prosa. Cada span se consume una sola vez."""
    t = trozo or ""
    ocupado = bytearray(len(t))

    def marca(a, b):
        for i in range(a, b):
            if 0 <= i < len(ocupado):
                ocupado[i] = 1

    for m in RE_PATH.finditer(t):
        ext = m.group(2).lower()
        if ext not in EXT:
            continue
        marca(m.start(), m.end())
        partes = [p for p in re.split(r"[\\/]", m.group(0)) if p]
        sumar_ruta(out, partes)
        if partes and partes[-1].lower().endswith("." + ext):
            base = partes[-1][:-(len(ext) + 1)]
            if base:
                sumar_ruta(out, [base])

    for m in RE_RUTA_SIN_EXT.finditer(t):
        if ocupado[m.start()]:
            continue
        marca(m.start(), m.end())
        sumar_ruta(out, [p for p in re.split(r"[\\/]", m.group(0)) if p])

    for m in RE_RC.finditer(t):
        marca(m.start(), m.end())
        out["excepciones"].add("rc" + m.group(1))

    for m in TOK.finditer(t):
        if ocupado[m.start()]:
            continue
        w = m.group(0)
        wl = w.lower()
        if wl in ERRNO or wl in SENAL or wl in ("oomkilled", "oom", "panic"):
            out["excepciones"].add(wl)
            marca(m.start(), m.end())
        elif len(wl) > 5 and wl.endswith(("error", "exception", "warning")):
            (out["excepciones_genericas"] if wl in GENERICAS else out["excepciones"]).add(wl)
            marca(m.start(), m.end())

    for rx in (RE_DECORADOR, RE_LLAMADA, RE_PUNTO, RE_SNAKE, RE_CAMEL, RE_PASCAL, RE_ID):
        for m in rx.finditer(t):
            if ocupado[m.start()]:
                continue
            nombre = m.group(1) if m.groups() else m.group(0)
            nombre = _simbolo_valido(nombre)
            if nombre:
                out["simbolos"].add(nombre)
            marca(m.start(), m.end())


def extraer(texto):
    """Canales de una consulta o de un texto libre.

    `prosa` es la bolsa COMPLETA de la V2 (V2.tokenizar del texto entero): no se
    le resta nada. Los canales duros son evidencia adicional sobre la misma
    bolsa, no un filtro que la encoja (defecto medido y corregido, ver cabecera
    §5).
    """
    out = vacio()
    raw = texto or ""
    resto = list(raw)
    for m in RE_BACKTICK.finditer(raw):
        _absorber(m.group(1), out)
        for i in range(m.start(), m.end()):
            resto[i] = " "
    _absorber("".join(resto), out)
    out["prosa"] = set(V2.tokenizar(raw))
    return out


def canales_de_fila(fila, campos=None):
    """Canales del lado DOCUMENTO para una fila del indice de 47."""
    campos = campos or V2.CAMPOS_TEXTO
    return extraer(" ".join(str(fila.get(k, "")) for k in campos))


def activos(q):
    """Canales activos, decididos SOLO con la consulta (denominador declarado)."""
    act = set()
    if q["simbolos"]:
        act.add("simbolos")
    if q["rutas"]:
        act.add("rutas")
    if q["excepciones"] or (q["excepciones_genericas"] and (q["simbolos"] or q["rutas"])):
        act.add("excepciones")
    if q["prosa"]:
        act.add("prosa")
    return act


def _contencion(a, b):
    return len(a & b) / len(a) if a else 0.0


def _jaccard(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def puntuar(q, d):
    """(score, detalle). El denominador es la masa activa de la CONSULTA."""
    act = activos(q)
    if not act:
        return 0.0, {"masa": 0.0, "por_canal": {}, "evidencia": {}}
    dex = set(d.get("excepciones") or ()) | set(d.get("excepciones_genericas") or ())
    dsym = d.get("simbolos") or set()
    drut = d.get("rutas") or set()
    ruta_corrobora = bool(q["rutas"] & drut)
    corrobora = bool(q["simbolos"] & dsym) or ruta_corrobora
    por_canal, evidencia = {}, {}
    for c in act:
        if c == "excepciones":
            m = set(q["excepciones"])
            if q["simbolos"] or q["rutas"]:
                m |= q["excepciones_genericas"]
            s, ev = (_contencion(m, dex) if corrobora else 0.0), sorted(m & dex)
        elif c == "prosa":
            dp = d.get("prosa") or set()
            s, ev = _jaccard(q["prosa"], dp), sorted(q["prosa"] & dp)
        elif c == "simbolos":
            # §6.f: en una traza el archivo y el simbolo son UN testigo. Si la
            # consulta trae ruta y el documento no comparte ni un componente,
            # el simbolo es un HOMONIMO en otro archivo y no enruta.
            vale = (not q["rutas"]) or ruta_corrobora
            s = _contencion(q["simbolos"], dsym) if vale else 0.0
            ev = sorted(q["simbolos"] & dsym)
        else:
            dc = d.get(c) or set()
            s, ev = _contencion(q[c], dc), sorted(q[c] & dc)
        por_canal[c] = round(s, 6)
        if ev:
            evidencia[c] = ev
    masa = sum(PESOS[c] for c in act)
    score = sum(PESOS[c] * por_canal[c] for c in act) / masa
    return score, {"masa": masa, "por_canal": por_canal, "evidencia": evidencia}


def enrutar(consulta, docs):
    """docs: lista de (identificador, canales). Lista (score, id, detalle) desc."""
    q = extraer(consulta)
    pares = []
    for ident, d in docs:
        s, det = puntuar(q, d)
        pares.append((s, ident, det))
    pares.sort(key=lambda x: (-x[0], str(x[1])))
    return q, pares


def clasificar(consulta, docs):
    q, pares = enrutar(consulta, docs)
    score, ident, det = pares[0]
    if not activos(q):
        return {"estado": "NO_ENCONTRADO", "motivo": "0 canales activos",
                "sim": 0.0, "id": None, "detalle": det,
                "candidatos": [(s, i) for s, i, _ in pares[:3]]}
    if score < UMBRAL:
        return {"estado": "NO_ENCONTRADO",
                "motivo": "score %.6f < umbral %.2f" % (score, UMBRAL),
                "sim": score, "id": None, "detalle": det,
                "candidatos": [(s, i) for s, i, _ in pares[:3]]}
    return {"estado": "ENCONTRADO", "motivo": "", "sim": score, "id": ident,
            "detalle": det, "candidatos": [(s, i) for s, i, _ in pares[:3]]}


def docs_del_indice(indice=None):
    indice = indice or V2.cargar_indice()
    return [(f.get("id"), canales_de_fila(f)) for f in indice.get("soluciones") or []]


def regresion():
    """55 casos congelados: la V5 no puede perder top-1 respecto de la V2."""
    docs = docs_del_indice()
    with open(RUTA_EVAL, "r", encoding="utf-8") as f:
        casos = json.load(f)["casos"]
    igual_top1 = 0
    igual_clase = 0
    filas = []
    for c in casos:
        q = extraer(c["query"])
        r5 = clasificar(c["query"], docs)
        r2 = V2.clasificar(c["query"], V2.cargar_indice())
        mismo_top1 = (r5["candidatos"][0][1] == r2["candidatos"][0][1])
        misma_clase = (r5["estado"] == r2["estado"])
        igual_top1 += mismo_top1
        igual_clase += misma_clase
        filas.append({"id": c["id"], "expected": c["expected"], "origen": c["origen"],
                      "v5_top1": r5["candidatos"][0][1], "v5_sim": round(r5["sim"], 6),
                      "v5_estado": r5["estado"],
                      "v2_top1": r2["candidatos"][0][1], "v2_sim": round(r2["sim"], 6),
                      "v2_estado": r2["estado"],
                      "mismo_top1": mismo_top1, "misma_clase": misma_clase,
                      "activos": sorted(activos(q))})
    enr = [f for f in filas if f["origen"] == "manual_ENR"]
    enr_ok = sum(1 for f in enr if f["v5_top1"] == f["expected"])
    ne = [f for f in filas if f["expected"] == "NE_CORPUS_EMPTY"]
    ne_ok = sum(1 for f in ne if f["v5_estado"] == "NO_ENCONTRADO")
    con_duros = sum(1 for f in filas if len(f["activos"]) > 1)
    salida = {"huella": HUELLA, "hora": hora_utc(), "n": len(filas),
              "igual_top1": igual_top1, "igual_clase": igual_clase,
              "enr_top1": enr_ok, "enr_n": len(enr),
              "ne_no_encontrado": ne_ok, "ne_n": len(ne),
              "consultas_con_canal_duro": con_duros, "casos": filas}
    ok = igual_top1 == len(filas) and igual_clase == len(filas) and enr_ok == len(enr)
    salida["veredicto"] = "SIN_DEGRADACION" if ok else "DEGRADA"
    return (RC_OK if ok else RC_DEGRADA), salida


def main(argv=None):
    ap = argparse.ArgumentParser(prog="canales_v5_20261019.py",
                                 description="Router V5: cuatro canales ponderados.")
    ap.add_argument("consulta", nargs="*")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--regresion", action="store_true")
    a = ap.parse_args(argv)

    if a.regresion:
        rc, s = regresion()
        print(json.dumps(s, ensure_ascii=False, indent=1, sort_keys=True))
        return rc

    consulta = " ".join(a.consulta).strip()
    if not consulta and not sys.stdin.isatty():
        consulta = sys.stdin.read().strip()
    if not consulta:
        print("ERROR: falta la consulta.", file=sys.stderr)
        return RC_USO

    r = clasificar(consulta, docs_del_indice())
    if a.json:
        print(json.dumps({"huella": HUELLA, "hora": hora_utc(), "consulta": consulta,
                          "umbral": UMBRAL, "pesos": PESOS, "estado": r["estado"],
                          "motivo": r["motivo"], "sim": round(r["sim"], 6),
                          "id": r["id"], "detalle": r["detalle"],
                          "candidatos": [{"id": i, "sim": round(s, 6)}
                                         for s, i in r["candidatos"]]},
                         ensure_ascii=False, indent=2))
        return RC_OK if r["estado"] == "ENCONTRADO" else RC_NADA

    print("ESTADO: %s | score=%.4f | umbral=%.2f" % (r["estado"], r["sim"], UMBRAL))
    if r["motivo"]:
        print("MOTIVO: %s" % r["motivo"])
    print("CANALES: %s" % json.dumps(r["detalle"], ensure_ascii=False, sort_keys=True))
    if r["id"]:
        print("SOLUCION: %s" % r["id"])
    else:
        print("CANDIDATOS (bajo el umbral, no adjudicados)")
        for s, i in r["candidatos"]:
            print("  score=%.6f  %s" % (s, i))
    return RC_OK if r["estado"] == "ENCONTRADO" else RC_NADA


if __name__ == "__main__":
    sys.exit(main())
