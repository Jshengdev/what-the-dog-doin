"""Living room to a brightness percent (Hue zone + strip), read back."""
NAME, DOC = "lights_dim", __doc__.strip()
ARGS = {"percent": {"type": "number", "default": 20, "doc": "0 to 100"}}


def run(percent=20):
    from ..commands import lights
    return {"result": lights(True, float(percent))}
