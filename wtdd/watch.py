"""The eye's second opinion: an open-source detector (ultralytics YOLO11n, COCO's 80 classes, Apache-2.0 weights) in
its own process over the dog's live frames. It pulls GET /dog/frame.jpg from the API at --hz, draws the boxes into
~/Pictures/wtdd/watch.jpg (the API serves it at /pictures/watch.jpg) and writes the counts and boxes to <repo>/watch.json
(GET /watch); the remote shows both. One watch.detect ledger row whenever the set of classes in view changes (a cup
appears, a person walks in); frames themselves are not rows.

  python -m wtdd.watch                              live from the API, 4 frames a second
  python -m wtdd.watch --source ~/Pictures/wtdd/dog-live.jpg --once     one file, prints the detections

Facts. cv2 lives here and never in the API process (its ffmpeg clashes with PyAV's). COCO names cup, bowl, bottle,
wine glass, chair, couch, person, backpack, handbag, suitcase, laptop, cell phone, book ... and does NOT name socks,
clothes or "out of place": the vision model in wtdd/tools/dog_say.py names those, and its trials count the misses. The
detector is observability and a receipt, not a gate: nothing in the round acts on it. First run downloads yolo11n.pt
(about 5 MB) next to the working directory. The API adds age_ms to /watch so the page hides stale boxes."""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

from .config import ROOT
from .ledger import append, log

WATCH = ROOT / "watch.json"
OUT = Path("~/Pictures/wtdd/watch.jpg").expanduser()
MODEL = "yolo11n.pt"
CONF = 0.35
API = "http://127.0.0.1:7788"


def detect(model, img: bytes) -> tuple[list[dict], object, int]:
    import cv2
    import numpy as np
    arr = cv2.imdecode(np.frombuffer(img, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        raise ValueError(f"not a decodable image ({len(img)} bytes)")
    t0 = time.perf_counter()
    r = model.predict(arr, conf=CONF, verbose=False)[0]
    ms = round((time.perf_counter() - t0) * 1000)
    boxes = [{"name": r.names[int(c)], "conf": round(float(p), 2), "xyxy": [round(float(v)) for v in b]}
             for c, p, b in zip(r.boxes.cls.tolist(), r.boxes.conf.tolist(), r.boxes.xyxy.tolist())]
    return boxes, r.plot(), ms


def publish(boxes: list[dict], plotted, ms: int, source: str) -> dict:
    import cv2
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_name("watch.tmp.jpg")
    cv2.imwrite(str(tmp), plotted, [cv2.IMWRITE_JPEG_QUALITY, 75])
    os.replace(tmp, OUT)
    classes: dict[str, int] = {}
    for b in boxes:
        classes[b["name"]] = classes.get(b["name"], 0) + 1
    d = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "t": time.time(), "ms": ms, "n": len(boxes), "classes": classes,
         "boxes": boxes, "source": source, "model": MODEL}
    tmpj = WATCH.with_suffix(".tmp")
    tmpj.write_text(json.dumps(d))
    os.replace(tmpj, WATCH)
    return d


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m wtdd.watch")
    p.add_argument("--source", default=f"{API}/dog/frame.jpg", help="a URL (default: the API's live frame) or an image file")
    p.add_argument("--hz", type=float, default=4.0)
    p.add_argument("--once", action="store_true")
    a = p.parse_args(argv)
    from ultralytics import YOLO
    t0 = time.perf_counter()
    model = YOLO(MODEL)
    log("watch", f"model {MODEL} loaded", ms=round((time.perf_counter() - t0) * 1000), conf=CONF, source=a.source)
    is_url = a.source.startswith("http")
    last: set[str] | None = None
    n = warned = 0
    while True:
        try:
            if is_url:
                import requests
                r = requests.get(a.source, timeout=5)
                if r.status_code != 200:
                    raise RuntimeError(f"{a.source} -> {r.status_code}: {r.text[:80]}")
                img = r.content
            else:
                img = Path(a.source).expanduser().read_bytes()
            boxes, plotted, ms = detect(model, img)
            d = publish(boxes, plotted, ms, a.source)
            n += 1
            warned = 0
            now = set(d["classes"])
            if now != last:
                append({"step": "watch.detect", "agent": "watch", "tool": "watch.detect", "app": "yolo", "ok": True,
                        "args": {"source": a.source, "model": MODEL, "conf": CONF},
                        "state_before": sorted(last) if last is not None else None,
                        "state_after": {"classes": d["classes"], "n": d["n"]},
                        "response_or_error": boxes[:12], "latency_ms": ms})
                log("watch", f"in view: {', '.join(f'{k} x{v}' for k, v in d['classes'].items()) or 'nothing'}", ms=ms, frame=n)
                last = now
            elif n % 40 == 0:
                log("watch", f"frame {n}", n_boxes=d["n"], ms=ms)
        except Exception as e:  # noqa: BLE001  (no dog, stale video, a bad frame: logged, then try again; never a fake box)
            if warned == 0:
                log("watch", f"WARN no detection: {type(e).__name__}: {str(e)[:100]}")
            warned += 1
            if a.once:
                return 1
            time.sleep(2)
            continue
        if a.once:
            print(json.dumps({k: d[k] for k in ("ts", "ms", "n", "classes", "boxes")}, indent=1))
            return 0
        time.sleep(max(0.0, 1 / a.hz))


if __name__ == "__main__":
    sys.exit(main())
