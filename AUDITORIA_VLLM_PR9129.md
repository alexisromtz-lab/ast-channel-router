# Auditoría estática de vLLM-Omni — PR #9129

## Alcance y referencia

Análisis estático del snapshot de [`vllm-project/vllm-omni#9129`](https://github.com/vllm-project/vllm-omni/pull/9129) fijado al commit `943914c75c503bcabe274dceb75e904da367e14c`. La ingesta procesó 1.869 archivos Python y 24.665 aristas de importación, sin errores de sintaxis reportados. El análisis se hizo directamente con el extractor AST; no ejercitó el wrapper MCP `obtener_impacto`.

## Resultado del grafo

Para `vllm_omni/platforms/__init__.py`, el grafo encontró 703 dependientes runtime posibles y 61 dependientes alcanzables solo al incluir imports de tipado. «Runtime posible» incluye aristas bajo guardas, pero no predice qué rama se ejecuta ni si una dependencia opcional está instalada.

El módulo usa `__getattr__` para resolver de forma diferida el atributo `current_omni_platform`. Esa resolución dinámica no se deduce del grafo de imports estáticos: el grafo no identifica el destino efectivo del atributo ni puede explicar por sí solo un error ocurrido durante esa resolución.

## Límite observado

La ingesta `ingesta_ast/v2` puede publicar `puntos_ciegos` por archivo como señal sintáctica. Para este patrón, la señal indica la presencia de `__getattr__`; no equivale a `dinamico: true`, no resuelve el destino ni prueba el comportamiento en ejecución.

## Límite del entorno y conclusión

Se intentó importar `current_omni_platform` en el entorno local, pero la ejecución terminó antes de entrar al paquete con `ModuleNotFoundError: No module named 'vllm_omni'`. Por tanto, no se obtuvo el traceback del entorno NPU/CI y no se pudo determinar la causa del error reportado. No hay evidencia aquí para concluir que falte el registro de NPU, que falte un módulo concreto o que `__getattr__` maneje mal una excepción.

Para cerrar el diagnóstico hace falta el traceback completo del entorno que falla, junto con sus versiones y dependencias instaladas. Con esa evidencia se puede seguir la ruta efectiva de `__getattr__` y distinguir entre plataforma no registrada, módulo/dependencia ausente u otra excepción. Este reporte documenta el alcance y el límite del análisis; no es un diagnóstico causal confirmado.

<!-- HUELLA-AUDITORIA-VLLM-PR9129-20261026 -->

## Adenda 2026-10-26 — el detalle no lo borra PEP 562: lo borra la frontera de importación

**Objeto medido:** `vllm_omni/platforms/__init__.py`, blob `d5ee64353bf12c42ac437977dedfc4f1ee2333c2`, 209 líneas. Es byte idéntico en el commit fijado `943914c7` y en el checkout actual `c84638f` (`git diff --stat 943914c7 c84638f -- vllm_omni/platforms/__init__.py` vacío, exit 0), así que la lectura del archivo no depende de qué commit se tenga desplegado.

Se sostuvo que el traceback «se borra por diseño» y que el fallo es indiagnosticable sin parchear `vllm-omni`. Medido en Python 3.12.13, esa afirmación es **falsa como regla general**: el detalle se pierde o se conserva según qué excepción cruce la frontera.

### Las tres ramas de `__getattr__("current_omni_platform")`

| rama dentro de `__getattr__` | excepción que nace | lo que ve quien hace `from vllm_omni.platforms import current_omni_platform` |
|---|---|---|
| el módulo de plataforma no se puede importar (`importlib.import_module`) | `ModuleNotFoundError` | se propaga **intacta**, con marcos de `__getattr__` e `import_module` |
| el módulo importa pero la clase no existe (`getattr(module, obj_name)`) | `AttributeError` | se sustituye por `ImportError: cannot import name 'current_omni_platform'` **sin `__cause__`, sin `__context__` y sin el marco de `__getattr__`** |
| dos plugins activados (`resolve_current_omni_platform_cls_qualname`) | `RuntimeError` | se propaga **intacta** |

`resolve_obj_by_qualname` se leyó del `main` de `vllm` (no del pin exacto de la release), donde es `importlib.import_module(module)` seguido de `getattr(module, obj_name)`.

### Reproducción (módulo de juguete, mismo mecanismo)

```python
# mod_attr.py
def __getattr__(name):
    if name == "target":
        raise AttributeError("inner failure detail: platform class missing")
    raise AttributeError(f"No attribute named '{name}'")
```

```python
from mod_attr import target      # ImportError: cannot import name 'target' from 'mod_attr'
getattr(__import__("mod_attr"), "target")
                                 # AttributeError: inner failure detail: platform class missing
```

Salida medida en 3.12.13: el `from ... import` publica `frames: ['<module>', '<module>']` y `__cause__: None`, `__context__: None`; el `getattr` publica `frames: ['<module>', '__getattr__']` con el mensaje íntegro. **El mismo fallo, dos caminos, uno borra y el otro no.**

### Consecuencia: hay recuperación sin parchear `vllm-omni`

```python
import vllm_omni.platforms as p
try:
    p.current_omni_platform                      # acceso a atributo: sin frontera de importación
except BaseException as e:
    print(type(e).__name__, e)                   # el detalle real, con su marco
    print("init_trace:", repr(p._init_trace))    # el propio módulo guarda traceback.format_stack()
    print("qualname:", p.resolve_current_omni_platform_cls_qualname())  # llamada directa
```

El módulo ya publica `_init_trace` (`_init_trace = "".join(traceback.format_stack())` tras inicializar la plataforma) y expone `resolve_current_omni_platform_cls_qualname()`; ninguna de las dos pasa por la frontera que borra. Llamar al resolutor de forma directa devuelve la excepción verdadera con su traza completa.

### Lo que sigue sin medirse

Nada de esto se ejecutó contra el entorno NPU/CI: localmente `vllm_omni` no está instalado y la importación muere con `ModuleNotFoundError: No module named 'vllm_omni'` antes de entrar al paquete. Por tanto no se afirma cuál de las tres ramas ocurre allí; se afirma que **la rama se puede distinguir sin modificar el código**, con el bloque de arriba, y que solo la rama `AttributeError` pierde el detalle al cruzar un `from ... import`.

<!-- HUELLA-ADENDA-PEP562-MEDIDA-20261026 -->