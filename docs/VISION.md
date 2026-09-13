# VISION: the dog sits, looks, and reports what is out of place

Reference for step 4 of `SCOPE-LOCK.md` §3: "the dog sits; a camera frame is captured; vision compares it to the baseline and lists what is out of place." Johnny's words: "the dog sits down and looks at the scene and it's like oh, a broken light... you'll see if anything's out of place or if anything's changed"; "socks on the floor... tracking for messes on the ground"; "will it be able to see up here? Not up there." The camera is at floor height, so this step is floor-level by design (CUT list: no table tops unless the dog stands).

Gradeable claims this step must support: a planted object on the floor is found (recall); an empty floor is reported empty (no hallucinated mess); a light the API says is on but the camera sees off is flagged. Everything else is optional.

**Sources** (cited inline): [DRV] https://github.com/legion1581/unitree_webrtc_connect (files `examples/go2/video/camera_stream/display_video_channel.py`, `unitree_webrtc_connect/webrtc_driver.py`, `webrtc_video.py`, `webrtc_datachannel.py`, `pyproject.toml`, read 2026-09-12) · [VIS] https://platform.claude.com/docs/en/build-with-claude/vision · [SO] https://platform.claude.com/docs/en/build-with-claude/structured-outputs · [PYAV] https://pyav.org/docs/stable/api/video.html · [SKILL] the `claude-api` skill (model ids, pricing, effort, error classes, image block shape, timeouts and retries) · [PYPI] https://pypi.org/pypi/<pkg>/json, checked 2026-09-12.

## 0. Install (macOS, Apple Silicon)

- Python 3.11 or newer in the dog process: `av` 18.1.0 requires >=3.11, `aiortc` 1.15.0 and `anthropic` 1.5.0 >=3.10 [PYPI]; the driver's own `requires-python >=3.8` [DRV] is older than its dependencies. `av` and `opencv-python` 5.0.0.93 ship macOS arm64 wheels; `aiortc` and `anthropic` are pure Python [PYPI]. Nothing on the video path compiles.
- The driver depends on `pyaudio` and `sounddevice` [DRV pyproject]; its Linux install line pulls `portaudio19-dev`. On macOS run `brew install portaudio` before `pip install unitree_webrtc_connect anthropic`, or pip fails building pyaudio. UNVERIFIED on this Mac; the failure, if it happens, is at install time and obvious.
- Never call `cv2.imshow` in the dog process. We are headless; encode to JPEG and write a file. (The upstream example opens a window on the main thread only because it is a viewer.)
- UNVERIFIED: macOS may prompt for Local Network permission for `python` the first time it talks to the dog's IP. If `connect()` hangs with no ICE progress, check System Settings > Privacy & Security > Local Network.

## 1. Frame capture

How the driver exposes the camera [DRV]: `init_webrtc()` creates `self.video = WebRTCVideoChannel(pc, datachannel)` (a `recvonly` video transceiver). On the aiortc `"track"` event the driver itself does `await track.recv()` once (discards frame 1, its comment says "Discard first frame") and then awaits every callback registered with `conn.video.add_track_callback(cb)`, passing the live `MediaStreamTrack`. Callbacks run sequentially, so one callback that loops forever is the whole reader. `conn.video.switchVideoChannel(True)` publishes `"on"` on the `VID` data-channel topic; nothing arrives until that is sent. When the peer closes, `recv()` raises `MediaStreamError`, which the driver catches around the reader.

Register the callback **before** switching the channel on, then drain forever so aiortc's frame queue stays flat and `latest` is always the newest frame:

```python
# dog/camera.py  (inside the dog process's asyncio loop, next to the sport commands)
import asyncio, hashlib, json, time, cv2
from unitree_webrtc_connect.webrtc_driver import UnitreeWebRTCConnection, WebRTCConnectionMethod

def log(msg): print(f"[wtdd:vision] {msg}", flush=True)
def ledger(step, **row):
    row.update(step=step, ts=time.strftime("%Y-%m-%dT%H:%M:%S"))
    with open("ledger.jsonl", "a") as f: f.write(json.dumps(row) + "\n")

class Camera:
    def __init__(self): self.latest = None; self.n = 0; self.t0 = self.first_at = self.last_at = None
    async def drain(self, track):                        # driver awaits this with the live track [DRV]
        while True:
            self.latest = await track.recv()             # raises MediaStreamError on peer close [DRV]
            self.n += 1; self.last_at = time.monotonic()
            if self.n == 1:
                self.first_at = self.last_at
                log(f"first frame after {int((self.first_at - self.t0) * 1000)}ms shape={self.latest.to_ndarray(format='bgr24').shape}")
            elif self.n % 300 == 0:
                log(f"frames={self.n} fps={self.n / (self.last_at - self.first_at):.1f}")
    async def wait_ready(self, timeout_s=15.0):
        t = time.monotonic()
        while self.latest is None:
            if time.monotonic() - t > timeout_s: raise RuntimeError(f"track not ready after {timeout_s}s (frames=0)")
            await asyncio.sleep(0.05)
    def jpeg(self, path):
        if self.latest is None: raise RuntimeError("no frame yet")
        if time.monotonic() - self.last_at > 2.0: raise RuntimeError(f"track stale: last frame {time.monotonic() - self.last_at:.1f}s ago (n={self.n})")
        img = self.latest.to_ndarray(format="bgr24")     # PyAV VideoFrame.to_ndarray; to_image() gives PIL [PYAV]
        luma = float(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).mean())
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok: raise RuntimeError("jpeg encode failed")
        data = buf.tobytes(); open(path, "wb").write(data)
        r = {"path": path, "w": img.shape[1], "h": img.shape[0], "bytes": len(data), "luma": round(luma, 1),
             "frame_sha256": hashlib.sha256(data).hexdigest(), "frames_seen": self.n}
        log(f"captured {path} {r['w']}x{r['h']} bytes={r['bytes']} luma={r['luma']} sha256={r['frame_sha256'][:12]} (n={self.n})")
        ledger("vision.capture", app="unitree", op="video.track.recv", status="ok", **r)
        return r

async def open_camera(conn: UnitreeWebRTCConnection) -> Camera:
    cam = Camera()
    conn.video.add_track_callback(cam.drain)             # before switch-on, or the first frames are handed to nobody
    cam.t0 = time.monotonic(); conn.video.switchVideoChannel(True)
    await cam.wait_ready()
    return cam
# usage, once per process:  await conn.connect(); cam = await open_camera(conn)
# per look-point:            receipt = cam.jpeg(f"frames/{time.strftime('%Y%m%dT%H%M%S')}_{lookpoint}.jpg")
```

- **Warm-up.** The driver discards frame 1 itself [DRV]. Time from `switchVideoChannel(True)` to the first usable frame is UNVERIFIED; the `first frame after Nms` line is the number, do not type one.
- **Resolution and rate.** UNVERIFIED. The upstream example's placeholder window is 1280x720 [DRV], which is a hint, not a fact. The `shape=` and `fps=` log lines are the facts; put those in the brief.
- **Serving "latest frame."** The track lives in the dog process; `cam.jpeg()` is the on-demand read. If central is another process (Node), the dog sidecar answers `GET /frame.jpg` by calling `cam.jpeg()` and returning the file; stdlib `http.server.ThreadingHTTPServer` in a thread is enough, no new dependency. Reading `cam.latest` from that thread is safe (it is one reference swap).
- **Receipt.** `frame_sha256` is the hash of the exact JPEG bytes on disk, which are the bytes the group chat receives. It appears in the `vision.capture` row and again in the `vision.call` row so the two can be joined.

## 2. The vision call

- **Model: `claude-opus-5`** [SKILL]. Reasons: it is the skill's default and its strongest vision tier; models 4.7 and later run the high-resolution tier (long edge up to 2576 px, up to 4784 visual tokens per image, no downscale of a 1280x720 frame) [VIS]. Price $5 in / $25 out per MTok [SKILL]. Adaptive thinking runs when `thinking` is omitted; `temperature`/`top_p`/`top_k` return 400 on Opus 5, so none are sent [SKILL].
- **Cost per look.** A 1280x720 frame costs ceil(1280/28) x ceil(720/28) = 46 x 26 = 1196 visual tokens [VIS formula]. Two images (baseline + current) plus about 700 prompt tokens and about 300 output tokens is roughly 3.1k in and 0.3k out, about $0.023 per look at the prices above. Cheap enough to run every eval trial live.
- **Latency.** UNVERIFIED until measured; it is the `ms` field of the `vision.call` ledger row. `output_config.effort: "low"` is the latency knob [SKILL]; raise to `medium` only if eval scenario (a) loses recall. The first request with a new schema pays grammar compilation, cached for 24 h after last use [SO], so run one warm-up look at setup, before the demo.
- **Image size.** Send the frame as captured. Hard caps: 10 MB base64 per image on the Claude API, 8000x8000 px [VIS]; our JPEG is far below both. If a long edge ever exceeds 2576 px, `cv2.resize` it down first, since the API would downscale anyway and coordinates would drift [VIS].
- **Refusal fallback: deliberately off.** The skill recommends the server-side `fallbacks` parameter for Opus 5 code. This repo does not enable it: a `stop_reason: "refusal"` on a photo of a floor is a step failure to see in the ledger, not something to re-route to another model behind a 200 (CLAUDE.md §2).

```python
# vision/look.py
import base64, json, time, cv2, anthropic          # cv2: used by scene_diff_pct and light_check below, same file
from anthropic import transform_schema
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from dog.camera import log, ledger

MODEL = "claude-opus-5"
client = anthropic.Anthropic()                     # ANTHROPIC_API_KEY or `ant auth login` profile [SKILL]

class FloorObject(BaseModel):
    label: str = Field(description="short noun, e.g. cup, sock, shirt, cable")
    location_in_frame: str = Field(description="one of: left, center, right, plus near or far, e.g. 'left near'")
    confidence: float = Field(ge=0, le=1)
class Lights(BaseModel):
    visible_fixtures: list[str] = Field(description="fixture ids from the list that are in view")
    which_appear_on: list[str]
    which_appear_off: list[str]
class VisionReport(BaseModel):
    objects_on_floor: list[FloorObject]
    lights: Lights
    people_present: int
    baseline_used: bool
    changes_vs_baseline: list[str]
    nothing_out_of_place: bool
    too_dark_to_judge: bool
    summary_for_group_chat: str = Field(description="one sentence, under 140 characters, no adjectives, no names")

SCHEMA = transform_schema(TypeAdapter(VisionReport).json_schema())   # strips ge/le, adds additionalProperties:false [SO]

def img_block(path):
    with open(path, "rb") as f:
        return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                            "data": base64.standard_b64encode(f.read()).decode("utf-8")}}  # [SKILL]

def look(current, baseline, lookpoint, fixtures, frame_sha256, source="live"):
    content = []
    if baseline: content += [{"type": "text", "text": "BASELINE frame (earlier today, same spot, lights known on):"}, img_block(baseline)]
    content += [{"type": "text", "text": "CURRENT frame:"}, img_block(current),
                {"type": "text", "text": USER_PROMPT.format(lookpoint=lookpoint, fixtures=json.dumps(fixtures),
                                                            baseline_line="Compare CURRENT with BASELINE." if baseline else "No baseline exists yet: set baseline_used=false and changes_vs_baseline=[].")}]
    base = dict(app="anthropic", op="messages.create", model=MODEL, frame_sha256=frame_sha256, baseline=baseline, source=source, lookpoint=lookpoint)
    t = time.monotonic()
    try:
        r = client.with_options(timeout=60.0, max_retries=0).messages.create(   # max_retries=0: a 429 is recorded, never silently retried [SKILL]
            model=MODEL, max_tokens=2048, system=SYSTEM_PROMPT, messages=[{"role": "user", "content": content}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}})            # [SKILL][SO]
    except anthropic.RateLimitError as e:
        ledger("vision.call", status=429, retry_after=e.response.headers.get("retry-after"), ms=int((time.monotonic() - t) * 1000), **base); raise
    except anthropic.APITimeoutError:
        ledger("vision.call", status="timeout", ms=int((time.monotonic() - t) * 1000), **base); raise
    except anthropic.APIStatusError as e:
        ledger("vision.call", status=e.status_code, error=e.message, ms=int((time.monotonic() - t) * 1000), **base); raise
    except anthropic.APIConnectionError as e:
        ledger("vision.call", status="connection", error=str(e), ms=int((time.monotonic() - t) * 1000), **base); raise
    ms = int((time.monotonic() - t) * 1000)
    text = next((b.text for b in r.content if b.type == "text"), "")
    if r.stop_reason != "end_turn":                    # "refusal" or "max_tokens": output may not match the schema [SO]
        ledger("vision.call", status="fail", stop_reason=r.stop_reason, raw_text=text, ms=ms, **base)
        raise RuntimeError(f"vision call stopped with {r.stop_reason} (see ledger)")
    try:
        report = VisionReport.model_validate_json(text)
    except ValidationError as e:
        ledger("vision.call", status="invalid_json", raw_text=text, error=str(e), ms=ms, **base)
        raise RuntimeError("vision JSON failed validation (raw text kept in ledger)")
    derived = not report.objects_on_floor and not report.lights.which_appear_off and report.people_present == 0 and not report.changes_vs_baseline
    if derived != report.nothing_out_of_place:
        log(f"WARN nothing_out_of_place={report.nothing_out_of_place} but fields say {derived}; fields win")
    ledger("vision.call", status="ok", ms=ms, input_tokens=r.usage.input_tokens, output_tokens=r.usage.output_tokens,
           request_id=r._request_id, report=report.model_dump(), **base)
    log(f"report objects={len(report.objects_on_floor)} lights_off={len(report.lights.which_appear_off)} people={report.people_present} changes={len(report.changes_vs_baseline)} ({ms}ms, in={r.usage.input_tokens} out={r.usage.output_tokens})")
    return report
```

Schema notes [SO]: every field is required (the 24-optional-parameter cap is not an issue), no numeric constraints on the wire (`transform_schema` moves `ge/le` into the description; Pydantic re-checks them locally in `model_validate_json`), no enums, so the enum-casing caveat does not apply. Grammar applies only to the final text block, not to thinking [SO].

## 3. Baseline comparison

The honest answer to "has anything changed" is a second photo, not memory. At the start of the day, per look-point, with the dog at the same spot and heading and the lights in a known state, run `make-baseline <lookpoint>`: it captures `baselines/<lookpoint>.jpg` and writes `baselines/<lookpoint>.json` with `captured_at`, `heading`, `lights_state` (read back from the lights API at that moment), `frame_sha256`, and for each fixture in view its ROI luminance with the zone on and again with it off (§4 needs both). The look step then sends baseline + current as two images in one call (§2) and asks for differences.

First run of the day, or a missing baseline file: skip the second image, pass `baseline=None`, the prompt tells the model to set `baseline_used=false`, and the ledger row carries `baseline: null`. The group-chat sentence then ends with "(no baseline yet)". Never substitute another day's baseline.

Cheap pre-check, logged before the model call so the ledger has a number that does not depend on the model:

```python
def scene_diff_pct(baseline_jpg, current_jpg):
    g = lambda p: cv2.resize(cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2GRAY), (160, 90)).astype("float32")
    pct = float(abs(g(baseline_jpg) - g(current_jpg)).mean() / 255 * 100)
    log(f"scene changed vs baseline: {pct:.1f}% ({baseline_jpg} -> {current_jpg})")
    ledger("vision.diff", baseline=baseline_jpg, current=current_jpg, scene_diff_pct=round(pct, 1))
    return pct     # a receipt, never a gate: a sock is under 2% of a frame; a big number explains a wild report (lights off, wrong heading)
```

## 4. The broken-light check

The lights API returning 200 with `on: true` is locally correct; the room being dark is the globally wrong part, and this cross-check is the one place the agent catches its own world model being wrong from device state. That is the check the judges' benchmark grades from before-and-after state.

Rule, per fixture in view at the look-point (`api_state` from Hue CLIP v2 or Tuya read-back in step 3 of the round):

```python
def light_check(zone, fixture_id, api_state, report, current_jpg, roi_box, luma_on, luma_off):
    x0, y0, x1, y1 = roi_box                                                   # from baselines/<lookpoint>.json
    roi = float(cv2.cvtColor(cv2.imread(current_jpg), cv2.COLOR_BGR2GRAY)[y0:y1, x0:x1].mean())
    split = (luma_on + luma_off) / 2                                           # measured at baseline time, not typed
    api_on, seen_on = bool(api_state["on"]), fixture_id in report.lights.which_appear_on
    row = dict(zone=zone, fixture=fixture_id, state_api={"on": api_on, "brightness": api_state.get("brightness")},
               state_seen={"appears_on": seen_on, "roi_luma": round(roi, 1), "roi_split": round(split, 1), "roi_says_on": roi >= split},
               agree=(api_on == seen_on))
    ledger("vision.light_check", **row)
    if not row["agree"]: log(f"WARN light mismatch zone={zone} fixture={fixture_id} api_on={api_on} seen_on={seen_on} roi_luma={roi:.1f} split={split:.1f}")
    return row
```

`agree=false` with `api_on=true` is reported as "light <fixture> should be on but looks off" and the round marks the zone for a human. The model's verdict decides `state_seen.appears_on`; `roi_luma` is the numeric receipt beside it. If the two disagree with each other, the row shows it and the sentence says "unsure" rather than "broken." Nothing is toggled in response; this step only reports.

## 5. Eval with planted truth

Three scenarios, three trials each, run in the real room with the real dog. `evals/vision/frames/<scenario>/<trial>.jpg` plus `evals/vision/frames/<scenario>/truth.json`:

| scenario | truth.json | pass rule (from the JSON fields, never the sentence) |
|---|---|---|
| a. planted | `{"planted": ["sock"], "light_api_on": true, "light_seen_on": true}` | some `objects_on_floor[].label` matches the planted label (synonym list: cup/mug, sock/socks, shirt/clothes) with `confidence >= 0.6`; `people_present == 0` |
| b. empty | `{"planted": [], "light_api_on": true, "light_seen_on": true}` | `objects_on_floor == []` and `nothing_out_of_place == true` (or `baseline_used == false` with all other fields clean) |
| c. dark fixture | `{"planted": [], "light_api_on": true, "light_seen_on": false}` (switched off by hand at the wall, API still says on) | `vision.light_check.agree == false` and the fixture id is in `lights.which_appear_off` |

Grades: **pass** as above; **fail** otherwise, with the failing field named in the result row; **unsafe** overrides both when the run would have posted something prohibited: `summary_for_group_chat` contains a housemate name from `config/housemates.json` (or `people_present > 0` and any name at all), or the sentence claims an object whose `confidence < 0.6`, or the step raised and a report was posted anyway. Precision and recall count the planted object only (one per trial): TP = planted and found, FN = planted and missed, FP = nothing planted and `objects_on_floor` non-empty at `confidence >= 0.6`. The printed table, pasted verbatim into `RELIABILITY-BRIEF.md`:

```
scenario   trials pass fail unsafe  TP FP FN  precision recall  mean_ms
a.planted       3    3    0      0   3  0  0      1.00   1.00     ....
b.empty         3    3    0      0   0  0  0       n/a    n/a     ....
c.dark          3    2    1      0   0  0  0       n/a    n/a     ....
```

Command: `python -m wtdd.eval_vision --trials 3` runs the three scenarios live (it prompts "plant the sock, press enter" between trials, captures through §1, calls §2, checks §4) and appends to `evals/vision/results.jsonl`. `python -m wtdd.eval_vision --frames evals/vision/frames --offline` skips capture, runs §2 and §4 on the recorded frames, prints `OFFLINE: recorded frames from <captured_at>` as the first line, and writes `source: "recorded"` on every ledger row. Offline numbers are labeled offline in the brief. Commit the eval failing first (before the prompt is tuned) so it has been seen to fail.

## 6. Prompt design notes

Floor-level framing, an explicit "empty is normal" so the model is not pushed to find something, uncertainty as a number, no names, a sentence the group would actually read. Fixture ids come from config so §4 can match them mechanically. The model is told what to ignore because the dog's own nose and legs and reflections off the floor are in most frames.

```python
SYSTEM_PROMPT = """You are the eyes of a small robot dog sitting on the floor of a shared house. The camera is at knee height: you see the floor and the lower part of the room. Table tops are out of view and out of scope.
Report only what you can actually see. If unsure, keep the item and give it a low confidence instead of dropping it or guessing. A floor with nothing on it is a normal, common answer.
Ignore: the dog's own body (nose, legs, the dark frame edge), reflections in glass or on the floor, shadows, lens glare, and furniture that belongs there.
Never identify, name, or describe any person. If people are in view, count them only.
summary_for_group_chat: one sentence, under 140 characters, plain nouns and counts, no adjectives, no names, no emoji, no exclamation marks, starting with the look-point name."""

USER_PROMPT = """Look-point: {lookpoint}. Fixture ids that should be visible: {fixtures}.
{baseline_line}
1. objects_on_floor: every loose object on the floor (cups, socks, clothes, bags, cables, wrappers). Not furniture. confidence from 0 to 1.
2. lights: which fixture ids appear lit and which appear unlit. Use only ids from the list. A fixture that is not in view goes in neither list.
3. people_present: how many people are in the CURRENT frame.
4. changes_vs_baseline: differences between BASELINE and CURRENT that matter (new object, missing object, a light changed, furniture or a door moved). Empty if there is no baseline.
5. nothing_out_of_place: true only if objects_on_floor is empty, which_appear_off is empty, people_present is 0, and changes_vs_baseline is empty.
6. too_dark_to_judge: true if the CURRENT frame is too dark to answer 1 and 2.
7. summary_for_group_chat, for example: "Hall-1: 1 sock on the floor, 2 of 2 lights on." or "Hall-1: nothing on the floor, 2 of 2 lights on (no baseline yet)." """
```

The model cannot be used to name people in images and refuses to [VIS Limitations]; the prompt says so anyway so the sentence never tries. Counting is approximate [VIS Limitations], which is why `people_present` gates a send but is never posted as a number.

## 7. Failure modes and loud logging

Every line is `[wtdd:vision] ...` with a count and a millisecond figure where one exists, so one grep of the console finds the symptom (CLAUDE.md §5). Every failure below writes a ledger row on the exact step before raising; nothing retries silently.

| symptom | detect | do | ledger row |
|---|---|---|---|
| frame black or too dark | `luma < 20` from `cam.jpeg()` (a physical floor, not app data; `# wtdd:` constant) | log `WARN dark frame luma=8.3`, ask the lights agent to light the zone, capture once more, then fail loud | `vision.capture status=dark luma=8.3 retry=1` |
| track not ready | `wait_ready()` times out with `frames=0` | fail the look; the dog step reports "camera track never started" | `vision.capture status=not_ready frames=0 ms=15000` |
| track stale | `jpeg()` sees the last frame older than 2 s | fail loud; the WebRTC peer likely dropped, `conn.reconnect()` is the operator's call, not a hidden loop | `vision.capture status=stale age_s=4.2 n=812` |
| API 429 | `anthropic.RateLimitError` with `max_retries=0` [SKILL] | record `retry-after`, fail the step; the round may re-run it once as a new, visible row | `vision.call status=429 retry_after=12` |
| API timeout or 5xx or network | `APITimeoutError`, `APIStatusError`, `APIConnectionError` [SKILL] | fail the step with the class and status in the row | `vision.call status=timeout ms=60012` |
| refusal or truncated output | `stop_reason` is `refusal` or `max_tokens` [SO] | fail the step, raw text kept | `vision.call status=fail stop_reason=refusal raw_text=...` |
| JSON fails validation | `pydantic.ValidationError` | fail the step, raw text kept, never patch the JSON | `vision.call status=invalid_json raw_text=...` |
| zero fixtures seen when config lists some | `lights.visible_fixtures == []` | WARN with the fixture list and heading; the light check for that look-point is marked `not_in_view`, not `agree` | `vision.light_check status=not_in_view` |

Shape of one good look on the console (format only; real numbers come from `ledger.jsonl`):

```
[wtdd:vision] captured frames/20260913T132005_hall-1.jpg 1280x720 bytes=142811 luma=96.4 sha256=3f9a1c07b2e4 (n=412)
[wtdd:vision] report objects=1 lights_off=0 people=0 changes=1 (4210ms, in=3088 out=241)
[wtdd:vision] WARN light mismatch zone=hall fixture=hall-lamp api_on=True seen_on=False roi_luma=21.0 split=58.5
```

## 8. DEMO_CACHE policy for this step (CLAUDE.md §2)

If the WebRTC video fights the stack on the day, the engineered half-half is: a frame **this dog captured earlier that day** from the same look-point, on disk with its ledger `vision.capture` row and `frame_sha256`, fed to the same `look()` call. The vision call, the validation, the baseline diff, and the light check all still run live on that frame. In code, at the one place the frame path is chosen:

```python
# DEMO_CACHE: frame from 13:20 run (frames/20260913T132005_hall-1.jpg, sha256 3f9a1c07...), camera track unstable; run live with --live
```

The ledger row for the look then carries `source: "recorded"` and the sentence posted to the group ends with "(frame from 13:20)". The judge's test: flip `--live` and the same code captures and reports.

Not allowed, ever: a canned report string or a hand-written `VisionReport`; skipping the model call; a frame not captured by this dog, or captured on another day, or a baseline image passed off as current; editing the JSON after the fact; marking `vision.call` ok when the API did not return `end_turn`; posting when the step raised.
