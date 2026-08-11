"""Smoke verification — Line B lexicon correctness (spec
specs/SPEC_LINE_B_lexicon_v1_2026-08-10_COW1.md §8), pin ec9cd8f.

Mirrors move-1's verify script. Run from the repo root:

    python analysis/verify_line_b_lexicon_2026-08-10.py

Commit 1 asserts (B-3 word boundaries + B-4 negation suppression):
  * workforce / Cyber Forces / arguably / bondholder score 0
  * "no pressure" scores 0 (suppressed, not inverted)
  * "de-escalation" scores 0 (hyphenated negator prefix)
  * "escalating" still matches escalat*
Commit 2 asserts (B-1 null emits null) are appended with that commit.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ELINS import standard_elins as se  # noqa: E402


def _intensities(text: str) -> dict:
    return se._layer_1_primitives(text)["intensities"]


def check(name: str, cond: bool) -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")
    if not cond:
        raise SystemExit(f"SMOKE FAIL: {name}")


print("Line B commit 1 — B-3 word boundaries + B-4 negation window")

i = _intensities("The workforce discussed Cyber Forces and arguably the bondholder smiled.")
check("workforce  -> pressure 0.0", i["pressure"] == 0.0)
check("Cyber Forces -> pressure 0.0", i["pressure"] == 0.0)
check("arguably   -> tension 0.0", i["tension"] == 0.0)
check("bondholder -> trust 0.0", i["trust"] == 0.0)

i = _intensities("There is no pressure in the housing data.")
check("'no pressure' suppressed -> pressure 0.0", i["pressure"] == 0.0)

i = _intensities("The de-escalation continued through the week.")
check("'de-escalation' suppressed -> pressure 0.0", i["pressure"] == 0.0)

i = _intensities("Tension is escalating.")
check("whole-word tension still matches", i["tension"] > 0.0)
check("prefix escalat* still matches 'escalating'", i["pressure"] > 0.0)

i = _intensities("There is no trust between them.")
check("suppression is NOT inversion -> all six 0.0", all(v == 0.0 for v in i.values()))

print("SMOKE OK — commit 1 asserts hold")

print("Line B commit 2 — B-1 null emits null (asserts land with that commit)")
