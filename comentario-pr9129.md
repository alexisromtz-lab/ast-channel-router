**Static import-graph notes on `platforms/__init__.py`** (fyi, no action implied)

Object: `vllm_omni/platforms/__init__.py` @ `943914c7` (current head of this PR), blob `d5ee6435`, 209 lines.

**Graph facts.** AST import graph over the pinned tree (1,869 Python files, 24,665 import edges): 703 runtime-reachable dependents of this module, plus 61 reachable only through `type_checking` edges. "Runtime possible" includes guarded imports and does not predict branch execution.

`current_omni_platform` is resolved lazily via module-level `__getattr__` (PEP 562), so a static graph cannot resolve the attribute target — it can only flag the file as dynamically resolved. That is a limit of the tool, not a claim about the failure.

**What the message implies.** `ImportError: cannot import name 'current_omni_platform'` is the replacement the import machinery produces for an `AttributeError` raised inside `__getattr__`. Measured on CPython 3.12.13, whether you get usable detail depends on which branch raised:

| raised inside `__getattr__` | caller of `from vllm_omni.platforms import current_omni_platform` sees |
|---|---|
| `ModuleNotFoundError` (platform module not importable) | propagated intact: `__getattr__` and `import_module` frames preserved |
| `AttributeError` (module imports, `getattr(module, obj_name)` misses) | replaced by `ImportError: cannot import name …` — no `__cause__`, no `__context__`, no `__getattr__` frame |
| `RuntimeError` (two plugins activated) | propagated intact |

Minimal repro for the middle row: a module whose `__getattr__` raises `AttributeError`. `from m import x` yields `ImportError` whose traceback holds only the caller frame and whose `__cause__` is `None`; `getattr(m, "x")` yields the original `AttributeError` with both the caller and the `__getattr__` frames.

**Recovering the detail without patching the package.** Attribute access does not cross the import boundary, and the module already records a stack:

```python
import vllm_omni.platforms as p
try:
    p.current_omni_platform          # attribute access, not `from ... import`
except BaseException as e:
    import traceback; traceback.print_exc()
    print("INIT_TRACE:", repr(p._init_trace))
    print("QUALNAME:", p.resolve_current_omni_platform_cls_qualname())
```

`_init_trace` is filled with `traceback.format_stack()` right after platform init; calling `resolve_current_omni_platform_cls_qualname()` directly re-raises with the real traceback. Either path distinguishes "module missing", "class missing" and "two plugins" from outside.

**Disclosure.** I could not reproduce this on NPU hardware — `vllm_omni` is not installed in the environment I measured in, so I make no claim about which branch fires in your CI. The table and snippet are what separates them. The middle row was measured on CPython 3.12.13 with a toy module, as described above.
