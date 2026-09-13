"""One file, one task. Every tool module declares NAME, DOC, ARGS and a run(**kwargs) -> dict.

ARGS = {"percent": {"type": "number", "default": 20, "doc": "0 to 100"}}
run() must do the real thing and read the result back (or raise). The registry below is what the HTTP API
(`python -m wtdd.api`), the MCP server (`python -m wtdd.mcp_server`) and the React remote all use.
"""
from __future__ import annotations
import importlib
import pkgutil
from typing import Any


def registry() -> dict[str, Any]:
    tools = {}
    for m in pkgutil.iter_modules(__path__):
        if m.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{m.name}")
        if hasattr(mod, "run"):
            tools[getattr(mod, "NAME", m.name)] = mod
    return dict(sorted(tools.items()))


def describe() -> list[dict[str, Any]]:
    return [{"name": n, "doc": getattr(m, "DOC", (m.__doc__ or "").strip()), "args": getattr(m, "ARGS", {})}
            for n, m in registry().items()]


def call(name: str, **kwargs: Any) -> Any:
    tools = registry()
    if name not in tools:
        raise KeyError(f"no tool {name!r}; tools: {', '.join(tools)}")
    mod = tools[name]
    spec = getattr(mod, "ARGS", {})
    unknown = set(kwargs) - set(spec)
    if unknown:
        raise ValueError(f"{name}: unknown args {sorted(unknown)}; accepts {sorted(spec)}")
    for k, v in spec.items():
        if k not in kwargs and "default" in v:
            kwargs[k] = v["default"]
    return mod.run(**kwargs)
