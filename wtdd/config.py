"""Env loading. Reads .env at the repo root once; missing required keys throw (CLAUDE.md §2: fail loud)."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_loaded = False


def _load() -> None:
    global _loaded
    if _loaded:
        return
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.split(" #", 1)[0].strip().strip('"').strip("'")   # a comment needs a space before #; keys can contain #
            os.environ.setdefault(k.strip(), v)
    _loaded = True


def get(key: str, default: str | None = None) -> str:
    _load()
    v = os.environ.get(key, default)
    if v is None or v == "":
        raise RuntimeError(f"[wtdd:config] {key} is required. Set it in {ROOT / '.env'} (see .env.example).")
    return v


def maybe(key: str) -> str | None:
    _load()
    v = os.environ.get(key)
    return v if v else None
