"""The proximity field: an entity with a radius walks the path drawn on ui/map.json and every light's brightness is how
much of it sits inside that radius, weighted toward the centre. One implementation, used by the chat's wake demo
(tools.call("walk_path")) and by the remote's walk button (POST /tools/walk_path); the page only animates the dot.

  python -m wtdd walk_path dry=true        compute and log every level, write nothing
  python -m wtdd walk_path                 drive the real lights
  lamp:   score = (1 - d/R) ** falloff at the lamp's point
  strip:  the mean of that over `samples` points along its line (a graze at the edge is dim, a pass over the middle bright)
  rooms:  score *= other_room_factor when the light's room (the polygon its point sits in) is not the entity's room
Map keys read: path (at least 2 points), entity {radius_px 220, speed_px_s 60, falloff 1.6, other_room_factor 0.3,
samples 12, min_step 4, floor 6}, lights [{id, label, kind dot|line, pts, device hue|strip}], rooms [{name, poly}].
lights[].room is recomputed here from the polygons, whatever the file says.
Writes go through the registry (hue_light_set per lamp, strip_set for the strip): one thread per light and at most one
write in flight per light, so each light steps exactly as fast as its own measured latency allows (the strip about 0.4 s
on the LAN, a Hue lamp through the cloud about 0.8 s), only when the level moved by at least `min_step` points or
crossed zero, and is simply off below `floor`. The loop polls at HZ. Order: every light to 0 and wait for all of it (the
room starts dark and the first latency of each light is measured), the walk in real time at speed_px_s, then every
light to 0 again and wait. One field.walk ledger row with seconds, writes, errors, rooms crossed and the mean latency per
light; every write is its own row, a failed write is counted and logged, never retried. Measured on the live wake demo
(2026-09-13): dark start 1.46 s, walk 63.6 s across four rooms (seven crossings, five lights), 67 writes, 0 errors.
"""
from __future__ import annotations
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from . import tools
from .config import ROOT
from .ledger import log, step

MAP = ROOT / "ui" / "map.json"
HZ = 10.0


def inside(p, poly) -> bool:
    c = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > p[1]) != (yj > p[1]) and p[0] < (xj - xi) * (p[1] - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


def room_of(p, rooms) -> str | None:
    return next((r["name"] for r in rooms if inside(p, r["poly"])), None)


def score(light: dict[str, Any], p, ent: dict[str, Any], here: str | None) -> float:
    R, k = float(ent.get("radius_px", 220)), float(ent.get("falloff", 1.6))
    w = lambda q: max(0.0, 1 - math.dist(p, q) / R) ** k  # noqa: E731
    if light["kind"] == "line":
        n = int(ent.get("samples", 12))
        (ax, ay), (bx, by) = light["pts"]
        s = sum(w((ax + (bx - ax) * i / n, ay + (by - ay) * i / n)) for i in range(n + 1)) / (n + 1)
    else:
        s = w(light["pts"][0])
    if here and light["room"] and light["room"] != here:
        s *= float(ent.get("other_room_factor", 0.3))
    return s


def _label(light: dict[str, Any]) -> str:
    return light.get("label", light["id"])


def _write(light: dict[str, Any], level: int) -> float:
    """One real write through the registry; returns its latency in seconds."""
    t0 = time.monotonic()
    if light["device"] == "strip":
        tools.call("strip_set", on=level > 0, percent=max(level, 1))
    else:
        tools.call("hue_light_set", light=light["id"], on=level > 0, percent=max(level, 1))
    return time.monotonic() - t0


def walk(dry: bool = False) -> dict[str, Any]:
    """Runs the entity along the map's path in real time and drives the real lights (see the module doc for the order).
    Returns seconds, dark_ms, writes, errors, rooms crossed, latency_ms per light, and the light labels."""
    m = json.loads(MAP.read_text())
    pts, ent, lights, rooms = m["path"], m.get("entity", {}), m.get("lights", []), m.get("rooms", [])
    if len(pts) < 2:
        raise ValueError("map.json has fewer than 2 path points; draw the path on the remote and save")
    for L in lights:
        (ax, ay), (bx, by) = L["pts"][0], L["pts"][-1]     # a dot's midpoint is the dot itself
        L["room"] = room_of(((ax + bx) / 2, (ay + by) / 2), rooms)
    speed = float(ent.get("speed_px_s", 60))
    min_step = int(ent.get("min_step", 4))
    floor = int(ent.get("floor", 6))
    segs = [(pts[i - 1], pts[i], math.dist(pts[i - 1], pts[i])) for i in range(1, len(pts))]
    total = sum(d for _, _, d in segs)

    def at(s):
        acc = 0.0
        for a, b, d in segs:
            if s <= acc + d:
                k = (s - acc) / d if d else 0
                return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
            acc += d
        return tuple(pts[-1])

    pool = ThreadPoolExecutor(max_workers=max(1, len(lights)))
    lat: dict[str, list[float]] = {L["id"]: [] for L in lights}
    inflight: dict[str, Any] = {}
    last: dict[str, int] = {L["id"]: 0 for L in lights}
    writes = errors = 0

    def settle(fut, lid):
        nonlocal errors
        try:
            lat[lid].append(fut.result(timeout=30))
        except Exception as e:  # noqa: BLE001  (counted and logged here; the failed write has its own ledger row)
            errors += 1
            log("field", "write failed", light=lid[:8], err=f"{type(e).__name__}: {str(e)[:80]}")

    with step("field", "field.walk", "map", {"path_pts": len(pts), "lights": len(lights), "radius": ent.get("radius_px"),
                                             "falloff": ent.get("falloff"), "speed": speed, "seconds": round(total / speed, 1), "dry": dry}) as r:
        t_dark = time.monotonic()
        if not dry:                                      # dark start: everything off, and wait for it
            for lid, fut in {L["id"]: pool.submit(_write, L, 0) for L in lights}.items():
                settle(fut, lid)
            writes += len(lights)
        dark_ms = round((time.monotonic() - t_dark) * 1000)
        log("field", "dark, starting", ms=dark_ms, latency={_label(L)[:12]: round(1000 * lat[L["id"]][-1]) if lat[L["id"]] else None for L in lights})
        t0 = time.monotonic()
        rooms_seen: list[str] = []
        while True:
            s = min(total, (time.monotonic() - t0) * speed)
            p = at(s)
            here = room_of(p, rooms)
            if here and (not rooms_seen or rooms_seen[-1] != here):
                rooms_seen.append(here)
            for L in lights:
                lid = L["id"]
                level = int(round(100 * score(L, p, ent, here)))
                if level < floor:
                    level = 0
                fut = inflight.get(lid)
                if fut is not None:
                    if not fut.done():
                        continue                       # one write in flight per light: pace = that light's real latency
                    settle(fut, lid)
                    inflight.pop(lid)
                if abs(level - last[lid]) >= min_step or (level == 0) != (last[lid] == 0):
                    last[lid] = level
                    writes += 1
                    log("field", f"{_label(L)[:18]} -> {level}%", room=here or "-", x=int(p[0]), y=int(p[1]))
                    if not dry:
                        inflight[lid] = pool.submit(_write, L, level)
            if s >= total:
                break
            time.sleep(1 / HZ)
        for lid, fut in list(inflight.items()):
            settle(fut, lid)
        for L in lights:                                 # ends dark, and wait for it
            writes += 1
            if not dry:
                inflight[L["id"]] = pool.submit(_write, L, 0)
        for lid, fut in inflight.items():
            settle(fut, lid)
        pool.shutdown(wait=True)
        latency = {_label(L): round(1000 * sum(lat[L["id"]]) / len(lat[L["id"]])) if lat[L["id"]] else None for L in lights}
        out = {"seconds": round(time.monotonic() - t0, 1), "dark_ms": dark_ms, "writes": writes, "errors": errors,
               "rooms": rooms_seen, "latency_ms": latency, "lights": [_label(L) for L in lights]}
        r["state_after"] = out
        return out
