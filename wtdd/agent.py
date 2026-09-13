"""The model takes charge: a free-form ask becomes tool calls over wtdd/tools, executed for real, then one honest line.

One loop, no framework: OpenRouter chat completions with the registry as function-calling tools; every call the model
makes is executed through tools.call (so it can only touch what the tools can touch), its result is fed back, and the
loop ends when the model answers in text or after MAX_STEPS. The model call rows and the tool rows are all in the ledger.
"""
from __future__ import annotations
import json
from typing import Any

from . import tools
from .ledger import log
from .llm import generate

MAX_STEPS = 8
SYSTEM = (
    "You are the house agent of a shared house (the castle). You control the living room lights and the robot dog only "
    "through the tools given. Do the ask with the fewest calls, read results, then answer in one casual sentence under "
    "140 characters saying what actually happened, including any failure verbatim. Never claim something you did not do."
)


def _specs() -> list[dict[str, Any]]:
    out = []
    for t in tools.describe():
        props = {}
        for k, v in t["args"].items():
            typ = v.get("type", "string")
            props[k] = {"type": {"number": "number", "boolean": "boolean"}.get(typ, "string"), "description": v.get("doc", "")}
        out.append({"type": "function", "function": {"name": t["name"], "description": t["doc"],
                    "parameters": {"type": "object", "properties": props}}})
    return out


def ask(text: str, context: str | None = None) -> dict[str, Any]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM + (f"\n\nContext:\n{context}" if context else "")},
                                      {"role": "user", "content": text}]
    calls: list[dict[str, Any]] = []
    usage: dict[str, Any] = {}
    for step in range(MAX_STEPS):
        out = generate("central", messages, max_tokens=300, temperature=0.2, tools=_specs())
        usage = out["usage"]
        msg = out["raw"]["choices"][0]["message"]
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            return {"text": (msg.get("content") or "").strip(), "calls": calls, "usage": usage}
        messages.append(msg)
        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            log("agent", f"step {step} -> {name}", args=json.dumps(args)[:120])
            try:
                result = tools.call(name, **args)
                payload = {"ok": True, "result": result}
            except Exception as e:  # noqa: BLE001  (the failure goes back to the model verbatim; it must report it)
                payload = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}
            calls.append({"tool": name, "args": args, **payload})
            messages.append({"role": "tool", "tool_call_id": tc["id"], "name": name, "content": json.dumps(payload, default=str)[:4000]})
    return {"text": f"stopped after {MAX_STEPS} steps; did: " + ", ".join(c["tool"] for c in calls), "calls": calls, "usage": usage}
