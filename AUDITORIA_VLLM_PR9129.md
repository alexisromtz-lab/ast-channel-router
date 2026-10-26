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