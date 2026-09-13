"""Living room on: the four Hue lights in the zone (cloud) and the Tuya strip (local), each read back."""
NAME, DOC = "lights_on", __doc__.strip()
ARGS = {"percent": {"type": "number", "default": None, "doc": "optional brightness 0 to 100"}}


def run(percent=None):
    from ..commands import lights
    return {"result": lights(True, percent)}
