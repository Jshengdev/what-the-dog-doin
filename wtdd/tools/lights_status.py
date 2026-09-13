"""Read every light back: the Hue lights (name, room, on, brightness) and the Tuya strip (on, brightness, temp)."""
NAME, DOC = "lights_status", __doc__.strip()
ARGS = {}


def run():
    from ..hue.api import HueBridge, summary
    from ..tuya.__main__ import device, read
    b = HueBridge.from_env()
    rooms = {}
    for room in b.rooms():
        for ch in room.get("children", []):
            rooms[ch["rid"]] = room["metadata"]["name"]
    hue = [{"id": l["id"], "name": l["metadata"]["name"], "room": rooms.get(l.get("owner", {}).get("rid")), **summary(l)} for l in b.lights()]
    try:
        strip = read(device())
    except Exception as e:  # noqa: BLE001  (reported as an error field, never as fake state)
        strip = {"error": f"{type(e).__name__}: {e}"}
    strip.pop("raw", None)
    return {"hue": hue, "strip": strip}
