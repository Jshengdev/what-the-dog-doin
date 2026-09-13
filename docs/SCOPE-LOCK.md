# SCOPE-LOCK: the one agent

Johnny fills this. Claude sharpens it. Nothing gets built until §1 through §4 are filled and §7 is signed.

**Status: DRAFT, awaiting Johnny's signature** (drafted 2026-09-12 from his words in `docs/raw/2026-09-12-yap-01.md`; every line below is his idea reflected back, not Claude's)

## 1. The job (one sentence)

A robot dog that does rounds of the house for the housemates: as it moves through the dark house the lights ahead of it turn on and the lights behind it turn off, so nobody trips over it and no electricity is wasted; on each round it looks at the space and reports what is out of place into the house group chat.

Who: the housemates of THE CASTLE. Trigger: a housemate asks in the group chat, or a scheduled night round. True afterwards: the lights tracked the body, and the group has a photo and a list of what is out of place.

## 2. The apps (at least three)

| # | App | Role in the job | Read / Write | Auth we have today | Risk (auth, rate limit, odd API) |
|---|---|---|---|---|---|
| A | Unitree robot dog | The body: moves the route, reports position (odometry), captures the camera frame, sits and looks | R/W | Dog owned; house Wi-Fi + per-device AES key (firmware 1.1.15+) still to do | Wi-Fi mode, firmware key, asyncio process must hold one connection |
| B | Lights: Philips Hue bridge + Tuya (Smart Life) living room lights, optionally other lights via reverse-engineered app (Proxyman) | The environment: light the zone ahead, darken the zone behind, "light up the space" when the dog looks | R/W | Signed into both apps on phone; Hue bridge on another subnet; Tuya developer project not created | Subnet, link button, Tuya account approval, latency of cloud calls |
| C | iMessage group chat (THE CASTLE), Slack as fallback | The people: asks come in, the report with photo goes out | R/W | chat.db readable, Full Disk Access granted, free imessage-kit | Real housemates on the other end: gate every send, never send twice |

## 3. The steps (numbered)

1. A message lands in the group chat (iMessage). The central agent reads it and decides the round.
2. Central dispatches the dog agent: route to walk, where to sit and look.
3. As the dog moves, the dog agent publishes its position; the lights agent lights the zone ahead and darkens the zone behind (Hue / Tuya), reading light state back after each change.
4. The dog sits; a camera frame is captured; vision compares it to the baseline and lists what is out of place (cups, socks, a broken light, anything changed, anyone unexpected).
5. Central posts the report and the photo to the group chat, behind a gate. One ledger row per step.

## 4. Crystal I/O

- **Trigger** (the exact input): a text in the group chat such as "what the dog doin" or "dog, do a round"; or a scheduled time.
- **Result** (the exact visible output): lights that visibly tracked the dog; one message in the group with a photo and the list of what is out of place; the house-layout UI showing the dog and the lit zones lined up.
- **Receipt** (what the ledger shows for one successful run): message received (guid) · each dog command and the state read back (mode, position) · light state before and after per zone · frame hash and the vision output · message sent (guid) · latency per step.

## 5. Sharpening questions (answer before building)

- What would have to be true for this to work? Dog on the house Wi-Fi with its key; lights reachable from the demo Mac; odometry position mapped to light zones well enough; vision can see floor-level mess from the dog's camera; iMessage send works into the group.
- What is the test that would falsify it? Run the round three times. If the zone containing the dog is not lit within a few seconds, or the report misses a planted object, or the group gets texted twice for one ask: fail.
- What is the smallest version that would prove the bet? One corridor or room with three lights in a row (the demo scene), one planted object on the floor, one message in, one message out.
- Why these three apps and not any other three? Body, environment, people. Remove any one and it is a smart-home app, not an agent with a body in a house.
- What is unique about doing this on our stack? An embodied agent in a real house with real housemates, three agents orchestrating one body, and a ledger that proves every step from device state.

## 6. CUT list (explicitly not building)

- A scan or map of the whole house (a hand-written zone list is enough; LiDAR map only if it is free).
- Table-top vision. The camera is at floor level. Floor only, unless the dog stands.
- Intruder detection beyond "an unexpected person is in the frame."
- Reverse-engineering the non-Hue lights. Only if Hue and Tuya are both done.
- Slack. iMessage first.
- Voice, TTS, a custom head, any hardware beyond the dog.

## 7. Stack lock

- Runtime / language: Python is forced for the dog (asyncio driver). The rest is the open decision: all-Python, or Node central (imessage-kit) with a Python dog sidecar over local HTTP. See `docs/ARCHITECTURE.md` for the recommendation.
- Agent loop (model, tool calling):
- App connectors (SDKs, MCP, raw API): `unitree_webrtc_connect` · Hue CLIP v2 or `openhue` · `tinytuya` · `@photon-ai/imessage-kit` or chat.db + osascript
- Where the ledger lives: `ledger.jsonl`, append-only, one row per step
- Where evals live and the one command that runs them:

Signed: ________ (date)

## Feasibility check (2026-09-12, verified from this Mac)

Facts found before the lock. Not decisions.

| App | What was verified | Status | Risk / what has to be true |
|---|---|---|---|
| iMessage | `~/Library/Messages/chat.db` is readable from this process (327 chats; Full Disk Access already granted). Most active named group chat: "THE CASTLE" (last message 2026-09-12 20:51). Free `@photon-ai/imessage-kit` reads chat.db via WAL watching, sends to a group `chatId` via AppleScript, and `onGroupMessage` carries sender identity. The `doubles` repo already wraps the paid Photon kit (`src/spectrum/imessage.ts`, needs `IMESSAGE_SERVER_URL` + `IMESSAGE_API_KEY`). | GREEN | Messages.app must be running and signed in on the demo Mac. Sends are fire-and-forget; confirm via the from-me watcher. Tapbacks and threaded replies need the paid kit. Real housemates are on the other end: every write must be idempotent and gated. |
| Philips Hue | Bridge `001788fffe616851` at `10.66.1.109` sits on the wired 10.66.1.x side; the Mac's Wi-Fi is 10.66.10.x and cannot reach it. **Solved 2026-09-13 01:45 via the Remote Hue API (cloud OAuth): probe ok, 7 lights, 4 in the Living room (Hue Iris 2, Go table lamp 1, special, sticky canbo), set + read-back ok, alternating red/blue signal ok, 15 quick sets with no 429, median 0.8 s per set including read-back.** | GREEN (cloud) | The Mac and the bridge must be on the same subnet (join the router the bridge is wired to, or move the bridge). Then one link-button press to pair. Local CLIP v2 API or `openhue` CLI (`brew install openhue/cli/openhue-cli`). Fallback is the Hue Remote API (cloud OAuth, developer account, slower to set up). |
| Tuya (Smart Life app) | **Solved 2026-09-13 02:25: WT1 2CH CCT LED controller, local protocol 3.5 at 10.66.10.44, key via Tuya IoT project + QR link; on/off/dim/temp/fade with read-back (`wtdd/tuya`).** No prior code in any repo. Path: Tuya IoT Platform project, link the Smart Life app by QR, `python -m tinytuya wizard` to pull device ids and local keys, then local LAN control or `tinytuya.Cloud`. | GREEN (local) | Developer account approval and the app-link step were the friction; done. Which physical devices are on the app decides what the agent can actually do (plug, bulb, heater, fan). Same-LAN needed for local control. |
| Unitree robot dog | Physical dog confirmed by Johnny (model and firmware not yet stated). `unitree_webrtc_connect` (PyPI) drives Go2 Air/Pro/Edu, G1, R1 over Wi-Fi with the same WebRTC protocol as the Unitree app, no jailbreak. Exposes `SPORT_CMD` (StandUp, Sit, Hello, Move, Dance, ...), the **front camera as a WebRTC video track** (`examples/go2/video/camera_stream/`), two-way audio (Go2), and LiDAR point cloud (Go2). Modes: AP (join the dog's hotspot), STA-L (dog on house Wi-Fi, connect by IP or serial), STA-T (Unitree cloud relay). | YELLOW | Go2 firmware 1.1.15+ needs a per-device AES-128 key for the LAN handshake, fetched once with `unitree-fetch-aes-key --email ... --password ... --device-type Go2` using the Unitree account the dog is bound to. Dog must be put on the house Wi-Fi via the Unitree Go app (STA-L) so the Mac keeps internet for iMessage. "Go find out" = move + camera frame + vision description; the dog cannot navigate to a named room without a map, so the smallest version is a fixed route or a look-around from where it sits. |

Sources: https://github.com/photon-hq/imessage-kit · https://github.com/legion1581/unitree_webrtc_connect · https://github.com/jasonacox/tinytuya · https://www.openhue.io/cli · https://discovery.meethue.com/

## Decision log

- 2026-09-12: repo created. Idea not yet articulated.
- 2026-09-12 (Johnny, verbatim): "a basic idea i have is just something to connect an agent to imessage group chats about housemates, then it connects to phillips hue if possible and this tuya app on my phone and then finally a unitree robo dog and want to call the project what hte dog doin. and its just an agent that acts as the intermediate for your smart home"
- 2026-09-12 (Johnny, verbatim): "i have a phsyical unitree dog i signedi nto phillip and tuya does tha wok?> the devices tuya is just hte living room lights. THe overall concept here is real world housemate enviornemtn. when you live iwth housemates and want the dog to go find out what you doin. something liek that"
  - Resolved: physical Unitree dog exists (model not yet stated). Tuya devices = the living room lights only. Signed into the Hue app and the Tuya app on the phone.
- 2026-09-12 (Johnny, verbatim, on the name's reading): "it should be some sort of real world orchestration but for housemates and having agents actually control with a physical body"
- 2026-09-12 (yap 01, saved verbatim at `docs/raw/2026-09-12-yap-01.md`): lights follow the body ("as the robot dog moves through the space, it tells other agents to turn on the other lights"); the tidy/security round ("a round of like making sure everything is tidy", "one is security, two is making sure everything's in its place"); three agents ("light agent, dog embedded body system, central guy"); the demo (three lights in a row, dog walks, behind off, front on, title card, then dog sits and spots a broken light / what changed); house-layout UI "for optics"; headless allowed; sponsors optional; the judges' read ("make your agents more capable in the real world").
- 2026-09-12 (yap 02, saved verbatim at `docs/raw/2026-09-12-yap-02.md`): the map ("a 3D scan converted into a flat 2D image", draw the routine, "drag and lasso a circle for check for consistency"); the cost gate ("if OpenCV detects [a change] in this boundary then call up" Claude, "instead of spamming tokens"); send rule ("boundary then send to group chat. Just send"); no drawn path in the demo ("just say run daily checks and the dog just goes"); lights only where it is looking, so it runs at night and you wake up to updates; the intruder scene ("person not recognized enters the house, turn lights on, red flashing, and spam the group chat"); stairs clip as the money shot ("don't blow it too much"); the final 2-minute structure (open on dog + lights, title, "we designed this dog to do this, this and this", the scan, the map, night scenario 1 cups on the table before/after "who the flip did this", scenario 2 lights on/off briefly, scenario 3 intruder, end on the title). Conflicts with the draft above to resolve at signing: cups ON THE TABLE vs the floor-level camera (§6 cut); "person not recognized" vs "unexpected person in frame" (§6 cut); the lasso UI vs headless (see `docs/THREADS.md`).

