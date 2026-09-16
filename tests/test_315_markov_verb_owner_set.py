"""
#315 -- /markov renders the verb-owner set -- render only, no store.

1. POST /markov carries ``verb_owner_set``: G1..G7 (primitives_extract
   .grammar_counts) + D / N / T, the SAME dict the thread shadow logs
   (app._verb_owner_set is the one producer; _emophysics_shadow logs it).
2. Nothing is stored and nothing names a thread: the adapter is pure compute
   plus the unchanged model call.
3. #117 (a): "current" is a hydronic FLOW only as a noun -- "under the current
   rule" fires nothing. #117 (b): sentence-initial function words and single
   letters are not P1 entities.
4. W1 of WALK_eeoc_nprm, loaded from OUTSIDE the tree at test time (skipped
   with the reason when the file is absent): hydronic 0, and P1 without the
   thirteen tokens. No character of the walk enters an assertion message.
"""
from __future__ import annotations

import ast
import inspect
import json
import os
import textwrap
import re
import secrets
import time
import uuid

import pytest

from conftest import TestClient

import primitives_extract as pe
import sessions_store
import users_store

THIRTEEN = ("Under", "Yet", "Given", "Rather", "Even", "Consequently", "Instead",
            "One", "B", "U", "S", "C", "Id")
G_KEYS = ("G1", "G2", "G3", "G4", "G5", "G6", "G7")

# The walk's place OUTSIDE the tree (as test_307_lit_record_pin does it):
# <home>/ClarityOS_Library/<relative>, or wherever CLARITYOS_WALK_EEOC_PATH points.
RELATIVE_PATH = os.path.join(
    "ClarityOS_Library", "Launch GalileOnline", "WALK_eeoc_nprm_four_seats_2026-09-16.md",
)
DEFAULT_PATH = os.path.join(os.path.expanduser("~"), RELATIVE_PATH)


def _walk_path() -> str:
    return os.environ.get("CLARITYOS_WALK_EEOC_PATH") or DEFAULT_PATH


def _w1_text():
    path = _walk_path()
    if not os.path.isfile(path):
        pytest.skip("WALK_eeoc_nprm is outside the tree and absent here: " + RELATIVE_PATH)
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    m = re.search(r"^# W1 [^\n]*\n(.*?)(?=^# W2 )", txt, re.S | re.M)
    if not m or len(m.group(1).strip()) < 100:
        pytest.skip("WALK_eeoc_nprm has no W1 section under a '# W1 ' heading")
    return m.group(1)


@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


def _member(username: str = "member_315"):
    import bcrypt
    users_store.create_user(
        username=username, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="", tier="free", created_at=time.time(),
    )
    users_store.set_membership(username, tier="founding", price=50.0, status="active")
    users_store.add_g_credits(username, 5_000_000)
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, {"X-Session-ID": sid, "Idempotency-Key": uuid.uuid4().hex}


# ===========================================================================
# 1 -- the wire
# ===========================================================================
def test_315_markov_response_carries_the_verb_owner_set_beside_the_p_series(app_module):
    client = TestClient(app_module.app)
    user, h = _member()
    text = "The committee is unhappy that the process is too long. It decides nothing."
    r = client.post("/markov", headers=h, json={"text": text})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "primitives" in data and "primitives_meta" in data          # the P-series is still there
    vos = data["verb_owner_set"]
    for k in G_KEYS:
        assert isinstance(vos[k], int) and vos[k] >= 0, k
    assert vos["G4_reflexive_only"] is True and isinstance(vos["G_sentences"], int)
    assert isinstance(vos["D"], int) and vos["D_status"] == "CANDIDATE"
    for flow in ("T", "N"):
        assert isinstance(vos[flow], float) or vos[flow] == app_module._EMOPHYSICS_UNMAPPED
        assert vos[flow + "_status"] in ("CANDIDATE", app_module._EMOPHYSICS_UNMAPPED)
    assert vos["E"] == vos["E_status"] == app_module._EMOPHYSICS_UNMAPPED
    assert vos["computed"] is False and isinstance(vos["reason"], str)
    # it is grammar_counts, on the wire
    assert {k: vos[k] for k in G_KEYS} == {k: pe.grammar_counts(text)[k] for k in G_KEYS}
    assert vos["counts"] == data["primitives_meta"]["counts"]
    # no thread on the wire, in or out
    assert "thread_id" not in data


def test_315_the_shadow_and_the_wire_share_one_producer(app_module):
    text = "The committee is unhappy that the process is too long."
    pure = app_module._verb_owner_set(text)
    shadow = app_module._emophysics_shadow("member_315", text)
    plan = shadow.pop("plan")                         # the shadow attaches its plan; the set is the rest
    assert plan is not None
    assert shadow == pure
    assert "plan" not in pure
    # nothing of the member's text rides in the set: not one content word
    dumped = json.dumps(pure).lower()
    for word in ("committee", "unhappy", "process", "long"):
        assert word not in dumped, word
    # pure: the same answer twice, and neither producer nor adapter names a store,
    # a thread, or the log (read off the AST -- names in code, not words in comments)
    assert app_module._verb_owner_set(text) == pure
    names = set()
    for fn in (app_module._verb_owner_set, app_module.markov_adapter):
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
    forbidden = {"threads_vault", "turn_record", "memory_vault", "vault_put", "record_turn",
                 "append_message", "thread_id", "logger", "log_event", "library_store", "el_ins",
                 "timeline", "anomaly_store", "operator_state", "kernel_logging", "logging",
                 "getLogger", "print", "open", "write", "info", "warning", "debug"}
    assert not (names & forbidden), sorted(names & forbidden)


# ===========================================================================
# 3 -- #117 (a) and (b), on fixed sentences
# ===========================================================================
def test_117a_current_as_an_adjective_is_not_a_flow():
    for adjective in (
        "Under the current rule the process is too long.",
        "The current filing rule takes ninety days; the current summary says so.",
        "Current practice and current law differ.",
        "The current-law baseline and the current 2024 rule both apply.",
        "The current (revised) rule; the current, proposed rule; current \u00a7 1614.",
        "Data current through June; keep current with the law; current for six months.",
    ):
        assert pe.extract_primitives(adjective)["hydronic"]["flows"] == [], adjective
    for noun in (
        "The river's current runs strong.",
        "Swim against the current.",
        "The current of the stream turned; strong currents pulled the boat.",
        "Feel the current.",
        "The current swept the boat away.",
        "The current pushes the boat.",
        "\"Swim against the current\" he said.",
        "(Against the current) he swam.",
    ):
        assert "current" in pe.extract_primitives(noun)["hydronic"]["flows"], noun
    # the rest of the flows list is untouched (word boundary, plural)
    assert pe.extract_primitives("The pipeline and its channels carry the throughput.")["hydronic"]["flows"] == \
        ["throughput", "pipeline", "channel"]


def test_117b_sentence_starters_and_single_letters_are_not_entities():
    text = ("Under the rule, nothing moves. Yet the agency waits. Given that, one wonders. "
            "Rather than act, it stalls. Even so, B and C differ under 5 U.S.C. 7702. "
            "Consequently the case sits. Instead it is Id. at 4. One commenter agreed.")
    p1 = pe.extract_primitives(text)["P1"]
    assert not (set(THIRTEEN) & set(p1)), sorted(set(THIRTEEN) & set(p1))
    # real names, acronyms and multi-word runs still pass; a leading article or
    # connective is dropped from a run, an ordinal / month / number / determiner is not
    p1b = pe.extract_primitives("Under Secretary Alvarez met the EEOC in Denver. Yet Congress waited.")["P1"]
    assert "Under Secretary Alvarez" in p1b and "EEOC" in p1b and "Denver" in p1b and "Congress" in p1b
    assert "Yet" not in p1b and "Yet Congress" not in p1b
    p1c = pe.extract_primitives(
        "The First Amendment claim failed in the Second Circuit. Both Parties cited August Wilson. "
        "No Child Left Behind applied. The Commission agreed."
    )["P1"]
    for kept in ("First Amendment", "Second Circuit", "Both Parties", "August Wilson", "No Child Left Behind", "Commission"):
        assert kept in p1c, (kept, p1c)
    for gone in ("Amendment", "Circuit", "Parties", "Wilson", "The Commission", "The First Amendment"):
        assert gone not in p1c, (gone, p1c)
    # conjunctions, citation signals and prepositions at a run's head go too; "Under" alone is kept for the title
    p1d = pe.extract_primitives("But Congress waited. See Smith v. Jones. In Denver the agency stalled. Under Title VII it must act.")["P1"]
    for kept in ("Congress", "Smith", "Jones", "Denver", "Under Title VII"):
        assert kept in p1d, (kept, p1d)
    for gone in ("But Congress", "See Smith", "In Denver", "Title VII"):
        assert gone not in p1d, (gone, p1d)


# ===========================================================================
# 4 -- W1 of the walk, from outside the tree
# ===========================================================================
def test_315_w1_of_the_walk_yields_hydronic_0_and_p1_without_the_thirteen():
    w1 = _w1_text()
    prim = pe.extract_primitives(w1)
    h = prim["hydronic"]
    assert sum(len(v) for v in h.values()) == 0, {k: len(v) for k, v in h.items()}   # counts only
    hit = sorted(set(THIRTEEN) & set(prim["P1"]))
    assert hit == [], hit
    assert len(prim["P1"]) > 0
    g = pe.grammar_counts(w1)
    assert g["sentences"] > 0 and all(g[k] >= 0 for k in G_KEYS)
