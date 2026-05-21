"""
elins_timeline_dashboard.py — ELINS Unit 2.

Read-only sibling surface to elins_dashboard. Wraps the Unit 1
Single-Party Fear regression validator into a dashboard-friendly dict
(adds the score-band label) without touching ELINS basin inference,
the existing dashboard module, or the regression module itself.

ROLE
----
This is a presentation layer for the regression validator. It:
    * accepts a Timeline,
    * calls run_single_party_fear_regression,
    * shapes the result into a dict with a human-readable score band.

It does NOT:
    * mutate the timeline,
    * store anything,
    * log,
    * perform I/O,
    * call any ELINS inference modules,
    * import or modify elins_dashboard.py.

PUBLIC API
----------
    get_single_party_fear_regression(timeline) -> dict
"""
from __future__ import annotations

from elins_regression_single_party import (
    SCORE_ACCEPTABLE_FLOOR,
    SCORE_STRONG_FLOOR,
    SCORE_WEAK_FLOOR,
    Timeline,
    run_single_party_fear_regression,
)
from elins_regression_economic_coercion import (
    TimelineEconomic,
    run_economic_coercion_regression,
)
from elins_regression_compare import (
    compare_regressions,
    compare_regressions_batch,
)
from elins_directory_scanner import scan_directory_for_timeline_pairs
from elins_persistence import save_comparison_result


# Locked human-readable labels for the four rubric bands. Adding or
# renaming a label is a deliberate spec change.
_BAND_STRONG: str = "Strong"
_BAND_ACCEPTABLE: str = "Acceptable"
_BAND_WEAK: str = "Weak"
_BAND_FAILS: str = "Fails core logic"


def _score_band(score: int) -> str:
    """Pure mapping from a 0-10 score to a human-readable band label.

    Bands per ELINS Unit 1 work-set:
        9-10 → "Strong"
        7-8  → "Acceptable"
        5-6  → "Weak"
        0-4  → "Fails core logic"
    """
    if score >= SCORE_STRONG_FLOOR:
        return _BAND_STRONG
    if score >= SCORE_ACCEPTABLE_FLOOR:
        return _BAND_ACCEPTABLE
    if score >= SCORE_WEAK_FLOOR:
        return _BAND_WEAK
    return _BAND_FAILS


def analyze_and_store(
    pairs_or_path,
    run_id=None,
    *,
    source=None,
    evidence_dir=None,
) -> dict:
    """Run an analysis and persist the result.

    Args:
        pairs_or_path: either
            * a directory path (str) → routed through analyze_directory
            * a list of (Timeline, TimelineEconomic) tuples → routed
              through compare_regressions_batch_dashboard
        run_id: optional caller-supplied run identifier. Must match
            ``^[A-Za-z0-9_-]+$`` (validated by the persistence layer).
            When omitted, a fresh ``"run_<32-hex-chars>"`` UUID is
            generated.
        source: optional Unit 19 metadata source tag — one of
            "single" / "batch" / "directory". When ``None`` (default),
            inferred from the input shape:
                * directory path (str)              → "directory"
                * list of pairs with len == 1       → "single"
                * list of pairs with len != 1       → "batch"
        evidence_dir: optional Unit 19 metadata evidence-directory
            string. When ``None`` and the input is a directory path,
            defaults to that path. Otherwise stored as ``None``.

    Returns:
        ``{"run_id": str, "result": list[dict]}``.

    Pure modulo file I/O (the underlying scanner reads input files;
    the persistence layer writes one JSON file).

    Raises:
        ValueError if `pairs_or_path` is neither str nor list.
        ValueError if `run_id` is malformed (propagated from
            persistence validation).
        ValueError if `source` is non-None and not one of the allowed
            values (propagated from persistence validation).
        FileNotFoundError if a directory path is invalid (propagated
            from the scanner).
    """
    import uuid

    if isinstance(pairs_or_path, str):
        # Unit 24: validate the caller-supplied directory against the
        # operator-managed allowlist before scanning. Returns the
        # symlink-resolved, normalised absolute path so both the scan
        # and the metadata.evidence_dir field share the same canonical
        # form. Validation failures bubble up as ValueError → 400 at
        # the endpoint layer.
        from elins_evidence_allowlist import validate_evidence_dir
        validated_path = validate_evidence_dir(pairs_or_path)
        result = analyze_directory(validated_path)
        inferred_source = "directory"
        inferred_evidence_dir = validated_path
    elif isinstance(pairs_or_path, list):
        result = compare_regressions_batch_dashboard(pairs_or_path)
        inferred_source = "single" if len(pairs_or_path) == 1 else "batch"
        inferred_evidence_dir = None
    else:
        raise ValueError(
            f"analyze_and_store expected directory path (str) or list of "
            f"pairs, got {type(pairs_or_path).__name__}"
        )

    if run_id is None:
        run_id = "run_" + uuid.uuid4().hex

    final_source = source if source is not None else inferred_source
    final_evidence_dir = (
        evidence_dir if evidence_dir is not None else inferred_evidence_dir
    )

    save_comparison_result(
        run_id, result,
        source=final_source,
        evidence_dir=final_evidence_dir,
    )
    return {"run_id": run_id, "result": result}


def analyze_directory(path: str) -> list:
    """Directory-level evidence pipeline: scan → ingest → batch
    compare → dashboard dicts.

    Args:
        path: directory containing matching ``<stem>_sp.{csv,json}`` and
            ``<stem>_ec.{csv,json}`` files.

    Returns:
        list[dict] — one dashboard dict per complete pair found,
        ordered by stem ascending. Empty list if the directory has no
        complete pairs (or is empty).

    Raises:
        ValueError if `path` is malformed (propagated from scanner).
        FileNotFoundError / NotADirectoryError if the path is invalid.
        ValueError if a file in the directory is malformed
        (propagated from Unit 6 ingestors).

    Pure modulo the file reads done by the scanner. No logging,
    network, LLM, or ELINS basin inference imports.
    """
    pairs = scan_directory_for_timeline_pairs(path)
    return compare_regressions_batch_dashboard(pairs)


def compare_regressions_batch_dashboard(
    pairs: list,
) -> list:
    """Read-only batch wrapper around compare_regressions_batch. Each
    RegressionComparisonResult is shaped into the same dashboard-friendly
    dict (with score/band delta labels) as the single-pair wrapper.

    Args:
        pairs: list of 2-element tuples/lists of
            ``(Timeline, TimelineEconomic)``.

    Returns:
        list[dict] — one dashboard dict per input pair, in input order.

    Pure: no I/O, no logging, no network. Empty input → empty output.
    """
    results = compare_regressions_batch(pairs)
    out: list = []
    # ELINS Unit 11 — iterate pairs alongside results so we can attach
    # the composite pair_id from the source timelines.
    for (sp_tl, ec_tl), cmp in zip(pairs, results):
        delta = cmp.score_delta
        if delta > 0:
            score_label = f"economic coercion +{delta} points"
        elif delta < 0:
            score_label = f"single party fear +{-delta} points"
        else:
            score_label = "tied"

        if cmp.band_delta == "up":
            band_label = (
                f"economic coercion is one or more bands higher "
                f"(now {cmp.economic_coercion_band})"
            )
        elif cmp.band_delta == "down":
            band_label = (
                f"single party fear is one or more bands higher "
                f"(now {cmp.single_party_band})"
            )
        else:
            band_label = f"tied at {cmp.single_party_band}"

        out.append({
            "pair_id":                         f"{sp_tl.timeline_id}::{ec_tl.timeline_id}",
            "single_party_score":              cmp.single_party_score,
            "economic_coercion_score":         cmp.economic_coercion_score,
            "score_delta":                     cmp.score_delta,
            "score_delta_label":               score_label,
            "single_party_band":               cmp.single_party_band,
            "economic_coercion_band":          cmp.economic_coercion_band,
            "band_delta":                      cmp.band_delta,
            "band_delta_label":                band_label,
            "assertions_failed_single_party":  list(cmp.assertions_failed_single_party),
            "assertions_failed_economic":      list(cmp.assertions_failed_economic),
            "scenario_results_single_party":   dict(cmp.scenario_results_single_party),
            "scenario_results_economic":       dict(cmp.scenario_results_economic),
        })
    return out


def compare_regressions_dashboard(
    timeline_single_party: Timeline,
    timeline_economic: TimelineEconomic,
) -> dict:
    """Read-only wrapper around compare_regressions. Adds human-readable
    delta labels to the structured comparison.

    Args:
        timeline_single_party: A Unit 1 Timeline.
        timeline_economic:     A Unit 4 TimelineEconomic.

    Returns:
        A dict with:
            * single_party_score, economic_coercion_score
            * score_delta (int, ec - sp)
            * score_delta_label (str, e.g. "economic coercion +3 points")
            * single_party_band, economic_coercion_band
            * band_delta ("up" / "down" / "same")
            * band_delta_label (str, e.g. "economic coercion is one band higher")
            * assertions_failed_single_party (list[str])
            * assertions_failed_economic (list[str])
            * scenario_results_single_party (dict[str, bool])
            * scenario_results_economic (dict[str, bool])

    Pure: no I/O, no logging, no network. Does not mutate either timeline.
    """
    cmp = compare_regressions(timeline_single_party, timeline_economic)
    delta = cmp.score_delta
    if delta > 0:
        score_label = f"economic coercion +{delta} points"
    elif delta < 0:
        score_label = f"single party fear +{-delta} points"
    else:
        score_label = "tied"

    if cmp.band_delta == "up":
        band_label = (
            f"economic coercion is one or more bands higher "
            f"(now {cmp.economic_coercion_band})"
        )
    elif cmp.band_delta == "down":
        band_label = (
            f"single party fear is one or more bands higher "
            f"(now {cmp.single_party_band})"
        )
    else:
        band_label = f"tied at {cmp.single_party_band}"

    return {
        # ELINS Unit 11 — composite stable id for run-to-run diff.
        "pair_id":                         f"{timeline_single_party.timeline_id}::{timeline_economic.timeline_id}",
        "single_party_score":              cmp.single_party_score,
        "economic_coercion_score":         cmp.economic_coercion_score,
        "score_delta":                     cmp.score_delta,
        "score_delta_label":               score_label,
        "single_party_band":               cmp.single_party_band,
        "economic_coercion_band":          cmp.economic_coercion_band,
        "band_delta":                      cmp.band_delta,
        "band_delta_label":                band_label,
        "assertions_failed_single_party":  list(cmp.assertions_failed_single_party),
        "assertions_failed_economic":      list(cmp.assertions_failed_economic),
        "scenario_results_single_party":   dict(cmp.scenario_results_single_party),
        "scenario_results_economic":       dict(cmp.scenario_results_economic),
    }


def get_economic_coercion_regression(timeline: TimelineEconomic) -> dict:
    """Read-only wrapper around run_economic_coercion_regression.

    Args:
        timeline: A TimelineEconomic (Unit 4 dataclass).

    Returns:
        A dict with:
            * timeline_id, score, score_band
            * structural_consistency_score, timeline_sensitivity_score,
              coercion_mechanism_score, shock_mechanism_score,
              buffer_mechanism_score
            * assertions_passed (list[str])
            * assertions_failed (list[str])
            * scenario_results (dict[str, bool])

    Pure: no I/O, no logging, no network, no LLM. Does not mutate the
    timeline. Score-band labels reuse the Unit 1 / Unit 2 thresholds
    (Strong / Acceptable / Weak / Fails core logic).

    Raises:
        ValueError if `timeline` is not a TimelineEconomic (propagated
        from the validator).
    """
    result = run_economic_coercion_regression(timeline)
    return {
        "timeline_id":                  result.timeline_id,
        "score":                        result.score,
        "score_band":                   _score_band(result.score),
        "structural_consistency_score": result.structural_consistency_score,
        "timeline_sensitivity_score":   result.timeline_sensitivity_score,
        "coercion_mechanism_score":     result.coercion_mechanism_score,
        "shock_mechanism_score":        result.shock_mechanism_score,
        "buffer_mechanism_score":       result.buffer_mechanism_score,
        "assertions_passed":            list(result.assertions_passed),
        "assertions_failed":            list(result.assertions_failed),
        "scenario_results":             dict(result.scenario_results),
    }


def get_single_party_fear_regression(timeline: Timeline) -> dict:
    """Read-only wrapper around run_single_party_fear_regression.

    Args:
        timeline: A Timeline (Unit 1 dataclass).

    Returns:
        A dict with:
            * timeline_id, score, score_band
            * structural_consistency_score, timeline_sensitivity_score,
              fear_mechanism_score, threat_mechanism_score,
              repression_coverage_score
            * assertions_passed (list[str])
            * assertions_failed (list[str])
            * scenario_results (dict[str, bool])

    Pure: no I/O, no logging, no network, no LLM. Does not mutate the
    timeline. Does not store the result anywhere.

    Raises:
        ValueError if `timeline` is not a Timeline (propagated from
        the validator).
    """
    result = run_single_party_fear_regression(timeline)
    return {
        "timeline_id":                  result.timeline_id,
        "score":                        result.score,
        "score_band":                   _score_band(result.score),
        "structural_consistency_score": result.structural_consistency_score,
        "timeline_sensitivity_score":   result.timeline_sensitivity_score,
        "fear_mechanism_score":         result.fear_mechanism_score,
        "threat_mechanism_score":       result.threat_mechanism_score,
        "repression_coverage_score":    result.repression_coverage_score,
        "assertions_passed":            list(result.assertions_passed),
        "assertions_failed":            list(result.assertions_failed),
        "scenario_results":             dict(result.scenario_results),
    }
