#!/usr/bin/env python3
"""
prompt_interrogator.py — K3 witness instrument · 2026-08-04

Interrogates an LLM prompt contract. For every field the contract demands,
it reports the EDGES (where the contract can manufacture invention) and the
SUBSTRATE REQUIREMENT (what evidence must exist for an honest fill).

Design basis (all session-verified):
  - D6 / null-result principle: a required field with no null member is a
    forced choice; forced choice manufactures invention (residue audit).
  - Subject declaration: person-subject fields are cold-illegal; they are
    legal only against return-loop history (E/r pairs). Situation-subject
    fields are cold-legal with span citation.
  - Magnitude discipline: magnitude labels require a baseline_ref or they
    are untethered (test 6: intensity: high, no baseline).
  - Strip rule: free-text fields are un-auditable paraphrase surfaces
    unless verbatim-quote discipline or a render-time strip applies.
  - Coherence: cross-field contradictions (e.g. boundary: clear +
    dominant_pattern: boundary_uncertainty) pass through when validation
    is key-presence only (kernel :1757-1766).

Usage:
  python analysis/prompt_interrogator.py [--kernel PATH] [--prompt PATH]

Default: extracts _EMOTIONAL_PHYSICS_PROMPT from intelligence_kernel.py at pin.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Rulebook configuration — the interrogator's judgment layer.
# Everything here is declared, tunable, and printed in the report header so a
# reader can see exactly which rules produced which edge. [designed]
# ---------------------------------------------------------------------------

# Fields whose values are magnitude claims requiring a baseline reference.
MAGNITUDE_FIELDS = {"intensity", "signal_intensity", "risk_of_misread"}

# Null members that make an enum honest.
NULL_MEMBERS = {"unclear", "none", "unknown", "null", "n/a"}

# Subject hints. "person" = about the user's operating state (cold-illegal,
# return-loop-gated). "situation" = about the described situation (cold-legal
# with span citation). Anything unmatched = AMBIGUOUS → interrogation question.
SUBJECT_HINTS = {
    "person": {"intensity", "stability", "gradient_direction"},
    "situation": {"signal_clarity", "signal_intensity", "coherence",
                  "perceived_posture", "trust", "alignment", "boundary",
                  "agency", "distance", "dominant_pattern", "risk_of_misread",
                  "recommended_posture", "message_guidance",
                  "friction_reduction_moves", "risk_if_unchanged", "next_step"},
}

# Cross-field coherence pairs: (field_a, value_a, field_b, value_b) that must
# not co-fire. [designed — seeded from the 08-01 self-contradiction]
COHERENCE_PAIRS = [
    ("boundary", "clear", "dominant_pattern", "boundary_uncertainty"),
]

# Where validation actually lives, per K3 recon 2026-08-03 [Corr]:
VALIDATION_NOTE = (
    "kernel validates top-level key presence only "
    "(intelligence_kernel.py:1757-1766); subfield values pass through "
    "unvalidated to the panel."
)

ENUM_RE = re.compile(r'^\s*"([a-z_]+)"\s*:\s*"([^"]*\|[^"]*)"')
LIST_START_RE = re.compile(r'^\s*"([a-z_]+)"\s*:\s*\[')
SUBSET_RE = re.compile(r'//\s*subset of:\s*(.+)')
FREETEXT_RE = re.compile(r'^\s*"([a-z_]+)"\s*:\s*"([^"|]+)"\s*,?\s*$')
LAYER_RE = re.compile(r"^LAYER\s+\d+\s+—\s+([a-z_]+)")


def extract_kernel_prompt(kernel_path: Path) -> str:
    src = kernel_path.read_text(encoding="utf-8")
    m = re.search(r'_EMOTIONAL_PHYSICS_PROMPT:\s*str\s*=\s*"""(.*?)"""',
                  src, re.DOTALL)
    if not m:
        raise SystemExit("could not extract _EMOTIONAL_PHYSICS_PROMPT")
    return m.group(1)


def parse_fields(prompt: str) -> list[dict]:
    """Mechanical parse of the contract text into field records."""
    fields: list[dict] = []
    layer = None
    pending_list: dict | None = None
    for line in prompt.splitlines():
        lm = LAYER_RE.match(line)
        if lm:
            layer = lm.group(1)
            continue
        em = ENUM_RE.match(line)
        if em:
            members = [x.strip() for x in em.group(2).split("|")]
            fields.append({"layer": layer, "name": em.group(1),
                           "kind": "enum", "members": members,
                           "guard": False})
            continue
        sm = LIST_START_RE.match(line)
        if sm:
            pending_list = {"layer": layer, "name": sm.group(1),
                            "kind": "list", "members": [],
                            "guard": False}
            fields.append(pending_list)
            continue
        if pending_list is not None:
            sub = SUBSET_RE.search(line)
            if sub:
                toks = re.findall(r'"([a-z_]+)"', sub.group(1))
                pending_list["members"].extend(toks)
            if "do not force-fit" in line:
                pending_list["guard"] = True
            if line.strip() == "],":
                pending_list = None
            continue
        fm = FREETEXT_RE.match(line)
        if fm and not ENUM_RE.match(line):
            fields.append({"layer": layer, "name": fm.group(1),
                           "kind": "freetext", "members": [],
                           "guard": False})
    return fields


def subject_of(name: str) -> str:
    for subj, names in SUBJECT_HINTS.items():
        if name in names:
            return subj
    return "AMBIGUOUS"


def interrogate(fields: list[dict]) -> list[dict]:
    """Apply the rulebook. Returns one verdict record per field."""
    out = []
    for f in fields:
        edges: list[str] = []
        reqs: list[str] = []
        questions: list[str] = []
        subj = subject_of(f["name"])

        if f["kind"] == "enum":
            if not (set(f["members"]) & NULL_MEMBERS):
                edges.append("FORCED-CHOICE: enum has no null member — "
                             "abstention is converted into a claim")
                reqs.append("add a null member, or require span citation "
                            "per emission")
        if f["name"] in MAGNITUDE_FIELDS:
            edges.append("UNTETHERED-MAGNITUDE: magnitude label with no "
                         "baseline_ref in contract")
            reqs.append("baseline_ref required at render, pre-serialize")
        if f["kind"] == "list" and not f["guard"]:
            edges.append("UNGUARDED-SUBSET: list may be force-filled; no "
                         "'do not force-fit' guard")
            reqs.append("add force-fit guard, or declare empty list legal")
        if f["kind"] == "freetext":
            edges.append("PARAPHRASE-SURFACE: free text is un-auditable "
                         "without verbatim-quote discipline")
            reqs.append("verbatim quotes only, or render-time strip-check")
        if subj == "person":
            edges.append("COLD-PERSON-READ: person-subject field filled "
                         "from situation text — false-mirror doorway")
            reqs.append("gate on return-loop history (E/r pairs); until "
                        "then render per-field null")
        if subj == "AMBIGUOUS":
            questions.append(f"declare subject for '{f['name']}' — "
                             f"situation or person?")
            edges.append("SUBJECT-UNDECLARED")

        for a, va, b, vb in COHERENCE_PAIRS:
            if f["name"] == a and va in f["members"]:
                reqs.append(f"cross-field check: '{a}:{va}' must not "
                            f"co-fire with '{b}:{vb}'")

        verdict = ("COLD-ILLEGAL" if subj == "person"
                   else "EDGE" if edges and subj != "AMBIGUOUS"
                   else "INTERROGATE" if subj == "AMBIGUOUS"
                   else "OK")
        out.append({**f, "subject": subj, "edges": edges,
                    "requirements": reqs, "questions": questions,
                    "verdict": verdict})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kernel", default="intelligence_kernel.py")
    ap.add_argument("--prompt", default=None,
                    help="raw prompt text file (skips kernel extraction)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.prompt:
        prompt = Path(args.prompt).read_text(encoding="utf-8")
        source = args.prompt
    else:
        prompt = extract_kernel_prompt(Path(args.kernel))
        source = f"{args.kernel}::_EMOTIONAL_PHYSICS_PROMPT (at pin)"

    fields = parse_fields(prompt)
    verdicts = interrogate(fields)

    if args.json:
        print(json.dumps({"source": source, "validation": VALIDATION_NOTE,
                          "fields": verdicts}, indent=2))
        return

    print(f"INTERROGATION — {source}")
    print(f"Validation at enforcement point: {VALIDATION_NOTE}")
    print(f"Rulebook: magnitude={sorted(MAGNITUDE_FIELDS)} · "
          f"null={sorted(NULL_MEMBERS)} · coherence_pairs={len(COHERENCE_PAIRS)}")
    print("=" * 78)
    n_edge = n_cold = n_inter = 0
    for v in verdicts:
        tag = v["verdict"]
        n_edge += tag == "EDGE"
        n_cold += tag == "COLD-ILLEGAL"
        n_inter += tag == "INTERROGATE"
        print(f"\n[{tag}] {v['layer']}.{v['name']} "
              f"({v['kind']}, subject={v['subject']})")
        if v["kind"] == "enum":
            print(f"  members: {' | '.join(v['members'])}")
        for e in v["edges"]:
            print(f"  EDGE: {e}")
        for r in v["requirements"]:
            print(f"  REQ : {r}")
        for q in v["questions"]:
            print(f"  ASK : {q}")
    print("\n" + "=" * 78)
    print(f"FIELDS {len(verdicts)} · EDGE {n_edge} · "
          f"COLD-ILLEGAL {n_cold} · INTERROGATE {n_inter}")


if __name__ == "__main__":
    sys.exit(main())
