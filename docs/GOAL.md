# GOAL: the demo works, and the map matches the room

The one loop to run until it is true. Read `docs/PLAN.md` for the day; this is the goal you can check in ten minutes.

## Goal

A housemate texts the group. The dog wakes, answers, plays the living room lights, and sends the picture. Free-form asks while it is awake become tool calls the model chooses. The map on the remote shows every real light where it actually is, and a dot crossing the room brightens the lights nearest to it and dims the ones it leaves. Every action has a receipt.

## Done when (check in order)

1. `python -m wtdd list` shows every tool, one file each in `wtdd/tools/`, and `python -m wtdd lights_status` reads all lights.
2. `python -m wtdd ask "dim the living room to 30 and make the strip warm"` does it with real calls and one honest sentence.
3. `python -m wtdd.chat simulate "what the dog doin"` posts (dry) the reply, runs the show, and makes the picture.
4. `python -m wtdd.chat listen` is running and a housemate's "what the dog doin" in the castle gets the reply, the show, and "this is fine" with the picture. Then "dim" and "lights on" work. Then a free-form ask works.
5. On http://127.0.0.1:7788/ every lamp and the strip sit where they are in the room, labeled by Johnny, verified by clicking each marker and watching the real light blink.
6. "run the corridor" with follow = proximity brightens the nearest lights as the dot crosses, and the ledger shows one read-back row per write.

## Software to hardware alignment (Johnny, ten minutes)

1. `python -m wtdd.api` then open http://127.0.0.1:7788/ and press "read all" so the palette lists the living room lights.
2. For each lamp: press "blink" next to its name, look at which physical lamp flashes, then "place dot" and click that spot on the map. For the strip: "draw line", click one end, click the other.
3. Drag any marker to fix it. Double-click a marker to give it your own label. Click a marker at any time to blink it again.
4. "save map". The positions and labels live in `ui/map.json`, which the proximity field reads.

## Where things are (organized by use)

| use | folder or file | how to call it |
|---|---|---|
| one task, one file | `wtdd/tools/<name>.py` | `python -m wtdd <name> key=value` |
| the model in charge | `wtdd/agent.py` | `python -m wtdd ask "..."` |
| the group chat | `wtdd/chat/` | `python -m wtdd.chat listen` |
| the lights, Hue | `wtdd/hue/` | `python -m wtdd.hue probe` |
| the lights, strip | `wtdd/tuya/` | `python -m wtdd.tuya probe` |
| the body | `wtdd/dog/` | `python -m wtdd.dog probe` |
| the remote and the map | `wtdd/api.py`, `ui/` | `python -m wtdd.api` |
| any MCP client | `wtdd/mcp_server.py` | `claude mcp add wtdd -- .venv/bin/python -m wtdd.mcp_server` |
| receipts | `ledger.jsonl` | `python -m wtdd ledger_tail n=20` |
