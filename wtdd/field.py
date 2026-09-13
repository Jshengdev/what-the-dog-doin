"""The field: an entity with a radius walks the path drawn on the map; each light's brightness is how much of it sits
inside that radius, weighted toward the center; lights in rooms the entity is not in are scaled down. One
implementation, used by the wake demo in the chat and by the remote's button (the page only animates the dot).

  lamp:  score = (1 - d/R) ** falloff at the lamp's point
  strip: the mean of that over `samples` points along its line (a graze at the edge is dim, a pass over the middle is bright)
  rooms: score *= other_room_factor when the light's room is not the entity's room
Real writes go through the tool registry (hue_light_set, strip_set), one thread per light so a slow lamp never
stalls the timeline, throttled to a change of at least 10 points and 1.2 s per light.
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


def walk(hz: float = 8.0, dry: bool = False) -> dict[str, Any]:
    """Runs the entity along the map's path in real time and drives the real lights. Returns what it did."""
    m = load_map()
    pts, ent, lights, rooms = m["path"], m.get("entity", {}), m.get("lights", []), m.get("rooms", [])
    if len(pts) < 2:
        raise ValueError("map.json has fewer than 2 path points; draw the path on the remote and save")
    for L in lights:  # room membership from the polygons, once
        c = L["pts"][0] if L["kind"] == "dot" else ((L["pts"][0][0] + L["pts"][1][0]) / 2, (L["pts"][0][1] + L["pts"][1][1]) / 2)
        L["room"] = room_of(c, rooms)
    speed = float(ent.get("speed_px_s", 60))
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

    sent: dict[str, tuple[int, float]] = {}
    writes = 0
    pool = ThreadPoolExecutor(max_workers=max(1, len(lights)))
    futures = []
    with step("field", "field.walk", "map", {"path_pts": len(pts), "lights": len(lights), "radius": ent.get("radius_px"),
                                             "speed": speed, "seconds": round(total / speed, 1), "dry": dry}) as r:
        t0 = time.monotonic()
        rooms_seen: list[str] = []
        while True:
            s = min(total, (time.monotonic() - t0) * speed)
            p = at(s)
            here = room_of(p, rooms)
            if here and (not rooms_seen or rooms_seen[-1] != here):
                rooms_seen.append(here)
            now = time.monotonic()
            for L in lights:
                level = int(round(100 * score(L, p, ent, here)))
                prev, t = sent.get(L["id"], (-1, 0.0))
                if abs(level - prev) >= 10 and now - t >= 1.2:
                    sent[L["id"]] = (level, now)
                    writes += 1
                    log("field", f"{L.get('label', L['id'])[:18]} -> {level}%", room=here or "-", x=int(p[0]), y=int(p[1]))
                    if not dry:
                        futures.append(pool.submit(_write, L, level))
            if s >= total:
                break
            time.sleep(1 / hz)
        for L in lights:  # the walk ends with everything off
            writes += 1
            if not dry:
                futures.append(pool.submit(_write, L, 0))
        errors = 0
        for f in futures:
            try:
                f.result(timeout=30)
            except Exception as e:  # noqa: BLE001  (each failed write already has its own ledger row)
                errors += 1
                log("field", "write failed", err=f"{type(e).__name__}: {str(e)[:80]}")
        pool.shutdown(wait=True)
        out = {"seconds": round(time.monotonic() - t0, 1), "writes": writes, "errors": errors, "rooms": rooms_seen,
               "lights": [L.get("label", L["id"]) for L in lights]}
        r["state_after"] = out
        return out
