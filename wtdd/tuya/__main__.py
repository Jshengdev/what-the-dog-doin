"""Tuya WT1 Wi-Fi 2CH LED controller (warm white + cool white strip) over the LAN, protocol 3.5, via tinytuya.

Found 2026-09-13 by `python -m tinytuya scan`: device ebfd2e5d73c07e6f302clt at 10.66.10.44, product hprgre8k9nlpjayk.
Control needs the device's LOCAL KEY, which only the Tuya IoT platform hands out (project + link the Smart Life app by
QR + `python -m tinytuya wizard`). Datapoints for this "dj" light: 20 switch, 21 work_mode, 22 brightness 10..1000,
23 colour temperature 0..1000. Every write reads the status back and is one ledger row.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from typing import Any

import tinytuya

from .. import config
from ..ledger import log, step

AGENT, APP = "lights", "tuya"
DPS = {"switch": "20", "mode": "21", "bright": "22", "temp": "23"}


def decode(status: dict[str, Any]) -> dict[str, Any]:
    d = status.get("dps", {}) if isinstance(status, dict) else {}
    out = {"on": d.get(DPS["switch"]), "mode": d.get(DPS["mode"]), "raw": d}
    if d.get(DPS["bright"]) is not None:
        out["brightness_pct"] = round((int(d[DPS["bright"]]) - 10) / 990 * 100, 1)
    if d.get(DPS["temp"]) is not None:
        out["temp_pct"] = round(int(d[DPS["temp"]]) / 1000 * 100, 1)
    return out


def device() -> tinytuya.BulbDevice:
    d = tinytuya.BulbDevice(config.get("TUYA_DEVICE_ID"), config.get("TUYA_DEVICE_IP"), config.get("TUYA_LOCAL_KEY"),
                            version=float(config.maybe("TUYA_VERSION") or 3.5))
    d.set_socketPersistent(True)
    d.set_socketTimeout(5)
    return d


def read(d: tinytuya.BulbDevice) -> dict[str, Any]:
    st = d.status()
    if not isinstance(st, dict) or "dps" not in st:
        raise RuntimeError(f"tuya status failed: {st}")   # e.g. {'Error': 'Network Error: Unable to Connect', 'Err': '901'}
    return decode(st)


def write(tool: str, args: dict[str, Any], fn) -> dict[str, Any]:
    d = device()
    before = read(d)
    with step(AGENT, tool, APP, args, before) as r:
        resp = fn(d)
        if isinstance(resp, dict) and resp.get("Error"):
            raise RuntimeError(f"tuya {tool} failed: {resp}")
        time.sleep(0.3)
        after = read(d)
        r["state_after"] = after
        r["response_or_error"] = json.dumps(resp, default=str)[:300]
        return after


def cmd_probe(a: argparse.Namespace) -> int:
    rows = []
    want = config.maybe("TUYA_DEVICE_ID")
    found = tinytuya.deviceScan(False, 8)
    hit = next((v for v in found.values() if v.get("id") == want), None)
    rows.append(("scan", "ok" if hit else "FAIL", f"{len(found)} tuya device(s); " + (f"ours at {hit['ip']} v{hit['version']}" if hit else f"{want} not broadcasting")))
    key = config.maybe("TUYA_LOCAL_KEY")
    rows.append(("TUYA_LOCAL_KEY", "ok" if key else "FAIL", "present" if key else "empty: Tuya IoT project + QR link + `python -m tinytuya wizard` (see docs/SETUP.md §3)"))
    if hit and key:
        try:
            st = read(device())
            rows.append(("status", "ok", json.dumps({k: v for k, v in st.items() if k != "raw"})))
        except Exception as e:  # noqa: BLE001
            rows.append(("status", "FAIL", f"{type(e).__name__}: {str(e)[:120]}"))
    w = max(len(l) for l, _, _ in rows)
    for l, s, n in rows:
        print(f"{l:<{w}}  {s:<5} {n}")
    return 0 if all(s == "ok" for _, s, _ in rows) else 1


def cmd_status(a: argparse.Namespace) -> int:
    print(json.dumps(read(device()), indent=1))
    return 0


def cmd_on(a: argparse.Namespace) -> int:
    print(json.dumps(write("lights.tuya_set", {"on": True}, lambda d: d.turn_on())))
    return 0


def cmd_off(a: argparse.Namespace) -> int:
    print(json.dumps(write("lights.tuya_set", {"on": False}, lambda d: d.turn_off())))
    return 0


def cmd_dim(a: argparse.Namespace) -> int:
    pct = max(0, min(100, a.percent))
    print(json.dumps(write("lights.tuya_set", {"brightness_pct": pct}, lambda d: d.set_brightness_percentage(pct))))
    return 0


def cmd_temp(a: argparse.Namespace) -> int:
    pct = max(0, min(100, a.percent))
    print(json.dumps(write("lights.tuya_set", {"temp_pct": pct}, lambda d: d.set_colourtemp_percentage(pct))))
    return 0


def cmd_fade(a: argparse.Namespace) -> int:
    """Play with dimming: ramp brightness from --start to --end over --seconds in --steps steps; one ledger row."""
    d = device()
    before = read(d)
    with step(AGENT, "lights.tuya_fade", APP, {"start": a.start, "end": a.end, "seconds": a.seconds, "steps": a.steps}, before) as r:
        d.turn_on()
        for i in range(a.steps + 1):
            pct = a.start + (a.end - a.start) * i / a.steps
            resp = d.set_brightness_percentage(pct)
            if isinstance(resp, dict) and resp.get("Error"):
                raise RuntimeError(f"tuya fade step {i} failed: {resp}")
            log(AGENT, f"fade step {i}/{a.steps}", pct=round(pct, 1))
            time.sleep(a.seconds / a.steps)
        time.sleep(0.3)
        r["state_after"] = read(d)
        print(json.dumps(r["state_after"]))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m wtdd.tuya", description="Tuya WT1 LED controller, local protocol 3.5")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe", help="scan for the device, key check, live status").set_defaults(fn=cmd_probe)
    sub.add_parser("status", help="read dps and decode on/brightness/temp").set_defaults(fn=cmd_status)
    sub.add_parser("on").set_defaults(fn=cmd_on)
    sub.add_parser("off").set_defaults(fn=cmd_off)
    s = sub.add_parser("dim", help="brightness percent"); s.add_argument("percent", type=float); s.set_defaults(fn=cmd_dim)
    s = sub.add_parser("temp", help="colour temperature percent (0 warm .. 100 cool)"); s.add_argument("percent", type=float); s.set_defaults(fn=cmd_temp)
    s = sub.add_parser("fade", help="ramp brightness"); s.add_argument("--start", type=float, default=5); s.add_argument("--end", type=float, default=100)
    s.add_argument("--seconds", type=float, default=4); s.add_argument("--steps", type=int, default=16); s.set_defaults(fn=cmd_fade)
    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
