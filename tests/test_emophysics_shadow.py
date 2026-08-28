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
def test_t_and_n_are_unmapped_never_defaulted():
    p = app_module._emophysics_shadow("u", LOW)
    assert p["T"] == "UNMAPPED"
    assert p["N"] == "UNMAPPED"
    assert p["computed"] is False


def test_the_reason_names_both_gaps_specifically():
    """A sentinel that says only 'unmapped' does not tell the next reader
    WHY, and the two gaps have different causes and different fixes."""
    reason = app_module._emophysics_shadow("u", LOW)["reason"]
    assert "no server-side producer" in reason      # T
    assert "not implemented" in reason              # N (CI)


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
    pressure."""
    p = app_module._emophysics_shadow("u", HIGH)
    assert p["N"] != 5.0 and p["N"] != "5.0"
    assert isinstance(p["N"], str)


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
