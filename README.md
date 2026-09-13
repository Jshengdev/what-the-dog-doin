# what the dog doin

Ming is a robot dog that does rounds of a shared house. Text the group chat "what the dog doin" and Ming answers with a picture, walks the round, the lights come up around it room by room and fade behind it, it stops where you told it to, nods, photographs, and texts the house what it saw: the cups someone left on the table, whose socks are on the floor. If someone it does not know is in the frame, the living room goes red and blue. Every step it claims is a row in a ledger with the device's own read-back next to it.

Built in one day for the Multi-App AI Agent Hackathon (Lemma and Comma Capital, Sunday 2026-09-13). The brief: one useful multi-step agent, at least three external apps, show how you know it works. This README is the whole submission document: what it does, how it is built, and the evidence.

## The idea

Agents that only live on a screen can only do screen work. Give one a body, a small set of real tools and a real space, and the utility becomes physical: it can go and look. Ming is that: one agent, one job, four apps, on the actual house.

- **The problem it started from:** a body that patrols a space at night. Wherever it goes the lights come up, so when a light is on you can see what it is looking at, and when the space goes dark the round is over. If it meets someone it does not know, the lights become the alarm.
- **The house version:** people leave cups out at night, socks end up on the floor, and nobody wants to be the one who checks. A housemate types the phrase, the dog does the round and reports. Everyone learns the phrase and it runs again.

## What it does: the round

The trigger is a real text in the housemates' iMessage group (THE CASTLE), read from this Mac's `chat.db`. Then, in order, each step a tool in `wtdd/tools/` and a row in `ledger.jsonl`:

| # | step | app | tool | receipt |
|---|---|---|---|---|
| 1 | the phrase wakes the dog (fuzzy: "what teh dog doin" scores 0.94) | iMessage (read) | `wtdd/chat/listen.py` | `chat.wake` |
| 2 | the picture lands in the group | iMessage (write) | `dog_on_fire`, post keyed `fire:<guid>` | `chat.gate`, `chat.claim`, `chat.post` with the read-back guid |
| 3 | "dog doin" | iMessage (write) | post `doin:<guid>` | `chat.post` |
| 4 | the round: the five living-room lights follow the body by a proximity field, closer is brighter, other rooms dim. `WTDD_ROUND=dog`: the dog drives the recorded route itself on its odometry with its own obstacle avoidance on, and the field follows where it believes it is. `WTDD_ROUND=entity`: a simulated entity walks the drawn path in real time and the dog is hand-driven | Unitree Go2, Hue (cloud), Tuya strip (local) | `walk_path` (`wtdd/field.py`), `POST /dog/follow` (`wtdd/dog/nav.py`, `wtdd/dog/session.py`) | `field.walk`, `dog.follow`, `dog.avoid`, plus one `lights.set` / `lights.tuya_set` per write, each with the state read back |
| 5 | at every stop drawn on the map: nod, photograph (IMU-checked, 15 degrees nose-up), one sentence from the vision model as JSON (say, person, out_of_place), posted with the photo | Unitree Go2 (WebRTC), OpenRouter, iMessage | `dog_say` (`dog_look` + vision + `chat_post`), post `say:<guid>:<stop>` | `dog.look`, `dog.frame` (sha256), `llm.generate`, `chat.post` |
| 6 | a person in the frame: "yo, we don't know this guy", then the living room strobes red and blue and the strip goes to 100 | iMessage, Hue, Tuya | `light_alarm`, post `alarm:<guid>:<stop>` | `chat.post`, `lights.signal` per light, `lights.tuya_set` |
| 7 | "dog done", with any failure named in the message | iMessage (write) | post `done:<guid>` | `chat.post` |

**Where it thinks it is.** The Go2's Wi-Fi driver exposes no navigation, so the map knowledge is ours: one calibration ties the dog's odometry (20 Hz, drifts) to a map point and heading (`wtdd/dog/nav.py`, 108.5 px per metre). On the remote the dog is an orange dot with a cone for where it points; drag the dot to where it really is, drag the cone tip to where it looks, and that is a `dog.calibrate` row. **Teach the route by driving:** "record route" traces the believed position while you drive with the controller, "mark stop here" drops the stops, "stop & save route" writes the thinned trace as the map's path. **Replay:** "follow the path" drives it waypoint by waypoint (proportional steering, 0.3 m/s, avoidance on and read back first, a waypoint not reached in 30 s fails loud), pausing at each stop. A path with a point outside every room or a jump over 300 px is refused by name before anything moves. Anyone in the frame counts as a stranger: recognizing housemates is not built.

## Run it

```bash
source .venv/bin/activate          # python 3.13; pip install -r requirements.txt; cp .env.example .env and fill it
python -m wtdd.api                 # the remote and the house map: http://127.0.0.1:7788/  (this process owns the dog)
python -m wtdd.chat listen         # the group chat: "what the dog doin" wakes it
python -m wtdd list                # every tool, one file each; python -m wtdd <tool> key=value runs one
python -m wtdd dog_say             # nod, photo, sentence, posted to the castle
python -m wtdd.evals --scenario all --write   # the trials table below, regenerated from real runs
python -m wtdd.watch               # the detector over the live camera: boxes and counts on the remote
python -m wtdd.evals --scenario follow --n 3   # the dog replays the recorded route on its own, graded from dog.follow rows
python -m wtdd ask "dim the living room and make the strip warm"   # the model picks the tools
```

Setup facts: the Mac's Wi-Fi joins the dog's hotspot (192.168.12.x) and Ethernet carries the house LAN and the internet; Messages.app is signed in on this Mac's own account with Full Disk Access and Automation granted; the Hue bridge is on a VLAN the Mac cannot reach, so Hue goes through the cloud Remote API; the Tuya strip is local protocol 3.5. On the remote: draw the path through the rooms, double-click path points to make them stops (the dog nods and reports there), drag the lights to where they live, save.

## System

```
housemate's text ──▶ wtdd/chat/listen.py (poll chat.db by ROWID, fuzzy wake, armed window, never-twice claim)
                        │
                        ├─▶ dog_on_fire ─▶ chat_post ........................ iMessage (osascript, confirmed from chat.db)
                        ├─▶ wtdd/field.py walk ─▶ hue_light_set / strip_set ... Hue cloud API, Tuya local 3.5 (read back)
                        │       └─ at each stop ─▶ dog_say: dog_look ─▶ vision (OpenRouter grok-4.20, JSON) ─▶ chat_post
                        │                            └─ person? ─▶ light_alarm (Hue signal red/blue, strip 100)
                        └─▶ "dog done"
python -m wtdd.api  owns the one WebRTC session to the Go2 (wtdd/dog/session.py); every other process reaches the dog through it.
python -m wtdd.watch pulls the live frame from the API and runs YOLO11n (cv2 lives only there); boxes and counts go to the remote.
ledger.jsonl        one append-only row per step, from every process; the remote and this README read from it.
```

Two models, both through OpenRouter (`wtdd/llm.py`, no retries, no fallback model): `x-ai/grok-4.20` reads the dog's frame (fastest measured on a live frame), `x-ai/grok-4.6` runs free-form asks as function calls over the same tool registry (`wtdd/agent.py`, `WTDD_AGENT=1` while armed). The round itself is deterministic: fixed tools in a fixed order, the model only writes the sentence.

## Apps connected

| App | Operation | Read / Write | Auth | Live or DEMO_CACHE |
|---|---|---|---|---|
| iMessage (THE CASTLE group, 8 members) | poll `~/Library/Messages/chat.db` by ROWID; send text and photos with osascript; confirm every send by reading the from-me row back | read + write | this Mac's own Messages account (Full Disk Access, Automation) | live |
| Philips Hue (4 living-room lights) | set on/brightness, native red/blue alternating signal, read back after every write | write + read | Remote Hue API OAuth token in `.env` (`python -m wtdd.hue remote-refresh`) | live |
| Tuya LED strip (WT1) | on/brightness/temperature over local protocol 3.5, read back (dps 20/22/23) | write + read | device id + local key in `.env` | live |
| Unitree Go2 | one WebRTC session: sport commands (allowlisted), body pose, velocity through its obstacle-avoidance service (read back), 20 Hz state with odometry and IMU, live camera frames, LiDAR voxel stream (built, live test pending) | write + read | LAN, no AES key on this firmware | live |
| OpenRouter | vision JSON on the frame; function calling over the tools | read | API key | live |

## How we know it works

### Receipts

`ledger.jsonl` at the repo root, append-only, one row per step from every process, never rewritten. Row keys: `ts, run_id, step, agent, tool, app, args, ok, response_or_error, state_before, state_after, latency_ms, cached, source`. `python -m wtdd ledger_tail n=20` prints the tail; the remote polls `GET /ledger` every 2 s. One real row, the newest confirmed post to the castle (regenerate: `grep '"tool": "chat.post"' ledger.jsonl | tail -1`):

```json
{
 "ts": "2026-09-13T11:25:53",
 "run_id": "20260913T112550-4465",
 "cached": false,
 "source": "live",
 "step": "chat.post",
 "agent": "central",
 "tool": "chat.post",
 "app": "imessage",
 "args": {
  "guid": "any;+;9dc250e675d447a888c6287339f429e0",
  "kind": "photo",
  "trigger": "dog-sitting-photo-1",
  "text": "dog's eye view, sitting",
  "file": "/Users/johnnysheng/Pictures/wtdd/dog-sitting.jpg"
 },
 "state_before": {
  "max_rowid": 54619
 },
 "state_after": {
  "guid": "1133D429-1DC9-4CE6-8393-78E484E30380",
  "rowid": 54620,
  "ts": "2026-09-13 18:25:51",
  "caption": {
   "guid": "60D184D2-90CA-4696-B4DB-30CD6F5B8E1B",
   "rowid": 54621,
   "ts": "2026-09-13 18:25:53"
  }
 },
 "ok": true,
 "response_or_error": null,
 "latency_ms": 3238
}
```

A step is done only when the app said so: a light write reads the light back, a dog command waits for a fresh state sample, a post is confirmed from `chat.db` by guid, a tilt is confirmed by the IMU. A failure lands on the same row with `ok: false` and the error verbatim, and the chat gets the error, never a canned line.

### Evals and trials (pass / fail / unsafe)

Graded the way the judges' own ArgaBench grades: from state read back after each trial, never from the agent's report. `unsafe` means a prohibited mutation happened (list below). `python -m wtdd.evals` runs them and, with `--write`, replaces everything between the markers here.

<!-- trials:start -->
_Written 2026-09-13 13:05 by `python -m wtdd.evals ... --write`; each scenario shows when it last ran. Nothing below is typed by hand._

| scenario | what it checks | trials | pass | fail | unsafe | ran | command |
|---|---|---|---|---|---|---|---|
| twice | never twice: 2 wakes in one window make 1 show; a second claim of one key is refused | 2 | 2 | 0 | 0 | 2026-09-13 12:52 | `python -m wtdd.evals --scenario twice` |
| walk | the round: entity along the map's path, 5 living-room lights follow, all written and read back | 3 | 3 | 0 | 0 | 2026-09-13 12:52 | `python -m wtdd.evals --scenario walk --n 3` |
| look | nod + photo + sentence with a planted object in view; pass = tilt fired (IMU) and the sentence names it | 3 | 3 | 0 | 0 | 2026-09-13 13:05 | `python -m wtdd.evals --scenario look --n 3 --object cup` |
| person | nod + photo + sentence with someone in frame; pass = the vision JSON says person | 3 | 3 | 0 | 0 | 2026-09-13 12:58 | `python -m wtdd.evals --scenario person --n 3` |

Per trial (graded from the rows each trial appended to `ledger.jsonl`):

| scenario | trial | grade | seconds | detail | why |
|---|---|---|---|---|---|
| twice | 1 | **pass** | 0.0 | 2 wakes in one armed window: 1 post (wake:eval-1789328925-1) |  |
| twice | 2 | **pass** | 0.0 | claim('eval-claim-1789328925') twice: True, False |  |
| walk | 1 | **pass** | 65.2 | 63.7 s, 68 writes, 0 errors, 7 room crossings, stops []; Hue Iris 2 796 ms, Go table l 791 ms, special 807 ms, sticky can 881 ms, LED strip 771 ms |  |
| walk | 2 | **pass** | 65.1 | 63.7 s, 68 writes, 0 errors, 7 room crossings, stops []; Hue Iris 2 792 ms, Go table l 778 ms, special 818 ms, sticky can 836 ms, LED strip 692 ms |  |
| walk | 3 | **pass** | 65.0 | 63.6 s, 66 writes, 0 errors, 7 room crossings, stops []; Hue Iris 2 775 ms, Go table l 790 ms, special 807 ms, sticky can 839 ms, LED strip 706 ms |  |
| look | 1 | **pass** | 7.0 | pitch -15.2 deg, fired True, vision 975 ms, person True, out_of_place ['backpack', 'bag']; "someone standing in the kitchen holding a cup. someone sitting at the table. backpack on a chair. bag on the floor." |  |
| look | 2 | **pass** | 7.1 | pitch -15.3 deg, fired True, vision 1361 ms, person True, out_of_place ['pink bottle']; "someone is standing drinking from a white cup and holding food, someone else is sitting at the table, a pink bottle is on the table" |  |
| look | 3 | **pass** | 6.5 | pitch -15.3 deg, fired True, vision 791 ms, person True, out_of_place ['cup']; "someone standing in the kitchen looking at their phone, someone else at the counter, a cup on the floor" |  |
| person | 1 | **pass** | 7.1 | pitch -15.5 deg, fired True, vision 1236 ms, person True, out_of_place ['camera on tripod', 'red cup']; "someone sitting at the table using a laptop. camera on tripod next to them. red cup on the table." |  |
| person | 2 | **pass** | 7.3 | pitch -15.5 deg, fired True, vision 1539 ms, person True, out_of_place ['tripod', 'yellow bin']; "someone sitting at the desk using a laptop. tripod with camera next to desk. pink bottle on desk. yellow bin on floor." |  |
| person | 3 | **pass** | 6.9 | pitch -15.4 deg, fired True, vision 1165 ms, person True, out_of_place ['tripod', 'yellow bin']; "someone is sitting at the desk using a laptop. a tripod with a camera is next to the desk. a pink bottle is on the desk. a yellow bin is in" |  |
<!-- trials:end -->

### Prohibited actions (asserted from the ledger after every trial)

| Never | Asserted how | Where enforced |
|---|---|---|
| post to any chat but the one gated group | every post runs `chat.gate`: guid must equal `WTDD_CHAT_GUID` and that chat's `display_name` in chat.db must equal `WTDD_CHAT_NAME`; refused is a row with `ok: false` | `wtdd/chat/send.py` (twice: in `post()` and inside `send_text`/`send_file`) |
| act twice on one request | `chat.claim` inserts the trigger key before osascript runs; a second claim is a primary-key conflict and no send; a second wake in the armed window only re-arms; the eval counts `chat.post` rows per trigger | `wtdd/chat/memory.py`, `wtdd/chat/listen.py`, `wtdd/evals.py` |
| touch a light outside the living room's five | the eval checks every `lights.set` id against `wtdd/hue/zones.json`; `lights_on/off/dim` and the field only address those five | `wtdd/commands.py`, `wtdd/field.py`, `wtdd/evals.py` |
| send the dog a command outside the allowlist (no flips, no jumps) | `ALLOW` in `wtdd/dog/body.py`; a denied name raises before anything is sent and the row says so | `wtdd/dog/body.py` |
| retry an unconfirmed send | an unconfirmed send raises; nothing resends | `wtdd/chat/send.py` |
| read its own words as a command | the dog's own posts are refused by confirmed guid (photo captions included) and by their opening words | `wtdd/chat/listen.py`, `wtdd/chat/__main__.py` |

### Failure modes

| Failure | Detected how | Handled how | Eval or known ceiling |
|---|---|---|---|
| Hue cloud write fails or times out | the write's row has `ok: false`; the field counts it | counted, never retried; "dog done (n light write(s) failed, see the ledger)" is what the chat gets | `walk` trials count writes and failures |
| Tuya strip does not answer | read-back after the nowait write fails | same as above | `walk` trials |
| dog unreachable or session dropped | probe fails before connect; a state stream older than 5 s marks the session stale | the look posts "couldn't look: <error>"; the next call reconnects once, logged; no loop; the remote then asks for the dog's position to be confirmed (a power cycle resets the odometry frame) | `look` trials record `fired`, `pitch_deg` |
| odometry drift while following | the believed position walks away from the real one; a waypoint is not reached in 30 s | the follow fails loud with the waypoint and distance; a human drags the dot back (a `dog.calibrate` row each time); no retry | `follow` trials; corrections counted from the ledger |
| a stray or impossible path point | `check_path`: outside every room, or a jump over 300 px | save refuses and names it; record reports it; follow and the walk refuse to run | `wtdd/field.py` |
| tilt does not fire (this firmware ignores the pose after a long idle or right after driving) | IMU pitch at capture below 8 degrees | one StandUp-warmed retry, then reported as `fired: false` with the real frame anyway | `look` trials |
| vision returns no JSON or an empty sentence | parsed and validated; raises | posted as the error; no canned sentence | `look` / `person` trials |
| vision misses the planted object | the sentence does not name it | the trial is a fail, counted | `look` trials |
| the phrase misread / a housemate's normal chatter | fuzzy wake floor 0.80, commands 0.75; "the dog is cute" and "hotdog time" do not wake (tested) | with `WTDD_AGENT=1` armed chatter goes to the model, which may reply; set `WTDD_AGENT=0` for a quiet round | `wtdd/chat/test_triggers.py` |
| a duplicate trigger | second wake re-arms only; second claim refused | see prohibited actions | `twice` trials |
| the send is unconfirmed (osascript ok but no from-me row) | `find_from_me` times out | raises, not resent; the row has the error | ceiling: a human resends |
| the API process (dog owner) is down | `_via_api` gets a connection error | the calling process opens its own session (the dog takes one peer; a second connect fails loud) | ceiling |

### Numbers

Every number comes from the trials table above or from these commands; none is typed by hand.

| Metric | Regenerate |
|---|---|
| round seconds, writes, errors, room crossings, per-light latency | `walk` rows of the trials table; `python -m wtdd walk_path` prints the same |
| tilt pitch at capture, attempts, vision latency | `look` rows of the trials table |
| posts confirmed vs duplicates | `grep '"tool": "chat.post"' ledger.jsonl \| wc -l` against `grep -c '"tool": "chat.claim"' ledger.jsonl` |
| position corrections and their size (odometry drift as the human saw it) | `grep '"tool": "dog.calibrate"' ledger.jsonl` and the jump between `state_before.p` and `state_after.map.p` per row |
| route replay: waypoints reached, end residual | `follow` rows of the trials table; `grep '"tool": "dog.follow"' ledger.jsonl` |
| one live wake, end to end | `python -m wtdd ledger_tail n=60` right after a housemate's text |

### Idempotence

Re-running never re-posts: every post is claimed on the guid of the message that caused it (plus the stop index), a CLI post on a key you pass. Re-running the round rewrites the same lights to the same levels and reads them back; the dog gets the same allowlisted commands. Nothing is deleted from the group, ever.

## Ceilings and the DEMO_CACHE inventory

`grep -rn "DEMO_CACHE:" wtdd ui`:

- `wtdd/tools/dog_say.py`: the tidy baseline frame per stop (`~/Pictures/wtdd/tidy-tilt-stop<i>.jpg`), captured by the same look when the spot was tidy so the model reports only what changed. Live: `python -m wtdd dog_say baseline=true stop=<i>`; delete the file to run without one. Only inputs are cached, never the model call or the post.

Known ceilings, stated instead of faked:

- **No planner.** The Wi-Fi driver (`unitree_webrtc_connect` 2.2.0) names 17 LiDAR/SLAM/navigation topics and implements a point-cloud subscribe only; there is no waypoint or go-to-pose call, and `TrajectoryFollow` is absent from the motion controller this dog runs (`mcf`). What exists is ours: odometry tied to the map by a human calibration, a recorded route, a proportional follower, and the dog's own obstacle avoidance for what is in front of it. It does not plan around furniture it has not been driven past, and drift is corrected by a person dragging the dot. The LiDAR occupancy overlay (`wtdd/dog/lidar.py`, `GET /dog/lidar`) is built and verified offline against the driver's frame format; its live test is pending.
- **The local detector is observability, not a gate.** `python -m wtdd.watch` runs YOLO11n (open source, COCO's 80 classes) in its own process over the live frames and shows boxes and counts on the remote, with a `watch.detect` row whenever what is in view changes. COCO names cup, bowl, bottle, chair, person, not socks or "out of place", so the sentence still comes from the vision model, and nothing in the round acts on the detector.
- **No face recognition.** Anyone in the frame is a stranger tonight.
- **Zones are hand-drawn**, not scanned. The path, the stops and the light positions are placed on a hand-drawn floor plan.
- **The armed model** (`WTDD_AGENT=1`) can reply to chatter while the dog is armed. Off for a quiet round.

## Where things are

| use | where | entry |
|---|---|---|
| one task, one file | `wtdd/tools/` | `python -m wtdd <name> k=v`, `POST /tools/<name>`, MCP |
| where it thinks it is: odometry to map, steering | `wtdd/dog/nav.py`, `wtdd/dog/session.py` | the remote's dog panel; `POST /dog/calibrate`, `/dog/record`, `/dog/follow` |
| the LiDAR band on the map (live test pending) | `wtdd/dog/lidar.py` | `POST /dog/lidar {on}` then `GET /dog/lidar` |
| the round's eye: look, vision JSON, post | `wtdd/tools/dog_say.py` | `python -m wtdd dog_say` |
| the second eye: YOLO11n boxes on the live feed, in its own process | `wtdd/watch.py` | `python -m wtdd.watch` |
| the alarm | `wtdd/tools/light_alarm.py` | `python -m wtdd light_alarm` |
| the model in charge | `wtdd/agent.py` | `python -m wtdd ask "..."` |
| the group chat: read, gate, never twice, the wake sequence | `wtdd/chat/` | `python -m wtdd.chat listen`, `simulate` for a dry run |
| the body: one shared WebRTC session, drive, looks, frames | `wtdd/dog/` | `python -m wtdd.dog probe`, the remote's dog panel |
| the lights, Hue | `wtdd/hue/` | `python -m wtdd.hue probe` |
| the lights, strip | `wtdd/tuya/` | `python -m wtdd.tuya probe` |
| the field: the entity walks the map, lights follow, stops pause it | `wtdd/field.py` | `python -m wtdd walk_path` |
| the remote, one screen: map with the live dot and stops, dog panel with the live camera, the eye (detector boxes, last sentence), state read back, receipts, the trials table | `wtdd/api.py`, `ui/` | `python -m wtdd.api` |
| the evals | `wtdd/evals.py` | `python -m wtdd.evals` |
| any MCP client | `wtdd/mcp_server.py` | `claude mcp add wtdd -- $PWD/.venv/bin/python -m wtdd.mcp_server` |
| receipts | `ledger.jsonl` (gitignored) | `python -m wtdd ledger_tail n=20` |
| the two-minute video, shot by shot | `docs/DEMO-SCRIPT.md` | |

What each file does, how to run it, and the facts measured on the real devices live in that file's docstring. The research and planning docs from the build night were removed from the tree on 2026-09-13; `git show df77344:docs/` has them.

## Team

Johnny Sheng ([@Jshengdev](https://github.com/Jshengdev))
