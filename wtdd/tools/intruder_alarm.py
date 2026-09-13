"""Stranger in the house: a photo (level by default, the fastest look; tilt or sit if the face is higher), the
detector's boxes on it, "STRANGER DANGER!!!" three times to the castle with the picture, then the living room strobes
red and blue for N seconds (light_alarm). Triggered by python -m wtdd.watch when the intruder watch is armed (GET/POST
/intruder) and a person is in view for a few frames, at most once a minute; or by hand. One intruder.alarm row around
the look, the boxes, the post and the lights; each part has its own rows. Nothing here retries."""
ARGS = {"look": {"type": "string", "default": "level", "doc": "level | tilt | sit"},
        "seconds": {"type": "number", "default": 5},
        "trigger": {"type": "string", "default": None, "doc": "idempotence key of the post; defaults to intruder-<epoch>"}}

TEXT = "STRANGER DANGER!!! STRANGER DANGER!!! STRANGER DANGER!!!"


def run(look="level", seconds=5, trigger=None):
    import time
    from ..commands import look as _look
    from ..ledger import step
    from . import chat_post, light_alarm
    from .dog_say import boxed
    with step("central", "intruder.alarm", "wtdd", {"look": look, "seconds": seconds}) as r:
        shot = _look(look)
        file, det = shot["file"], None
        try:
            det = boxed(file)
            file = det["file"]
        except Exception as e:  # noqa: BLE001  (the plain photo is posted; the failure is on its own watch.boxes row)
            det = {"error": f"{type(e).__name__}: {str(e)[:100]}"}
        post = chat_post.run(text=TEXT, file=file, trigger=trigger or f"intruder-{int(time.time())}")
        lights = light_alarm.run(seconds=seconds)
        out = {"file": file, "pitch_deg": shot.get("pitch_deg"), "detector": det, "post": post, "lights": lights, "text": TEXT}
        r["state_after"] = {k: out[k] for k in ("file", "pitch_deg", "lights")} | {"posted": post.get("rowid"), "classes": (det or {}).get("classes")}
        return out
