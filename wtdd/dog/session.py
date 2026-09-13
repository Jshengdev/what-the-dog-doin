"""One WebRTC session to the dog per process, shared by every tool, the API and the remote.

The dog accepts one peer at a time and keeps the slot for about ten seconds after a close, so connecting per command is
slow and collides. This module holds a single Body on a background asyncio loop; synchronous callers (tools, HTTP
handlers) submit coroutines with run(). The API process owns the dog while it runs (WTDD_API_PROCESS=1); other
processes reach the dog through the API (wtdd/commands.py) so two peers never fight for the slot. If the 20 Hz state
stream goes quiet for STALE_MS (the dog was power-cycled or left its hotspot) the next call closes the dead peer and
connects once more, logged; there is no reconnect loop.

drive() is hold-to-move: the remote refreshes a velocity every 200 ms while a key is down; the loop republishes it at
MOVE_HZ and sends StopMove 0.6 s after the last refresh or on stop(). Speeds are capped at DRIVE_MAX.

The looks, measured on this dog (firmware < 1.1.15, motion mode mcf) on 2026-09-13:
  level: BalanceStand, frame.
  tilt:  BalanceStand, Pose on, Euler y=+0.3 (nose down, +15 deg at 0.7 s), 1.6 s, Euler y=-0.3 (nose up, -15 deg from
         0.36 s to 0.79 s), frame at 0.6 s, Euler 0, Pose off. The pose is a nod, not a hold, and only fires as this
         down-then-up pair: a single cold Euler does nothing and re-sending it every 2 s does nothing.
  sit:   Sit, 1.8 s, frame at 48 deg up, RiseSit.
Frames land in ~/Pictures/wtdd/look-<kind>.jpg (the API serves them at /pictures/<name>). snapshot() is the
un-receipted newest frame behind GET /dog/frame.jpg, the remote's live view at a few frames per second.
"""
from __future__ import annotations
import asyncio
import math
import threading
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from ..ledger import log, step
from .body import MOVE_HZ, Body

PICTURES = Path("~/Pictures/wtdd").expanduser()
DRIVE_MAX = {"x": 0.4, "y": 0.4, "z": 0.6}   # m/s, m/s, rad/s for the hand-driven remote
DRIVE_HOLD_S = 0.6                            # a velocity older than this is a released key
LOOKS = ("level", "tilt", "sit")
TILT_MIN_DEG = 8.0                            # a tilt frame counts only if the IMU shows at least this much nose-up
STALE_MS = 5000                               # state stream (20 Hz) older than this: the peer is dead, reconnect once


class DogSession:
    _inst: "DogSession | None" = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> "DogSession":
        with cls._lock:
            if cls._inst is None:
                cls._inst = cls()
            return cls._inst

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, name="dog-session", daemon=True).start()
        self.body: Body | None = None
        self._connecting = asyncio.Lock()   # one connect at a time: the dog takes one peer (a frame pull and a look can race)
        self.vel = (0.0, 0.0, 0.0)
        self.vel_t = 0.0
        self.moving = False
        self._driver: asyncio.Task | None = None

    # ---- plumbing
    def run(self, coro: Awaitable[Any], timeout: float = 120.0) -> Any:
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    async def _ensure(self) -> Body:
      async with self._connecting:
        if self.body is not None:
            st = self.body.state()
            if st and st["age_ms"] > STALE_MS:   # the peer is gone (power cycle, hotspot drop): one logged reconnect, no loop
                log("dog", "WARN session stale, reconnecting once", age_ms=st["age_ms"], state_n=st["n"])
                if self._driver:
                    self._driver.cancel()
                try:
                    await asyncio.wait_for(self.body.close(), 5)
                except Exception as e:  # noqa: BLE001  (the old peer is already dead; a failed close is logged, then replaced)
                    log("dog", "old session close failed", err=f"{type(e).__name__}: {str(e)[:80]}")
                self.body = None
        if self.body is None:
            b = Body()
            await b.connect()
            self.body = b
            self._driver = self.loop.create_task(self._drive_loop())
        return self.body

    async def with_body(self, fn: Callable[[Body], Awaitable[Any]]) -> Any:
        return await fn(await self._ensure())

    def connected(self) -> bool:
        return self.body is not None

    def state(self) -> dict[str, Any]:
        st = self.body.state() if self.body else None
        return {"connected": self.body is not None, "moving": self.moving, "vel": list(self.vel), "state": st}

    def close(self) -> None:
        if self.body is not None:
            self.run(self.body.close())
            self.body = None

    # ---- commands
    def cmd(self, name: str, parameter: Any = None) -> int:
        return self.run(self.with_body(lambda b: b.cmd(name, parameter)))

    def snapshot(self) -> bytes:
        """The newest camera frame as JPEG, no ledger row (the remote's live view)."""
        return self.run(self.with_body(lambda b: b.jpeg()))[0]

    # ---- hold-to-move
    def drive(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> dict[str, Any]:
        clamp = lambda v, k: max(-DRIVE_MAX[k], min(DRIVE_MAX[k], float(v)))  # noqa: E731
        self.vel = (clamp(x, "x"), clamp(y, "y"), clamp(z, "z"))
        self.vel_t = time.monotonic()
        if self.body is None:
            self.run(self._ensure())
        return {"vel": list(self.vel), "hold_s": DRIVE_HOLD_S}

    def stop(self) -> dict[str, Any]:
        self.vel, self.vel_t = (0.0, 0.0, 0.0), 0.0
        return {"vel": [0.0, 0.0, 0.0]}

    async def _drive_loop(self) -> None:
        while True:
            try:
                fresh = time.monotonic() - self.vel_t < DRIVE_HOLD_S and any(abs(v) > 0 for v in self.vel)
                if fresh:
                    await self.body._tick("sport", *self.vel)
                    self.moving = True
                    await asyncio.sleep(1 / MOVE_HZ)
                else:
                    if self.moving:
                        await self.body.cmd("StopMove")
                        self.moving = False
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                return
            except Exception as e:  # noqa: BLE001  (logged and the loop keeps serving; the tick's own row has it)
                log("dog", "drive tick failed", err=f"{type(e).__name__}: {str(e)[:100]}")
                await asyncio.sleep(0.5)

    # ---- the looks
    def look(self, kind: str = "tilt") -> dict[str, Any]:
        if kind not in LOOKS:
            raise ValueError(f"look must be one of {LOOKS}, got {kind!r}")
        return self.run(self.with_body(lambda b: self._look(b, kind)))

    async def _look(self, b: Body, kind: str) -> dict[str, Any]:
        """The looks. The tilt nod is verified by the IMU at capture: below TILT_MIN_DEG it did not fire (this dog
        sometimes ignores the pair after a long idle, and refuses Pose with code 401001 right after driving), so the
        routine settles the controller (StopMove, BalanceStand), and on a miss warms it with StandUp and tries once
        more. The returned pitch_deg is what the IMU measured; a miss is reported as fired=False, never hidden."""
        out = PICTURES / f"look-{kind}.jpg"
        with step("dog", "dog.look", "unitree", {"kind": kind}, b.state()) as r:
            attempts, pitch = 0, 0.0
            if kind == "level":
                await b.cmd("BalanceStand"); await asyncio.sleep(0.8)
                pitch = self._pitch(b); await b.frame(out); attempts = 1
            elif kind == "sit":
                await b.cmd("Sit"); await asyncio.sleep(1.8)
                pitch = self._pitch(b); await b.frame(out); attempts = 1
                await b.cmd("RiseSit"); await asyncio.sleep(2.0)
            else:
                for attempts in (1, 2):
                    if attempts == 2:
                        log("dog", "tilt did not fire, warming with StandUp and retrying once")
                        await b.cmd("StandUp"); await asyncio.sleep(2.0)
                    await b.cmd("StopMove"); await asyncio.sleep(0.3)
                    await b.cmd("BalanceStand"); await asyncio.sleep(1.0)
                    await b.cmd("Pose", {"flag": True}); await asyncio.sleep(0.5)
                    await b.cmd("Euler", {"x": 0.0, "y": 0.3, "z": 0.0}); await asyncio.sleep(1.6)    # nod down
                    await b.cmd("Euler", {"x": 0.0, "y": -0.3, "z": 0.0}); await asyncio.sleep(0.6)   # nod up, plateau
                    pitch = self._pitch(b)
                    await b.frame(out)
                    await b.cmd("Euler", {"x": 0.0, "y": 0.0, "z": 0.0}); await asyncio.sleep(0.8)
                    await b.cmd("Pose", {"flag": False}); await asyncio.sleep(0.3)
                    if pitch <= -TILT_MIN_DEG:
                        break
            fired = kind != "tilt" or pitch <= -TILT_MIN_DEG
            res = {"text": "here's what i see", "file": str(out), "kind": kind, "pitch_deg": pitch, "fired": fired, "attempts": attempts}
            r["state_after"] = res
            log("dog", f"look {kind}", pitch=pitch, fired=fired, attempts=attempts)
            return res

    @staticmethod
    def _pitch(b: Body) -> float:
        raw = b.raw() or {}
        rpy = (raw.get("imu_state") or {}).get("rpy") or [0, 0, 0]
        return round(math.degrees(rpy[1]), 1)
