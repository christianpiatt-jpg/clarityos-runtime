"""Line B falsifier harness — corpus re-run at current pin.

Spec: specs/SPEC_LINE_B_lexicon_v1_2026-08-10_COW1.md §6/§8.
Splitter per §6: <h1-6> boundaries; >=3 headings = newsletter.
Scorer: ELINS.standard_elins.generate_ELINS at the CURRENT repo pin.

BEFORE-SIDE (COW-1, measured, on record):
  8 newsletters / 6 publishers / 60 segments / Jul 4-Aug 5 2026
  57/60 balanced - 33/60 exact zero - median intensity_mean 0.0000

FALSIFIER: if segment-level output is materially unchanged vs before-side,
the defect was never in the lexicon and the spec is wrong.

NOTE: this corpus (13 .eml, OneDrive/Copilot/ELINS) is not proven to be
COW-1's 60-segment set. Composition is reported, not assumed.

CORPUS DEPENDENCY: this harness reads corpus/news_sum_eml/*.eml, which is
third-party newsletter content and is deliberately NOT tracked in the repo.
A clean clone will find CORPUS empty and report 0 files; that is expected,
not a failure. Supply the corpus out-of-band to reproduce any measurement
taken with this harness.

SPLITTER: HEADING_RE carries a capture group so re.split RETAINS the <hN>
delimiters. segments_of() at :58-70 pairs parts[i]+parts[i+1] on the shape
[pre, tag, body, tag, body, ...]. Without the group re.split drops the
delimiters and the same loop pairs two ADJACENT BODIES, halving the segment
count and discarding every heading. Do not remove the group.
"""
from __future__ import annotations

import email
import re
import statistics
import sys
from email import policy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ELINS import standard_elins as se  # noqa: E402

CORPUS = Path(__file__).resolve().parent.parent / "corpus" / "news_sum_eml"
HEADING_RE = re.compile(r"(<h[1-6][^>]*>)", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def html_of(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    return part.get_content()
                except Exception:
                    payload = part.get_payload(decode=True) or b""
                    return payload.decode(part.get_content_charset() or "utf-8", "replace")
    payload = msg.get_payload(decode=True)
    if payload:
        return payload.decode(msg.get_content_charset() or "utf-8", "replace")
    return msg.get_payload() or ""


def text_of(html_fragment: str) -> str:
    t = TAG_RE.sub(" ", html_fragment)
    t = (t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
          .replace("&nbsp;", " ").replace("&#39;", "'").replace("&rsquo;", "'")
          .replace("&ldquo;", '"').replace("&rdquo;", '"').replace("&quot;", '"'))
    return WS_RE.sub(" ", t).strip()


def segments_of(html: str) -> list[str]:
    """Split on h1-6 boundaries; each segment = heading + body to next heading."""
    parts = HEADING_RE.split(html)
    # parts: [pre, tag, body, tag, body, ...]
    segs: list[str] = []
    i = 1
    while i < len(parts) - 1:
        heading_html = parts[i] + parts[i + 1]
        t = text_of(heading_html)
        if t:
            segs.append(t)
        i += 2
    return segs


def main() -> None:
    rows = []
    for path in sorted(CORPUS.glob("*.eml")):
        msg = email.message_from_bytes(path.read_bytes(), policy=policy.default)
        html = html_of(msg)
        segs = segments_of(html)
        is_newsletter = len(segs) >= 3  # spec §6 classifier
        rows.append((path, msg.get("Subject", "?"), msg.get("Date", "?"), segs, is_newsletter))

    print(f"corpus: {len(rows)} .eml files")
    total = scored = no_sig = balanced = stress = relief = 0
    intensities: list[float] = []
    zero_seg_examples: list[str] = []
    for path, subj, date, segs, is_nl in rows:
        print(f"\n== {path.name}\n   date: {date}  segments: {len(segs)}  newsletter(>=3 h): {is_nl}")
        if not is_nl:
            print("   (skipped — below newsletter classifier)")
            continue
        for s in segs:
            total += 1
            try:
                obj = se.generate_ELINS(s)
            except ValueError:
                continue
            scored += 1
            syn = obj["synthesis"]
            im = obj["ep_field_summary"]["intensity_mean"]
            intensities.append(im)
            if syn["no_signal"]:
                no_sig += 1
                if len(zero_seg_examples) < 5:
                    zero_seg_examples.append(s[:70])
            elif syn["signal"] == "balanced":
                balanced += 1
            elif syn["signal"] == "stress_dominant":
                stress += 1
            elif syn["signal"] == "relief_dominant":
                relief += 1

    print("\n==== AGGREGATE (newsletter segments only) ====")
    print(f"segments total/scored : {total}/{scored}")
    print(f"no_signal (null path) : {no_sig}")
    print(f"balanced (measured)   : {balanced}")
    print(f"stress_dominant       : {stress}")
    print(f"relief_dominant       : {relief}")
    if intensities:
        print(f"median intensity_mean : {statistics.median(intensities):.4f}")
        nz = [v for v in intensities if v > 0]
        if nz:
            print(f"median non-zero       : {statistics.median(nz):.4f}  (n={len(nz)})")
    if zero_seg_examples:
        print("\nsample no_signal segments:")
        for e in zero_seg_examples:
            print(f"  - {e}")

    print("\n==== BEFORE-SIDE (COW-1 record) ====")
    print("60 segments - 57 balanced - 33 exact zero - median int 0.0000")
    print("FALSIFIER: materially unchanged output => spec wrong")


if __name__ == "__main__":
    main()
