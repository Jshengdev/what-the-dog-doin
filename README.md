# what-the-dog-doin

A robot dog that does rounds of a shared house. Text the group, the dog answers, the lights follow it room by room, it looks and says what it saw. Every action has a receipt.

Built for the Multi-App AI Agent Hackathon (Lemma and Comma Capital), Sunday 2026-09-13. The brief: one useful multi-step agent, at least three external apps, show how you know it works. The apps: a Unitree Go2 (WebRTC over Wi-Fi), Philips Hue (cloud route) and a Tuya LED strip (local protocol 3.5), and the housemates' iMessage group (this Mac's own account).

## Run it

```bash
source .venv/bin/activate          # python 3.13; pip install -r requirements.txt; cp .env.example .env and fill it
python -m wtdd.api                 # the remote and the house map: http://127.0.0.1:7788/  (this process owns the dog)
python -m wtdd.chat listen         # the group chat: "what the dog doin" wakes it
python -m wtdd list                # every tool, one file each; python -m wtdd <tool> key=value runs one
python -m wtdd ask "dim the living room and make the strip warm"   # the model picks the tools
```

## Where things are

| use | where | entry |
|---|---|---|
| one task, one file | `wtdd/tools/` | `python -m wtdd <name> k=v`, `POST /tools/<name>`, MCP |
| the model in charge | `wtdd/agent.py` | `python -m wtdd ask "..."` |
| the group chat: read, gate, never twice, wake demo | `wtdd/chat/` | `python -m wtdd.chat listen` |
| the body: one shared WebRTC session, drive, looks | `wtdd/dog/` | `python -m wtdd.dog probe`, the remote's dog panel |
| the lights, Hue | `wtdd/hue/` | `python -m wtdd.hue probe` |
| the lights, strip | `wtdd/tuya/` | `python -m wtdd.tuya probe` |
| the field: an entity walks the map, lights follow | `wtdd/field.py` | `python -m wtdd walk_path` |
| the remote and the map | `wtdd/api.py`, `ui/` | `python -m wtdd.api` |
| any MCP client | `wtdd/mcp_server.py` | `claude mcp add wtdd -- $PWD/.venv/bin/python -m wtdd.mcp_server` |
| receipts | `ledger.jsonl` (gitignored) | `python -m wtdd ledger_tail n=20` |
| the submission | `docs/RELIABILITY-BRIEF.md`, `docs/DEMO-SCRIPT.md` | |

What each file does, how to run it, and the facts measured on the real devices live in that file's docstring. The research and planning docs from the build night were removed from the tree on 2026-09-13; `git show df77344:docs/` has them.

## How we know it works

Every write reads its result back and lands as one row in `ledger.jsonl`; every number in the brief regenerates from a command. The measured runs so far are in `docs/RELIABILITY-BRIEF.md`.

## Team

Johnny Sheng ([@Jshengdev](https://github.com/Jshengdev))
