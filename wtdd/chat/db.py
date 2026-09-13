"""The ears: a read-only view of ~/Library/Messages/chat.db. SQL and epoch conversion verbatim from docs/CHAT.md."""
from __future__ import annotations
import os
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ..ledger import log

CHAT_DB = Path("~/Library/Messages/chat.db").expanduser()

# docs/CHAT.md "Reading the group", verbatim.
NEW_MESSAGES_SQL = """
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
ORDER BY m.ROWID ASC
"""

CHATS_SQL = """
SELECT c.guid, c.display_name AS name,
       (SELECT COUNT(*) FROM chat_handle_join chj WHERE chj.chat_id = c.ROWID) AS members,
       (SELECT datetime(MAX(m.date) / 1000000000 + 978307200, 'unixepoch')
          FROM message m JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
         WHERE cmj.chat_id = c.ROWID) AS last_ts
FROM chat c
WHERE c.display_name IS NOT NULL AND c.display_name != ''
ORDER BY last_ts DESC
"""

# The dog's own echo. text = ? for a text send; cache_has_attachments = 1 for a file send (from-me file rows have text NULL).
FROM_ME_SQL = """
SELECT m.ROWID, m.guid, datetime(m.date / 1000000000 + 978307200, 'unixepoch') AS ts_utc
FROM message m
JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
JOIN chat c ON c.ROWID = cmj.chat_id
WHERE c.guid = ? AND m.ROWID > ? AND m.is_from_me = 1 AND {cond}
ORDER BY m.ROWID ASC LIMIT 1
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect("file:" + str(CHAT_DB) + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        yield c
    finally:
        c.close()


def chats() -> list[dict[str, Any]]:
    """Every named chat: guid, name, member count, last message time (UTC)."""
    with connect() as c:
        return [dict(r) for r in c.execute(CHATS_SQL)]


def chat_name(guid: str) -> str | None:
    with connect() as c:
        r = c.execute("SELECT display_name FROM chat WHERE guid = ?", (guid,)).fetchone()
    return r["display_name"] if r else None


def max_rowid() -> int:
    with connect() as c:
        r = c.execute("SELECT MAX(ROWID) AS m FROM message").fetchone()
    return int(r["m"] or 0)


def attributed_text(blob: bytes | None) -> str | None:
    """Plain text out of a typedstream attributedBody (macOS stores some messages with text NULL).
    Layout after the NSString marker: 5 bytes, then a 1-byte length (or 0x81 + 2-byte little-endian length), then UTF-8.
    Returns None when the blob does not follow that shape; the caller logs [non-text]."""
    if not blob:
        return None
    i = blob.find(b"NSString")
    if i < 0:
        return None
    j = i + len(b"NSString") + 5
    if j >= len(blob):
        return None
    n = blob[j]
    j += 1
    if n == 0x81:
        n = int.from_bytes(blob[j:j + 2], "little")
        j += 2
    out = blob[j:j + n].decode("utf-8", errors="replace").replace("\ufffc", "").strip()   # U+FFFC = attachment placeholder
    return out or None


def new_messages(guid: str, after_rowid: int) -> list[dict[str, Any]]:
    """Rows above the watermark, oldest first. Tapbacks dropped. NULL text stays None (logged as [non-text] by the caller)."""
    t0 = time.perf_counter()
    out: list[dict[str, Any]] = []
    tapbacks = 0
    with connect() as c:
        for r in c.execute(NEW_MESSAGES_SQL, (guid, after_rowid)):
            if r["associated_message_type"] != 0:
                tapbacks += 1
                continue
            files = [os.path.expanduser(p) for p in (r["attachments"] or "").split("|") if p]
            out.append({
                "rowid": r["ROWID"], "guid": r["guid"],
                "text": r["text"] if r["text"] is not None else attributed_text(r["attributedBody"]),
                "is_from_me": int(r["is_from_me"]), "sender": r["sender"], "ts_utc": r["ts_utc"],
                "attachments": files, "has_attachments": int(r["cache_has_attachments"] or 0),
            })
    if out or tapbacks:
        log("chat", f"new_messages n={len(out)}", tapbacks=tapbacks,
            nontext=sum(1 for m in out if m["text"] is None), after=after_rowid,
            ms=round((time.perf_counter() - t0) * 1000))
    return out


def find_from_me(guid: str, after_rowid: int, text: str | None, timeout_s: float = 10.0) -> dict[str, Any] | None:
    """Polls for the dog's own from-me row above the watermark: text match, or (text None) an attachment row.
    Returns {guid, rowid, ts} or None. The caller treats None as a failed step; nothing here retries the send."""
    t0 = time.perf_counter()
    if text is None:
        sql, params = FROM_ME_SQL.format(cond="m.cache_has_attachments = 1"), (guid, after_rowid)
    else:
        # wtdd: on macOS 26 outgoing text lands in attributedBody with text NULL, so match either column
        sql, params = FROM_ME_SQL.format(cond="(m.text = ? OR instr(cast(m.attributedBody as text), ?) > 0)"), (guid, after_rowid, text, text)
    deadline = t0 + timeout_s
    while True:
        with connect() as c:
            r = c.execute(sql, params).fetchone()
        if r:
            row = {"guid": r["guid"], "rowid": r["ROWID"], "ts": r["ts_utc"]}
            log("chat", "confirmed from-me row", rowid=row["rowid"], ms=round((time.perf_counter() - t0) * 1000))
            return row
        if time.perf_counter() > deadline:
            log("chat", "WARN no from-me row", guid=guid, after=after_rowid,
                text=(text[:40] if text else "[file]"), ms=round((time.perf_counter() - t0) * 1000))
            return None
        time.sleep(0.5)
