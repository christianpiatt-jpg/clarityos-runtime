"""
web_intelligence_panel.py — Web Intelligence Panel HTTP surface (Phase 3 Unit 2).

Thin pure-stdlib HTTP server exposing a single read-only endpoint:

    GET /intelligence/<user_id>   →  JSON snapshot from
                                     runtime_intelligence_wiring.get_intelligence_snapshot

Plus two static-HTML routes for convenience:

    GET /                              →  web/intelligence_panel.html
    GET /intelligence_panel.html       →  web/intelligence_panel.html

DESIGN COMMITMENTS:
    * Pure stdlib (http.server). No frameworks, no external libraries.
    * Read-only. The HTTP layer never mutates the bus, archives,
      operator_state, or any other ClarityOS state.
    * No caching. No cookies. No sessions. No global state.
    * Deterministic. Same wiring state → byte-identical JSON body.
    * Graceful. Catastrophic failures land as 500 with a JSON error
      envelope. Malformed routes / user_ids land as 404. Method-not-GET
      lands as 405. The Unit-1 wiring layer never raises, so 500 here
      is genuinely unreachable in production.

PUBLIC API:
    build_response(method, path)     -> (status, headers_dict, body_bytes)
    IntelligencePanelHandler         -> BaseHTTPRequestHandler subclass
    serve(host='127.0.0.1', port=8088) -> HTTPServer

Run for development:

    python -m web_intelligence_panel --port 8088
"""
from __future__ import annotations

import json
import logging
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import runtime_intelligence_wiring as _wiring_mod

logger = logging.getLogger("clarityos.web_intelligence_panel")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# HTML lives next to the Python module, under ./web/intelligence_panel.html.
_HTML_PATH: Path = Path(__file__).resolve().parent / "web" / "intelligence_panel.html"

# Allowed user_id shape: alphanumeric + dot + underscore + hyphen, 1..128 chars.
_USER_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

# Disallowed exact values (path-traversal patterns even though the dispatcher
# never touches the filesystem with user_id, defense-in-depth).
_DISALLOWED_USER_IDS: frozenset = frozenset({".", ".."})

# Path patterns.
_INTELLIGENCE_PATH_RE = re.compile(r"^/intelligence/([^/]+)/?$")
_HTML_PATHS: frozenset = frozenset({"/", "/intelligence_panel.html"})

# Headers added to every response.
_BASE_HEADERS: dict = {
    "Cache-Control":          "no-store",
    "X-Content-Type-Options": "nosniff",
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def _valid_user_id(uid: Any) -> bool:
    """Return True iff ``uid`` is a non-empty string matching the allowed
    user-id shape and is not in the disallowed set."""
    if not isinstance(uid, str):
        return False
    if uid in _DISALLOWED_USER_IDS:
        return False
    return bool(_USER_ID_RE.match(uid))


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------
def _error_response(status: int, code: str, message: str) -> tuple:
    """Build a (status, headers, body) error response with a JSON envelope."""
    body = json.dumps(
        {"error": code, "message": message}, ensure_ascii=False,
    ).encode("utf-8")
    headers = {
        **_BASE_HEADERS,
        "Content-Type":   "application/json; charset=utf-8",
        "Content-Length": str(len(body)),
    }
    return (status, headers, body)


def _json_response(status: int, payload: dict) -> tuple:
    """Build a (status, headers, body) JSON response."""
    body = json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8")
    headers = {
        **_BASE_HEADERS,
        "Content-Type":   "application/json; charset=utf-8",
        "Content-Length": str(len(body)),
    }
    return (status, headers, body)


def _html_response() -> tuple:
    """Build the HTML panel response. 404 if the HTML file is missing."""
    if not _HTML_PATH.exists():
        return _error_response(
            404, "html_missing", "panel HTML file not found",
        )
    try:
        text = _HTML_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:  # pragma: no cover (defensive)
        return _error_response(500, "html_read_failed", str(e))
    body = text.encode("utf-8")
    headers = {
        **_BASE_HEADERS,
        "Content-Type":   "text/html; charset=utf-8",
        "Content-Length": str(len(body)),
    }
    return (200, headers, body)


# ---------------------------------------------------------------------------
# Pure-function dispatcher
# ---------------------------------------------------------------------------
def build_response(method: str, path: str) -> tuple:
    """Pure-function HTTP dispatcher.

    Returns ``(status, headers, body_bytes)`` for any (method, path).
    All side effects (wiring read, HTML file read) happen inside this
    function. Tests can call it directly without spinning up a server.

    Routes:
        * ``GET /intelligence/<user_id>`` → JSON snapshot
        * ``GET /``                       → HTML panel
        * ``GET /intelligence_panel.html``→ HTML panel
        * anything else                   → 404 JSON
        * non-GET method                  → 405 JSON
    """
    if method != "GET":
        return _error_response(
            405, "method_not_allowed",
            f"only GET is supported; got {method}",
        )

    # Strip query string / fragment; we don't use them.
    parsed = urlparse(path)
    clean_path = parsed.path or "/"

    # HTML routes.
    if clean_path in _HTML_PATHS:
        return _html_response()

    # Intelligence API route.
    m = _INTELLIGENCE_PATH_RE.match(clean_path)
    if not m:
        return _error_response(
            404, "not_found",
            f"no such endpoint: {clean_path}",
        )

    user_id = unquote(m.group(1))
    if not _valid_user_id(user_id):
        return _error_response(
            404, "invalid_user_id",
            "user_id contains invalid characters or wrong length",
        )

    # Call the read-only wiring layer.
    try:
        snapshot = _wiring_mod.get_intelligence_snapshot(user_id)
    except Exception as e:
        logger.warning(
            "web_intelligence_panel: wiring failed for %s: %s", user_id, e,
        )
        return _error_response(
            500, "wiring_failed",
            f"intelligence snapshot unavailable: {e}",
        )

    if not isinstance(snapshot, dict):
        return _error_response(
            500, "shape_mismatch",
            "wiring returned a non-dict snapshot",
        )

    return _json_response(200, snapshot)


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class IntelligencePanelHandler(BaseHTTPRequestHandler):
    """Stdlib HTTP handler for the Web Intelligence Panel.

    All GET requests are dispatched through ``build_response``. Other
    methods reach ``send_response(501)`` via BaseHTTPRequestHandler's
    default behaviour (no ``do_<METHOD>`` defined here).
    """

    server_version = "ClarityOSIntelligencePanel/1.0"

    def do_GET(self) -> None:
        try:
            status, headers, body = build_response("GET", self.path)
        except Exception as e:  # pragma: no cover (build_response never raises)
            logger.warning(
                "web_intelligence_panel: catastrophic GET error: %s", e,
            )
            body = json.dumps(
                {"error": "internal", "message": str(e)},
            ).encode("utf-8")
            status = 500
            headers = {
                **_BASE_HEADERS,
                "Content-Type":   "application/json; charset=utf-8",
                "Content-Length": str(len(body)),
            }
        self._send(status, headers, body)

    def _send(self, status: int, headers: dict, body: bytes) -> None:
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default access logs — they would flood test output and
        offer no operational value in this surface."""
        return


# ---------------------------------------------------------------------------
# Convenience server entrypoint
# ---------------------------------------------------------------------------
def serve(host: str = "127.0.0.1", port: int = 8088) -> HTTPServer:
    """Bind a server on ``host:port`` and return the HTTPServer instance.

    Caller owns the server lifecycle (``serve_forever`` / ``shutdown``).
    Bind to port 0 to get an OS-assigned random port (useful in tests).
    """
    return HTTPServer((host, port), IntelligencePanelHandler)


if __name__ == "__main__":  # pragma: no cover
    import argparse
    parser = argparse.ArgumentParser(description="Web Intelligence Panel server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    args = parser.parse_args()

    srv = serve(args.host, args.port)
    print(f"ClarityOS Intelligence Panel — http://{args.host}:{args.port}/")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
        srv.server_close()
