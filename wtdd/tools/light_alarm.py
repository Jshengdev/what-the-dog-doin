"""The alarm: every colour Hue light in the living room flashes red and blue (the native alternating signal) for N
seconds and the strip goes to 100 percent, all at once, each read back. A light that refuses the signal is counted in
errors and reported, never retried; the tool raises only when nothing answered. The chat's wake sequence sounds it when
the look finds a person in frame (anyone in frame is a stranger tonight: recognizing housemates is not built)."""
ARGS = {"seconds": {"type": "number", "default": 8}}


def run(seconds=8):
    import json
    from concurrent.futures import ThreadPoolExecutor
    from ..hue.api import HueBridge
    from ..hue.__main__ import ZONES
    from ..ledger import log
    from ..tuya.__main__ import strip
    ids = json.loads(ZONES.read_text())["living room"]["lights"]
    names = {l["id"]: l["metadata"]["name"] for l in HueBridge.from_env().lights()}
    done, errors = [], []
    with ThreadPoolExecutor(max_workers=len(ids) + 1) as pool:
        futs = {rid: pool.submit(lambda rid=rid: HueBridge.from_env().signal(rid, float(seconds))) for rid in ids}
        st = pool.submit(strip, on=True, bri=100.0)
        for rid, f in futs.items():
            try:
                f.result()
                done.append(names.get(rid, rid[:8]))
            except Exception as e:  # noqa: BLE001  (its own ledger row has ok=False; counted here, not hidden)
                errors.append(f"{names.get(rid, rid[:8])}: {type(e).__name__}: {str(e)[:60]}")
        try:
            s = st.result()
            done.append(f"strip {s.get('brightness_pct')}%")
        except Exception as e:  # noqa: BLE001
            errors.append(f"strip: {type(e).__name__}: {str(e)[:60]}")
    log("lights", "alarm", signaled=len(done), errors=len(errors))
    if not done:
        raise RuntimeError(f"alarm: nothing answered: {'; '.join(errors)}")
    return {"signaled": done, "errors": errors, "seconds": seconds}
