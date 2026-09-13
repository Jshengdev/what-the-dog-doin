# PLAN: the day, and what "done" looks like

Read this at 9:00 AM. It is the whole plan on one page. Everything else in `docs/` is the detail behind one line here.

## What we are building (the pitch, in Johnny's words)

"A robot dog does a round of the house, the lights follow it, and it texts the house what's out of place." Three agents (central, lights, body), three connectors (dog, lights, iMessage group chat), one ledger that proves every step from device state. The dog is the body of the house's agent. The name is the question you ask it.

## Done means all of this exists at 4:00 PM

1. **The repo** `what-the-dog-doin` (make it public, or share access, the moment the submission mechanism is known at 9:00):
   - `wtdd/` one Python package, one process: `dog.py` (connection, state, moves, latest frame), `lights.py` (zones, set, read-back, alternating signal), `chat.py` and `memory.py` (per `docs/CHAT.md`: poll the group by ROWID, trigger gate, osascript send of text and image, read-back confirm, never twice), `follow.py` (odometry to zones), `watch.py` (baseline, OpenCV region gate, vision call, report), `central.py` (the one model loop with typed tools), `ledger.py`, `evals.py`, `zones.json` and `regions.json` (authored once), `ui/index.html` (the map and the ledger page).
   - `ledger.jsonl` from the real trials, `baselines/` frames with sidecars, `evals/` truth files.
   - `docs/RELIABILITY-BRIEF.md` filled: system, apps, receipts, trials table (pass / fail / unsafe, 3 runs × 5 scenarios), prohibited actions with zero violations asserted from state, failure modes, DEMO_CACHE inventory, idempotence.
   - `README.md` with a "How we know it works" section that mirrors the brief and the one command that regenerates the trials table.
2. **The system runs on command:** `python -m wtdd round` does one round end to end on the corridor; `python -m wtdd evals --trials 3` prints the trials table and writes it into the brief. Every number on any screen comes from the ledger.
3. **The video:** 120 seconds per `docs/DEMO-SCRIPT.md`. Opens on the dog and the lights, title, "we designed this dog to do this, this and this," the map, the night scenario with the before-and-after photo landing in the group chat, the lights following, the unexpected-person alert with the red and blue signal, the trials table, the title again.
4. **The brief:** one page, readable in 90 seconds, every number sourced.

## The clock

| When | Window A: body and house | Window B: eyes and mouth | Window C: optics |
|---|---|---|---|
| 9:00 | Opening. Write down the submission mechanism and any rules. Sign `docs/SCOPE-LOCK.md` §7. | | |
| 9:30 to 11:00 | T1 dog: connect, state stream, Hello, one camera frame saved with its hash. T2 Hue: app key, one light on/off with read-back, one `alternating` signal. | T3 chat: poll the test group, send text and an image with from-me read-back, dedupe by guid. `ledger.py`. | Floor plan image in `ui/` (scan or hand-drawn). |
| 11:00 to 12:00 | T4 follow: corridor zones, hysteresis, ahead lit and behind dark, read-back per change. | T5 watch: baseline per look-point, OpenCV region gate, one live vision call, the one-sentence report. | Map page: dog dot from state, zone fills, ledger rows. |
| 12:00 to 1:30 | Corridor round three times with receipts. Fix what the ledger shows. | Report with photo lands in the test group. The gate. | Map page live against a real run. |
| 1:30 to 2:15 | T6 alert: person detected during the night route, signal red and blue on Hue, one alert plus bounded follow-ups. | `evals.py` for the five scenarios. | Rehearse the shots. Props on marks. |
| 2:15 to 2:50 | Trials: 5 scenarios × 3 runs. Brief filled from the ledger. | | |
| 2:50 to 3:20 | Record per the shot list. | | |
| 3:00 | **Freeze.** No new code. | | |
| 3:20 to 3:40 | Edit and export. | | |
| 3:45 | Brief done. README done. Repo shared. | | |
| 4:00 | Submit. | | |

Cut order if behind: lasso authoring UI, LiDAR scan, the alert scene, Tuya, the table-top mess. Never cut: the corridor with receipts, the report in the group, the trials table.

## Tonight, before sleep (in this order, stop when tired)

1. Mac, dog, and Hue bridge on one subnet (`docs/SETUP.md` §1). Verify with the unauthenticated bridge config curl.
2. Dog on house Wi-Fi in STA mode via the Unitree Go app; note IP and firmware; fetch the AES key if 1.1.15+ (§5). Verify with the read-only state example.
3. Hue link button, app key, one GET of a light's state (§2).
4. Create the test group chat "wtdd test" with Johnny and one housemate (§6). Never THE CASTLE until the demo.
5. Optional: Tuya project and QR link (§3). Optional: Polycam floor plan on a LiDAR iPhone.

## Open decisions to sign at 9:00

- Stack: all-Python, one process (the recommendation in `docs/ARCHITECTURE.md` §2).
- Model access for the central loop: API key, or the subscription through a headless harness.
- The three corridor lights and their zone ranges.
- The mess is planted on the floor or a low table, not the dining table top (camera height).
- "Unexpected person during the night round" replaces "person not recognized."
- Dog model and firmware (decides the key step and whether stairs B-roll is allowed).
