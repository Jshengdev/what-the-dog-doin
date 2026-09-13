# wtdd

One package, one process. Each folder is one thing to get working on its own, with a GOAL.md that states the goal, the loop, the commands, the done criteria, the verified facts, and what only Johnny can do.

| folder | thing | entry |
|---|---|---|
| `hue/` | the lights | `python -m wtdd.hue probe` |
| `dog/` | the body | `python -m wtdd.dog probe` |
| `chat/` | the ears and the mouth | `python -m wtdd.chat chats` · `python -m wtdd.chat listen` (wake phrase arms it, then commands from WTDD_COMMANDS run) · `python -m wtdd.chat triggers "<phrase>"` |
| `commands.py` | what a recognized command does: calls the real lights and dog modules, fails loud | |
| `ledger.py` | receipts for all of them | `python -c "from wtdd.ledger import rows; print(rows(5))"` |
| `config.py` | .env loading, fails loud | |
| `llm.py` | the one model call path (OpenRouter, Claude), one ledger row per call | `python -c "from wtdd.llm import generate; print(generate('test',[{'role':'user','content':'ok'}])['text'])"` |

Run everything inside `.venv` (`source .venv/bin/activate`). Follow-the-body (`follow/`), watch (`watch/`), central (`central/`), evals, and the map page come after these three are green.
