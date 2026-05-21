"""
Tests for web_intelligence_panel.py + web/intelligence_panel.html (Phase 3 Unit 2).

Two test layers:
  1. Pure-function tests of ``build_response`` — fast, no I/O.
  2. Integration tests via a real HTTPServer thread on 127.0.0.1:0 —
     exercises the BaseHTTPRequestHandler dispatch and headers.

The runtime wiring layer is stubbed for every test (autouse fixture)
so the panel never touches real ingestion bus / archives / operator_state.

50+ tests across 9 test classes.
"""
from __future__ import annotations

import json
import re
import threading
from http.server import HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

import runtime_intelligence_wiring as rwi
import web_intelligence_panel as wip


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
_CANNED_SNAPSHOT = {
    "date":        "2026-05-11",
    "daily_elins": None,
    "news":        [],
    "email":       [],
    "micro":       [],
    "macro":       {},
}


@pytest.fixture(autouse=True)
def _stub_wiring(monkeypatch: pytest.MonkeyPatch):
    """Stub the wiring to return the canned snapshot. Tests that need a
    different snapshot or a recorder override this in their own body."""
    monkeypatch.setattr(
        rwi, "get_intelligence_snapshot",
        lambda uid: dict(_CANNED_SNAPSHOT),
    )


@pytest.fixture
def server():
    """Start a panel server on a random local port in a daemon thread."""
    srv = HTTPServer(("127.0.0.1", 0), wip.IntelligencePanelHandler)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=2.0)


def _http_get(url: str, method: str = "GET") -> tuple:
    """Return (status, headers_dict, body_bytes). Uses HTTPError to capture
    non-2xx responses without raising."""
    req = Request(url, method=method)
    try:
        with urlopen(req, timeout=5) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except HTTPError as e:
        return e.code, dict(e.headers), e.read()


# ===========================================================================
# A. HTTP surface behavior (pure-function build_response)
# ===========================================================================
class TestBuildResponse:
    def test_valid_user_returns_200(self):
        status, _, _ = wip.build_response("GET", "/intelligence/alice")
        assert status == 200

    def test_content_type_is_json(self):
        _, headers, _ = wip.build_response("GET", "/intelligence/alice")
        assert headers["Content-Type"].startswith("application/json")

    def test_response_has_all_six_keys(self):
        _, _, body = wip.build_response("GET", "/intelligence/alice")
        data = json.loads(body)
        assert set(data.keys()) == {"date", "daily_elins", "news", "email", "micro", "macro"}

    def test_lists_never_none(self):
        _, _, body = wip.build_response("GET", "/intelligence/alice")
        data = json.loads(body)
        assert isinstance(data["news"],  list)
        assert isinstance(data["email"], list)
        assert isinstance(data["micro"], list)

    def test_macro_is_dict(self):
        _, _, body = wip.build_response("GET", "/intelligence/alice")
        data = json.loads(body)
        assert isinstance(data["macro"], dict)

    def test_content_length_matches_body(self):
        _, headers, body = wip.build_response("GET", "/intelligence/alice")
        assert int(headers["Content-Length"]) == len(body)

    def test_response_is_valid_utf8(self):
        _, _, body = wip.build_response("GET", "/intelligence/alice")
        body.decode("utf-8")  # Should not raise

    def test_non_get_method_405(self):
        status, _, body = wip.build_response("POST", "/intelligence/alice")
        assert status == 405
        err = json.loads(body)
        assert err["error"] == "method_not_allowed"


# ===========================================================================
# B. Integration with runtime wiring
# ===========================================================================
class TestWiringIntegration:
    def test_wiring_called_with_correct_user_id(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            rwi, "get_intelligence_snapshot",
            lambda uid: (calls.append(uid), dict(_CANNED_SNAPSHOT))[1],
        )
        wip.build_response("GET", "/intelligence/alice")
        wip.build_response("GET", "/intelligence/bob")
        assert calls == ["alice", "bob"]

    def test_response_body_matches_snapshot(self, monkeypatch):
        custom = {
            "date": "2026-05-11",
            "daily_elins": {"type": "daily_personal_elins", "macro": {"field_weather": "stable"}},
            "news":  [{"headline": "X"}],
            "email": [{"subject": "Y"}],
            "micro": [{"kind": "elins"}],
            "macro": {"field_weather": "stable"},
        }
        monkeypatch.setattr(rwi, "get_intelligence_snapshot", lambda uid: dict(custom))
        _, _, body = wip.build_response("GET", "/intelligence/alice")
        assert json.loads(body) == custom

    def test_partial_snapshot_passthrough(self, monkeypatch):
        partial = {**_CANNED_SNAPSHOT, "news": [{"headline": "only news"}]}
        monkeypatch.setattr(rwi, "get_intelligence_snapshot", lambda uid: dict(partial))
        _, _, body = wip.build_response("GET", "/intelligence/alice")
        assert json.loads(body)["news"] == [{"headline": "only news"}]

    def test_full_snapshot_passthrough(self, monkeypatch):
        full = {
            "date": "2026-05-11",
            "daily_elins": {"type": "daily_personal_elins"},
            "news":  [{"a": 1}, {"a": 2}],
            "email": [{"b": 1}],
            "micro": [{"c": 1}],
            "macro": {"field_weather": "turbulent"},
        }
        monkeypatch.setattr(rwi, "get_intelligence_snapshot", lambda uid: dict(full))
        _, _, body = wip.build_response("GET", "/intelligence/alice")
        assert json.loads(body) == full

    def test_no_mutation_between_calls(self, monkeypatch):
        """Two calls with the same user_id produce identical bodies."""
        b1 = wip.build_response("GET", "/intelligence/alice")[2]
        b2 = wip.build_response("GET", "/intelligence/alice")[2]
        assert b1 == b2


# ===========================================================================
# C. Determinism
# ===========================================================================
class TestDeterminism:
    def test_same_snapshot_same_response_bytes(self):
        r1 = wip.build_response("GET", "/intelligence/alice")
        r2 = wip.build_response("GET", "/intelligence/alice")
        assert r1 == r2

    def test_repeated_calls_consistent(self):
        bodies = set()
        for _ in range(5):
            _, _, body = wip.build_response("GET", "/intelligence/alice")
            bodies.add(body)
        assert len(bodies) == 1

    def test_json_stable_via_real_server(self, server):
        s1, _, b1 = _http_get(f"{server}/intelligence/alice")
        s2, _, b2 = _http_get(f"{server}/intelligence/alice")
        assert s1 == s2 == 200
        assert b1 == b2


# ===========================================================================
# D. Error handling
# ===========================================================================
class TestErrorHandling:
    def test_malformed_user_id_slash_404(self):
        # `..` percent-encoded into a single user_id segment decodes to ".."
        status, _, body = wip.build_response("GET", "/intelligence/..")
        assert status == 404
        assert json.loads(body)["error"] == "invalid_user_id"

    def test_malformed_user_id_space_404(self):
        # Space char isn't in the allowed regex.
        status, _, _ = wip.build_response("GET", "/intelligence/alice%20bob")
        assert status == 404

    def test_user_id_too_long_404(self):
        long_uid = "a" * 200  # > 128
        status, _, body = wip.build_response("GET", f"/intelligence/{long_uid}")
        assert status == 404
        assert json.loads(body)["error"] == "invalid_user_id"

    def test_path_traversal_user_id_404(self):
        # `..%2Fadmin` decodes to "../admin" which fails the regex.
        status, _, _ = wip.build_response("GET", "/intelligence/..%2Fadmin")
        assert status == 404

    def test_wiring_raises_500(self, monkeypatch):
        def fails(uid):
            raise RuntimeError("simulated wiring failure")
        monkeypatch.setattr(rwi, "get_intelligence_snapshot", fails)
        status, _, body = wip.build_response("GET", "/intelligence/alice")
        assert status == 500
        err = json.loads(body)
        assert err["error"] == "wiring_failed"

    def test_wiring_returns_non_dict_500(self, monkeypatch):
        monkeypatch.setattr(rwi, "get_intelligence_snapshot", lambda uid: "not a dict")
        status, _, body = wip.build_response("GET", "/intelligence/alice")
        assert status == 500
        err = json.loads(body)
        assert err["error"] == "shape_mismatch"

    def test_404_returns_json_error_body(self):
        _, headers, body = wip.build_response("GET", "/no/such/route")
        assert headers["Content-Type"].startswith("application/json")
        err = json.loads(body)
        assert "error" in err and "message" in err

    def test_500_returns_json_error_body(self, monkeypatch):
        monkeypatch.setattr(
            rwi, "get_intelligence_snapshot",
            lambda uid: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        _, headers, body = wip.build_response("GET", "/intelligence/alice")
        assert headers["Content-Type"].startswith("application/json")
        err = json.loads(body)
        assert "error" in err


# ===========================================================================
# E. URL routing
# ===========================================================================
class TestURLRouting:
    def test_intelligence_alice_matches(self):
        status, _, _ = wip.build_response("GET", "/intelligence/alice")
        assert status == 200

    def test_trailing_slash_ok(self):
        status, _, _ = wip.build_response("GET", "/intelligence/alice/")
        assert status == 200

    def test_unknown_path_404(self):
        status, _, _ = wip.build_response("GET", "/foo/bar")
        assert status == 404

    def test_bare_intelligence_path_404(self):
        status, _, _ = wip.build_response("GET", "/intelligence")
        assert status == 404

    def test_intelligence_with_empty_segment_404(self):
        status, _, _ = wip.build_response("GET", "/intelligence/")
        assert status == 404

    def test_extra_segments_404(self):
        status, _, _ = wip.build_response("GET", "/intelligence/alice/extra")
        assert status == 404

    def test_query_string_ignored(self):
        status, _, body = wip.build_response("GET", "/intelligence/alice?debug=1")
        assert status == 200
        assert json.loads(body)["date"] == "2026-05-11"


# ===========================================================================
# F. HTML serving
# ===========================================================================
class TestHTMLServing:
    def test_root_serves_html(self):
        status, headers, body = wip.build_response("GET", "/")
        assert status == 200
        assert headers["Content-Type"].startswith("text/html")
        assert b"<!DOCTYPE html>" in body[:30]

    def test_named_path_serves_html(self):
        status, headers, body = wip.build_response("GET", "/intelligence_panel.html")
        assert status == 200
        assert headers["Content-Type"].startswith("text/html")
        assert b"<!DOCTYPE html>" in body[:30]

    def test_html_contains_user_input(self):
        _, _, body = wip.build_response("GET", "/")
        text = body.decode("utf-8")
        assert 'id="user-id"' in text
        assert "<input" in text

    def test_html_contains_load_button(self):
        _, _, body = wip.build_response("GET", "/")
        text = body.decode("utf-8")
        assert 'id="load-btn"' in text
        assert "<button" in text

    def test_html_contains_fetch_call(self):
        _, _, body = wip.build_response("GET", "/")
        text = body.decode("utf-8")
        assert "/intelligence/" in text
        assert "fetch(" in text

    def test_html_uses_monospace_font(self):
        _, _, body = wip.build_response("GET", "/")
        text = body.decode("utf-8").lower()
        assert "monospace" in text or "consolas" in text or "monaco" in text


# ===========================================================================
# G. Security
# ===========================================================================
class TestSecurity:
    def test_no_set_cookie_header(self):
        _, headers, _ = wip.build_response("GET", "/intelligence/alice")
        header_keys = {k.lower() for k in headers.keys()}
        assert "set-cookie" not in header_keys

    def test_cache_control_no_store(self):
        _, headers, _ = wip.build_response("GET", "/intelligence/alice")
        assert headers.get("Cache-Control") == "no-store"

    def test_x_content_type_options_nosniff(self):
        _, headers, _ = wip.build_response("GET", "/intelligence/alice")
        assert headers.get("X-Content-Type-Options") == "nosniff"

    def test_no_state_shared_between_requests(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            rwi, "get_intelligence_snapshot",
            lambda uid: (calls.append(uid), dict(_CANNED_SNAPSHOT))[1],
        )
        for uid in ("alice", "bob", "charlie"):
            wip.build_response("GET", f"/intelligence/{uid}")
        assert calls == ["alice", "bob", "charlie"]

    def test_html_escapes_in_js(self):
        """The panel JS includes an escapeHtml function so any displayed
        user input / JSON content can't smuggle HTML."""
        _, _, body = wip.build_response("GET", "/")
        text = body.decode("utf-8")
        assert "escapeHtml" in text
        # Confirms the escaping function targets the four critical chars.
        assert "&amp;" in text and "&lt;" in text and "&gt;" in text


# ===========================================================================
# H. HTML file integrity (static checks against the on-disk file)
# ===========================================================================
class TestHTMLFile:
    def test_html_file_exists(self):
        assert wip._HTML_PATH.exists()
        assert wip._HTML_PATH.is_file()

    def test_html_starts_with_doctype(self):
        text = wip._HTML_PATH.read_text(encoding="utf-8")
        assert text.lstrip().startswith("<!DOCTYPE html>")

    def test_html_has_required_elements(self):
        text = wip._HTML_PATH.read_text(encoding="utf-8")
        for required in (
            'id="user-id"',
            'id="load-btn"',
            'id="output"',
            'id="status"',
            'fetch(',
            '/intelligence/',
            'encodeURIComponent',
        ):
            assert required in text, f"missing in HTML: {required}"

    def test_html_no_external_scripts(self):
        text = wip._HTML_PATH.read_text(encoding="utf-8")
        # Only inline <script>...</script> blocks are allowed.
        external_script = re.search(r'<script[^>]+src=', text)
        assert external_script is None

    def test_html_no_external_stylesheets(self):
        text = wip._HTML_PATH.read_text(encoding="utf-8")
        # No <link rel="stylesheet" href="..."> allowed.
        external_link = re.search(r'<link[^>]+rel=["\']stylesheet', text)
        assert external_link is None

    def test_html_no_external_fetches_in_js(self):
        """Verify the JS only fetches relative paths (no http://, https://)."""
        text = wip._HTML_PATH.read_text(encoding="utf-8")
        # Find every fetch call's URL argument.
        for m in re.finditer(r"fetch\(\s*['\"]([^'\"]+)", text):
            url = m.group(1)
            # All fetches must start with `/` (same-origin) or be a relative path.
            assert url.startswith("/") or not url.startswith(("http://", "https://")), (
                f"external URL in fetch: {url}"
            )

    def test_html_uses_credentials_omit(self):
        text = wip._HTML_PATH.read_text(encoding="utf-8")
        assert 'credentials: "omit"' in text or "credentials:'omit'" in text


# ===========================================================================
# I. Real-server integration
# ===========================================================================
class TestRealServer:
    def test_real_server_200(self, server):
        status, headers, body = _http_get(f"{server}/intelligence/alice")
        assert status == 200
        assert headers.get("Content-Type", "").startswith("application/json")
        data = json.loads(body)
        assert set(data.keys()) == {"date", "daily_elins", "news", "email", "micro", "macro"}

    def test_real_server_404_for_bad_route(self, server):
        status, _, body = _http_get(f"{server}/no/such/route")
        assert status == 404
        err = json.loads(body)
        assert err["error"] == "not_found"

    def test_real_server_404_for_invalid_user_id(self, server):
        status, _, body = _http_get(f"{server}/intelligence/" + "a" * 200)
        assert status == 404
        assert json.loads(body)["error"] == "invalid_user_id"

    def test_real_server_serves_html(self, server):
        status, headers, body = _http_get(f"{server}/")
        assert status == 200
        assert headers.get("Content-Type", "").startswith("text/html")
        assert b"<!DOCTYPE html>" in body[:30]

    def test_real_server_500_on_wiring_failure(self, server, monkeypatch):
        def fails(uid):
            raise RuntimeError("simulated")
        monkeypatch.setattr(rwi, "get_intelligence_snapshot", fails)
        status, _, body = _http_get(f"{server}/intelligence/alice")
        assert status == 500
        err = json.loads(body)
        assert err["error"] == "wiring_failed"

    def test_real_server_non_get_method(self, server):
        # urllib doesn't easily allow POST without a body; use a Request.
        status, _, _ = _http_get(f"{server}/intelligence/alice", method="DELETE")
        # BaseHTTPRequestHandler returns 501 for unsupported methods.
        # Our handler only implements do_GET, so DELETE → 501.
        assert status in (405, 501)

    def test_real_server_cache_control(self, server):
        _, headers, _ = _http_get(f"{server}/intelligence/alice")
        assert headers.get("Cache-Control") == "no-store"

    def test_real_server_no_set_cookie(self, server):
        _, headers, _ = _http_get(f"{server}/intelligence/alice")
        # urllib lowercases all header keys in dict()
        keys = {k.lower() for k in headers.keys()}
        assert "set-cookie" not in keys
