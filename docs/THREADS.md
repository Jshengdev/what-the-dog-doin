# THREADS: the live threads, what each needs, headless or UI

The parallel workstreams for the build day, cut from `docs/raw/2026-09-12-yap-02.md` and yap 01. Each thread is one window's job. Feasibility is rated from facts verified on 2026-09-12 (see `docs/SCOPE-LOCK.md` Feasibility table, `docs/ARCHITECTURE.md`, `docs/VISION.md`, `docs/DEMO-SCRIPT.md`). GREEN = verified path, YELLOW = works with one unknown, RED = not in 6.5 hours as described. Every thread ends in ledger rows; nothing counts until it has printed one.

## The verdict on headless vs UI

The agent is headless. Every job in the yap (run daily checks, lights follow the body, before-and-after, the intruder alert, the group chat) runs with no screen: the trigger is a text in the group chat or a schedule, the outputs are lights, dog motion, and a message. The one thing that needs a screen is the optics: the map with the dog on it. That is a read-only page fed by the ledger and a state file (`docs/ARCHITECTURE.md` §8, `docs/TASTE.md` §3). The authoring interactions in the yap (draw the routine line, drag and lasso a region to check) are a second tier: nice in the video, not needed by the agent, because regions and the route can be authored once as a JSON file. Build the read-only map. Build the lasso only if everything else is green by 1:30 PM.

## Thread table

| # | Thread | Delivers | Headless? | Feasibility | Depends on | Time-box | Demo shot |
|---|---|---|---|---|---|---|---|
| T0 | Tonight: connectors | Dog on Wi-Fi with key, Hue app key, Tuya linked, test group chat | yes | GREEN, see `docs/SETUP.md` | nothing | tonight | all |
| T1 | Body | One Python process holding the dog connection: state stream (mode, odometry, IMU), StandUp / Move / Sit / Hello, latest camera frame on request | yes | GREEN (driver verified; camera track YELLOW until the first frame lands on this Mac) | T0 | 9:30 to 11:00 | corridor, sit-and-look |
| T2 | Lights | Zone control with read-back on Hue (and Tuya if linked); the `alternating` red and blue signal for the alert | yes | GREEN (CLIP v2 `signaling` verified: `signal: alternating`, `duration` ms, two `color` xy values; color bulbs only, white bulbs flash on/off) | T0 | 9:30 to 10:30 | corridor, intruder |
| T3 | Chat | Read the group chat, gate, send with from-me read-back, never twice | yes | GREEN (chat.db readable; osascript send; test group only) | T0 | 10:00 to 11:00 | who-the-flip, intruder |
| T4 | Follow the body | Odometry to zones, hysteresis, ahead lit and behind dark, read-back per change | yes | GREEN in a straight corridor; YELLOW anywhere with turns (odometry drift, no map) | T1, T2 | 11:00 to 12:00 | corridor |
| T5 | Watch | Baseline per look-point; OpenCV region diff as the cheap gate; Claude vision only when a region changed; the one-sentence report with photo | yes | GREEN (see `docs/VISION.md`; the OpenCV gate is a per-region mean-abs-diff, no new dependency) | T1, T3 | 12:00 to 1:30 | who-the-flip |
| T6 | Night alert | Person detected during the night round: lights to alternating red and blue, one alert to the group with the frame, bounded follow-ups | yes | YELLOW: "person detected" is green (local detector or the vision call's `people_present`); "person not recognized" is RED (face recognition of housemates is not a 6.5-hour job and is a privacy call) | T2, T3, T5 | 1:30 to 2:15 | intruder |
| T7 | Map | The floor plan image with the dog as the one live dot, zones filling as lights change, ledger rows printing on the right | NO, one static page | GREEN for a read-only page; the scan source is the open question (below) | T1, T4 | 12:00 to 1:30 | "opens the UI" |
| T7b | Map authoring | Draw the route line; lasso a region to check | NO | YELLOW, 2 to 3 hours on its own; cut first | T7 | only after 1:30 if all green | optional |
| T8 | Receipts | `ledger.jsonl`, `evals.py --trials 3`, trials table spliced into `docs/RELIABILITY-BRIEF.md`, Lemma trace per run | yes | GREEN (designed in `docs/ARCHITECTURE.md` §5 to §7) | T1 to T5 | 2:15 to 2:50 | trials table |
| T9 | Capture | The 120-second video per `docs/DEMO-SCRIPT.md`, stairs B-roll if the model allows, edit, export | NO (a phone and an editor) | GREEN if T1, T2, T4 are green by 1:30 | everything | 2:50 to 3:40 | all |

Freeze at 3:00 PM. Cut order if behind, first to go: T7b, the LiDAR scan option, T6, Tuya, the table-top mess.

## The five feasibility calls from yap 02

**1. "A 3D scan converted into a flat 2D image."** Three sources, in order of honesty per hour:
- An iPhone Pro or iPad Pro (2021 or later, LiDAR) running Polycam Space Mode: one scan gives a 2D floor plan with measurements, processed on device, exported as PNG. Ten minutes tonight. Whether PNG export needs the paid tier is UNVERIFIED; the help center lists PNG and DXF as export formats. Source: https://learn.poly.cam/hc/en-us/articles/30299187161620-How-to-Create-Floorplan-Captures
- The dog's own LiDAR through the driver (`examples/go2/data_channel/lidar/lidar_stream.py`) projected top-down with numpy while the dog is walked around. Looks like "the dog scanned the house" and is the more on-brand story, but it is a front-mounted sensor with no SLAM, so the image drifts and takes two hours of fiddling. Not on the critical path. If used, the caption must say "point cloud from the dog's LiDAR, projected top-down."
- A hand-drawn SVG of the corridor with the three zones. Twenty minutes. Boring, honest, and enough for the map page.
Recommendation: scan with a LiDAR iPhone tonight if one is in the house; otherwise draw it. The demo line "first it did a scan of our house" is only true with the second source; with the first it becomes "we scanned the house."

**2. "Draw a line for its routine, drag and lasso a region to check."** The route is a hard-coded command sequence (his words: "hard code that path"), authored once in a JSON file in map pixel coordinates and drawn on the map page as a polyline. Regions to check are polygons in the same file. A 20-line helper page that logs click coordinates on the floor plan image authors both in minutes. Live drawing in the video is T7b. Honest caption on the map: "route and regions authored once."

**3. "If OpenCV detects a change in this boundary, then call up Claude."** This is the right cost gate and it is already the pre-check in `docs/VISION.md` §3, made per-region: crop each region from the baseline and the current frame, mean absolute difference in grayscale, threshold per region, log `scene_diff_pct` per region as its own ledger row, and only a changed region triggers the vision call. Zero new dependencies (cv2 is already required for frame encoding). Person detection for T6 is the same shape: a local detector on every frame during the night round, Claude only on a hit.

**4. "Cups, drinks on the table."** The camera sits about 30 cm off the floor and the Go2 has no pose that lifts it to table height. A dining table top is out of frame. The honest versions: plant the mess on the floor or a low table in the look-point's view, or angle the look-point at a chair. Decide at signing; it is a §6 conflict in `docs/SCOPE-LOCK.md`.

**5. "Person not recognized enters, lights flash red, spam the group chat."**
- Detection: "a person is in frame during the night round" is green. "Not recognized" means face recognition against housemates' faces, which is red for tomorrow and a consent conversation. The demo line becomes "unexpected person during the night round."
- Lights: Hue color bulbs take one PUT with `signaling: {signal: "alternating", duration: 15000, color: [{xy: red}, {xy: blue}]}`; verified in the OpenHue OpenAPI source (`src/common/Signaling.yaml`, https://github.com/openhue/openhue-api). White-only bulbs and Tuya bulbs get an on/off loop from the lights agent.
- "Spam": the no-double-send rule wins. One alert with the frame, then one follow-up every 30 seconds while a person is still detected, capped at five, each a ledger row. That reads as urgency on the phone without the agent violating its own prohibited-actions list.

**Stairs.** The Go2 Pro and Edu have dedicated climb and descend modes; the Air is not documented as climbing stairs. Sources: https://newatlas.com/robotics/review-unitree-go2-pro-quadruped-robot/ and https://www.docs.quadruped.de/projects/go2/html/Overview_1.html. It is B-roll driven by hand from the app, captioned as B-roll, never claimed as the agent. His own caution stands: "don't blow it too much." Skip on an Air.

## Windows (two people)

- **Window A, the body and the house:** T1, T2, T4, then T6 lights half. Owns the dog and the lights. Ends with the corridor running three times with receipts.
- **Window B, the eyes and the mouth:** T3, T5, T6 detection half, T8. Owns the chat, the baseline, the vision call, the evals, the brief.
- **Window C, the optics (after lunch):** T7, then T9. Owns the map page and the video. Starts on the scan tonight (T0).

Each window reads `CLAUDE.md` first, then its docs, and prints `[wtdd:...]` log lines from minute one.
