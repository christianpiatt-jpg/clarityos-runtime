"""
Emotional Physics PHASE 1 — the shadow layer.

★★★ THESE TESTS PIN THE PROHIBITIONS, NOT THE FEATURE.

The phase computes almost nothing on purpose. Its value is that two
absences — T and N — stay visible instead of being defaulted into a
plausible number. So the tests that matter here are the ones asserting what
does NOT happen.

★★ EmotionalState's own defaults are the hazard: `EmotionalState()` yields
N=5.0, E=0.5, m=3.0, T=0.5 — a complete, plausible, meaningless state.
Merely constructing it would manufacture the answer this phase withholds.
That is why the guard is "never constructed", not "constructed carefully".
"""
import os

os.environ.setdefault("CLARITYOS_BACKEND", "memory")
os.environ.setdefault("CLARITYOS_VAULT_SECRET", "test-only-not-a-real-secret")

import re  # noqa: E402

import app as app_module  # noqa: E402

LOW = "The constraint caused friction. A bottleneck appeared. There was tension."
HIGH = (
    "The constraint caused friction and contradiction. A bottleneck and a deadlock "
    "appeared under structural tension. Competition and regulation from a competitor "
    "created external demand pressure. The goal and the objective and the incentive "
    "drove the motive. Trade-off, limitation and imbalance under strain and load."
)


# --------------------------------------------------------------------------
# THE SENTINEL — tested first, because a sentinel that never fires is
# indistinguishable from one that is not there.
# --------------------------------------------------------------------------
def test_t_stays_unmapped_and_is_never_defaulted():
    """T is blocked by DEVICE TOPOLOGY, not by a missing formula:
    hedgeRatio is computed client-side in phone/lib/langbridg.ts and the
    web path has no producer at all. N left this list when CI was
    implemented; T cannot leave it by being built."""
    p = app_module._emophysics_shadow("u", LOW)
    assert p["T"] == "UNMAPPED"
    assert p["computed"] is False


def test_the_reason_names_both_gaps_specifically():
    """A sentinel that says only 'unmapped' does not tell the next reader
    WHY, and the two gaps have different causes and different fixes."""
    reason = app_module._emophysics_shadow("u", LOW)["reason"]
    assert "no server-side producer" in reason      # T
    assert "weighting unruled" in reason            # N (CI) -- built,
    #                                                 but not yet ruled
    assert "not implemented" not in reason          # it IS implemented


def test_no_physics_number_is_ever_emitted():
    """★ The payload must carry no P, P_perc, alpha or collapse_probability
    under any name. A number here would be a confident value with correct
    units and no measurement behind it."""
    p = app_module._emophysics_shadow("u", HIGH)
    for forbidden in ("P", "P_perc", "alpha", "collapse_probability",
                      "pressure", "collapse"):
        assert forbidden not in p, f"shadow emitted {forbidden}"
    assert not re.search(r"\b(P|alpha)\b\s*[:=]\s*[\d.]", str(p))


def test_n_never_appears_as_five():
    """The specific failure this phase exists to prevent: N silently
    becoming EmotionalState's 5.0 default and logging a plausible
    pressure.

    * N is now a real measurement, so the guard is stronger than it was:
    CI is bounded in [0,1] BY CONSTRUCTION, so 5.0 is not merely absent,
    it is unreachable. The assertion is kept because the value it
    excludes is the one that would look most convincing."""
    p = app_module._emophysics_shadow("u", HIGH)
    assert p["N"] != 5.0 and p["N"] != "5.0"
    assert isinstance(p["N"], float)
    assert 0.0 <= p["N"] <= 1.0


def test_the_engine_is_never_constructed(monkeypatch):
    """★★ Merely instantiating EmotionalState manufactures a full plausible
    state from dataclass defaults. Nothing in the shadow path may touch the
    engine at all."""
    import engine.emophysics as ep

    touched = []
    for name in ("EmotionalState", "PressureModel", "RelationalModel",
                 "ThresholdModel", "ConversionModel"):
        real = getattr(ep, name)

        def tripwire(*a, _n=name, **k):
            touched.append(_n)
            raise AssertionError(f"shadow constructed {_n}")

        monkeypatch.setattr(ep, name, tripwire)
        assert real is not None
    app_module._emophysics_shadow("u", HIGH)
    assert touched == [], f"engine touched: {touched}"


# --------------------------------------------------------------------------
# D — the one thing this phase does measure.
# --------------------------------------------------------------------------
def test_d_moves_with_the_members_text():
    """★ THE GATE. If D does not move, the extractor is not on the path and
    everything after this phase is built on nothing."""
    low = app_module._emophysics_shadow("u", LOW)["D"]
    high = app_module._emophysics_shadow("u", HIGH)["D"]
    assert low > 0, "no signal at all from tension-bearing text"
    assert high > low, f"D did not move ({low} -> {high})"


def test_the_full_distribution_is_captured():
    """The 8-way counts vector is CI's `p` in Phase 2. This phase starts
    accumulating the input the next phase consumes, so the whole vector is
    logged, not just the sum."""
    p = app_module._emophysics_shadow("u", HIGH)
    assert set(p["counts"]) == {"P1", "P2", "P3", "P4", "Ts", "Te", "M", "hydronic"}
    assert p["D"] == sum(p["counts"].values())


def test_d_is_tagged_a_candidate():
    """D = sum(counts) is unruled. The tag is what makes a later change one
    line instead of an archaeology exercise."""
    assert app_module._emophysics_shadow("u", LOW)["D_status"] == "CANDIDATE"


def test_empty_and_non_string_input_do_not_raise():
    for bad in ("", "   ", None, 42, []):
        p = app_module._emophysics_shadow("u", bad)  # type: ignore[arg-type]
        assert p["D"] == 0 and p["computed"] is False


# --------------------------------------------------------------------------
# N — the compression index. CI = 1 - H/H_max over the fixed eight.
# --------------------------------------------------------------------------
# ★★★ WHAT THESE PIN. Not the arithmetic — that is four lines out of a
# spec. They pin the ZERO EDGE, because that is where this metric would
# have been quietly wrong. engine/emophysics/relational.py:142 answers the
# same shape of failure with `return 1.0`, which reads as PERFECT
# REGISTRATION at precisely the point the instrument has no measurement.
# The sentinel is asserted BY TYPE so no future refactor can round it into
# a number without a test going red.
def _counts(**kw):
    """The eight fixed keys, zero unless named. Mirrors
    primitives_extract.build_metadata, which never returns fewer."""
    base = {"P1": 0, "P2": 0, "P3": 0, "P4": 0,
            "Ts": 0, "Te": 0, "M": 0, "hydronic": 0}
    base.update(kw)
    return base


def test_ci_moves_when_the_distribution_moves():
    """★ THE GATE. If CI does not move with the counts, the field is
    decorative and the order failed."""
    concentrated = app_module._compression_index(_counts(P1=10, P2=1))
    spread = app_module._compression_index(
        _counts(P1=3, P2=3, P3=3, P4=3, Ts=3, Te=3, M=3, hydronic=3))
    assert isinstance(concentrated, float) and isinstance(spread, float)
    assert concentrated > spread, f"CI did not move ({spread} -> {concentrated})"


def test_a_single_category_turn_is_maximally_compressed():
    """All the weight in one category is zero entropy, so CI is exactly 1.
    ★ That is the CORRECT reading — over-compressed, brittle — and not an
    artifact of the zero categories, which each contribute 0 to H."""
    assert app_module._compression_index(_counts(Ts=7)) == 1.0


def test_a_perfectly_flat_spread_is_minimally_compressed():
    """Eight equal categories is maximum entropy: H == H_max, so CI is
    exactly 0. Entropy-friendly, resilient."""
    flat = _counts(P1=2, P2=2, P3=2, P4=2, Ts=2, Te=2, M=2, hydronic=2)
    assert app_module._compression_index(flat) == 0.0


def test_no_extraction_returns_a_different_kind_not_a_number():
    """★★★★★ D5, and the whole reason this order was written. An extraction
    that found nothing leaves p_i UNDEFINED. Asserted BY TYPE: a float here
    — any float — would be a confident reading with no measurement behind
    it, which is exactly relational.py:142's `return 1.0`."""
    out = app_module._compression_index(_counts())
    assert not isinstance(out, float)
    assert isinstance(out, str)
    assert out == "UNMAPPED"


def test_a_different_taxonomy_size_returns_the_sentinel():
    """n is the taxonomy size and it is CONSTANT. A denominator that varied
    would make two turns' CI values different measurements, and the series
    they are plotted in meaningless."""
    assert app_module._compression_index({"P1": 3, "P2": 1}) == "UNMAPPED"
    assert app_module._compression_index({}) == "UNMAPPED"


def test_the_empty_turn_carries_the_sentinel_through_the_payload():
    """End to end: the shadow payload, not just the function."""
    p = app_module._emophysics_shadow("u", "")
    assert p["N"] == "UNMAPPED"
    assert p["N_status"] == "UNMAPPED"
    assert not isinstance(p["N"], float)
    assert "p_i undefined" in p["reason"]


def test_n_is_tagged_a_candidate_exactly_as_d_is():
    """The closed form is ruled; the WEIGHTING is not. Whether Ts/Te should
    outrank P1-P4 before the counts become a probability vector is the same
    open question D carries. The tag is what makes that change one line."""
    p = app_module._emophysics_shadow("u", HIGH)
    assert p["N_status"] == "CANDIDATE"
    assert p["D_status"] == "CANDIDATE"


def test_the_returned_value_is_not_rounded():
    """Rounding is a display decision and belongs at the log boundary. A
    consumer must never inherit a truncation made for readability."""
    p = app_module._emophysics_shadow("u", HIGH)
    assert p["N"] == app_module._compression_index(p["counts"])
