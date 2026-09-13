# wtdd

One package, one process. Each folder is one thing to get working on its own, with a GOAL.md that states the goal, the loop, the commands, the done criteria, the verified facts, and what only Johnny can do.

| folder | thing | entry |
|---|---|---|
| `hue/` | the lights | `python -m wtdd.hue probe` |
| `dog/` | the body | `python -m wtdd.dog probe` |
| `chat/` | the ears and the mouth | `python -m wtdd.chat chats` · `python -m wtdd.chat listen` (wake phrase arms it, then commands from WTDD_COMMANDS run) · `python -m wtdd.chat triggers "<phrase>"` |
| `commands.py` | what a recognized command does: calls the real lights and dog modules, fails loud | |
| `tools/` | one file = one task (lights_on, lights_off, lights_dim, strip_set, strip_temp, strip_fade, hue_signal, zone_set, lights_status, chat_post, ledger_tail); the registry every surface uses | `python -c "from wtdd import tools; print(tools.describe())"` |
| `api.py` | local HTTP API over the tools + serves `ui/` (the React remote and the house map) | `python -m wtdd.api` then http://127.0.0.1:7788/ |
| `mcp_server.py` | MCP stdio server over the same tools | `claude mcp add wtdd -- $PWD/.venv/bin/python -m wtdd.mcp_server` |
| `tuya/` | the Tuya WT1 LED strip, local protocol 3.5 | `python -m wtdd.tuya probe` |
| `ledger.py` | receipts for all of them | `python -c "from wtdd.ledger import rows; print(rows(5))"` |
| `config.py` | .env loading, fails loud | |
| `llm.py` | the one model call path (OpenRouter, Claude), one ledger row per call | `python -c "from wtdd.llm import generate; print(generate('test',[{'role':'user','content':'ok'}])['text'])"` |

Run everything inside `.venv` (`source .venv/bin/activate`). Follow-the-body (`follow/`), watch (`watch/`), central (`central/`), evals, and the map page come after these three are green.
