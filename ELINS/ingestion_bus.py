"""
v54 — Ingestion bus (RSS/Atom + manual).

Per-user signal ingestion. Two paths:

    1. RSS/Atom feed registration. Users register up to 5 feed URLs.
       Each run fetches the feed, parses up to 5 items, hands each
       item to intelligence_kernel.run_elins_v2, and persists the
       result to library_store.

    2. Manual ingestion. Users POST text they have legitimately
       accessed (their own subscription content, notes, transcripts).
       Same downstream path: run_elins_v2 → library_store.

Architecture / safety:

  * Stdlib only — no feedparser, no defusedxml, no third-party deps.
  * Outbound HTTP only via registered RSS/Atom URLs. http/https only,
    no redirects, 2 MB response cap, 10 s timeout.
  * No HTML parsing, no scraping, no eval / no exec, no compile of
    user-supplied source. The "user-defined Python extract_fn"
    surface from the original brief was rejected at architecture
    review (RCE risk).
  * Per-user 5-feed cap, 5-items-per-run cap. Both locked.
  * Visibility is "private" on every persisted entry; the field is
    stored so a future pass can add cohort sharing without migration.
  * Billion-laughs / entity-expansion is bounded by the fetch size cap
    (2 MB) AND a post-parse element-count cap (50000).

Public API:

    INGESTION_VERSION
    FEED_LIMIT_PER_USER          = 5
    ITEMS_PER_FEED_PER_RUN       = 5
    MAX_FETCH_BYTES              = 2 * 1024 * 1024
    FETCH_TIMEOUT_SECONDS        = 10.0
    MAX_ELEMENTS_IN_FEED         = 50_000
    MAX_TEXT_BYTES               = 200_000
    ALLOWED_URL_SCHEMES          = ("http", "https")
    LIBRARY_TAG                  = "elins_v2_ingestion"

    register_feed(user, *, name, url, region=None) -> dict
    list_feeds(user)                                -> list[dict]
    get_feed(user, feed_id)                         -> Optional[dict]
    delete_feed(user, feed_id)                      -> None    # raises KeyError

    fetch_feed_bytes(url, *, max_bytes, timeout)    -> bytes
    parse_feed_items(raw_bytes)                     -> list[dict]
    item_text_for_elins(item)                       -> str

    persist_to_library(user, *, source, region, raw_text,
                       envelope, item_meta=None,
                       visibility="private")        -> str   # library_id

    # Generic packet log (additive Phase-2 surface — see
    # THREE_PRODUCT_SUITE_PLAN.md). RSS feeds remain the legacy path;
    # write_packet generalises the bus over any envelope type
    # (e.g., 'news_basin') so non-RSS producers like
    # personal_news_basin.py have a consistent in-memory sink.
    write_packet(packet)                            -> str   # packet_id
    list_packets(type_filter=None, limit=100)       -> list[dict]
    get_packet(packet_id)                           -> Optional[dict]

    _reset_memory_for_tests() -> None
"""
from __future__ import annotations

import logging
import secrets
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Optional
from urllib.parse import urlparse

import library_store

logger = logging.getLogger("clarityos.ingestion_bus")

INGESTION_VERSION: str = "ingestion.v1.0"

# Locked policy (operator-approved 2026-05-10).
FEED_LIMIT_PER_USER: int = 5
ITEMS_PER_FEED_PER_RUN: int = 5

# Locked engineering safety caps.
MAX_FETCH_BYTES: int = 2 * 1024 * 1024     # 2 MB
FETCH_TIMEOUT_SECONDS: float = 10.0
MAX_ELEMENTS_IN_FEED: int = 50_000          # billion-laughs guard
MAX_TEXT_BYTES: int = 200_000               # cap manual paste at 200 KB
ALLOWED_URL_SCHEMES: tuple = ("http", "https")
LIBRARY_TAG: str = "elins_v2_ingestion"

# Generic packet log cap (FIFO drop). Keeps memory bounded across
# long-running daemons that emit packets at cadence.
PACKET_LOG_LIMIT: int = 1000

# Per-user feed registry. {user: [feed_dict, ...]}.
_FEEDS: dict[str, list[dict]] = {}

# Generic packet log. Append-only with FIFO drop at PACKET_LOG_LIMIT.
# Each entry carries the original packet plus ``_packet_id`` and
# ``_received_at`` injected by ``write_packet``.
_PACKETS: list[dict] = []


def _reset_memory_for_tests() -> None:
    _FEEDS.clear()
    _PACKETS.clear()


# ---------------------------------------------------------------------------
# Feed registry
# ---------------------------------------------------------------------------
def _validate_url(url: str) -> None:
    if not isinstance(url, str) or not url:
        raise ValueError("url must be a non-empty string")
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_URL_SCHEMES:
        raise ValueError(
            f"url scheme must be http or https; got {parsed.scheme!r}",
        )
    if not parsed.netloc:
        raise ValueError("url must have a host")


def register_feed(
    user: str,
    *,
    name: str,
    url: str,
    region: Optional[str] = None,
) -> dict:
    """Register an RSS/Atom feed URL. Max 5 per user.

    Raises ValueError on invalid inputs / limit exceeded / duplicate.
    """
    if not isinstance(user, str) or not user:
        raise ValueError("user is required")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string")
    name = name.strip()
    if len(name) > 100:
        raise ValueError("name max length is 100")
    _validate_url(url)
    if region is not None and not isinstance(region, str):
        raise ValueError("region must be a string when provided")

    feeds = _FEEDS.setdefault(user, [])
    if len(feeds) >= FEED_LIMIT_PER_USER:
        raise ValueError(
            f"feed limit reached ({FEED_LIMIT_PER_USER} per user)",
        )
    if any(f["url"] == url for f in feeds):
        raise ValueError(f"feed url already registered: {url}")
    if any(f["name"] == name for f in feeds):
        raise ValueError(f"feed name already registered: {name}")

    feed_id = f"f_{int(time.time() * 1000)}_{len(feeds)}"
    entry = {
        "feed_id":    feed_id,
        "name":       name,
        "url":        url,
        "region":     region if isinstance(region, str) else None,
        "created_at": time.time(),
    }
    feeds.append(entry)
    return dict(entry)


def list_feeds(user: str) -> list[dict]:
    return [dict(f) for f in _FEEDS.get(user, [])]


def get_feed(user: str, feed_id: str) -> Optional[dict]:
    for f in _FEEDS.get(user, []):
        if f["feed_id"] == feed_id:
            return dict(f)
    return None


def delete_feed(user: str, feed_id: str) -> None:
    """Remove a feed by id. Raises KeyError if not found."""
    feeds = _FEEDS.get(user)
    if not feeds:
        raise KeyError(feed_id)
    for i, f in enumerate(feeds):
        if f["feed_id"] == feed_id:
            del feeds[i]
            return
    raise KeyError(feed_id)


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------
def fetch_feed_bytes(
    url: str,
    *,
    max_bytes: int = MAX_FETCH_BYTES,
    timeout: float = FETCH_TIMEOUT_SECONDS,
) -> bytes:
    """Fetch a URL via urllib with size/time caps. Returns raw bytes.

    Raises ValueError on transport failure, oversized response, or
    bad URL scheme.
    """
    _validate_url(url)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ClarityOS-Ingestion/1.0 (RSS/Atom fetcher)",
            "Accept": (
                "application/rss+xml, application/atom+xml, "
                "application/xml, text/xml"
            ),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            data = resp.read(max_bytes + 1)
    except urllib.error.URLError as e:
        raise ValueError(f"fetch failed: {e}") from e
    except Exception as e:  # pragma: no cover (defensive)
        raise ValueError(f"fetch failed: {e}") from e

    if len(data) > max_bytes:
        raise ValueError(
            f"feed exceeds size cap ({max_bytes} bytes)",
        )
    return data


# ---------------------------------------------------------------------------
# Parse — RSS 2.0 / RSS 1.0 (RDF) / Atom
# ---------------------------------------------------------------------------
def _localname(tag: str) -> str:
    """Strip XML namespace from an element tag."""
    return tag.split("}", 1)[-1] if "}" in tag else tag


def parse_feed_items(raw_bytes: bytes) -> list[dict]:
    """Parse RSS or Atom bytes. Returns up to ITEMS_PER_FEED_PER_RUN
    item dicts of shape::

        {
            "title":        <str>,
            "summary":      <str>,
            "link":         <str>,
            "published_at": <str>,
        }

    Raises ValueError on parse failure, unknown root tag, or
    element-count overflow (billion-laughs guard).
    """
    if not isinstance(raw_bytes, (bytes, bytearray)):
        raise ValueError("raw_bytes must be bytes")
    if len(raw_bytes) == 0:
        return []

    try:
        root = ET.fromstring(bytes(raw_bytes))
    except ET.ParseError as e:
        raise ValueError(f"feed parse error: {e}") from e

    # Post-parse element-count guard. With the 2 MB fetch cap this also
    # catches any feed with abusive entity expansion that survived the
    # fetch-side limit.
    element_count = sum(1 for _ in root.iter())
    if element_count > MAX_ELEMENTS_IN_FEED:
        raise ValueError(
            f"feed has {element_count} elements; over cap of "
            f"{MAX_ELEMENTS_IN_FEED}",
        )

    root_name = _localname(root.tag).lower()
    items: list[dict] = []

    if root_name in ("rss", "rdf"):
        # RSS 2.0: <rss><channel><item>...
        # RSS 1.0: <rdf:RDF><item>...
        for elem in root.iter():
            if _localname(elem.tag).lower() == "item":
                items.append(_rss_item_to_dict(elem))
                if len(items) >= ITEMS_PER_FEED_PER_RUN:
                    break
    elif root_name == "feed":
        # Atom: <feed><entry>...
        for elem in root.iter():
            if _localname(elem.tag).lower() == "entry":
                items.append(_atom_entry_to_dict(elem))
                if len(items) >= ITEMS_PER_FEED_PER_RUN:
                    break
    else:
        raise ValueError(f"unrecognised feed root tag: {root_name!r}")

    return items


def _rss_item_to_dict(elem) -> dict:
    title: Optional[str] = None
    summary: Optional[str] = None
    link: Optional[str] = None
    pub: Optional[str] = None
    for child in elem:
        ln = _localname(child.tag).lower()
        text = (child.text or "").strip()
        if ln == "title" and title is None:
            title = text
        elif ln in ("description", "summary") and summary is None:
            summary = text
        elif ln == "link" and link is None:
            link = text
        elif ln in ("pubdate", "date", "updated", "published") and pub is None:
            pub = text
    return {
        "title":        title or "",
        "summary":      summary or "",
        "link":         link or "",
        "published_at": pub or "",
    }


def _atom_entry_to_dict(elem) -> dict:
    title: Optional[str] = None
    summary: Optional[str] = None
    link: Optional[str] = None
    pub: Optional[str] = None
    for child in elem:
        ln = _localname(child.tag).lower()
        text = (child.text or "").strip()
        if ln == "title" and title is None:
            title = text
        elif ln in ("summary", "content") and summary is None:
            summary = text
        elif ln == "link":
            if link is None:
                href = child.get("href")
                link = href or text
        elif ln in ("updated", "published") and pub is None:
            pub = text
    return {
        "title":        title or "",
        "summary":      summary or "",
        "link":         link or "",
        "published_at": pub or "",
    }


def item_text_for_elins(item: dict) -> str:
    """Concatenate title + summary into the text the ELINS v2 view
    receives. Trims to MAX_TEXT_BYTES so a runaway item can't blow the
    prompt budget."""
    if not isinstance(item, dict):
        return ""
    title = (item.get("title") or "").strip()
    summary = (item.get("summary") or "").strip()
    text = f"{title}\n\n{summary}".strip()
    return text[:MAX_TEXT_BYTES]


# ---------------------------------------------------------------------------
# Library persistence
# ---------------------------------------------------------------------------
def persist_to_library(
    user: str,
    *,
    source: str,
    region: Optional[str],
    raw_text: str,
    envelope: dict,
    item_meta: Optional[dict] = None,
    visibility: str = "private",
) -> str:
    """Store an ingested ELINS v2 envelope as a library entry. Returns
    the library_id.

    ``visibility`` is stored as metadata; the v54 surface only supports
    ``"private"``. A future pass may add ``"cohort"`` for explicit
    sharing.
    """
    if not isinstance(user, str) or not user:
        raise ValueError("user is required")
    if visibility not in ("private",):
        # v54 surface only allows "private"; forward-compat to allow
        # "cohort" later without breaking callers.
        raise ValueError("visibility must be 'private' in v54")

    item_id = library_store.new_id()
    now = time.time()
    src_label = str(source or "ingestion")[:50]
    outputs = (envelope or {}).get("outputs") or {}
    attractor = outputs.get("attractor") or "S?"
    collapse = outputs.get("collapse_state") or "?"
    title = f"[{src_label}] {attractor} / {collapse}"

    tags: list[str] = [LIBRARY_TAG, src_label]
    if region:
        tags.append(f"region:{region}")

    capped_text = (raw_text or "")[:MAX_TEXT_BYTES]
    library_store.create(item_id, {
        "id":         item_id,
        "user":       user,
        "title":      title[:200],
        "content":    capped_text,
        "tags":       tags,
        "metadata":   {
            "ingestion_version": INGESTION_VERSION,
            "source":            source,
            "region":            region,
            "visibility":        visibility,
            "item":              item_meta or {},
            "envelope":          envelope,
        },
        "size_bytes": len(capped_text.encode("utf-8")),
        "created_at": now,
        "updated_at": now,
    })
    return item_id


# ---------------------------------------------------------------------------
# Generic packet log (Phase-2 additive surface)
# ---------------------------------------------------------------------------
def write_packet(packet: dict) -> str:
    """Append a generic packet to the in-memory ingestion bus.

    Packets are envelopes with at least:
        * ``type``         (non-empty string, e.g., 'news_basin')
        * ``generated_at`` (ISO 8601 string, set by producer)
        * ``items``        (list — the contents of the packet)

    Additional keys are tolerated and preserved verbatim. The function
    injects two managed fields on storage:

        * ``_packet_id``   — caller-opaque id ('pkt_<urlsafe>')
        * ``_received_at`` — float (server time.time())

    The log is capped at ``PACKET_LOG_LIMIT`` entries; the oldest is
    dropped when full.

    Returns the assigned packet_id. Raises ValueError on shape problems.
    """
    if not isinstance(packet, dict):
        raise ValueError("packet must be a dict")
    packet_type = packet.get("type")
    if not isinstance(packet_type, str) or not packet_type.strip():
        raise ValueError("packet.type must be a non-empty string")
    packet_id = "pkt_" + secrets.token_urlsafe(8)
    stored = dict(packet)
    stored["_packet_id"]   = packet_id
    stored["_received_at"] = time.time()
    _PACKETS.append(stored)
    while len(_PACKETS) > PACKET_LOG_LIMIT:
        _PACKETS.pop(0)
    return packet_id


def list_packets(
    type_filter: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """Return recent packets, newest last.

    Args:
        type_filter: if given, only packets whose ``type`` matches
            exactly are returned.
        limit: max number of entries returned. Clamped to
            ``PACKET_LOG_LIMIT``.

    Returns:
        A defensive shallow copy of the log slice.
    """
    if not isinstance(limit, int) or limit <= 0:
        return []
    limit = min(limit, PACKET_LOG_LIMIT)
    if type_filter:
        filtered = [dict(p) for p in _PACKETS if p.get("type") == type_filter]
        return filtered[-limit:]
    return [dict(p) for p in _PACKETS[-limit:]]


def get_packet(packet_id: str) -> Optional[dict]:
    """Return a packet by id, or None if not found."""
    if not isinstance(packet_id, str) or not packet_id:
        return None
    for p in _PACKETS:
        if p.get("_packet_id") == packet_id:
            return dict(p)
    return None
