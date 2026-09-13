"""The field: an entity with a radius walks the path drawn on the map; each light's brightness is how much of it sits
inside that radius, weighted toward the center; lights in rooms the entity is not in are scaled down. One
implementation, used by the wake demo in the chat and by the remote's button (the page only animates the dot).

  lamp:  score = (1 - d/R) ** falloff at the lamp's point
  strip: the mean of that over `samples` points along its line (a graze at the edge is dim, a pass over the middle is bright)
  rooms: score *= other_room_factor when the light's room is not the entity's room
Real writes go through the tool registry (hue_light_set, strip_set), one thread per light; each light has at most one
write in flight, so it steps exactly as fast as its own measured latency allows (the strip about 0.4 s, a Hue lamp
through the cloud about 0.8 s), in steps of `min_step` points, and is simply off below `floor`.
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


def load_map() -> dict[str, Any]:
    return json.loads(MAP.read_text())


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
    return next((r["name"] for r in rooms or [] if inside(p, r["poly"])), None)


def score(light: dict[str, Any], p, ent: dict[str, Any], here: str | None) -> float:
    R, k = float(ent.get("radius_px", 220)), float(ent.get("falloff", 1.6))
    w = lambda q: max(0.0, 1 - math.dist(p, q) / R) ** k  # noqa: E731
    if light["kind"] == "line":
        n = int(ent.get("samples", 12))
        (ax, ay), (bx, by) = light["pts"]
        s = sum(w((ax + (bx - ax) * i / n, ay + (by - ay) * i / n)) for i in range(n + 1)) / (n + 1)
    else:
        s = w(light["pts"][0])
    room = light.get("room") or room_of(light["pts"][0] if light["kind"] == "dot" else
                                        ((light["pts"][0][0] + light["pts"][1][0]) / 2, (light["pts"][0][1] + light["pts"][1][1]) / 2), None)
    if here and room and room != here:
        s *= float(ent.get("other_room_factor", 0.3))
    return s


def _write(light: dict[str, Any], level: int) -> None:
    if light["device"] == "strip":
        tools.call("strip_set", on=level > 0, percent=max(level, 1))
    else:
        tools.call("hue_light_set", light=light["id"], on=level > 0, percent=max(level, 1))


def _timed_write(light: dict[str, Any], level: int) -> float:
    t0 = time.monotonic()
    _write(light, level)
    return time.monotonic() - t0


def walk(hz: float = 10.0, dry: bool = False) -> dict[str, Any]:
    """Runs the entity along the map's path in real time and drives the real lights.

    Order: every light to 0 and WAIT for all of it to land (the room starts fully dark and the first latency of each light
    is measured); then the walk, where each light updates as soon as its previous write has finished and the level moved
    by at least `min_step` (so a fast strip steps often and a slow lamp steps as often as the cloud lets it); then all off.
    Returns seconds, writes, errors, rooms crossed, and the measured latency per light."""
    m = load_map()
    pts, ent, lights, rooms = m["path"], m.get("entity", {}), m.get("lights", []), m.get("rooms", [])
    if len(pts) < 2:
        raise ValueError("map.json has fewer than 2 path points; draw the path on the remote and save")
    for L in lights:
        c = L["pts"][0] if L["kind"] == "dot" else ((L["pts"][0][0] + L["pts"][1][0]) / 2, (L["pts"][0][1] + L["pts"][1][1]) / 2)
        L["room"] = room_of(c, rooms)
    speed = float(ent.get("speed_px_s", 60))
    min_step = int(ent.get("min_step", 4))
    floor = int(ent.get("floor", 6))          # below this the light is simply off: far means dark
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
    last: dict[str, int] = {}
    writes = errors = 0

    def settle(fut, lid):
        nonlocal errors
        try:
            lat[lid].append(fut.result(timeout=30))
        except Exception as e:  # noqa: BLE001  (the failed write has its own ledger row)
            errors += 1
            log("field", "write failed", light=lid[:8], err=f"{type(e).__name__}: {str(e)[:80]}")

    with step("field", "field.walk", "map", {"path_pts": len(pts), "lights": len(lights), "radius": ent.get("radius_px"),
                                             "falloff": ent.get("falloff"), "speed": speed, "seconds": round(total / speed, 1), "dry": dry}) as r:
        # dark start: everything off, and wait for it
        t_dark = time.monotonic()
        if not dry:
            futs = {L["id"]: pool.submit(_timed_write, L, 0) for L in lights}
            for lid, fut in futs.items():
                settle(fut, lid)
            writes += len(futs)
        for L in lights:
            last[L["id"]] = 0
        dark_ms = round((time.monotonic() - t_dark) * 1000)
        log("field", "dark, starting", ms=dark_ms, latency={L.get("label", L["id"])[:12]: round(1000 * lat[L["id"]][-1]) if lat[L["id"]] else None for L in lights})
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
                    log("field", f"{L.get('label', lid)[:18]} -> {level}%", room=here or "-", x=int(p[0]), y=int(p[1]))
                    if not dry:
                        inflight[lid] = pool.submit(_timed_write, L, level)
            if s >= total:
                break
            time.sleep(1 / hz)
        for lid, fut in list(inflight.items()):
            settle(fut, lid)
        for L in lights:                                 # ends dark, and wait for it
            writes += 1
            if not dry:
                inflight[L["id"]] = pool.submit(_timed_write, L, 0)
        for lid, fut in inflight.items():
            settle(fut, lid)
        pool.shutdown(wait=True)
        latency = {L.get("label", L["id"]): (round(1000 * sum(lat[L["id"]]) / len(lat[L["id"]])) if lat[L["id"]] else None) for L in lights}
        out = {"seconds": round(time.monotonic() - t0, 1), "dark_ms": dark_ms, "writes": writes, "errors": errors,
               "rooms": rooms_seen, "latency_ms": latency, "lights": [L.get("label", L["id"]) for L in lights]}
        r["state_after"] = out
        return out
