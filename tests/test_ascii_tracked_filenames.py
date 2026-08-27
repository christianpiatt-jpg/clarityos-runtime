"""
ASCII tracked-filename guard (runtime_spine).

Origin: 2026-08-26 import discriminator (K3). Cloud Run image import
rejects tar member names whose bytes are not valid UTF-8. A tracked
file with a non-ASCII name can be materialized by a checkout in a
legacy codepage, packed verbatim into the build context, and fail
EVERY deploy with ContainerImageImportFailed while every
registry-side check passes. Case: canon/_definitions/PROMPT_PACK
<em-dash> Clarity OS Dewey Auto.txt, bytes d4 c7 f6 in the image tar.

Gate: any TRACKED path containing a codepoint >127 that is not on
the frozen legacy allowlist fails this test. The allowlist is the 55
pre-existing names observed 2026-08-26, all inside
build-context-excluded trees (Clarity_OS_Operating_System/,
source_docs/). It is FROZEN: do not add entries — rename the file
instead. Removing an entry when its file is renamed or deleted is
correct and encouraged.

git ls-files -z is mandatory: default quotepath octal-escapes
non-ASCII bytes, hiding real names behind backslash text.
NUL-split output carries raw bytes.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Frozen 2026-08-26. 55 legacy names, all in context-excluded trees.
_LEGACY_ALLOWLIST = frozenset({
    'Clarity_OS_Operating_System/Clarity_Library/00_System/Hydronic Compression Index — Library Entry.pdf',
    'Clarity_OS_Operating_System/Clarity_Library/01_Constitution/01_Definitions/CANONICAL INDEX — STACK PILOT ENTER.txt',
    'Clarity_OS_Operating_System/Clarity_Library/01_Constitution/04_Identity/📚 Clarity OS Library Handoff.pdf',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/1. Curvature‑Aware Leadership Model.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/1. Identity‑Field Green’s Function.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/Buddy Box — Full Clarity Tool Bundle.pdf',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/ELINS_Library/2026‑04‑03_0930CST_IDENTITY‑RAMP_ELINS.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/ELINS_Library/CST0930_IST0700_EDT2130_IDENTITY‑RAMP_ELINS.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/ELINS_Library/ELINS_News/2026-04-08-Elon Musk’s Starship Hea.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/ELINS_Library/ELINS_News/2026-04-08-wsj-The U.S. Navy’s New.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/ELINS_Library/ELINS_News/2026‑03‑23_ELINS_AfricaBasin_Consolidated_Full.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/ELINS_Library/ELINS_News/2026‑03‑23_ELINS_China_Basin_FullFusion_Caixin.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/ELINS_Library/ELINS_News/2026‑03‑23_ELINS_PanNikkei_AsiaBasin_FullFusion.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/ELINS_Library/ELINS_News/2026‑03‑23_ELINS_USUrbanCorridor_FullFusion.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/ELINS_Library/ELINS_News/2026‑03‑23_FT_Markets_Corridor_ELINS_Summary.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/ELINS_Library/ELINS_Objects/2026_03_23_Asia‑Centered ELINS — AR → ZH → EN.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/ELINS_Library/ELINS_Objects/2026_03_30_003.7‑ELINS.GLOBAL‑SYSTEMS‑2026.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/ELINS_Library/ELINS_Objects/2026‑04‑03_0930CST_IDENTITY‑RAMP_ELINSPLUS.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/ELINS_Library/ELINS_Objects/CST0930_IST0700_EDT2130_IDENTITY‑RAMP_ELINSPLUS.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/Here is Layer 3, one level deeper —.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/Here we go — Layer 2, one level dee.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/Here we go — Layer 4, the final flo.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/Narrative_Architecture/2026‑03‑24_Architect_Mode_Signal.tx.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/Narrative_Architecture/Here we go — Layer 4, the final flo.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/Narrative_Architecture/Hydronic Compression Index — Library Entry.pdf',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/Narrative_Architecture/Let’s deepen the couplings — for re.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/Narrative_Architecture/Summary (Dewey 003.74‑CR).txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/Narrative_Architecture/The_Predator–Civilization_Table_Explained.pdf',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/TITLE Stack Pilot — Enterprise Laye.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/🟦 1. Identity‑Field Fiber Bundle (.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/🟦 1. Planetary Curvature Command‑a.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/🟦 1. Planetary Curvature Conservat.txt',
    'Clarity_OS_Operating_System/Clarity_Library/02_Subsystems/🟦 1. Planetary curvature stack int.txt',
    'Clarity_OS_Operating_System/Clarity_Library/03_Operator Notes/# 🏛️ THE CLARITYOS LIBRARY — WALK‑.txt',
    'Clarity_OS_Operating_System/Clarity_Library/03_Operator Notes/2026‑03‑24_Architect_Mode_Signal.tx.txt',
    'Clarity_OS_Operating_System/Clarity_Library/03_Operator Notes/Here we go — Layer 4, the final flo.txt',
    'Clarity_OS_Operating_System/Clarity_Library/03_Operator Notes/Let’s deepen the couplings — for re.txt',
    'Clarity_OS_Operating_System/Clarity_Library/03_Operator Notes/Summary (Dewey 003.74‑CR).txt',
    'Clarity_OS_Operating_System/Clarity_Library/03_Operator Notes/📚 Clarity OS Library Handoff 160309.pdf',
    'Clarity_OS_Operating_System/Clarity_Library/04_Analytics/2026‑04‑02_2123EDT_CLARITY_RUNTIME_DEPLOYMENT.txt',
    'Clarity_OS_Operating_System/Clarity_Library/04_Analytics/2026‑04‑02_2130EDT_IDENTITY‑RAMP_ARCHIVE.txt',
    'Clarity_OS_Operating_System/Clarity_Library/04_Analytics/2026‑04‑02_2138EDT_MARKET‑INTEGRATION_ARCHIVE.txt',
    'Clarity_OS_Operating_System/Clarity_Library/04_Analytics/2026‑04‑02_2142EDT_SUMMARY_THREAD_RECORD.txt',
    'Clarity_OS_Operating_System/Clarity_Library/04_Analytics/Global predator‑geometry_2026_04_07.txt',
    'Clarity_OS_Operating_System/Clarity_Library/04_Analytics/Predator-Civ Table_Dewey‑tagged_2026_04_07.txt',
    'Clarity_OS_Operating_System/Clarity_Library/04_Analytics/VA Case — Disclosure Event, Multi‑Channel Drift, and Administrative Outcome.txt',
    'Clarity_OS_Operating_System/GALILEO/📚 Clarity OS Library Handoff.docx',
    'Clarity_OS_Operating_System/META‑EXECUTIVE LAYER.md',
    'source_docs/copilot_tools_2026-08-03/# 🎯 Plain Language Explanation_Gohard.txt',
    'source_docs/copilot_tools_2026-08-03/# 🗺️ DYNAMIC PRESSURE MAP INTEGRAT.txt',
    'source_docs/copilot_tools_2026-08-03/### Universal Primitive–Geometry–Te.txt',
    'source_docs/copilot_tools_2026-08-03/Christian — yes..txt',
    'source_docs/copilot_tools_2026-08-03/Recon 2 · Configurat.txt',
    'source_docs/floating_geometry_2026-08-04/# 🗺️ DYNAMIC PRESSURE MAP INTEGRAT.txt',
    'source_docs/floating_geometry_2026-08-04/### Universal Primitive–Geometry–Te.txt',
})


def _tracked_paths() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, check=True
    ).stdout
    return [n.decode("utf-8") for n in out.split(bytes([0])) if n]


def test_tracked_filenames_are_ascii_or_grandfathered():
    offenders = [
        n
        for n in _tracked_paths()
        if any(ord(c) > 127 for c in n) and n not in _LEGACY_ALLOWLIST
    ]
    assert not offenders, (
        "non-ASCII tracked filename(s) outside the frozen legacy allowlist "
        "(rename to ASCII — Cloud Run import rejects non-UTF-8 tar names): "
        + chr(10).join("  " + repr(n) for n in offenders)
    )


def test_allowlist_entries_still_exist():
    """Entries whose files are gone are dead weight — prune them in the
    same commit that renames/removes the file."""
    tracked = set(_tracked_paths())
    stale = sorted(_LEGACY_ALLOWLIST - tracked)
    assert not stale, (
        "allowlist entries whose files are gone (remove these lines): "
        + chr(10).join("  " + repr(n) for n in stale)
    )
