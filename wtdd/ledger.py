"""Receipts. One append-only JSONL row per step, plus one grep-able log line. Every number on any screen is read from here.

Row schema (docs/ARCHITECTURE.md §5): ts, run_id, step, agent, tool, args, app, ok, response_or_error,
state_before, state_after, latency_ms, cached, source. Never rewritten.
"""
from __future__ import annotations
import json
import os
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .config import ROOT

LEDGER = Path(os.environ.get("WTDD_LEDGER", ROOT / "ledger.jsonl"))
RUN_ID = os.environ.get("WTDD_RUN_ID") or time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:4]


def log(tag: str, msg: str, **kv: Any) -> None:
    extra = " ".join(f"{k}={v}" for k, v in kv.items())
    print(f"[wtdd:{tag}] {msg} {extra}".rstrip(), file=sys.stderr, flush=True)


def append(row: dict[str, Any]) -> dict[str, Any]:
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "run_id": RUN_ID, "cached": False, "source": "live", **row}
    with LEDGER.open("a") as f:
        f.write(json.dumps(row, default=str) + "\n")
    return row


@contextmanager
def step(agent: str, tool: str, app: str, args: dict[str, Any] | None = None,
         state_before: Any = None):
    """Times a tool call and writes exactly one row, ok or not. Usage:
        with step("lights", "lights.set_zone", "hue", {"zone": "a", "on": True}, before) as r:
            r["state_after"] = do_it()
    An exception inside the block is recorded on this exact step and re-raised (no swallowing).
    """
    t0 = time.perf_counter()
    r: dict[str, Any] = {"step": tool, "agent": agent, "tool": tool, "app": app, "args": args or {},
                         "state_before": state_before, "state_after": None, "ok": False, "response_or_error": None}
    try:
        yield r
        r["ok"] = True
    except Exception as e:  # noqa: BLE001  (recorded, then re-raised: never a silent fallback)
        r["response_or_error"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        r["latency_ms"] = round((time.perf_counter() - t0) * 1000)
        append(r)
        log(agent, f"{tool} ok={r['ok']}", app=app, ms=r["latency_ms"],
            err=str(r["response_or_error"] or "")[:80])


def rows(n: int | None = None) -> list[dict[str, Any]]:
    if not LEDGER.exists():
        return []
    out = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
    return out[-n:] if n else out
