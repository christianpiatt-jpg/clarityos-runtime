"""
Tests for runtime_intelligence_wiring.py (Phase 3 Unit 1).

Same hermetic discipline as Phase-2 unit tests: tmp_path-scoped
library dirs, reset ingestion bus, stubbed operator_state. No network,
no LLM, no real perplexity.

12 test classes, 50+ tests covering A–I of the spec.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ELINS import ingestion_bus
import runtime_intelligence_wiring as riw


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Scope all three producer library dirs to tmp_path, reset the
    ingestion bus, and stub operator_state to empty by default."""
    monkeypatch.setenv("CLARITYOS_NEWS_BASIN_DIR",    str(tmp_path / "news"))
    monkeypatch.setenv("CLARITYOS_EMAIL_EP_DASH_DIR", str(tmp_path / "email"))
    monkeypatch.setenv("CLARITYOS_DAILY_ELINS_DIR",   str(tmp_path / "daily"))

    # Default: operator_state returns empty histories so micro signals are [].
    import operator_state
    monkeypatch.setattr(
        operator_state, "get_operator_state",
        lambda uid: {"elins_history": [], "g_history": []},
    )

    ingestion_bus._reset_memory_for_tests()
    yield tmp_path
    ingestion_bus._reset_memory_for_tests()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _push_news(*, user: str, generated_at=None, items=None) -> str:
    if generated_at is None:
        generated_at = _iso(_now_utc())
    elif isinstance(generated_at, datetime):
        generated_at = _iso(generated_at)
    return ingestion_bus.write_packet({
        "type":         "news_basin",
        "user":         user,
        "generated_at": generated_at,
        "items":        items or [],
    })


def _push_email(*, user: str, generated_at=None, items=None) -> str:
    if generated_at is None:
        generated_at = _iso(_now_utc())
    elif isinstance(generated_at, datetime):
        generated_at = _iso(generated_at)
    return ingestion_bus.write_packet({
        "type":         "email_ep_dash",
        "user":         user,
        "generated_at": generated_at,
        "items":        items or [],
    })


def _push_daily(*, user: str, generated_at=None, date=None, macro=None, **extra) -> str:
    if generated_at is None:
        generated_at = _iso(_now_utc())
    elif isinstance(generated_at, datetime):
        generated_at = _iso(generated_at)
    if date is None:
        date = _now_utc().date().isoformat()
    env = {
        "type":         "daily_personal_elins",
        "user":         user,
        "date":         date,
        "generated_at": generated_at,
        "macro":        macro if macro is not None else {
            "field_weather": "stable", "dominant_themes": [], "risk_zones": [],
        },
        "meso":         {"news": {}, "email": {}},
        "micro":        {"message_count": 0, "ep_flags": {}, "notable_events": []},
        "summary":      {"headline": "test", "focus": []},
    }
    env.update(extra)
    return ingestion_bus.write_packet(env)


def _write_daily_archive(tmp_path: Path, *, user: str, envelope: dict, date=None) -> Path:
    if date is None:
        date = _now_utc().date().isoformat()
    archive_dir = tmp_path / "daily" / user
    archive_dir.mkdir(parents=True, exist_ok=True)
    p = archive_dir / f"{date}.json"
    p.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    return p


# ===========================================================================
# A. Empty-day behavior
# ===========================================================================
class TestEmptyDay:
    def test_snapshot_returns_full_schema_when_empty(self):
        snap = riw.get_intelligence_snapshot("alice")
        assert set(snap.keys()) == {"date", "daily_elins", "news", "email", "micro", "macro"}
        assert snap["daily_elins"] is None
        assert snap["news"]  == []
        assert snap["email"] == []
        assert snap["micro"] == []
        assert snap["macro"] == {}

    def test_individual_getters_empty(self):
        assert riw.get_today_elins("alice")          is None
        assert riw.get_latest_news("alice")          == []
        assert riw.get_latest_email_signals("alice") == []
        assert riw.get_latest_micro_signals("alice") == []

    def test_date_field_is_iso_date(self):
        snap = riw.get_intelligence_snapshot("alice")
        # Parse round-trip should succeed.
        from datetime import date as date_cls
        date_cls.fromisoformat(snap["date"])


# ===========================================================================
# B. Partial data
# ===========================================================================
class TestPartialData:
    def test_only_news(self):
        _push_news(user="alice", items=[{"headline": "X"}])
        snap = riw.get_intelligence_snapshot("alice")
        assert len(snap["news"]) == 1
        assert snap["email"] == []
        assert snap["micro"] == []
        assert snap["daily_elins"] is None
        assert snap["macro"] == {}

    def test_only_email(self):
        _push_email(user="alice", items=[{"subject": "X"}])
        snap = riw.get_intelligence_snapshot("alice")
        assert snap["news"]  == []
        assert len(snap["email"]) == 1
        assert snap["micro"] == []
        assert snap["daily_elins"] is None

    def test_only_micro(self, monkeypatch):
        import operator_state
        ts = _now_utc().timestamp()
        monkeypatch.setattr(
            operator_state, "get_operator_state",
            lambda uid: {
                "elins_history": [{"ts": ts, "topic": "x"}],
                "g_history": [],
            },
        )
        snap = riw.get_intelligence_snapshot("alice")
        assert snap["news"]  == []
        assert snap["email"] == []
        assert len(snap["micro"]) == 1
        assert snap["daily_elins"] is None

    def test_only_daily_elins(self):
        _push_daily(user="alice", macro={"field_weather": "turbulent", "dominant_themes": ["US"], "risk_zones": []})
        snap = riw.get_intelligence_snapshot("alice")
        assert snap["news"]  == []
        assert snap["email"] == []
        assert snap["micro"] == []
        assert snap["daily_elins"] is not None
        assert snap["daily_elins"]["type"] == "daily_personal_elins"
        # macro extracted to top-level snapshot
        assert snap["macro"]["field_weather"] == "turbulent"

    def test_news_plus_email(self):
        _push_news(user="alice",  items=[{"h": "n"}])
        _push_email(user="alice", items=[{"s": "e"}])
        snap = riw.get_intelligence_snapshot("alice")
        assert len(snap["news"])  == 1
        assert len(snap["email"]) == 1
        assert snap["micro"] == []

    def test_all_four_sources_present(self, monkeypatch):
        import operator_state
        ts = _now_utc().timestamp()
        monkeypatch.setattr(
            operator_state, "get_operator_state",
            lambda uid: {
                "elins_history": [{"ts": ts, "topic": "x", "ep_flags": ["pressure"]}],
                "g_history": [],
            },
        )
        _push_news(user="alice",  items=[{"h": "n"}])
        _push_email(user="alice", items=[{"s": "e"}])
        _push_daily(user="alice")
        snap = riw.get_intelligence_snapshot("alice")
        assert len(snap["news"])  == 1
        assert len(snap["email"]) == 1
        assert len(snap["micro"]) == 1
        assert snap["daily_elins"] is not None


# ===========================================================================
# C. Determinism
# ===========================================================================
class TestDeterminism:
    def test_same_state_same_snapshot(self):
        _push_news(user="alice",  items=[{"h": "1"}])
        _push_news(user="alice",  items=[{"h": "2"}])
        _push_email(user="alice", items=[{"s": "e"}])
        snap1 = riw.get_intelligence_snapshot("alice")
        snap2 = riw.get_intelligence_snapshot("alice")
        # The two snapshots differ only in the `date` (consistent across both
        # within the same UTC day) — every list is sorted, every packet is
        # normalized to the same canonical form.
        assert snap1 == snap2

    def test_sort_order_stable(self):
        # Push out of order; both queries should return the same order.
        t1 = _now_utc() - timedelta(minutes=10)
        t2 = _now_utc() - timedelta(minutes=5)
        t3 = _now_utc() - timedelta(minutes=1)
        _push_news(user="alice", generated_at=t2, items=[{"o": "B"}])
        _push_news(user="alice", generated_at=t1, items=[{"o": "A"}])
        _push_news(user="alice", generated_at=t3, items=[{"o": "C"}])
        first  = riw.get_latest_news("alice")
        second = riw.get_latest_news("alice")
        assert first == second
        ordering = [p["items"][0]["o"] for p in first]
        assert ordering == ["A", "B", "C"]

    def test_snapshot_keys_always_identical(self):
        _push_news(user="alice", items=[{"h": "x"}])
        snap = riw.get_intelligence_snapshot("alice")
        assert set(snap.keys()) == {"date", "daily_elins", "news", "email", "micro", "macro"}


# ===========================================================================
# D. Timestamp normalization
# ===========================================================================
class TestTimestampNormalization:
    def test_normalizes_z_suffix(self):
        ts = _now_utc().replace(microsecond=0)
        ingestion_bus.write_packet({
            "type":         "news_basin",
            "user":         "alice",
            "generated_at": ts.isoformat().replace("+00:00", "Z"),
            "items":        [],
        })
        result = riw.get_latest_news("alice")
        assert len(result) == 1
        # Output uses +00:00 form (canonical).
        assert result[0]["generated_at"].endswith("+00:00")

    def test_normalizes_offset_format(self):
        ts = _now_utc().replace(microsecond=0)
        _push_news(user="alice", generated_at=ts.isoformat(), items=[])
        result = riw.get_latest_news("alice")
        assert len(result) == 1
        assert result[0]["generated_at"] == ts.isoformat()

    def test_normalizes_naive_to_utc(self):
        ts = _now_utc().replace(tzinfo=None, microsecond=0)
        ingestion_bus.write_packet({
            "type":         "news_basin",
            "user":         "alice",
            "generated_at": ts.isoformat(),  # naive
            "items":        [],
        })
        result = riw.get_latest_news("alice")
        assert len(result) == 1
        # Treated as UTC.
        assert "+00:00" in result[0]["generated_at"]

    def test_mixed_formats_sort_correctly(self):
        # Use second-precision deltas so both timestamps are guaranteed
        # to fall within the same UTC day even when the suite runs
        # within 30 minutes of UTC midnight. The test's purpose is to
        # verify mixed-format parsing + sorting, not day-boundary logic
        # (the day-boundary path is covered by dedicated tests below).
        t1 = _now_utc() - timedelta(seconds=2)
        t2 = _now_utc() - timedelta(seconds=1)
        # Push in mixed forms, out of order.
        ingestion_bus.write_packet({
            "type": "news_basin", "user": "alice",
            "generated_at": t2.isoformat().replace("+00:00", "Z"),
            "items": [{"o": "second"}],
        })
        _push_news(user="alice", generated_at=t1, items=[{"o": "first"}])
        result = riw.get_latest_news("alice")
        assert [p["items"][0]["o"] for p in result] == ["first", "second"]

    def test_mixed_formats_never_cross_day_boundary(self):
        """Second-precision deltas keep both timestamps in the same UTC
        day for any wall-clock start time. Both packets must survive
        the today-window filter."""
        t1 = _now_utc() - timedelta(seconds=2)
        t2 = _now_utc() - timedelta(seconds=1)
        # Same UTC date guaranteed.
        assert t1.date() == t2.date() == _now_utc().date()
        ingestion_bus.write_packet({
            "type": "news_basin", "user": "alice",
            "generated_at": t1.isoformat().replace("+00:00", "Z"),
            "items": [{"o": "first"}],
        })
        ingestion_bus.write_packet({
            "type": "news_basin", "user": "alice",
            "generated_at": t2.isoformat(),  # +00:00 form
            "items": [{"o": "second"}],
        })
        result = riw.get_latest_news("alice")
        assert len(result) == 2

    def test_mixed_formats_sort_correctly_even_near_midnight(
        self, monkeypatch: pytest.MonkeyPatch,
    ):
        """Pin _today_utc to a deterministic date and place both
        timestamps inside that day. Sorting works regardless of wall-
        clock proximity to midnight."""
        from datetime import date as _date_cls
        pinned = _date_cls(2026, 5, 11)
        monkeypatch.setattr(riw, "_today_utc", lambda: pinned)

        # Both timestamps inside the pinned UTC day, mixed formats.
        t1 = datetime(2026, 5, 11, 1, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 5, 11, 23, 0, 0, tzinfo=timezone.utc)

        ingestion_bus.write_packet({
            "type": "news_basin", "user": "alice",
            "generated_at": t2.isoformat().replace("+00:00", "Z"),
            "items": [{"o": "second"}],
        })
        ingestion_bus.write_packet({
            "type": "news_basin", "user": "alice",
            "generated_at": t1.isoformat(),
            "items": [{"o": "first"}],
        })
        result = riw.get_latest_news("alice")
        assert [p["items"][0]["o"] for p in result] == ["first", "second"]

    def test_mixed_formats_filter_out_yesterday(
        self, monkeypatch: pytest.MonkeyPatch,
    ):
        """A timestamp on yesterday's UTC date is filtered out by the
        today-window. Only today's timestamp survives."""
        from datetime import date as _date_cls
        pinned = _date_cls(2026, 5, 11)
        monkeypatch.setattr(riw, "_today_utc", lambda: pinned)

        yesterday_late = datetime(2026, 5, 10, 23, 59, 0, tzinfo=timezone.utc)
        today_early    = datetime(2026, 5, 11,  0,  1, 0, tzinfo=timezone.utc)

        ingestion_bus.write_packet({
            "type": "news_basin", "user": "alice",
            "generated_at": yesterday_late.isoformat().replace("+00:00", "Z"),
            "items": [{"o": "yesterday"}],
        })
        ingestion_bus.write_packet({
            "type": "news_basin", "user": "alice",
            "generated_at": today_early.isoformat(),
            "items": [{"o": "today"}],
        })
        result = riw.get_latest_news("alice")
        assert len(result) == 1
        assert result[0]["items"][0]["o"] == "today"


# ===========================================================================
# E. Ingestion bus integration
# ===========================================================================
class TestBusIntegration:
    def test_news_packets_routed_to_news(self):
        _push_news(user="alice",  items=[{"h": "x"}])
        _push_email(user="alice", items=[{"s": "y"}])
        assert len(riw.get_latest_news("alice"))           == 1
        assert len(riw.get_latest_email_signals("alice"))  == 1

    def test_packet_preserves_items_field(self):
        _push_news(user="alice", items=[{"h": "first"}, {"h": "second"}])
        result = riw.get_latest_news("alice")
        assert result[0]["items"] == [{"h": "first"}, {"h": "second"}]

    def test_packet_carries_packet_id_from_bus(self):
        pid = _push_news(user="alice", items=[])
        result = riw.get_latest_news("alice")
        assert result[0]["_packet_id"] == pid

    def test_packet_carries_received_at(self):
        _push_news(user="alice", items=[])
        result = riw.get_latest_news("alice")
        assert "_received_at" in result[0]
        assert isinstance(result[0]["_received_at"], (int, float))

    def test_daily_envelope_returned_from_bus_when_present(self):
        _push_daily(user="alice", macro={"field_weather": "mixed"})
        env = riw.get_today_elins("alice")
        assert env is not None
        assert env["macro"]["field_weather"] == "mixed"


# ===========================================================================
# F. Operator state integration
# ===========================================================================
class TestOperatorStateIntegration:
    def test_micro_in_window(self, monkeypatch):
        import operator_state
        ts = _now_utc().timestamp()
        monkeypatch.setattr(
            operator_state, "get_operator_state",
            lambda uid: {
                "elins_history": [{"ts": ts, "topic": "x"}],
                "g_history": [],
            },
        )
        micro = riw.get_latest_micro_signals("alice")
        assert len(micro) == 1
        assert micro[0]["topic"] == "x"
        assert micro[0]["kind"]  == "elins"

    def test_micro_out_of_window_excluded(self, monkeypatch):
        import operator_state
        yesterday_ts = (_now_utc() - timedelta(days=2)).timestamp()
        monkeypatch.setattr(
            operator_state, "get_operator_state",
            lambda uid: {
                "elins_history": [{"ts": yesterday_ts, "topic": "old"}],
                "g_history": [],
            },
        )
        assert riw.get_latest_micro_signals("alice") == []

    def test_micro_combines_both_history_sources(self, monkeypatch):
        import operator_state
        ts_e = _now_utc().timestamp()
        ts_g = ts_e - 60
        monkeypatch.setattr(
            operator_state, "get_operator_state",
            lambda uid: {
                "elins_history": [{"ts": ts_e, "topic": "e"}],
                "g_history":     [{"ts": ts_g, "topic": "g"}],
            },
        )
        micro = riw.get_latest_micro_signals("alice")
        kinds = sorted(m["kind"] for m in micro)
        assert kinds == ["elins", "g_run"]

    def test_micro_sorted_ascending_by_ts(self, monkeypatch):
        import operator_state
        ts_late = _now_utc().timestamp()
        ts_mid  = ts_late - 60
        ts_early = ts_late - 120
        monkeypatch.setattr(
            operator_state, "get_operator_state",
            lambda uid: {
                "elins_history": [
                    {"ts": ts_late, "topic": "C"},
                    {"ts": ts_early, "topic": "A"},
                ],
                "g_history":     [
                    {"ts": ts_mid,  "topic": "B"},
                ],
            },
        )
        micro = riw.get_latest_micro_signals("alice")
        assert [m["topic"] for m in micro] == ["A", "B", "C"]

    def test_micro_adds_ts_iso(self, monkeypatch):
        import operator_state
        ts = _now_utc().timestamp()
        monkeypatch.setattr(
            operator_state, "get_operator_state",
            lambda uid: {"elins_history": [{"ts": ts, "topic": "x"}], "g_history": []},
        )
        micro = riw.get_latest_micro_signals("alice")
        assert "ts_iso" in micro[0]
        assert "+00:00" in micro[0]["ts_iso"]


# ===========================================================================
# G. Archive fallback
# ===========================================================================
class TestArchiveFallback:
    def test_bus_empty_archive_present(self, _isolated_env):
        tmp = _isolated_env
        envelope = {
            "type": "daily_personal_elins",
            "user": "alice",
            "date": _now_utc().date().isoformat(),
            "macro": {"field_weather": "stable", "dominant_themes": ["US"], "risk_zones": []},
            "meso":  {"news": {}, "email": {}},
            "micro": {"message_count": 0, "ep_flags": {}, "notable_events": []},
            "summary": {"headline": "archived", "focus": []},
        }
        _write_daily_archive(tmp, user="alice", envelope=envelope)
        env = riw.get_today_elins("alice")
        assert env is not None
        assert env["summary"]["headline"] == "archived"

    def test_bus_takes_precedence_over_archive(self, _isolated_env):
        tmp = _isolated_env
        archive_env = {
            "type": "daily_personal_elins", "user": "alice",
            "date": _now_utc().date().isoformat(),
            "summary": {"headline": "from-archive", "focus": []},
        }
        _write_daily_archive(tmp, user="alice", envelope=archive_env)
        _push_daily(user="alice", summary={"headline": "from-bus", "focus": []})
        env = riw.get_today_elins("alice")
        assert env["summary"]["headline"] == "from-bus"

    def test_archive_missing_returns_none(self):
        # No bus packet, no archive file → None.
        assert riw.get_today_elins("alice") is None

    def test_archive_corrupt_json_returns_none(self, _isolated_env):
        tmp = _isolated_env
        archive_dir = tmp / "daily" / "alice"
        archive_dir.mkdir(parents=True, exist_ok=True)
        (archive_dir / f"{_now_utc().date().isoformat()}.json").write_text(
            "not json{{", encoding="utf-8",
        )
        assert riw.get_today_elins("alice") is None

    def test_archive_non_dict_returns_none(self, _isolated_env):
        tmp = _isolated_env
        archive_dir = tmp / "daily" / "alice"
        archive_dir.mkdir(parents=True, exist_ok=True)
        (archive_dir / f"{_now_utc().date().isoformat()}.json").write_text(
            json.dumps([1, 2, 3]), encoding="utf-8",
        )
        assert riw.get_today_elins("alice") is None


# ===========================================================================
# H. Error handling
# ===========================================================================
class TestErrorHandling:
    def test_operator_state_raises(self, monkeypatch):
        import operator_state
        def raises(uid):
            raise RuntimeError("vault down")
        monkeypatch.setattr(operator_state, "get_operator_state", raises)
        assert riw.get_latest_micro_signals("alice") == []
        # Snapshot still composes correctly.
        snap = riw.get_intelligence_snapshot("alice")
        assert snap["micro"] == []

    def test_operator_state_returns_non_dict(self, monkeypatch):
        import operator_state
        monkeypatch.setattr(
            operator_state, "get_operator_state",
            lambda uid: "not a dict",
        )
        assert riw.get_latest_micro_signals("alice") == []

    def test_packet_missing_user_field(self):
        ingestion_bus.write_packet({
            "type": "news_basin",
            # no 'user'
            "generated_at": _iso(_now_utc()),
            "items": [{"h": "x"}],
        })
        assert riw.get_latest_news("alice") == []

    def test_packet_missing_generated_at(self):
        ingestion_bus.write_packet({
            "type": "news_basin",
            "user": "alice",
            # no 'generated_at'
            "items": [{"h": "x"}],
        })
        assert riw.get_latest_news("alice") == []

    def test_packet_with_invalid_generated_at(self):
        ingestion_bus.write_packet({
            "type": "news_basin",
            "user": "alice",
            "generated_at": "not-a-date",
            "items": [{"h": "x"}],
        })
        assert riw.get_latest_news("alice") == []

    def test_entry_missing_ts_is_skipped(self, monkeypatch):
        import operator_state
        monkeypatch.setattr(
            operator_state, "get_operator_state",
            lambda uid: {
                "elins_history": [{"topic": "no-ts"}],
                "g_history": [],
            },
        )
        assert riw.get_latest_micro_signals("alice") == []

    def test_entry_with_invalid_ts_type_is_skipped(self, monkeypatch):
        import operator_state
        monkeypatch.setattr(
            operator_state, "get_operator_state",
            lambda uid: {
                "elins_history": [{"ts": "not-a-number", "topic": "x"}],
                "g_history": [],
            },
        )
        assert riw.get_latest_micro_signals("alice") == []


# ===========================================================================
# I. Snapshot schema
# ===========================================================================
class TestSnapshotSchema:
    def test_all_keys_present_when_empty(self):
        snap = riw.get_intelligence_snapshot("alice")
        for k in ("date", "daily_elins", "news", "email", "micro", "macro"):
            assert k in snap

    def test_all_keys_present_when_full(self, monkeypatch):
        import operator_state
        ts = _now_utc().timestamp()
        monkeypatch.setattr(
            operator_state, "get_operator_state",
            lambda uid: {"elins_history": [{"ts": ts, "topic": "x"}], "g_history": []},
        )
        _push_news(user="alice",  items=[{"h": "n"}])
        _push_email(user="alice", items=[{"s": "e"}])
        _push_daily(user="alice")
        snap = riw.get_intelligence_snapshot("alice")
        for k in ("date", "daily_elins", "news", "email", "micro", "macro"):
            assert k in snap

    def test_list_fields_never_none(self):
        snap = riw.get_intelligence_snapshot("alice")
        assert isinstance(snap["news"],  list)
        assert isinstance(snap["email"], list)
        assert isinstance(snap["micro"], list)

    def test_macro_is_always_dict(self):
        # No daily_elins → macro must be {} (not None)
        snap = riw.get_intelligence_snapshot("alice")
        assert snap["macro"] == {}
        # Empty-day daily envelope (no macro key) → macro must be {}
        _push_daily(user="alice")  # full envelope WITH macro
        snap = riw.get_intelligence_snapshot("alice")
        assert isinstance(snap["macro"], dict)

    def test_empty_envelope_short_circuit_yields_empty_macro(self):
        """daily_personal_elins's empty-day envelope is
        {type, user, date, empty: True} — no 'macro' key. macro must
        still be {} (not None, not missing)."""
        ingestion_bus.write_packet({
            "type":  "daily_personal_elins",
            "user":  "alice",
            "date":  _now_utc().date().isoformat(),
            "generated_at": _iso(_now_utc()),
            "empty": True,
        })
        snap = riw.get_intelligence_snapshot("alice")
        assert snap["daily_elins"]["empty"] is True
        assert snap["macro"] == {}


# ===========================================================================
# J. Multi-user isolation
# ===========================================================================
class TestMultiUserIsolation:
    def test_news_isolated_per_user(self):
        _push_news(user="alice", items=[{"h": "alice"}])
        _push_news(user="bob",   items=[{"h": "bob"}])
        assert len(riw.get_latest_news("alice")) == 1
        assert len(riw.get_latest_news("bob"))   == 1
        assert riw.get_latest_news("alice")[0]["items"][0]["h"] == "alice"
        assert riw.get_latest_news("bob")[0]["items"][0]["h"]   == "bob"

    def test_email_isolated_per_user(self):
        _push_email(user="alice", items=[{"s": "alice"}])
        _push_email(user="bob",   items=[{"s": "bob"}])
        assert riw.get_latest_email_signals("alice")[0]["items"][0]["s"] == "alice"
        assert riw.get_latest_email_signals("bob")[0]["items"][0]["s"]   == "bob"

    def test_daily_archive_isolated_per_user(self, _isolated_env):
        tmp = _isolated_env
        _write_daily_archive(tmp, user="alice", envelope={
            "type": "daily_personal_elins", "user": "alice",
            "summary": {"headline": "for-alice", "focus": []},
        })
        _write_daily_archive(tmp, user="bob", envelope={
            "type": "daily_personal_elins", "user": "bob",
            "summary": {"headline": "for-bob", "focus": []},
        })
        assert riw.get_today_elins("alice")["summary"]["headline"] == "for-alice"
        assert riw.get_today_elins("bob")["summary"]["headline"]   == "for-bob"


# ===========================================================================
# K. Cross-day filtering
# ===========================================================================
class TestCrossDayFiltering:
    def test_yesterday_news_excluded(self):
        yesterday = _now_utc() - timedelta(days=1, hours=2)  # safely yesterday
        _push_news(user="alice", generated_at=yesterday, items=[{"h": "old"}])
        assert riw.get_latest_news("alice") == []

    def test_future_news_excluded(self):
        tomorrow = _now_utc() + timedelta(days=1, hours=2)
        _push_news(user="alice", generated_at=tomorrow, items=[{"h": "future"}])
        assert riw.get_latest_news("alice") == []

    def test_today_news_included(self):
        # Use a timestamp safely within today's window: 10 minutes ago.
        in_window = _now_utc() - timedelta(minutes=10)
        _push_news(user="alice", generated_at=in_window, items=[{"h": "in"}])
        result = riw.get_latest_news("alice")
        assert len(result) == 1
        assert result[0]["items"][0]["h"] == "in"


# ===========================================================================
# L. Individual function contracts
# ===========================================================================
class TestIndividualFunctions:
    def test_get_today_elins_return_type(self):
        # None when empty
        assert riw.get_today_elins("alice") is None
        # dict when present
        _push_daily(user="alice")
        env = riw.get_today_elins("alice")
        assert isinstance(env, dict)

    def test_get_latest_news_return_type(self):
        assert riw.get_latest_news("alice") == []
        _push_news(user="alice", items=[])
        assert isinstance(riw.get_latest_news("alice"), list)

    def test_get_latest_email_signals_return_type(self):
        assert riw.get_latest_email_signals("alice") == []
        _push_email(user="alice", items=[])
        assert isinstance(riw.get_latest_email_signals("alice"), list)

    def test_get_latest_micro_signals_return_type(self):
        assert riw.get_latest_micro_signals("alice") == []
        assert isinstance(riw.get_latest_micro_signals("alice"), list)

    def test_get_intelligence_snapshot_never_raises(self, monkeypatch):
        """Every failure path lands the same canonical empty snapshot."""
        import operator_state
        def raises(uid): raise RuntimeError("simulated")
        monkeypatch.setattr(operator_state, "get_operator_state", raises)
        snap = riw.get_intelligence_snapshot("alice")
        assert set(snap.keys()) == {"date", "daily_elins", "news", "email", "micro", "macro"}
        assert snap["daily_elins"] is None
        assert snap["news"]  == []
        assert snap["email"] == []
        assert snap["micro"] == []
        assert snap["macro"] == {}
