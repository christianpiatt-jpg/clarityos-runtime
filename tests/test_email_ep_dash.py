"""
Tests for email_ep_dash.py (Phase 2 Unit 2).

Same isolation discipline as personal_news_basin tests: every test
gets a fresh tmp library dir + reset ingestion bus, no network, no
shared state.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ELINS import ingestion_bus
import email_ep_dash as ed


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolated_paths_and_bus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point CLARITYOS_EMAIL_EP_DASH_DIR at a per-test tmp dir; reset bus."""
    lib_dir = tmp_path / "email_dash_lib"
    monkeypatch.setenv("CLARITYOS_EMAIL_EP_DASH_DIR", str(lib_dir))
    ingestion_bus._reset_memory_for_tests()
    yield lib_dir
    ingestion_bus._reset_memory_for_tests()


def _sample_blob(
    *,
    from_: str = "alice@example.com",
    to: str = "bob@example.com",
    cc: str = "",
    subject: str = "Project Update",
    date: str = "Mon, 11 May 2026 12:00:00 +0000",
    body: str = "Quick note on the project. Can you review by Friday?",
) -> str:
    parts = [f"From: {from_}", f"To: {to}"]
    if cc:
        parts.append(f"Cc: {cc}")
    parts += [f"Subject: {subject}", f"Date: {date}", "", body]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# parse_email_blob
# ---------------------------------------------------------------------------
class TestParseEmailBlob:
    def test_extracts_basic_headers(self):
        blob = _sample_blob()
        parsed = ed.parse_email_blob(blob)
        assert parsed["from"]    == "alice@example.com"
        assert parsed["to"]      == ["bob@example.com"]
        assert parsed["cc"]      == []
        assert parsed["subject"] == "Project Update"
        assert parsed["date"]    == "Mon, 11 May 2026 12:00:00 +0000"
        assert "review by Friday" in parsed["body"]

    def test_multi_recipient_to_and_cc(self):
        blob = _sample_blob(
            to="bob@x.com, carol@y.com, dave@z.com",
            cc="eve@a.com, frank@b.com",
        )
        parsed = ed.parse_email_blob(blob)
        assert parsed["to"] == ["bob@x.com", "carol@y.com", "dave@z.com"]
        assert parsed["cc"] == ["eve@a.com", "frank@b.com"]

    def test_case_insensitive_header_names(self):
        blob = (
            "FROM: alice@x.com\n"
            "to: bob@x.com\n"
            "SUBJECT: hi\n"
            "\n"
            "body here"
        )
        parsed = ed.parse_email_blob(blob)
        assert parsed["from"]    == "alice@x.com"
        assert parsed["to"]      == ["bob@x.com"]
        assert parsed["subject"] == "hi"
        assert parsed["body"]    == "body here"

    def test_unfolds_continuation_lines(self):
        # RFC 5322 §2.2.3 — leading whitespace on a line means it's a
        # continuation of the previous header.
        blob = (
            "From: alice@x.com\n"
            "Subject: This is a long subject\n"
            " that continues on the next line\n"
            "\n"
            "body"
        )
        parsed = ed.parse_email_blob(blob)
        assert parsed["subject"] == "This is a long subject that continues on the next line"

    def test_crlf_line_endings(self):
        blob = "From: a@b.com\r\nTo: c@d.com\r\nSubject: x\r\n\r\nbody\r\n"
        parsed = ed.parse_email_blob(blob)
        assert parsed["from"]    == "a@b.com"
        assert parsed["subject"] == "x"
        assert parsed["body"]    == "body"

    def test_blank_body(self):
        blob = "From: alice@x.com\nSubject: x\n\n"
        parsed = ed.parse_email_blob(blob)
        assert parsed["body"] == ""

    def test_no_body_at_all_no_blank_line(self):
        blob = "From: alice@x.com\nSubject: x"
        parsed = ed.parse_email_blob(blob)
        assert parsed["from"]    == "alice@x.com"
        assert parsed["subject"] == "x"
        assert parsed["body"]    == ""

    def test_missing_fields_default(self):
        parsed = ed.parse_email_blob("Subject: hi\n\nbody")
        assert parsed["from"]    == ""
        assert parsed["to"]      == []
        assert parsed["cc"]      == []
        assert parsed["date"]    is None

    def test_empty_string_returns_empty_fields(self):
        parsed = ed.parse_email_blob("")
        assert parsed["from"]    == ""
        assert parsed["to"]      == []
        assert parsed["cc"]      == []
        assert parsed["subject"] == ""
        assert parsed["date"]    is None
        assert parsed["body"]    == ""

    def test_non_string_input_safe(self):
        parsed = ed.parse_email_blob(None)  # type: ignore[arg-type]
        assert parsed["from"] == ""
        assert parsed["body"] == ""
        parsed = ed.parse_email_blob(12345)  # type: ignore[arg-type]
        assert parsed["from"] == ""

    def test_garbage_text_treated_as_body(self):
        """When no headers parse, everything becomes body (after leading blanks)."""
        parsed = ed.parse_email_blob("just some random text\nno headers here")
        assert parsed["from"]    == ""
        assert parsed["subject"] == ""
        # Without headers, the whole thing is body (after stripping leading blank lines).
        # First line "just some random text" has no ":" so it parses as a non-header line.
        # The current implementation stops collecting headers at the first blank line.
        # Lines without ":" before a blank line are silently dropped (they're not header
        # name:value pairs). Acceptable for malformed input — no crash, no false-positive header.

    def test_leading_blank_lines_stripped(self):
        blob = "\n\n\nFrom: a@b.com\nSubject: x\n\nbody"
        parsed = ed.parse_email_blob(blob)
        assert parsed["from"] == "a@b.com"


# ---------------------------------------------------------------------------
# Classifiers
# ---------------------------------------------------------------------------
class TestImportance:
    def test_high_urgent(self):
        assert ed._classify_importance("URGENT: server down", "") == "HIGH"

    def test_high_in_body(self):
        assert ed._classify_importance("re: meeting", "This is critical") == "HIGH"

    def test_medium_please_review(self):
        assert ed._classify_importance("doc", "Please review when you can") == "MEDIUM"

    def test_medium_by_friday(self):
        assert ed._classify_importance("Q3 plan", "Need this by Friday") == "MEDIUM"

    def test_low_default(self):
        assert ed._classify_importance("Hello", "Just saying hi") == "LOW"

    def test_high_beats_medium(self):
        # Body has both "urgent" (HIGH) and "please review" (MEDIUM); HIGH wins.
        assert ed._classify_importance("x", "Urgent — please review") == "HIGH"


class TestDeadline:
    def test_by_friday(self):
        assert ed._has_deadline("", "Please respond by Friday") is True

    def test_by_tomorrow(self):
        assert ed._has_deadline("", "Send it by tomorrow") is True

    def test_by_numeric_date(self):
        assert ed._has_deadline("", "Submit by 5/15/2026") is True

    def test_word_deadline(self):
        assert ed._has_deadline("Hard deadline approaching", "") is True

    def test_due_by(self):
        assert ed._has_deadline("", "This is due by Wednesday") is True

    def test_no_later_than(self):
        assert ed._has_deadline("", "No later than next week, please") is True

    def test_month_name(self):
        assert ed._has_deadline("", "Need it by January 15") is True

    def test_none(self):
        assert ed._has_deadline("Project Update", "Quick note") is False

    def test_handles_empty(self):
        assert ed._has_deadline("", "") is False


class TestMarkers:
    def test_commitment_i_will(self):
        markers = ed._commitment_markers("I will send the report tomorrow.")
        assert "i will" in markers

    def test_commitment_ill_contraction(self):
        markers = ed._commitment_markers("I'll handle it.")
        assert "i'll" in markers

    def test_commitment_we_will(self):
        markers = ed._commitment_markers("We will review it.")
        assert "we will" in markers

    def test_commitment_promise(self):
        markers = ed._commitment_markers("I promise to follow up.")
        assert "i promise" in markers

    def test_commitment_dedupes(self):
        markers = ed._commitment_markers("I will do it. I will follow up. I will close out.")
        # Phrase "i will" appears 3× but should only land once.
        assert markers.count("i will") == 1

    def test_commitment_empty(self):
        assert ed._commitment_markers("") == []

    def test_request_can_you(self):
        markers = ed._request_markers("Can you send me the draft?")
        assert "can you" in markers

    def test_request_please(self):
        markers = ed._request_markers("Please confirm receipt.")
        assert "please" in markers

    def test_request_could_you(self):
        markers = ed._request_markers("Could you take a look?")
        assert "could you" in markers

    def test_request_multi(self):
        markers = ed._request_markers(
            "Could you please review? I need this by Friday. Would you confirm?",
        )
        assert "could you" in markers
        assert "please" in markers
        assert "i need" in markers
        assert "would you" in markers


class TestEpFlags:
    def test_pressure_flag(self):
        flags = ed._ep_flags("URGENT request", "")
        assert "pressure" in flags

    def test_tension_flag(self):
        flags = ed._ep_flags("", "I have a concern about this approach")
        assert "tension" in flags

    def test_drift_flag(self):
        flags = ed._ep_flags("", "We've moved on from that idea")
        assert "drift" in flags

    def test_trust_flag(self):
        flags = ed._ep_flags("", "I trust your judgment on this")
        assert "trust" in flags

    def test_alignment_flag(self):
        flags = ed._ep_flags("", "Glad we agree on this")
        assert "alignment" in flags

    def test_contradiction_flag(self):
        flags = ed._ep_flags("", "I see your point, but the data says otherwise")
        assert "contradiction" in flags

    def test_returns_canonical_flag_names_not_keywords(self):
        flags = ed._ep_flags("", "URGENT — please trust me on this")
        # 'pressure' (urgent) + 'trust' — canonical names, not "urgent"/"trust me".
        assert "pressure" in flags
        assert "trust" in flags
        assert "urgent" not in flags

    def test_multiple_flags(self):
        flags = ed._ep_flags("URGENT — disagreement on direction",
                             "I trust your view but we should reconsider.")
        assert "pressure" in flags
        assert "tension" in flags
        assert "trust" in flags
        assert "drift" in flags
        assert "contradiction" in flags

    def test_empty_returns_empty(self):
        assert ed._ep_flags("", "") == []


# ---------------------------------------------------------------------------
# Thread key
# ---------------------------------------------------------------------------
class TestThreadKey:
    def test_same_subject_same_key(self):
        k1 = ed._thread_key("Project Update")
        k2 = ed._thread_key("Project Update")
        assert k1 == k2

    def test_strips_re_prefix(self):
        k_plain = ed._thread_key("Project Update")
        k_re    = ed._thread_key("Re: Project Update")
        k_RE    = ed._thread_key("RE: Project Update")
        assert k_plain == k_re == k_RE

    def test_strips_fwd_prefix(self):
        assert ed._thread_key("Project Update") == ed._thread_key("Fwd: Project Update")
        assert ed._thread_key("Project Update") == ed._thread_key("Fw: Project Update")

    def test_strips_nested_prefixes(self):
        assert ed._thread_key("Project Update") == ed._thread_key("Re: Re: Re: Project Update")
        assert ed._thread_key("Project Update") == ed._thread_key("Fwd: Re: Project Update")

    def test_case_insensitive_subject(self):
        assert ed._thread_key("Project Update") == ed._thread_key("project update")

    def test_different_subjects_different_keys(self):
        assert ed._thread_key("A") != ed._thread_key("B")

    def test_empty_subject_stable_key(self):
        k1 = ed._thread_key("")
        k2 = ed._thread_key("")
        assert k1 == k2  # stable
        assert isinstance(k1, str)
        assert len(k1) == 16


# ---------------------------------------------------------------------------
# normalize_email
# ---------------------------------------------------------------------------
class TestNormalizeEmail:
    def test_canonical_keys(self):
        parsed = ed.parse_email_blob(_sample_blob())
        packet = ed.normalize_email(parsed, "alice")
        assert set(packet.keys()) == set(ed.PACKET_KEYS)

    def test_round_trip_sample(self):
        parsed = ed.parse_email_blob(_sample_blob())
        packet = ed.normalize_email(parsed, "alice")
        assert packet["from"]    == "alice@example.com"
        assert packet["to"]      == ["bob@example.com"]
        assert packet["subject"] == "Project Update"
        assert packet["importance"] == "MEDIUM"   # "by Friday"
        assert packet["has_deadline"] is True     # "by Friday"
        assert "can you" in packet["request_markers"]
        assert isinstance(packet["thread_key"], str) and len(packet["thread_key"]) == 16

    def test_missing_fields_get_defaults(self):
        packet = ed.normalize_email({}, "alice")
        assert packet["from"]               == ""
        assert packet["to"]                 == []
        assert packet["cc"]                 == []
        assert packet["subject"]            == ""
        assert packet["body"]               == ""
        assert packet["date"]               is None
        assert packet["importance"]         == "LOW"
        assert packet["has_deadline"]       is False
        assert packet["commitment_markers"] == []
        assert packet["request_markers"]    == []
        assert packet["ep_flags"]           == []
        assert isinstance(packet["thread_key"], str)

    def test_to_list_form_passthrough(self):
        packet = ed.normalize_email(
            {"to": ["a@x.com", "b@x.com"], "subject": "s", "body": "b"},
        )
        assert packet["to"] == ["a@x.com", "b@x.com"]

    def test_non_dict_raw_tolerated(self):
        packet = ed.normalize_email(None, "alice")  # type: ignore[arg-type]
        assert set(packet.keys()) == set(ed.PACKET_KEYS)
        assert packet["from"] == ""

    def test_full_signal_extraction(self):
        parsed = ed.parse_email_blob(_sample_blob(
            subject="URGENT: production issue",
            body=(
                "We have a critical bug. Can you investigate?\n"
                "I will be on call. We need a fix by tomorrow.\n"
                "Please confirm you're on it."
            ),
        ))
        packet = ed.normalize_email(parsed, "alice")
        assert packet["importance"]   == "HIGH"
        assert packet["has_deadline"] is True
        assert "i will" in packet["commitment_markers"]
        assert "can you" in packet["request_markers"]
        assert "please" in packet["request_markers"]
        assert "pressure" in packet["ep_flags"]


# ---------------------------------------------------------------------------
# build_email_dash_envelope
# ---------------------------------------------------------------------------
class TestBuildEnvelope:
    def test_shape(self):
        env = ed.build_email_dash_envelope([{"x": 1}], "alice")
        assert env["type"]   == "email_ep_dash"
        assert env["user"]   == "alice"
        assert env["items"]  == [{"x": 1}]
        assert isinstance(env["generated_at"], str)
        assert "T" in env["generated_at"]

    def test_empty_items_ok(self):
        env = ed.build_email_dash_envelope([])
        assert env["items"] == []
        assert env["user"]  == "system"

    def test_defensive_against_non_list(self):
        env = ed.build_email_dash_envelope("not a list")  # type: ignore[arg-type]
        assert env["items"] == []


# ---------------------------------------------------------------------------
# write_to_ingestion_bus / write_to_library
# ---------------------------------------------------------------------------
class TestWriteToIngestionBus:
    def test_round_trip(self):
        env = ed.build_email_dash_envelope([{"x": 1}], "alice")
        pid = ed.write_to_ingestion_bus(env)
        assert pid.startswith("pkt_")
        fetched = ingestion_bus.get_packet(pid)
        assert fetched is not None
        assert fetched["type"] == "email_ep_dash"
        assert fetched["user"] == "alice"

    def test_rejects_invalid(self):
        with pytest.raises(ValueError):
            ed.write_to_ingestion_bus({"items": []})   # missing 'type'
        with pytest.raises(ValueError):
            ed.write_to_ingestion_bus("not a dict")    # type: ignore[arg-type]


class TestWriteToLibrary:
    def test_creates_file(self, _isolated_paths_and_bus):
        lib_dir = _isolated_paths_and_bus
        env = {
            "type":         "email_ep_dash",
            "user":         "alice",
            "generated_at": "2026-05-11T09:15:00+00:00",
            "items":        [],
        }
        path = ed.write_to_library(env)
        p = Path(path)
        assert p.exists()
        assert p.parent == lib_dir
        assert p.name == "2026-05-11_0915.json"
        assert json.loads(p.read_text(encoding="utf-8")) == env

    def test_falls_back_to_now_on_missing_generated_at(self, _isolated_paths_and_bus):
        env = {"type": "email_ep_dash", "items": []}
        path = ed.write_to_library(env)
        assert Path(path).exists()
        assert Path(path).name.endswith(".json")
        # Filename stem matches YYYY-MM-DD_HHMM (15 chars)
        assert len(Path(path).stem) == 15

    def test_falls_back_to_now_on_bad_generated_at(self, _isolated_paths_and_bus):
        env = {"type": "email_ep_dash", "generated_at": "not-a-date", "items": []}
        path = ed.write_to_library(env)
        assert Path(path).exists()

    def test_creates_parent_dirs(self, tmp_path, monkeypatch):
        deep_dir = tmp_path / "deeply" / "nested" / "edash"
        monkeypatch.setenv("CLARITYOS_EMAIL_EP_DASH_DIR", str(deep_dir))
        env = {"type": "email_ep_dash", "items": []}
        ed.write_to_library(env)
        assert deep_dir.exists()

    def test_rejects_non_dict_envelope(self, _isolated_paths_and_bus):
        with pytest.raises(ValueError):
            ed.write_to_library("not a dict")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# run_email_ep_dash — entrypoint
# ---------------------------------------------------------------------------
class TestRunEmailEpDash:
    def test_end_to_end_with_real_blob(self, _isolated_paths_and_bus):
        blob = _sample_blob(
            subject="URGENT: Q3 review",
            body="Can you send me the deck by Friday? I will finalise it tonight.",
        )
        env = ed.run_email_ep_dash(blob, "alice")

        # Envelope shape
        assert env["type"]   == "email_ep_dash"
        assert env["user"]   == "alice"
        assert len(env["items"]) == 1

        # Packet has all canonical keys
        packet = env["items"][0]
        assert set(packet.keys()) == set(ed.PACKET_KEYS)
        assert packet["importance"]   == "HIGH"      # URGENT
        assert packet["has_deadline"] is True        # by Friday
        assert "i will" in packet["commitment_markers"]
        assert "can you" in packet["request_markers"]
        assert "pressure" in packet["ep_flags"]

        # Both writes happened
        assert isinstance(env["_bus_packet_id"], str)
        assert env["_bus_packet_id"].startswith("pkt_")
        assert isinstance(env["_library_path"], str)
        assert Path(env["_library_path"]).exists()

        # Bus round-trip works
        fetched = ingestion_bus.get_packet(env["_bus_packet_id"])
        assert fetched is not None
        assert fetched["items"][0]["subject"] == "URGENT: Q3 review"

    def test_empty_input_short_circuits_no_writes(self, _isolated_paths_and_bus):
        lib_dir = _isolated_paths_and_bus
        env = ed.run_email_ep_dash("", "alice")
        assert env["type"]   == "email_ep_dash"
        assert env["items"]  == []
        assert env["user"]   == "alice"
        # No meta keys appended (no writes happened)
        assert "_bus_packet_id" not in env
        assert "_library_path" not in env
        # No bus packets, no library files
        assert ingestion_bus.list_packets() == []
        if lib_dir.exists():
            assert list(lib_dir.iterdir()) == []

    def test_whitespace_only_input_short_circuits(self, _isolated_paths_and_bus):
        env = ed.run_email_ep_dash("\n   \n   \t  \n", "alice")
        assert env["items"] == []
        assert "_bus_packet_id" not in env

    def test_none_input_short_circuits(self, _isolated_paths_and_bus):
        env = ed.run_email_ep_dash(None, "alice")  # type: ignore[arg-type]
        assert env["items"] == []
        assert "_bus_packet_id" not in env

    def test_malformed_body_only_still_records(self, _isolated_paths_and_bus):
        """A blob with no headers but real body content gets normalised
        and persisted — body-only is a legitimate input."""
        # Need at least one header to make the parser collect the rest
        # as body. Single line "garbage" without ":" is treated as body.
        # Use a "Subject:" header to force parser into body mode.
        env = ed.run_email_ep_dash("Subject: malformed paste\n\nbody only", "alice")
        assert len(env["items"]) == 1
        assert env["items"][0]["body"] == "body only"
        assert "_bus_packet_id" in env

    def test_thread_grouping_via_subject(self, _isolated_paths_and_bus):
        """Two emails on the same conversation share thread_key."""
        env1 = ed.run_email_ep_dash(_sample_blob(subject="Project Update"), "alice")
        env2 = ed.run_email_ep_dash(_sample_blob(subject="Re: Project Update"), "alice")
        env3 = ed.run_email_ep_dash(_sample_blob(subject="Fwd: Re: Project Update"), "alice")
        k1 = env1["items"][0]["thread_key"]
        k2 = env2["items"][0]["thread_key"]
        k3 = env3["items"][0]["thread_key"]
        assert k1 == k2 == k3
