"""
Tests for personal_news_basin.py (Phase 2 Unit 1).

All side-effecting paths (perplexity HTTP, filesystem, ingestion bus)
are either monkey-patched or scoped to ``tmp_path`` so the suite runs
hermetically with no network and no shared state between tests.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ELINS import ingestion_bus
import personal_news_basin as pnb


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolated_paths_and_bus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point every test at its own tmp sources file + library dir and
    reset the ingestion bus packet log."""
    sources_file = tmp_path / "news_basin_sources.json"
    library_dir = tmp_path / "library"
    monkeypatch.setenv("CLARITYOS_NEWS_BASIN_SOURCES", str(sources_file))
    monkeypatch.setenv("CLARITYOS_NEWS_BASIN_DIR",     str(library_dir))
    # Make sure EP-classifier env-gate is OFF for the deterministic path.
    monkeypatch.delenv("CLARITYOS_NEWS_BASIN_EP", raising=False)
    ingestion_bus._reset_memory_for_tests()
    yield sources_file, library_dir
    ingestion_bus._reset_memory_for_tests()


def _write_sources(p: Path, sources: list) -> None:
    p.write_text(json.dumps({"sources": sources}), encoding="utf-8")


def _fake_perplexity_response(headlines: list[dict]) -> dict:
    """Build a fake chat-completion response carrying a JSON 'headlines' list."""
    payload = json.dumps({"headlines": headlines})
    return {
        "choices": [
            {"message": {"role": "assistant", "content": payload}},
        ],
    }


# ---------------------------------------------------------------------------
# load_sources
# ---------------------------------------------------------------------------
class TestLoadSources:
    def test_reads_normal_list(self, _isolated_paths_and_bus):
        sf, _ = _isolated_paths_and_bus
        _write_sources(sf, ["Reuters", "AP News", "Bloomberg"])
        assert pnb.load_sources() == ["Reuters", "AP News", "Bloomberg"]

    def test_caps_at_max(self, _isolated_paths_and_bus):
        sf, _ = _isolated_paths_and_bus
        _write_sources(sf, [f"Src{i}" for i in range(20)])
        result = pnb.load_sources()
        assert len(result) == pnb.MAX_USER_SOURCES  # 13
        assert result[0] == "Src0"
        assert result[12] == "Src12"

    def test_dedupes_case_insensitive(self, _isolated_paths_and_bus):
        sf, _ = _isolated_paths_and_bus
        _write_sources(sf, ["Reuters", "reuters", "REUTERS", "AP News"])
        assert pnb.load_sources() == ["Reuters", "AP News"]

    def test_strips_whitespace(self, _isolated_paths_and_bus):
        sf, _ = _isolated_paths_and_bus
        _write_sources(sf, ["  Reuters  ", "\tAP News\n"])
        assert pnb.load_sources() == ["Reuters", "AP News"]

    def test_skips_non_strings_and_empty(self, _isolated_paths_and_bus):
        sf, _ = _isolated_paths_and_bus
        _write_sources(sf, ["Reuters", "", None, 42, "   ", "AP"])
        assert pnb.load_sources() == ["Reuters", "AP"]

    def test_missing_file_returns_empty(self, _isolated_paths_and_bus):
        # tmp file deliberately not created
        assert pnb.load_sources() == []

    def test_broken_json_returns_empty(self, _isolated_paths_and_bus):
        sf, _ = _isolated_paths_and_bus
        sf.write_text("not json{{", encoding="utf-8")
        assert pnb.load_sources() == []

    def test_missing_sources_key_returns_empty(self, _isolated_paths_and_bus):
        sf, _ = _isolated_paths_and_bus
        sf.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
        assert pnb.load_sources() == []

    def test_non_dict_root_returns_empty(self, _isolated_paths_and_bus):
        sf, _ = _isolated_paths_and_bus
        sf.write_text(json.dumps(["Reuters"]), encoding="utf-8")
        assert pnb.load_sources() == []


# ---------------------------------------------------------------------------
# Classifiers — pure functions, no fixtures needed beyond the autouse env
# ---------------------------------------------------------------------------
class TestClassifyRegion:
    def test_us(self):
        assert pnb._classify_region("Federal Reserve raises rates again") == "US"
        assert pnb._classify_region("White House announces tariffs") == "US"

    def test_eu(self):
        assert pnb._classify_region("ECB warns Germany on inflation") == "EU"
        assert pnb._classify_region("Brussels and London agree on trade deal") == "EU"

    def test_apac(self):
        assert pnb._classify_region("China and Japan signal tension") == "APAC"
        assert pnb._classify_region("Tokyo markets rally on Beijing news") == "APAC"

    def test_mea(self):
        assert pnb._classify_region("Israel and Iran exchange warnings") == "MEA"

    def test_markets(self):
        assert pnb._classify_region("Bitcoin yields surge as bond market falls") == "Markets"

    def test_tech(self):
        assert pnb._classify_region("OpenAI announces new chip partnership") == "Tech"

    def test_default_us_on_unmatchable_text(self):
        assert pnb._classify_region("Generic uncategorisable noise") == "US"

    def test_empty_text_default(self):
        assert pnb._classify_region("") == "US"
        assert pnb._classify_region(None) == "US"  # type: ignore[arg-type]


class TestClassifyPressureLexical:
    def test_high(self):
        assert pnb._classify_pressure_lexical("Market crash sparks panic") == "high"
        assert pnb._classify_pressure_lexical("War declared in region") == "high"

    def test_medium(self):
        assert pnb._classify_pressure_lexical("Rising tension over trade") == "medium"
        assert pnb._classify_pressure_lexical("Concern about decline in earnings") == "medium"

    def test_low(self):
        assert pnb._classify_pressure_lexical("New product launches today") == "low"

    def test_empty(self):
        assert pnb._classify_pressure_lexical("") == "low"


class TestNarrativeTemperature:
    def test_zero_at_neutral(self):
        assert pnb._compute_narrative_temperature(0.0, "low") == 0.0

    def test_one_at_extreme(self):
        assert pnb._compute_narrative_temperature(1.0, "high") == 1.0
        assert pnb._compute_narrative_temperature(-1.0, "high") == 1.0  # |sent|

    def test_blend(self):
        # |0.5| * 0.5 + 0.5 (medium) * 0.5 = 0.25 + 0.25 = 0.5
        assert pnb._compute_narrative_temperature(0.5, "medium") == 0.5

    def test_clamps_sentiment(self):
        # |2.0| clamped to 1.0 → 0.5*1.0 + 0.5*0.0 = 0.5
        assert pnb._compute_narrative_temperature(2.0, "low") == 0.5


# ---------------------------------------------------------------------------
# normalize_headline
# ---------------------------------------------------------------------------
class TestNormalizeHeadline:
    def test_canonical_keys(self):
        raw = {
            "title":     "China unveils new semiconductor policy",
            "timestamp": "2026-05-11T12:00:00Z",
            "category":  "tech",
            "sentiment": 0.2,
        }
        out = pnb.normalize_headline(raw, "Nikkei Asia", "alice")
        assert set(out.keys()) == set(pnb.PACKET_KEYS)
        assert out["source"]    == "Nikkei Asia"
        assert out["headline"]  == "China unveils new semiconductor policy"
        assert out["timestamp"] == "2026-05-11T12:00:00Z"
        assert out["category"]  == "tech"
        assert out["sentiment"] == 0.2
        # Derived fields
        assert out["pressure"] in ("low", "medium", "high")
        assert 0.0 <= out["narrative_temperature"] <= 1.0
        # "China … semiconductor" — APAC keyword "china" beats Tech "semiconductor"
        # by score; the tie-breaker is alphabetical (APAC < Tech). Verify the
        # function picks something stable, not the specific bucket.
        assert out["region"] in ("APAC", "Tech")
        assert isinstance(out["retrieved_at"], str)
        assert "T" in out["retrieved_at"]  # ISO 8601

    def test_accepts_headline_alias(self):
        out = pnb.normalize_headline({"headline": "Fed warns"}, "AP News")
        assert out["headline"] == "Fed warns"

    def test_missing_fields_get_defaults(self):
        out = pnb.normalize_headline({}, "AP News")
        assert out["headline"]  == ""
        assert out["timestamp"] == "unknown"
        assert out["category"]  == "general"
        assert out["sentiment"] == 0.0
        assert out["pressure"]  == "low"  # empty text → low
        assert out["region"]    == "US"   # empty text → default
        assert out["narrative_temperature"] == 0.0

    def test_sentiment_clamping(self):
        assert pnb.normalize_headline({"title": "x", "sentiment":  5.0}, "S")["sentiment"] ==  1.0
        assert pnb.normalize_headline({"title": "x", "sentiment": -5.0}, "S")["sentiment"] == -1.0
        assert pnb.normalize_headline({"title": "x", "sentiment": "garbage"}, "S")["sentiment"] == 0.0

    def test_pressure_detected_from_title(self):
        out = pnb.normalize_headline(
            {"title": "Banking crisis triggers market crash"},
            "Reuters",
        )
        assert out["pressure"] == "high"
        assert out["region"]   == "Markets"

    def test_non_dict_raw_tolerated(self):
        out = pnb.normalize_headline(None, "src")  # type: ignore[arg-type]
        assert set(out.keys()) == set(pnb.PACKET_KEYS)
        assert out["source"]   == "src"
        assert out["headline"] == ""


# ---------------------------------------------------------------------------
# build_envelope
# ---------------------------------------------------------------------------
class TestBuildEnvelope:
    def test_shape(self):
        items = [{"a": 1}, {"a": 2}]
        env = pnb.build_envelope(items, "alice")
        assert env["type"] == "news_basin"
        assert env["user"] == "alice"
        assert env["items"] == items
        assert isinstance(env["generated_at"], str)
        assert "T" in env["generated_at"]

    def test_empty_items_ok(self):
        env = pnb.build_envelope([])
        assert env["items"] == []
        assert env["user"]  == "system"

    def test_defensive_against_non_list_items(self):
        env = pnb.build_envelope("not a list")  # type: ignore[arg-type]
        assert env["items"] == []


# ---------------------------------------------------------------------------
# write_to_library
# ---------------------------------------------------------------------------
class TestWriteToLibrary:
    def test_creates_file_with_envelope(self, _isolated_paths_and_bus):
        _, lib_dir = _isolated_paths_and_bus
        env = {
            "type":         "news_basin",
            "user":         "alice",
            "generated_at": "2026-05-11T08:30:00+00:00",
            "items":        [{"a": 1}],
        }
        path = pnb.write_to_library(env)
        p = Path(path)
        assert p.exists()
        assert p.parent == lib_dir
        # Filename uses YYYY-MM-DD_HHMM
        assert p.name == "2026-05-11_0830.json"
        # Content round-trips through JSON
        roundtrip = json.loads(p.read_text(encoding="utf-8"))
        assert roundtrip == env

    def test_falls_back_to_now_when_generated_at_missing(self, _isolated_paths_and_bus):
        env = {"type": "news_basin", "user": "alice", "items": []}
        path = pnb.write_to_library(env)
        # Filename should still match YYYY-MM-DD_HHMM pattern.
        assert Path(path).name.endswith(".json")
        assert len(Path(path).stem) == len("2026-05-11_0830")

    def test_falls_back_to_now_when_generated_at_invalid(self, _isolated_paths_and_bus):
        env = {"type": "news_basin", "generated_at": "not-a-date", "items": []}
        path = pnb.write_to_library(env)
        assert Path(path).exists()

    def test_creates_parent_dirs(self, _isolated_paths_and_bus, monkeypatch, tmp_path):
        deep_dir = tmp_path / "a" / "b" / "c" / "news"
        monkeypatch.setenv("CLARITYOS_NEWS_BASIN_DIR", str(deep_dir))
        env = {"type": "news_basin", "items": []}
        path = pnb.write_to_library(env)
        assert Path(path).exists()
        assert deep_dir.exists()


# ---------------------------------------------------------------------------
# write_to_ingestion_bus
# ---------------------------------------------------------------------------
class TestWriteToIngestionBus:
    def test_round_trip(self):
        env = pnb.build_envelope([{"headline": "x"}], "alice")
        pid = pnb.write_to_ingestion_bus(env)
        assert pid.startswith("pkt_")
        fetched = ingestion_bus.get_packet(pid)
        assert fetched is not None
        assert fetched["type"] == "news_basin"
        assert fetched["user"] == "alice"
        assert fetched["items"] == [{"headline": "x"}]

    def test_list_filters_by_type(self):
        env = pnb.build_envelope([], "alice")
        pnb.write_to_ingestion_bus(env)
        # Also write a non-news packet directly
        ingestion_bus.write_packet({"type": "other", "generated_at": "x", "items": []})

        news = ingestion_bus.list_packets(type_filter="news_basin")
        other = ingestion_bus.list_packets(type_filter="other")
        all_ = ingestion_bus.list_packets()
        assert len(news) == 1
        assert len(other) == 1
        assert len(all_) == 2

    def test_rejects_invalid_envelope(self):
        with pytest.raises(ValueError):
            pnb.write_to_ingestion_bus({"items": []})  # missing 'type'
        with pytest.raises(ValueError):
            pnb.write_to_ingestion_bus("not a dict")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# fetch_headlines_for_source — degraded paths
# ---------------------------------------------------------------------------
class TestFetchHeadlines:
    def test_missing_api_key_returns_empty(self, monkeypatch):
        # No API key set → _call_perplexity raises RuntimeError → empty.
        monkeypatch.delenv("CLARITYOS_PERPLEXITY_API_KEY", raising=False)
        assert pnb.fetch_headlines_for_source("Reuters") == []

    def test_empty_source_returns_empty(self):
        assert pnb.fetch_headlines_for_source("") == []
        assert pnb.fetch_headlines_for_source(None) == []  # type: ignore[arg-type]

    def test_malformed_oracle_response(self, monkeypatch):
        import perplexity_oracle
        monkeypatch.setattr(
            perplexity_oracle, "_call_perplexity",
            lambda q: {"choices": [{"message": {"content": "totally not json"}}]},
        )
        assert pnb.fetch_headlines_for_source("Reuters") == []

    def test_response_without_headlines_key(self, monkeypatch):
        import perplexity_oracle
        monkeypatch.setattr(
            perplexity_oracle, "_call_perplexity",
            lambda q: _fake_perplexity_response_no_headlines(),
        )
        assert pnb.fetch_headlines_for_source("Reuters") == []

    def test_canned_headlines_pass_through(self, monkeypatch):
        import perplexity_oracle
        canned = [
            {"title": "A", "sentiment": 0.0, "category": "x", "timestamp": "2026-05-11"},
            {"title": "B", "sentiment": 0.5, "category": "y", "timestamp": "2026-05-11"},
        ]
        monkeypatch.setattr(
            perplexity_oracle, "_call_perplexity",
            lambda q: _fake_perplexity_response(canned),
        )
        result = pnb.fetch_headlines_for_source("Reuters")
        assert result == canned

    def test_caps_at_max_headlines(self, monkeypatch):
        import perplexity_oracle
        canned = [{"title": f"H{i}"} for i in range(10)]
        monkeypatch.setattr(
            perplexity_oracle, "_call_perplexity",
            lambda q: _fake_perplexity_response(canned),
        )
        result = pnb.fetch_headlines_for_source("Reuters")
        assert len(result) == pnb.MAX_HEADLINES_PER_SOURCE  # 5


def _fake_perplexity_response_no_headlines() -> dict:
    payload = json.dumps({"foo": "bar"})
    return {"choices": [{"message": {"content": payload}}]}


# ---------------------------------------------------------------------------
# JSON-loose parsing
# ---------------------------------------------------------------------------
class TestParseJsonLoose:
    def test_direct_parse(self):
        assert pnb._parse_json_loose('{"a":1}') == {"a": 1}

    def test_with_code_fence(self):
        assert pnb._parse_json_loose('```json\n{"a":1}\n```') == {"a": 1}

    def test_with_prose_around_json(self):
        assert pnb._parse_json_loose('Here you go: {"a":1} done.') == {"a": 1}

    def test_returns_none_on_garbage(self):
        assert pnb._parse_json_loose("nope") is None
        assert pnb._parse_json_loose("") is None

    def test_returns_none_on_non_object_json(self):
        # Top-level list — not a dict.
        assert pnb._parse_json_loose('[1,2,3]') is None


# ---------------------------------------------------------------------------
# run_news_basin — end-to-end
# ---------------------------------------------------------------------------
class TestRunNewsBasin:
    def test_empty_sources_short_circuits_no_writes(self, _isolated_paths_and_bus):
        sf, lib_dir = _isolated_paths_and_bus
        # No sources file → empty envelope, no bus writes, no library writes
        env = pnb.run_news_basin("alice")
        assert env["items"] == []
        assert env["user"]  == "alice"
        assert env["type"]  == "news_basin"
        # No bus writes
        assert ingestion_bus.list_packets() == []
        # No library files
        if lib_dir.exists():
            assert list(lib_dir.iterdir()) == []
        # No bus/library meta keys appended (because no fetch happened)
        assert "_bus_packet_id" not in env
        assert "_library_path" not in env

    def test_end_to_end_with_canned_oracle(self, _isolated_paths_and_bus, monkeypatch):
        sf, lib_dir = _isolated_paths_and_bus
        _write_sources(sf, ["Reuters", "AP News"])

        canned = [
            {"title": "Fed warns of inflation",  "sentiment": -0.3, "category": "markets", "timestamp": "2026-05-11"},
            {"title": "Apple unveils new chip",  "sentiment":  0.4, "category": "tech",    "timestamp": "2026-05-11"},
        ]
        import perplexity_oracle
        monkeypatch.setattr(
            perplexity_oracle, "_call_perplexity",
            lambda q: _fake_perplexity_response(canned),
        )

        env = pnb.run_news_basin("alice")

        # Envelope shape
        assert env["type"] == "news_basin"
        assert env["user"] == "alice"
        # 2 sources × 2 canned headlines = 4 items
        assert len(env["items"]) == 4
        # Bus + library writes both happened
        assert isinstance(env["_bus_packet_id"], str)
        assert env["_bus_packet_id"].startswith("pkt_")
        assert isinstance(env["_library_path"], str)
        assert Path(env["_library_path"]).exists()
        # Bus has the packet
        assert ingestion_bus.get_packet(env["_bus_packet_id"]) is not None
        # Each item has full canonical key set
        for item in env["items"]:
            assert set(item.keys()) == set(pnb.PACKET_KEYS)

    def test_per_source_failure_doesnt_kill_batch(self, _isolated_paths_and_bus, monkeypatch):
        """If one source raises, other sources still produce items."""
        sf, _ = _isolated_paths_and_bus
        _write_sources(sf, ["GoodSource", "BadSource"])

        import perplexity_oracle

        def picky_oracle(query: str) -> dict:
            if "BadSource" in query:
                raise RuntimeError("simulated upstream failure")
            return _fake_perplexity_response(
                [{"title": "Working headline", "sentiment": 0.1}],
            )

        monkeypatch.setattr(perplexity_oracle, "_call_perplexity", picky_oracle)
        env = pnb.run_news_basin("bob")
        # Only GoodSource produced items
        assert len(env["items"]) == 1
        assert env["items"][0]["source"] == "GoodSource"
