"""
canon.py — Dewey-canon loader. Pattern-setting module (COW-1 envelope
2026-08-24): every canon-consuming module after this one follows the
shape written here, so failure behaviour matters more than features.

Reads the canon ONCE at import from the shipped canon/ tree
(/app/canon/ in the container; override with CLARITYOS_CANON_DIR for
local/dev/test). NO I/O per request, NO network, NO model call.
Deterministic: same files, same output, every time.

FAIL LOUD, by design:
  - canon dir missing            -> CanonError at import
  - a .md entry that won't parse -> CanonError at import (file:line
                                    in the message)
  - get() on a COLLIDED number   -> CanonCollisionError naming every
                                    candidate path. CT-1 has NOT ruled
                                    on the four known collisions, so
                                    the loader refuses to silently
                                    pick one. (get() returns None only
                                    when the number is absent
                                    entirely.)
A canon loader that quietly returns nothing is the eighth
indistinguishable zero. Nothing here returns a silent default.

The files on disk stay byte-identical to Clarity_Library. The "\\#",
"\\-\\", "\\[", "\\_" escapes are a paste artifact and are stripped
at READ time only.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional, TypedDict


class CanonError(RuntimeError):
    """Canon's own failure type — never swallowed, never defaulted."""


class CanonCollisionError(CanonError):
    """Raised by get() when a Dewey number has more than one entry.

    Carries ``paths``: every file claiming the number, so the caller
    can surface the collision instead of guessing."""

    def __init__(self, number: str, paths: list[str]):
        self.number = number
        self.paths = paths
        super().__init__(
            f"canon collision at {number}: {len(paths)} entries — "
            + ", ".join(paths)
        )


class Xref(TypedDict):
    label: str
    target: str


class CanonEntry(TypedDict):
    number: str            # Dewey number as declared in the file ("200")
    title: str
    summary: str
    concepts: list[str]
    body: str
    xrefs: list[Xref]
    path: str              # repo-relative source path
    empty: bool            # True for the known 0-byte twin (430)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_CANON_DIR = Path(os.environ.get("CLARITYOS_CANON_DIR", "/app/canon"))

# Band directories are three-digit prefixes; _definitions and any
# non-.md payload (2 PDFs, 1 diagram .txt.txt, 2 _definitions .txt)
# are NOT entries — they are recorded in SKIPPED_FILES so the skip is
# a fact on record, not silence.
_BAND_DIR_RE = re.compile(r"^(\d)00_")


# ---------------------------------------------------------------------------
# Escape stripping (read-time only; files on disk untouched)
# ---------------------------------------------------------------------------
_ESCAPED_CHARS = "#*[]_-+.`"


def _unescape(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text) and text[i + 1] in _ESCAPED_CHARS:
            out.append(text[i + 1])
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# Entry parsing
# ---------------------------------------------------------------------------
_TITLE_RE = re.compile(r"^(?:[A-Za-z]{1,4})?#\s+(.+?)\s*$")
# ★ The optional ≤4-letter prefix tolerance exists for exactly ONE
# measured artifact: 900_Governance_and_Planetary_Mesh/990_Governance_
# Crossrefs.md begins "cc# Governance Cross-References" — a paste
# prefix on an unescaped '#'. Tolerated at read time, recorded here,
# file untouched. Anything larger still fails the title check.
_DEWEY_RE = re.compile(r"^##\s+Dewey:\s*(\S+)\s*$")
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^-\s+(.+?)\s*$")
_XREF_RE = re.compile(r"^\[(.+?)\]\((.+?)\)\s*$")
_FILENAME_NUM_RE = re.compile(r"^(\d{3})_")


def _parse_entry(path: Path, rel: str) -> CanonEntry:
    raw = path.read_text(encoding="utf-8")

    # The known 0-byte twin (400_Basins_and_Language/430_Langbridg_
    # Core.md). An empty file is a recorded STATE, not a parse
    # failure — it carries its filename number and empty=True so the
    # collision with its 804-byte sibling stays visible.
    if not raw.strip():
        m = _FILENAME_NUM_RE.match(path.name)
        if not m:
            raise CanonError(f"canon: empty file with no number: {rel}")
        return {
            "number": m.group(1), "title": path.stem, "summary": "",
            "concepts": [], "body": "", "xrefs": [],
            "path": rel, "empty": True,
        }

    text = _unescape(raw)
    lines = text.splitlines()

    title: Optional[str] = None
    number: Optional[str] = None
    sections: dict[str, list[str]] = {}
    current: Optional[str] = None

    for lineno, line in enumerate(lines, 1):
        s = line.strip()
        if not s:
            continue
        if title is None:
            tm = _TITLE_RE.match(s)
            if tm:
                title = tm.group(1)
                continue
            raise CanonError(
                f"canon: {rel}:{lineno} — first content line is not a "
                f"'# Title': {s[:60]!r}"
            )
        dm = _DEWEY_RE.match(s)
        if dm:
            number = dm.group(1)
            continue
        sm = _SECTION_RE.match(s)
        if sm:
            current = sm.group(1).strip().lower()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(s)

    if number is None:
        raise CanonError(f"canon: {rel} — no '## Dewey: NNN' line found")

    # Corpus shape, measured 2026-08-24 (85 .md):
    #   82 files — Summary / Core Concepts / Body / Cross-References
    #    1 file  — 900.C constitution: Preamble + Articles + Closing
    #    1 file  — 900.M notes: Overview / Required Integrations / Status
    #    1 file  — 0-byte (handled above)
    # Section content is captured generically IN ORDER; the canonical
    # fields are extracted when their sections exist, derived when not.
    ordered_sections = [(k, v) for k, v in sections.items()]

    def _section(*names: str) -> list[str]:
        for n in names:
            if n in sections:
                return sections[n]
        return []

    def _bullets(lines: list[str]) -> list[str]:
        out = []
        for line in lines:
            bm = _BULLET_RE.match(line)
            if bm:
                out.append(bm.group(1))
            else:
                out.append(line)  # wrapped line — keep, don't drop
        return out

    xrefs: list[Xref] = []
    for line in _bullets(_section("cross-references")):
        xm = _XREF_RE.match(line)
        if xm:
            xrefs.append({"label": xm.group(1), "target": xm.group(2)})
        else:
            xrefs.append({"label": line, "target": ""})

    # summary: canonical Summary, else Preamble, else Overview, else
    # the first content section — named so the derivation is visible.
    summary_lines = _section("summary", "preamble", "overview")
    summary = " ".join(summary_lines).strip()

    # body: canonical Body if present; otherwise every remaining
    # section that wasn't consumed as summary / concepts / xrefs,
    # rendered WITH its header so structure survives.
    consumed = {"summary", "preamble", "overview", "core concepts",
                "cross-references"}
    if "body" in sections:
        body = "\n\n".join(sections["body"]).strip()
    else:
        parts = []
        for name, lines in ordered_sections:
            if name in consumed or not lines:
                continue
            parts.append("## " + name + "\n" + "\n".join(lines))
        body = "\n\n".join(parts).strip()

    if not summary and not body:
        raise CanonError(
            f"canon: {rel} — parsed but no content sections; "
            f"refusing to emit a hollow entry"
        )

    return {
        "number": number,
        "title": title or path.stem,
        "summary": summary,
        "concepts": _bullets(_section("core concepts")),
        "body": body,
        "xrefs": xrefs,
        "path": rel,
        "empty": False,
    }


# ---------------------------------------------------------------------------
# Load once, at import. Anything wrong -> raise NOW, not per-request.
# ---------------------------------------------------------------------------
def _load() -> tuple[dict[str, list[CanonEntry]], list[str]]:
    if not _CANON_DIR.is_dir():
        raise CanonError(
            f"canon: directory {_CANON_DIR} absent — the canon did not "
            f"ship with this build (expected Dockerfile COPY canon/ "
            f"/app/canon/)"
        )

    by_number: dict[str, list[CanonEntry]] = {}
    skipped: list[str] = []

    for child in sorted(_CANON_DIR.iterdir()):
        if not child.is_dir() or not _BAND_DIR_RE.match(child.name):
            for f in sorted(child.rglob("*")):
                if f.is_file():
                    skipped.append(str(f.relative_to(_CANON_DIR)))
            continue
        for f in sorted(child.glob("*.md")):
            rel = str(f.relative_to(_CANON_DIR))
            entry = _parse_entry(f, rel)
            by_number.setdefault(entry["number"], []).append(entry)
        for f in sorted(child.iterdir()):
            if f.is_file() and f.suffix != ".md":
                skipped.append(str(f.relative_to(_CANON_DIR)))

    if not by_number:
        raise CanonError(
            f"canon: {_CANON_DIR} holds no parseable entries — "
            f"refusing to run with an empty canon"
        )

    # Deterministic order everywhere: entries within a number sorted
    # by path; numbers sorted lexicographically (Dewey numbers here
    # are zero-padded three-digit strings, so lexical == numeric).
    for entries in by_number.values():
        entries.sort(key=lambda e: e["path"])
    return dict(sorted(by_number.items())), skipped


_ENTRIES, SKIPPED_FILES = _load()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get(dewey: str) -> Optional[CanonEntry]:
    """The entry for a Dewey number ("200", "430", "900").

    None  — the number has no entry at all.
    raise CanonCollisionError — more than one entry claims it.
    A collision is never resolved by silence."""
    entries = _ENTRIES.get(str(dewey))
    if not entries:
        return None
    if len(entries) > 1:
        raise CanonCollisionError(
            str(dewey), [e["path"] for e in entries]
        )
    return entries[0]


def band(n: int) -> list[CanonEntry]:
    """All entries in the 000/100/.../900 band, collision or not —
    band() is the enumeration surface, so it shows EVERYTHING,
    including both 430s and all three 900s."""
    lo = (n // 100) * 100
    out: list[CanonEntry] = []
    for number, entries in _ENTRIES.items():
        try:
            if (int(number) // 100) * 100 == lo:
                out.extend(entries)
        except ValueError:
            continue  # non-numeric Dewey labels stay get()-only
    return sorted(out, key=lambda e: (e["number"], e["path"]))


def all() -> list[CanonEntry]:  # noqa: A001 — API name per envelope
    """Every entry, number-sorted, collisions included."""
    return [e for entries in _ENTRIES.values() for e in entries]


def entry_count() -> int:
    """Total parsed entries (collisions counted individually)."""
    return sum(len(v) for v in _ENTRIES.values())


def collisions() -> dict[str, list[str]]:
    """Every Dewey number claimed by more than one file, mapped to
    the claiming paths. The four known collisions live here in the
    open until CT-1 rules."""
    return {
        number: [e["path"] for e in entries]
        for number, entries in _ENTRIES.items()
        if len(entries) > 1
    }
