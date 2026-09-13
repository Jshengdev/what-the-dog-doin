"""Walk the entity along the path drawn on the map and drive the real lights by the field (closer = brighter, the strip
scored along its length, other rooms dimmed). The same walk the remote's button runs. Returns seconds, writes, rooms."""
ARGS = {"dry": {"type": "boolean", "default": False, "doc": "true = compute and log levels, write nothing"}}


def run(dry=False):
    from ..field import walk
    return walk(dry=dry)
