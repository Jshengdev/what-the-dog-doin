# DEMO-SCRIPT: the two minutes, shot by shot

Three acts. Every row on screen is a real ledger row; every number in a caption is read from `ledger.jsonl` or the trials table in `README.md` on the day. Status column: **proven live** = seen on the real device and in the ledger today; **built** = code path exists, not yet seen live in this form; **cut** = not made true today, the honest shot is written instead.

Clock: freeze 3:00 PM, record about 2:00, judging 4:00.

## Act 1: the problem (0:00 to 0:25)

| # | camera sees | screen shows | behind it | status | honest line |
|---|---|---|---|---|---|
| 1.1 | Caption over a dark house: an agent that only lives on a screen can only do screen work. Ming has a body, a few real tools and a real house | nothing | | | "give an agent a body and a space, and it can go and look" |
| 1.2 | Night. The dog walks a hallway; the lights come up around it and fade behind it | nothing, or the map's dot and glow | `walk_path` from the remote while Johnny drives the dog with the controller along the drawn route | lights **proven live**; the dog in sync is a filming task | "wherever it goes the lights come up; when the space goes dark the round is over" |

## Act 2: the round, one real take (0:25 to 1:30)

| # | camera sees | screen shows | behind it | status | honest line |
|---|---|---|---|---|---|
| 2.1 | A housemate's phone: "what the dog doin" sent to THE CASTLE | listener log `WAKE`, row `chat.wake` | `python -m wtdd.chat listen` | **proven live** | "a real text in the real group, read from chat.db" |
| 2.2 | The picture lands, then "dog doin" | rows `chat.post` with read-back guids | `dog_on_fire`, posts `fire:` and `doin:` | **proven live** | |
| 2.3 | Down the steps and into the living room; the lights get brighter the farther it walks; into the next room, the last room dims | the map: the dot walking, lamps glowing by distance, the room highlighted; receipts printing one write at a time | `walk_path` (`wtdd/field.py`), `GET /field` drives the page | field and page **proven live** today; the new route (steps, living room, workspace) and its stops are Johnny's to draw and save | "as the robot dog moves through the space, it tells the lights to come on" |
| 2.4 | Stop 1, cups on the table: the dog stops, nods, the photo lands with the sentence | `stopped at 1: looking`; rows `dog.look` (pitch), `dog.frame` (sha256), `llm.generate`, `chat.post` | stop on the map, `dog_say` in the wake sequence, post `say:<guid>:<stop>` | **built**: look, vision JSON and photo+caption post each proven live; together as a stop, needs the dog back | the sentence itself, whatever it says |
| 2.5 | Stop 2, socks on the floor: same, the sentence asks whose they are | same | same | **built** | the sentence itself |
| 2.6 | Stop 3, someone walks into frame: "yo, we don't know this guy", the living room strobes red and blue, the strip goes full | rows `chat.post`, `lights.signal` x4, `lights.tuya_set` | `person: true` from the vision JSON, `light_alarm`, `WTDD_ALARM=1` | **built**: signal proven live on one light, person flag proven on a real frame; the four-light alarm not yet seen live | "anyone it doesn't know. tonight that's anyone: recognizing housemates is not built" |
| 2.7 | "dog done" lands; the lights go dark behind it | row `chat.post`, the last `lights.set` rows to 0 | post `done:` | **proven live** | |
| 2.8 | The failure shot: whichever the trials produced (a tilt that did not fire, a light write that failed, a refused duplicate) | the red row, the honest message in the chat | | **built**; pick from the trials | "the row says what did not happen" |

## Act 3: the overlay (1:30 to 2:00)

| # | camera sees | screen shows | behind it | status | honest line |
|---|---|---|---|---|---|
| 3.1 | screen only | the remote, one screen: the map with the dot and the stops, the dog panel with the live camera, the eye (YOLO boxes on the feed, the last sentence and photo), state read back, receipts printing, the trials table | `http://127.0.0.1:7788/`, `python -m wtdd.watch` | **proven live** (map, receipts, dog panel, trials panel, detector on a real frame); the live camera and live boxes need the dog | "every button is one file; every row is one call and its read-back" |
| 3.2 | screen only | the trials table, the eval command's stdout, then the same table in the README | `python -m wtdd.evals --scenario all --write` | **built**; `twice` proven, `walk` and `look` run when the dog is back | "graded from the devices after every run. nothing typed by hand" |
| 3.3 | Last frame: the dark room, one light on, the dog sitting under it | the ledger's last line | | | "that's what the dog doin" |

Cut today, said out loud instead of faked: autonomous navigation (the driver has none; the dog is hand-driven on the drawn route), a local object detector (the vision model is the eye, its misses count as fails), face recognition (anyone in frame is a stranger).

## Filming

- Lights at 40 percent aimed at the floor and walls, never at the lens. Camera at knee height, 3/4 from the side, static for the walking shots. 30 fps, exposure locked on a lit lamp, HDR off.
- Phone B (a housemate in THE CASTLE) sends the trigger in 2.1 and is in frame for 2.2, 2.4, 2.5, 2.6, 2.7. Brightness max, chat open before the take.
- Screen recording of the remote for the whole take, microphone on, one clap on both recordings to sync.
- Before the take: `python -m wtdd.api` and `python -m wtdd.chat listen` running (logs in `/tmp/wtdd-api.log`, `/tmp/wtdd-listen.log`), the dog on its hotspot, the path and stops saved, the cup and the socks placed, nobody in frame at stops 1 and 2, someone stepping in at stop 3. `WTDD_AGENT=0` for a quiet round.
- After the last take: `python -m wtdd.evals --scenario all --write`, commit the README.
