"""
#186 -- vault.write / vault.update / vault.delete timeline events carry
data.source = "vault".

The member's timeline tag reads events[].data.source (#180b, the web); no
vault emitter sent one, so every vault row read a dash (restore point
2026-09-08, STILL OPEN 52). One word at each emitter; the rest of the
event's data (type, tags) keeps the shape it had.
"""
import os

os.environ.setdefault("CLARITYOS_BACKEND", "memory")
os.environ.setdefault("CLARITYOS_VAULT_SECRET", "test-only-not-a-real-secret")

import secrets  # noqa: E402
import time  # noqa: E402

import bcrypt  # noqa: E402
import pytest  # noqa: E402

from conftest import TestClient  # noqa: E402
import app as appmod  # noqa: E402
import sessions_store  # noqa: E402
import users_store  # noqa: E402

client = TestClient(appmod.app)


def _session(user: str) -> dict:
    """An active member (the vault routes sit behind require_active_entitlement)."""
    users_store.create_user(
        username=user, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="", tier="free", created_at=time.time(),
    )
    users_store.update_user(user, {"cohort": "terrace_1"})
    users_store.set_membership(user, tier="founding", price=50.0, status="active")
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


@pytest.fixture(autouse=True)
def _reset(reset_stores):
    yield


def _events(headers: dict, kind: str) -> list:
    r = client.get("/timeline/list", headers=headers)
    assert r.status_code == 200, r.text[:200]
    return [e for e in r.json()["events"] if e.get("kind") == kind]


def test_vault_write_update_delete_events_carry_source_vault():
    h = _session("vault_src_u")
    r = client.post("/vault/write", headers=h, json={"title": "t", "content": "a note"})
    assert r.status_code == 200, r.text[:200]
    item_id = r.json()["item"]["id"]

    ev = _events(h, "vault.write")
    assert ev, "no vault.write event was emitted"
    assert ev[-1]["data"].get("source") == "vault", ev[-1]["data"]
    assert ev[-1]["data"].get("type") == "note"           # the shape it had is kept
    assert ev[-1]["data"].get("tags") == []

    r = client.post("/vault/update", headers=h, json={"id": item_id, "content": "a longer note"})
    assert r.status_code == 200, r.text[:200]
    ev = _events(h, "vault.update")
    assert ev and ev[-1]["data"].get("source") == "vault", ev

    r = client.post("/vault/delete", headers=h, json={"id": item_id})
    assert r.status_code == 200, r.text[:200]
    ev = _events(h, "vault.delete")
    assert ev and ev[-1]["data"].get("source") == "vault", ev


def test_the_elins_raw_ingest_vault_write_carries_source_vault():
    """The fourth emitter: the controller's raw ELINS ingest writes into the
    vault (type elins_raw) and its vault.write event says so too."""
    h = _session("vault_src_ctl")
    users_store.update_user("vault_src_ctl", {"controller": True})
    r = client.post("/elins/ingest/raw", headers=h, json={"payload": {"k": 1}, "label": "raw"})
    assert r.status_code == 200, r.text[:200]
    ev = _events(h, "vault.write")
    assert ev, "no vault.write event was emitted by the raw ingest"
    assert ev[-1]["data"].get("source") == "vault", ev[-1]["data"]
    assert ev[-1]["data"].get("type") == "elins_raw"


def test_the_emitters_name_the_source_in_the_source():
    """Guards the guard: the word is at the emitter, not added by a reader.
    Four emitters write vault.* events: the three /vault/* routes and the
    ELINS raw ingest, which writes into the vault too."""
    import inspect
    src = "".join(inspect.getsource(f) for f in (
        appmod.vault_write, appmod.vault_update, appmod.vault_delete, appmod.elins_ingest_raw,
    ))
    assert src.count('"source": "vault"') == 4, src.count('"source": "vault"')
