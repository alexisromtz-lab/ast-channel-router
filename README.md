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

<!-- HUELLA-README-LOCUS-RAIZ-20261026 -->
**Locus de raíz.** La identidad de un archivo es el par `(locus, rel)`. `rel`
es la ruta relativa a la raíz ingerida; `locus` es el `sha256` de la raíz
**absoluta** resuelta con `realpath`, publicado en el sobre para la raíz
primaria y repetido en cada entrada de `archivos` con el de **su** raíz. Sin
él, dos paquetes homónimos en raíces distintas —o dos copias del mismo
paquete— publican el mismo `paquete` y los mismos `rel`: son indistinguibles.
`raiz` publica la ruta absoluta; `raiz_rel` es la relativa al checkout de la
herramienta (informativa, cambia si el corpus viaja). Medido el 26-Oct-2026: un
corpus que concatenara dos raíces resolvía `mod.py` de A con `usador.py` de B y
devolvía un dependiente que no existe; hoy `extractor_ast` lo rechaza con
`corpus fusiona raices distintas` — salvo que las raíces estén **declaradas**.
Los corpus sin `locus` (esquema anterior) siguen siendo legibles.

**Raíces de namespace.** Un paquete de namespace puede vivir en varias entradas
de `sys.path`. La ingesta recorre **todas** las declaradas, cada una con su
propio `locus`, y las publica en `raices_ingeridas` (`raiz`, `locus` y
`n_archivos` por raíz); `raices_declaradas` conserva las rutas y
`raices_omitidas` queda vacía. Medido el 26-Oct-2026 en 3.12.13: antes de este
cambio un namespace con dos rutas publicaba `n_archivos: 1` y el segundo
`mod_b.py` desaparecía sin conteo; hoy publica `n_archivos: 2` con dos `locus`
distintos y el impacto atraviesa las raíces. Un `rel` presente en dos raíces no
se resuelve adivinando —Python tomaría la primera de `sys.path`—: el consumidor
falla cerrado con `rel ambiguo entre raices`. `raices_ingeridas` es la
declaración que distingue un namespace legítimo de una fusión a mano.

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

<!-- HUELLA-ERRATA-CENSO-ARISTAS-20261026 -->
El censo histórico de 5,657 imports citado arriba se originó en `340abce`; su mensaje registra 954 archivos `.py` y 952 parseados, pero no identifica el paquete, la ruta del corpus ni el comando. Es una medición histórica distinta de la línea base `_pytest` reproducida aquí; su locus queda pendiente y no deben compararse como el mismo universo.

<!-- HUELLA-ERRATA-CENSO-ARISTAS-20261026 -->

<!-- HUELLA-ERRATA-CENSO-NO-REPRODUCIBLE-20261026 -->
El censo histórico de 5,657/5,150 (commit `340abce`) se declara `NO_REPRODUCIBLE` por falta de locus (paquete y comando desconocidos). No se usará como base para auditorías.
<!-- HUELLA-ERRATA-CENSO-NO-REPRODUCIBLE-20261026 -->

<!-- HUELLA-CORPUS-LOCUS-VLLM-OMNI-20261026 -->
## Corpus de medición: `vllm_omni`

El corpus que sostiene la auditoría del PR 9129 no es una cifra de chat: es un archivo con `sha256` y un comando que lo reconstruye.

| campo | valor |
|---|---|
| paquete | `vllm_omni` |
| fuente | checkout `vllm-omni` en `c84638f3208f0fffd872200adfc5860103a6244b` |
| esquema | `ingesta_ast/v2` (`locus` por archivo, `raices_ingeridas`) |
| archivos · imports · nodos | **1 975 · 25 931 · 25 076** |
| modalidades | `requerida` 24 613 · `runtime_data` 702 · `type_checking` 400 · `except_import` 216 |
| raíces de namespace | **1**, `raices_omitidas` vacío |
| `sha256` del corpus | `28f78e8cb1706fadb310d0b9a9180e6dd48fbea595e96f12df16f576c5789bbb` |
| serializador | `json.dumps(ensure_ascii=False, indent=1, sort_keys=True) + '\n'` |
| tamaño | 46 940 422 B |

Comando de reproducción, con el checkout en `PYTHONPATH`:

```bash
PYTHONPATH=/ruta/al/checkout/vllm-omni uv run --no-project --python 3.12.13 -- \
  python ingesta_ast_20261019.py --paquete vllm_omni --json > vllm_omni.json
```

**Por qué la corrección de H4 no mueve estas cifras (medido 26-Oct-2026).** `vllm_omni` declara **una sola** raíz en `submodule_search_locations`, así que el defecto de H4 —ingerir solo la primera— no tocaba este corpus. Regenerado bajo el esquema v2, el conjunto de `rel`, el multiconjunto de aristas y los tres conteos coinciden con el corpus congelado bajo v1, y `impacto_importaciones('platforms/__init__.py')` devuelve **743 runtime + 63 sólo `type_checking`** en las dos versiones. El corpus v1 sigue siendo legible (`test_corpus_de_una_raiz_sin_declaracion_sigue_siendo_legible`): regenerar no era obligatorio para reproducir el 743/63. La v2 —ya producida y pineada en la tabla, y la única que debe usarse para consultas nuevas— añade `locus` por archivo y `puntos_ciegos`.

El corpus no se versiona —es dato derivado de decenas de MB—. Su identidad viaja en el `sha256` de esta tabla y en el manifiesto hermano, que el motor compara contra el archivo medido antes de cargarlo.

<!-- HUELLA-MANIFIESTO-CORPUS-POR-MEDICION-20261026 -->
**El manifiesto no se escribe a mano.** `manifiesto_corpus_20261026.py` deriva cada celda de medición del propio corpus y verifica el serializador reproduciendo los bytes; la proveniencia (`comando`, `fuente_checkout`, `fuente_commit`, `python`, `medido_en_utc`) se hereda del manifiesto previo o se declara con `--prov clave=valor`. Sin `--comprobar` escribe el hermano de forma atómica; con `--comprobar` no escribe nada y devuelve RC 1 nombrando la celda desfasada.

```bash
uv run --no-project --python 3.12.13 -- python manifiesto_corpus_20261026.py \
  ~/Library/Caches/ast-channel-router/vllm_omni.json --comprobar   # RC 0 · 19 celdas
```

La primera corrida contra el manifiesto escrito a mano encontró **tres** desfases reales sobre 18 celdas: el `serializador` declaraba la llamada sin el LF final (un byte, y con ese byte la firma deja de ser reproducible), y faltaban `objetivos` y el `objetivo` del impacto. Las otras quince —`bytes`, `sha256`, los tres conteos, las cuatro modalidades y las dos raíces— ya coincidían: el manifiesto era correcto en lo que declaraba y mudo en lo que omitía.

<!-- HUELLA-CORPUS-SERIALIZADOR-Y-LOCUS-20261026 -->
Dos precisiones que cuestan caro si se omiten. **El `sha256` contrata también al serializador:** dos volcados del mismo objeto con `indent=1` y compacto difieren en bytes (46 940 422 frente a 43 766 237) y por tanto en huella; la tabla publica el del serializador que usa el CLI, que es el que produce el comando de arriba sin post-proceso —incluido el `\n` final, que el cuerpo del `json.dumps` no aporta y sin el cual el archivo mide 46 940 421 B y hashea `5e8cd24c…`—. **Y el corpus tiene locus durable:** vive en `~/Library/Caches/ast-channel-router/vllm_omni.json`, junto a `vllm_omni.manifest.json` con la misma tupla, porque `/tmp` se purga y un corpus citado en un acta no puede depender de eso. El archivo `vllm_omni_corpus.json` congelado bajo el esquema v1 (`sha256` `210942836ef60d78…`) queda **superseded**: se conserva porque §4 y §9 del acta lo citan, y no debe usarse para consultas nuevas.

<!-- HUELLA-H5-FALSADOR-1601-20261026 -->
## Índice de adyacencia (H5)

`impacto_importaciones` reconstruye el grafo inverso en cada consulta. `indice_adyacencia(corpus)` lo construye una vez y lo publica; `impacto_importaciones(corpus, objetivo, indice=...)` lo reutiliza. Sin `indice` el resultado es el mismo por construcción: la firma histórica sigue valiendo y ninguna respuesta cambia.

**El índice no se adopta porque sea rápido: se adopta porque reproduce.** Falsador medido el 26-Oct-2026 sobre el corpus durable de `vllm_omni` (`28f78e8c…`, 25 931 aristas): **1 601 destinos, 0 discrepancias** frente a la reconstrucción por consulta, y `platforms/__init__.py → 743/63` idéntico con y sin índice. El índice publica 1 601 destinos y 5 629 pares origen→destino únicos (una arista repetida entre el mismo par no añade destino). Los falsadores viven en [`tests/test_indice_adyacencia_20261026.py`](tests/test_indice_adyacencia_20261026.py): 10 pruebas, de las cuales la paridad recorre una muestra determinista de 62 destinos en 2,3 s; la corrida completa —1 601 destinos, **154,16 s**— se pide con `AST_PARIDAD_H5=completa`.

Medición con su instrumento declarado: 5 repeticiones, 200 destinos, corpus durable ya cargado en memoria.

| magnitud | min | mediana | max |
|---|---|---|---|
| construcción del índice | 0,0293 s | 0,0333 s | 0,0483 s |
| consulta con índice | 0,0002 s | 0,0002 s | 0,0002 s |
| consulta sin índice | 0,0221 s | 0,0238 s | 0,0246 s |

Factor medido: **91,5×–147,2×**. En dos sesiones anteriores del mismo día el mismo instrumento dio 77× y 118,9× sobre el mismo corpus. La cifra es **de orden, no exacta**: publicar un decimal de una medición con 2× de varianza entre corridas es el defecto que este repositorio ya castiga en otro sitio.

**Tamaño del índice: 337 144 B = 0,72 % del corpus**, bajo el serializador declarado `json.dumps({destino: sorted(origenes)}, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")`. La cifra `714 793 B / 1,52 %` que circuló antes se declara **`NO_REPRODUCIBLE`**: no declaró su serializador y no se reproduce con este. Es la misma regla que retiró el censo `5 657/5 150` —un byte sin su serializador es un rumor— y la que ya corrigió el `serializador` del manifiesto.

**El defecto que H5 no arregla, porque no existía.** `impacto_importaciones` hoistea `_modulos_del_corpus` fuera del bucle desde su primer commit: el camino de producción nunca reconstruyó el índice de módulos por arista. El sesgo apareció en un *script de medición* que sí lo llamaba dentro del bucle —4,56 ms por llamada × 25 931 aristas ≈ **131 s**—. Un instrumento que mide su propio defecto no mide el objeto.

Un índice de otro corpus **se rechaza** (`indice de otro corpus`): reutilizarlo fusionaría dos identidades en silencio, la clase de defecto que H1 cerró en la ingesta y que aquí se cierra en el consumo. El índice publica `fuente_n_archivos` y `fuente_n_imports` —el corpus del que salió— y la comprobación es O(1).

## Límite de resolución dinámica

<!-- HUELLA-LIMITE-AST-DINAMICO-20261026 -->
La ingesta AST no puede resolver dependencias creadas dinámicamente (por ejemplo, mediante `__getattr__` o `globals()`). El esquema v2 publica `puntos_ciegos` por archivo para señalar patrones observables, pero no resuelve sus destinos. Para diagnosticar fallos de resolución dinámica sigue siendo necesario el traceback del entorno de ejecución.

El detalle de ese fallo **sí** se conserva si se cruza la frontera por acceso a atributo en vez de `from ... import`: medido el 26-Oct-2026 en 3.12.13, `getattr(mod, "x")` deja el `AttributeError` con su marco y su mensaje, mientras que `from mod import x` lo sustituye por `ImportError: cannot import name ...` sin `__cause__` ni `__context__`. El borrado es de la frontera de importación, no de PEP 562.
<!-- HUELLA-README-FRONTERA-IMPORT-20261026 -->
<!-- HUELLA-LIMITE-AST-DINAMICO-20261026 -->
