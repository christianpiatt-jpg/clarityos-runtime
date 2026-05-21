"""
phone_intelligence_panel.py — Phone Intelligence Panel HTTP surface (Phase 3 Unit 3).

Mobile-optimized HTTP surface that mirrors the Web panel architecture
(Phase 3 Unit 2) and serves the same canonical snapshot via a
mobile-friendly route prefix:

    GET /m/<user_id>                 →  JSON snapshot from
                                        runtime_intelligence_wiring.get_intelligence_snapshot
    GET /m/                          →  phone/intelligence_panel.html
    GET /m                           →  phone/intelligence_panel.html  (no-slash courtesy)
    GET /m/intelligence_panel.html   →  phone/intelligence_panel.html  (explicit)

DESIGN COMMITMENTS (identical to Unit 2):
    * Pure stdlib (http.server). No frameworks, no external libraries.
    * Read-only. Never mutates bus / archives / operator_state.
    * No caching. No cookies. No sessions. No global state.
    * Deterministic. Same wiring state → byte-identical JSON.
    * Graceful. 404 / 405 / 500 land as JSON error envelopes.

The mobile HTML is delivered at `/m/` (not the same `/` as the web
panel) so a single host can co-serve both surfaces on different
prefixes (`/intelligence/*` for web, `/m/*` for phone).

PUBLIC API:
    build_response(method, path)         -> (status, headers_dict, body_bytes)
    PhoneIntelligencePanelHandler        -> BaseHTTPRequestHandler subclass
    serve(host='127.0.0.1', port=8089)   -> HTTPServer

Run for development:

    python -m phone_intelligence_panel --port 8089
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

logger = logging.getLogger("clarityos.phone_intelligence_panel")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HTML_PATH: Path = (
    Path(__file__).resolve().parent / "phone" / "intelligence_panel.html"
)

# Allowed user_id shape: alphanumeric + dot + underscore + hyphen, 1..128 chars.
_USER_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

# Disallowed exact values (defense-in-depth path-traversal patterns).
_DISALLOWED_USER_IDS: frozenset = frozenset({".", ".."})

# Mobile-route patterns. HTML paths are matched first so the explicit
# `/m/intelligence_panel.html` route isn't accidentally parsed as a
# user_id named "intelligence_panel.html" (which would pass the regex).
_PHONE_INTELLIGENCE_RE = re.compile(r"^/m/([^/]+)/?$")
_PHONE_HTML_PATHS: frozenset = frozenset({
    "/m",
    "/m/",
    "/m/intelligence_panel.html",
})

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
    user-id shape and not in the disallowed set."""
    if not isinstance(uid, str):
        return False
    if uid in _DISALLOWED_USER_IDS:
        return False
    return bool(_USER_ID_RE.match(uid))


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------
def _error_response(status: int, code: str, message: str) -> tuple:
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
    body = json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8")
    headers = {
        **_BASE_HEADERS,
        "Content-Type":   "application/json; charset=utf-8",
        "Content-Length": str(len(body)),
    }
    return (status, headers, body)


def _html_response() -> tuple:
    if not _HTML_PATH.exists():
        return _error_response(
            404, "html_missing", "phone panel HTML file not found",
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
    """Pure-function HTTP dispatcher for the phone panel.

    Returns ``(status, headers, body_bytes)``. Identical contract to the
    Web Unit-2 dispatcher; the only differences are the mobile route
    prefix and the HTML file location.
    """
    if method != "GET":
        return _error_response(
            405, "method_not_allowed",
            f"only GET is supported; got {method}",
        )

    parsed = urlparse(path)
    clean_path = parsed.path or "/"

    # HTML routes matched FIRST so the explicit
    # `/m/intelligence_panel.html` isn't parsed as a user_id.
    if clean_path in _PHONE_HTML_PATHS:
        return _html_response()

    # JSON route.
    m = _PHONE_INTELLIGENCE_RE.match(clean_path)
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
            "phone_intelligence_panel: wiring failed for %s: %s", user_id, e,
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
class PhoneIntelligencePanelHandler(BaseHTTPRequestHandler):
    """Stdlib HTTP handler for the Phone Intelligence Panel."""

    server_version = "ClarityOSPhoneIntelligencePanel/1.0"

    def do_GET(self) -> None:
        try:
            status, headers, body = build_response("GET", self.path)
        except Exception as e:  # pragma: no cover (build_response never raises)
            logger.warning(
                "phone_intelligence_panel: catastrophic GET error: %s", e,
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
        """Suppress default access logs."""
        return


# ---------------------------------------------------------------------------
# Convenience server entrypoint
# ---------------------------------------------------------------------------
def serve(host: str = "127.0.0.1", port: int = 8089) -> HTTPServer:
    """Bind a server on ``host:port`` and return the HTTPServer instance."""
    return HTTPServer((host, port), PhoneIntelligencePanelHandler)


if __name__ == "__main__":  # pragma: no cover
    import argparse
    parser = argparse.ArgumentParser(description="Phone Intelligence Panel server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8089)
    args = parser.parse_args()

    srv = serve(args.host, args.port)
    print(f"ClarityOS Phone Intelligence Panel — http://{args.host}:{args.port}/m/")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
        srv.server_close()
