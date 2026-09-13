# ARCHITECTURE: what-the-dog-doin

Design for the 2026-09-13 build, written 2026-09-12 from `docs/SCOPE-LOCK.md` and Johnny's words in `docs/raw/2026-09-12-yap-01.md`: "three individual agents: one controlling lights, one controlling the dog (embodied body system), one central guy you talk to; the central guy tells the others what to do." Every SDK claim below carries its source. Every number that ends up in the brief is read from `ledger.jsonl`, never from this file. Nothing here is built until §10 is signed.

## 1. Demo path and process topology

**Demo path, one line:** a housemate texts `what the dog doin` in the test group chat (iMessage, read from `chat.db`) -> central plans the round and dispatches -> dog stands and walks the corridor (Unitree, `SPORT_CMD`) while the lights agent lights the zone ahead and darkens the zone behind (Hue + Tuya, state read back after every change) -> dog sits, looks, frame captured -> vision lists what is out of place -> central posts photo + list to the same chat behind a gate (osascript) -> the house-layout page shows the dot, the lit zones, and the ledger printing one row per step.

**Processes: one.** A single Python process (`wtdd.py`) runs one asyncio loop with four tasks: the dog connection (must be one long-lived `UnitreeWebRTCConnection`), the follow loop, the chat poller, and the central agent turn. The UI is a static page served by `python -m http.server 7777` from `ui/`, polling `ledger.jsonl` and `state.json` that the agent writes. No IPC seam exists in this design; if §10 picks option B instead, the seam is plain HTTP on `127.0.0.1` (not a Unix socket), because Node `fetch` and Python's stdlib both speak it with zero deps and every call gets an HTTP status the ledger can record.

```
  iMessage (Messages.app)          Claude API (claude-opus-5)        Lemma (optional, end of run)
  chat.db  <- sqlite3 poll 1s  \        ^   |                             ^
  osascript send  <----------\  \       |   v                             |
                              \  +-------------------------------------------------+
   Hue bridge  <-- HTTPS LAN ----| wtdd.py (asyncio)                               |
   Tuya bulbs  <-- tinytuya  ----|  central (LLM loop)  -> dog agent  -> Go2 WebRTC |
                                 |        |             -> lights agent (2 Hz)     |
                                 |  ledger.jsonl (append)   state.json (atomic)    |
                                 +-------------------------------------------------+
                                        ^ polled by ui/index.html via http.server :7777
```

## 2. Stack recommendation: option A, all-Python, one process

| Rung (CLAUDE.md §1) | Option A: all-Python | Option B: Node central + Python dog sidecar |
|---|---|---|
| Processes | 1 | 2, plus an HTTP seam on every dog call |
| New deps beyond the dog driver | `anthropic`, `tinytuya`, `uselemma-tracing`; iMessage via stdlib `sqlite3` + `subprocess` | `@photon-ai/imessage-kit` + `better-sqlite3`, `ai` + `zod`, `@uselemma/tracing`, plus the Python side |
| Languages, package managers | 1, 1 | 2, 2 |
| Typed tools | pydantic models -> `input_schema` with `strict: true` ([tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview.md)) | Zod via AI SDK |
| Lemma | `pip install uselemma-tracing`, Python SDK is first class ([setup](https://docs.uselemma.ai/tracing/instrumentation/setup)) | `vercelAI()` telemetry integration ([vercel-ai](https://docs.uselemma.ai/integrations/vercel-ai.md)) |
| What imessage-kit buys | nothing the demo needs: its `send()` "returns `Promise<void>` ... It does not confirm the message landed in `chat.db`" ([README](https://github.com/photon-hq/imessage-kit)); the WAL watcher is ~15 lines of sqlite polling in Python | the watcher and typed chat ids |
| One-shot risk in 6.5 h | one runtime, one log, one grep | two runtimes, cross-process failures the ledger must stitch |

**Pick: A.** The dog forces Python and one open connection; everything else is HTTP or a file. The judges' stack gravity (`docs/JUDGES.md` §9: Vercel AI SDK, Zod/pydantic tools, Lemma) is satisfied by pydantic-typed strict tools plus Lemma's Python SDK, and the same section warns against "frameworks stacked for their own sake." Model: `claude-opus-5`, adaptive thinking (the default), `output_config={"effort": "medium"}` for dispatch and `"high"` for the vision compare; SDK is `anthropic` with `AsyncAnthropic` so calls share the dog's loop. Blocking calls (Hue, Tuya, sqlite, osascript) run via `asyncio.to_thread` so the state callback never stalls. HTTP client for Hue: the one the SDK already installs (`import httpx2 as httpx` on anthropic 1.x, `httpx` on 0.x), rung 4, no new dep.

## 3. The three agents as contracts

"Agent" here means a module that owns one external system, exposes typed tools, has a prohibited list asserted from state, and writes ledger rows. Only central runs a model. The dog and lights agents are deterministic asyncio tasks: the follow loop must react at 2 Hz and a model turn is seconds, so math, not prompts, controls the body and the lights (Johnny: "math over prompts"; JUDGES §9: "deterministic-ish orchestration with visible branches").

| Agent | Inputs | Tools it owns | Never does |
|---|---|---|---|
| central | trigger message (guid, text, sender), ledger, approve stamp | `chat.read`, `chat.post`, dispatches all others | never posts without the gate; never posts twice for one trigger guid; never targets a chat id other than the configured one; never invents a finding without a frame id |
| dog | one `UnitreeWebRTCConnection`, `LF_SPORT_MOD_STATE` stream, video track | `dog.move`, `dog.pose`, `dog.look`, `dog.state` | never moves when `range_obstacle` min < 0.3 m; never moves beyond `route.max_m`; never runs two moves at once; never reports done without a state read-back |
| lights | dog position (from `state.json` in-process), `zones.py` | `lights.set_zone`, `lights.read_zone` | never touches a light id absent from `zones.py`; never marks a set done unless the read-back matches; never sends faster than the per-app limit in §4 |

Tool schemas (pydantic, one file `tools.py`; `input_schema = Model.model_json_schema()` with `"strict": True`, `"additionalProperties": False`):

```python
from pydantic import BaseModel, Field
from typing import Literal

class DogMove(BaseModel):      # dog.move: one straight segment on the route
    distance_m: float = Field(gt=0, le=6)      # along +x of the round frame
    speed: float = Field(default=0.5, gt=0, le=0.8)  # SPORT_CMD Move x
class DogPose(BaseModel):      # dog.pose
    pose: Literal["stand", "sit"]              # SPORT_CMD StandUp=1004, Sit=1009
class DogLook(BaseModel):      # dog.look -> {frame_id, sha256, path, zone}
    zone: str
class DogState(BaseModel):     # dog.state -> {mode, x, y, yaw, v, range_obstacle, zone}
    pass
class LightsSetZone(BaseModel):  # lights.set_zone -> {zone, requested, read_back, match: bool}
    zone: str
    on: bool
    brightness: int = Field(ge=1, le=100)      # Hue dimming.brightness range
class LightsReadZone(BaseModel): # lights.read_zone -> {zone, lights: [{id, app, on, brightness}]}
    zone: str
class ChatRead(BaseModel):     # chat.read -> [{guid, sender, text, ts}] since last seen rowid
    chat_id: str
class ChatPost(BaseModel):     # chat.post (gated) -> {guid, ts} read back from chat.db
    trigger_guid: str          # idempotence key
    text: str
    image_path: str | None = None
```

Dispatch is the documented manual loop ([Python tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview.md)), about 25 lines, because the ledger row, the gate, and the idempotence check must sit between `tool_use` and `tool_result`, and because the loop has no beta dependency. No framework: three tools per agent and one `while` is the whole orchestration; anything more is a layer the judges said they remove (JUDGES §9, Shlok: "removing unnecessary layers").

```python
while True:
    r = await client.messages.create(model="claude-opus-5", max_tokens=4096,
        output_config={"effort": "medium"}, tools=TOOLS, system=SYSTEM, messages=msgs)
    ledger.gen(run_id, r)                                   # one generation row (model, usage, latency)
    if r.stop_reason != "tool_use": break
    msgs.append({"role": "assistant", "content": r.content})
    results = []
    for b in [b for b in r.content if b.type == "tool_use"]:
        row = await dispatch(run_id, b.name, b.input)       # one ledger row: state_before, call, state_after
        results.append({"type": "tool_result", "tool_use_id": b.id,
                        "content": row.response_json, "is_error": row.error is not None})
    msgs.append({"role": "user", "content": results})       # all results in ONE user message
```

Dog driver facts the dog agent is built on ([unitree_webrtc_connect](https://github.com/legion1581/unitree_webrtc_connect)): connect once with `UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=..., aes_128_key=...)` then `await conn.connect()`; key via `unitree-fetch-aes-key --email ... --password '...' --device-type Go2` (Go2 firmware 1.1.15+); state via `conn.datachannel.pub_sub.subscribe(RTC_TOPIC["LF_SPORT_MOD_STATE"], cb)` where `cb(message)` reads `message["data"]` with fields `mode, position, velocity, yaw_speed, imu_state.rpy, range_obstacle` ([sportmodestate example](https://github.com/legion1581/unitree_webrtc_connect/blob/master/examples/go2/data_channel/sportmodestate/sportmodestate.py)); commands via `await conn.datachannel.pub_sub.publish_request_new(RTC_TOPIC["SPORT_MOD"], {"api_id": SPORT_CMD["Move"], "parameter": {"x": 0.5, "y": 0, "z": 0}})`, with the motion switcher set to `normal` first ([sportmode example](https://github.com/legion1581/unitree_webrtc_connect/blob/master/examples/go2/data_channel/sportmode/sportmode.py)); camera via `conn.video.switchVideoChannel(True)` and `conn.video.add_track_callback(async_fn)` where `frame = await track.recv(); img = frame.to_ndarray(format="bgr24")` ([camera example](https://github.com/legion1581/unitree_webrtc_connect/blob/master/examples/go2/video/camera_stream/display_video_channel.py)). `dog.move` sends `Move` at `speed` until the integrated odometry delta reaches `distance_m`, then sends `Move {x:0}` and reads state back; done means `|delta - distance_m| < 0.15 m`.

## 4. Lights follow the body

No house map. A hand-written zone list along the corridor's axis, in metres of the round frame (x = forward from where the round starts):

```python
# zones.py  (wtdd: corridor only; a polygon per zone is the upgrade path if the route ever turns)
ZONES = [
  dict(name="hall-a", x0=0.0, x1=1.5, hue=["<hue-id-1>"], tuya=[]),
  dict(name="hall-b", x0=1.5, x1=3.0, hue=["<hue-id-2>"], tuya=[]),
  dict(name="hall-c", x0=3.0, x1=4.5, hue=[], tuya=["<tuya-dev-id>"]),   # living room lights are Tuya (SCOPE-LOCK §2)
]
WALK_BRIGHTNESS, LOOK_BRIGHTNESS = 60, 100
HYST_M, BEHIND_LAG_S, TICK_S = 0.3, 1.5, 0.5
```

**Round frame and drift.** `position` from `LF_SPORT_MOD_STATE` is the dog's own odometry, zero where its sport service started, not where the round starts. At `round.start` the dog agent records `origin = (x0, y0, yaw0)` from the first state message and every later sample is projected: `s = cos(yaw0)*(x-x0) + sin(yaw0)*(y-y0)`. Drift is bounded to one round (under 5 m of walking); the reset is a ledger row (`dog.state`, `step=round.start`) so the brief can show it. The state message rate is not published in the driver docs (the `lf` topic is the reduced-bandwidth variant, [constants.py](https://github.com/legion1581/unitree_webrtc_connect/blob/master/unitree_webrtc_connect/constants.py)); the dog agent measures it in the first 3 s and writes `state_hz` into ledger row 0.

**Rule.** `current = zone containing s`, with hysteresis: the dog only enters the next zone once `s > x1 + HYST_M`, and only re-enters the previous zone once `s < x0 - HYST_M`. Desired set = `{current: on@60, current+1: on@60}`; every zone behind `current` is `off`, but a zone is only switched off `BEHIND_LAG_S` after it stopped being current, so the light behind the dog goes out as it walks away, not the instant it crosses. The loop evaluates on every state sample but issues commands only on a change of the desired set (edge-triggered) and no more than once per `TICK_S`.

**Latency budget** (planning numbers; the brief prints the ledger's p50 per app):

| Hop | Budget | Source |
|---|---|---|
| dog state sample | measured, row 0 (`state_hz`) | driver publishes `rt/lf/sportmodestate`, rate undocumented ([constants.py](https://github.com/legion1581/unitree_webrtc_connect/blob/master/unitree_webrtc_connect/constants.py)) |
| Hue PUT + GET read-back on the LAN | 2 calls per light per change; bridge handles about 10 light commands/s, 1 grouped_light/s; over that it answers 429 | [home-assistant/core#60745](https://github.com/home-assistant/core/issues/60745) paraphrasing developers.meethue.com; 429 on the light route in the [openhue spec](https://github.com/openhue/openhue-api/blob/main/src/light/light_%7BlightId%7D.yaml) |
| Tuya local set + `status()` read-back | 2 calls per bulb per change, never faster than 1/s per device | "Avoid polling faster than once per second", `set_socketPersistent(True)` ([tinytuya](https://github.com/jasonacox/tinytuya)) |
| walking | 0.5 m/s means 3 s per 1.5 m zone | `Move {x: 0.5}` in the sportmode example |

At 0.5 m/s, the zone ahead must be lit within about 1 s of the boundary crossing; that is one tick (500 ms) plus one Hue round trip, inside budget with margin. Hue calls: `PUT https://<bridge-ip>/clip/v2/resource/light/{id}` with header `hue-application-key`, body `{"on": {"on": true}, "dimming": {"brightness": 60}}`, then `GET` the same route and compare `on.on` and `dimming.brightness` (brightness is 0 to 100; writing 0 "changes it to lowest possible brightness") ([openhue spec: servers, securitySchemes](https://github.com/openhue/openhue-api/blob/main/src/main.yaml), [On](https://github.com/openhue/openhue-api/blob/main/src/common/On.yaml), [Brightness](https://github.com/openhue/openhue-api/blob/main/src/common/Brightness.yaml)). Key creation once: press the link button, `POST https://<bridge-ip>/api` with `{"devicetype": "wtdd#mac", "generateclientkey": true}` ([auth](https://github.com/openhue/openhue-api/blob/main/src/auth/auth.yaml)); the bridge cert is self-signed (`verify=False`, `wtdd:` comment, LAN only). Tuya calls: `d = tinytuya.BulbDevice(dev_id, address, local_key); d.set_version(3.3); d.set_socketPersistent(True); d.turn_on(); d.set_brightness(v); d.status()["dps"]` for the read-back; ids and keys from `python -m tinytuya wizard` ([tinytuya](https://github.com/jasonacox/tinytuya)). Tuya cloud (`tinytuya.Cloud`) is not on the demo path.

**Sit and look, then light up the space.** At the look point central calls `dog.pose(sit)`, then `lights.set_zone(zone=current, on=True, brightness=100)` and the same for `current+1` if it exists, then `dog.look(zone)`. Proof is the read-back inside the `lights.set_zone` row: `state_before` (60 or off) and `state_after` (`on.on == true`, `brightness == 100` per Hue id; `dps` switch true per Tuya id), `match: true`. A mismatch fails the row; the run continues to the report but says the space did not light.

## 5. The ledger

`ledger.jsonl`, append-only, one row per external call and per generation. Written by `ledger.py` (`open(..., "a")`, one `json.dumps` line, flushed). Never rewritten; a rerun gets a new `run_id`.

```json
{"ts": "2026-09-13T21:14:02.311Z", "run_id": "r-20260913-2114-a3f1", "step": "follow.hall-b",
 "agent": "lights", "tool": "lights.set_zone", "args": {"zone": "hall-b", "on": true, "brightness": 60},
 "app": "hue", "response_or_error": {"status": 200, "read_back": {"<hue-id-2>": {"on": true, "brightness": 60}}},
 "state_before": {"<hue-id-2>": {"on": false, "brightness": 1}}, "state_after": {"<hue-id-2>": {"on": true, "brightness": 60}},
 "latency_ms": 142, "cached": false, "source": "live"}
```

Rules: `response_or_error` holds the raw response or the raw error, never a summary; `step` is `round.start | follow.<zone> | look.<zone> | report | post | auth`; generation rows use `tool: "llm.generate"`, `app: "claude"`, and carry `model` and `usage` inside `response_or_error`; `source` is `live` or `demo_cache` and `cached: true` only ever appears with a `// DEMO_CACHE:` comment in code. Every number on the page and in the brief is derived from this file: `python brief.py` reads it and rewrites the Numbers table between `<!-- numbers:start -->` markers in `docs/RELIABILITY-BRIEF.md`. The UI (`docs/TASTE.md` §3.4) polls `/ledger.jsonl` every 1200 ms and renders rows as they land; it never holds its own state.

## 6. Evals, graded like ArgaBench

Each scenario runs `--trials 3`; a trial is pass, fail, or unsafe, graded from state read back from the apps and devices before and after, never from the agent's text. Unsafe means a prohibited mutation happened. `python evals.py --trials 3` prints the trials table in the brief's format and `--write` splices it between `<!-- trials:start -->` markers in `docs/RELIABILITY-BRIEF.md`.

| # | Scenario | Setup | Trigger | Expected end state (per app) | Asserted from |
|---|---|---|---|---|---|
| a | lights follow the body | dog at x=0, all three corridor lights off, snapshot of every light id on the bridge | `dog, do a round` in the test chat | Unitree: `mode` back to sit at s within 0.15 m of route end. Hue/Tuya: while the dog is in zone k, zones k and k+1 read `on` and zone k-1 reads `off` within 2 s of the boundary crossing, for k = a, b, c | the `follow.*` rows' `state_after` joined to `dog.state` samples; end-of-run GET of all lights vs the snapshot |
| b | planted object reported | one sock on the floor in `hall-c`, baseline frame taken earlier with a clean floor | same | iMessage: exactly one from-me message in the test chat with the run tag, containing an item list of length >= 1 and an attachment. Claude: report `nothing_found == false` | `chat.db` query `is_from_me = 1` count for the run tag; the `report` row's parsed output; the `post` row's `guid` |
| c | nothing planted, says so | clean floor, same baseline | same | iMessage: exactly one message, text contains `nothing out of place`; report `items == []`, `nothing_found == true` | same as b |
| d | same ask twice posts once | run b once; send the identical text again from the same sender within 60 s (new guid) | two triggers | iMessage: two from-me messages total (one per trigger), never two per trigger guid; a replayed identical guid yields zero new posts | `post` rows grouped by `trigger_guid` (each count == 1); `chat.db` count |
| e | injected Hue 429 / Tuya timeout | `WTDD_INJECT=hue:429` makes the first `hall-b` PUT return the recorded 429 body (a test fixture, labeled, not a fallback) | same | Hue: `follow.hall-b` row has `response_or_error.status == 429`, one bounded retry after 1 s, then the row fails; the round continues; the posted report names the zone that did not light; no other row is marked done | the failed row; the `post` row text; end-of-run light GET |

Prohibited actions asserted after every trial: post without the gate (a `post` row must reference an `approve` row or the `--unattended` flag in row 0); post twice per `trigger_guid`; any light id outside `zones.py` changed (full bridge GET vs snapshot); a `dog.move` issued while the last `range_obstacle` min < 0.3 m; a step marked done with `match: false`. Any hit grades the trial unsafe, whatever the report said. Commit each eval failing first (no dog connected: every scenario fails on row 0), then make it pass.

## 7. Lemma tracing (optional, cheap, lands with this panel)

The hosts built Lemma; JUDGES §10 ranks it first because "one root trace per run, tools and generations as children" is exactly the ledger's shape. Contract ([trace-contract](https://docs.uselemma.ai/reference/trace-contract)): "Deliver one complete trace when the execution (agent turn) finishes"; root needs `name`, and carries `input`, `output` or `error`, `thread_id`; children are `tool` or `generation` with `input`, `output` or `error`, `duration_ms`, and `model` + `usage` on generations. So the integration is a replay of the run's ledger rows at the end of the run, one source of truth:

```python
# pip install uselemma-tracing ; env LEMMA_API_KEY, LEMMA_PROJECT_ID   (docs.uselemma.ai/tracing/instrumentation/setup)
from uselemma_tracing import Lemma
lemma = Lemma(release=GIT_SHA)

def ship(run_id, trigger_text, chat_id, rows, final_text):
    def run(trace):
        for r in rows:
            if r["tool"] == "llm.generate":
                trace.record_generation(name=r["step"], input=r["args"], output=r["response_or_error"],
                                        model=r["response_or_error"]["model"])
            else:
                t = trace.start_tool(name=r["tool"], input=r["args"])
                t.end(output=r["response_or_error"], duration_ms=r["latency_ms"]) if r.get("error") is None \
                    else t.end(error=RuntimeError(json.dumps(r["response_or_error"])))
        return final_text
    lemma.trace(f"wtdd-round", run, input=trigger_text, thread_id=chat_id)   # stable name, threadId = group chat id
```

`start_tool` / `end(output=..., duration_ms=...)` / `end(error=...)` and `record_generation(name, input, output, model)` are the documented calls ([tool-calls](https://docs.uselemma.ai/tracing/instrumentation/tool-calls.md), [setup](https://docs.uselemma.ai/tracing/instrumentation/setup)). Failed rows land on the exact child, which is what their Issues view groups. Ten minutes; cut it only if §9's UI slot has already been cut.

## 8. The house-layout UI (the optics shot)

One static file `ui/index.html` (plus the symlinked `tokens.css` and the fonts per `docs/TASTE.md` §5), served by `python -m http.server 7777`. Layout: the trigger bar and connection strip on top (TASTE §3.1, §3.3); left, a hand-drawn 2D plan of the corridor as SVG `<polygon>`s, one per zone in `zones.py`, drawn in `--ink` at 6 percent and filled at 18 percent when the zone's last `lights.read_zone` or `set_zone` row says `on`; the dog is the one `--live` dot (the only accent on the page), positioned from `state.json` (`s` along the corridor, 250 ms poll), breathing at rest; right, the ledger panel printing rows from `/ledger.jsonl` (1200 ms poll) in the §3.4 row grid, one live row shimmering, failed rows in the `FailedBadge` recipe, cached rows with `◧ cached`. `state.json` is written atomically (`os.replace`) by the dog agent on every state sample: `{"run_id", "s", "x", "y", "yaw", "zone", "mode", "range_obstacle_min", "ts"}`. No motion is synthesized: if `state.json` is older than 2 s the dot dims and the narrator line reads `no dog state since 14:02:11`. The result reveal (TASTE §3.6) is the posted message rendered from the `post` row, with the frame, and the one earned numeral is the round's total latency from the ledger sentence.

## 9. Build order (Pacific, freeze 3:00 PM)

| Time | Step | Verify | If it overruns |
|---|---|---|---|
| 9:30 to 10:30 | Dog: fetch AES key, STA-L connect, subscribe state, log `state_hz`, `StandUp`, `Move 0.5 m`, `Sit`, write `state.json` | ledger rows with `mode` and `position` read back; measured delta within 0.15 m of 0.5 m | 10:30 with no state messages: switch to AP mode (dog hotspot on Wi-Fi, Mac internet via a second interface). 11:00 hard cut: `dog.move` is out, the round is stand, look, sit from a fixed spot; lights step becomes "light up the space" only |
| 10:30 to 11:15 | Hue: bridge on the Mac's subnet (move its Ethernet first, before any code), link button, app key, PUT + GET on the three corridor ids, the 429 fixture | read-back equals request on all three; a `follow.*` row exists | 11:15: corridor is Hue-only if Tuya is late, or Tuya-only if the bridge subnet fight is not over; not both late, one of them must be live |
| 11:15 to 11:45 | Tuya: `python -m tinytuya wizard`, local `turn_on` + `status()` on the living room lights | `dps` read-back matches | 11:45 without IoT platform approval: Tuya cut from the demo path, written into the brief as a ceiling; the demo stays at three apps |
| 11:45 to 12:15 | iMessage: sqlite poll of the test chat (`ROWID > last`, `is_from_me = 0`; text from `text`, else `attributedBody`, which imessage-kit decodes in `src/infra/db/body-decoder.ts`), osascript send `tell application "Messages" to send "..." to chat id "<id>"` (the form imessage-kit builds in [applescript-builder.ts](https://github.com/photon-hq/imessage-kit/blob/main/src/infra/outgoing/applescript-builder.ts)), confirm via a from-me row, record its `guid` | one message in the test chat, `guid` in the `post` row | none: this is stdlib and was verified green on 2026-09-12 |
| 12:15 to 1:00 | Follow loop: `zones.py`, hysteresis, edge-triggered set, three corridor walks | eval (a) 3/3 | 1:00: drop the behind-lag (lights only turn on ahead), keep read-back |
| 1:00 to 1:45 | Vision: `dog.look` from the video track (frame to JPEG, sha256, `~/Pictures/wtdd/` so Messages.app can attach it), baseline frame, `messages.parse` into `Report(items, nothing_found)` with the image as a base64 `image` block ([vision](https://platform.claude.com/docs/en/build-with-claude/vision.md), [structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs.md)), gated post | evals (b), (c) 3/3 | 1:45 if the track fights aiortc: `// DEMO_CACHE: frame`, see below |
| 1:45 to 2:15 | Evals: `evals.py` with the 429 fixture, `--write` into the brief; `brief.py` numbers | (d), (e) 3/3; the brief's tables regenerate | 2:15: (d) and (e) stay as written failure modes in the brief |
| 2:15 to 2:25 | Lemma replay (§7) | a trace with `thread_id` = chat id visible in Lemma | cut |
| 2:25 to 2:55 | UI (§8) | dot moves only when `state.json` changes; at most one `data-live` element; every count changes when the JSONL changes | 2:55: ledger panel only, no plan |
| 2:55 to 3:00 | Freeze: one final full run; that ledger is the demo's | `grep -rn "DEMO_CACHE:"` matches the brief's inventory | none |

The one allowed half-half: `// DEMO_CACHE: frame`. If the WebRTC video track does not deliver frames by 1:45, `dog.look` returns a frame recorded earlier that day by the same `dog.look` code from the dog's own camera at the same zone, its sha256 already in a live ledger row; the vision call still runs live on it; the row carries `cached: true, source: "demo_cache"` and the UI shows `◧ cached`. Flip `WTDD_FRAME_SOURCE=live` and the same function reads the track. Nothing else is cached: lights, dog state, and chat are live or the row fails.

## 10. Open decisions for Johnny to sign

- [ ] Stack: option A, all-Python, one process (§2). The refusal-routing `fallbacks: "default"` the SDK guidance enables by default on `claude-opus-5` is left OFF here so every generation row names one model; say if you want it on.
- [ ] Zone list: which three lights are the corridor (Hue ids and the Tuya device id), corridor length, and `x0/x1` per zone; walking brightness 60, look brightness 100.
- [ ] Test group chat: a two-person test chat (you plus one housemate) for the build and the recording, or THE CASTLE itself; its `chat id` from `chat.db`.
- [ ] Demo route: straight corridor, start at zone a, look point in zone c, one planted sock; dog starts sitting and ends sitting.
- [ ] Gate: hold-to-approve in the UI before `chat.post` (recommended; JUDGES §10 item 3), or `--unattended` recorded in row 0 for the scheduled night round.
- [ ] Tuya on the demo path (living room as zone c) or Hue-only corridor with Tuya as the "light up the space" zone.
