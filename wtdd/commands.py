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


ZONE = "living room"   # the only zone the chat may touch (docs/SCOPE-LOCK: never a device that was not asked for)


def lights(on: bool, bri: float | None = None) -> str:
    """The living room, both protocols: the four Hue lights in the zone (cloud CLIP v2) and the Tuya LED strip
    (local protocol 3.5). Never any other light. Each device is read back; a failure on either is reported, not hidden."""
    from .hue.__main__ import set_zone
    from .tuya.__main__ import strip
    b = _bridge()
    names = {l["id"]: l["metadata"]["name"] for l in b.lights()}
    hue = set_zone(b, ZONE, on, bri)
    done = [names.get(i, i[:8]) for i in hue]
    st = strip(on=on, bri=(bri if on else None))
    done.append(f"strip {'on' if st.get('on') else 'off'}" + (f" {st.get('brightness_pct')}%" if st.get("on") else ""))
    verb = "on" if on else "off"
    if bri is not None and on:
        verb += f" at {int(bri)}%"
    return f"{ZONE} lights {verb}: {', '.join(done)} (read back)"


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


def _t(tool: str, **args: Any) -> Callable[[], Any]:
    """A chat command is exactly one registry tool call (wtdd/tools): the same code path as the remote and the MCP."""
    from . import tools
    return lambda: tools.call(tool, **args)


def _status() -> str:
    from . import tools
    st = tools.call("lights_status")
    hue = ", ".join(f"{l['name']} {'on' if l['on'] else 'off'}" for l in st["hue"] if l.get("room") == "Living room")
    s = st["strip"]
    return f"{hue}; strip {'on' if s.get('on') else 'off'} {s.get('brightness_pct', '?')}%" if "error" not in s else f"{hue}; strip: {s['error']}"


HANDLERS: dict[str, Callable[[], Any]] = {
    "lights on": _t("lights_on"),
    "lights off": _t("lights_off"),
    "dim": _t("lights_dim", percent=20),
    "bright": _t("lights_dim", percent=100),
    "show": _t("light_show"),
    "sit": _t("dog_cmd", name="Sit"),
    "stand": _t("dog_cmd", name="RiseSit"),
    "hello": _t("dog_cmd", name="Hello"),
    "look": _t("dog_look"),
    "do a round": _t("dog_round"),
    "status": _status,
}


def run(name: str) -> Any:
    """Returns a str, or {"text", "file"} for a photo reply. Raises on any failure; one ledger row either way."""
    if name not in HANDLERS:
        raise KeyError(f"no handler for command {name!r}; handlers: {', '.join(HANDLERS)}")
    with step("central", "command." + name.replace(" ", "_"), "wtdd", {"command": name}) as r:
        out = HANDLERS[name]()
        r["state_after"] = out if isinstance(out, dict) else {"text": str(out)}
        return out
