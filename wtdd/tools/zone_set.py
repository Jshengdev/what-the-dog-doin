"""Set one Hue zone from wtdd/hue/zones.json (a, b, c, living room) on or off with optional brightness, read back per light.
This is the primitive the follow-the-body loop and the map page use."""
NAME, DOC = "zone_set", __doc__.strip()
ARGS = {"zone": {"type": "string", "default": "a"}, "on": {"type": "boolean", "default": True},
        "percent": {"type": "number", "default": None}}


def run(zone="a", on=True, percent=None):
    from ..hue.api import HueBridge
    from ..hue.__main__ import set_zone
    on = on if isinstance(on, bool) else str(on).lower() in ("1", "true", "on", "yes")
    return set_zone(HueBridge.from_env(), zone, on, float(percent) if percent is not None else None)
