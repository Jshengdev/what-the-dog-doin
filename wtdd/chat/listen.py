"""The ears' state machine: a wake phrase arms the dog for listen_s; while armed, messages are matched against the
command list and run; "stop" disarms. Every wake, command, and ask is a ledger row (chat.wake / chat.command /
chat.ask); every post goes through __main__.post keyed on the guid of the message that caused it
(wake:/fire:/doin:/done:/ack:/res:/stop:/ai:<guid>), so a re-read message can never post twice.

Run: python -m wtdd.chat listen [--dry-run] [--every 2] [--listen-s 120] [--once]
     python -m wtdd.chat simulate "what the dog doin" "lights off" "stop"   (dry-run posts, REAL commands)

Facts. No replay at boot: the watermark starts at MAX(ROWID). WTDD_LISTEN_S (default 120) is the armed window and any
recognized message re-arms it. Who may wake the dog: any member while HOUSEMATES is empty (one WARN), else the listed
handles; from-me rows only with WTDD_ALLOW_SELF=1 (Johnny's phone shares the dog's account), and even then the dog's
own posts are refused by confirmed guid and by the opening words of its replies. WTDD_WAKE_SHOW=1 makes a wake run the
demo in Johnny's order (dog_on_fire picture, "dog doin", walk_path, "dog done") instead of a text ack. WTDD_AGENT=1
sends an armed message that is not a fixed command to wtdd.agent.ask with the chat context. A failed command is
reported to the group as its class and message, never faked. Live wake demo receipt (2026-09-13 03:0x, in
docs/RELIABILITY-BRIEF.md): "what teh dog doin" recognized at 0.94, picture 3.4 s, walk 63.6 s, 3 posts, 3 read-back
guids, 0 duplicates."""
from __future__ import annotations
import time
from typing import Any, Callable

from .. import commands as cmds
from .. import config
from ..ledger import append, log
from . import db, memory
from .housemates import HOUSEMATES, name as hname
from .triggers import commands as command_list, is_wake, match_command, wake_phrases

Poster = Callable[[str, str, str, str | None, str | None], Any]   # (guid, trigger_key, kind, text, file)
OWN_OPENERS = ("the dog is doin", "dog doin", "dog done", "on it:", "couldn't", "ok, done listening",
               "living room lights", "did:", "listening for")   # how the dog's own text posts begin


def _flag(key: str) -> bool:
    return config.maybe(key) not in (None, "0", "false", "no")


class Listener:
    def __init__(self, guid: str, post: Poster, listen_s: float = 120.0, dry_run: bool = False):
        self.guid, self.post, self.listen_s, self.dry = guid, post, listen_s, dry_run
        self.armed_until = 0.0
        self.armed_by: str | None = None
        self.last = db.max_rowid()          # no replay at boot
        self._warned = False

    @property
    def armed(self) -> bool:
        return time.time() < self.armed_until

    def allowed(self, m: dict[str, Any]) -> bool:
        if m["is_from_me"]:
            # WTDD_ALLOW_SELF=1 lets Johnny trigger from his own phone (same account as the dog). The dog's own posts are
            # still refused: by confirmed guid, and by the shape of its replies, so it can never wake itself.
            if not _flag("WTDD_ALLOW_SELF"):
                return False
            text = (m.get("text") or "").lower()
            return not (m["guid"] in memory.posted_guids() or text.startswith(OWN_OPENERS))
        if not HOUSEMATES:
            if not self._warned:
                log("chat", "WARN HOUSEMATES is empty: any member of the group may wake the dog")
                self._warned = True
            return True
        return m["sender"] in HOUSEMATES

    def say(self, key: str, text: str | None, file: str | None = None) -> None:
        if self.dry:
            log("chat", f"DRY would post [{key}]: {text}", file=file or "")
            return
        self.post(self.guid, key, "listen", text, file)

    def _event(self, tool: str, m: dict[str, Any], **extra: Any) -> None:
        append({"step": tool, "agent": "central", "tool": tool, "app": "imessage", "ok": True,
                "args": {"from": m["sender"], "text": (m["text"] or "")[:200], "guid": m["guid"], **extra},
                "state_before": None, "state_after": {"armed": self.armed, "armed_by": self.armed_by},
                "response_or_error": None, "latency_ms": 0})

    def wake_show(self, m: dict[str, Any]) -> None:
        """The wake demo, in Johnny's order: the picture, then "dog doin" as the walk starts, the walk (the same one the
        remote's button runs), then "dog done". Each part is a tool call and a gated post keyed on the wake message."""
        from .. import tools
        try:
            pic = tools.call("dog_on_fire")
            self.say(f"fire:{m['guid']}", None, pic["file"])
        except Exception as e:  # noqa: BLE001
            self.say(f"fire:{m['guid']}", f"couldn't make the picture: {type(e).__name__}: {str(e)[:100]}")
        self.say(f"doin:{m['guid']}", "dog doin")
        try:
            out = tools.call("walk_path")
            log("chat", "walked", seconds=out["seconds"], writes=out["writes"], errors=out["errors"], rooms=",".join(out["rooms"]))
            self.say(f"done:{m['guid']}", "dog done" + (f" ({out['errors']} light write(s) failed, see the ledger)" if out.get("errors") else ""))
        except Exception as e:  # noqa: BLE001
            self.say(f"done:{m['guid']}", f"dog done, but couldn't walk the path: {type(e).__name__}: {str(e)[:100]}")

    def handle(self, m: dict[str, Any]) -> None:
        text = m["text"]
        if not text or not self.allowed(m):
            return
        wake = is_wake(text)
        if not self.armed:
            if not wake:
                return
            self.armed_until = time.time() + self.listen_s
            self.armed_by = m["sender"]
            log("chat", "WAKE", by=hname(m["sender"]), phrase=wake[0], score=wake[1])
            self._event("chat.wake", m, phrase=wake[0], score=wake[1])
            if _flag("WTDD_WAKE_SHOW"):
                self.wake_show(m)
            else:
                self.say(f"wake:{m['guid']}", f"the dog is doin. listening for {int(self.listen_s)}s: {' · '.join(command_list())}")
            return
        hit = match_command(text)
        if not hit:
            if wake:
                self.armed_until = time.time() + self.listen_s
                return
            if not _flag("WTDD_AGENT"):
                log("chat", "armed, no command in message", by=hname(m["sender"]), chars=len(text))
                return
            # the model takes charge: a free-form ask while armed becomes tool calls over the registry
            from ..agent import ask
            self._event("chat.ask", m)
            self.armed_until = time.time() + self.listen_s
            try:
                out = ask(text, context=memory.context(self.guid))
                self.say(f"ai:{m['guid']}", out["text"][:300] or f"did: {', '.join(c['tool'] for c in out['calls']) or 'nothing'}")
            except Exception as e:  # noqa: BLE001
                self.say(f"ai:{m['guid']}", f"couldn't: {type(e).__name__}: {str(e)[:120]}")
            return
        cmd, score = hit
        log("chat", "COMMAND", by=hname(m["sender"]), command=cmd, score=score)
        self._event("chat.command", m, command=cmd, score=score)
        if cmd == "stop":
            self.armed_until = 0.0
            self.armed_by = None
            self.say(f"stop:{m['guid']}", "ok, done listening")
            return
        self.armed_until = time.time() + self.listen_s
        self.say(f"ack:{m['guid']}", f"on it: {cmd}")
        try:
            out = cmds.run(cmd)
        except Exception as e:  # noqa: BLE001  (reported truthfully to the group; the ledger row already has it)
            self.say(f"res:{m['guid']}", f"couldn't {cmd}: {type(e).__name__}: {str(e)[:120]}")
            return
        if isinstance(out, dict):
            self.say(f"res:{m['guid']}", out.get("text"), out.get("file"))
        else:
            self.say(f"res:{m['guid']}", str(out)[:300])

    def poll(self) -> int:
        if self.armed_by and not self.armed:
            log("chat", "disarmed (timeout)", was=hname(self.armed_by))
            self.armed_by = None
        msgs = db.new_messages(self.guid, self.last)
        if not msgs:
            return 0
        memory.store(self.guid, msgs)
        self.last = msgs[-1]["rowid"]
        for m in msgs:
            self.handle(m)
        return len(msgs)

    def run(self, every: float = 2.0, once: bool = False) -> None:
        log("chat", f"listen guid={self.guid}", from_rowid=self.last, listen_s=self.listen_s, dry=self.dry,
            wake_phrases=len(wake_phrases()), commands=len(command_list()))
        while True:
            self.poll()
            if once:
                break
            time.sleep(every)
