"""
v33 — Standardized ELINS 10-layer pipeline + S_ELINS QC.

Canonical pipeline shape (all stages return plain JSON-serializable
dicts; no embeddings, no model calls):

    0. Input phase            — accept + normalize raw text
    1. Primitive extraction   — six EP primitives extracted via lexicon
    2. Domain mapping         — keyword-to-domain weights
    3. EP field summary       — averaged primitive intensity + signs
    4. Causal chain mapping   — pairwise primitive co-occurrence
    5. Stress/relief signals  — net pressure (stress - relief)
    6. Five-day forecast      — deterministic phase trajectory
    7. Synthesis layer        — top-line summary fields
    8. QC layer (S_ELINS)     — re-extract + score alignment
    9. Output object          — final flat record

The implementation is intentionally LEXICAL + DETERMINISTIC: no
embeddings, no model calls, no network. Tests assert stable output
shapes for given inputs. Real integration with the embedding /
neighborhood layer happens in `app.py:_run_g_elins` (the v28 path);
this module is the canonical SCENARIO-TEXT pipeline that the
standardization spec requires every ELINS surface to produce.

Public API:
    generate_ELINS(input_text: str, *, domain_hint: Optional[str]=None,
                   user: Optional[str]=None) -> dict
    generate_S_ELINS(elins_object: dict) -> dict

Both return JSON-serialisable dicts; ``generate_S_ELINS`` re-runs
extraction + EP scoring on the original input recovered from the
ELINS object's `input_phase.text` and reports pass/fail + deltas.
"""
from __future__ import annotations

import hashlib
import re
import time
from typing import Optional

from . import forecast_engine

# ---------------------------------------------------------------------------
# Layer + primitive identifiers
# ---------------------------------------------------------------------------
LAYER_NAMES: tuple = (
    "input_phase",
    "primitives",
    "domain_mapping",
    "ep_field_summary",
    "causal_chain",
    "stress_relief",
    "forecast_5day",
    "forecast_engine",
    "synthesis",
    "qc_s_elins",
    "output_object",
)

# Six EP primitives. Keep the keys stable — downstream consumers (Dewey,
# membership cohort metadata, the QC alignment scorer) depend on the names.
PRIMITIVE_KEYS: tuple = (
    "pressure",          # external force magnitude
    "tension",           # internal opposition
    "trust",             # cohesion / good-faith density
    "drift",             # vector-of-change toward a different state
    "contradiction",     # contradictory signals in the same field
    "alignment",         # convergence / shared direction
)

# Lexicon — deliberately small + well-bounded so the extraction is
# transparent. Keys are lowercase substrings; values are the primitive
# they bump and the increment per match. Tunable; tests pin behavior on
# specific inputs so changes here surface immediately.
# Trailing ``*`` marks a PREFIX token (leading \b only, open right edge) —
# see _compile_primitive_token. Unstarred tokens match as whole words.
# ``argu`` is deliberately UNSTARRED: starred it would still match
# "arguably" (spec §4 flags this); as a whole word it is a dead token,
# which satisfies the spec §8 / FRAGO requirement that "arguably" scores 0.
_PRIMITIVE_LEXICON: dict[str, list[tuple[str, float]]] = {
    "pressure":      [("pressure", 0.4), ("force", 0.3), ("strain", 0.3),
                      ("squeeze", 0.3), ("urgent", 0.2), ("crisis", 0.4),
                      ("collapse", 0.5), ("escalat*", 0.4)],
    "tension":       [("tension", 0.4), ("conflict", 0.3), ("dispute", 0.3),
                      ("oppos*", 0.3), ("argu", 0.2), ("clash", 0.3),
                      ("stand-off", 0.4), ("standoff", 0.4)],
    # Retired (B-2): trust and alignment are two-frame COMPARISONS, not
    # motions. The four stress primitives derive from motion and are
    # measurable at n=1; a comparison is not. This lexicon was scoring
    # word presence in place of a comparison the single-frame instrument
    # cannot make. Restore when memory exists (prior-run delta), not
    # with a better word list.
    "trust":         [],
    "drift":         [("drift", 0.4), ("erod*", 0.3), ("shift", 0.3),
                      ("slid*", 0.3), ("deteriorat*", 0.4), ("decline", 0.3),
                      ("trend toward", 0.4), ("away from", 0.3)],
    "contradiction": [("contradict*", 0.4), ("hypocris*", 0.4), ("inconsis*", 0.4),
                      ("paradox", 0.3), ("but also", 0.2), ("yet", 0.1),
                      ("at odds", 0.3), ("doublethink", 0.4)],
    # Retired (B-2) — same reason as "trust" above: a comparison, not a
    # motion. Keys stay in RELIEF_PRIMITIVES and score 0.0.
    "alignment":     [],
}

# Domain heuristic — same lexical pattern, mapped to the canonical
# domains the spec calls out. Tests pin a few representative inputs.
DOMAIN_HINTS: tuple = (
    "legal",
    "institutional",
    "economic",
    "geopolitical",
    "social",
    "personal",
    "technological",
    "ecological",
)

_DOMAIN_LEXICON: dict[str, list[str]] = {
    "legal":          ["law", "court", "judge", "ruling", "constitut", "statute",
                       "legal", "litigat", "supreme court", "judic"],
    "institutional":  ["institution", "agency", "regulat", "ministr", "bureau",
                       "oversight", "compliance", "governance", "watchdog"],
    "economic":       ["econom", "market", "inflat", "supply", "demand",
                       "tariff", "trade", "currenc", "fiscal", "monetary",
                       "deficit", "growth", "recession"],
    "geopolitical":   ["china", "russia", "us-", "u.s.", "nato", "border",
                       "alliance", "diploma", "sanction", "treaty", "war"],
    "social":         ["public", "voter", "protest", "movement", "communit",
                       "popular", "social", "media coverage", "sentiment"],
    "personal":       ["i ", "my ", "feel", "myself", "we ", "our ", "she ", "he ",
                       "they ", "personal"],
    "technological":  ["ai ", "model", "algorithm", "platform", "infrastructure",
                       "software", "chip", "data center"],
    "ecological":     ["climate", "carbon", "emission", "ecolog", "environment",
                       "drought", "biodivers", "energy supply"],
}

# Stress vs. relief separation — used by Layer 5. Stress primitives push
# the system toward instability; relief primitives push toward stability.
STRESS_PRIMITIVES = ("pressure", "tension", "drift", "contradiction")
RELIEF_PRIMITIVES = ("trust", "alignment")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalize(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError("input must be a string")
    s = text.strip()
    if not s:
        raise ValueError("input must be non-empty")
    return s


def _scenario_id(text: str) -> str:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sc_{h[:16]}"


# B-4 negation window (Line B spec §5). SUPPRESS only — never invert.
_NEGATORS = frozenset({
    "no", "not", "never", "without", "lacks", "lacking", "absent",
})
_NEGATOR_PREFIXES = ("de-", "dis-", "mis-", "un-", "non-")
_NEGATION_WINDOW = 3  # tokens preceding the match


def _compile_primitive_token(token: str) -> "re.Pattern":
    """Starred token (trailing ``*``) = prefix: leading boundary, open right
    edge. Unstarred = whole word. (Line B spec §4.)"""
    if token.endswith("*"):
        return re.compile(r"\b" + re.escape(token[:-1]))
    return re.compile(r"\b" + re.escape(token) + r"\b")


_PRIMITIVE_PATTERNS: dict = {
    key: [(_compile_primitive_token(tok), float(w)) for tok, w in entries]
    for key, entries in _PRIMITIVE_LEXICON.items()
}


# ---------------------------------------------------------------------------
# #355 3a -- THE DOMAIN MATCHER. Version-stamped, because 3a changes what a
# domain score MEANS and the stored records carry the old calibration.
# ---------------------------------------------------------------------------
#: Bumped whenever the domain MATCHING RULE changes. Stamped forward onto every
#: new run (``domain_mapping.matcher_version``) so an old score and a new score
#: are never silently averaged into one series. NOT a backfill: records written
#: before this carry no stamp, and their absence of a stamp is the reading
#: "matched under the pre-#355 substring rule".
#: ★ THE NAME DESCRIBES THE RULE, and it is "classed" rather than
#: "wordboundary" because a blanket word boundary is precisely what this is
#: NOT: the eight space-marked tokens get one and the seventy roots do not.
#: An earlier draft of this constant said ``v2-wordboundary`` while the code
#: did something else, which is the same defect as a comment that lies. Safe
#: to name correctly now because nothing has been deployed and no stored
#: record carries v2 yet -- once one does, this string is frozen.
DOMAIN_MATCHER_VERSION: str = "domain.matcher.v2-classed"

#: #355 3c -- the minimum signal a domain must clear to be NAMED.
#: AT THE GLOBAL CALL SITE scores are whole-token hit counts, so ``> 0.0`` and
#: ``>= 1.0`` select the same set and a floor only bites at 2. One token is an
#: OCCURRENCE (a legal brief may say "market" once); two is a signal. This is
#: v1.8.3 §14.7 applied to the sibling it was never applied to --
#: ``_domain_top`` crowns a winner by strict inequality over magnitudes.
#:
#: ★★ THAT UNIT DOES NOT HOLD AT THE TWO REGIONAL CALL SITES, and #355 is what
#: routed them here. ``_apply_domain_overlay`` feeds ``round((raw + 0.1) *
#: multiplier, 4)`` (regional_elins.py:173) and ``_merge_eso`` feeds raw plus
#: an ESO ``domain_bias`` float (:243), so a regional score is a WEIGHTED
#: MAGNITUDE, not a count -- 1.65, 1.76, 1.32 are ordinary values there. A
#: floor calibrated in counts therefore bites differently: measured
#: 2026-09-18 on ``run_regional_elins(region, "u1")`` with no ESO, FIVE OF SIX
#: regions now return ``top: None`` (US 1.65, MEA 1.76, APAC 1.32, Markets
#: 1.76, Tech 1.76) where all six crowned before. ``effective_top`` still
#: reads, because every region profile supplies a ``default_domain_hint`` and
#: the hint stands in -- so the SURFACE is unchanged and it is ``top`` that
#: went null. Named, not silently absorbed.
#:
#: ★ PROVISIONAL, AND NOW IN TWO PARTS: the NUMBER is CT-1's to ratify, and so
#: is whether one number can serve two units at all. R-374-B.
DOMAIN_MIN_SIGNAL: float = 2.0


def _compile_domain_token(token: str) -> "re.Pattern":
    """#355 3a/3b -- THE LEXICON ALREADY MARKS ITS OWN TOKEN CLASSES, in the
    one character it was always carrying. Read the mark; do not impose a rule.

        token ENDS IN A SPACE   a WHOLE WORD -- leading ``\b``, and the space
                                itself closes the right edge.
                                Eight of them: ``'i '``, ``'my '``, ``'we '``,
                                ``'our '``, ``'she '``, ``'he '``, ``'they '``
                                (:130-131) and ``'ai '`` (:133).
        otherwise               a ROOT -- matched anywhere, exactly as before
                                (bare substring, expressed as a literal
                                pattern). The other seventy.

    ★ THE DEFECT THIS SITE WAS OPENED FOR IS ENTIRELY IN THE FIRST CLASS.
    Under bare substring ``'he '`` matched inside ``'the '``, so ``personal``
    scored on any English prose and a purely third-person legal text read
    personal 5.0 vs legal 4.0 and was classified PERSONAL. A leading ``\b``
    fixes exactly that: in ``'the '`` the ``h`` is preceded by ``t``, so there
    is no boundary and no match, while a real ``'he '`` still scores.

    ★★ AND IT MUST NOT BE APPLIED TO THE SECOND CLASS. The roots are written
    to match INSIDE longer words -- that is what ``constitut``, ``regulat``,
    ``econom``, ``ministr``, ``judic``, ``inflat``, ``currenc`` are FOR. A
    leading ``\b`` turns "root anywhere" into "word-initial only" and silently
    deletes deregulation, unconstitutional, macroeconomic, administration,
    illegal, interagency, hydrocarbons, prejudicial, disinflation,
    cryptocurrency. Measured 2026-09-18 -- "Deregulation of the agency was
    challenged as unconstitutional." scored institutional 2.0 and named
    `institutional` under substring, and named NOTHING under a blanket
    leading ``\b``; "Macroeconomic conditions and socioeconomic pressure
    dominated." lost its scores dict entirely. Domain history would have gone
    blank on text whose domain is unambiguous.

    ★★★ THREE RULES WERE MEASURED AGAINST ALL FIVE REQUIREMENTS AT ONCE, and
    only this one satisfies them (the earlier two each satisfied one axis and
    were caught by refuters, not by the tests, because every probe placed its
    token at a word start and so could only ever test the right edge):

        rule                'he ' false / real   roots   inflected   regressions
        substring (pre)         5 / 2            10/10     5/5          3 of 6 wrong
        leading-\b on ALL       0 / 2             0/10     5/5          2 of 6 wrong
        classed (this)          0 / 2            10/10     5/5          6 of 6 right

    NOT CHANGED, and named: a root still matches inside an unrelated word --
    ``public`` inside "republic", ``war`` inside "toward", ``model`` inside
    "remodel". That is the pre-#355 behaviour of the second class, it is not
    what this site was opened for, and narrowing it means editing the lexicon,
    which is out of scope. Pinned by ``test_a_root_token_matches_inside_a
    _prefixed_word`` and ``test_a_pronoun_token_matches_only_the_pronoun``."""
    if token.endswith(" "):
        return re.compile(r"\b" + re.escape(token))
    return re.compile(re.escape(token))


_DOMAIN_PATTERNS: dict = {
    key: [_compile_domain_token(tok) for tok in tokens]
    for key, tokens in _DOMAIN_LEXICON.items()
}


def _is_negated(text_lower: str, start: int) -> bool:
    """True when the match at ``start`` is negated: a standalone negator
    inside the 3-token window, the phrase 'free of', or a hyphenated
    negator prefix attached to the match ('de-escalate'). Suppression
    only — an inverted hit would be a direction claim this lexicon
    cannot support (Line B spec §5)."""
    head = text_lower[:start]
    if head.endswith(_NEGATOR_PREFIXES):
        return True
    toks = [t.strip(".,;:!?()\"'") for t in head.split()[-_NEGATION_WINDOW:]]
    if any(t in _NEGATORS for t in toks):
        return True
    return "free of" in " ".join(toks)


def _count_matches(text_lower: str, lexicon: dict) -> dict:
    """For each key in ``lexicon``, sum match weights present in the
    text. Accepts both lexicon shapes used in this module:
    ``list[(token, weight)]`` (primitive lexicon) or plain
    ``list[str]`` (domain lexicon — every match weighs 1.0).

    The primitive lexicon is matched via precompiled word-boundary
    patterns with negation suppression (Line B spec §4-§5).

    ★ #355 3a (CT-1 2026-09-18) -- THE DOMAIN LEXICON NOW USES WORD
    BOUNDARIES TOO. Spec §7's exclusion is lifted. Under bare substring
    the token ``'he '`` matched inside ``'the '``, so ``personal`` scored
    on any English prose: a purely third-person legal text read
    personal 5.0 vs legal 4.0 and was classified PERSONAL. The floor was
    one token, not a register effect.

    ★ THE PER-TOKEN RULE (#355 3b) IS READ OFF THE LEXICON, NOT IMPOSED:
    a token ending in a SPACE is a whole word and gets a leading ``\b``
    (eight of them, all pronouns); every other token is a ROOT and is
    matched anywhere, exactly as before. See ``_compile_domain_token``
    for the measurement -- a blanket leading ``\b`` deletes 10 of 10
    tested root-inside-word matches (deregulation, unconstitutional,
    macroeconomic, administration, illegal, ...), and a trailing ``\b``
    kills 45 of 78 tokens against inflected prose. Only the classed rule
    satisfies all five requirements at once. ``'us-'``, ``'u.s.'`` and the
    four multi-word phrases are roots and are unchanged from pre-#355.
    Negation suppression is NOT applied here -- it is calibrated for the
    primitive lexicon and a domain mention inside a negation is still a
    mention of the domain.

    Cap min(5, hits) per token preserved unchanged."""
    out: dict[str, float] = {k: 0.0 for k in lexicon.keys()}
    if lexicon is _DOMAIN_LEXICON:
        for key, patterns in _DOMAIN_PATTERNS.items():
            for pattern in patterns:
                hits = min(5, len(pattern.findall(text_lower)))
                out[key] += float(hits)
        return out
    if lexicon is _PRIMITIVE_LEXICON:
        for key, patterns in _PRIMITIVE_PATTERNS.items():
            for pattern, weight in patterns:
                hits = 0
                for m in pattern.finditer(text_lower):
                    if not _is_negated(text_lower, m.start()):
                        hits += 1
                out[key] += weight * min(5, hits)
        return out
    for key, entries in lexicon.items():
        for entry in entries:
            if isinstance(entry, tuple) and len(entry) == 2:
                token, weight = entry
            else:
                token, weight = entry, 1.0
            if token in text_lower:
                # Count multiple occurrences (cap at 5 per token to bound
                # output range without thresholding the lexicon further).
                hits = min(5, text_lower.count(token))
                out[key] += float(weight) * hits
    return out


def _round_dict(d: dict, places: int = 4) -> dict:
    return {k: round(float(v), places) for k, v in d.items()}


def _domain_top(scores: dict) -> tuple[Optional[str], dict]:
    """Pick the highest-scoring domain, or NAME NONE when nothing clears the
    floor. Ties are broken alphabetically so the output is deterministic.

    ★ #355 3c -- NO DEFAULT WINNER. v1.8.3 §14.7 removed ``dominant`` for
    "deriving a categorical claim from a strict inequality where only a
    magnitude exists", and recorded that the thresholded and unthresholded
    reads "disagreed on 17 of 19 non-null segments" (:305-309). This function
    is the sibling that ruling was never applied to. A top score below
    ``DOMAIN_MIN_SIGNAL`` now names NO domain -- ``None``, which the callers
    already handle, because ``effective_top`` has always been able to be None.

    ★ THE SCORES ARE STILL RETURNED. A domain that scored but did not win, and
    a field that scored but did not clear the floor, are both still visible in
    ``scores``: the floor withholds the NAME, it does not hide the reading."""
    nz = {k: v for k, v in scores.items() if v > 0.0}
    if not nz:
        return None, {}
    top = sorted(nz.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    if nz[top] < DOMAIN_MIN_SIGNAL:
        # Below the floor: the reading stands, the claim does not.
        return None, _round_dict(nz)
    return top, _round_dict(nz)


# ---------------------------------------------------------------------------
# Per-layer functions (numbered to match the spec)
# ---------------------------------------------------------------------------
def _layer_0_input(text: str, *, domain_hint: Optional[str], user: Optional[str]) -> dict:
    return {
        "scenario_id": _scenario_id(text),
        "text": text,
        "char_count": len(text),
        "word_count": len(text.split()),
        "domain_hint": domain_hint,
        "user": user,
        "ts": time.time(),
    }


def _layer_1_primitives(text: str) -> dict:
    """Six-primitive extraction. Returns raw match counts + a
    normalized [0..1] intensity per primitive."""
    text_lower = text.lower()
    raw = _count_matches(text_lower, _PRIMITIVE_LEXICON)
    # Normalize: divide by 4.0 (a reasonable upper bound given the
    # weights + cap of 5 occurrences) and clip to [0..1].
    intensities = {k: max(0.0, min(1.0, v / 4.0)) for k, v in raw.items()}
    return {
        "raw_scores": _round_dict(raw),
        "intensities": _round_dict(intensities),
        "primitive_keys": list(PRIMITIVE_KEYS),
    }


def _layer_2_domains(text: str, hint: Optional[str]) -> dict:
    text_lower = text.lower()
    matches = _count_matches(text_lower, _DOMAIN_LEXICON)
    top, scores = _domain_top(matches)
    # #355 -- the stamp rides on the layer it describes, so a reader never has
    # to infer which calibration produced the number in front of it.
    if hint and hint in DOMAIN_HINTS:
        # Caller hint nudges but does not override; record both.
        return {
            "scores": scores,
            "top": top,
            "hint": hint,
            "effective_top": hint if top is None else top,
            "matcher_version": DOMAIN_MATCHER_VERSION,
        }
    return {
        "scores": scores, "top": top, "hint": None, "effective_top": top,
        "matcher_version": DOMAIN_MATCHER_VERSION,
    }


def _layer_3_ep_summary(primitives: dict) -> dict:
    intensities = primitives["intensities"]
    # B-1 (Line B spec §2): an all-zero intensity vector is ABSENCE, not
    # balance. "balanced" must mean measured-and-even, not nothing-found.
    no_signal = all(v == 0.0 for v in intensities.values())
    # Net signed value: relief primitives count positive; stress primitives
    # count negative. Bounded by the count of primitive groups.
    pos = sum(intensities[k] for k in RELIEF_PRIMITIVES)
    neg = sum(intensities[k] for k in STRESS_PRIMITIVES)
    return {
        "stress_total": round(neg, 4),
        "relief_total": round(pos, 4),
        "net": round(pos - neg, 4),
        # `dominant` removed (v1.8.3 §14.7): it derived a categorical claim
        # from a strict inequality (pos > neg) where only a magnitude exists —
        # a rank, not an option-delta. `signal` already carries the
        # thresholded read, and the two disagreed on 17 of 19 non-null
        # segments.
        "intensity_mean": round(sum(intensities.values()) / len(intensities), 4),
        "no_signal": no_signal,
    }


def _layer_4_causal_chain(primitives: dict) -> dict:
    """Pairwise co-occurrence — surfaces which pairs of primitives are
    BOTH present at meaningful intensity. Threshold: 0.05."""
    intensities = primitives["intensities"]
    pairs = []
    threshold = 0.05
    keys = list(PRIMITIVE_KEYS)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            ia, ib = intensities[a], intensities[b]
            if ia >= threshold and ib >= threshold:
                pairs.append({
                    "from": a, "to": b,
                    "weight": round(min(ia, ib), 4),
                    # Addendum 3, 2026-08-04: signed gradient in [-1, 1] with
                    # a true zero. weight is a co-occurrence FLOOR -- it
                    # discards magnitude and direction; delta carries both.
                    # The existing both->=threshold guard means delta == 0 can
                    # only mean balanced-by-evidence, never balanced-by-miss.
                    "delta": round(ia - ib, 4),
                })
    pairs.sort(key=lambda p: -p["weight"])
    return {
        "edges": pairs,
        "edge_count": len(pairs),
        "threshold": threshold,
    }


def _layer_5_stress_relief(ep_summary: dict, causal: dict) -> dict:
    net = float(ep_summary["net"])
    if ep_summary.get("no_signal"):
        # B-1 (Line B spec §2): absence is not balance — null propagates.
        signal = None
    elif net > 0.15:
        signal = "relief_dominant"
    elif net < -0.15:
        signal = "stress_dominant"
    else:
        signal = "balanced"
    return {
        "signal": signal,
        "net_pressure": round(-net, 4),  # +ve = system is stressed
        "edge_count": causal["edge_count"],
    }


def _layer_6_forecast_5day(ep_summary: dict, stress_relief: dict) -> dict:
    """Deterministic phase trajectory. Each day's bias is the previous day's
    net plus a small mean-reversion component. No randomness."""
    base = float(ep_summary["net"])
    days = []
    cur = base
    for d in range(1, 6):
        # Mean-revert toward 0 by 12% per step; add a small "drift" term
        # equal to half of the contradiction intensity so contradictions
        # extend the stress trajectory a bit longer.
        cur = round(cur - cur * 0.12, 4)
        days.append({
            "day": d,
            "projected_net": cur,
            "phase": "relief" if cur > 0.05 else ("stress" if cur < -0.05 else "balanced"),
        })
    return {
        "days": days,
        "starting_net": round(base, 4),
        "ending_net": days[-1]["projected_net"],
        # B-1 class (§17.3): "flat" is a measured claim about a trajectory;
        # absence of signal is not. Emit null rather than defaulting.
        "trend": None if ep_summary.get("no_signal") else (
            "easing" if days[-1]["projected_net"] > base + 0.01
            else "tightening" if days[-1]["projected_net"] < base - 0.01
            else "flat"
        ),
    }


def _layer_7_synthesis(layers: dict) -> dict:
    """Top-line summary fields. Pure functions of earlier layers; no new
    inference."""
    primitives = layers["primitives"]["intensities"]
    domain = layers["domain_mapping"]
    ep = layers["ep_field_summary"]
    sr = layers["stress_relief"]
    forecast = layers["forecast_5day"]
    # Top-1 primitive (alphabetical tiebreak for determinism).
    # B-1 (Line B spec §2): on an all-zero vector the alphabetical tiebreak
    # fabricates a winner ("alignment") — emit null instead.
    no_signal = bool(ep.get("no_signal"))
    if no_signal:
        top_name, top_intensity = None, None
    else:
        top_prim = sorted(primitives.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        top_name, top_intensity = top_prim[0], round(top_prim[1], 4)
    return {
        "top_primitive": top_name,
        "top_primitive_intensity": top_intensity,
        "domain": domain.get("effective_top"),
        "signal": sr["signal"],
        "trend": forecast["trend"],
        "stress_score": round(ep["stress_total"], 4),
        "relief_score": round(ep["relief_total"], 4),
        "no_signal": no_signal,
    }


def _layer_8_qc_self(text: str, layers: dict) -> dict:
    """Inline self-QC — re-extract primitives once, compare to the
    primary extraction. Not the same as the public ``generate_S_ELINS``
    (which takes the full ELINS object); this one is a sanity check
    embedded in the main pipeline."""
    second = _layer_1_primitives(text)
    deltas = {
        k: round(layers["primitives"]["intensities"][k] - second["intensities"][k], 4)
        for k in PRIMITIVE_KEYS
    }
    max_delta = max(abs(v) for v in deltas.values()) if deltas else 0.0
    return {
        "self_check": "stable" if max_delta < 1e-6 else "unstable",
        "max_delta": max_delta,
        "deltas": deltas,
    }


def _layer_9_output(layers: dict) -> dict:
    """Flat output mirror — copies the synthesis fields onto the top
    level of the ELINS object so downstream consumers don't have to
    walk the full record."""
    syn = layers["synthesis"]
    return {
        "scenario_id": layers["input_phase"]["scenario_id"],
        "summary": syn,
        "ts": layers["input_phase"]["ts"],
        "version": "elins.v34.1",
    }


# ---------------------------------------------------------------------------
# Public — generate_ELINS
# ---------------------------------------------------------------------------
def generate_ELINS(
    input_text: str,
    *,
    domain_hint: Optional[str] = None,
    user: Optional[str] = None,
) -> dict:
    """Run the canonical 10-layer ELINS pipeline. Returns a flat dict
    with every layer present + an ``output_object`` mirror. Raises
    ValueError on bad input."""
    text = _normalize(input_text)
    if domain_hint is not None and domain_hint not in DOMAIN_HINTS:
        raise ValueError(
            f"domain_hint must be one of {DOMAIN_HINTS!r}, got {domain_hint!r}"
        )
    layers: dict = {}
    layers["input_phase"] = _layer_0_input(text, domain_hint=domain_hint, user=user)
    layers["primitives"] = _layer_1_primitives(text)
    layers["domain_mapping"] = _layer_2_domains(text, domain_hint)
    layers["ep_field_summary"] = _layer_3_ep_summary(layers["primitives"])
    layers["causal_chain"] = _layer_4_causal_chain(layers["primitives"])
    layers["stress_relief"] = _layer_5_stress_relief(
        layers["ep_field_summary"], layers["causal_chain"],
    )
    layers["forecast_5day"] = _layer_6_forecast_5day(
        layers["ep_field_summary"], layers["stress_relief"],
    )
    # v34 — multi-primitive envelope forecast layer. Pure function of the
    # extracted intensities + causal edges; no model calls.
    layers["forecast_engine"] = forecast_engine.compute_forecast_block(
        layers["primitives"]["intensities"],
        edges=layers["causal_chain"]["edges"],
        days=5,
    )
    layers["synthesis"] = _layer_7_synthesis(layers)
    layers["qc_s_elins"] = _layer_8_qc_self(text, layers)
    layers["output_object"] = _layer_9_output(layers)
    layers["layer_names"] = list(LAYER_NAMES)
    return layers


# ---------------------------------------------------------------------------
# Public — generate_S_ELINS
# ---------------------------------------------------------------------------
def generate_S_ELINS(elins_object: dict) -> dict:
    """Re-extract primitives from the original input, recompute the EP
    field summary, and report pass/fail + per-primitive deltas.

    Pass criterion: max absolute delta across all six primitives is
    below ``S_ELINS_PASS_THRESHOLD`` (default 0.05). Stable + lexical
    extraction means this should always pass for unchanged inputs;
    failures indicate the ELINS object was edited or partially built."""
    if not isinstance(elins_object, dict):
        raise ValueError("elins_object must be a dict")
    input_phase = elins_object.get("input_phase") or {}
    text = input_phase.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("elins_object.input_phase.text is required")

    fresh_primitives = _layer_1_primitives(text)
    fresh_ep = _layer_3_ep_summary(fresh_primitives)

    original_intensities = (
        (elins_object.get("primitives") or {}).get("intensities") or {}
    )
    deltas = {
        k: round(
            float(fresh_primitives["intensities"][k])
            - float(original_intensities.get(k, 0.0)),
            4,
        )
        for k in PRIMITIVE_KEYS
    }
    max_delta = max(abs(v) for v in deltas.values()) if deltas else 0.0
    # Alignment score: 1.0 when deltas are all zero, decays linearly.
    alignment = max(0.0, 1.0 - max_delta * 4.0)
    threshold = S_ELINS_PASS_THRESHOLD
    return {
        "ok": True,
        "scenario_id": (elins_object.get("output_object") or {}).get("scenario_id")
                        or _scenario_id(text),
        "alignment_score": round(alignment, 4),
        "max_delta": round(max_delta, 4),
        "deltas": deltas,
        "fresh_primitives": fresh_primitives["intensities"],
        "fresh_ep_summary": fresh_ep,
        "passed": max_delta < threshold,
        "threshold": threshold,
        "version": "selins.v33.1",
        "ts": time.time(),
    }


S_ELINS_PASS_THRESHOLD: float = 0.05
