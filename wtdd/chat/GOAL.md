# GOAL: the mouth and the ears (iMessage on Johnny's own account)

**Goal.** From this Mac's own Messages account: read new messages from one group chat (sender, text, attachments), answer only trigger phrases from known housemates, send text, send a photo, send an "update" (one line), and send a bounded burst ("spam": N messages spaced S seconds, capped), each confirmed by reading the dog's own from-me row back, never twice per trigger. Conversation memory per `docs/CHAT.md`. Every send writes a ledger row with the confirmed guid.

**Loop.** Build `wtdd/chat/__main__.py` so `python -m wtdd.chat <cmd>` works, run `chats` and `watch` (read-only, live now), then the send commands against the TEST group only, fix, repeat until done.

**Commands.** `chats` (named chats with guid, members, last message time; read-only) · `watch [--guid G]` (poll by ROWID, print new rows with sender and attachments, skip tapbacks, store into memory.db) · `send --guid G --text "..."` · `photo --guid G --file path.jpg [--text "..."]` · `update --guid G --text "..."` (same as send, tagged update) · `spam --guid G --n 5 --every 2 --text "..."` (bounded burst; each message distinct with an index; cap n at 10) · `reply --guid G` (one turn: read the last trigger, compose a reply with the memory context and the Claude API via `anthropic`, send behind the gate) · `context --guid G` (print the composed context).

**Done when.** `chats` lists the groups; `watch` shows a live message arriving with its sender; `send`, `photo`, `update`, `spam` each land in the TEST group and their ledger rows carry the read-back guid; a second `send` for the same trigger is refused by the gate; `reply` answers a trigger phrase with memory context.

**Facts (verified on this Mac tonight).** chat.db is readable (Full Disk Access granted). Group chat guids have the form `any;+;<32 hex>`; AppleScript `get id of every chat` returns exactly those ids (verified 00:45, Automation permission already granted to the terminal). `THE CASTLE` is the real housemates group: NEVER send to it. The exact SQL, AppleScript (text and POSIX file under ~/Pictures), epoch conversion, gate table, and memory tables are in `docs/CHAT.md`; use them verbatim. `text` can be NULL with content in `attributedBody`; log those as `[non-text]`.

**Johnny must do (prompt him).** 1) Create a group chat named exactly `wtdd test` with himself and one housemate, send one message in it, then run `python -m wtdd.chat chats` to get its guid and put it in .env as WTDD_CHAT_GUID. Until that group exists, do not send anything anywhere; build and test reading only. 2) Fill `HOUSEMATES` (handle to name) in `wtdd/chat/housemates.py` from the `chats` output. 3) Nothing for the model: OPENROUTER_API_KEY is already in .env and `wtdd/llm.py` is the one call path.

**Never.** No sends to any chat other than WTDD_CHAT_GUID; no retries of an unconfirmed send; no replaying history at boot; no git commit.
