"""
#138 -- provenance: the basis column on the engine's own ledger.

Every library write lands with five nullable fields at the top level of
``metadata``: created_ts (the server's clock, always), origin_route (the
write site's own word -- library_write | ingest_manual | feed | elins_brief
-- or one of the two a client alone can know, personal | thread_footer),
origin_thread_id, origin_turn_id, run_id. The server stamps the first two;
the client may supply the other three and may not override the first two.
Anything else for origin_route is refused 400 -- a paste cannot claim it was
a feed. No backfill: items that predate the fields read "—" (#110), never
"", never "unknown". The three timeline kinds a library write emits are ONE
constant (timeline_store.LIBRARY_TIMELINE_KINDS), imported by the emit
sites -- never the literals (#287).
"""
from __future__ import annotations

import re
import secrets
import time
from pathlib import Path

import pytest

from conftest import TestClient, seed_controller

import library_store
import sessions_store
import timeline_store

_ROOT = Path(__file__).resolve().parents[1]
_RSS_ONE = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Feed</title>
<item><title>Headline</title><description>Body of one.</description>
<link>https://example.com/1</link><pubDate>Mon, 10 May 2026 12:00:00 GMT</pubDate></item>
</channel></rss>"""


@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    return TestClient(app_module.app)


def _member(username=None):
    """Active membership + the controller flag (require_active_entitlement,
    _require_founder) + a minted op_ id + a session."""
    import bcrypt
    import users_store
    username = username or f"lib_{secrets.token_hex(4)}@example.com"
    users_store.create_user(
        username=username, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="", tier="free", created_at=time.time(),
    )
    users_store.set_membership(username, tier="founding_500", price=50.0, status="active")
    seed_controller(username)
    users_store.update_user(username, {"operator_id": "op_" + secrets.token_urlsafe(12)})
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, {"X-Session-ID": sid}


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self, n: int) -> bytes:
        return self._body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# ===========================================================================
# (a) the four write paths stamp created_ts + origin_route server-side
# ===========================================================================
def test_a_library_write_stamps_and_a_client_created_ts_is_overwritten(client):
    import threads_vault
    user, h = _member()
    t0 = time.time()
    own = threads_vault.create_thread(user, title="mine")["thread_id"]
    r = client.post("/library/write", headers=h, json={
        "title": "note", "content": "x",
        "metadata": {"created_ts": 1.0, "origin_thread_id": f"  {own} ", "run_id": "r-1", "note": "kept"},
    })
    assert r.status_code == 200, r.text
    md = library_store.get(r.json()["item"]["id"])["metadata"]
    assert md["origin_route"] == "library_write"                  # the site's own word
    assert isinstance(md["created_ts"], float) and md["created_ts"] >= t0   # the server's clock, not 1.0
    assert md["origin_thread_id"] == own and md["run_id"] == "r-1" and md["origin_turn_id"] is None
    assert md["note"] == "kept"                                    # the rest of the client's metadata rides


def test_a_library_write_drops_a_thread_the_member_does_not_own(client):
    import threads_vault
    user, h = _member()
    other, _ = _member()
    theirs = threads_vault.create_thread(other, title="theirs")["thread_id"]
    r = client.post("/library/write", headers=h, json={
        "title": "note", "content": "x", "metadata": {"origin_thread_id": theirs},
    })
    assert r.status_code == 200
    assert library_store.get(r.json()["item"]["id"])["metadata"]["origin_thread_id"] is None


def test_a_ingest_manual_stamps_the_doors_word(client):
    user, h = _member()
    r = client.post("/ingest/manual", headers=h, json={"raw_text": "a paste", "source": "op"})
    assert r.status_code == 200, r.text
    md = library_store.get(r.json()["library_id"])["metadata"]
    assert md["origin_route"] == "ingest_manual" and isinstance(md["created_ts"], float)
    assert md["origin_thread_id"] is None and md["origin_turn_id"] is None and md["run_id"] is None


def test_a_feed_path_stamps_feed(reset_stores, monkeypatch):
    from ELINS import ingestion_bus as ib
    import intelligence_kernel as ik
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: _FakeResponse(_RSS_ONE))
    feed = ib.register_feed("alice", name="f1", url="https://example.com/rss")
    out = ik.run_feed_ingestion("alice", feed["feed_id"])
    assert out["stored"] == 1
    md = library_store.get(out["library_ids"][0])["metadata"]
    assert md["origin_route"] == "feed" and isinstance(md["created_ts"], float)
    assert md["origin_thread_id"] is None and md["run_id"] is None


def test_a_elins_brief_stamps_and_refuses_a_client_override(client):
    user, h = _member()                                            # a controller: _require_founder
    t0 = time.time()
    r = client.post("/elins/ingest/brief", headers=h, json={
        "content": "the brief", "metadata": {"created_ts": 1.0, "run_id": "run-9"},
    })
    assert r.status_code == 200, r.text
    md = library_store.get(r.json()["item"]["id"])["metadata"]
    assert md["origin_route"] == "elins_brief" and md["created_ts"] >= t0 and md["run_id"] == "run-9"
    assert md["source"] == "elins" and md["date"]                  # the route's own keys stay
    r2 = client.post("/elins/ingest/brief", headers=h, json={
        "content": "the brief", "metadata": {"origin_route": "feed"},
    })
    assert r2.status_code == 400                                   # a client cannot claim a server word


# ===========================================================================
# (b) origin_route is one of the six words or the write 400s
# ===========================================================================
def test_b_the_vocabulary_is_six_words_on_the_ledger():
    assert library_store.ORIGIN_ROUTES == (
        "library_write", "ingest_manual", "feed", "elins_brief", "personal", "thread_footer",
    )
    assert library_store.CLIENT_ORIGIN_ROUTES == ("personal", "thread_footer")
    import intelligence_kernel as ik
    assert ik.ORIGIN_ROUTES == frozenset(library_store.ORIGIN_ROUTES)    # one vocabulary, not two


@pytest.mark.parametrize("word", ["bogus", "rss", "manual", "feed", "elins_brief", "ingest_manual"])
def test_b_library_write_refuses_any_word_but_its_own_or_a_clients(client, word):
    user, h = _member()
    r = client.post("/library/write", headers=h, json={
        "title": "note", "content": "x", "metadata": {"origin_route": word},
    })
    assert r.status_code == 400, (word, r.text)
    body = r.json(); err = body.get("detail", body)          # the app flattens error_response
    assert (err.get("error") if isinstance(err, dict) else err) == "bad_input"


def test_b_a_client_may_name_personal_or_thread_footer(client):
    user, h = _member()
    for word in ("personal", "thread_footer"):
        r = client.post("/library/write", headers=h, json={
            "title": "note", "content": "x", "metadata": {"origin_route": word},
        })
        assert r.status_code == 200, r.text
        assert library_store.get(r.json()["item"]["id"])["metadata"]["origin_route"] == word
    r = client.post("/library/write", headers=h, json={
        "title": "note", "content": "x", "metadata": {"origin_route": "library_write"},
    })
    assert r.status_code == 200                                    # naming the route's own word is harmless


def test_b_ingest_manual_refuses_a_word_outside_the_vocabulary_and_never_echoes_it(client):
    user, h = _member()
    marker = "alice@example.com thread_ab12 my private note"
    r = client.post("/ingest/manual", headers=h, json={"raw_text": "a paste", "origin_route": marker})
    assert r.status_code == 400
    assert marker not in r.text and "alice@example.com" not in r.text
    r = client.post("/ingest/manual", headers=h, json={"raw_text": "a paste", "origin_route": "thread_footer"})
    assert r.status_code == 200
    assert library_store.get(r.json()["library_id"])["metadata"]["origin_route"] == "thread_footer"


def test_b_stamp_provenance_unit():
    with pytest.raises(ValueError):
        library_store.stamp_provenance({}, "not_a_route")
    md = library_store.stamp_provenance({"origin_route": "   ", "created_ts": "yesterday"}, "feed")
    assert md["origin_route"] == "feed" and isinstance(md["created_ts"], float)     # blank claim -> the route
    md = library_store.stamp_provenance(None, "ingest_manual", origin_route="personal",
                                        origin_thread_id=" t1 ", origin_turn_id="", run_id="x" * 300)
    assert md["origin_route"] == "personal" and md["origin_thread_id"] == "t1"
    assert md["origin_turn_id"] is None and len(md["run_id"]) == 200


# ===========================================================================
# (c) + (e) the reader renders "—" for null; legacy items read dashes
# ===========================================================================
def test_c_list_renders_a_dash_for_null_and_the_substrate_keeps_null(client):
    user, h = _member()
    legacy_id = library_store.new_id()
    library_store.create(legacy_id, {                              # an item from before the fields
        "id": legacy_id, "user": user, "title": "old", "content": "x", "tags": [],
        "metadata": {"source": "hand"}, "size_bytes": 1,
        "created_at": time.time() - 100, "updated_at": time.time() - 100,
    })
    r = client.post("/library/write", headers=h, json={"title": "new", "content": "y",
                                                       "metadata": {"run_id": "r-2"}})
    assert r.status_code == 200
    items = client.get("/library/list", headers=h).json()["items"]
    by_id = {i["id"]: i for i in items}
    old, new = by_id[legacy_id], by_id[r.json()["item"]["id"]]
    assert old["provenance"] == {k: "—" for k in library_store.PROVENANCE_FIELDS}   # five dashes, no KeyError
    assert "created_ts" not in old["metadata"]                                     # no backfill
    assert new["provenance"]["origin_route"] == "library_write"
    assert isinstance(new["provenance"]["created_ts"], float)
    assert new["provenance"]["run_id"] == "r-2"
    assert new["provenance"]["origin_thread_id"] == "—" and new["provenance"]["origin_turn_id"] == "—"
    assert new["metadata"]["origin_thread_id"] is None                             # the render, not the substrate
    for item in items:
        for v in item["provenance"].values():
            assert v != "" and v != "unknown"


def test_e_update_carries_the_servers_two_and_never_plants_them(client):
    user, h = _member()
    r = client.post("/library/write", headers=h, json={"title": "n", "content": "x", "metadata": {"run_id": "r-3"}})
    item = r.json()["item"]
    stamped = library_store.get(item["id"])["metadata"]
    r2 = client.post("/library/update", headers=h, json={
        "id": item["id"],
        "metadata": {"created_ts": 1.0, "origin_route": "feed", "origin_turn_id": "turn-7", "other": True},
    })
    assert r2.status_code == 200, r2.text
    md = library_store.get(item["id"])["metadata"]
    assert md["created_ts"] == stamped["created_ts"] and md["origin_route"] == "library_write"   # carried, not overridden
    assert md["origin_turn_id"] == "turn-7" and md["run_id"] == "r-3" and md["other"] is True     # the client's three may change
    # a legacy item stays without the two after an update -- no backfill by the back door
    legacy_id = library_store.new_id()
    library_store.create(legacy_id, {"id": legacy_id, "user": user, "title": "old", "content": "x",
                                     "tags": [], "metadata": {}, "size_bytes": 1,
                                     "created_at": time.time(), "updated_at": time.time()})
    r3 = client.post("/library/update", headers=h, json={"id": legacy_id,
                                                         "metadata": {"created_ts": 5.0, "origin_route": "personal"}})
    assert r3.status_code == 200
    md = library_store.get(legacy_id)["metadata"]
    assert "created_ts" not in md and "origin_route" not in md


# ===========================================================================
# (d) the three emit sites reference the constant, not literals
# ===========================================================================
def test_d_the_kinds_are_one_constant_and_the_emit_sites_use_it():
    assert timeline_store.LIBRARY_TIMELINE_KINDS == ("library.write", "library.ingest", "elins.brief")
    assert (timeline_store.LIBRARY_WRITE_KIND, timeline_store.LIBRARY_INGEST_KIND,
            timeline_store.ELINS_BRIEF_KIND) == timeline_store.LIBRARY_TIMELINE_KINDS
    app_src = (_ROOT / "app.py").read_bytes().decode("utf-8")
    bus_src = (_ROOT / "ELINS" / "ingestion_bus.py").read_bytes().decode("utf-8")
    # the emit calls name the constant
    assert re.search(r"_emit_timeline\(user, timeline_store\.LIBRARY_WRITE_KIND,", app_src)
    assert re.search(r"_emit_timeline\(user, timeline_store\.ELINS_BRIEF_KIND,", app_src)
    assert re.search(r'"kind":\s*timeline_store\.LIBRARY_INGEST_KIND', bus_src)
    # and never the literal
    assert not re.search(r'_emit_timeline\(user, "library\.write"', app_src)
    assert not re.search(r'_emit_timeline\(user, "elins\.brief"', app_src)
    assert not re.search(r'"kind":\s*"library\.ingest"', bus_src)


def test_d_the_events_carry_the_kinds(client):
    user, h = _member()
    client.post("/library/write", headers=h, json={"title": "n", "content": "x"})
    client.post("/ingest/manual", headers=h, json={"raw_text": "a paste"})
    client.post("/elins/ingest/brief", headers=h, json={"content": "the brief"})
    kinds = sorted(e["kind"] for e in timeline_store.list_for_user(user))
    assert kinds == sorted(timeline_store.LIBRARY_TIMELINE_KINDS)


# ===========================================================================
# the refuter question: no path reaches library_store.create unstamped, and
# dewey_worker's update keeps the five
# ===========================================================================
def test_r_dewey_backfill_update_preserves_the_five(reset_stores):
    import dewey_worker
    user = "alice"
    item_id = library_store.new_id()
    md = library_store.stamp_provenance({"source": "x"}, "library_write", run_id="r-5")
    library_store.create(item_id, {"id": item_id, "user": user, "title": "t", "content": "c", "tags": [],
                                   "metadata": md, "size_bytes": 1,
                                   "created_at": time.time(), "updated_at": time.time()})
    doc = library_store.get(item_id)
    assert "object_vector" not in doc                              # a legacy object: the worker backfills a vector
    dewey_worker.process_object(user, "library", item_id, doc)
    after = library_store.get(item_id)
    assert after.get("object_vector")                              # the backfill wrote the vector ...
    for k in library_store.PROVENANCE_FIELDS:
        assert after["metadata"][k] == md[k]                       # ... and kept every provenance field


def test_r_every_create_site_stamps():
    """Every library_store.create call in the runtime sits after a stamp:
    app.py's two sites and ingestion_bus's one. A fourth site is a finding."""
    src = {p: (_ROOT / p).read_bytes().decode("utf-8")
           for p in ("app.py", "ELINS/ingestion_bus.py", "intelligence_kernel.py", "dewey_worker.py")}
    creates = {p: len(re.findall(r"library_store\.create\(", s)) for p, s in src.items()}
    assert creates == {"app.py": 2, "ELINS/ingestion_bus.py": 1, "intelligence_kernel.py": 0, "dewey_worker.py": 0}
    assert src["app.py"].count("library_store.stamp_provenance(") == 2
    assert src["ELINS/ingestion_bus.py"].count("library_store.stamp_provenance(") == 1


# ===========================================================================
# the refuters' three catches
# ===========================================================================
def test_r_update_takes_the_ownership_rule_too(client):
    import threads_vault
    user, h = _member()
    other, _ = _member()
    own = threads_vault.create_thread(user, title="mine")["thread_id"]
    theirs = threads_vault.create_thread(other, title="theirs")["thread_id"]
    item = client.post("/library/write", headers=h, json={"title": "n", "content": "x"}).json()["item"]
    r = client.post("/library/update", headers=h, json={"id": item["id"], "metadata": {"origin_thread_id": theirs}})
    assert r.status_code == 200
    assert library_store.get(item["id"])["metadata"]["origin_thread_id"] is None      # not yours -> null
    r = client.post("/library/update", headers=h, json={"id": item["id"], "metadata": {"origin_thread_id": own}})
    assert library_store.get(item["id"])["metadata"]["origin_thread_id"] == own        # yours -> kept


def test_r_a_forged_route_is_refused_before_the_elins_pass(reset_stores, caplog):
    import logging
    import intelligence_kernel as ik
    caplog.set_level(logging.INFO, logger="clarityos.kernel.runs")
    before = len(library_store.list_for_user("alice"))
    with pytest.raises(ValueError):
        ik.run_manual_ingestion("alice", "a paste", origin_route="feed")
    assert len(library_store.list_for_user("alice")) == before
    assert not [r for r in caplog.records if "kernel_run" in r.getMessage()]     # no ELINS pass ran, no line


@pytest.mark.parametrize("claim", [5, True, 0, ["feed"], {"x": 1}])
def test_r_a_non_string_claim_is_refused_not_coerced(client, claim):
    with pytest.raises(ValueError):
        library_store.stamp_provenance({"origin_route": claim}, "library_write")
    user, h = _member()
    r = client.post("/library/write", headers=h, json={"title": "n", "content": "x",
                                                       "metadata": {"origin_route": claim}})
    assert r.status_code == 400
