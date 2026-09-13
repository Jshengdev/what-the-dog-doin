"""Capture a frame from the dog camera to ~/Pictures/wtdd/look.jpg; returns text and the file path."""
NAME, DOC = "dog_look", __doc__.strip()
ARGS = {}


def run():
    from ..commands import look
    return look()
