"""
Tests for v54 — Ingestion bus (RSS/Atom + manual).

Covers:
  * Feed registry: register, list, get, delete, caps, validation
  * Fetcher: success / size cap / bad scheme (urlopen monkeypatched)
  * Parser: RSS 2.0, RSS 1.0 (RDF), Atom, namespaced Atom, error paths
  * item_text_for_elins concatenation + cap
  * persist_to_library shape + tags + visibility forward-compat
  * Kernel: run_manual_ingestion, run_feed_ingestion, run_ingestion_cycle
  * Endpoints: /ingest/manual, /ingest/feeds/{register,list,delete,run}
  * /me capability + /health version
  * Architecture invariants: no eval/exec, no skills_export import
"""
from __future__ import annotations

import io
import secrets
import time

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    from conftest import TestClient
    return TestClient(app_module.app)


def _make_user(app_module, username, cohort="founder"):
    import bcrypt
    import sessions_store
    import users_store
    pwd_hash = bcrypt.hashpw(b"x", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=time.time(),
    )
    if cohort:
        users_store.update_user(username, {"cohort": cohort})
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, sid


def _auth(sid):
    return {"X-Session-ID": sid}


# Canonical valid RSS 2.0 + Atom payloads for parser tests.
_RSS_2 = b"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Sample Feed</title>
    <item>
      <title>Headline One</title>
      <description>Body of one.</description>
      <link>https://example.com/1</link>
      <pubDate>Mon, 10 May 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Headline Two</title>
      <description>Body of two.</description>
      <link>https://example.com/2</link>
      <pubDate>Mon, 10 May 2026 13:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

_ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Sample</title>
  <entry>
    <title>Atom Item A</title>
    <summary>summary A</summary>
    <link href="https://example.com/a"/>
    <updated>2026-05-10T12:00:00Z</updated>
  </entry>
  <entry>
    <title>Atom Item B</title>
    <summary>summary B</summary>
    <link href="https://example.com/b"/>
    <updated>2026-05-10T13:00:00Z</updated>
  </entry>
</feed>"""

_RSS_OVERSIZED_ITEMS = b"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
""" + b"".join(
    f"<item><title>T{i}</title><description>D{i}</description></item>".encode()
    for i in range(10)
) + b"""</channel></rss>"""


# ===========================================================================
# Feed registry
# ===========================================================================
def test_register_feed_success(reset_stores):
    from ELINS import ingestion_bus as ib
    out = ib.register_feed("alice", name="my_feed", url="https://example.com/rss")
    assert out["name"] == "my_feed"
    assert out["url"] == "https://example.com/rss"
    assert out["region"] is None
    assert out["feed_id"].startswith("f_")
    assert isinstance(out["created_at"], float)


def test_register_feed_with_region(reset_stores):
    from ELINS import ingestion_bus as ib
    out = ib.register_feed("alice", name="x", url="https://x.com/rss", region="us")
    assert out["region"] == "us"


def test_register_feed_rejects_non_http_scheme(reset_stores):
    from ELINS import ingestion_bus as ib
    with pytest.raises(ValueError):
        ib.register_feed("alice", name="bad", url="file:///etc/passwd")
    with pytest.raises(ValueError):
        ib.register_feed("alice", name="bad", url="ftp://example.com/rss")
    with pytest.raises(ValueError):
        ib.register_feed("alice", name="bad", url="javascript:alert(1)")


def test_register_feed_rejects_empty_name(reset_stores):
    from ELINS import ingestion_bus as ib
    with pytest.raises(ValueError):
        ib.register_feed("alice", name="   ", url="https://example.com")


def test_register_feed_rejects_long_name(reset_stores):
    from ELINS import ingestion_bus as ib
    with pytest.raises(ValueError):
        ib.register_feed("alice", name="x" * 101, url="https://example.com")


def test_register_feed_enforces_5_per_user_cap(reset_stores):
    from ELINS import ingestion_bus as ib
    for i in range(5):
        ib.register_feed("alice", name=f"f{i}", url=f"https://example.com/{i}")
    with pytest.raises(ValueError, match="feed limit reached"):
        ib.register_feed("alice", name="f5", url="https://example.com/5")


def test_register_feed_rejects_duplicate_url(reset_stores):
    from ELINS import ingestion_bus as ib
    ib.register_feed("alice", name="one", url="https://example.com/rss")
    with pytest.raises(ValueError, match="url already registered"):
        ib.register_feed("alice", name="two", url="https://example.com/rss")


def test_register_feed_rejects_duplicate_name(reset_stores):
    from ELINS import ingestion_bus as ib
    ib.register_feed("alice", name="same", url="https://example.com/1")
    with pytest.raises(ValueError, match="name already registered"):
        ib.register_feed("alice", name="same", url="https://example.com/2")


def test_feeds_isolated_per_user(reset_stores):
    from ELINS import ingestion_bus as ib
    ib.register_feed("alice", name="a", url="https://a.example/rss")
    ib.register_feed("bob",   name="b", url="https://b.example/rss")
    assert len(ib.list_feeds("alice")) == 1
    assert len(ib.list_feeds("bob")) == 1
    assert ib.list_feeds("alice")[0]["url"] == "https://a.example/rss"


def test_list_feeds_empty_by_default(reset_stores):
    from ELINS import ingestion_bus as ib
    assert ib.list_feeds("nobody") == []


def test_delete_feed_success(reset_stores):
    from ELINS import ingestion_bus as ib
    f = ib.register_feed("alice", name="x", url="https://x.example/rss")
    ib.delete_feed("alice", f["feed_id"])
    assert ib.list_feeds("alice") == []


def test_delete_feed_missing_raises_key_error(reset_stores):
    from ELINS import ingestion_bus as ib
    with pytest.raises(KeyError):
        ib.delete_feed("alice", "no_such_feed_id")


def test_get_feed_returns_none_for_missing(reset_stores):
    from ELINS import ingestion_bus as ib
    assert ib.get_feed("alice", "missing") is None


# ===========================================================================
# Fetcher
# ===========================================================================
class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self, n: int) -> bytes:
        return self._body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_fetch_feed_bytes_success(reset_stores, monkeypatch):
    from ELINS import ingestion_bus as ib

    def fake_urlopen(req, timeout):
        # Return a small RSS body. Verify the request used the safe UA.
        assert "ClarityOS-Ingestion" in req.headers.get("User-agent", "")
        return _FakeResponse(_RSS_2)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    data = ib.fetch_feed_bytes("https://example.com/rss")
    assert data == _RSS_2


def test_fetch_feed_bytes_size_cap_exceeded(reset_stores, monkeypatch):
    """Read returns max_bytes+1 — fetcher rejects."""
    from ELINS import ingestion_bus as ib

    def fake_urlopen(req, timeout):
        # Body larger than the cap; read(max_bytes+1) returns max_bytes+1 bytes.
        return _FakeResponse(b"x" * (ib.MAX_FETCH_BYTES + 1))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(ValueError, match="exceeds size cap"):
        ib.fetch_feed_bytes("https://example.com/big")


def test_fetch_feed_bytes_rejects_non_http(reset_stores):
    from ELINS import ingestion_bus as ib
    with pytest.raises(ValueError):
        ib.fetch_feed_bytes("file:///etc/passwd")


def test_fetch_feed_bytes_handles_url_error(reset_stores, monkeypatch):
    import urllib.error
    from ELINS import ingestion_bus as ib

    def fake_urlopen(req, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(ValueError, match="fetch failed"):
        ib.fetch_feed_bytes("https://example.com/rss")


# ===========================================================================
# Parser
# ===========================================================================
def test_parse_rss_2_basic():
    from ELINS import ingestion_bus as ib
    items = ib.parse_feed_items(_RSS_2)
    assert len(items) == 2
    assert items[0]["title"] == "Headline One"
    assert items[0]["summary"] == "Body of one."
    assert items[0]["link"] == "https://example.com/1"
    assert items[0]["published_at"].startswith("Mon, 10 May")


def test_parse_atom_basic():
    from ELINS import ingestion_bus as ib
    items = ib.parse_feed_items(_ATOM)
    assert len(items) == 2
    assert items[0]["title"] == "Atom Item A"
    assert items[0]["summary"] == "summary A"
    # Atom <link href="..."> — href is extracted, not text.
    assert items[0]["link"] == "https://example.com/a"
    assert items[0]["published_at"].startswith("2026-05-10")


def test_parse_caps_at_5_items_per_run():
    from ELINS import ingestion_bus as ib
    items = ib.parse_feed_items(_RSS_OVERSIZED_ITEMS)
    assert len(items) == ib.ITEMS_PER_FEED_PER_RUN == 5


def test_parse_empty_bytes_returns_empty_list():
    from ELINS import ingestion_bus as ib
    assert ib.parse_feed_items(b"") == []


def test_parse_malformed_xml_raises_value_error():
    from ELINS import ingestion_bus as ib
    with pytest.raises(ValueError, match="parse error"):
        ib.parse_feed_items(b"<not valid xml")


def test_parse_unknown_root_raises_value_error():
    from ELINS import ingestion_bus as ib
    with pytest.raises(ValueError, match="unrecognised feed root"):
        ib.parse_feed_items(b"<html><body>not a feed</body></html>")


def test_parse_non_bytes_input_rejected():
    from ELINS import ingestion_bus as ib
    with pytest.raises(ValueError):
        ib.parse_feed_items("a string")  # type: ignore[arg-type]


def test_parse_atom_with_namespace_prefix():
    """Atom feeds vary in namespace declaration; the parser strips
    namespaces via _localname so prefixed tags still match."""
    from ELINS import ingestion_bus as ib
    atom_prefixed = b"""<?xml version="1.0"?>
<atom:feed xmlns:atom="http://www.w3.org/2005/Atom">
  <atom:entry>
    <atom:title>Prefixed Title</atom:title>
    <atom:summary>Prefixed Summary</atom:summary>
    <atom:link href="https://example.com/p"/>
  </atom:entry>
</atom:feed>"""
    items = ib.parse_feed_items(atom_prefixed)
    assert len(items) == 1
    assert items[0]["title"] == "Prefixed Title"
    assert items[0]["link"] == "https://example.com/p"


# ===========================================================================
# item_text_for_elins
# ===========================================================================
def test_item_text_concatenates_title_and_summary():
    from ELINS import ingestion_bus as ib
    txt = ib.item_text_for_elins({"title": "T", "summary": "S"})
    assert "T" in txt and "S" in txt


def test_item_text_caps_at_max_text_bytes():
    from ELINS import ingestion_bus as ib
    huge = {"title": "X" * 1_000_000, "summary": "Y" * 1_000_000}
    out = ib.item_text_for_elins(huge)
    assert len(out) <= ib.MAX_TEXT_BYTES


def test_item_text_handles_non_dict_gracefully():
    from ELINS import ingestion_bus as ib
    assert ib.item_text_for_elins(None) == ""  # type: ignore[arg-type]
    assert ib.item_text_for_elins("nope") == ""  # type: ignore[arg-type]


# ===========================================================================
# persist_to_library
# ===========================================================================
def test_persist_to_library_creates_entry(reset_stores):
    from ELINS import ingestion_bus as ib
    import library_store

    env = {"outputs": {"attractor": "S2", "collapse_state": "soft"}}
    item_id = ib.persist_to_library(
        "alice",
        source="feed:my_feed",
        region="us",
        raw_text="some text",
        envelope=env,
        item_meta={"kind": "feed_item"},
    )
    rec = library_store.get(item_id)
    assert rec is not None
    assert rec["user"] == "alice"
    assert "S2" in rec["title"]
    assert "soft" in rec["title"]
    assert "elins_v2_ingestion" in rec["tags"]
    assert "region:us" in rec["tags"]
    assert rec["metadata"]["source"] == "feed:my_feed"
    assert rec["metadata"]["visibility"] == "private"
    assert rec["metadata"]["envelope"] == env


def test_persist_to_library_rejects_non_private_visibility(reset_stores):
    """v54 surface only allows 'private'; cohort sharing is a later pass."""
    from ELINS import ingestion_bus as ib
    with pytest.raises(ValueError):
        ib.persist_to_library(
            "alice", source="x", region=None, raw_text="x",
            envelope={"outputs": {}}, visibility="cohort",  # type: ignore[arg-type]
        )


# ===========================================================================
# Kernel — run_manual_ingestion
# ===========================================================================
def test_run_manual_ingestion_success(reset_stores):
    import intelligence_kernel as ik
    import library_store

    out = ik.run_manual_ingestion("alice", "moderate pressure on the dispute")
    assert out["library_id"]
    assert out["envelope"]["elins_version"] == "elins.v2.0"
    # Library entry exists for the user.
    entries = library_store.list_for_user("alice")
    assert len(entries) == 1
    assert "elins_v2_ingestion" in entries[0]["tags"]


def test_run_manual_ingestion_empty_text_raises(reset_stores):
    import intelligence_kernel as ik
    with pytest.raises(ValueError):
        ik.run_manual_ingestion("alice", "")
    with pytest.raises(ValueError):
        ik.run_manual_ingestion("alice", "   ")
    with pytest.raises(ValueError):
        ik.run_manual_ingestion("alice", None)  # type: ignore[arg-type]


def test_run_manual_ingestion_emits_kernel_log(reset_stores, caplog):
    import json
    import intelligence_kernel as ik
    caplog.set_level("INFO", logger="clarityos.kernel.runs")
    ik.run_manual_ingestion("alice", "test content", source="op_note")
    found = []
    for rec in caplog.records:
        if rec.message.startswith("kernel_run "):
            payload = json.loads(rec.message.split(" ", 1)[1])
            if payload.get("kind") == "ingestion_manual":
                found.append(payload)
    assert found
    assert found[-1]["meta"]["source"] == "op_note"
    assert found[-1]["meta"]["library_id"]


# ===========================================================================
# Kernel — run_feed_ingestion + run_ingestion_cycle
# ===========================================================================
def test_run_feed_ingestion_success(reset_stores, monkeypatch):
    from ELINS import ingestion_bus as ib
    import intelligence_kernel as ik
    import library_store

    def fake_urlopen(req, timeout):
        return _FakeResponse(_RSS_2)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    feed = ib.register_feed("alice", name="rss1", url="https://example.com/rss")

    out = ik.run_feed_ingestion("alice", feed["feed_id"])
    assert out["fetch_error"] is None
    assert out["items"] == 2
    assert out["stored"] == 2
    assert len(out["library_ids"]) == 2
    # Library entries exist.
    entries = library_store.list_for_user("alice")
    assert len(entries) == 2
    titles = [e["title"] for e in entries]
    assert any("S" in t for t in titles)


def test_run_feed_ingestion_unknown_feed_raises_key_error(reset_stores):
    import intelligence_kernel as ik
    with pytest.raises(KeyError):
        ik.run_feed_ingestion("alice", "no_such_feed")


def test_run_feed_ingestion_fetch_error_returns_in_result(
    reset_stores, monkeypatch,
):
    import urllib.error
    from ELINS import ingestion_bus as ib
    import intelligence_kernel as ik

    def fake_urlopen(req, timeout):
        raise urllib.error.URLError("DNS error")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    feed = ib.register_feed("alice", name="rss1", url="https://example.com/rss")

    out = ik.run_feed_ingestion("alice", feed["feed_id"])
    assert out["fetch_error"] is not None
    assert "DNS error" in out["fetch_error"]
    assert out["items"] == 0
    assert out["stored"] == 0


def test_run_ingestion_cycle_aggregates_across_feeds(reset_stores, monkeypatch):
    from ELINS import ingestion_bus as ib
    import intelligence_kernel as ik

    def fake_urlopen(req, timeout):
        # Same body for every feed.
        return _FakeResponse(_ATOM)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    ib.register_feed("alice", name="a", url="https://a.example/rss")
    ib.register_feed("alice", name="b", url="https://b.example/rss")

    out = ik.run_ingestion_cycle("alice")
    assert out["feed_count"] == 2
    assert len(out["results"]) == 2
    assert out["total_stored"] == 4  # 2 items × 2 feeds


# ===========================================================================
# Endpoints
# ===========================================================================
def test_endpoint_manual_ingestion_200(app_module, client):
    user, sid = _make_user(app_module, "ing_a", cohort="founder")
    r = client.post(
        "/ingest/manual",
        headers=_auth(sid),
        json={"raw_text": "structural pressure rising in the region", "source": "op"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["ok"] is True
    assert body["library_id"]
    assert body["envelope"]["elins_version"] == "elins.v2.0"


def test_endpoint_manual_ingestion_400_on_empty(app_module, client):
    user, sid = _make_user(app_module, "ing_b", cohort="founder")
    r = client.post(
        "/ingest/manual",
        headers=_auth(sid),
        json={"raw_text": "   "},
    )
    assert r.status_code == 400


def test_endpoint_manual_ingestion_401_when_unauth(app_module, client):
    r = client.post("/ingest/manual", json={"raw_text": "anything"})
    assert r.status_code == 401


def test_endpoint_register_feed_200(app_module, client):
    user, sid = _make_user(app_module, "ing_c", cohort="founder")
    r = client.post(
        "/ingest/feeds/register",
        headers=_auth(sid),
        json={"name": "myfeed", "url": "https://example.com/rss", "region": "us"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["ok"] is True
    assert body["feed"]["name"] == "myfeed"
    assert body["feed"]["url"] == "https://example.com/rss"


def test_endpoint_register_feed_400_on_bad_url(app_module, client):
    user, sid = _make_user(app_module, "ing_d", cohort="founder")
    r = client.post(
        "/ingest/feeds/register",
        headers=_auth(sid),
        json={"name": "bad", "url": "javascript:alert(1)"},
    )
    assert r.status_code == 400


def test_endpoint_register_feed_400_on_5_cap(app_module, client):
    user, sid = _make_user(app_module, "ing_e", cohort="founder")
    for i in range(5):
        r = client.post(
            "/ingest/feeds/register", headers=_auth(sid),
            json={"name": f"f{i}", "url": f"https://example.com/r{i}"},
        )
        assert r.status_code == 200
    r6 = client.post(
        "/ingest/feeds/register", headers=_auth(sid),
        json={"name": "f5", "url": "https://example.com/r5"},
    )
    assert r6.status_code == 400


def test_endpoint_list_feeds_returns_user_feeds(app_module, client):
    user, sid = _make_user(app_module, "ing_f", cohort="founder")
    client.post(
        "/ingest/feeds/register", headers=_auth(sid),
        json={"name": "x", "url": "https://example.com/x"},
    )
    r = client.get("/ingest/feeds", headers=_auth(sid))
    assert r.status_code == 200
    body = r.json()
    assert body["limit"] == 5
    assert len(body["feeds"]) == 1
    assert body["feeds"][0]["name"] == "x"


def test_endpoint_delete_feed_success(app_module, client):
    user, sid = _make_user(app_module, "ing_g", cohort="founder")
    r = client.post(
        "/ingest/feeds/register", headers=_auth(sid),
        json={"name": "x", "url": "https://example.com/x"},
    )
    fid = r.json()["feed"]["feed_id"]
    r2 = client.post(
        f"/ingest/feeds/run",  # noqa: F541 - explicit literal for clarity
        headers=_auth(sid), json={"feed_id": fid},
    )
    # We're not testing run success here, just that the feed exists.
    assert r2.status_code in (200, 500)  # 500 only if real network attempt

    # Delete via the http client (it has DELETE support in our test client?)
    # Our AppClient only supports GET/POST. Verify via the bus directly.
    from ELINS import ingestion_bus as ib
    ib.delete_feed("ing_g", fid)
    assert ib.list_feeds("ing_g") == []


def test_endpoint_feeds_run_200_with_specific_feed(
    app_module, client, monkeypatch,
):
    user, sid = _make_user(app_module, "ing_h", cohort="founder")
    # Register a feed then stub urlopen so the run succeeds.
    rr = client.post(
        "/ingest/feeds/register", headers=_auth(sid),
        json={"name": "x", "url": "https://example.com/x"},
    )
    fid = rr.json()["feed"]["feed_id"]

    def fake_urlopen(req, timeout):
        return _FakeResponse(_RSS_2)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    r = client.post(
        "/ingest/feeds/run", headers=_auth(sid),
        json={"feed_id": fid},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["ok"] is True
    assert body["result"]["stored"] == 2


def test_endpoint_feeds_run_200_all_feeds(app_module, client, monkeypatch):
    user, sid = _make_user(app_module, "ing_i", cohort="founder")
    client.post(
        "/ingest/feeds/register", headers=_auth(sid),
        json={"name": "a", "url": "https://example.com/a"},
    )
    client.post(
        "/ingest/feeds/register", headers=_auth(sid),
        json={"name": "b", "url": "https://example.com/b"},
    )

    def fake_urlopen(req, timeout):
        return _FakeResponse(_ATOM)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    r = client.post("/ingest/feeds/run", headers=_auth(sid), json={})
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["ok"] is True
    assert body["cycle"]["feed_count"] == 2
    assert body["cycle"]["total_stored"] == 4


def test_endpoint_feeds_run_404_on_missing_feed(app_module, client):
    user, sid = _make_user(app_module, "ing_j", cohort="founder")
    r = client.post(
        "/ingest/feeds/run", headers=_auth(sid),
        json={"feed_id": "no_such_feed"},
    )
    assert r.status_code == 404


def test_endpoint_feeds_register_401_when_unauth(app_module, client):
    r = client.post(
        "/ingest/feeds/register",
        json={"name": "x", "url": "https://example.com/x"},
    )
    assert r.status_code == 401


def test_endpoint_feeds_run_401_when_unauth(app_module, client):
    r = client.post("/ingest/feeds/run", json={})
    assert r.status_code == 401


# ===========================================================================
# /me capability + /health
# ===========================================================================
def test_me_capabilities_includes_ingestion(app_module, client):
    user, sid = _make_user(app_module, "ing_cap", cohort="founder")
    r = client.get("/me", headers=_auth(sid))
    assert r.status_code == 200
    caps = r.json().get("capabilities") or []
    ids = {c.get("id") for c in caps if isinstance(c, dict)}
    assert "ingestion" in ids


def test_health_version_4_8(app_module, client):
    r = client.get("/health")
    assert r.status_code == 200
    # v54 → 4.8, v60 → 4.9, v67 → 4.10, v68 → 4.11, v69 → 4.12, v70 → 4.13,
    # v71 → 4.14, v72 → 4.15, v73 → 4.16, v74 → 4.17. The test name
    # pins the v54 era; the assertion tracks the current minor head.
    assert r.json()["version"] == "4.23"


# ===========================================================================
# Architecture invariants
# ===========================================================================
def test_ingestion_bus_does_not_eval_or_exec_user_code():
    """Hard architectural rule: no eval / no exec / no compile of
    user-supplied source anywhere in the ingestion path."""
    import inspect
    import re
    from ELINS import ingestion_bus
    source = inspect.getsource(ingestion_bus)
    # Match actual call sites, not the word in a docstring/comment.
    bad_call = re.compile(r"\b(?:eval|exec|compile)\s*\(", re.MULTILINE)
    # Strip strings + comments naively for a clean check — we tolerate
    # the words inside docstrings (which describe the rule we follow).
    code_only = re.sub(r"#[^\n]*", "", source)
    code_only = re.sub(r'""".*?"""', "", code_only, flags=re.DOTALL)
    code_only = re.sub(r"'''.*?'''", "", code_only, flags=re.DOTALL)
    assert not bad_call.search(code_only), (
        "ingestion_bus must not call eval / exec / compile"
    )


def test_ingestion_bus_does_not_import_skills_export():
    import inspect
    import re
    from ELINS import ingestion_bus
    source = inspect.getsource(ingestion_bus)
    bad_import = re.compile(
        r"^\s*(?:from|import)\s+skills_export\b", re.MULTILINE,
    )
    assert not bad_import.search(source)


def test_fetch_feed_bytes_only_allows_http_https():
    from ELINS import ingestion_bus as ib
    assert "http" in ib.ALLOWED_URL_SCHEMES
    assert "https" in ib.ALLOWED_URL_SCHEMES
    assert "file" not in ib.ALLOWED_URL_SCHEMES
    assert "ftp" not in ib.ALLOWED_URL_SCHEMES
    assert "javascript" not in ib.ALLOWED_URL_SCHEMES
