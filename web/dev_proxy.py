"""
ClarityOS web — local dev server with optional CORS-bypass proxy.

The Cloud Run backend's CORS_ORIGINS env var defaults to
"https://pro-mediations.com,https://www.pro-mediations.com", so a
browser at http://localhost:8000 can't call it directly. Two options:

  1) Add http://localhost:8000 to CLARITYOS_CORS_ORIGINS on Cloud Run
     and use plain `python -m http.server 8000`. Easiest.
  2) Run THIS script. It serves the static site AND proxies /api/*
     to the Cloud Run backend, so the browser only ever talks to
     localhost. No backend changes required.

Usage
-----
    python dev_proxy.py [--port 8000] [--backend https://...run.app]

Then open http://localhost:8000 and override the API base in the
browser console once:
    localStorage.setItem('clarityos_api_base', 'http://localhost:8000/api')
    location.reload()
"""
from __future__ import annotations

import argparse
import http.server
import socketserver
import urllib.parse
import urllib.request
import urllib.error
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class Proxy(http.server.SimpleHTTPRequestHandler):
    backend = ""

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/"):
            self._proxy("GET")
        else:
            super().do_GET()

    def do_POST(self):  # noqa: N802
        if self.path.startswith("/api/"):
            self._proxy("POST")
        else:
            self.send_error(405)

    def _proxy(self, method: str):
        target = self.backend.rstrip("/") + self.path[len("/api"):]
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(target, data=body, method=method)
        for h in ("Content-Type", "X-Session-ID", "Authorization"):
            v = self.headers.get(h)
            if v:
                req.add_header(h, v)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                self.send_response(resp.status)
                for k, v in resp.getheaders():
                    if k.lower() in ("transfer-encoding", "connection", "content-encoding"):
                        continue
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(resp.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_error(502, f"proxy error: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--backend", default="", help="Cloud Run base URL")
    args = ap.parse_args()

    if not args.backend:
        print("note: --backend not set; /api/* proxy disabled. Static files only.", file=sys.stderr)
    Proxy.backend = args.backend

    with socketserver.ThreadingTCPServer(("0.0.0.0", args.port), Proxy) as srv:
        print(f"serving {ROOT} on http://localhost:{args.port}")
        if args.backend:
            print(f"proxying /api/* -> {args.backend}")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
