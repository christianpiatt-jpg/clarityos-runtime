"""
#307 E3 -- the twelve-window pin.

WHAT THIS PINS. The ELINS counting layer (ELINS/standard_elins
_layer_1_primitives -> _layer_3_ep_summary -> _layer_4_causal_chain) over
the twelve fixed windows of CT-1's litigation record, exactly as COW-1's
recon of 2026-09-16 tabulated them (table 1: raw scores per stress
primitive, the signed net, the edge count). Windows 01 / 03 / 07 / 08
score zero on every primitive -- the four zeros are pinned first, so a
lexicon change is MEASURED against the document that started the case and
the agency's two dispositive filings.

THE RECORD NEVER ENTERS THE TREE. It lives OUTSIDE the repository
(Launch GalileOnline/LIT_RECORD_twelve_windows_2026-09-16.md, or the path in
CLARITYOS_LIT_RECORD_PATH), is read at test time only, and no assertion
message, log line or fixture carries a character of it: only counts. When
the file is absent (CI has no copy) every test here SKIPS with the reason
named.
"""
from __future__ import annotations

import os
import re

import pytest

from ELINS import standard_elins as se

# The record's place OUTSIDE the tree: <home>/ClarityOS_Library/<relative>,
# or wherever CLARITYOS_LIT_RECORD_PATH points. No account name in the tree.
RELATIVE_PATH = os.path.join(
    "ClarityOS_Library", "Launch GalileOnline", "LIT_RECORD_twelve_windows_2026-09-16.md",
)
DEFAULT_PATH = os.path.join(os.path.expanduser("~"), RELATIVE_PATH)
_HEADER_RE = re.compile(r"^## RUN (\d{2}) ")

# COW-1 recon table 1 (RECON_lexicon_scan_lit_record_2026-09-16 §1):
# window -> (pressure, tension, drift, contradiction, net, edges). The four
# primitive columns are Layer-1 RAW SCORES (lexicon weights summed); net is
# Layer 3's signed value over the /4.0 intensities; edges is Layer 4's count.
TABLE_1 = {
    "01": (0.0, 0.0, 0.0, 0.0,  0.000, 0),
    "02": (0.0, 0.3, 0.0, 0.1, -0.100, 0),
    "03": (0.0, 0.0, 0.0, 0.0,  0.000, 0),
    "04": (0.0, 1.2, 0.0, 0.0, -0.300, 0),
    "05": (0.0, 0.3, 0.0, 0.0, -0.075, 0),
    "06": (0.3, 0.0, 0.0, 0.0, -0.075, 0),
    "07": (0.0, 0.0, 0.0, 0.0,  0.000, 0),
    "08": (0.0, 0.0, 0.0, 0.0,  0.000, 0),
    "09": (0.0, 0.6, 0.0, 0.0, -0.150, 0),
    "10": (0.0, 0.6, 0.0, 0.0, -0.150, 0),
    "11": (0.0, 0.6, 0.0, 0.1, -0.175, 0),
    "12": (0.4, 1.2, 0.0, 0.4, -0.500, 3),
}
ALL_ZERO = ("01", "03", "07", "08")


def _record_path() -> str:
    return os.environ.get("CLARITYOS_LIT_RECORD_PATH") or DEFAULT_PATH


def _windows() -> dict:
    """{'01': text, ...} -- the text under each header, read at test time.
    Skips, with the reason, when the record is not on this machine."""
    path = _record_path()
    if not os.path.isfile(path):
        pytest.skip(
            "litigation record not present (<home>/%s, or CLARITYOS_LIT_RECORD_PATH); "
            "it lives outside the tree and CI has no copy -- the twelve-window pin "
            "cannot run here" % RELATIVE_PATH
        )
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    out: dict = {}
    current = None
    buf: list = []
    for line in lines:
        m = _HEADER_RE.match(line)
        if m:
            if current is not None:
                out[current] = "\n".join(buf).strip()
            current, buf = m.group(1), []
        elif current is not None:
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf).strip()
    n = len(out)
    if n != 12:
        pytest.fail("expected 12 windows, found %d" % n, pytrace=False)   # counts only, never the text
    empty = [k for k in out if not out[k]]
    if empty:
        pytest.fail("empty windows: %s" % empty, pytrace=False)
    return out


def _count(text: str) -> tuple:
    prim = se._layer_1_primitives(text)
    ep = se._layer_3_ep_summary(prim)
    causal = se._layer_4_causal_chain(prim)
    raw = prim["raw_scores"]
    return (
        round(raw["pressure"], 4), round(raw["tension"], 4),
        round(raw["drift"], 4), round(raw["contradiction"], 4),
        round(ep["net"], 4), int(causal["edge_count"]),
    )


@pytest.fixture(scope="module")
def windows():
    return _windows()


@pytest.mark.parametrize("w", ALL_ZERO)
def test_the_four_zeros_first_no_primitive_fires_on_windows_01_03_07_08(windows, w):
    prim = se._layer_1_primitives(windows[w])
    assert all(v == 0.0 for v in prim["raw_scores"].values()), (
        "window %s: a primitive fired (raw scores %s)" % (w, prim["raw_scores"])
    )
    assert se._layer_3_ep_summary(prim)["no_signal"] is True


@pytest.mark.parametrize("w", sorted(TABLE_1))
def test_table_1_raw_scores_net_and_edges(windows, w):
    got = _count(windows[w])
    assert got == TABLE_1[w], "window %s: counted %s, table 1 says %s" % (w, got, TABLE_1[w])


def test_trust_and_alignment_are_retired_on_every_window(windows):
    # B-2: the two comparison lexicons are empty by design; nothing fires.
    for w, text in windows.items():
        raw = se._layer_1_primitives(text)["raw_scores"]
        assert raw["trust"] == 0.0 and raw["alignment"] == 0.0, w


def test_only_window_12_opens_an_edge(windows):
    edges = {w: _count(t)[5] for w, t in windows.items()}
    assert [w for w, n in edges.items() if n > 0] == ["12"]
    assert edges["12"] == 3
