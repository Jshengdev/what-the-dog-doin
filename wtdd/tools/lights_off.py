"""Living room off: the four Hue lights in the zone and the Tuya strip, each read back."""
NAME, DOC = "lights_off", __doc__.strip()
ARGS = {}


def run():
    from ..commands import lights
    return {"result": lights(False)}
