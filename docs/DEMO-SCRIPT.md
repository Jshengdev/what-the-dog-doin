# DEMO-SCRIPT: two minutes, 25% failure, 75% proof

The shot list and recording plan for the two-minute demo, plus the outline of the brief that ships with it. Sources: the founder's words in `docs/raw/2026-09-12-yap-01.md`, the job in `docs/SCOPE-LOCK.md`, the graders in `docs/JUDGES.md` (§9, §10 item 8: "A 2-minute demo that is 25% failure, 75% proof"), the screen in `docs/TASTE.md`, and the half-half rule in `CLAUDE.md` §2. Judging is a 40-minute window for every team, so this video and the brief are what get read. Every row on screen is a real ledger row; the row numbers and latencies below are examples and are replaced by whatever the ledger says on the day.

Clock: agent frozen 3:00, trials run 2:15 to 2:50, record 2:50 to 3:20, edit 3:20 to 3:40, brief done 3:45.

## 1. First five seconds, last frame

- Pitch line, shown as a caption at 0:00 over the dark room, read once, flat: **"a robot dog does a round of the house, the lights follow it, and it texts the house what's out of place."** It is his own framing: "as the robot dog moves through the space, it tells other agents to turn on the other lights" and "a round of like making sure everything is tidy."
- Last frame at 1:58: the dark corridor, one light on, the dog sitting under it. Mono line from the ledger, `run 14 · 12 steps · 3 apps · 1 failed, reported · ledger.jsonl`, and under it, in Onest, **"that's what the dog doin."** No logo, no URL over the voice; the repo path sits small in the corner.

## 2. Shot table (120 s)

Lights: A (background), B (middle), C (front), 1.5 m apart on a tape line. Marks: START under A, MID under B, FRONT under C, the sock 1 m past FRONT. Split: 0:00 to 0:25 corridor, 0:25 to 0:55 sit and report, 0:55 to 1:25 UI and ledger, 1:25 to 1:50 failure and trials, 1:50 to 2:00 close. Failure plus proof is 55 s of 120.

| # | start | dur | camera sees | screen shows | one line (caption unless marked voice) | technical claim |
|---|---|---|---|---|---|---|
| 1 | 0:00 | 5s | Dark room, A B C off, dog lying at START. Housemate's phone in the foreground, THE CASTLE open; they type "what the dog doin" and send | Trigger bar, three chips `dog · connected` `hue · connected` `imessage · connected`, ledger `receipts · 0 rows` | the pitch line | The trigger is a real text in a real group, read from chat.db |
| 2 | 0:05 | 5s | Dog stands. A comes on over it | Rows land one at a time: `#01 imessage · received · guid`, `#02 dog · StandUp · mode read back`, `#03 hue · zone a · on · read back on` | "it read the text. it stood up. the light over it came on." | A step is done only when the device read-back says so |
| 3 | 0:10 | 10s | Dog walks A to C. Crossing A/B: A off, B on. Crossing B/C: B off, C on. Static camera, 3/4 side angle, all three lights and the whole path in frame | Corridor strip: three zone chips, the dog dot on odometry, the lit chip is the one live thing. Rows `#04 hue · zone b on · zone a off`, `#05 hue · zone c on · zone b off` | "as the robot dog moves through the space, it tells other agents to turn on the other lights" (his words, verbatim) | Light state follows body position from odometry, read back, within 2 s |
| 4 | 0:20 | 5s | Cut to black | Title card, editorial black on white: `what the dog doin`. Mono sub-line `dog · hue · imessage` | silence | none; the single editorial moment TASTE allows |
| 5 | 0:25 | 8s | Dog stops at FRONT, sits. The sock is 1 m ahead in the front zone. All three lights come on | Rows `#06 dog · Sit`, `#07 hue+tuya · all zones on · read back 3/3`, `#08 dog · frame captured · sha256`. Stage shows the frame itself | "it sits, looks, and lights up the space." ("the dog like sits down and it looks at the scene ... it'll light up the space") | The frame in the UI is the dog's front camera; its hash is in the ledger |
| 6 | 0:33 | 9s | Hold on dog and sock | Stage: vision as key-value rows `baseline · run 3 frame · ◧ cached`, `diff · 1 item`, `item · sock · floor · front zone`. Row `#09 vision · 1 item · 1.9s` | "one thing on the floor that wasn't there this morning." | Vision compares the live frame to a labeled baseline; output is structured, not prose |
| 7 | 0:42 | 5s | Johnny's hand on the trackpad | ApproveGate `⛋ your call`, 900 ms hold, stamp `approved`. Row `#10 gate · approved · johnny` | "nothing goes to the house without a human holding the key." | Every write to real people is gated; the gate is a ledger row |
| 8 | 0:47 | 8s | Housemate's phone in frame, dog behind it. The message and photo land in THE CASTLE | Row `#11 imessage · sent · guid · confirmed from chat.db`. Chip `11/11 ✓`. Sentence `11 steps · 3 apps · 0 failed · 41.3s · live` | voice, the message itself: "round done. front zone: sock on the floor. lights 3/3 read back on." | The send is confirmed from chat.db, not from the AppleScript return |
| 9 | 0:55 | 12s | Split: left, shot 3 footage again; right, the Mac screen recording of the same seconds | Corridor strip and rows advancing in step with the room. Header pill `same take · run 13` | "the ui and the room, same run, same seconds. the layout is three zones, hand-written, not a scan of the house." | The UI renders from ledger.jsonl; the dot is odometry; the chips are read-back |
| 10 | 1:07 | 10s | screen only | Full ledger. Bottom-left mode-light `live`. The one `◧ cached` chip, on the baseline row | "is this real? bottom left says live. one thing is cached: this morning's clean-floor photo. labeled. one flag re-captures it." | Cached inputs are labeled on screen; logic is never cached |
| 11 | 1:17 | 8s | screen only | Click `#04`: it expands to the raw request and the raw read-back `{"on":true,"reachable":true}` | "every row opens to the raw call and the raw state read back." | Receipts are device state, not the agent's own report |
| 12 | 1:25 | 13s | Second run. A hand flips the wall switch on C to off (his "broken light"). Trigger sent again. Dog stands, A on, walks, B on. At B/C, C stays dark. The dog stops at MID and does not enter the dark zone. Phone: the message lands | Row `#06 FAILED · hue · zone c · on · read back unreachable`, red wash, `role=alert`. `#07 dog · StopMove · pos read back`. `#09 imessage · sent`. Sentence `9 steps · 3 apps · 1 failed · live` | voice, the message itself: "stopped at the middle. front light: commanded on, read back unreachable. not walking into a dark zone." | The failure is on the exact step, no retry loop, and the report says what did not complete |
| 13 | 1:38 | 12s | screen only | Trials table, the eval command's stdout, not a slide: 5 scenarios x 3 runs, pass / fail / unsafe, eyebrow shows the command and run ids. Under it the prohibited-actions list with its violation count | "five scenarios, three runs each, graded from the lights, the dog and chat.db after every run. nothing typed by hand." | Grading is from before-and-after state; unsafe is asserted every run |
| 14 | 1:50 | 10s | Dark room, A and B off, C on, dog sitting under it. Hello once if it worked in rehearsal, else hold | The last frame from §1 | voice: "that's what the dog doin." | none; the close is the receipt |

Four things from his description that cannot be made true by 3:00, and the honest shot instead:
- "scan entire house ... the UI is just like the layout of the house": cut in SCOPE-LOCK §6. Shot 9 shows three hand-written zones and the odometry dot, and the caption says so.
- "a broken light" seen by vision: vision cannot tell a broken bulb from an off bulb at floor level. The broken light is a device-state fact (commanded on, read back unreachable) and it is the failure shot, 12.
- "anything out of place ... anything changed": one planted floor object per run, floor only (SCOPE-LOCK §6). Shot 6 claims one sock, not the room.
- "even the top lights over there" via Tuya: only if the Tuya link lands. Otherwise shot 5 is Hue only and the ledger shows `tuya · not linked · skipped`.

## 3. What must be true, live or recorded, and the filming

| # | must be true before filming | live or recorded | DEMO_CACHE label and the flip |
|---|---|---|---|
| 1 | Messages.app signed in on the demo Mac, Full Disk Access on, watcher tailing chat.db, the housemate is a member of THE CASTLE | live | none |
| 2 | Dog on house Wi-Fi (STA-L) with its AES key fetched; Hue bridge on the Mac's subnet and paired; zone list maps light A to `zone a` | live | none |
| 3 | Odometry arrives from the driver; boundaries at x=0.75 and x=2.25; lights agent reads state after every write | live | none |
| 4 | an edit | recorded (title) | none |
| 5 | Sit works; a frame is pulled from the WebRTC video track, written to disk, hashed; Tuya linked, else Hue only | live | none |
| 6 | Baseline frame captured by the same capture code at FRONT with a clean floor, during rehearsal run 3 | live call, cached input | `// DEMO_CACHE: baseline_frame` (what: clean-floor frame at FRONT; why: stable diff, 3 s saved; live: `WTDD_BASELINE=capture`). Flip: set the flag, the run captures its own baseline first |
| 7 | Gate sits before the send; the hold is a real 900 ms; the stamp writes a row | live | none |
| 8 | AppleScript send to the group `chatId`; from-me watcher confirms the guid; phone B online, notifications on | live | none |
| 9 | Screen recording ran for the whole take; one clap on both recordings | recorded, same take | none; on-screen pill `same take · run 13` |
| 10 | Mode-light reads the environment at boot, never a constant | live | none |
| 11 | Row expansion renders the stored request and response | live | none |
| 12 | Light C on a wall switch or a plug; Hue reports `reachable:false` (or Tuya local times out) inside the 5 s step timeout; dog policy is stop, not retry | live, a physical fault | none. Backup only: `WTDD_INJECT=hue_timeout`, row chip `◧ injected`. Flip: unset it and use the wall switch |
| 13 | The eval command reads the day's ledger and prints the table | recorded output of real runs | none; eyebrow carries the command and run ids. Flip: rerun the command |
| 14 | same as 12's end state | live | none |

Flag names above are what the code must use; if the code lands with different names, fix this table, not the video.

Filming, physical:
- Lights at 40% brightness (Hue `dimming` 40, Tuya `bright_value` 400) aimed at the floor and the wall, never at the lens. Full brightness clips the sensor and the dog vanishes into the blowout.
- Camera phone A on a tripod (or a stack of books) at knee height, 3/4 from the side, 4 m back, so all three lights, the dog's whole path and the sock are in frame. Never handheld for shots 2, 3, 12.
- Exposure: long-press to lock AE/AF on the middle light while it is ON, then drag exposure to about -1.0; it must not re-meter when a light flips. Better: Blackmagic Camera (free), 1080p30, ISO 800, shutter 1/60, WB 3200K locked. Stock app: Settings > Camera > Record Video 1080p at 30 fps, HDR Video off, Auto FPS off (or the dark frames drop to 24). 30 fps, not 60, to avoid LED flicker.
- The real iMessage on a real phone: phone B belongs to a housemate who is in THE CASTLE. Brightness max, Do Not Disturb off, chat open before the take, held 40 cm from the lens with the dog 2 m behind; both stay sharp on a phone sensor. It sends the trigger in shot 1 and receives the report in shot 8 and 12.
- The UI: QuickTime screen recording (Cmd+Shift+5) of the browser window, microphone on, started before "record" on phone A. Sync: one clap after both are rolling; align on the clap in the edit. Cross-check: the `hue · zone a · on` row timestamp against the frame where A lights.
- Voice lines are read after, over the cut, flat, no music under them.

## 4. Dog choreography, rehearsal, reset

Driver: `unitree_webrtc_connect`, `SPORT_CMD` names. Move is a velocity command sent at 10 Hz for the stated duration (x m/s forward, y lateral, z rad/s yaw); 0.3 m/s covers 1.5 m per zone in 5 s. Verify every name against the driver's table before the first rehearsal.

- Pre-roll: dog powered, lying at START (StandDown), facing +x down the tape line. All lights off, read back off. Ledger: new `run_id`.
- Shot 1: no dog command. Housemate sends the trigger.
- Shot 2: `StandUp`; hold 2 s. Lights agent: zone a on.
- Shot 3: `Move(x=0.3, y=0, z=0)` for 10.0 s; `StopMove`. Zone switches fire from odometry at x=0.75 and x=2.25. Expect x=3.0 at FRONT.
- Shot 5: `Sit`; hold 1.5 s (the look: the sit pose points the camera down the corridor at the sock). Lights: all zones on, read back. Capture frame, hash it.
- Shots 6 to 8: no dog command. Vision, gate, send.
- Shot 12 (failure run): reset, then `StandUp`; `Move(x=0.3)` until the B/C boundary (about 7.5 s); the zone c write fails; `StopMove`; position read back; stays at MID. Send.
- Shot 14: `Hello` once (only after `RiseSit`, then `Sit` again) if it passed rehearsal; else nothing.

Rehearsal: the trials are the rehearsal. Run S1 clean x3, S2 sock x3, S3 broken light x3 (9 corridor runs), then S4 double trigger x1 full run plus 2 short, S5 non-trigger x3 (no movement). About 30 minutes with resets, every run in the ledger. The recorded take is run 13 (S2) and run 14 (S3), one more row each, not special cases. Budget three takes per recorded scene.

Reset between takes: `StopMove`, `StandDown`; carry the dog to START, nose on the tape. Lights agent `baseline`: all off, read back off (this is row 0 of the next run). Sock back on its tape X. Wall switch C back on for clean runs. New `run_id`; the previous run's rows are never rewritten. Nothing is deleted from THE CASTLE; the gate is what stops duplicates.

## 5. Fallback tree

| if | the demo still shows, honestly | on-screen line |
|---|---|---|
| The dog will not connect | The lights and iMessage run live with the dog step red (`FAILED · dog · webrtc handshake`), and the corridor footage from rehearsal plays under the header pill `◧ replay · run 4 · 13:12 today` with its ledger timestamps in frame | "the dog would not connect at 15:20. this corridor is run 4 from this afternoon, ledger on screen. lights and chat are live." |
| Hue is unreachable (subnet) | Three Tuya plugs take the three lights if Tuya is linked. Else the lights step fails loud on every zone, the dog still walks, sits, sees, sends; the message says the lights did not answer | "hue is on another subnet and did not answer. the lights rows are red. the dog and the chat are live." |
| Tuya is not linked | Corridor is Hue only; shot 5 lights up with Hue only; a `tuya · not linked · skipped` row stays in the ledger | "tuya did not link today. skipped, not faked. three apps: dog, hue, imessage." |
| Vision is wrong on the day | Ship the run anyway; the message says exactly what vision said; the trials table counts it as fail | "vision missed the sock this run. counted as a fail. 2 of 3 in trials." |
| Light C does not fail cleanly on the wall switch | `WTDD_INJECT=hue_timeout`, chip `◧ injected` on the row | "this timeout is injected by flag, and the row says so." |

## 6. The brief that goes with it (readable in 90 s)

Mirrors `docs/RELIABILITY-BRIEF.md` and the judges' pass / fail / unsafe framing. Every number is read from a file or a command named beside it.

| section | one line | source of the numbers |
|---|---|---|
| What it does | The job from SCOPE-LOCK §1, trigger to result, four sentences | none |
| System | Trigger, dog, lights, iMessage, result, as a numbered list; model and loop named | none |
| Apps connected | Dog / Hue (+Tuya) / iMessage: operation, read or write, auth, live or DEMO_CACHE | `grep -rn "DEMO_CACHE:" .` |
| Receipts | Where `ledger.jsonl` lives, one real row pasted, the poll that renders it | `tail -n 1 ledger.jsonl` |
| Evals | Five scenarios S1 to S5, what each checks, one command | the eval command from SCOPE-LOCK §7 |
| Trials | 5 x 3 runs, pass / fail / unsafe, graded from read-back state after each run | the eval command's table |
| Prohibited actions | Never send without the gate; never act twice on one ask; never touch a light not in the zone list; never enter an unlit zone. Asserted from chat.db, Hue/Tuya state, odometry vs lit zone | the eval command's violations line |
| Numbers | Zone-lit latency, round time, sends per ask, vision hit rate | `jq` over `ledger.jsonl` |
| Failure modes | Hue unreachable, Tuya timeout, dog handshake, vision miss, duplicate trigger; detected how, handled how, eval or ceiling | the trials table |
| Ceilings and cache | One cache (`baseline_frame`) with its flip; floor-only vision; hand-written zones | `grep -rn "DEMO_CACHE:" .` |
| Idempotence | Re-running never re-sends: the gate plus a per-ask guid check | `S4` row of the trials |

## 7. Recording-day checklist

- Props: Justin's three big lights, each on Hue or on a Tuya plug (a light the agent cannot address is a prop, not a zone); the tape line with START, MID, FRONT and the sock's X; one sock (or a cup); light C on a reachable wall switch; the dog charged, on house Wi-Fi; a tripod or a book stack.
- People: Johnny at the Mac (runs the agent, holds the gate, claps). One housemate in THE CASTLE with phone B (sends the trigger, holds the phone in frame). Everyone else out of the corridor and off the lights app.
- Files: `ledger.jsonl` copied to `docs/evidence/ledger-2026-09-13.jsonl` after the last take; the trials table stdout saved to `docs/evidence/trials.txt`; the baseline frame and the two report frames saved beside them; the screen recording and the phone footage in one folder named by `run_id`.
- Export: 1080p, 30 fps, exactly 120 s, captions burned in (lowercase, one line, under 60 characters), voice lines dry, no music over the voice, mono captions for measured truths and Onest for everything else. Title card is the only black-on-white frame. Check: every number on screen exists in the copied ledger.
