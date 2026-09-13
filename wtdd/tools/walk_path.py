"""Walk the entity along the path drawn on the map and drive the real lights by the field (closer = brighter, the strip
scored along its length, other rooms dimmed). The same walk the remote's button runs. Returns seconds, writes, rooms."""
NAME, DOC = "walk_path", __doc__.strip()
ARGS = {"dry": {"type": "boolean", "default": False, "doc": "true = compute and log levels, write nothing"}}


def run(dry=False):
    from ..field import walk
    dry = dry if isinstance(dry, bool) else str(dry).lower() in ("1", "true", "yes")
    return walk(dry=dry)
