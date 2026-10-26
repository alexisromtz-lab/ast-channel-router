# ast-channel-router

**Búsqueda y recuperación estructural de código: canales ponderados sobre el AST en
lugar de una bolsa de palabras plana.**

El canal de prosa es el último recurso. Antes se miran los canales duros que una
consulta trae cuando viene de una falla real: **símbolos**, **excepciones** y **rutas**.

```
masa dura = 0.45 (símbolos) + 0.35 (excepciones) = 0.80
resto     = 0.10 (rutas) + 0.10 (prosa)
```

Una consulta con `AttributeError` y `src/loader.py` no se parece a un issue escrito en
prosa: se parece a una traza. Ponderar los canales por separado permite que la traza
gane sin que la prosa tenga que desaparecer.

## Módulos

| archivo | qué hace |
|---|---|
| `ingesta_ast_20261019.py` | recorre un paquete con `ast` y extrae símbolos, llamadas, excepciones y rutas por documento, más las aristas de importación del corpus |
| `canales_v5_20261019.py` | puntúa una consulta por canal y suma con pesos; expone `puntuar(evidencia, documento)` |
| `extractor_ast.py` | extrae la evidencia dura de una consulta (símbolos, excepciones, rutas) usando los mismos canales |
| `router_soluciones_v2.py` | núcleo de enrutamiento: Jaccard con filtro de stopwords |

## Uso

```bash
# 1) ingerir un paquete instalado en el intérprete activo
python3 ingesta_ast_20261019.py --paquete yaml --json > documentos.json
#    el paquete se resuelve con importlib, no por ruta clavada: si no está
#    instalado, sale RC 2 (AUSENTE) en vez de un error de ruta. Con
#    --site /ruta/site-packages se apunta a otra instalación.

# 2) puntuar una consulta real
python3 canales_v5_20261019.py "AttributeError: 'NoneType' object has no attribute 'get' en src/loader.py"

# 3) enrutar contra un catálogo propio
python3 router_soluciones_v2.py --indice examples/indice_ejemplo.json "el cargador revienta con None"
```

## Grafo de importaciones (`imports`)

La ingesta emite las aristas de importación **a nivel de corpus**, al lado de
`nodos`, no como campo de cada nodo. Salida real de `--paquete _pytest --json`,
recortada a dos aristas:

```json
{"n_imports": 1686, "n_imports_cond": 117,
 "imports": [
   {"rel": "_io/terminalwriter.py", "linea": 80, "qual": "TerminalWriter.__init__",
    "modulo": "colorama", "nombre": null, "asname": null,
    "cond": "if hasattr(file, 'isatty') and file.isatty() and (sys.platform == 'win32') / except ImportError",
    "modalidad": "runtime_data"},
   {"rel": "__init__.py", "linea": 7, "qual": null,
    "modulo": "._version", "nombre": "version", "asname": "__version__",
    "cond": "except ImportError", "modalidad": "except_import"}
 ]}
```

- `qual` — la declaración que encierra la arista, o `null` a nivel módulo.
- `cond` — la guarda que la hace condicional, o `null` si no hay guarda. Se
  compone con ` / ` de fuera hacia dentro: `if <test>` (el test tal como lo
  escribe `ast.unparse`) y `except <tipos>`.
- `modalidad` — `requerida` (sin guarda), `type_checking` (guarda directa
  `TYPE_CHECKING` importada de `typing`/`typing_extensions`), `except_import`
  (import dentro de `try` con `ImportError`) o `runtime_data` (otras guardas).
  `type_checking` se conserva en el JSON, pero no cuenta como impacto runtime.
  `runtime_data` y `except_import` sí cuentan como impacto runtime posible; no
  predicen si la rama se ejecutará ni si el paquete opcional estará instalado.
- `modulo` / `nombre` / `asname` — `import a.b` deja `modulo="a.b"`,
  `nombre=null`; `from a.b import c as d` deja `modulo="a.b"`, `nombre="c"`,
  `asname="d"`. Los puntos relativos se preservan (`.`, `..paquete`).
- `n_imports` y `n_imports_cond` son el denominador: el descarte se publica.

# HUELLA-README-IMPACTO-CONSUMER-20261026
El consumidor `extractor_ast.impacto_importaciones(corpus, objetivo)` devuelve
los dependientes transitivos internos en `runtime` y los alcanzables solo al
incluir aristas `type_checking` en `solo_type_checking`. `runtime` significa
impacto posible: incluye imports bajo guardas de datos o `ImportError`, sin
predecir la ejecución de esas ramas. La resolución cubre imports relativos y
absolutos con prefijo del paquete; dependencias externas o no resueltas quedan
fuera del resultado.

```python
impacto = extractor_ast.impacto_importaciones(corpus, "_io/terminalwriter.py")
```

La primera arista del ejemplo es el patrón que se busca: un `import` dentro de
una declaración, bajo una guarda de plataforma **y** un `except ImportError`
anidado. Existe en el corpus real (`_pytest`, no en el árbol de esta
herramienta) y por eso el campo lo publica en vez de descartarlo.

**Por qué a nivel de corpus y no por nodo.** Medido el 26-Oct-2026 sobre el
corpus declarado: de 5 657 imports, **5 150 (91%) viven a nivel módulo** y no
tienen nodo al que colgarse; 56 de los condicionales están en ese estrato. Un
campo por nodo habría publicado el 9% del objeto y dejado el resto invisible.

## Qué se distribuye y qué no

Este repositorio es el **corte público** de un motor que corre en producción:

- **Se distribuye** el motor: tokenizador, stopwords, Jaccard, canales, pesos, ingesta
  AST y extractor. Son copias literales del original, verificadas por hash de fuente
  (`inspect.getsource`), no reimplementaciones.
- **No se distribuye** el catálogo de soluciones, el banco de casos congelados con
  identificadores de solución, ni el barrido contra la versión anterior del motor. Ese
  material es del operador privado; aquí el catálogo **lo pone el usuario**.

Por eso el índice y el banco de evaluación se leen de `ROUTER_INDICE` y
`EVAL_CASOS`, o de los argumentos explícitos. Actualiza la configuración de despliegue
para usar `ROUTER_INDICE`; el archivo por defecto es `catalogo.json`. El umbral se lee
de `ROUTER_UMBRAL` (por defecto `0.07`): el valor calibrado lo es contra un corpus
concreto, y cada corpus trae el suyo. Se imprime en cada salida para que la corrida sea
auditable.

## Formato del índice

```json
{"soluciones": [
  {"id": "SOL-A", "problema": "...", "solucion": "...",
   "dominio": "...", "cuando_aplicar": "..."}
]}
```

El ejemplo distribuido, `examples/indice_ejemplo.json`, declara 3 soluciones y cada una
trae los 5 campos del formato: `len(d['soluciones'])` y `len(d['soluciones'][0])` son
las dos cifras del ejemplo. La batería semántica activa se declara en
`.github/ci-apparatus`.

`CAMPOS_TEXTO = ("problema", "solucion", "dominio", "cuando_aplicar")` — cambiar el
texto de comparación y las stopwords a la vez hace inatribuible cualquier mejora: un
solo actor por medición.

## Qué **no** mide

- No mide si la solución es correcta: mide si la evidencia dura está en la consulta y si
  el documento la conserva.
- `calls` guarda el nombre tal como aparece (`yaml.error.X` se guarda como `X` y como
  `yaml.error.X`). No hay inferencia de tipos.
- `imports` publica la arista `A importa B`; **no** resuelve la dependencia: no dice si
  `B` se puede importar en este intérprete ni arrastra transitivas. La guarda se lee del
  cuerpo de `if` y de `try`; un import en `else`/`finally`/`except` se publica con
  `cond: null`.
- Para lenguajes que no son Python se declara `soportado: False` en vez de inventar
  símbolos con una regex que se haría pasar por AST.

## Licencia

MIT. Ver `LICENSE`.

<!-- HUELLA-README-INGESTA-SITE-RC-20261025 -->

<!-- HUELLA-README-IMPORTS-20261026 -->

<!-- HUELLA-README-IMPORTS-B-20261026 -->

<!-- HUELLA-README-IMPORTS-C-20261026 -->

<!-- HUELLA-ERRATA-ORIGEN-ARISTAS-20261026 -->
## Adenda de procedencia de aristas — 2026-10-26

`git log --all -S '658'` y `git log --all -S '707'` no identifican commits de origen en este repositorio. Se retiran los conteos `658/39/8/2` y el total `707`: no tienen locus reproducible y no deben atribuirse a `_pytest`.

Línea base reproducida para el módulo `_pytest`, provisto por la distribución `pytest==9.1.1`, con Python 3.12.13 seleccionado por `uv`: **1,686 aristas** — `requerida`: 1,569; `type_checking`: 68; `runtime_data`: 43; `except_import`: 6.

Comando de reproducción:

```bash
uv run --no-project --python 3.12.13 --with 'pytest==9.1.1' -- python ingesta_ast_20261019.py --paquete _pytest --json | jq -c '{paquete,n_imports,modalidades:([.imports[].modalidad] | group_by(.) | map({(.[0]):length}) | add)}'
```

<!-- HUELLA-ERRATA-ORIGEN-ARISTAS-20261026 -->
