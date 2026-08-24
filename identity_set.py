"""
identity_set.py — pressure inside a single set of identities.

CANON 100 · Energy Rings
    "Energy rings form the emotional geometry of a system. The inner
     ring holds identity and is the least permeable... Pressure applied
     to inner rings produces greater distortion and collapse risk."

WHAT THIS IS
------------
The multi-agent model treats N PEOPLE, each with their own state and
their own margin, coupled by social edges.

This treats N IDENTITIES IN ONE PERSON — parent, employee, litigant,
patient, son — coupled by something stronger than a social edge:

    ★ THEY SHARE ONE MARGIN.

One nervous system, one calendar, one capacity. Pressure on the
litigant identity does not leave the parent identity untouched; it
draws down the same pool. That is the coupling, and it is why a set
can be over-committed while every individual role looks survivable.

STRAIN FORMULA — carried verbatim, not re-derived
-------------------------------------------------
From v2_Individual_Support.txt:52-69, SystemState._calculate_strain:

    fragility    = 10 - margin
    base_strain  = 0.30*P + 0.25*fragility + 0.20*T
                 + 0.15*|D| + 0.10*(E*10)          weights sum to 1.0
    strain       = min(10, base_strain * (1 + P*fragility/100))

Weighted sum preserves range by construction; ONE coupling multiplier
applies the nonlinearity. Products of independent primitives would
collapse the scale — this does not do that, and neither does this
module.

WHAT IT REPORTS
---------------
    per-identity strain          each role, under the shared margin
    shared-margin utilization    total demand against one pool
    OVER-COMMITTED               demand exceeds the pool. A set can be
                                 over-committed with no single role
                                 above its own threshold.
    SHEAR                        two identities whose demands land in
                                 the same window and conflict

NO MODEL. NO NETWORK. NO #G. Deterministic: same input, same output.
Fails loud; returns no number a caller cannot distinguish from a
measurement.
"""
from __future__ import annotations

from typing import Optional, Sequence, TypedDict

CANON_ENTRY = "100"

# Carried from v2_Individual_Support.txt:52-69. Sum to 1.0 by design —
# asserted at import, not assumed.
W_PRESSURE, W_FRAGILITY, W_TEMPERATURE, W_DRIFT, W_ESCALATION = (
    0.30, 0.25, 0.20, 0.15, 0.10
)
assert abs(
    W_PRESSURE + W_FRAGILITY + W_TEMPERATURE + W_DRIFT + W_ESCALATION - 1.0
) < 1e-9, "strain weights must sum to 1.0"

SCALE_MAX = 10.0


class IdentitySetError(ValueError):
    """identity_set's own failure type — never swallowed."""


class Identity(TypedDict, total=False):
    name: str
    pressure: float        # 0-10   force per unit capacity
    temperature: float     # 0-10   internal agitation
    drift: float           # -5..+5 cumulative displacement
    escalation_risk: float # 0-1    proximity to critical point
    window: Optional[str]  # when the demand lands, e.g. "weekday_evening"


class IdentityReading(TypedDict):
    name: str
    strain: float
    pressure: float
    share_of_demand: float


class SetReading(TypedDict):
    canon: str
    n_identities: int
    shared_margin: float
    fragility: float
    total_demand: float
    utilization: float
    over_committed: bool
    identities: list[IdentityReading]
    shear: list[tuple[str, str, str]]
    line: str


def _require(v, name: str, lo: float, hi: float) -> float:
    if not isinstance(v, (int, float)) or v != v:
        raise IdentitySetError(f"{name} must be a finite number, got {v!r}")
    v = float(v)
    if not (lo <= v <= hi):
        raise IdentitySetError(f"{name}={v} outside [{lo}, {hi}]")
    return v


def strain(
    *, pressure: float, margin: float, temperature: float,
    drift: float, escalation_risk: float,
) -> float:
    """The carried formula. One identity, against a given margin."""
    p = _require(pressure, "pressure", 0.0, 10.0)
    m = _require(margin, "margin", 0.0, 10.0)
    t = _require(temperature, "temperature", 0.0, 10.0)
    d = _require(drift, "drift", -5.0, 5.0)
    e = _require(escalation_risk, "escalation_risk", 0.0, 1.0)

    fragility = SCALE_MAX - m
    base = (
        W_PRESSURE * p
        + W_FRAGILITY * fragility
        + W_TEMPERATURE * t
        + W_DRIFT * abs(d)
        + W_ESCALATION * (e * 10.0)
    )
    return min(SCALE_MAX, base * (1.0 + p * fragility / 100.0))


def assess_set(
    identities: Sequence[Identity],
    *,
    shared_margin: float,
) -> SetReading:
    """N identities drawing on ONE margin.

    `shared_margin` is the person's single remaining capacity. It is
    NOT divided among the identities and NOT re-supplied per role —
    that is the entire point. Every strain below is computed against
    the same pool.
    """
    if not isinstance(identities, (list, tuple)):
        raise IdentitySetError("identities must be a list or tuple")
    if len(identities) < 2:
        raise IdentitySetError(
            "a set requires >= 2 identities; a single identity is the "
            "individual case and belongs in the base model"
        )
    m = _require(shared_margin, "shared_margin", 0.0, 10.0)
    fragility = SCALE_MAX - m

    names: list[str] = []
    readings: list[IdentityReading] = []
    total_demand = 0.0

    for i, ident in enumerate(identities):
        if not isinstance(ident, dict):
            raise IdentitySetError(f"identities[{i}] is not a dict")
        name = ident.get("name")
        if not isinstance(name, str) or not name:
            raise IdentitySetError(f"identities[{i}] has no name")
        if name in names:
            raise IdentitySetError(f"duplicate identity name: {name!r}")
        names.append(name)

        p = _require(ident.get("pressure"), f"{name}.pressure", 0.0, 10.0)
        s = strain(
            pressure=p,
            margin=m,
            temperature=ident.get("temperature", 0.0),
            drift=ident.get("drift", 0.0),
            escalation_risk=ident.get("escalation_risk", 0.0),
        )
        total_demand += p
        readings.append({
            "name": name, "strain": s, "pressure": p,
            "share_of_demand": 0.0,   # filled below
        })

    if total_demand > 0:
        for r in readings:
            r["share_of_demand"] = r["pressure"] / total_demand

    # Utilization: total demand against the single pool. Above 1.0 the
    # set is over-committed — and that can be true while every single
    # identity sits below its own threshold, which is why per-role
    # readings alone cannot detect it.
    utilization = total_demand / m if m > 0 else float("inf")
    over = utilization > 1.0

    # SHEAR: two identities whose demands land in the same window.
    # Reported only when the window is DECLARED on both — an absent
    # window is unknown, never assumed to be non-conflicting.
    shear: list[tuple[str, str, str]] = []
    for i in range(len(identities)):
        wi = identities[i].get("window")
        if not wi:
            continue
        for j in range(i + 1, len(identities)):
            if identities[j].get("window") == wi:
                shear.append((names[i], names[j], wi))

    readings.sort(key=lambda r: r["strain"], reverse=True)

    if over and shear:
        line = (
            f"{len(identities)} identities drawing on one margin of {m:.1f}. "
            f"Total demand exceeds it ({utilization:.2f}x), and "
            f"{len(shear)} pair(s) land in the same window."
        )
    elif over:
        line = (
            f"{len(identities)} identities drawing on one margin of {m:.1f}. "
            f"Total demand exceeds it ({utilization:.2f}x). No single role "
            f"has to be over threshold for this to be true."
        )
    elif shear:
        line = (
            f"Margin covers total demand ({utilization:.2f}x), but "
            f"{len(shear)} pair(s) land in the same window."
        )
    else:
        line = f"Margin covers total demand ({utilization:.2f}x). No window conflicts declared."

    return {
        "canon": CANON_ENTRY,
        "n_identities": len(identities),
        "shared_margin": m,
        "fragility": fragility,
        "total_demand": total_demand,
        "utilization": utilization,
        "over_committed": over,
        "identities": readings,
        "shear": shear,
        "line": line,
    }
