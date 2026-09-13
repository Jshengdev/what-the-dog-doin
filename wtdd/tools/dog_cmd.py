"""Send one predefined sport command to the dog (Sit, RiseSit, StandUp, StandDown, Hello, Stretch), state read back."""
NAME, DOC = "dog_cmd", __doc__.strip()
ARGS = {"name": {"type": "string", "default": "Hello"}}


def run(name="Hello"):
    from ..commands import dog_cmd
    return {"result": dog_cmd(name)}
