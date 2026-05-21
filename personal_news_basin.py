"""
personal_news_basin.py — PERSONAL NEWS BASIN EP (Phase 2 Unit 1).

User-defined news intelligence archive. Collects up to 5 headlines from
each of up to 13 configured sources via perplexity_oracle, normalises
them into a canonical packet, writes the envelope to the ingestion
bus, and persists a JSON archive copy to the library directory.

Cadence is 2×/day — driven externally by ``intelligence_scheduler``
(Phase 2 Unit 4). This module exposes a stateless ``run_news_basin``
entrypoint; the scheduler calls it on each cadence tick.

DESIGN COMMITMENTS:
    * News-only. No personal email or thread signals (per spec § 3.3).
    * Distinct from the 6 fixed regional basins (v35 regional_elins)
      — those are global; this is user-curated.
    * Deterministic by default. EP-classification (LLM-backed pressure)
      is gated behind ``CLARITYOS_NEWS_BASIN_EP=1``; the default lexical
      classifier is fast, free, and reproducible — important for tests
      and for keeping the 2×/day cadence cheap.
    * Graceful degradation. Missing API key, network failure, JSON
      parse failure all return empty headline lists; the envelope is
      still written (operator sees the failure mode as empty items
      rather than a crash).

CONFIG:
    Source list:  config/news_basin_sources.json
        {"sources": ["Reuters", "AP News", ...]}
        Override path with CLARITYOS_NEWS_BASIN_SOURCES.

    Archive dir:  ClarityOS_Library/news_basin
        Files named YYYY-MM-DD_HHMM.json
        Override with CLARITYOS_NEWS_BASIN_DIR.

PUBLIC API (per THREE_PRODUCT_SUITE_PLAN.md § 7 Unit 1 spec):
    MAX_USER_SOURCES                  = 13
    MAX_HEADLINES_PER_SOURCE          = 5
    load_sources()                    -> list[str]
    fetch_headlines_for_source(src)   -> list[dict]
    normalize_headline(raw, src, uid) -> dict
    build_envelope(items, user_id)    -> dict
    write_to_ingestion_bus(envelope)  -> str          # packet_id
    write_to_library(envelope)        -> str          # file path
    run_news_basin(user_id='system')  -> dict         # entrypoint
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("clarityos.personal_news_basin")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Spec cap from THREE_PRODUCT_SUITE_PLAN.md § 3.3.
MAX_USER_SOURCES: int = 13

# Per the perplexity prompt — we ask for 5 headlines per source.
MAX_HEADLINES_PER_SOURCE: int = 5

# Filesystem defaults — both env-var overridable.
DEFAULT_SOURCES_CONFIG_PATH: str = "config/news_basin_sources.json"
DEFAULT_LIBRARY_DIR:         str = "ClarityOS_Library/news_basin"

# Canonical packet key set the normaliser produces. Documented for
# downstream consumers (DAILY PERSONAL ELINS, surface views).
PACKET_KEYS: tuple = (
    "source",
    "headline",
    "timestamp",
    "category",
    "sentiment",
    "pressure",
    "narrative_temperature",
    "region",
    "retrieved_at",
)

# Envelope type tag used by the ingestion bus + downstream consumers.
ENVELOPE_TYPE: str = "news_basin"


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
def _resolve_sources_path() -> Path:
    """Resolve the news-basin sources config path.

    Honors ``CLARITYOS_NEWS_BASIN_SOURCES`` env var; otherwise falls
    back to ``DEFAULT_SOURCES_CONFIG_PATH`` relative to the current
    working directory.
    """
    override = (os.environ.get("CLARITYOS_NEWS_BASIN_SOURCES") or "").strip()
    return Path(override) if override else Path(DEFAULT_SOURCES_CONFIG_PATH)


def _resolve_library_dir() -> Path:
    """Resolve the news-basin archive directory.

    Honors ``CLARITYOS_NEWS_BASIN_DIR``; otherwise falls back to
    ``DEFAULT_LIBRARY_DIR`` relative to the current working directory.
    Operators on a workstation typically set this to the absolute path
    of their personal corpus folder (e.g.,
    ``C:\\Users\\chris\\ClarityOS_Library\\news_basin``).
    """
    override = (os.environ.get("CLARITYOS_NEWS_BASIN_DIR") or "").strip()
    return Path(override) if override else Path(DEFAULT_LIBRARY_DIR)


# ---------------------------------------------------------------------------
# 1. load_sources
# ---------------------------------------------------------------------------
def load_sources() -> list[str]:
    """Read the configured source list from disk.

    Returns up to ``MAX_USER_SOURCES`` entries, deduped (case-insensitive)
    and stripped. Missing file, broken JSON, or non-list ``sources``
    all return ``[]`` (the caller short-circuits on empty).
    """
    p = _resolve_sources_path()
    if not p.exists():
        logger.info("personal_news_basin: sources file missing at %s", p)
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("personal_news_basin: bad sources file at %s: %s", p, e)
        return []

    raw = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []

    cleaned: list[str] = []
    seen: set[str] = set()
    for s in raw:
        if not isinstance(s, str):
            continue
        s2 = s.strip()
        if not s2:
            continue
        key = s2.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(s2)
        if len(cleaned) >= MAX_USER_SOURCES:
            break
    return cleaned


# ---------------------------------------------------------------------------
# 2. fetch_headlines_for_source
# ---------------------------------------------------------------------------
def _build_headlines_prompt(source: str) -> str:
    """The deterministic prompt we send to perplexity for one source."""
    return (
        f"Return only a single JSON object with a 'headlines' key whose "
        f"value is a list of the top {MAX_HEADLINES_PER_SOURCE} current "
        f"headlines from {source}. Each headline object must have these "
        f"keys: title (string), timestamp (ISO 8601 string or 'unknown'), "
        f"category (short string like 'markets' / 'tech' / 'geopolitics'), "
        f"sentiment (float -1.0 to 1.0 where negative is bad-news). "
        f"No commentary outside the JSON."
    )


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_BRACE_RE = re.compile(r"\{[\s\S]*\}")


def _parse_json_loose(content: str) -> Optional[dict]:
    """Defensive JSON extractor for model output.

    Tries direct parse → code-fence content → first ``{...}`` block.
    Returns None when no dict can be recovered.
    """
    if not isinstance(content, str) or not content.strip():
        return None

    # 1. Direct parse.
    try:
        v = json.loads(content.strip())
        return v if isinstance(v, dict) else None
    except json.JSONDecodeError:
        pass

    # 2. Code fence (```json ... ```).
    m = _FENCE_RE.search(content)
    if m:
        try:
            v = json.loads(m.group(1))
            if isinstance(v, dict):
                return v
        except json.JSONDecodeError:
            pass

    # 3. Greedy brace extraction.
    m = _BRACE_RE.search(content)
    if m:
        try:
            v = json.loads(m.group(0))
            if isinstance(v, dict):
                return v
        except json.JSONDecodeError:
            pass

    return None


def _extract_message_content(raw_response: dict) -> str:
    """Pull ``choices[0].message.content`` out of a chat-completion."""
    if not isinstance(raw_response, dict):
        return ""
    choices = raw_response.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    return content if isinstance(content, str) else ""


def fetch_headlines_for_source(source: str) -> list[dict]:
    """Fetch raw headlines for one source via perplexity_oracle.

    Returns an empty list on missing API key, network failure, JSON
    parse failure, or malformed response. Never raises — callers chain
    over sources expecting per-source degradation.
    """
    if not isinstance(source, str) or not source.strip():
        return []

    # Lazy import — perplexity_oracle pulls in stdlib HTTP but the
    # module is also a sensible mock target in tests.
    try:
        import perplexity_oracle
    except ImportError as e:
        logger.warning("personal_news_basin: perplexity_oracle unavailable: %s", e)
        return []

    prompt = _build_headlines_prompt(source.strip())
    try:
        raw = perplexity_oracle._call_perplexity(prompt)
    except RuntimeError as e:
        # Missing API key, HTTP failure, JSON failure → soft fail.
        logger.info("personal_news_basin: perplexity unavailable for %s: %s",
                    source, e)
        return []
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning("personal_news_basin: perplexity exception for %s: %s",
                       source, e)
        return []

    content = _extract_message_content(raw)
    parsed = _parse_json_loose(content)
    if parsed is None:
        return []

    headlines = parsed.get("headlines")
    if not isinstance(headlines, list):
        return []

    return [h for h in headlines if isinstance(h, dict)][:MAX_HEADLINES_PER_SOURCE]


# ---------------------------------------------------------------------------
# 3. normalize_headline
# ---------------------------------------------------------------------------

# Deterministic lexical region classifier. Six buckets match
# regional_elins.REGION_CODES exactly so downstream consumers can
# join with the regional basin layer without translation.
_REGION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "US":      ("usa", "united states", "america", "washington",
                "biden", "trump", "federal reserve", "wall street",
                "nasdaq", "white house"),
    "EU":      ("europe", "european union", " eu ", "brussels", "germany",
                "france", "italy", "spain", "uk ", "britain", "london",
                "ecb"),
    "MEA":     ("middle east", "israel", "palestine", "gaza", "iran",
                "saudi", "uae", "africa", "egypt", "nigeria", "turkey"),
    "APAC":    ("china", "japan", "korea", "india", "asia", "pacific",
                "taiwan", "vietnam", "indonesia", "singapore",
                "tokyo", "beijing", "seoul"),
    "Markets": ("market", "stock", "bond", "yield", "earnings",
                "ipo", "ftse", "dow", "s&p", "currency", "bitcoin",
                "crypto", "commodity", "oil price"),
    "Tech":    ("openai", "anthropic", "google", "apple", "microsoft",
                "nvidia", " tech ", "startup", "silicon valley", "chip",
                "semiconductor", " ai ", "llm"),
}


def _classify_region(text: str) -> str:
    """Lexical region classifier.

    Returns the region with the most keyword hits; ties broken by
    alphabetical order. Falls back to 'US' when no keywords match
    (matches the spec's pragmatic default for ungeographed headlines).
    """
    if not isinstance(text, str) or not text:
        return "US"
    low = " " + text.lower() + " "
    scores: dict[str, int] = {}
    for region, keywords in _REGION_KEYWORDS.items():
        scores[region] = sum(1 for kw in keywords if kw in low)
    best_region, best_score = max(
        scores.items(), key=lambda x: (x[1], -ord(x[0][0])),
    )
    return best_region if best_score > 0 else "US"


# Deterministic pressure markers. Operator can flip to LLM-backed by
# setting CLARITYOS_NEWS_BASIN_EP=1 (see _classify_pressure).
_PRESSURE_HIGH: tuple = (
    "crisis", "collapse", "war", "panic", "crash",
    "default", "emergency", "shock", "meltdown", "bombing",
)
_PRESSURE_MEDIUM: tuple = (
    "tension", "risk", "warning", "concern", "pressure",
    "uncertainty", "decline", "downturn", "fall", "drop",
    "threat", "dispute",
)


def _classify_pressure_lexical(text: str) -> str:
    """Deterministic pressure level: 'low' | 'medium' | 'high'.

    Cheap + reproducible. Used as the default path and as the fallback
    when the LLM-backed path fails.
    """
    if not isinstance(text, str) or not text:
        return "low"
    low = text.lower()
    if any(kw in low for kw in _PRESSURE_HIGH):
        return "high"
    if any(kw in low for kw in _PRESSURE_MEDIUM):
        return "medium"
    return "low"


def _classify_pressure(user_id: str, text: str) -> str:
    """Resolve pressure level.

    Default: deterministic lexical classifier (fast, free).
    When ``CLARITYOS_NEWS_BASIN_EP=1``: call
    ``intelligence_kernel.run_emotional_physics`` and read
    ``edge_pressure.signal_intensity`` from the result. Falls back to
    lexical on any error (the kernel call is expensive enough that
    failures shouldn't poison the batch).
    """
    if not (os.environ.get("CLARITYOS_NEWS_BASIN_EP") or "").strip():
        return _classify_pressure_lexical(text)
    try:
        import intelligence_kernel
        result = intelligence_kernel.run_emotional_physics(user_id, text)
        ep_layer = result.get("edge_pressure") if isinstance(result, dict) else None
        if isinstance(ep_layer, dict):
            si = ep_layer.get("signal_intensity")
            if isinstance(si, str) and si in ("low", "medium", "high"):
                return si
    except Exception as e:  # pragma: no cover (defensive)
        logger.info(
            "personal_news_basin: EP classifier failed, falling back: %s", e,
        )
    return _classify_pressure_lexical(text)


_PRESSURE_TO_FLOAT: dict[str, float] = {
    "low":    0.0,
    "medium": 0.5,
    "high":   1.0,
}


def _compute_narrative_temperature(sentiment: float, pressure: str) -> float:
    """Blend |sentiment| and pressure level into a 0–1 scalar.

    Formula:
        temp = 0.5 * clamp(|sentiment|) + 0.5 * pressure_float

    where pressure_float is {low:0, medium:0.5, high:1.0}. Rounded to
    3 decimal places for stable comparison.
    """
    try:
        s = float(sentiment) if sentiment is not None else 0.0
    except (TypeError, ValueError):
        s = 0.0
    sent_mag = abs(s)
    if sent_mag > 1.0:
        sent_mag = 1.0
    pres_val = _PRESSURE_TO_FLOAT.get(pressure, 0.0)
    return round(0.5 * sent_mag + 0.5 * pres_val, 3)


def _coerce_sentiment(v: Any) -> float:
    """Coerce a model-supplied sentiment to a float in [-1, 1]."""
    try:
        f = float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0
    if f < -1.0:
        return -1.0
    if f > 1.0:
        return 1.0
    return f


def normalize_headline(
    raw: dict,
    source: str,
    user_id: str = "system",
) -> dict:
    """Convert a raw oracle headline into the canonical packet schema.

    Tolerates missing fields with sensible defaults. Pressure +
    narrative_temperature + region are derived deterministically (the
    model is not asked for them) so the output is reproducible at the
    level of (raw, source) pairs when EP-classifier is off.

    Returns a dict with exactly the ``PACKET_KEYS`` keys.
    """
    if not isinstance(raw, dict):
        raw = {}
    src = source.strip() if isinstance(source, str) else "unknown"

    title = str(raw.get("title") or raw.get("headline") or "").strip()
    timestamp = str(raw.get("timestamp") or "unknown").strip() or "unknown"
    category = str(raw.get("category") or "general").strip() or "general"
    sentiment = _coerce_sentiment(raw.get("sentiment"))

    pressure = _classify_pressure(user_id, title)
    region = _classify_region(title)
    narrative_temperature = _compute_narrative_temperature(sentiment, pressure)

    return {
        "source":                src,
        "headline":              title,
        "timestamp":             timestamp,
        "category":              category,
        "sentiment":             sentiment,
        "pressure":              pressure,
        "narrative_temperature": narrative_temperature,
        "region":                region,
        "retrieved_at":          datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# 4. build_envelope
# ---------------------------------------------------------------------------
def build_envelope(items: list[dict], user_id: str = "system") -> dict:
    """Wrap normalised items in the news_basin envelope.

    Envelope shape:
        {
            "type":         "news_basin",
            "user":         <str>,
            "generated_at": <ISO 8601 string>,
            "items":        [<packet>, ...],
        }
    """
    return {
        "type":         ENVELOPE_TYPE,
        "user":         str(user_id) if user_id is not None else "system",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items":        list(items) if isinstance(items, list) else [],
    }


# ---------------------------------------------------------------------------
# 5. write_to_ingestion_bus
# ---------------------------------------------------------------------------
def write_to_ingestion_bus(envelope: dict) -> str:
    """Submit the envelope as a packet on the ingestion bus.

    Returns the packet_id. Propagates ValueError from the bus (e.g.,
    when ``envelope.type`` is missing); the caller in ``run_news_basin``
    catches and records None.
    """
    from ELINS import ingestion_bus
    return ingestion_bus.write_packet(envelope)


# ---------------------------------------------------------------------------
# 6. write_to_library
# ---------------------------------------------------------------------------
def _safe_iso_to_dt(s: Any) -> Optional[datetime]:
    """Best-effort ISO 8601 → datetime. Returns None on failure."""
    if not isinstance(s, str):
        return None
    try:
        # Tolerate trailing 'Z'.
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def write_to_library(envelope: dict) -> str:
    """Persist a JSON copy of the envelope at
    ``<library_dir>/<YYYY-MM-DD_HHMM>.json``.

    Filename is derived from the envelope's ``generated_at`` (falls
    back to now if missing/invalid). Returns the absolute file path
    as a string.

    Creates ``library_dir`` if it doesn't exist (parents=True).
    """
    if not isinstance(envelope, dict):
        raise ValueError("envelope must be a dict")

    dir_path = _resolve_library_dir()
    dir_path.mkdir(parents=True, exist_ok=True)

    dt = _safe_iso_to_dt(envelope.get("generated_at"))
    if dt is None:
        dt = datetime.now(timezone.utc)
    fname = dt.strftime("%Y-%m-%d_%H%M") + ".json"
    file_path = dir_path / fname

    file_path.write_text(
        json.dumps(envelope, indent=2, default=str),
        encoding="utf-8",
    )
    return str(file_path)


# ---------------------------------------------------------------------------
# 7. run_news_basin (entrypoint)
# ---------------------------------------------------------------------------
def run_news_basin(user_id: str = "system") -> dict:
    """Main entrypoint. Fetch → normalise → write.

    Workflow:
        1. Load configured sources. Empty list short-circuits to an
           empty envelope with NO bus/library writes (don't pollute
           the archive with vacuous runs).
        2. Per source, fetch headlines via perplexity. Errors degrade
           that source to zero items; other sources continue.
        3. Normalise each raw headline into the canonical packet.
        4. Build the envelope.
        5. Write to the ingestion bus AND the library (each is
           best-effort; failures are recorded as None on the returned
           envelope under the leading-underscore meta keys).

    Returns the envelope (with ``_bus_packet_id`` and ``_library_path``
    appended). The scheduler / surface consumes this directly.
    """
    sources = load_sources()
    if not sources:
        logger.info("personal_news_basin: no sources configured — short-circuiting")
        return build_envelope([], user_id)

    items: list[dict] = []
    for source in sources:
        raw_headlines = fetch_headlines_for_source(source)
        for raw in raw_headlines:
            items.append(normalize_headline(raw, source, user_id))

    envelope = build_envelope(items, user_id)

    # Side-effect writes are best-effort; failures don't poison the
    # envelope returned to the caller. The two meta keys are leading-
    # underscore so they don't collide with the published shape.
    try:
        envelope["_bus_packet_id"] = write_to_ingestion_bus(envelope)
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning("personal_news_basin: bus write failed: %s", e)
        envelope["_bus_packet_id"] = None

    try:
        envelope["_library_path"] = write_to_library(envelope)
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning("personal_news_basin: library write failed: %s", e)
        envelope["_library_path"] = None

    return envelope
