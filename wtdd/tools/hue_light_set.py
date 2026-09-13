"""Set one Hue light by name or id (on/off, brightness percent), read back. The proximity field uses this per lamp."""
NAME, DOC = "hue_light_set", __doc__.strip()
ARGS = {"light": {"type": "string", "default": "special"}, "on": {"type": "boolean", "default": True},
        "percent": {"type": "number", "default": None}}


def run(light="special", on=True, percent=None):
    from ..hue.api import HueBridge
    from ..hue.__main__ import resolve
    on = on if isinstance(on, bool) else str(on).lower() in ("1", "true", "on", "yes")
    b = HueBridge.from_env()
    return b.set(resolve(b.lights(), light)["id"], on=on, bri=(float(percent) if (percent is not None and on) else None))
