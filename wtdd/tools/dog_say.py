"""Look and say: the dog nods and photographs (dog_look, tilt by default), the frame goes to the vision model, and the
one sentence plus the photo are posted to the castle behind the gate and the never-twice claim. Returns the look's
fields (file, pitch_deg, fired, attempts), text, person, out_of_place, baseline, model, vision_ms and the confirmed
post row. look_and_see() is the half without the post: the chat listener calls it and posts under the wake message's
guid (say:<guid>), and sounds light_alarm when person is true.

  python -m wtdd dog_say                          nod, look, say, post (trigger defaults to say-<epoch>)
  python -m wtdd dog_say look=sit trigger=k       the sit look; trigger is the idempotence key of the post
  python -m wtdd dog_say baseline=true stop=2     capture this look at map stop 2 as its tidy reference (DEMO_CACHE below), no post
Vision: OPENROUTER_VISION_MODEL (x-ai/grok-4.20, about 1 s on a dog frame), the JSON prompt below, the frame (and the
tidy baseline when one exists) downscaled to 640 px wide and sent as base64 JPEG. The reply must be JSON with say,
person and out_of_place, or the call raises (no canned sentence, CLAUDE.md section 2); say over 140 characters is cut
at a word with a WARN. One llm.generate row (agent watch) per look. A tilt that did not fire (fired=False, IMU-checked
in wtdd/dog/session.py) still yields a real frame and a real sentence; the result says so."""
ARGS = {"look": {"type": "string", "default": "tilt", "doc": "tilt | level | sit"},
        "trigger": {"type": "string", "default": None, "doc": "idempotence key of the post; defaults to say-<epoch>"},
        "baseline": {"type": "boolean", "default": False, "doc": "true = capture this look as the tidy reference, no post"},
        "stop": {"type": "number", "default": None, "doc": "map stop index the dog is at (picks that stop's tidy baseline)"}}

SYSTEM = (
    "You are a robot dog's eyes on a night round of a shared house. Floor-level camera. Reply with JSON only: "
    '{"say": <one casual sentence under 140 characters for the housemates\' group chat: what you see and anything out of '
    "place (cups, clothes, trash, bags on the floor); if a sock or clothes are on the floor ask whose they are; no "
    'adjectives, no dashes, no names of people, say "someone" if a person is in view>, '
    '"person": <true if any person is in view, else false>, '
    '"out_of_place": <a list of short names of the things out of place, [] if none>}. '
    "If an image labeled tidy is given, it is the same spot when it was tidy: report only what is new or moved since."
)
MAX_CHARS = 140
WIDTH = 640
PICTURES = "~/Pictures/wtdd"


def _part(file: str) -> dict:
    import base64
    import io
    from PIL import Image
    img = Image.open(file).convert("RGB")
    img.thumbnail((WIDTH, WIDTH))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}}


def see(file: str, baseline: str | None = None) -> dict:
    """The frame at `file` (and the tidy baseline, if any) to the vision model. Returns {text, person, out_of_place,
    model, ms}; raises on an empty or malformed reply (no canned sentence)."""
    import json
    import time
    from ..ledger import log
    from ..llm import generate
    content = []
    if baseline:
        content += [{"type": "text", "text": "this is the spot when it was tidy:"}, _part(baseline)]
    content += [{"type": "text", "text": "this is now. what do you see?"}, _part(file)]
    t0 = time.perf_counter()
    out = generate("watch", [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}],
                   max_tokens=160, temperature=0.3, response_format={"type": "json_object"})
    raw = out["text"].strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        d = json.loads(raw)
        text = " ".join(str(d["say"]).split())
        person = bool(d["person"])
        items = [str(x) for x in d.get("out_of_place") or []]
    except (ValueError, KeyError, TypeError) as e:
        raise RuntimeError(f"vision model reply is not the expected JSON ({type(e).__name__}: {e}): {raw[:160]!r}") from None
    if not text:
        raise RuntimeError(f"vision model returned an empty sentence (model={out['model']})")
    if len(text) > MAX_CHARS:
        log("watch", f"WARN sentence {len(text)} chars, cut to {MAX_CHARS}")
        text = text[:MAX_CHARS].rsplit(" ", 1)[0]
    ms = round((time.perf_counter() - t0) * 1000)
    log("watch", f"saw: {text}", person=person, out_of_place=len(items), baseline=bool(baseline), model=out["model"], ms=ms)
    return {"text": text, "person": person, "out_of_place": items, "model": out["model"], "ms": ms}


def tidy_path(look: str, stop: int | None = None) -> str:
    import os
    return os.path.expanduser(f"{PICTURES}/tidy-{look}" + (f"-stop{stop}" if stop is not None else "") + ".jpg")


def look_and_see(look: str = "tilt", stop: int | None = None) -> dict:
    """The look (through the API while it owns the dog), then the sentence. Posts nothing. `stop` is the map stop index
    the dog is at, which picks that stop's tidy baseline when one was captured."""
    import os
    from ..commands import look as _look
    shot = _look(look)
    # DEMO_CACHE: tidy baseline frame (~/Pictures/wtdd/tidy-<look>[-stop<i>].jpg). What: the same look at the same stop,
    # captured when the spot was tidy, so the model reports only what changed. Why: a tripod and a bin that always sit
    # there are not "out of place". Live: `python -m wtdd dog_say baseline=true stop=<i>` recaptures it with the real dog
    # at that stop; delete the file to run without one (the model then judges the frame on its own, which is logged).
    tidy = tidy_path(look, stop)
    has = os.path.isfile(tidy)
    seen = see(shot["file"], tidy if has else None)
    return {**shot, **seen, "vision_ms": seen.pop("ms"), "stop": stop, "baseline": tidy if has else None}


def run(look="tilt", trigger=None, baseline=False, stop=None):
    import shutil
    import time
    from . import chat_post
    stop = int(stop) if stop is not None else None
    if baseline:   # capture the tidy reference for this look (and stop): no model call, no post
        from ..commands import look as _look
        shot = _look(look)
        shutil.copy2(shot["file"], tidy_path(look, stop))
        return {**shot, "baseline": tidy_path(look, stop), "text": "tidy baseline captured"}
    out = look_and_see(look, stop)
    out["post"] = chat_post.run(text=out["text"], file=out["file"], trigger=trigger or f"say-{int(time.time())}")
    return out
