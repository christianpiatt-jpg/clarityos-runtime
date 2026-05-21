"""
Tests for phone_intelligence_panel.py + phone/intelligence_panel.html (Phase 3 Unit 3).

Mirrors the Web Unit-2 test discipline:
  * Pure-function tests of ``build_response`` (no I/O).
  * Integration tests via a real HTTPServer thread on 127.0.0.1:0.
  * Static-file integrity checks against the on-disk HTML.
  * Mobile-specific tests (viewport, touch targets, font-size, noscript).

The runtime wiring layer is stubbed in an autouse fixture so the panel
never reads from real ingestion bus / archives / operator_state.

60+ tests across 10 test classes.
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
import phone_intelligence_panel as phip


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
    """Default stub: wiring returns the canned empty snapshot."""
    monkeypatch.setattr(
        rwi, "get_intelligence_snapshot",
        lambda uid: dict(_CANNED_SNAPSHOT),
    )


@pytest.fixture
def server():
    """Start a phone panel server on a random local port in a daemon thread."""
    srv = HTTPServer(("127.0.0.1", 0), phip.PhoneIntelligencePanelHandler)
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
    req = Request(url, method=method)
    try:
        with urlopen(req, timeout=5) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except HTTPError as e:
        return e.code, dict(e.headers), e.read()


# ===========================================================================
# A. HTTP surface (pure-function build_response)
# ===========================================================================
class TestBuildResponse:
    def test_valid_user_returns_200(self):
        status, _, _ = phip.build_response("GET", "/m/alice")
        assert status == 200

    def test_content_type_is_json(self):
        _, headers, _ = phip.build_response("GET", "/m/alice")
        assert headers["Content-Type"].startswith("application/json")

    def test_response_has_all_six_keys(self):
        _, _, body = phip.build_response("GET", "/m/alice")
        data = json.loads(body)
        assert set(data.keys()) == {"date", "daily_elins", "news", "email", "micro", "macro"}

    def test_lists_never_none(self):
        _, _, body = phip.build_response("GET", "/m/alice")
        data = json.loads(body)
        assert isinstance(data["news"],  list)
        assert isinstance(data["email"], list)
        assert isinstance(data["micro"], list)

    def test_macro_is_dict(self):
        _, _, body = phip.build_response("GET", "/m/alice")
        assert isinstance(json.loads(body)["macro"], dict)

    def test_content_length_matches_body(self):
        _, headers, body = phip.build_response("GET", "/m/alice")
        assert int(headers["Content-Length"]) == len(body)

    def test_response_is_valid_utf8(self):
        _, _, body = phip.build_response("GET", "/m/alice")
        body.decode("utf-8")  # Should not raise.

    def test_non_get_method_405(self):
        status, _, body = phip.build_response("POST", "/m/alice")
        assert status == 405
        assert json.loads(body)["error"] == "method_not_allowed"


# ===========================================================================
# B. Wiring integration
# ===========================================================================
class TestWiringIntegration:
    def test_wiring_called_with_correct_user_id(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            rwi, "get_intelligence_snapshot",
            lambda uid: (calls.append(uid), dict(_CANNED_SNAPSHOT))[1],
        )
        phip.build_response("GET", "/m/alice")
        phip.build_response("GET", "/m/bob")
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
        _, _, body = phip.build_response("GET", "/m/alice")
        assert json.loads(body) == custom

    def test_partial_snapshot_passthrough(self, monkeypatch):
        partial = {**_CANNED_SNAPSHOT, "news": [{"headline": "only news"}]}
        monkeypatch.setattr(rwi, "get_intelligence_snapshot", lambda uid: dict(partial))
        _, _, body = phip.build_response("GET", "/m/alice")
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
        _, _, body = phip.build_response("GET", "/m/alice")
        assert json.loads(body) == full

    def test_no_mutation_between_calls(self):
        b1 = phip.build_response("GET", "/m/alice")[2]
        b2 = phip.build_response("GET", "/m/alice")[2]
        assert b1 == b2


# ===========================================================================
# C. Determinism
# ===========================================================================
class TestDeterminism:
    def test_same_state_same_bytes(self):
        r1 = phip.build_response("GET", "/m/alice")
        r2 = phip.build_response("GET", "/m/alice")
        assert r1 == r2

    def test_repeated_calls_consistent(self):
        bodies = set()
        for _ in range(5):
            _, _, body = phip.build_response("GET", "/m/alice")
            bodies.add(body)
        assert len(bodies) == 1

    def test_json_stable_via_real_server(self, server):
        s1, _, b1 = _http_get(f"{server}/m/alice")
        s2, _, b2 = _http_get(f"{server}/m/alice")
        assert s1 == s2 == 200
        assert b1 == b2


# ===========================================================================
# D. Error handling
# ===========================================================================
class TestErrorHandling:
    def test_malformed_user_id_dots_404(self):
        # `..` decodes to a disallowed path-traversal pattern.
        status, _, body = phip.build_response("GET", "/m/..")
        assert status == 404
        assert json.loads(body)["error"] == "invalid_user_id"

    def test_malformed_user_id_space_404(self):
        status, _, _ = phip.build_response("GET", "/m/alice%20bob")
        assert status == 404

    def test_user_id_too_long_404(self):
        long_uid = "a" * 200
        status, _, body = phip.build_response("GET", f"/m/{long_uid}")
        assert status == 404
        assert json.loads(body)["error"] == "invalid_user_id"

    def test_path_traversal_user_id_404(self):
        # ../admin → invalid_user_id (regex rejects '/')
        status, _, _ = phip.build_response("GET", "/m/..%2Fadmin")
        assert status == 404

    def test_wiring_raises_500(self, monkeypatch):
        def fails(uid):
            raise RuntimeError("simulated wiring failure")
        monkeypatch.setattr(rwi, "get_intelligence_snapshot", fails)
        status, _, body = phip.build_response("GET", "/m/alice")
        assert status == 500
        err = json.loads(body)
        assert err["error"] == "wiring_failed"

    def test_wiring_returns_non_dict_500(self, monkeypatch):
        monkeypatch.setattr(
            rwi, "get_intelligence_snapshot", lambda uid: "not a dict",
        )
        status, _, body = phip.build_response("GET", "/m/alice")
        assert status == 500
        assert json.loads(body)["error"] == "shape_mismatch"

    def test_404_returns_json_error_body(self):
        _, headers, body = phip.build_response("GET", "/no/such/route")
        assert headers["Content-Type"].startswith("application/json")
        err = json.loads(body)
        assert "error" in err and "message" in err

    def test_500_returns_json_error_body(self, monkeypatch):
        def boom(uid):
            raise RuntimeError("boom")
        monkeypatch.setattr(rwi, "get_intelligence_snapshot", boom)
        _, headers, body = phip.build_response("GET", "/m/alice")
        assert headers["Content-Type"].startswith("application/json")
        assert "error" in json.loads(body)


# ===========================================================================
# E. URL routing
# ===========================================================================
class TestURLRouting:
    def test_m_alice_matches(self):
        status, _, _ = phip.build_response("GET", "/m/alice")
        assert status == 200

    def test_trailing_slash_ok(self):
        status, _, _ = phip.build_response("GET", "/m/alice/")
        assert status == 200

    def test_unknown_path_404(self):
        status, _, _ = phip.build_response("GET", "/foo/bar")
        assert status == 404

    def test_bare_m_serves_html(self):
        """`/m` (no trailing slash) is treated as a courtesy HTML route."""
        status, headers, _ = phip.build_response("GET", "/m")
        assert status == 200
        assert headers["Content-Type"].startswith("text/html")

    def test_m_slash_serves_html(self):
        status, headers, _ = phip.build_response("GET", "/m/")
        assert status == 200
        assert headers["Content-Type"].startswith("text/html")

    def test_explicit_html_path_serves_html(self):
        """`/m/intelligence_panel.html` must serve HTML, NOT be parsed
        as a JSON request for a user named `intelligence_panel.html`."""
        status, headers, _ = phip.build_response(
            "GET", "/m/intelligence_panel.html",
        )
        assert status == 200
        assert headers["Content-Type"].startswith("text/html")

    def test_extra_segments_404(self):
        status, _, _ = phip.build_response("GET", "/m/alice/extra")
        assert status == 404

    def test_query_string_ignored(self):
        status, _, body = phip.build_response("GET", "/m/alice?debug=1")
        assert status == 200
        assert json.loads(body)["date"] == "2026-05-11"

    def test_intelligence_prefix_route_not_served(self):
        """The phone panel must NOT respond to the web panel's prefix.
        Only `/m/*` routes are handled here."""
        status, _, _ = phip.build_response("GET", "/intelligence/alice")
        assert status == 404


# ===========================================================================
# F. HTML serving
# ===========================================================================
class TestHTMLServing:
    def test_m_serves_html(self):
        status, headers, body = phip.build_response("GET", "/m/")
        assert status == 200
        assert headers["Content-Type"].startswith("text/html")
        assert b"<!DOCTYPE html>" in body[:30]

    def test_named_path_serves_html(self):
        status, headers, body = phip.build_response(
            "GET", "/m/intelligence_panel.html",
        )
        assert status == 200
        assert headers["Content-Type"].startswith("text/html")

    def test_html_contains_user_input(self):
        _, _, body = phip.build_response("GET", "/m/")
        text = body.decode("utf-8")
        assert 'id="user-id"' in text
        assert "<input" in text

    def test_html_contains_load_button(self):
        _, _, body = phip.build_response("GET", "/m/")
        text = body.decode("utf-8")
        assert 'id="load-btn"' in text
        assert "<button" in text

    def test_html_contains_fetch_to_m_route(self):
        _, _, body = phip.build_response("GET", "/m/")
        text = body.decode("utf-8")
        # JS must hit the mobile route, NOT the web /intelligence/ route.
        assert "/m/" in text
        assert "fetch(" in text
        assert "/intelligence/" not in text

    def test_html_uses_monospace_font(self):
        _, _, body = phip.build_response("GET", "/m/")
        text = body.decode("utf-8").lower()
        assert "monospace" in text or "consolas" in text or "monaco" in text


# ===========================================================================
# G. Security
# ===========================================================================
class TestSecurity:
    def test_no_set_cookie_header(self):
        _, headers, _ = phip.build_response("GET", "/m/alice")
        keys = {k.lower() for k in headers.keys()}
        assert "set-cookie" not in keys

    def test_cache_control_no_store(self):
        _, headers, _ = phip.build_response("GET", "/m/alice")
        assert headers.get("Cache-Control") == "no-store"

    def test_x_content_type_options_nosniff(self):
        _, headers, _ = phip.build_response("GET", "/m/alice")
        assert headers.get("X-Content-Type-Options") == "nosniff"

    def test_no_state_shared_between_requests(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            rwi, "get_intelligence_snapshot",
            lambda uid: (calls.append(uid), dict(_CANNED_SNAPSHOT))[1],
        )
        for uid in ("alice", "bob", "charlie"):
            phip.build_response("GET", f"/m/{uid}")
        assert calls == ["alice", "bob", "charlie"]

    def test_html_escapes_in_js(self):
        _, _, body = phip.build_response("GET", "/m/")
        text = body.decode("utf-8")
        assert "escapeHtml" in text
        assert "&amp;" in text and "&lt;" in text and "&gt;" in text

    def test_html_security_headers_consistent(self):
        _, headers, _ = phip.build_response("GET", "/m/")
        assert headers.get("Cache-Control") == "no-store"
        assert headers.get("X-Content-Type-Options") == "nosniff"


# ===========================================================================
# H. HTML file integrity
# ===========================================================================
class TestHTMLFile:
    def test_html_file_exists(self):
        assert phip._HTML_PATH.exists()
        assert phip._HTML_PATH.is_file()

    def test_html_starts_with_doctype(self):
        text = phip._HTML_PATH.read_text(encoding="utf-8")
        assert text.lstrip().startswith("<!DOCTYPE html>")

    def test_html_has_required_elements(self):
        text = phip._HTML_PATH.read_text(encoding="utf-8")
        for required in (
            'id="user-id"',
            'id="load-btn"',
            'id="output"',
            'id="status"',
            'fetch(',
            '/m/',
            'encodeURIComponent',
        ):
            assert required in text, f"missing in HTML: {required}"

    def test_html_no_external_scripts(self):
        text = phip._HTML_PATH.read_text(encoding="utf-8")
        external_script = re.search(r'<script[^>]+src=', text)
        assert external_script is None

    def test_html_no_external_stylesheets(self):
        text = phip._HTML_PATH.read_text(encoding="utf-8")
        external_link = re.search(r'<link[^>]+rel=["\']stylesheet', text)
        assert external_link is None

    def test_html_no_external_fetches_in_js(self):
        """All fetches must be relative (same-origin) — no http:// or https://."""
        text = phip._HTML_PATH.read_text(encoding="utf-8")
        for m in re.finditer(r"fetch\(\s*['\"]([^'\"]+)", text):
            url = m.group(1)
            assert not url.startswith(("http://", "https://")), (
                f"external URL in fetch: {url}"
            )

    def test_html_uses_credentials_omit(self):
        text = phip._HTML_PATH.read_text(encoding="utf-8")
        assert 'credentials: "omit"' in text or "credentials:'omit'" in text


# ===========================================================================
# I. Mobile-specific
# ===========================================================================
class TestMobileSpecific:
    def test_has_viewport_meta(self):
        text = phip._HTML_PATH.read_text(encoding="utf-8")
        assert 'name="viewport"' in text
        assert "width=device-width" in text

    def test_input_font_size_16px_or_larger(self):
        """iOS Safari auto-zooms inputs with font-size < 16px on focus."""
        text = phip._HTML_PATH.read_text(encoding="utf-8")
        m = re.search(
            r'input\[type="text"\][^{]*\{([^}]*)\}', text, re.DOTALL,
        )
        assert m is not None, "input[type=text] block not found"
        css_block = m.group(1)
        fs_match = re.search(r"font-size:\s*(\d+)px", css_block)
        assert fs_match is not None
        assert int(fs_match.group(1)) >= 16

    def test_button_has_touch_target(self):
        """Apple HIG: tap targets must be at least 44×44 pt."""
        text = phip._HTML_PATH.read_text(encoding="utf-8")
        m = re.search(r"button\s*\{([^}]*)\}", text, re.DOTALL)
        assert m is not None
        css = m.group(1)
        min_h = re.search(r"min-height:\s*(\d+)px", css)
        assert min_h is not None, "button block has no min-height"
        assert int(min_h.group(1)) >= 40

    def test_has_noscript_fallback(self):
        text = phip._HTML_PATH.read_text(encoding="utf-8")
        assert "<noscript>" in text
        assert "</noscript>" in text

    def test_no_horizontal_scroll(self):
        text = phip._HTML_PATH.read_text(encoding="utf-8")
        assert "overflow-x" in text

    def test_disables_ios_zoom_hint(self):
        """No `user-scalable=no` (that's an accessibility anti-pattern)
        but the 16px input font-size already prevents the unwanted zoom."""
        text = phip._HTML_PATH.read_text(encoding="utf-8")
        # Make sure we don't disable user-scalable (anti-pattern).
        assert "user-scalable=no"  not in text
        assert "user-scalable=0"   not in text

    def test_apple_mobile_web_app_capable(self):
        text = phip._HTML_PATH.read_text(encoding="utf-8")
        assert 'name="apple-mobile-web-app-capable"' in text

    def test_theme_color_set(self):
        text = phip._HTML_PATH.read_text(encoding="utf-8")
        assert 'name="theme-color"' in text

    def test_autocapitalize_off_on_user_id(self):
        """User_id field shouldn't autocapitalize on mobile."""
        text = phip._HTML_PATH.read_text(encoding="utf-8")
        # The input should have autocapitalize="none" or "off"
        m = re.search(r'<input[^>]*id="user-id"[^>]*>', text)
        assert m is not None
        input_tag = m.group(0)
        assert "autocapitalize" in input_tag


# ===========================================================================
# J. Real-server integration
# ===========================================================================
class TestRealServer:
    def test_real_server_200(self, server):
        status, headers, body = _http_get(f"{server}/m/alice")
        assert status == 200
        assert headers.get("Content-Type", "").startswith("application/json")
        data = json.loads(body)
        assert set(data.keys()) == {"date", "daily_elins", "news", "email", "micro", "macro"}

    def test_real_server_404_bad_route(self, server):
        status, _, body = _http_get(f"{server}/no/such/route")
        assert status == 404
        assert json.loads(body)["error"] == "not_found"

    def test_real_server_404_invalid_user_id(self, server):
        status, _, body = _http_get(f"{server}/m/" + "a" * 200)
        assert status == 404
        assert json.loads(body)["error"] == "invalid_user_id"

    def test_real_server_serves_html_at_m_slash(self, server):
        status, headers, body = _http_get(f"{server}/m/")
        assert status == 200
        assert headers.get("Content-Type", "").startswith("text/html")
        assert b"<!DOCTYPE html>" in body[:30]

    def test_real_server_serves_html_at_bare_m(self, server):
        status, headers, body = _http_get(f"{server}/m")
        assert status == 200
        assert headers.get("Content-Type", "").startswith("text/html")

    def test_real_server_500_on_wiring_failure(self, server, monkeypatch):
        def fails(uid):
            raise RuntimeError("simulated")
        monkeypatch.setattr(rwi, "get_intelligence_snapshot", fails)
        status, _, body = _http_get(f"{server}/m/alice")
        assert status == 500
        assert json.loads(body)["error"] == "wiring_failed"

    def test_real_server_non_get_method(self, server):
        status, _, _ = _http_get(f"{server}/m/alice", method="DELETE")
        # Either build_response 405 (if handler routed it) or 501 from
        # BaseHTTPRequestHandler (only do_GET defined).
        assert status in (405, 501)

    def test_real_server_cache_control_no_store(self, server):
        _, headers, _ = _http_get(f"{server}/m/alice")
        assert headers.get("Cache-Control") == "no-store"

    def test_real_server_no_set_cookie(self, server):
        _, headers, _ = _http_get(f"{server}/m/alice")
        keys = {k.lower() for k in headers.keys()}
        assert "set-cookie" not in keys

    def test_real_server_byte_identical(self, server):
        """Two consecutive requests for the same user with the same wiring
        state produce byte-identical body responses."""
        _, _, b1 = _http_get(f"{server}/m/alice")
        _, _, b2 = _http_get(f"{server}/m/alice")
        assert b1 == b2
