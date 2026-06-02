"""
structure_format.py — deterministic structural formatter for #structure (A22).

Pure, side-effect-free Markdown SHAPE normalisation. It is meaning-preserving:
it never reclassifies content. In particular it will NOT turn a plain
``"Heading:"`` line or a no-space ``"##text"`` into a heading — both are
commonly literal text (a ``"Status:"`` label, a ``"#climate"`` hashtag, a
``"#cite"`` token), and promoting them would alter meaning, which #structure
must not do (it "enforces shape only").

Applied OUTSIDE fenced code blocks:
  * normalise line endings to \n
  * strip trailing whitespace per line
  * collapse runs of 2+ blank lines to a single blank line
  * collapse extra spaces after the leading #'s of an EXISTING ATX heading
    ("##   H" -> "## H") — existing headings only, never created
  * normalise unordered list bullets ("* " / "+ " -> "- "), skipping
    thematic breaks ("* * *", "***")
  * trim leading/trailing blank lines from the whole text

Fenced code blocks (``` or ~~~) are preserved VERBATIM, except the fence
delimiter lines themselves get trailing whitespace trimmed.

Deliberately NOT done (meaning-altering or high corruption risk; deferred):
  * auto-detecting headings from "Heading:" or no-space "##text"
  * auto-fencing indented code
  * table column / pipe alignment

The pass is idempotent: format_output(format_output(x)) == format_output(x).
"""
from __future__ import annotations

import re

_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
# An EXISTING ATX heading: 1–6 #'s, then at least one space, then content.
_ATX_RE = re.compile(r"^(#{1,6})[ \t]+(\S.*)$")
# An unordered bullet: optional indent, * or +, space(s), content.
_BULLET_RE = re.compile(r"^([ \t]*)[*+][ \t]+(\S.*)$")
# A thematic break: 3+ of the same marker (* - _) separated only by spaces.
_THEMATIC_RE = re.compile(r"^[ \t]*([*\-_])([ \t]*\1){2,}[ \t]*$")


def format_output(text: str) -> str:
    if not isinstance(text, str):
        return text

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    out: list[str] = []
    in_fence = False
    blank_run = 0

    for line in lines:
        if _FENCE_RE.match(line):
            # Fence delimiter: toggle state; the delimiter itself is safe to
            # rstrip. Reset the blank-run counter across the boundary.
            out.append(line.rstrip())
            in_fence = not in_fence
            blank_run = 0
            continue

        if in_fence:
            out.append(line)          # preserve code verbatim
            blank_run = 0
            continue

        norm = line.rstrip()          # strip trailing whitespace

        if norm == "":
            blank_run += 1
            if blank_run > 1:
                continue              # collapse: keep at most one blank line
            out.append("")
            continue
        blank_run = 0

        # Existing ATX heading: collapse the post-# whitespace to one space.
        # (Never creates a heading — requires an existing space + content.)
        m = _ATX_RE.match(norm)
        if m:
            out.append(f"{m.group(1)} {m.group(2)}")
            continue

        # Unordered list bullet -> "-", unless the line is a thematic break.
        if not _THEMATIC_RE.match(norm):
            b = _BULLET_RE.match(norm)
            if b:
                out.append(f"{b.group(1)}- {b.group(2)}")
                continue

        out.append(norm)

    # Trim leading/trailing blank lines from the whole text.
    while out and out[0] == "":
        out.pop(0)
    while out and out[-1] == "":
        out.pop()

    return "\n".join(out)
