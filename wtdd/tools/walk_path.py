"""Walk the route and drive the real lights by the field (closer = brighter, the strip scored along its length, other
rooms dimmed), pausing at the map's stops. source=entity: a simulated entity walks the drawn path in real time (the dog
is hand-driven). source=dog: the API's follower drives the real dog along the same path (calibrated, avoidance on) and
the lights follow where it believes it is; the walk ends when the follower ends. The same walk the remote's button
runs; the chat's wake sequence calls wtdd.field.walk directly to hang its look-and-say on the stops. Returns seconds,
writes, rooms, stops."""
ARGS = {"dry": {"type": "boolean", "default": False, "doc": "true = compute and log levels, write nothing"},
        "source": {"type": "string", "default": "entity", "doc": "entity | dog"}}


def run(dry=False, source="entity"):
    from ..field import MAP, walk
    if source == "dog":
        import json
        from ..commands import _via_api
        via = _via_api("walk_path", dry=dry, source=source)   # the API process owns the dog: it runs the whole round
        if via is not None:
            return via
        from ..dog.session import DogSession
        m = json.loads(MAP.read_text())
        DogSession.get().follow(m["path"], [int(i) for i in m.get("stops", [])])
    return walk(dry=dry, source=source)
