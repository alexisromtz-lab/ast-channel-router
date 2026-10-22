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
| `ingesta_ast_20261019.py` | recorre un paquete con `ast` y extrae símbolos, llamadas, excepciones y rutas por documento |
| `canales_v5_20261019.py` | puntúa una consulta por canal y suma con pesos; expone `puntuar(evidencia, documento)` |
| `extractor_ast.py` | extrae la evidencia dura de una consulta (símbolos, excepciones, rutas) usando los mismos canales |
| `router_soluciones_v2.py` | núcleo de enrutamiento: Jaccard con filtro de stopwords |

## Uso

```bash
# 1) ingerir un paquete
python3 ingesta_ast_20261019.py --paquete yaml --json > documentos.json

# 2) puntuar una consulta real
python3 canales_v5_20261019.py "AttributeError: 'NoneType' object has no attribute 'get' en src/loader.py"

# 3) enrutar contra un catálogo propio
python3 router_soluciones_v2.py --indice examples/indice_ejemplo.json "el cargador revienta con None"
```

## Qué se distribuye y qué no

Este repositorio es el **corte público** de un motor que corre en producción:

- **Se distribuye** el motor: tokenizador, stopwords, Jaccard, canales, pesos, ingesta
  AST y extractor. Son copias literales del original, verificadas por hash de fuente
  (`inspect.getsource`), no reimplementaciones.
- **No se distribuye** el catálogo de soluciones, el banco de casos congelados con
  identificadores de solución, ni el barrido contra la versión anterior del motor. Ese
  material es del operador privado; aquí el catálogo **lo pone el usuario**.

Por eso el índice y el banco de evaluación se leen de `INDICE_SOLUCIONES` y
`EVAL_CASOS`, o de los argumentos explícitos. El umbral se lee de `ROUTER_UMBRAL`
(por defecto `0.07`): el valor calibrado lo es contra un corpus concreto, y cada corpus
trae el suyo. Se imprime en cada salida para que la corrida sea auditable.

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
  `yaml.error.X`). No hay inferencia de tipos ni resolución de imports.
- Para lenguajes que no son Python se declara `soportado: False` en vez de inventar
  símbolos con una regex que se haría pasar por AST.

## Licencia

MIT. Ver `LICENSE`.
