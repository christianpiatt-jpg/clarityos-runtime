"""
Tests for intelligence_scheduler.py (Phase 2 Unit 4).

Eight test classes matching the spec § 8 plan:
  1. TestDailyElinsCadence
  2. TestNewsBasinCadence
  3. TestEmailDashCadence
  4. TestStatePersistence
  5. TestTickOrdering
  6. TestTickReturnValues
  7. TestMultiUserScheduling
  8. TestDeterminism

All three underlying producers are monkey-patched to canned envelopes
so the test suite is hermetic — no real network, no real perplexity,
no real filesystem outside tmp_path.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

import intelligence_scheduler as sched


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Scope the scheduler state file to a per-test tmp path and clear
    every env var the scheduler reads."""
    state_file = tmp_path / "scheduler_state.json"
    monkeypatch.setenv("CLARITYOS_SCHEDULER_STATE", str(state_file))
    monkeypatch.delenv("CLARITYOS_EMAIL_EP_SCHEDULED", raising=False)
    monkeypatch.delenv("CLARITYOS_NEWS_TIMES",        raising=False)
    yield state_file


@pytest.fixture
def mock_runners(monkeypatch: pytest.MonkeyPatch):
    """Replace the three underlying producers with canned-envelope stubs
    that record their calls in order so tests can assert ordering."""
    call_log: list[tuple] = []

    def fake_news(user_id):
        call_log.append(("news", user_id))
        return {
            "type":    "news_basin",
            "user":    user_id,
            "items":   [{"headline": "X"}],
            "_marker": "fake-news",
        }

    def fake_email(raw, user_id):
        call_log.append(("email", user_id, raw))
        return {
            "type":    "email_ep_dash",
            "user":    user_id,
            "items":   [],
            "_marker": "fake-email",
        }

    def fake_daily(user_id, d=None):
        call_log.append(("daily", user_id, d))
        return {
            "type":    "daily_personal_elins",
            "user":    user_id,
            "date":    str(d) if d is not None else None,
            "_marker": "fake-daily",
        }

    import daily_personal_elins
    import email_ep_dash
    import personal_news_basin

    monkeypatch.setattr(
        personal_news_basin,  "run_news_basin",          fake_news,
    )
    monkeypatch.setattr(
        email_ep_dash,        "run_email_ep_dash",       fake_email,
    )
    monkeypatch.setattr(
        daily_personal_elins, "run_daily_personal_elins", fake_daily,
    )
    return call_log


# Convenience constants used throughout the suite.
_UTC = timezone.utc

_T_BEFORE_NEWS_1 = datetime(2026, 5, 11,  8, 30, tzinfo=_UTC)   # before 09:00
_T_AT_NEWS_1    = datetime(2026, 5, 11,  9,  5, tzinfo=_UTC)    # just after 09:00
_T_NOON         = datetime(2026, 5, 11, 12,  0, tzinfo=_UTC)
_T_AT_EMAIL     = datetime(2026, 5, 11, 13, 30, tzinfo=_UTC)    # after 13:00
_T_AT_NEWS_2    = datetime(2026, 5, 11, 21,  5, tzinfo=_UTC)    # just after 21:00
_T_NEXT_MORNING = datetime(2026, 5, 12,  9,  5, tzinfo=_UTC)    # day rollover


# ===========================================================================
# 1. TestDailyElinsCadence
# ===========================================================================
class TestDailyElinsCadence:
    def test_runs_once_per_day_first_call(self, mock_runners):
        sched.register_user("alice")
        envelopes = sched.tick(now=_T_AT_NEWS_1)
        kinds = sorted(e["type"] for e in envelopes)
        assert "daily_personal_elins" in kinds

    def test_no_double_run_same_day(self, mock_runners):
        sched.register_user("alice")
        sched.tick(now=_T_AT_NEWS_1)         # first tick → daily runs
        before = sum(1 for c in mock_runners if c[0] == "daily")
        sched.tick(now=_T_NOON)              # later same day → no re-run
        after = sum(1 for c in mock_runners if c[0] == "daily")
        assert before == 1
        assert after  == 1

    def test_runs_next_day_automatically(self, mock_runners):
        sched.register_user("alice")
        sched.tick(now=_T_AT_NEWS_1)
        sched.tick(now=_T_NEXT_MORNING)
        daily_calls = [c for c in mock_runners if c[0] == "daily"]
        assert len(daily_calls) == 2
        # Each call carries the date it was running for.
        dates = [c[2] for c in daily_calls]
        assert dates == [date(2026, 5, 11), date(2026, 5, 12)]

    def test_state_records_last_daily_elins(self, mock_runners):
        sched.register_user("alice")
        sched.tick(now=_T_AT_NEWS_1)
        s = sched.get_state()
        assert s["users"]["alice"]["last_daily_elins"] == "2026-05-11"


# ===========================================================================
# 2. TestNewsBasinCadence
# ===========================================================================
class TestNewsBasinCadence:
    def test_runs_at_first_news_time(self, mock_runners):
        sched.register_user("alice")
        sched.tick(now=_T_AT_NEWS_1)
        news_calls = [c for c in mock_runners if c[0] == "news"]
        assert len(news_calls) == 1

    def test_does_not_run_before_first_news_time(self, mock_runners):
        sched.register_user("alice")
        sched.tick(now=_T_BEFORE_NEWS_1)
        news_calls = [c for c in mock_runners if c[0] == "news"]
        assert news_calls == []

    def test_runs_at_second_news_time(self, mock_runners):
        sched.register_user("alice")
        sched.tick(now=_T_AT_NEWS_1)   # 09:05 → news[0] fires
        sched.tick(now=_T_AT_NEWS_2)   # 21:05 → news[1] fires
        news_calls = [c for c in mock_runners if c[0] == "news"]
        assert len(news_calls) == 2

    def test_no_double_run_between_times(self, mock_runners):
        sched.register_user("alice")
        sched.tick(now=_T_AT_NEWS_1)
        sched.tick(now=_T_NOON)              # between 09:00 and 21:00 → no fire
        news_calls = [c for c in mock_runners if c[0] == "news"]
        assert len(news_calls) == 1

    def test_next_news_basin_pointer_advances(self, mock_runners):
        sched.register_user("alice")
        sched.tick(now=_T_AT_NEWS_1)
        s = sched.get_state()
        next_ts = sched._parse_iso(s["users"]["alice"]["next_news_basin"])
        # After 09:05, next news is today's 21:00
        assert next_ts == datetime(2026, 5, 11, 21, 0, tzinfo=_UTC)
        sched.tick(now=_T_AT_NEWS_2)
        s = sched.get_state()
        next_ts = sched._parse_iso(s["users"]["alice"]["next_news_basin"])
        # After 21:05, next news rolls to tomorrow 09:00
        assert next_ts == datetime(2026, 5, 12, 9, 0, tzinfo=_UTC)

    def test_custom_news_times_env(self, mock_runners, monkeypatch):
        monkeypatch.setenv("CLARITYOS_NEWS_TIMES", "06:00,18:00")
        sched.register_user("alice")
        sched.tick(now=datetime(2026, 5, 11, 6, 30, tzinfo=_UTC))
        news_calls = [c for c in mock_runners if c[0] == "news"]
        assert len(news_calls) == 1


# ===========================================================================
# 3. TestEmailDashCadence
# ===========================================================================
class TestEmailDashCadence:
    def test_on_demand_always_works(self, mock_runners):
        env = sched.run_email_ep_dash_once("From: x\n\nbody", "alice")
        assert env is not None
        assert env["type"] == "email_ep_dash"
        email_calls = [c for c in mock_runners if c[0] == "email"]
        assert len(email_calls) == 1

    def test_scheduled_mode_disabled_by_default(self, mock_runners):
        """Without the env var, tick at 13:30 should NOT mark an email
        scheduled tick."""
        sched.register_user("alice")
        sched.tick(now=_T_AT_EMAIL)
        s = sched.get_state()
        assert "last_email_scheduled_tick" not in s["users"]["alice"]

    def test_scheduled_mode_records_tick_when_enabled(
        self, mock_runners, monkeypatch,
    ):
        monkeypatch.setenv("CLARITYOS_EMAIL_EP_SCHEDULED", "1")
        sched.register_user("alice")
        sched.tick(now=_T_AT_EMAIL)
        s = sched.get_state()
        assert "last_email_scheduled_tick" in s["users"]["alice"]

    def test_scheduled_mode_does_not_fire_before_13(
        self, mock_runners, monkeypatch,
    ):
        monkeypatch.setenv("CLARITYOS_EMAIL_EP_SCHEDULED", "1")
        sched.register_user("alice")
        sched.tick(now=_T_NOON)   # 12:00 — before 13:00
        s = sched.get_state()
        assert "last_email_scheduled_tick" not in s["users"]["alice"]

    def test_scheduled_mode_does_not_invoke_runner(
        self, mock_runners, monkeypatch,
    ):
        """Scheduled mode records a cadence marker but does NOT auto-fetch
        raw — the email runner should not be invoked during tick."""
        monkeypatch.setenv("CLARITYOS_EMAIL_EP_SCHEDULED", "1")
        sched.register_user("alice")
        sched.tick(now=_T_AT_EMAIL)
        email_calls = [c for c in mock_runners if c[0] == "email"]
        assert email_calls == []


# ===========================================================================
# 4. TestStatePersistence
# ===========================================================================
class TestStatePersistence:
    def test_state_file_created_on_register(self, _isolated_state):
        assert not _isolated_state.exists()
        sched.register_user("alice")
        assert _isolated_state.exists()

    def test_atomic_write_no_temp_files_remain(self, _isolated_state, mock_runners):
        sched.register_user("alice")
        sched.tick(now=_T_AT_NEWS_1)
        # Only the canonical state file should remain — no .tmp leftovers.
        files = list(_isolated_state.parent.iterdir())
        names = [f.name for f in files]
        assert _isolated_state.name in names
        for n in names:
            assert not n.endswith(".tmp")

    def test_state_round_trip(self, _isolated_state, mock_runners):
        sched.register_user("alice")
        sched.tick(now=_T_AT_NEWS_1)
        raw = json.loads(_isolated_state.read_text(encoding="utf-8"))
        assert "alice" in raw["users"]
        assert raw["users"]["alice"]["last_daily_elins"] == "2026-05-11"
        # last_news_basin is the now stamp (ISO 8601)
        assert "last_news_basin" in raw["users"]["alice"]

    def test_corrupt_whole_file_resets_to_empty(self, _isolated_state):
        _isolated_state.write_text("not json{{{", encoding="utf-8")
        state = sched.get_state()
        assert state == {"users": {}}

    def test_corrupt_user_entry_dropped(self, _isolated_state):
        _isolated_state.write_text(
            json.dumps({"users": {
                "alice": {"last_daily_elins": "2026-05-11"},
                "bob":   "not a dict",
            }}),
            encoding="utf-8",
        )
        state = sched.get_state()
        assert "alice" in state["users"]
        assert "bob"   not in state["users"]

    def test_missing_file_returns_empty(self, _isolated_state):
        assert not _isolated_state.exists()
        state = sched.get_state()
        assert state == {"users": {}}

    def test_unregister_user(self, _isolated_state):
        sched.register_user("alice")
        sched.register_user("bob")
        assert sched.unregister_user("alice") is True
        assert sched.unregister_user("alice") is False   # idempotent
        state = sched.get_state()
        assert list(state["users"].keys()) == ["bob"]

    def test_register_rejects_bad_user_id(self):
        with pytest.raises(ValueError):
            sched.register_user("")
        with pytest.raises(ValueError):
            sched.register_user("   ")
        with pytest.raises(ValueError):
            sched.register_user(None)  # type: ignore[arg-type]


# ===========================================================================
# 5. TestTickOrdering
# ===========================================================================
class TestTickOrdering:
    def test_news_email_daily_ordering(self, mock_runners, monkeypatch):
        """Per spec § 5: execute news → email → daily within each user."""
        monkeypatch.setenv("CLARITYOS_EMAIL_EP_SCHEDULED", "1")
        sched.register_user("alice")
        sched.tick(now=_T_AT_EMAIL)   # 13:30 — both news[0] and email and daily fire

        # Email scheduled mode records a tick but doesn't invoke the runner,
        # so we only see news + daily in the call log. Verify their order.
        kinds = [c[0] for c in mock_runners]
        # news must come before daily
        assert kinds.index("news") < kinds.index("daily")

    def test_news_before_daily(self, mock_runners):
        sched.register_user("alice")
        sched.tick(now=_T_AT_NEWS_1)
        kinds = [c[0] for c in mock_runners]
        assert kinds == ["news", "daily"]


# ===========================================================================
# 6. TestTickReturnValues
# ===========================================================================
class TestTickReturnValues:
    def test_returns_list_of_envelopes(self, mock_runners):
        sched.register_user("alice")
        envelopes = sched.tick(now=_T_AT_NEWS_1)
        assert isinstance(envelopes, list)
        assert len(envelopes) == 2  # news + daily
        kinds = sorted(e["type"] for e in envelopes)
        assert kinds == ["daily_personal_elins", "news_basin"]

    def test_empty_list_when_no_users(self, mock_runners):
        envelopes = sched.tick(now=_T_AT_NEWS_1)
        assert envelopes == []

    def test_empty_list_when_no_tasks_triggered(self, mock_runners):
        sched.register_user("alice")
        sched.tick(now=_T_AT_NEWS_1)   # initial run
        envelopes = sched.tick(now=_T_NOON)  # nothing new triggers
        assert envelopes == []

    def test_skips_envelope_when_runner_returns_none(self, monkeypatch):
        """Producers may return None (e.g., empty-day short-circuit).
        tick should drop those rather than including None in the list."""
        import daily_personal_elins
        import personal_news_basin

        monkeypatch.setattr(
            personal_news_basin, "run_news_basin",
            lambda uid: None,
        )
        monkeypatch.setattr(
            daily_personal_elins, "run_daily_personal_elins",
            lambda uid, d=None: None,
        )
        sched.register_user("alice")
        envelopes = sched.tick(now=_T_AT_NEWS_1)
        assert envelopes == []

    def test_runner_exception_doesnt_break_tick(self, monkeypatch, mock_runners):
        """If one runner raises, tick logs + skips and continues. State
        still advances so we don't retry every tick."""
        import personal_news_basin

        def fails(uid):
            raise RuntimeError("simulated failure")
        monkeypatch.setattr(personal_news_basin, "run_news_basin", fails)

        sched.register_user("alice")
        envelopes = sched.tick(now=_T_AT_NEWS_1)
        # No news envelope (failed), but daily still ran
        kinds = sorted(e["type"] for e in envelopes)
        assert "news_basin" not in kinds
        assert "daily_personal_elins" in kinds

        # State advanced so retry won't happen this minute
        s = sched.get_state()
        assert "last_news_basin" in s["users"]["alice"]


# ===========================================================================
# 7. TestMultiUserScheduling
# ===========================================================================
class TestMultiUserScheduling:
    def test_independent_per_user_cadence(self, mock_runners):
        sched.register_user("alice")
        sched.register_user("bob")
        sched.tick(now=_T_AT_NEWS_1)
        # Both users got the same cadence treatment in the same tick.
        news_users = sorted(c[1] for c in mock_runners if c[0] == "news")
        daily_users = sorted(c[1] for c in mock_runners if c[0] == "daily")
        assert news_users  == ["alice", "bob"]
        assert daily_users == ["alice", "bob"]

    def test_one_user_failure_doesnt_block_others(self, monkeypatch):
        """A runner raising for one user shouldn't prevent the other user
        from completing its cadence."""
        call_users: list[tuple] = []

        def selective_news(uid):
            call_users.append(("news", uid))
            if uid == "alice":
                raise RuntimeError("alice news broken")
            return {"type": "news_basin", "user": uid, "items": []}

        def daily_ok(uid, d=None):
            call_users.append(("daily", uid))
            return {"type": "daily_personal_elins", "user": uid, "date": str(d)}

        import daily_personal_elins
        import personal_news_basin
        monkeypatch.setattr(personal_news_basin, "run_news_basin", selective_news)
        monkeypatch.setattr(daily_personal_elins, "run_daily_personal_elins", daily_ok)

        sched.register_user("alice")
        sched.register_user("bob")
        envelopes = sched.tick(now=_T_AT_NEWS_1)

        # Bob's news envelope made it through
        bob_news = [e for e in envelopes if e["type"] == "news_basin" and e["user"] == "bob"]
        assert len(bob_news) == 1
        # Alice's news envelope did not (runner raised)
        alice_news = [e for e in envelopes if e["type"] == "news_basin" and e["user"] == "alice"]
        assert alice_news == []
        # But Alice's daily still ran
        alice_daily = [e for e in envelopes if e["type"] == "daily_personal_elins" and e["user"] == "alice"]
        assert len(alice_daily) == 1

    def test_independent_state_per_user(self, mock_runners):
        sched.register_user("alice")
        sched.register_user("bob")

        # Tick at 09:05 advances both users equally.
        sched.tick(now=_T_AT_NEWS_1)

        # Unregister alice; tick at 21:05 should advance only bob.
        sched.unregister_user("alice")
        before_news = sum(1 for c in mock_runners if c[0] == "news")
        sched.tick(now=_T_AT_NEWS_2)
        after_news = sum(1 for c in mock_runners if c[0] == "news")
        # Only bob ran news the second time
        assert after_news == before_news + 1
        assert mock_runners[-1] == ("news", "bob")


# ===========================================================================
# 8. TestDeterminism
# ===========================================================================
class TestDeterminism:
    def _snapshot_state(self) -> dict:
        return sched.get_state()

    def test_same_now_same_start_state_same_output(
        self, _isolated_state, mock_runners,
    ):
        """Reset to a known initial state, tick twice with the same `now`
        on the same initial state — observed output identical."""
        sched.register_user("alice")
        initial = self._snapshot_state()

        # Run 1
        env1 = sched.tick(now=_T_AT_NEWS_1)
        final1 = self._snapshot_state()

        # Reset state to initial.
        _isolated_state.write_text(
            json.dumps(initial), encoding="utf-8",
        )
        # Reset call log so the new run sees only its own calls.
        mock_runners.clear()

        # Run 2 with the same starting state and same now.
        env2 = sched.tick(now=_T_AT_NEWS_1)
        final2 = self._snapshot_state()

        assert env1 == env2
        assert final1 == final2

    def test_user_iteration_order_is_sorted(self, mock_runners):
        sched.register_user("charlie")
        sched.register_user("alice")
        sched.register_user("bob")
        sched.tick(now=_T_AT_NEWS_1)
        news_order = [c[1] for c in mock_runners if c[0] == "news"]
        assert news_order == sorted(news_order) == ["alice", "bob", "charlie"]

    def test_aliased_entrypoint(self, mock_runners):
        """run_scheduled_tasks should produce the same result as tick."""
        sched.register_user("alice")
        envelopes = sched.run_scheduled_tasks(now=_T_AT_NEWS_1)
        kinds = sorted(e["type"] for e in envelopes)
        assert kinds == ["daily_personal_elins", "news_basin"]
