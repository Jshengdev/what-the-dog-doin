# CHAT: the iMessage transport and the conversation memory

The group chat is where the housemates talk to the house and where the dog reports. This is the design for `wtdd/chat.py` and `wtdd/memory.py`, informed by reading the earlier iMessage products in `~/code/doubles` and `~/code/icarus` (read-only, 2026-09-13). Everything here runs on Johnny's own Mac Messages account. No vendor, no server, no provisioned number.

## The transport decision

- **The old provisioned line is gone.** The Photon-hosted instance that doubles and Juno shared answers 404 to an authenticated request with the stored key. It was a different number that was never in the group, it needed Node and a hosted server, and its own handoff docs record reconnect cycles. Dead end.
- **The free Node kit rejects this Mac's group id.** Group chats on this Mac (macOS 26) have `chat.guid = any;+;<32 hex>`; the kit's validator only accepts `iMessage;+;chat...`. It also does not confirm a send landed.
- **So: stdlib only.** Read the Messages database with `sqlite3` (read-only URI), send with `osascript` via `subprocess.run` (list form, no shell), and confirm every post by reading the dog's own `is_from_me = 1` row back. The read-back is the receipt the ledger wants.

Prerequisites: Full Disk Access for the terminal (granted, verified by reading chat.db), Messages.app running and signed in, and the Automation permission prompt for Terminal/Python answered once. Do that before the demo with a read-only call:

```bash
osascript -e 'tell application "Messages" to get id of every chat' | tr ',' '\n' | grep -c 'any;+;'
```

UNVERIFIED until that runs: that AppleScript's `chat id` accepts the `any;+;` prefix. If it does not, the fallback is `send "..." to chat "wtdd test"` by display name (also UNVERIFIED).

## Reading the group

Find the chat once (read-only) and keep the guid in `.env` as `WTDD_CHAT_GUID`:

```sql
SELECT guid, chat_identifier, style FROM chat WHERE display_name = 'wtdd test';
```

Poll every 2 seconds for rows above a ROWID watermark. Never replay history: at boot set `last_rowid = MAX(message.ROWID)`.

```sql
SELECT m.ROWID, m.guid, m.text, m.attributedBody, m.is_from_me,
       m.associated_message_type, m.cache_has_attachments,
       COALESCE(h.id, '') AS sender,
       datetime(m.date / 1000000000 + 978307200, 'unixepoch') AS ts_utc,
       (SELECT group_concat(a.filename, '|')
          FROM message_attachment_join maj JOIN attachment a ON a.ROWID = maj.attachment_id
         WHERE maj.message_id = m.ROWID) AS attachments
FROM message m
JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
JOIN chat c ON c.ROWID = cmj.chat_id
LEFT JOIN handle h ON h.ROWID = m.handle_id
WHERE c.guid = ? AND m.ROWID > ?
ORDER BY m.ROWID ASC;
```

Rules on each row:
- `associated_message_type != 0` is a tapback (2000 to 2005 add, 3000 to 3005 remove). Store nothing, never feed it to the model.
- `is_from_me = 1` is the dog's own post echoing back. Store it (it is memory) and use it as the send confirmation. Never treat it as a trigger.
- `text` can be NULL with the content inside `attributedBody` (typedstream). For the demo filter `text IS NOT NULL`; a NULL-text row is logged as `[non-text]`.
- Attachment paths start with `~/Library/Messages/Attachments/`; expand `~`.
- `message.date` is nanoseconds since 2001-01-01; `date / 1e9 + 978307200` is unix seconds.
- Open with `sqlite3.connect("file:" + path + "?mode=ro", uri=True)`.

Trigger gate: the dog answers only messages that contain a trigger phrase (`what the dog doin`, `dog,`, `run daily checks`, `do a round`) from a sender in `HOUSEMATES`. Everything else is stored and ignored. A 2 second debounce on the trigger sender folds multi-bubble asks into one.

## Sending to the group

Text (shape verified against the kit's generated AppleScript; escape `\` and `"` in the text):

```applescript
tell application "Messages"
    set targetChat to chat id "any;+;<32 hex>"
    send "what the dog doin: starting the round" to targetChat
end tell
```

Image file (the file must live under `~/Pictures`, `~/Downloads`, or `~/Documents`, or sandboxed Messages cannot read it; write frames to `~/Pictures/wtdd/`; wait 3 seconds after send):

```applescript
tell application "Messages"
    set targetChat to chat id "any;+;<32 hex>"
    set theFile to (POSIX file "/Users/johnnysheng/Pictures/wtdd/frame-<id>.jpg") as alias
    send theFile to targetChat
    delay 3
end tell
```

Run: `subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)`. A non-zero return code is a failed step, recorded on that step, never retried automatically (real housemates on the other end).

## Never twice: the gate table

```sql
CREATE TABLE IF NOT EXISTS posts(
  trigger_guid TEXT PRIMARY KEY,
  claimed_at   TEXT NOT NULL,
  posted_guid  TEXT UNIQUE,
  confirmed_at TEXT);
```

1. `INSERT INTO posts(trigger_guid, claimed_at)` BEFORE calling osascript. A primary-key conflict means already posted or in flight: return without sending.
2. After osascript, poll chat.db for up to 10 seconds for a row with `is_from_me = 1 AND ROWID > watermark AND text = ?` in the same chat. Write `posted_guid` and `confirmed_at`. That row is the `chat.post` ledger receipt: `{guid, ts}`.
3. A claim with no confirmation is a ledger error row, not a retry.

Unsafe, in the judges' grading sense, is any post without a claim row or any second post for one trigger. The eval asserts both from this table and from chat.db.

## Memory: two tables, one rule

The rule: the messages are the source of truth and context is computed from them each turn. No separate conversation log, no summaries, no embeddings.

```sql
CREATE TABLE IF NOT EXISTS chat_messages(
  rowid INTEGER PRIMARY KEY, guid TEXT UNIQUE NOT NULL, sender TEXT NOT NULL,
  is_from_me INTEGER NOT NULL, text TEXT, attachments_json TEXT NOT NULL DEFAULT '[]',
  ts_utc TEXT NOT NULL, seen_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_chat_ts ON chat_messages(ts_utc DESC);
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT NOT NULL);   -- last_rowid
```

`memory.db` sits next to `ledger.jsonl`. Dog actions and reports are NOT duplicated into memory; they are read from the ledger.

Context the central agent composes on every turn:
1. The last 20 `chat_messages`, oldest first, rendered `[HH:MM] <name>: <text>` with `[photo]` per attachment. Names come from a hand-written `HOUSEMATES = {"+1...": "Name"}` dict; from-me rows render as `dog:`.
2. The last 10 `ledger.jsonl` rows where `tool != "llm.generate"`: step, tool, args, state_after, ok. That is "what the dog did."
3. The last ledger row with `step == "report"` and the last `posts` row. That is "what was reported."
4. `state.json`: zone, position, lights.

Twenty rows is the window the earlier products settled on (16 to 20). Raise it if a run outgrows it; nothing else changes.

## What is deliberately not here

Hosted transports, input batchers, per-user rate limiters, RRF or embedding recall, silence-gap summarization, a mock mode on connect failure, and any `except: return []`. The earlier products needed the first four for one-to-one conversations at scale; this is one group, one trigger phrase, one post per trigger. The last two are the fallbacks `CLAUDE.md` §2 forbids.

## Research references (read-only)

`~/code/doubles/src/spectrum/imessage.ts` (guid dedupe, from-me skip) · `~/code/doubles/src/conversation/tapback.ts` (tapback codes) · `~/code/doubles/src/agents/context-builder.ts` and `~/code/icarus/src/memory/queries.ts` (the history window) · `~/code/icarus/src/core/juno-active/episodic-memory.ts` (the asked / did / said shape) · `~/code/icarus/node_modules/@photon-ai/imessage-kit/dist/index.js` (the AppleScript and SQL shapes, lines 611 to 1348) · `~/code/doubles/docs/juno-extraction-manifest.md` §"Conversation-as-Database".
