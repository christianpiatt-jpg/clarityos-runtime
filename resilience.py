"""
resilience.py — critical-transition early warning from a time series.

Pattern-setting rules inherited from canon.py: fail loud, never
default, never return a number the caller cannot distinguish from a
measurement.

WHAT THIS IS
------------
Two signals precede a critical transition in a wide class of systems
(Scheffer et al., "Early-warning signals for critical transitions"):

  1. RISING VARIANCE          fluctuations grow as the basin flattens
  2. RISING LAG-1 AUTOCORR    the system recovers more slowly from
                              perturbation — "critical slowing down"

Both are computed from the series alone. No model, no fit, no
provider call, no parameters chosen by hand.

WHAT THIS IS NOT
----------------
Not a prediction of WHEN. Not a claim about WHY. Not a diagnosis.
It reports two derivatives and their agreement. A rising trend means
the basin is flattening; it does not mean a transition will occur.

DELIBERATELY ABSENT: a confidence score. Any single number here would
be indistinguishable from a measurement, and the whole point of the
module is that it isn't one.

USAGE
-----
    r = assess(series, window=10)
    r["status"]         "insufficient" | "measured"
    r["variance_trend"] slope of rolling variance, or None
    r["autocorr_trend"] slope of rolling lag-1 autocorr, or None
    r["agreement"]      "both_rising" | "both_falling" | "divergent"
                        | None
    r["n"]              samples used
    r["windows"]        rolling windows produced
"""
from __future__ import annotations

from typing import Optional, Sequence, TypedDict

MIN_WINDOW = 4          # below this, variance is not meaningful
MIN_WINDOWS_FOR_TREND = 3   # below this, a slope is not meaningful

# MEASURED 2026-08-24, not chosen. Synthetic series with autocorrelation
# rising 0.30 -> 0.95 by construction, 12 seeds, 400 samples, against a
# stable control. Separation (every approaching run above every stable
# run) first holds at window=40:
#     window  10   stable +0.000173   approaching +0.001027   NO
#     window  20   stable +0.000201   approaching +0.001273   NO
#     window  40   stable +0.000163   approaching +0.001402   YES
#     window 100   stable +0.000015   approaching +0.001462   YES
# Below 40 the lag-1 estimate is computed from <39 pairs and sampling
# noise swamps the trend. Variance separates cleanly at window=10.
MIN_WINDOW_AUTOCORR = 40


class ResilienceError(ValueError):
    """resilience's own failure type — never swallowed, never
    defaulted."""


class Assessment(TypedDict):
    status: str
    n: int
    windows: int
    variance_trend: Optional[float]
    autocorr_trend: Optional[float]
    agreement: Optional[str]
    reason: Optional[str]


# ---------------------------------------------------------------------------
# primitives — stdlib only, no numpy dependency at import
# ---------------------------------------------------------------------------
def _variance(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        raise ResilienceError("variance requires >= 2 samples")
    mean = sum(xs) / n
    return sum((x - mean) ** 2 for x in xs) / n


def _lag1_autocorr(xs: Sequence[float]) -> Optional[float]:
    """Pearson correlation of xs[:-1] against xs[1:].

    Returns None when the series is constant over the window — a flat
    window has NO autocorrelation, which is different from zero
    autocorrelation. Returning 0.0 here would be a fabricated null.
    """
    n = len(xs)
    if n < 3:
        raise ResilienceError("lag-1 autocorrelation requires >= 3 samples")
    a, b = xs[:-1], xs[1:]
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a)
    db = sum((y - mb) ** 2 for y in b)
    if da == 0.0 or db == 0.0:
        return None            # flat window — undefined, not zero
    return num / ((da ** 0.5) * (db ** 0.5))


def _slope(xs: Sequence[float]) -> float:
    """Least-squares slope against index 0..n-1."""
    n = len(xs)
    if n < 2:
        raise ResilienceError("slope requires >= 2 samples")
    mean_x = (n - 1) / 2.0
    mean_y = sum(xs) / n
    num = sum((i - mean_x) * (y - mean_y) for i, y in enumerate(xs))
    den = sum((i - mean_x) ** 2 for i in range(n))
    if den == 0.0:
        raise ResilienceError("degenerate index range")
    return num / den


# ---------------------------------------------------------------------------
# public
# ---------------------------------------------------------------------------
def assess(series: Sequence[float], *, window: int = 10) -> Assessment:
    """Rolling variance and lag-1 autocorrelation trends over `series`.

    Raises ResilienceError on malformed input. Returns
    status="insufficient" with an explicit `reason` when the series is
    well-formed but too short — that is a legal, common, first-class
    outcome and it is NOT an error.
    """
    if series is None:
        raise ResilienceError("series is None")
    xs = list(series)
    if not all(isinstance(x, (int, float)) and x == x for x in xs):
        raise ResilienceError("series must contain finite numbers only")
    if not isinstance(window, int) or window < MIN_WINDOW:
        raise ResilienceError(f"window must be an int >= {MIN_WINDOW}")

    n = len(xs)
    n_windows = n - window + 1

    if n_windows < MIN_WINDOWS_FOR_TREND:
        return {
            "status": "insufficient",
            "n": n,
            "windows": max(0, n_windows),
            "variance_trend": None,
            "autocorr_trend": None,
            "agreement": None,
            "reason": (
                f"{n} samples at window={window} yields "
                f"{max(0, n_windows)} rolling windows; "
                f"{MIN_WINDOWS_FOR_TREND} required for a trend"
            ),
        }

    variances: list[float] = []
    autocorrs: list[float] = []
    for i in range(n_windows):
        w = xs[i:i + window]
        variances.append(_variance(w))
        ac = _lag1_autocorr(w)
        if ac is not None:
            autocorrs.append(ac)

    v_trend = _slope(variances)

    # The autocorrelation half is REFUSED below the measured minimum
    # rather than returned noisy. A trend computed from <39 pairs per
    # window is indistinguishable from the stable control — see
    # MIN_WINDOW_AUTOCORR. Returning it would be a fabricated reading.
    if window < MIN_WINDOW_AUTOCORR:
        a_trend = None
        ac_reason = (
            f"autocorrelation not reported: window={window} is below the "
            f"measured minimum of {MIN_WINDOW_AUTOCORR}; the estimate is "
            f"not separable from noise at this width"
        )
    elif len(autocorrs) >= MIN_WINDOWS_FOR_TREND:
        a_trend = _slope(autocorrs)
        ac_reason = None
    else:
        a_trend = None
        ac_reason = (
            "autocorrelation undefined in too many windows "
            "(series flat or near-flat)"
        )

    if a_trend is None:
        agreement = None
    elif v_trend > 0 and a_trend > 0:
        agreement = "both_rising"
    elif v_trend < 0 and a_trend < 0:
        agreement = "both_falling"
    else:
        agreement = "divergent"

    return {
        "status": "measured",
        "n": n,
        "windows": n_windows,
        "variance_trend": v_trend,
        "autocorr_trend": a_trend,
        "agreement": agreement,
        "reason": ac_reason,
    }


def describe(a: Assessment) -> str:
    """One line, in the register the operator reads. Never claims more
    than the assessment contains."""
    if a["status"] == "insufficient":
        return f"Not enough history to measure. {a['reason']}"
    if a["agreement"] == "both_rising":
        return (
            "Variance and recovery time are both increasing. In systems "
            "of this class that pattern precedes a transition. It does "
            "not say when, or whether one will occur."
        )
    if a["agreement"] == "both_falling":
        return "Variance and recovery time are both decreasing."
    if a["agreement"] == "divergent":
        return (
            "The two signals disagree: one is rising, the other falling. "
            "No combined reading."
        )
    return f"Partial measurement. {a['reason']}"
