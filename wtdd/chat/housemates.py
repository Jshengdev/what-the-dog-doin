"""Who the dog listens to, and the phrases it answers."""
from __future__ import annotations

# Johnny: fill this in. Keys are handles exactly as chat.db stores them (E.164 phone like "+13105551234", or an email),
# values are first names. Get the handles from `python -m wtdd.chat chats` and the sender column of `watch`.
# Unknown senders render as their handle in the context and never trigger a reply.
HOUSEMATES: dict[str, str] = {}

from .triggers import is_wake


def name(handle: str) -> str:
    return HOUSEMATES.get(handle, handle)


def is_trigger(text: str | None) -> bool:
    """A message that wakes the dog (see triggers.py)."""
    return is_wake(text) is not None
