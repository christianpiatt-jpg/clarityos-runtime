"""
effort_threshold.py — what it costs to move, given where you are.

CANON 030 · Stability Envelopes  ·  CANON 120 · Collapse Mechanics

WHAT THIS IS
------------
The state sits in a potential well whose shape is set by two controls:
pressure and margin. Carried from v2_Godhard Curve Integration:70-100.

    V(x)      = x**4/4  -  (margin/10)*x**2/2  -  (pressure/10)*x
    F(x)      = -dV/dx  =  -x**3 + (margin/10)*x + (pressure/10)
    d2V/dx2   = 3*x**2 - margin/10        stable where > 0

Equilibria are the roots of F. There are one or three.

    ONE   monostable. One place to be. No jump available.
    THREE bistable: low basin | ridge | high basin.
          ★ The ridge between them is the effort threshold.

WHY IT MATTERS
--------------
Effort is not uniform. The same push produces:

    - almost nothing, deep in a basin
    - a discontinuous jump, near the ridge

And the two directions are NOT equal. The distance from the low basin
up to the ridge is not the distance from the high basin back down to
it. Falling in and climbing out cost different amounts.

    ★ "It is harder to get out than it was to get in" is not a
      feeling about willpower. It is the shape of the well, and it
      is computable.

That asymmetry is hysteresis, and it is the single most useful thing
this module reports: it tells an operator that the effort now required
is larger than the effort that would have prevented this, WITHOUT
implying they should have tried harder.

NO MODEL. NO NETWORK. NO #G. Stdlib only. Deterministic.
Fails loud; reports UNDEFINED rather than a number it cannot support.
"""
from __future__ import annotations

from typing import Literal, Optional, TypedDict

CANON_ENTRIES = ("030", "120")

_SEARCH_LO, _SEARCH_HI = -6.0, 6.0
_SEARCH_STEPS = 2000
_BISECT_ITERS = 80
_TOL = 1e-9


class EffortError(ValueError):
    """effort_threshold's own failure type."""


class Threshold(TypedDict):
    canon: tuple[str, ...]
    regime: Literal["monostable", "bistable"]
    position: float
    basin: Literal["low", "high", "ridge", "single"]
    equilibria: list[float]
    ridge: Optional[float]
    effort_to_leave: Optional[float]
    effort_to_return: Optional[float]
    asymmetry: Optional[float]
    distance_to_ridge: Optional[float]
    sensitivity: Literal["flat", "responsive", "critical"]
    line: str


def _require(v, name: str, lo: float, hi: float) -> float:
    if not isinstance(v, (int, float)) or v != v:
        raise EffortError(f"{name} must be a finite number, got {v!r}")
    v = float(v)
    if not (lo <= v <= hi):
        raise EffortError(f"{name}={v} outside [{lo}, {hi}]")
    return v


def potential(x: float, pressure: float, margin: float) -> float:
    p, m = pressure / 10.0, margin / 10.0
    return 0.25 * x ** 4 - 0.5 * m * x ** 2 - p * x


def force(x: float, pressure: float, margin: float) -> float:
    p, m = pressure / 10.0, margin / 10.0
    return -(x ** 3) + m * x + p


def _curvature(x: float, margin: float) -> float:
    return 3.0 * x ** 2 - margin / 10.0


def _bisect(f, lo: float, hi: float) -> float:
    flo = f(lo)
    for _ in range(_BISECT_ITERS):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if abs(fm) < _TOL or (hi - lo) < _TOL:
            return mid
        if (flo < 0) != (fm < 0):
            hi = mid
        else:
            lo, flo = mid, fm
    return 0.5 * (lo + hi)


def equilibria(pressure: float, margin: float) -> list[float]:
    """Roots of F, found by sign change and bisection. Stdlib only."""
    p = _require(pressure, "pressure", 0.0, 10.0)
    m = _require(margin, "margin", 0.0, 10.0)

    def f(x: float) -> float:
        return force(x, p, m)

    roots: list[float] = []
    step = (_SEARCH_HI - _SEARCH_LO) / _SEARCH_STEPS
    x0 = _SEARCH_LO
    f0 = f(x0)
    for i in range(1, _SEARCH_STEPS + 1):
        x1 = _SEARCH_LO + i * step
        f1 = f(x1)
        if f0 == 0.0:
            roots.append(x0)
        elif (f0 < 0) != (f1 < 0):
            roots.append(_bisect(f, x0, x1))
        x0, f0 = x1, f1

    out: list[float] = []
    for r in roots:
        if not any(abs(r - s) < 1e-6 for s in out):
            out.append(r)
    if not out:
        raise EffortError(
            f"no equilibrium found for pressure={p}, margin={m} in "
            f"[{_SEARCH_LO}, {_SEARCH_HI}] — refusing to report a "
            f"position with no rest state"
        )
    return sorted(out)


def assess(
    position: float, *, pressure: float, margin: float
) -> Threshold:
    """Where the state sits, and what it costs to move from there."""
    x = _require(position, "position", _SEARCH_LO, _SEARCH_HI)
    p = _require(pressure, "pressure", 0.0, 10.0)
    m = _require(margin, "margin", 0.0, 10.0)

    eqs = equilibria(p, m)
    stable = [e for e in eqs if _curvature(e, m) > 0]
    unstable = [e for e in eqs if _curvature(e, m) < 0]

    if len(stable) < 2 or not unstable:
        # monostable — one rest state, nothing to jump between
        nearest = min(eqs, key=lambda e: abs(e - x))
        return {
            "canon": CANON_ENTRIES,
            "regime": "monostable",
            "position": x,
            "basin": "single",
            "equilibria": eqs,
            "ridge": None,
            "effort_to_leave": None,
            "effort_to_return": None,
            "asymmetry": None,
            "distance_to_ridge": None,
            "sensitivity": "flat",
            "line": (
                f"One rest state at {nearest:.2f}. No alternative basin "
                f"exists at this pressure and margin — there is nothing "
                f"to jump to, and nothing to fall into."
            ),
        }

    ridge = unstable[0]
    low, high = min(stable), max(stable)
    v_ridge = potential(ridge, p, m)
    v_low = potential(low, p, m)
    v_high = potential(high, p, m)

    # Which basin is the state actually in
    if x < ridge:
        basin: Literal["low", "high", "ridge"] = "low"
        leave = v_ridge - v_low
        back = v_ridge - v_high
    elif x > ridge:
        basin = "high"
        leave = v_ridge - v_high
        back = v_ridge - v_low
    else:
        basin = "ridge"
        leave = 0.0
        back = 0.0

    dist = abs(x - ridge)
    if dist < 0.15:
        sens: Literal["flat", "responsive", "critical"] = "critical"
    elif dist < 0.60:
        sens = "responsive"
    else:
        sens = "flat"

    asym = (back - leave) if basin in ("low", "high") else 0.0

    if basin == "ridge":
        line = (
            "The state is on the ridge itself. Any push decides which "
            "basin it falls into."
        )
    elif sens == "critical":
        line = (
            f"{dist:.2f} from the ridge. At this distance a small push "
            f"moves the state a long way — in either direction."
        )
    elif asym > 0:
        line = (
            f"Leaving this basin costs {leave:.3f}. Returning to it "
            f"afterwards costs {back:.3f} — {asym:.3f} more. The way "
            f"back is longer than the way out; that is the shape of "
            f"the well, not a failure of effort."
        )
    else:
        line = (
            f"Leaving this basin costs {leave:.3f}; returning costs "
            f"{back:.3f}. The return is not more expensive than the exit."
        )

    return {
        "canon": CANON_ENTRIES,
        "regime": "bistable",
        "position": x,
        "basin": basin,
        "equilibria": eqs,
        "ridge": ridge,
        "effort_to_leave": leave,
        "effort_to_return": back,
        "asymmetry": asym,
        "distance_to_ridge": dist,
        "sensitivity": sens,
        "line": line,
    }
