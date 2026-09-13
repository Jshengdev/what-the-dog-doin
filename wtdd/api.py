"""Local HTTP API over the tools folder, plus the static UI. Stdlib only.

  GET  /tools                 -> [{name, doc, args}]
  POST /tools/<name>  {args}  -> the tool's result (JSON) or {"error": ...} with 500
  GET  /ledger?n=20           -> last rows
  GET  /                      -> ui/index.html (the remote and the map)
Every tool call is already a ledger row; the API adds nothing on top.
"""
from __future__ import annotations
import json
import mimetypes
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import tools
from .config import ROOT
from .ledger import log, rows

UI = ROOT / "ui"


class H(BaseHTTPRequestHandler):
    def _json(self, code: int, obj) -> None:
        body = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        if u.path == "/tools":
            return self._json(200, tools.describe())
        if u.path == "/map":
            return self._json(200, json.loads((UI / "map.json").read_text()))
        if u.path == "/ledger":
            n = int((parse_qs(u.query).get("n") or ["20"])[0])
            return self._json(200, rows(n))
        rel = "index.html" if u.path in ("", "/") else u.path.lstrip("/")
        if ".." in rel:
            return self._json(404, {"error": "not found"})
        f = UI / rel   # symlinks inside ui/ (tokens.css -> taste-library) are allowed
        if not f.is_file():
            return self._json(404, {"error": f"no {rel}"})
        data = f.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(f))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):  # noqa: N802
        u = urlparse(self.path)
        if u.path == "/map":   # the map page saves its path and zones here
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n) or b"{}")
            (UI / "map.json").write_text(json.dumps(data, indent=2) + "\n")
            log("api", "map saved", points=len(data.get("path", [])), zones=len(data.get("zones", [])))
            return self._json(200, {"ok": True})
        if not u.path.startswith("/tools/"):
            return self._json(404, {"error": "not found"})
        name = u.path[len("/tools/"):]
        n = int(self.headers.get("Content-Length") or 0)
        args = json.loads(self.rfile.read(n) or b"{}") if n else {}
        t0 = time.perf_counter()
        try:
            out = tools.call(name, **args)
            log("api", f"{name} ok", ms=round((time.perf_counter() - t0) * 1000))
            return self._json(200, {"ok": True, "tool": name, "args": args, "result": out})
        except Exception as e:  # noqa: BLE001  (the tool's own ledger row has the failure; the API reports it truthfully)
            log("api", f"{name} FAILED", err=f"{type(e).__name__}: {str(e)[:100]}", ms=round((time.perf_counter() - t0) * 1000))
            return self._json(500, {"ok": False, "tool": name, "args": args, "error": f"{type(e).__name__}: {e}"})

    def log_message(self, fmt, *a):  # one line per request through our logger
        log("api", fmt % a)


def main(argv: list[str] | None = None) -> int:
    port = int((argv or sys.argv[1:] or ["7788"])[0])
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    log("api", f"serving http://127.0.0.1:{port}/  tools={len(tools.registry())} ui={UI}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
