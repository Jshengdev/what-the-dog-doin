"""Wake phrase and command recognition. Fuzzy on purpose: housemates type fast and misspell.

Wake phrases come from WTDD_TRIGGERS, commands from WTDD_COMMANDS (comma-separated, in .env). A message wakes the dog if
a wake phrase appears in it (after normalizing case, quotes, and punctuation), or a sliding window of the message is at
least 80% similar to one, or it contains the tokens "dog" and "doin"/"doing". A command matches at 75% similarity.
"""
from __future__ import annotations
import difflib
import re

from .. import config

DEFAULT_WAKE = "what the dog doin,what the dog doing,whats the dog doing,what is the dog doing,wtdd,yo dog,hey dog"
DEFAULT_COMMANDS = "do a round,lights on,lights off,dim,bright,sit,stand,hello,look,status,stop"
WAKE_FLOOR = 0.80
COMMAND_FLOOR = 0.75


def normalize(text: str | None) -> str:
    t = (text or "").lower().replace("’", "'").replace("‘", "'").replace("'", "")
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _phrases(key: str, default: str) -> list[str]:
    return [normalize(x) for x in (config.maybe(key) or default).split(",") if normalize(x)]


def wake_phrases() -> list[str]:
    return _phrases("WTDD_TRIGGERS", DEFAULT_WAKE)


def commands() -> list[str]:
    return _phrases("WTDD_COMMANDS", DEFAULT_COMMANDS)


def best(text: str | None, phrases: list[str], floor: float, fuzzy_min_words: int = 1) -> tuple[str, float] | None:
    """(phrase, score) for the best match of any phrase inside text. Substring scores 1.0; otherwise the best
    similarity between the phrase and any window of the message with the same word count (or the whole message)."""
    t = normalize(text)
    if not t:
        return None
    words = t.split()
    hit: tuple[str, float] | None = None
    for p in phrases:
        if f" {p} " in f" {t} ":
            return (p, 1.0)
        n = len(p.split())
        if n < fuzzy_min_words:      # short phrases match exactly or not at all ("hey dog" must not fire on "the dog")
            continue
        windows = [" ".join(words[i:i + n]) for i in range(max(1, len(words) - n + 1))] + [t]
        score = max(difflib.SequenceMatcher(None, p, w).ratio() for w in windows)
        if score >= floor and (hit is None or score > hit[1]):
            hit = (p, round(score, 2))
    return hit


def is_wake(text: str | None) -> tuple[str, float] | None:
    hit = best(text, wake_phrases(), WAKE_FLOOR, fuzzy_min_words=3)
    if hit:
        return hit
    words = normalize(text).split()
    if words and words[0] == "dog":          # addressed directly: "dog, do a round", "dog sit"
        return ("dog,", 0.9)
    toks = set(words)
    if "dog" in toks and toks & {"doin", "doing", "doinn", "doinnn"}:
        return ("dog doin", WAKE_FLOOR)
    return None


def match_command(text: str | None) -> tuple[str, float] | None:
    return best(text, commands(), COMMAND_FLOOR)
