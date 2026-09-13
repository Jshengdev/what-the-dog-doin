"""HueBridge: CLIP v2 over HTTPS on the LAN. Every network call runs inside wtdd.ledger.step and every PUT is
followed by a GET read-back that lands in state_after. Request shapes: docs/SETUP.md section 2a and the openhue
OpenAPI mirror (src/light/schemas/LightPut.yaml, src/common/Signaling.yaml, src/auth/auth.yaml).
"""
from __future__ import annotations
import json
import socket
import time
from typing import Any

import requests
import urllib3

from .. import ledger

AGENT, APP = "lights", "hue"
DISCOVERY_URL = "https://discovery.meethue.com/"
RED_XY, BLUE_XY = (0.675, 0.322), (0.167, 0.04)
# Hue guidance (SETUP.md 2a.5): about 10 light commands per second, 1 grouped_light per second.
PUT_GAP_S = {"light": 0.1, "grouped_light": 1.0}


def raw(x: Any) -> str:
    """response_or_error is stored as a compact JSON string: it is the raw response, never a summary, and
    wtdd.ledger.step slices it for the log line (a dict there raises KeyError inside the step's finally)."""
    return json.dumps(x, separators=(",", ":"), default=str)


class HueError(RuntimeError):
    def __init__(self, msg: str, status: int | None = None):
        super().__init__(msg)
        self.status = status


def discover() -> list[dict[str, Any]]:
    """Cloud discovery: [{"id", "internalipaddress", "port"}]. One row."""
    with ledger.step(AGENT, "lights.discover", APP, {"url": DISCOVERY_URL}) as r:
        resp = requests.get(DISCOVERY_URL, timeout=5)
        r["response_or_error"] = raw({"status": resp.status_code, "body": resp.text})
        if resp.status_code != 200:
            raise HueError(f"discovery HTTP {resp.status_code}", resp.status_code)
        bridges = resp.json()
        if not bridges:
            ledger.log(AGENT, "WARN discovery returned zero bridges")
        r["state_after"] = bridges
        return bridges


def tcp_open(ip: str, port: int = 443, timeout: float = 3.0) -> float:
    """Raw TCP connect to `host` or `host:port`; returns connect time in ms or raises. One row."""
    host, _, p = ip.partition(":")
    port = int(p) if p else port
    with ledger.step(AGENT, "lights.tcp", APP, {"ip": host, "port": port}) as r:
        t0 = time.perf_counter()
        try:
            socket.create_connection((host, port), timeout=timeout).close()
        except OSError as e:
            raise HueError(f"tcp {host}:{port} closed: {e}") from e
        ms = round((time.perf_counter() - t0) * 1000, 1)
        r["response_or_error"] = raw({"connect_ms": ms})
        return ms


def summary(light: dict[str, Any]) -> dict[str, Any]:
    """The compact state that goes into state_before and state_after."""
    xy = light.get("color", {}).get("xy")
    return {"on": light.get("on", {}).get("on"),
            "brightness": light.get("dimming", {}).get("brightness"),
            "xy": [xy["x"], xy["y"]] if xy else None,
            "signal": light.get("signaling", {}).get("status", {}).get("signal")}


REMOTE_BASE = "https://api.meethue.com/route"
OAUTH = "https://api.meethue.com/v2/oauth2"


class HueBridge:
    _warned = False

    def __init__(self, ip: str, key: str | None = None, timeout: float = 5.0, remote_token: str | None = None):
        """Local: https://<ip> with a self-signed cert. Remote: Hue's cloud route with an OAuth bearer token; same paths,
        same app key header, slower round trips, works from any network."""
        self.ip, self.key, self.timeout = ip, key, timeout
        self.remote = bool(remote_token)
        self.s = requests.Session()
        self._last_put: dict[str, float] = {}
        if self.remote:
            self.base = REMOTE_BASE
            self.s.headers["Authorization"] = f"Bearer {remote_token}"
            return
        self.base = f"https://{ip}"
        # wtdd: verify=False because the bridge cert is self-signed; LAN only. Upgrade path: pin the Hue root CA.
        self.s.verify = False
        if not HueBridge._warned:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            ledger.log(AGENT, "TLS verify=False: bridge cert is self-signed (LAN only)", ip=ip)
            HueBridge._warned = True

    @classmethod
    def from_env(cls, key_required: bool = True) -> "HueBridge":
        """Remote when HUE_REMOTE_TOKEN is set, else local via HUE_BRIDGE_IP."""
        from .. import config
        key = config.get("HUE_APP_KEY") if key_required else config.maybe("HUE_APP_KEY")
        token = config.maybe("HUE_REMOTE_TOKEN")
        return cls(config.maybe("HUE_BRIDGE_IP") or "api.meethue.com", key, remote_token=token)

    # one HTTP call; maps bad key, rate limit, and connection failures to HueError; never retries
    def _req(self, method: str, path: str, body: Any = None, auth: bool = True) -> Any:
        headers = {"hue-application-key": self.key} if auth else {}
        if auth and not self.key:
            raise HueError("HUE_APP_KEY is empty: run `python -m wtdd.hue pair`")
        try:
            resp = self.s.request(method, self.base + path, json=body, headers=headers, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            raise HueError(f"unreachable {self.base if self.remote else self.ip}: {type(e).__name__}: {str(e)[:120]}") from e
        text = resp.text[:2000]
        if resp.status_code in (401, 403):
            raise HueError(f"bad key (HTTP {resp.status_code}): {text}", resp.status_code)
        if resp.status_code == 429:
            raise HueError(f"rate limited (HTTP 429): {text}", 429)
        if resp.status_code >= 400:
            raise HueError(f"HTTP {resp.status_code} {method} {path}: {text}", resp.status_code)
        data = resp.json()
        if isinstance(data, dict) and data.get("errors"):
            raise HueError(f"bridge errors on {method} {path}: {data['errors']}", resp.status_code)
        return data

    def _throttle(self, rtype: str) -> None:
        wait = self._last_put.get(rtype, 0.0) + PUT_GAP_S[rtype] - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_put[rtype] = time.monotonic()

    def _get_light(self, rid: str) -> dict[str, Any]:
        return self._req("GET", f"/clip/v2/resource/light/{rid}")["data"][0]

    # unauthenticated: name, bridgeid, swversion, apiversion
    def config(self) -> dict[str, Any]:
        with ledger.step(AGENT, "lights.config", APP, {"path": "/api/0/config"}) as r:
            cfg = self._req("GET", "/api/0/config", auth=False)
            r["response_or_error"] = raw(cfg)
            return cfg

    def pair(self, devicetype: str = "wtdd#mac") -> str:
        """One POST /api attempt. Returns the username (the app key); raises HueError('link button not pressed')
        when the button has not been pressed. The caller polls. The key is never logged."""
        with ledger.step(AGENT, "lights.pair", APP, {"devicetype": devicetype}) as r:
            if self.remote:
                self._req("PUT", "/api/0/config", {"linkbutton": True}, auth=False)   # the cloud "link button"
            out = self._req("POST", "/api", {"devicetype": devicetype, "generateclientkey": True}, auth=False)
            first = out[0] if isinstance(out, list) and out else {}
            if "error" in first:
                r["response_or_error"] = raw(first["error"])
                raise HueError(str(first["error"].get("description", first["error"])))
            if "success" not in first or "username" not in first["success"]:
                raise HueError(f"unexpected pair response: {str(out)[:200]}")
            r["response_or_error"] = raw({"success": {"username": "<redacted>"}})
            return first["success"]["username"]

    def lights(self) -> list[dict[str, Any]]:
        with ledger.step(AGENT, "lights.list", APP) as r:
            data = self._req("GET", "/clip/v2/resource/light")["data"]
            r["response_or_error"] = raw(data)
            r["state_after"] = {l["id"]: summary(l) for l in data}
            if not data:
                ledger.log(AGENT, "WARN bridge returned zero lights", ip=self.ip)
            return data

    def rooms(self) -> list[dict[str, Any]]:
        with ledger.step(AGENT, "lights.rooms", APP) as r:
            data = self._req("GET", "/clip/v2/resource/room")["data"]
            r["response_or_error"] = raw(data)
            return data

    def connectivity(self) -> dict[str, str]:
        """device rid -> zigbee status (connected, disconnected, connectivity_issue, unidirectional_incoming)."""
        with ledger.step(AGENT, "lights.connectivity", APP) as r:
            data = self._req("GET", "/clip/v2/resource/zigbee_connectivity")["data"]
            r["response_or_error"] = raw(data)
            return {c["owner"]["rid"]: c["status"] for c in data if "owner" in c}

    def read(self, rid: str) -> dict[str, Any]:
        with ledger.step(AGENT, "lights.read", APP, {"id": rid}) as r:
            light = self._get_light(rid)
            r["response_or_error"] = raw(light)
            r["state_after"] = summary(light)
            return light

    def set(self, rid: str, on: bool | None = None, bri: float | None = None,
            xy: tuple[float, float] | None = None) -> dict[str, Any]:
        """PUT then GET. The step is ok only if the read-back matches what was requested."""
        body: dict[str, Any] = {}
        if on is not None:
            body["on"] = {"on": on}
        if bri is not None:
            body["dimming"] = {"brightness": bri}
        if xy is not None:
            body["color"] = {"xy": {"x": xy[0], "y": xy[1]}}
        if not body:
            raise ValueError("set: nothing to set (on, bri, or xy)")
        return self._put_light(rid, "lights.set", body)

    def signal(self, rid: str, seconds: float, colors: list[tuple[float, float]] = (RED_XY, BLUE_XY)) -> dict[str, Any]:
        """Native `alternating` signal between two xy colors for `seconds`. Field shape verified on the real bridge
        2026-09-13 (Hue Bridge Car, sw 1978293000): `signaling: {signal, duration, colors: [{xy}]}`; read-back shows
        `signaling.status.signal == "alternating"`. One PUT, one ledger row."""
        supported = self.read(rid).get("signaling", {}).get("signal_values", [])
        if "alternating" not in supported:
            raise HueError(f"light {rid[:8]} does not support signal alternating (signal_values={supported})")
        duration = int(round(seconds)) * 1000
        pts = [{"xy": {"x": x, "y": y}} for x, y in colors]
        return self._put_light(rid, "lights.signal", {"signaling": {"signal": "alternating", "duration": duration, "colors": pts}})

    def _put_light(self, rid: str, tool: str, body: dict[str, Any]) -> dict[str, Any]:
        before = summary(self._get_light(rid))
        with ledger.step(AGENT, tool, APP, {"id": rid, **body}, before) as r:
            self._throttle("light")
            r["response_or_error"] = raw(self._req("PUT", f"/clip/v2/resource/light/{rid}", body))
            after = summary(self._get_light(rid))
            r["state_after"] = after
            r["match"] = _matches(body, after)
            if not r["match"]:
                raise HueError(f"read-back mismatch: requested {body}, bridge has {after}")
            return after


def _matches(body: dict[str, Any], after: dict[str, Any]) -> bool:
    if "on" in body and after["on"] != body["on"]["on"]:
        return False
    if "dimming" in body and (after["brightness"] is None
                              or abs(after["brightness"] - body["dimming"]["brightness"]) > 1):
        return False
    if "color" in body:
        want = body["color"]["xy"]
        if after["xy"] is None or abs(after["xy"][0] - want["x"]) > 0.02 or abs(after["xy"][1] - want["y"]) > 0.02:
            return False
    if "signaling" in body and after["signal"] != body["signaling"]["signal"]:
        return False
    return True
