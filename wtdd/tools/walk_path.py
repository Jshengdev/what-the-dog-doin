"""Walk the entity along the path drawn on the map and drive the real lights by the field (closer = brighter, the strip
scored along its length, other rooms dimmed), pausing at the map's stops. The same walk the remote's button runs; the
chat's wake sequence calls wtdd.field.walk directly to hang its look-and-say on the stops. Returns seconds, writes,
rooms, stops."""
ARGS = {"dry": {"type": "boolean", "default": False, "doc": "true = compute and log levels, write nothing"}}


def run(dry=False):
    from ..field import walk
    return walk(dry=dry)
