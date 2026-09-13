"""python -m wtdd.hue <probe|pair|lights|read|set|signal|zone>. See GOAL.md. Every command writes ledger rows."""
from __future__ import annotations
import argparse
import requests
import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from .. import config, ledger
from .api import OAUTH, AGENT, APP, HueBridge, HueError, discover, raw, summary, tcp_open

HERE = Path(__file__).resolve().parent
ZONES = HERE / "zones.json"
ENV = config.ROOT / ".env"


def bridge() -> HueBridge:
    return HueBridge.from_env(key_required=False)


# ---------------------------------------------------------------- probe
def probe(ip: str | None, key: str | None) -> bool:
    """Never raises. Prints one status table; returns True only when every line is ok."""
    rows: list[tuple[str, str, str]] = []

    def run(label: str, fn, skip: str | None = None) -> Any:
        if skip:
            rows.append((label, "SKIP", skip))
            return None
        try:
            out, note = fn()
            rows.append((label, "ok", note))
            return out
        except Exception as e:  # noqa: BLE001  (probe reports; the ledger row already has the error)
            rows.append((label, "FAIL", f"{type(e).__name__}: {str(e)[:140]}"))
            return None

    def _disc():
        b = discover()
        found = [x for x in b if x.get("internalipaddress") == ip]
        return b, (f"{len(b)} bridge(s): " + ", ".join(f"{x.get('id')} @ {x.get('internalipaddress')}:{x.get('port')}" for x in b)
                   + (" (matches HUE_BRIDGE_IP)" if found else f" (HUE_BRIDGE_IP={ip} not in list)"))

    def _cfg():
        c = b.config()
        return c, f"name={c.get('name')} swversion={c.get('swversion')} apiversion={c.get('apiversion')} bridgeid={c.get('bridgeid')}"

    def _lights():
        ls = b.lights()
        return ls, f"n={len(ls)}: " + ", ".join(f"{l['id'][:8]} {l['metadata']['name']}" for l in ls)

    token = config.maybe("HUE_REMOTE_TOKEN")
    if token:
        b = HueBridge(ip or "api.meethue.com", key, remote_token=token)
        rows.append(("mode", "ok", "REMOTE via api.meethue.com/route (HUE_REMOTE_TOKEN set)"))
        run("GET /route/api/0/config", _cfg)
        rows.append(("HUE_APP_KEY", "ok" if key else "FAIL", f"present ({len(key)} chars)" if key else "empty: run `python -m wtdd.hue pair`"))
        run("GET /route/clip/v2/resource/light", _lights, skip=None if key else "no key")
        ok = all(st in ("ok", "warn") for _, st, _ in rows)
        w = max(len(l) for l, _, _ in rows)
        print(f"{'probe':<{w}}  status  detail")
        for label, st, note in rows:
            print(f"{label:<{w}}  {st:<6}  {note}")
        if not ok:
            print("\nBLOCKED. Johnny: if the token expired run `python -m wtdd.hue remote-refresh`; if there is no key run `python -m wtdd.hue pair`.")
        return ok
    # discovery is informational once HUE_BRIDGE_IP is set (Philips rate-limits it: HTTP 429 after repeated probes)
    run("discovery.meethue.com", _disc)
    if ip and rows and rows[-1][1] == "FAIL":
        rows[-1] = (rows[-1][0], "warn", rows[-1][2] + " (informational; HUE_BRIDGE_IP is set)")
    tcp = False
    if not ip:
        rows.append(("HUE_BRIDGE_IP", "FAIL", f"missing: cp .env.example .env (see {ENV})"))
    else:
        b = HueBridge(ip, key)
        tcp = run(f"tcp {ip if ':' in ip else ip + ':443'}", lambda: (tcp_open(ip), "open")) is not None
        run("GET /api/0/config", _cfg, skip=None if tcp else "tcp closed")
    rows.append(("HUE_APP_KEY", "ok" if key else "FAIL", f"present ({len(key)} chars)" if key else "empty: run `python -m wtdd.hue pair`"))
    if ip:
        run("GET /clip/v2/resource/light", _lights, skip=None if (tcp and key) else ("tcp closed" if not tcp else "no key"))

    w = max(len(r[0]) for r in rows)
    print(f"{'probe':<{w}}  status  detail")
    for label, status, note in rows:
        print(f"{label:<{w}}  {status:<6}  {note}")
    ok = all(r[1] in ("ok", "warn") for r in rows)
    if not ok:
        print("\nBLOCKED. Johnny: 1) put this Mac on the bridge's subnet (or move the bridge's Ethernet to this router), "
              "then re-run `python -m wtdd.hue probe`; 2) when tcp is open, run `python -m wtdd.hue pair` and press the link button.")
    return ok


# ---------------------------------------------------------------- pair
def write_env_key(path: Path, name: str, value: str) -> None:
    if not path.exists():
        shutil.copy(config.ROOT / ".env.example", path)
    text = path.read_text()
    line = f"{name}={value}"
    if re.search(rf"^{name}=.*$", text, flags=re.M):
        text = re.sub(rf"^{name}=.*$", line, text, count=1, flags=re.M)
    else:
        text = text.rstrip("\n") + "\n" + line + "\n"
    path.write_text(text)


def pair(b: HueBridge, env_path: Path = ENV, poll_s: float = 2.0, max_s: float = 60.0) -> bool:
    """Polls POST /api until the bridge hands out a username, then writes it to .env. Never prints the key."""
    t0 = time.monotonic()
    prompted = False
    while True:
        try:
            username = b.pair()
            break
        except HueError as e:
            if "link button not pressed" not in str(e):
                raise
            if not prompted:
                print(f"PRESS THE ROUND LINK BUTTON ON THE HUE BRIDGE NOW (polling every {poll_s:g}s for {max_s:g}s)", flush=True)
                prompted = True
            if time.monotonic() - t0 > max_s:
                print("pair: gave up, the link button was not pressed in time; re-run `python -m wtdd.hue pair`.")
                return False
            time.sleep(poll_s)
    write_env_key(env_path, "HUE_APP_KEY", username)
    b.key = username
    print(f"paired: HUE_APP_KEY ({len(username)} chars) written to {env_path}. Next: `python -m wtdd.hue lights`")
    return True


# ---------------------------------------------------------------- lights / resolve
def resolve(lights: list[dict[str, Any]], ref: str) -> dict[str, Any]:
    """Full rid, unique rid prefix, or case-insensitive name."""
    hits = [l for l in lights if l["id"] == ref] or [l for l in lights if l["id"].startswith(ref)] \
        or [l for l in lights if l["metadata"]["name"].lower() == ref.lower()]
    if len(hits) != 1:
        names = ", ".join(f"{l['id'][:8]} {l['metadata']['name']}" for l in lights)
        raise HueError(f"'{ref}' matches {len(hits)} lights; known: {names}")
    return hits[0]


def lights_table(b: HueBridge) -> list[dict[str, Any]]:
    ls, rooms, conn = b.lights(), b.rooms(), b.connectivity()
    room_of = {c["rid"]: rm["metadata"]["name"] for rm in rooms for c in rm.get("children", []) if c["rtype"] == "device"}
    out = []
    for l in ls:
        dev = l.get("owner", {}).get("rid")
        s = summary(l)
        out.append({"id": l["id"][:8], "name": l["metadata"]["name"], "room": room_of.get(dev, "?"),
                    "on": s["on"], "bri": s["brightness"], "color": "color" in l, "reachable": conn.get(dev, "?")})
    hdr = ("id", "name", "room", "on", "bri", "color", "reachable")
    widths = [max(len(h), *(len(str(r[h])) for r in out)) for h in hdr] if out else [len(h) for h in hdr]
    print("  ".join(f"{h:<{w}}" for h, w in zip(hdr, widths)))
    for r in out:
        print("  ".join(f"{str(r[h]):<{w}}" for h, w in zip(hdr, widths)))
    ledger.log(AGENT, f"lights table (n={len(out)})")
    return out


# ---------------------------------------------------------------- zone
def load_zones(path: Path = ZONES) -> dict[str, Any]:
    zones = json.loads(path.read_text())
    if not isinstance(zones, dict) or not zones:
        raise HueError(f"{path} must be a non-empty object of zones")
    return zones


def set_zone(b: HueBridge, name: str, on: bool, bri: float | None, path: Path = ZONES) -> dict[str, Any]:
    """Sets every light in the zone (contract: never touches an id absent from zones.json). One row for the zone
    on top of one lights.set row per light."""
    zones = load_zones(path)
    if name not in zones:
        raise HueError(f"zone '{name}' not in {path}; known: {', '.join(zones)}")
    ids = zones[name].get("lights", [])
    if not ids:
        raise HueError(f"zone '{name}' has no lights in {path}: Johnny must fill it (ids from `python -m wtdd.hue lights`)")
    known = {l["id"] for l in b.lights()}
    missing = [i for i in ids if i not in known]
    if missing:
        raise HueError(f"zone '{name}' names light ids the bridge does not have: {missing}")
    before = {i: summary(b._get_light(i)) for i in ids}
    with ledger.step(AGENT, "lights.set_zone", APP, {"zone": name, "on": on, "brightness": bri, "lights": ids}, before) as r:
        r["state_after"] = {i: b.set(i, on=on, bri=bri) for i in ids}
        r["response_or_error"] = raw({"read_back": r["state_after"]})
        r["match"] = True
        return r["state_after"]


# ---------------------------------------------------------------- cli
def _catch_code(port: int, timeout_s: float) -> str | None:
    """Tiny one-shot HTTP listener for the OAuth redirect http://localhost:<port>/callback?code=...; None on timeout."""
    import http.server
    import socketserver
    import urllib.parse
    got: dict[str, str] = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got["code"] = (q.get("code") or [""])[0]
            self.send_response(200); self.end_headers()
            self.wfile.write(b"wtdd: got the code, you can close this tab")

        def log_message(self, *a):  # quiet
            pass

    with socketserver.TCPServer(("127.0.0.1", port), H) as srv:
        srv.timeout = timeout_s
        srv.handle_request()
    return got.get("code") or None


def remote_auth(a: argparse.Namespace) -> int:
    """Cloud path: OAuth code -> tokens -> virtual link button -> app key. Needs HUE_CLIENT_ID, HUE_CLIENT_SECRET, HUE_APP_ID
    from a "Remote Hue API" app registered at https://developers.meethue.com/my-apps/ with callback http://localhost:8787/callback."""
    import subprocess
    import urllib.parse
    cid, secret, appid = config.get("HUE_CLIENT_ID"), config.get("HUE_CLIENT_SECRET"), config.get("HUE_APP_ID")
    url = (f"{OAUTH}/authorize?" + urllib.parse.urlencode({"client_id": cid, "response_type": "code", "state": "wtdd",
           "appid": appid, "deviceid": "wtdd-mac", "devicename": "wtdd"}))
    print("1) Log in and grant in the browser (opening it now):\n   " + url)
    subprocess.run(["open", url], check=False)
    print(f"2) Waiting up to {a.timeout:.0f}s for the redirect on http://localhost:{a.port}/callback ...")
    code = _catch_code(a.port, a.timeout)
    if not code:
        code = input("   No redirect caught. Paste the `code` from the redirect URL: ").strip()
    with ledger.step(AGENT, "lights.oauth_token", APP, {"grant": "authorization_code"}) as r:
        resp = requests.post(f"{OAUTH}/token", auth=(cid, secret), data={"grant_type": "authorization_code", "code": code}, timeout=15)
        if resp.status_code != 200:
            raise HueError(f"token exchange HTTP {resp.status_code}: {resp.text[:200]}")
        tok = resp.json()
        r["state_after"] = {"expires_in": tok.get("expires_in"), "token_type": tok.get("token_type")}
    write_env_key(ENV, "HUE_REMOTE_TOKEN", tok["access_token"])
    write_env_key(ENV, "HUE_REMOTE_REFRESH", tok.get("refresh_token", ""))
    print("3) Tokens written to .env. Creating the app key through the cloud link button ...")
    b = HueBridge("api.meethue.com", None, remote_token=tok["access_token"])
    username = b.pair("wtdd#remote")
    write_env_key(ENV, "HUE_APP_KEY", username)
    print("4) HUE_APP_KEY written. Now: python -m wtdd.hue probe && python -m wtdd.hue lights")
    return 0


def remote_refresh(a: argparse.Namespace) -> int:
    cid, secret, rt = config.get("HUE_CLIENT_ID"), config.get("HUE_CLIENT_SECRET"), config.get("HUE_REMOTE_REFRESH")
    with ledger.step(AGENT, "lights.oauth_token", APP, {"grant": "refresh_token"}) as r:
        resp = requests.post(f"{OAUTH}/token", auth=(cid, secret), data={"grant_type": "refresh_token", "refresh_token": rt}, timeout=15)
        if resp.status_code != 200:
            raise HueError(f"refresh HTTP {resp.status_code}: {resp.text[:200]}")
        tok = resp.json()
        r["state_after"] = {"expires_in": tok.get("expires_in")}
    write_env_key(ENV, "HUE_REMOTE_TOKEN", tok["access_token"])
    if tok.get("refresh_token"):
        write_env_key(ENV, "HUE_REMOTE_REFRESH", tok["refresh_token"])
    print("refreshed; HUE_REMOTE_TOKEN written")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m wtdd.hue", description="Philips Hue lights agent (CLIP v2, LAN)")
    sub = p.add_subparsers(dest="cmd", required=True)
    ra = sub.add_parser("remote-auth", help="cloud path: OAuth login -> tokens -> cloud link button -> app key (writes .env)")
    ra.add_argument("--port", type=int, default=8787); ra.add_argument("--timeout", type=float, default=180.0)
    ra.set_defaults(fn=remote_auth)
    sub.add_parser("remote-refresh", help="refresh the cloud token with HUE_REMOTE_REFRESH").set_defaults(fn=remote_refresh)
    sub.add_parser("probe", help="discovery, tcp, config, key, light count; never throws before the table")
    sp = sub.add_parser("pair", help="link-button flow; writes HUE_APP_KEY into .env")
    sp.add_argument("--force", action="store_true", help="re-pair even if HUE_APP_KEY is set")
    sub.add_parser("lights", help="table: id, name, room, on, bri, color, reachable")
    sp = sub.add_parser("read", help="read one light")
    sp.add_argument("light", help="id, id prefix, or name")
    sp = sub.add_parser("set", help="set on/off, brightness, xy")
    sp.add_argument("light")
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--on", action="store_true")
    g.add_argument("--off", action="store_true")
    sp.add_argument("--bri", type=float, help="0 to 100")
    sp.add_argument("--xy", help="x,y in CIE 1931, e.g. 0.675,0.322")
    sp = sub.add_parser("signal", help="native alternating red/blue signal")
    sp.add_argument("light")
    sp.add_argument("--seconds", type=float, default=10)
    sp = sub.add_parser("zone", help="set every light of a zone from zones.json")
    sp.add_argument("zone")
    g = sp.add_mutually_exclusive_group(required=True)
    g.add_argument("--on", action="store_true")
    g.add_argument("--off", action="store_true")
    sp.add_argument("--bri", type=float)
    a = p.parse_args(argv)

    try:
        if a.cmd == "probe":
            return 0 if probe(config.maybe("HUE_BRIDGE_IP"), config.maybe("HUE_APP_KEY")) else 1
        b = bridge()
        if a.cmd == "pair":
            if b.key and not a.force:
                print("HUE_APP_KEY already set in .env; use --force to re-pair.")
                return 1
            return 0 if pair(b) else 1
        if a.cmd == "lights":
            return 0 if lights_table(b) else 1
        if a.cmd == "read":
            print(json.dumps(summary(b.read(resolve(b.lights(), a.light)["id"])), indent=1))
            return 0
        if a.cmd == "set":
            on = True if a.on else (False if a.off else None)
            if on is None and a.bri is None and a.xy is None:
                p.error("set: give --on/--off, --bri, or --xy")
            if a.bri is not None and not 0 <= a.bri <= 100:
                p.error("--bri must be 0 to 100")
            xy = tuple(float(v) for v in a.xy.split(",")) if a.xy else None
            if xy and len(xy) != 2:
                p.error("--xy must be x,y")
            print(json.dumps(b.set(resolve(b.lights(), a.light)["id"], on=on, bri=a.bri, xy=xy)))
            return 0
        if a.cmd == "signal":
            print(json.dumps(b.signal(resolve(b.lights(), a.light)["id"], a.seconds)))
            return 0
        if a.cmd == "zone":
            print(json.dumps(set_zone(b, a.zone, a.on, a.bri)))
            return 0
    except HueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
