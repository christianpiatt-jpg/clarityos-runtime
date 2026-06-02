"""
directive_engine.py — Unified Directive Engine (A21).

Interpreter-layer foundation for the seven ClarityOS directives:

    #structure  #cite  #primitives  #regression  #compare  #reduce  #operator

A17/A18 wired ``#cite`` as a one-off. A21 generalises that pattern into a
single, extensible engine that every directive plugs into via a handler.

This module is PURE: it parses directives, runs per-directive pre/post
enforcement, and reports retry semantics + per-turn metadata. It performs
NO model calls, NO I/O, and — like ``cite_mode`` at A17 — is wired into
nothing yet. The kernel migration (replacing A18's inline ``#cite`` block in
``run_thread_message``) is A28; the handlers for the other six directives are
A22–A27.

Today only ``CiteHandler`` carries real logic, delegating to ``cite_mode`` so
the A18 grounded/incomplete/retry contract is reproduced exactly. The other
six are inert no-op stubs that the engine already recognises and routes, so
A22–A27 are drop-in handler implementations needing no engine changes.

Public API:
    parse_directives(text) -> DirectiveSet
    apply_pre_enforcement(directive_set, text) -> str
    apply_post_enforcement(directive_set, output, *, retry_used=False)
        -> (final_output, DirectiveMetadata)

    DIRECTIVES, DIRECTIVE_HANDLERS
    DirectiveSet, DirectiveResult, DirectiveMetadata, BaseDirectiveHandler
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cite_mode

# Canonical directive names, stable order.
DIRECTIVES: Tuple[str, ...] = (
    "structure", "cite", "primitives", "regression",
    "compare", "reduce", "operator",
)

# A leading "#word" token (alphabetic, word-bounded so "#citecisely" won't
# match "cite"). Case-insensitive; the captured name is normalised to lower.
_TOKEN_RE = re.compile(r"#([A-Za-z]+)\b")
# Separators consumed after each directive token (mirrors cite_mode).
_SEP = " \t:-"


@dataclass
class DirectiveSet:
    active: bool
    directives: List[str]        # normalized names, encounter order, de-duped
    raw_prefixes: List[str]      # original tokens as typed ("#Cite", "#cite", …)
    text: str                    # input with the leading directive run stripped


@dataclass
class DirectiveResult:
    """One handler's verdict on a model output."""
    name: str
    status: Optional[str] = None          # e.g. cite: "grounded"/"incomplete"/None
    retry_needed: bool = False
    retry_instruction: Optional[str] = None
    meta: dict = field(default_factory=dict)


@dataclass
class DirectiveMetadata:
    """Aggregate per-turn directive metadata + retry signalling."""
    per_directive: Dict[str, dict] = field(default_factory=dict)
    retry_needed: bool = False
    retry_instruction: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: dict(v) for k, v in self.per_directive.items()}


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
class BaseDirectiveHandler:
    """Default handler: recognised + routed, but enforces nothing.

    A22–A27 subclass this. ``pre`` may rewrite the user text before the model
    call; ``evaluate`` inspects the model output and returns a
    ``DirectiveResult`` (status / retry / metadata). Defaults are inert so an
    unimplemented directive is a safe no-op rather than a failure.
    """
    name: str = "base"

    def pre(self, text: str) -> str:
        return text

    def evaluate(self, output: str, *, retry_used: bool = False) -> DirectiveResult:
        return DirectiveResult(name=self.name)


class CiteHandler(BaseDirectiveHandler):
    """``#cite`` — delegates to ``cite_mode`` (A17), reproducing the A18
    contract: a factual claim without a citation, or an opinion without a
    basis, asks the kernel to re-query once; still ungrounded after that
    single retry → terminal ``"incomplete"``."""
    name = "cite"

    def evaluate(self, output: str, *, retry_used: bool = False) -> DirectiveResult:
        result = cite_mode.validate_cite_output(output)
        if result.ok:
            return DirectiveResult(
                name="cite", status="grounded",
                meta={"status": "grounded", "retry_used": retry_used},
            )
        if retry_used:
            # Retry budget spent and still ungrounded → terminal incomplete.
            return DirectiveResult(
                name="cite", status="incomplete",
                meta={"status": "incomplete", "retry_used": True},
            )
        # First pass, ungrounded → ask the kernel to re-query exactly once.
        return DirectiveResult(
            name="cite", status=None, retry_needed=True,
            retry_instruction=result.retry_instruction,
            meta={"status": None, "retry_used": False},
        )


# A22–A27 replace these stubs with real handlers. They are registered now so
# the engine already detects + routes the directive (no engine change later).
class StructureHandler(BaseDirectiveHandler):
    name = "structure"


class PrimitivesHandler(BaseDirectiveHandler):
    name = "primitives"


class RegressionHandler(BaseDirectiveHandler):
    name = "regression"


class CompareHandler(BaseDirectiveHandler):
    name = "compare"


class ReduceHandler(BaseDirectiveHandler):
    name = "reduce"


class OperatorHandler(BaseDirectiveHandler):
    name = "operator"


DIRECTIVE_HANDLERS: Dict[str, BaseDirectiveHandler] = {
    "structure":  StructureHandler(),
    "cite":       CiteHandler(),
    "primitives": PrimitivesHandler(),
    "regression": RegressionHandler(),
    "compare":    CompareHandler(),
    "reduce":     ReduceHandler(),
    "operator":   OperatorHandler(),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def parse_directives(text: str) -> DirectiveSet:
    """Detect + strip the leading run of directive tokens. Multiple may
    stack (``"#cite #structure …"``). Parsing stops at the first
    non-directive token, so ordinary ``#hashtag`` content mid-message is left
    intact. One-shot: only the leading run is inspected; nothing persists
    across turns. Non-str input returns an inactive set unchanged."""
    if not isinstance(text, str):
        return DirectiveSet(active=False, directives=[], raw_prefixes=[], text=text)
    remaining = text.lstrip()
    names: List[str] = []
    raws: List[str] = []
    while True:
        m = _TOKEN_RE.match(remaining)
        if not m:
            break
        name = m.group(1).lower()
        if name not in DIRECTIVE_HANDLERS:
            break  # unknown "#token" → not a directive; leave it in text
        raws.append(remaining[m.start():m.end()])
        if name not in names:
            names.append(name)
        remaining = remaining[m.end():].lstrip(_SEP)
    return DirectiveSet(
        active=bool(names), directives=names, raw_prefixes=raws, text=remaining,
    )


def apply_pre_enforcement(directive_set: DirectiveSet, text: str) -> str:
    """Run each active directive's ``pre`` hook over the user text, in
    encounter order. No-op for every directive at A21 (all ``pre`` are
    identity); A22–A27 may rewrite the prompt here."""
    out = text
    for name in directive_set.directives:
        handler = DIRECTIVE_HANDLERS.get(name)
        if handler is not None:
            out = handler.pre(out)
    return out


def apply_post_enforcement(
    directive_set: DirectiveSet,
    output: str,
    *,
    retry_used: bool = False,
) -> Tuple[str, DirectiveMetadata]:
    """Run each active directive's ``evaluate`` over the model output and
    aggregate the verdicts.

    Returns ``(final_output, DirectiveMetadata)``. ``retry_used`` marks the
    post-retry (final) evaluation so a handler can settle a terminal status
    (e.g. cite → ``"incomplete"``). Only directives that produce a status or
    metadata appear in ``per_directive``; inert stubs contribute nothing.

    ``final_output`` is the output unchanged at A21 — no handler rewrites it
    yet. A directive that needs to transform the reply (e.g. ``#reduce``) will
    do so here when its handler lands.
    """
    meta = DirectiveMetadata()
    instructions: List[str] = []
    for name in directive_set.directives:
        handler = DIRECTIVE_HANDLERS.get(name)
        if handler is None:
            continue
        result = handler.evaluate(output, retry_used=retry_used)
        if result.meta or result.status is not None:
            meta.per_directive[name] = dict(result.meta)
        if result.retry_needed:
            meta.retry_needed = True
            if result.retry_instruction:
                instructions.append(result.retry_instruction)
    meta.retry_instruction = " ".join(instructions) if instructions else None
    return output, meta
