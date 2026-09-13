"""Run the scripted corridor route on the dog (wtdd/dog/routes/corridor.json) with obstacle avoidance on."""
NAME, DOC = "dog_round", __doc__.strip()
ARGS = {}


def run():
    from ..commands import do_round
    return {"result": do_round()}
