"""What a recognized command actually does. Every handler calls the real module and fails loud; the listener posts the
truth either way (the result, or the error class and message). Nothing here fakes a success (CLAUDE.md §2)."""
from __future__ import annotations
import asyncio
import json
from pathlib import Path
from typing import Any, Callable

from . import config
from .ledger import step, rows

ROUTES = Path(__file__).parent / "dog" / "routes"
LOOK = Path("~/Pictures/wtdd/look.jpg").expanduser()


def _bridge():
    from .hue.api import HueBridge
    return HueBridge.from_env()


def lights(on: bool) -> str:
    b = _bridge()
    names = []
    for light in b.lights():
        b.set(light["id"], on=on)
        names.append(light["metadata"]["name"])
    return f"lights {'on' if on else 'off'}: {', '.join(names)}"


async def _with_dog(fn: Callable) -> Any:
    from .dog.body import Body
    body = Body()
    await body.connect()
    try:
        return await fn(body)
    finally:
        await body.close()


def dog_cmd(name: str) -> str:
    async def go(body):
        code = await body.cmd(name)
        st = body.state() or {}
        return f"{name.lower()} done (status {code}, mode {st.get('mode')})"
    return asyncio.run(_with_dog(go))


def look() -> dict[str, str]:
    async def go(body):
        await body.frame(LOOK)
        return str(LOOK)
    return {"text": "here's what i see", "file": asyncio.run(_with_dog(go))}


def do_round() -> str:
    from .dog.body import validate_route
    steps = json.loads((ROUTES / "corridor.json").read_text())
    problems = validate_route(steps)
    if problems:
        raise ValueError("corridor.json: " + "; ".join(problems))

    async def go(body):
        done = await body.route(steps, "corridor")
        return f"round done: {len(done)} steps"
    return asyncio.run(_with_dog(go))


def status() -> str:
    last = [r for r in rows(60) if r["tool"] not in ("chat.gate", "chat.claim", "llm.generate")][-3:]
    if not last:
        return "nothing in the ledger yet"
    return "; ".join(f"{r['tool']} {'ok' if r['ok'] else 'FAILED'} {r.get('latency_ms', '?')}ms" for r in last)


HANDLERS: dict[str, Callable[[], Any]] = {
    "lights on": lambda: lights(True),
    "lights off": lambda: lights(False),
    "sit": lambda: dog_cmd("Sit"),
    "stand": lambda: dog_cmd("RiseSit"),
    "hello": lambda: dog_cmd("Hello"),
    "look": look,
    "do a round": do_round,
    "status": status,
}


def run(name: str) -> Any:
    """Returns a str, or {"text", "file"} for a photo reply. Raises on any failure; one ledger row either way."""
    if name not in HANDLERS:
        raise KeyError(f"no handler for command {name!r}; handlers: {', '.join(HANDLERS)}")
    with step("central", "command." + name.replace(" ", "_"), "wtdd", {"command": name}) as r:
        out = HANDLERS[name]()
        r["state_after"] = out if isinstance(out, dict) else {"text": str(out)}
        return out
