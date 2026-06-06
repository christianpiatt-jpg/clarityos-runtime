"""
problem_solver/regression_first.py — V77 / ProblemSolver.REGRESSION_FIRST.

Operator-protocol kernel module. Each chain is an operator log of
**findings** (one per chain layer) plus free-form key/value tags and
a title + optional notes. Chains stay open until ``close_chain`` is
called; closing is irreversible (no ``reopen`` surface).

There is no canonical pre-populated layer scaffold and no automatic
state machine. The kernel never *advances* a chain — it only records
what the operator submits. The skills_export bundle's
``system_prompt.md`` (canonical EL/INS + RF integration) tells Claude
to *suggest* a layered diagnostic walk; the operator decides whether
to follow it.

V77 — pluggable storage. Every public function now takes an optional
``store=`` argument typed as ``RegressionChainStoreProtocol``
(``problem_solver.chain_store``). When omitted, the kernel uses
``DEFAULT_STORE`` (a module-level in-memory instance) which is the
right choice for unit tests and standalone scripts. Endpoint
handlers in ``app.py`` pass a fresh
``VaultBackedRegressionChainStore(session_user)`` per request, so
chains persist across requests and respect per-user vault
partitioning. The kernel itself stays user-agnostic.

Packet parser (``analyze_packet``) is a pure deterministic JSON
parser + validator. It does not call an LLM and does not load the
system prompt; it accepts a unified packet that an upstream caller
already constructed under the canonical bundle prompt. When
``build_chain=True AND regression_required=True AND the effective
title is non-empty``, it also opens an empty chain via
``start_chain`` and embeds it on the returned packet. The packet's
``regression_chain`` skeleton is informational — the kernel does not
seed it as layers. The operator drives layer creation via
``record_finding`` (1:N) until they post ``close_chain``.

Two vault namespaces are used: ``regression_chains.{chain_id}``
(every chain save, via ``VaultBackedRegressionChainStore``) and
``regression_packets.{chain_id}`` (write-once original packets for
V82 ``/replay``; written by the endpoint layer, not by this module).
Both are registered in ``memory_vault.ALLOWED_NAMESPACES``.

Pure functions, no I/O at module import. The system prompt file is
read lazily on the first ``_load_system_prompt`` call for upstream
callers that build LLM requests elsewhere — nothing in this
subsystem invokes a model. Tests reset the cache + default store
via ``_reset_for_tests``.

Public surface
--------------
    start_chain(title, *, notes=None, store=None) -> RegressionChain
    record_finding(chain_id, layer_index, status, notes=None, *, store=None) -> RegressionChain
    close_chain(chain_id, *, notes=None, store=None) -> RegressionChain
    tag_chain(chain_id, tags, *, store=None) -> RegressionChain
    delete_tag(chain_id, key, *, store=None) -> RegressionChain         # v81
    archive_chain(chain_id, *, store=None) -> RegressionChain           # v81
    get_chain(chain_id, *, store=None) -> RegressionChain
    list_chains(*, store=None) -> list[RegressionChain]
    analyze_packet(raw, *, title=None, build_chain=True, store=None) -> CognitivePacket | None
    RegressionChain, RegressionLayer, CognitivePacket  (TypedDicts)
    LAYER_STATUSES = ("ok", "issue", "blocked", "unknown")
    CLASSIFICATIONS = ("emotion-dominant", "balanced", "structure-dominant")
    SYSTEM_PROMPT_PATH
    PROTOCOL_NAME = "ProblemSolver.REGRESSION_FIRST"
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Literal, Optional, TypedDict, Union

from .chain_store import (
    DEFAULT_STORE,
    InMemoryRegressionChainStore,
    RegressionChainStoreProtocol,
    VaultBackedRegressionChainStore,
    _reset_default_store_for_tests,
)

logger = logging.getLogger("clarityos.problem_solver")

# ---------------------------------------------------------------------------
# Constants + paths
# ---------------------------------------------------------------------------
PROTOCOL_NAME: str = "ProblemSolver.REGRESSION_FIRST"

LAYER_STATUSES: tuple = ("ok", "issue", "blocked", "unknown")

# Per skills_export/regression_first/schema.json — what the canonical
# unified packet may emit as its classification field. NB: this is
# the bundle's vocabulary (hyphenated). The standalone el_ins bundle
# uses a different vocabulary (high_el / high_ins / balanced).
CLASSIFICATIONS: tuple = (
    "emotion-dominant",
    "balanced",
    "structure-dominant",
)

# Path to the canonical system prompt in the skills_export bundle.
# Read as plain text — NOT a Python import — so the ARCHITECTURE.md
# no-skills-import boundary is preserved.
_THIS_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT_PATH = (
    _THIS_DIR.parent / "skills_export" / "regression_first" / "system_prompt.md"
)

# Field length caps. Loose but bounded to keep stored payloads tame.
TITLE_MAX:        int = 200
NOTES_MAX:        int = 8 * 1024
LAYER_NOTES_MAX:  int = 4 * 1024
TAG_KEY_MAX:      int = 64
TAG_VALUE_MAX:    int = 256
TAGS_PER_CHAIN_MAX: int = 32


# ---------------------------------------------------------------------------
# Wall-clock helper (mockable for tests)
# ---------------------------------------------------------------------------
def _now_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------------------
# Creation-sequence counter (mirrors intelligence_kernel._next_macro_seq).
#
# Stamped onto every chain at ``start_chain`` time as ``seq``. It exists so
# stateless / per-request stores — notably ``VaultBackedRegressionChainStore``,
# which is reconstructed on every request and therefore cannot keep an
# in-process insertion counter — can order chains newest-first
# deterministically. ``created_at`` is a coarse ms wall clock
# (``time.time()`` resolves to ~15ms on Windows), so back-to-back
# ``start_chain`` calls routinely share an identical ``created_at``;
# ``seq`` is the monotonic tiebreak that keeps ordering stable instead of
# falling back to the random UUID ``chain_id``. The lock is pre-allocated at
# import to close the TOCTOU window (same reasoning as intelligence_kernel).
# ---------------------------------------------------------------------------
_creation_seq: int = 0
_creation_seq_lock: threading.Lock = threading.Lock()


def _next_creation_seq() -> int:
    global _creation_seq
    with _creation_seq_lock:
        _creation_seq += 1
        return _creation_seq


# ---------------------------------------------------------------------------
# TypedDicts — V76 stored chain shape
# ---------------------------------------------------------------------------
class RegressionLayer(TypedDict):
    layer_index: int          # 0-based, supplied by operator
    status: str               # ok | issue | blocked | unknown
    notes: Optional[str]
    updated_at: int           # ms epoch — set by kernel on every write


class RegressionChain(TypedDict):
    chain_id: str             # canonical UUID4 string (with dashes)
    created_at: int           # ms epoch — set by kernel on /start
    seq: int                  # monotonic creation counter — tiebreaks a
                              # shared (coarse) ``created_at`` so stateless
                              # stores order newest-first deterministically
    closed_at: Optional[int]  # ms epoch — set by kernel on /close
    title: str
    notes: Optional[str]
    layers: list[RegressionLayer]
    tags: dict[str, str]
    # v81 — visibility flag. Orthogonal to ``closed_at``: a chain can be
    # open+archived, closed+archived, etc. Archive does NOT lock
    # mutations — operators can still ``/step`` / ``/tag`` / ``/delete_tag``
    # / ``/close`` an archived chain. Default ``False``. Setting is
    # idempotent and (in V81) irreversible — no ``unarchive`` surface.
    archived: bool


# ---------------------------------------------------------------------------
# System prompt loader (cached)
# ---------------------------------------------------------------------------
_PROMPT_CACHE: Optional[str] = None


def _load_system_prompt() -> str:
    """Lazily read the canonical system prompt as plain text for
    upstream callers that build LLM requests elsewhere. Not used by
    ``analyze_packet`` — nothing in this subsystem invokes a model.
    Result is cached; ``_reset_prompt_cache`` is the test hook."""
    global _PROMPT_CACHE
    if _PROMPT_CACHE is not None:
        return _PROMPT_CACHE
    try:
        _PROMPT_CACHE = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning(
            "problem_solver: system_prompt.md not loadable (%s); "
            "upstream callers that build LLM requests will receive "
            "an empty string and must decide how to degrade.",
            e,
        )
        _PROMPT_CACHE = ""
    return _PROMPT_CACHE


def _reset_prompt_cache() -> None:
    """Test hook — clears the cached system prompt so a fresh read
    happens on the next call."""
    global _PROMPT_CACHE
    _PROMPT_CACHE = None


# ---------------------------------------------------------------------------
# Chain-id generator
# ---------------------------------------------------------------------------
def _make_chain_id() -> str:
    """Returns a canonical UUID4 string (36 chars with dashes).

    Tests can monkeypatch this when they need deterministic ids.
    """
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Chain store resolution
#
# The kernel never owns chain storage directly — it delegates to a
# pluggable ``RegressionChainStoreProtocol`` instance. When callers
# pass ``store=None`` the kernel uses ``DEFAULT_STORE``, an in-memory
# instance owned by ``problem_solver.chain_store``. Endpoints in
# ``app.py`` construct a fresh ``VaultBackedRegressionChainStore``
# per request so chains persist across requests and are per-user
# scoped via memory_vault.
# ---------------------------------------------------------------------------
def _resolve_store(
    store: Optional[RegressionChainStoreProtocol],
) -> RegressionChainStoreProtocol:
    return store if store is not None else DEFAULT_STORE


def get_chain(
    chain_id: str,
    *,
    store: Optional[RegressionChainStoreProtocol] = None,
) -> RegressionChain:
    """Return the stored chain for ``chain_id``. Raises ``KeyError``
    when the chain does not exist in ``store``."""
    chain = _resolve_store(store).get(chain_id)
    if chain is None:
        raise KeyError(chain_id)
    return chain   # type: ignore[return-value]


def list_chains(
    *,
    store: Optional[RegressionChainStoreProtocol] = None,
) -> list[RegressionChain]:
    """All chains in ``store``, newest-first.

    Ordering policy is delegated to the store's ``list_all``. Both stock
    backends order by ``(created_at, seq) DESC`` — ``seq`` is the
    monotonic per-chain creation counter stamped by ``start_chain``,
    which keeps newest-first stable when the coarse ms ``created_at``
    ties (e.g. rapid back-to-back creates on Windows). ``chain_id`` is a
    final deterministic tiebreak. The kernel just trusts whatever the
    store returns.
    """
    return _resolve_store(store).list_all()   # type: ignore[return-value]


def _reset_for_tests() -> None:
    """Wipe the module-level default store + prompt cache + seq counter."""
    global _creation_seq
    with _creation_seq_lock:
        _creation_seq = 0
    _reset_default_store_for_tests()
    _reset_prompt_cache()


# ---------------------------------------------------------------------------
# Public API — chain lifecycle
# ---------------------------------------------------------------------------
def start_chain(
    title: str,
    *,
    notes: Optional[str] = None,
    store: Optional[RegressionChainStoreProtocol] = None,
) -> RegressionChain:
    """Open a new chain. Layers + tags start empty; ``closed_at`` is
    None until ``close_chain`` is posted.

    Raises:
        ValueError — empty/whitespace title, oversized title/notes.
    """
    title = (title or "").strip()
    if not title:
        raise ValueError("title must be a non-empty string")
    if len(title) > TITLE_MAX:
        raise ValueError(f"title must be <= {TITLE_MAX} chars")
    norm_notes = _coerce_optional_notes(notes, cap=NOTES_MAX, field="notes")

    now = _now_ms()
    chain: RegressionChain = {
        "chain_id":   _make_chain_id(),
        "created_at": now,
        "seq":        _next_creation_seq(),
        "closed_at":  None,
        "title":      title,
        "notes":      norm_notes,
        "layers":     [],
        "tags":       {},
        "archived":   False,
    }
    _resolve_store(store).save(chain)
    return chain


def record_finding(
    chain_id: str,
    layer_index: int,
    status: Literal["ok", "issue", "blocked", "unknown"],
    notes: Optional[str] = None,
    *,
    store: Optional[RegressionChainStoreProtocol] = None,
) -> RegressionChain:
    """Record an operator finding for ``layer_index``. Layers
    auto-grow: if no entry exists for that index yet, one is
    appended; if one exists, it is overwritten (status + notes +
    updated_at). The layer list is then re-sorted by ``layer_index``
    ascending so callers see a stable order.

    Raises:
        KeyError   — unknown chain_id.
        ValueError — invalid status, negative/non-int layer_index,
                      oversized notes, chain already closed.
    """
    if status not in LAYER_STATUSES:
        raise ValueError(
            f"status must be one of {LAYER_STATUSES}, got {status!r}"
        )
    if not isinstance(layer_index, int) or isinstance(layer_index, bool):
        raise ValueError(
            f"layer_index must be a non-negative int, got "
            f"{type(layer_index).__name__}"
        )
    if layer_index < 0:
        raise ValueError(
            f"layer_index must be >= 0, got {layer_index}"
        )
    norm_notes = _coerce_optional_notes(
        notes, cap=LAYER_NOTES_MAX, field="notes",
    )

    resolved = _resolve_store(store)
    chain = get_chain(chain_id, store=resolved)
    if chain["closed_at"] is not None:
        raise ValueError(
            f"chain {chain_id} is closed; record_finding rejected"
        )

    now = _now_ms()
    found = False
    for layer in chain["layers"]:
        if layer["layer_index"] == layer_index:
            layer["status"]     = status
            layer["notes"]      = norm_notes
            layer["updated_at"] = now
            found = True
            break
    if not found:
        chain["layers"].append({
            "layer_index": layer_index,
            "status":      status,
            "notes":       norm_notes,
            "updated_at":  now,
        })
        chain["layers"].sort(key=lambda L: L["layer_index"])
    resolved.save(chain)
    return chain


def close_chain(
    chain_id: str,
    *,
    notes: Optional[str] = None,
    store: Optional[RegressionChainStoreProtocol] = None,
) -> RegressionChain:
    """Close a chain. Sets ``closed_at`` to now and (optionally)
    appends/overwrites the chain's top-level ``notes``. Closing is
    irreversible — subsequent ``record_finding`` / ``tag_chain`` /
    ``close_chain`` calls all raise.

    Raises:
        KeyError   — unknown chain_id.
        ValueError — chain already closed, oversized notes.
    """
    resolved = _resolve_store(store)
    chain = get_chain(chain_id, store=resolved)
    if chain["closed_at"] is not None:
        raise ValueError(
            f"chain {chain_id} is already closed"
        )
    if notes is not None:
        chain["notes"] = _coerce_optional_notes(
            notes, cap=NOTES_MAX, field="notes",
        )
    chain["closed_at"] = _now_ms()
    resolved.save(chain)
    return chain


def tag_chain(
    chain_id: str,
    tags: dict,
    *,
    store: Optional[RegressionChainStoreProtocol] = None,
) -> RegressionChain:
    """Merge ``tags`` into the chain's tag dict. Existing keys are
    overwritten by the supplied values; keys not in ``tags`` are
    preserved. Empty dict is a no-op. Validation is atomic — all
    keys/values are checked before any mutation, so a partial
    failure leaves no state behind. Single-key removal is exposed
    separately via ``delete_tag`` (V81+).

    Raises:
        KeyError   — unknown chain_id.
        ValueError — chain already closed, invalid key/value type,
                      oversized key/value, total tags exceeds cap.
    """
    if not isinstance(tags, dict):
        raise ValueError("tags must be a dict")

    resolved = _resolve_store(store)
    chain = get_chain(chain_id, store=resolved)
    if chain["closed_at"] is not None:
        raise ValueError(
            f"chain {chain_id} is closed; tag_chain rejected"
        )

    # Validate before mutating so a partial failure leaves no
    # state behind.
    normalised: dict[str, str] = {}
    for raw_key, raw_value in tags.items():
        if not isinstance(raw_key, str):
            raise ValueError(
                f"tag key must be a string, got {type(raw_key).__name__}"
            )
        if not isinstance(raw_value, str):
            raise ValueError(
                f"tag value must be a string, got "
                f"{type(raw_value).__name__}"
            )
        key = raw_key.strip()
        value = raw_value.strip()
        if not key:
            raise ValueError("tag key must be a non-empty string")
        if len(key) > TAG_KEY_MAX:
            raise ValueError(f"tag key must be <= {TAG_KEY_MAX} chars")
        if len(value) > TAG_VALUE_MAX:
            raise ValueError(
                f"tag value must be <= {TAG_VALUE_MAX} chars"
            )
        normalised[key] = value

    projected = {**chain["tags"], **normalised}
    if len(projected) > TAGS_PER_CHAIN_MAX:
        raise ValueError(
            f"chain tag count would exceed {TAGS_PER_CHAIN_MAX}"
        )
    chain["tags"] = projected
    resolved.save(chain)
    return chain


def delete_tag(
    chain_id: str,
    key: str,
    *,
    store: Optional[RegressionChainStoreProtocol] = None,
) -> RegressionChain:
    """Delete one tag key from the chain's tag dict. No-op when the
    key is not present (the returned chain is unchanged but the
    chain is still re-persisted to keep the store call shape uniform
    with the other mutators — vault backends may treat the no-op
    write as a touch on ``updated_at`` in future units).

    The endpoint layer wires this as ``POST /me/regression_first/delete_tag``
    and explicitly emits NO timeline event — tags are mid-investigation
    metadata, not state transitions.

    Raises:
        KeyError   — unknown chain_id.
        ValueError — invalid key type, chain closed.
    """
    if not isinstance(key, str):
        raise ValueError(f"tag key must be a string, got {type(key).__name__}")
    norm_key = key.strip()
    if not norm_key:
        raise ValueError("tag key must be a non-empty string")

    resolved = _resolve_store(store)
    chain = get_chain(chain_id, store=resolved)
    if chain["closed_at"] is not None:
        raise ValueError(
            f"chain {chain_id} is closed; delete_tag rejected"
        )

    if norm_key in chain["tags"]:
        chain["tags"].pop(norm_key, None)
        resolved.save(chain)
    # No-op path still returns the chain; the store hasn't drifted.
    return chain


def archive_chain(
    chain_id: str,
    *,
    store: Optional[RegressionChainStoreProtocol] = None,
) -> RegressionChain:
    """Mark a chain as archived (visibility flag only). Mutations
    remain allowed — ``archive_chain`` does NOT close the chain and
    does NOT lock further ``record_finding`` / ``tag_chain`` /
    ``delete_tag`` / ``close_chain`` calls.

    Idempotent: calling on an already-archived chain is a no-op and
    returns the chain unchanged. (Distinct from V77's ``close_chain``,
    which rejects double-close with ValueError. Archive is a *flag*,
    close is a *state transition*.)

    Raises:
        KeyError — unknown chain_id.
    """
    resolved = _resolve_store(store)
    chain = get_chain(chain_id, store=resolved)
    if chain.get("archived"):
        return chain
    chain["archived"] = True
    resolved.save(chain)
    return chain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _coerce_optional_notes(
    notes: Any, *, cap: int, field: str,
) -> Optional[str]:
    """Validate optional notes: accept None or a string up to ``cap``
    characters (after strip). Empty/whitespace-only strings normalise
    to None — callers shouldn't have to distinguish "I sent nothing"
    from "I sent the empty string"."""
    if notes is None:
        return None
    if not isinstance(notes, str):
        raise ValueError(f"{field} must be a string or null")
    stripped = notes.strip()
    if not stripped:
        return None
    if len(stripped) > cap:
        raise ValueError(f"{field} must be <= {cap} chars")
    return stripped


# ---------------------------------------------------------------------------
# Emitted-packet helper (auto-trigger path)
#
# The bundle prompt instructs Claude to emit a UNIFIED packet shape
# (EL/INS analysis + a stateless regression_chain skeleton — see
# ``skills_export/regression_first/schema.json``). The V76 kernel
# ingests the packet, returns a normalised analysis view, and
# (optionally) opens a chain with ``title = operator_intent``. The
# packet's skeleton is informational — not seeded as layers. The
# operator drives layer creation via ``/step``.
# ---------------------------------------------------------------------------
class CognitivePacket(TypedDict, total=False):
    EL: int
    INS: int
    ratio: str
    el_signals: list[str]
    ins_signals: list[str]
    classification: str
    operator_intent: str
    regression_required: bool
    regression_chain: list[dict]
    recommended_system_action: str
    chain: Optional[RegressionChain]   # populated when build_chain=True


def _extract_packet_dict(raw: Union[str, dict]) -> Optional[dict]:
    """Coerce ``raw`` into a dict. Strips a single ``` fence if
    present. Returns ``None`` on any parse failure."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if s.startswith("```"):
        fence_end = s.find("\n")
        if fence_end > 0:
            s = s[fence_end + 1:]
        if s.endswith("```"):
            s = s[:-3]
    try:
        body = json.loads(s)
    except (ValueError, TypeError):
        return None
    return body if isinstance(body, dict) else None


def analyze_packet(
    raw: Union[str, dict],
    *,
    title: Optional[str] = None,
    build_chain: bool = True,
    store: Optional[RegressionChainStoreProtocol] = None,
) -> Optional[CognitivePacket]:
    """Pure deterministic JSON parser + validator for a unified
    packet constructed upstream under the canonical bundle prompt.
    No LLM call, no prompt load, no I/O beyond the optional
    ``start_chain`` write through ``store``.

    Accepts ``raw`` as a JSON string (a single ``` fence is stripped
    if present) or a dict. Returns ``None`` — never raises — on any
    parse or validation failure: bad JSON, non-dict body, missing
    required field, ``EL`` or ``INS`` not an int in ``0..5``,
    ``classification`` not in ``CLASSIFICATIONS``, or
    ``regression_chain`` not a list.

    A chain is opened (via ``start_chain`` with ``store`` threaded
    through) and embedded at ``packet["chain"]`` only when all
    three conditions hold: ``build_chain=True``,
    ``regression_required=True``, and the effective title
    (``title`` or ``operator_intent`` from the packet) is non-empty
    after strip. Otherwise ``packet["chain"]`` is ``None``. The
    packet's ``regression_chain`` skeleton is informational — it is
    not seeded as layers; the operator drives layer creation via
    ``record_finding`` later.

    ``title`` defaults to ``operator_intent`` from the packet when
    the caller doesn't supply one.
    """
    body = _extract_packet_dict(raw)
    if body is None:
        return None

    # Required fields per schema.json.
    needed = (
        "EL", "INS", "ratio", "classification",
        "operator_intent", "regression_required",
        "regression_chain", "recommended_system_action",
    )
    for key in needed:
        if key not in body:
            return None

    try:
        el = int(body["EL"])
        ins = int(body["INS"])
    except (TypeError, ValueError):
        return None
    if not (0 <= el <= 5 and 0 <= ins <= 5):
        return None

    classification = body["classification"]
    if classification not in CLASSIFICATIONS:
        return None

    regression_required = bool(body["regression_required"])
    chain_skeleton = body["regression_chain"]
    if not isinstance(chain_skeleton, list):
        return None

    packet: CognitivePacket = {
        "EL":                        el,
        "INS":                       ins,
        "ratio":                     str(body["ratio"]),
        "el_signals":                [
            str(x) for x in (body.get("el_signals") or [])
        ],
        "ins_signals":               [
            str(x) for x in (body.get("ins_signals") or [])
        ],
        "classification":            classification,
        "operator_intent":           str(body["operator_intent"]),
        "regression_required":       regression_required,
        "regression_chain":          chain_skeleton,
        "recommended_system_action": str(body["recommended_system_action"]),
        "chain":                     None,
    }

    if build_chain and regression_required:
        effective_title = (title or packet["operator_intent"]).strip()
        if effective_title:
            try:
                chain = start_chain(
                    effective_title[:TITLE_MAX], store=store,
                )
                packet["chain"] = chain
            except ValueError:
                # Title was rejected (whitespace-only after slice) —
                # silently skip the chain build; caller still gets
                # the analysis view.
                pass

    return packet
