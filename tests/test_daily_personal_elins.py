"""
Tests for daily_personal_elins.py (Phase 2 Unit 3).

Same hermetic discipline as Units 1+2: env-var-driven library dir,
ingestion-bus reset, no network. Real news_basin and email_ep_dash
modules are exercised end-to-end (their writes land in the bus, which
the composer then re-reads) so the integration boundary is verified.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from ELINS import ingestion_bus
import daily_personal_elins as dpe
import email_ep_dash as ed
import personal_news_basin as pnb


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Reset bus + scope library dirs for all three Phase-2 modules."""
    monkeypatch.setenv("CLARITYOS_DAILY_ELINS_DIR",   str(tmp_path / "daily"))
    monkeypatch.setenv("CLARITYOS_NEWS_BASIN_DIR",    str(tmp_path / "news"))
    monkeypatch.setenv("CLARITYOS_EMAIL_EP_DASH_DIR", str(tmp_path / "edash"))
    monkeypatch.setenv(
        "CLARITYOS_NEWS_BASIN_SOURCES",
        str(tmp_path / "sources.json"),  # used only by run_news_basin in some tests
    )
    monkeypatch.delenv("CLARITYOS_NEWS_BASIN_EP", raising=False)
    ingestion_bus._reset_memory_for_tests()
    yield tmp_path
    ingestion_bus._reset_memory_for_tests()


@pytest.fixture
def fixed_dt():
    """A stable ISO timestamp used as ``generated_at`` for determinism tests."""
    return "2026-05-11T23:59:59+00:00"


@pytest.fixture
def target_date():
    return date(2026, 5, 11)


# ---------------------------------------------------------------------------
# Helpers — build synthetic envelopes directly via bus (no perplexity)
# ---------------------------------------------------------------------------
def _push_news_envelope(
    *,
    user: str,
    generated_at: str,
    items: list[dict],
) -> str:
    """Push a synthetic news_basin envelope onto the bus and return its packet_id."""
    env = {
        "type":         "news_basin",
        "user":         user,
        "generated_at": generated_at,
        "items":        items,
    }
    return ingestion_bus.write_packet(env)


def _push_email_envelope(
    *,
    user: str,
    generated_at: str,
    items: list[dict],
) -> str:
    env = {
        "type":         "email_ep_dash",
        "user":         user,
        "generated_at": generated_at,
        "items":        items,
    }
    return ingestion_bus.write_packet(env)


def _news_item(
    *,
    source: str = "Reuters",
    headline: str = "Sample",
    region: str = "US",
    pressure: str = "low",
    sentiment: float = 0.0,
    category: str = "general",
) -> dict:
    return {
        "source":                source,
        "headline":              headline,
        "timestamp":             "2026-05-11T08:00:00+00:00",
        "category":              category,
        "sentiment":             sentiment,
        "pressure":              pressure,
        "narrative_temperature": 0.5,
        "region":                region,
        "retrieved_at":          "2026-05-11T08:00:00+00:00",
    }


def _email_item(
    *,
    importance: str = "MEDIUM",
    has_deadline: bool = False,
    thread_key: str = "abc1234567890123",
    ep_flags: list = None,
    subject: str = "Sample",
) -> dict:
    return {
        "from":               "alice@x.com",
        "to":                 ["bob@x.com"],
        "cc":                 [],
        "subject":            subject,
        "date":               "Mon, 11 May 2026 08:00:00 +0000",
        "body":               "Sample body",
        "thread_key":         thread_key,
        "importance":         importance,
        "has_deadline":       has_deadline,
        "commitment_markers": [],
        "request_markers":    [],
        "ep_flags":           ep_flags or [],
    }


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------
class TestDateHelpers:
    def test_day_window_utc(self):
        start, end = dpe._day_window_utc(date(2026, 5, 11))
        assert start == datetime(2026, 5, 11, 0, 0, tzinfo=timezone.utc)
        assert end   == datetime(2026, 5, 12, 0, 0, tzinfo=timezone.utc)

    def test_parse_iso_with_z(self):
        dt = dpe._parse_iso("2026-05-11T12:00:00Z")
        assert dt.year == 2026 and dt.tzinfo is not None

    def test_parse_iso_with_offset(self):
        dt = dpe._parse_iso("2026-05-11T12:00:00+00:00")
        assert dt is not None and dt.tzinfo is not None

    def test_parse_iso_naive_coerces_to_utc(self):
        dt = dpe._parse_iso("2026-05-11T12:00:00")
        assert dt is not None
        assert dt.tzinfo == timezone.utc

    def test_parse_iso_garbage_returns_none(self):
        assert dpe._parse_iso("nope") is None
        assert dpe._parse_iso(None) is None
        assert dpe._parse_iso("") is None

    def test_coerce_date_accepts_date(self):
        d = date(2026, 5, 11)
        assert dpe._coerce_date(d) == d

    def test_coerce_date_accepts_datetime(self):
        dt = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
        assert dpe._coerce_date(dt) == date(2026, 5, 11)

    def test_coerce_date_accepts_string(self):
        assert dpe._coerce_date("2026-05-11") == date(2026, 5, 11)

    def test_coerce_date_none_returns_today(self):
        today = datetime.now(timezone.utc).date()
        assert dpe._coerce_date(None) == today


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------
class TestCollectNewsSignals:
    def test_flattens_items_for_user(self, target_date):
        start, end = dpe._day_window_utc(target_date)
        _push_news_envelope(
            user="alice",
            generated_at="2026-05-11T08:00:00+00:00",
            items=[_news_item(source="A"), _news_item(source="B")],
        )
        items = dpe.collect_news_signals("alice", since=start, until=end)
        assert len(items) == 2
        assert items[0]["source"] == "A"
        assert items[1]["source"] == "B"

    def test_filters_by_user(self, target_date):
        start, end = dpe._day_window_utc(target_date)
        _push_news_envelope(
            user="alice",
            generated_at="2026-05-11T08:00:00+00:00",
            items=[_news_item(source="alice-only")],
        )
        _push_news_envelope(
            user="bob",
            generated_at="2026-05-11T08:00:00+00:00",
            items=[_news_item(source="bob-only")],
        )
        assert len(dpe.collect_news_signals("alice", since=start, until=end)) == 1
        assert len(dpe.collect_news_signals("bob",   since=start, until=end)) == 1

    def test_filters_by_window(self, target_date):
        start, end = dpe._day_window_utc(target_date)
        # Yesterday
        _push_news_envelope(
            user="alice",
            generated_at="2026-05-10T23:00:00+00:00",
            items=[_news_item(source="yesterday")],
        )
        # Today
        _push_news_envelope(
            user="alice",
            generated_at="2026-05-11T08:00:00+00:00",
            items=[_news_item(source="today")],
        )
        # Tomorrow
        _push_news_envelope(
            user="alice",
            generated_at="2026-05-12T01:00:00+00:00",
            items=[_news_item(source="tomorrow")],
        )
        items = dpe.collect_news_signals("alice", since=start, until=end)
        assert len(items) == 1
        assert items[0]["source"] == "today"

    def test_empty_bus_returns_empty(self, target_date):
        start, end = dpe._day_window_utc(target_date)
        assert dpe.collect_news_signals("alice", since=start, until=end) == []

    def test_handles_envelope_without_items_key(self, target_date):
        start, end = dpe._day_window_utc(target_date)
        ingestion_bus.write_packet({
            "type": "news_basin", "user": "alice",
            "generated_at": "2026-05-11T08:00:00+00:00",
            # no 'items'
        })
        assert dpe.collect_news_signals("alice", since=start, until=end) == []


class TestCollectEmailSignals:
    def test_flattens_for_user(self, target_date):
        start, end = dpe._day_window_utc(target_date)
        _push_email_envelope(
            user="alice",
            generated_at="2026-05-11T08:00:00+00:00",
            items=[_email_item(subject="A"), _email_item(subject="B")],
        )
        items = dpe.collect_email_signals("alice", since=start, until=end)
        assert len(items) == 2

    def test_independent_of_news_type(self, target_date):
        start, end = dpe._day_window_utc(target_date)
        _push_news_envelope(
            user="alice",
            generated_at="2026-05-11T08:00:00+00:00",
            items=[_news_item()],
        )
        _push_email_envelope(
            user="alice",
            generated_at="2026-05-11T08:00:00+00:00",
            items=[_email_item()],
        )
        assert len(dpe.collect_news_signals("alice",  since=start, until=end)) == 1
        assert len(dpe.collect_email_signals("alice", since=start, until=end)) == 1


class TestCollectMicroSignals:
    def test_filters_history_to_window(self, target_date, monkeypatch):
        start, end = dpe._day_window_utc(target_date)
        # Fake operator_state: returns history entries inside + outside the window.
        ts_inside = (start + timedelta(hours=8)).timestamp()
        ts_before = (start - timedelta(hours=1)).timestamp()
        ts_after  = (end + timedelta(hours=1)).timestamp()
        fake_state = {
            "elins_history": [
                {"ts": ts_before, "topic": "old"},
                {"ts": ts_inside, "topic": "current", "ep_flags": ["pressure"]},
            ],
            "g_history": [
                {"ts": ts_inside, "topic": "g-current"},
                {"ts": ts_after,  "topic": "future"},
            ],
        }

        import operator_state
        monkeypatch.setattr(
            operator_state, "get_operator_state",
            lambda uid: fake_state,
        )
        signals = dpe.collect_micro_signals("alice", since=start, until=end)
        topics = [s.get("topic") for s in signals]
        assert "current"  in topics
        assert "g-current" in topics
        assert "old"      not in topics
        assert "future"   not in topics

    def test_tags_kind(self, target_date, monkeypatch):
        start, end = dpe._day_window_utc(target_date)
        ts = (start + timedelta(hours=8)).timestamp()
        fake_state = {
            "elins_history": [{"ts": ts}],
            "g_history":     [{"ts": ts}],
        }
        import operator_state
        monkeypatch.setattr(operator_state, "get_operator_state", lambda uid: fake_state)
        signals = dpe.collect_micro_signals("alice", since=start, until=end)
        kinds = sorted(s["kind"] for s in signals)
        assert kinds == ["elins", "g_run"]

    def test_operator_state_failure_returns_empty(self, target_date, monkeypatch):
        start, end = dpe._day_window_utc(target_date)
        import operator_state

        def raises(uid):
            raise RuntimeError("vault down")
        monkeypatch.setattr(operator_state, "get_operator_state", raises)
        assert dpe.collect_micro_signals("alice", since=start, until=end) == []


# ---------------------------------------------------------------------------
# Aggregators
# ---------------------------------------------------------------------------
class TestAggregators:
    def test_news_aggregation(self):
        items = [
            _news_item(source="Reuters", region="US",   pressure="high"),
            _news_item(source="Reuters", region="EU",   pressure="medium"),
            _news_item(source="AP",      region="US",   pressure="low"),
            _news_item(source="AP",      region="APAC", pressure="high"),
            _news_item(source="WSJ",     region="US",   pressure="medium"),
        ]
        agg = dpe._aggregate_news(items)
        assert agg["count"] == 5
        assert agg["pressure_distribution"] == {"HIGH": 2, "MEDIUM": 2, "LOW": 1}
        assert agg["regions"] == {"US": 3, "EU": 1, "APAC": 1}
        # Top 3 sources by frequency
        assert set(agg["top_sources"]) == {"Reuters", "AP", "WSJ"}

    def test_email_aggregation(self):
        items = [
            _email_item(importance="HIGH",   has_deadline=True,  thread_key="t1"),
            _email_item(importance="MEDIUM", has_deadline=True,  thread_key="t2"),
            _email_item(importance="HIGH",   has_deadline=False, thread_key="t1"),
            _email_item(importance="LOW",    has_deadline=False, thread_key="t3"),
        ]
        agg = dpe._aggregate_emails(items)
        assert agg["count"]           == 4
        assert agg["high_importance"] == 2
        assert agg["with_deadlines"]  == 2
        assert agg["threads"] == {"t1": 2, "t2": 1, "t3": 1}

    def test_micro_aggregation(self):
        items = [
            {"kind": "elins", "ts": 1.0, "ep_flags": ["pressure", "trust"]},
            {"kind": "elins", "ts": 2.0, "ep_flags": ["pressure"]},
            {"kind": "g_run", "ts": 3.0, "ep_flags": ["alignment"]},
        ]
        agg = dpe._aggregate_micro(items)
        assert agg["message_count"] == 3
        assert agg["ep_flags"] == {"pressure": 2, "trust": 1, "alignment": 1}
        # notable_events: kind→count labels sorted
        assert any("elins" in s for s in agg["notable_events"])
        assert any("g_run" in s for s in agg["notable_events"])

    def test_field_weather_turbulent_on_high(self):
        news = {"pressure_distribution": {"HIGH": 1}}
        email = {"high_importance": 0, "with_deadlines": 0}
        assert dpe._derive_field_weather(news, email) == "turbulent"

    def test_field_weather_mixed_on_medium(self):
        news = {"pressure_distribution": {"HIGH": 0, "MEDIUM": 1}}
        email = {"high_importance": 0, "with_deadlines": 0}
        assert dpe._derive_field_weather(news, email) == "mixed"

    def test_field_weather_stable_on_all_zero(self):
        news = {"pressure_distribution": {"HIGH": 0, "MEDIUM": 0, "LOW": 5}}
        email = {"high_importance": 0, "with_deadlines": 0}
        assert dpe._derive_field_weather(news, email) == "stable"

    def test_risk_zones_obligations(self):
        zones = dpe._derive_risk_zones(
            {"pressure_distribution": {"HIGH": 0}},
            {"with_deadlines": 1, "high_importance": 0, "threads": {}},
        )
        assert "obligations" in zones

    def test_risk_zones_external_pressure(self):
        zones = dpe._derive_risk_zones(
            {"pressure_distribution": {"HIGH": 3}},
            {"with_deadlines": 0, "high_importance": 0, "threads": {}},
        )
        assert "external_pressure" in zones

    def test_risk_zones_relationships(self):
        zones = dpe._derive_risk_zones(
            {"pressure_distribution": {"HIGH": 0}},
            {"with_deadlines": 0, "high_importance": 0,
             "threads": {"a": 1, "b": 1, "c": 1}},
        )
        assert "relationships" in zones

    def test_risk_zones_empty(self):
        zones = dpe._derive_risk_zones(
            {"pressure_distribution": {"HIGH": 0}},
            {"with_deadlines": 0, "high_importance": 0, "threads": {}},
        )
        assert zones == []


# ---------------------------------------------------------------------------
# build_daily_elins_envelope
# ---------------------------------------------------------------------------
class TestBuildEnvelope:
    def test_canonical_shape(self, fixed_dt, target_date):
        env = dpe.build_daily_elins_envelope(
            "alice", target_date, [], [], [],
            generated_at=fixed_dt,
        )
        assert env["type"]         == "daily_personal_elins"
        assert env["user"]         == "alice"
        assert env["date"]         == "2026-05-11"
        assert env["generated_at"] == fixed_dt
        assert "macro"   in env
        assert "meso"    in env
        assert "micro"   in env
        assert "summary" in env

    def test_macro_unknown_when_no_macro_context(self, fixed_dt, target_date):
        env = dpe.build_daily_elins_envelope(
            "alice", target_date, [], [], [],
            macro=None, generated_at=fixed_dt,
        )
        assert env["macro"]["field_weather"]   == "unknown"
        assert env["macro"]["dominant_themes"] == []

    def test_macro_uses_run_regions(self, fixed_dt, target_date):
        macro_run = {"run_id": "macro_x", "regions": ["US", "APAC"]}
        env = dpe.build_daily_elins_envelope(
            "alice", target_date,
            [_news_item(pressure="low")], [], [],
            macro=macro_run, generated_at=fixed_dt,
        )
        assert env["macro"]["dominant_themes"] == ["US", "APAC"]
        # field_weather computed from signals: low news, no emails → stable
        assert env["macro"]["field_weather"] == "stable"

    def test_meso_aggregates(self, fixed_dt, target_date):
        news = [
            _news_item(source="R", region="US", pressure="high"),
            _news_item(source="R", region="EU", pressure="medium"),
        ]
        emails = [
            _email_item(importance="HIGH", has_deadline=True,  thread_key="t1"),
        ]
        env = dpe.build_daily_elins_envelope(
            "alice", target_date, news, emails, [],
            generated_at=fixed_dt,
        )
        assert env["meso"]["news"]["count"] == 2
        assert env["meso"]["news"]["pressure_distribution"]["HIGH"] == 1
        assert env["meso"]["email"]["count"] == 1
        assert env["meso"]["email"]["high_importance"] == 1
        assert env["meso"]["email"]["with_deadlines"]  == 1

    def test_summary_headline_template(self, fixed_dt, target_date):
        env = dpe.build_daily_elins_envelope(
            "alice", target_date,
            [_news_item(pressure="high"), _news_item(pressure="low")],
            [_email_item(has_deadline=True)],
            [{"kind": "elins", "ts": 1.0}],
            generated_at=fixed_dt,
        )
        h = env["summary"]["headline"]
        assert "2 news items" in h
        assert "1 HIGH" in h
        assert "1 emails" in h
        assert "1 with deadlines" in h
        assert "1 micro events" in h

    def test_summary_focus_orders_obligations_first(self, fixed_dt, target_date):
        env = dpe.build_daily_elins_envelope(
            "alice", target_date,
            [],
            [_email_item(has_deadline=True), _email_item(importance="HIGH")],
            [],
            generated_at=fixed_dt,
        )
        focus = env["summary"]["focus"]
        # Deadlines come before high_importance per derivation order
        assert focus[0].startswith("deadlines:")
        assert focus[1].startswith("high_importance_email:")

    def test_determinism_same_inputs_identical_envelope(self, fixed_dt, target_date):
        news   = [_news_item(source="R", region="US", pressure="high")]
        emails = [_email_item(importance="HIGH", has_deadline=True, thread_key="t1")]
        micro  = [{"kind": "elins", "ts": 1.0, "ep_flags": ["pressure"]}]
        macro  = {"run_id": "r1", "regions": ["US"]}

        env1 = dpe.build_daily_elins_envelope(
            "alice", target_date, news, emails, micro,
            macro=macro, generated_at=fixed_dt,
        )
        env2 = dpe.build_daily_elins_envelope(
            "alice", target_date, news, emails, micro,
            macro=macro, generated_at=fixed_dt,
        )
        assert env1 == env2

    def test_partial_data_only_news(self, fixed_dt, target_date):
        env = dpe.build_daily_elins_envelope(
            "alice", target_date,
            [_news_item()], [], [],
            generated_at=fixed_dt,
        )
        assert env["meso"]["news"]["count"]  == 1
        assert env["meso"]["email"]["count"] == 0
        assert env["micro"]["message_count"] == 0

    def test_partial_data_only_email(self, fixed_dt, target_date):
        env = dpe.build_daily_elins_envelope(
            "alice", target_date,
            [], [_email_item()], [],
            generated_at=fixed_dt,
        )
        assert env["meso"]["news"]["count"]  == 0
        assert env["meso"]["email"]["count"] == 1
        assert env["micro"]["message_count"] == 0

    def test_partial_data_only_micro(self, fixed_dt, target_date):
        env = dpe.build_daily_elins_envelope(
            "alice", target_date,
            [], [], [{"kind": "elins", "ts": 1.0}],
            generated_at=fixed_dt,
        )
        assert env["meso"]["news"]["count"]  == 0
        assert env["meso"]["email"]["count"] == 0
        assert env["micro"]["message_count"] == 1


# ---------------------------------------------------------------------------
# write_to_ingestion_bus / write_to_library
# ---------------------------------------------------------------------------
class TestWriteToIngestionBus:
    def test_round_trip(self, fixed_dt, target_date):
        env = dpe.build_daily_elins_envelope(
            "alice", target_date, [_news_item()], [], [],
            generated_at=fixed_dt,
        )
        pid = dpe.write_to_ingestion_bus(env)
        assert pid.startswith("pkt_")
        back = ingestion_bus.get_packet(pid)
        assert back is not None
        assert back["type"] == "daily_personal_elins"
        assert back["user"] == "alice"


class TestWriteToLibrary:
    def test_creates_file_in_user_subdir(self, fixed_dt, target_date, _isolated_env):
        tmp = _isolated_env
        env = dpe.build_daily_elins_envelope(
            "alice", target_date, [], [], [],
            generated_at=fixed_dt,
        )
        path = dpe.write_to_library(env)
        p = Path(path)
        assert p.exists()
        assert p.name == "2026-05-11.json"
        assert p.parent.name == "alice"
        assert p.parent.parent == tmp / "daily"

    def test_overwrites_same_date(self, fixed_dt, target_date):
        env = dpe.build_daily_elins_envelope(
            "alice", target_date, [], [], [],
            generated_at=fixed_dt,
        )
        path1 = dpe.write_to_library(env)
        env["summary"]["headline"] = "MUTATED"
        path2 = dpe.write_to_library(env)
        assert path1 == path2
        loaded = json.loads(Path(path1).read_text(encoding="utf-8"))
        assert loaded["summary"]["headline"] == "MUTATED"

    def test_rejects_envelope_without_user(self):
        with pytest.raises(ValueError):
            dpe.write_to_library({"date": "2026-05-11"})

    def test_rejects_envelope_without_date(self):
        with pytest.raises(ValueError):
            dpe.write_to_library({"user": "alice"})

    def test_rejects_non_dict(self):
        with pytest.raises(ValueError):
            dpe.write_to_library("nope")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# run_daily_personal_elins — entrypoint
# ---------------------------------------------------------------------------
class TestRunDailyPersonalElins:
    def test_empty_day_short_circuits(self, _isolated_env, monkeypatch, target_date):
        # No bus packets, no macro, fake operator_state with empty history.
        import operator_state
        monkeypatch.setattr(
            operator_state, "get_operator_state",
            lambda uid: {"elins_history": [], "g_history": []},
        )
        env = dpe.run_daily_personal_elins("alice", target_date)
        assert env["type"]  == "daily_personal_elins"
        assert env["user"]  == "alice"
        assert env["date"]  == "2026-05-11"
        assert env["empty"] is True
        # No writes
        assert "_bus_packet_id" not in env
        assert "_library_path"  not in env
        assert ingestion_bus.list_packets() == []

    def test_end_to_end_with_news_and_emails(self, _isolated_env, monkeypatch, target_date):
        # Seed bus with news + email envelopes inside the date window.
        _push_news_envelope(
            user="alice",
            generated_at="2026-05-11T08:00:00+00:00",
            items=[_news_item(pressure="high", region="US")],
        )
        _push_email_envelope(
            user="alice",
            generated_at="2026-05-11T09:00:00+00:00",
            items=[_email_item(importance="HIGH", has_deadline=True)],
        )
        # No micro signals.
        import operator_state
        monkeypatch.setattr(
            operator_state, "get_operator_state",
            lambda uid: {"elins_history": [], "g_history": []},
        )

        env = dpe.run_daily_personal_elins("alice", target_date)

        # Envelope shape
        assert env["type"]  == "daily_personal_elins"
        assert env["user"]  == "alice"
        assert env["date"]  == "2026-05-11"
        assert "empty" not in env or env.get("empty") is not True

        # Meso aggregates landed
        assert env["meso"]["news"]["count"]  == 1
        assert env["meso"]["email"]["count"] == 1
        assert env["meso"]["news"]["pressure_distribution"]["HIGH"] == 1
        assert env["meso"]["email"]["with_deadlines"] == 1

        # No macro run was seeded for this test → spec says field_weather
        # stays "unknown" and dominant_themes is empty even when signals
        # are present. Risk zones, however, are always derived.
        assert env["macro"]["field_weather"]   == "unknown"
        assert env["macro"]["dominant_themes"] == []
        assert "obligations"       in env["macro"]["risk_zones"]
        assert "external_pressure" in env["macro"]["risk_zones"]

        # Both writes happened
        assert isinstance(env["_bus_packet_id"], str)
        assert env["_bus_packet_id"].startswith("pkt_")
        assert isinstance(env["_library_path"], str)
        assert Path(env["_library_path"]).exists()

        # Bus has the daily envelope
        back = ingestion_bus.get_packet(env["_bus_packet_id"])
        assert back is not None
        assert back["type"] == "daily_personal_elins"

    def test_default_date_is_today_utc(self, _isolated_env, monkeypatch):
        """No date passed → today UTC. With no signals we get the empty
        short-circuit, but the date field still confirms today UTC."""
        import operator_state
        monkeypatch.setattr(
            operator_state, "get_operator_state",
            lambda uid: {"elins_history": [], "g_history": []},
        )
        env = dpe.run_daily_personal_elins("alice")
        assert env["date"] == datetime.now(timezone.utc).date().isoformat()

    def test_date_window_excludes_yesterdays_packets(self, _isolated_env, monkeypatch, target_date):
        """Packets from yesterday should not appear in today's daily."""
        _push_news_envelope(
            user="alice",
            generated_at="2026-05-10T23:00:00+00:00",  # yesterday
            items=[_news_item(source="yesterday")],
        )
        import operator_state
        monkeypatch.setattr(
            operator_state, "get_operator_state",
            lambda uid: {"elins_history": [], "g_history": []},
        )
        env = dpe.run_daily_personal_elins("alice", target_date)
        # No today-news → empty (since no other signals)
        assert env.get("empty") is True

    def test_includes_micro_signals(self, _isolated_env, monkeypatch, target_date):
        start, _ = dpe._day_window_utc(target_date)
        ts = (start + timedelta(hours=10)).timestamp()
        fake_state = {
            "elins_history": [
                {"ts": ts, "topic": "x", "ep_flags": ["pressure", "trust"]},
            ],
            "g_history": [],
        }
        import operator_state
        monkeypatch.setattr(operator_state, "get_operator_state", lambda uid: fake_state)

        env = dpe.run_daily_personal_elins("alice", target_date)
        assert env["micro"]["message_count"] == 1
        assert env["micro"]["ep_flags"].get("pressure") == 1
        assert env["micro"]["ep_flags"].get("trust") == 1
        assert "_bus_packet_id" in env

    def test_macro_run_included_when_available(self, _isolated_env, monkeypatch, target_date):
        """A macro run within the day window populates dominant_themes."""
        start, _ = dpe._day_window_utc(target_date)
        ts = (start + timedelta(hours=5)).timestamp()
        fake_macro_runs = [{
            "run_id":  "macro_today",
            "ts":      ts,
            "regions": ["US", "EU", "APAC"],
        }]
        from ELINS import elins_project
        monkeypatch.setattr(
            elins_project, "list_macro_runs",
            lambda *, limit=20: fake_macro_runs,
        )
        # Add at least one signal so we're not empty.
        _push_news_envelope(
            user="alice",
            generated_at="2026-05-11T08:00:00+00:00",
            items=[_news_item()],
        )
        import operator_state
        monkeypatch.setattr(
            operator_state, "get_operator_state",
            lambda uid: {"elins_history": [], "g_history": []},
        )

        env = dpe.run_daily_personal_elins("alice", target_date)
        assert env["macro"]["dominant_themes"] == ["US", "EU", "APAC"]


# ---------------------------------------------------------------------------
# End-to-end via Unit 1 + Unit 2 (real producers writing to the bus)
# ---------------------------------------------------------------------------
class TestEndToEndAcrossModules:
    def test_real_email_run_lands_in_daily(self, _isolated_env, monkeypatch, target_date):
        """A real email_ep_dash run pushes to the bus; the composer
        finds it and folds it into the daily envelope."""
        # We need the email envelope's generated_at to be inside our
        # target_date window. The real run_email_ep_dash uses datetime.now,
        # which won't equal target_date except on actual 2026-05-11.
        # Solution: monkeypatch datetime in email_ep_dash to a fixed
        # time inside the target_date window.
        fixed = datetime(2026, 5, 11, 9, 0, tzinfo=timezone.utc)

        class FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return fixed.replace(tzinfo=None)
                return fixed.astimezone(tz)

        monkeypatch.setattr(ed, "datetime", FixedDatetime)

        blob = (
            "From: alice@x.com\n"
            "To: bob@x.com\n"
            "Subject: URGENT: review needed\n"
            "Date: Mon, 11 May 2026 09:00:00 +0000\n"
            "\n"
            "Can you review this by Friday? I will follow up."
        )
        email_env = ed.run_email_ep_dash(blob, "alice")
        assert email_env["_bus_packet_id"] is not None

        # Restore datetime in email_ep_dash before composer runs (its own
        # writes use now() too; we want them inside the window).
        monkeypatch.setattr(ed, "datetime", datetime)

        # Stub operator_state to keep the run hermetic.
        import operator_state
        monkeypatch.setattr(
            operator_state, "get_operator_state",
            lambda uid: {"elins_history": [], "g_history": []},
        )

        daily = dpe.run_daily_personal_elins("alice", target_date)
        assert daily["meso"]["email"]["count"]           == 1
        assert daily["meso"]["email"]["high_importance"] == 1
        assert daily["meso"]["email"]["with_deadlines"]  == 1
