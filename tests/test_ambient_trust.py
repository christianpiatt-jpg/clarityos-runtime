"""
Tests for the Ambient Trust module.

Two layers:
    1. Structural — enums / schemas / privacy contract / module-load guards.
    2. Behavioral — assess_trust_state / verify_no_hard_stops /
       verify_comprehension_leads_action / gentle_repair against concrete
       fixtures producing the expected outputs.

The engine is pure and deterministic, so behavioral tests assert
byte-equal returns. No mocking required — no I/O exists to mock.
"""
from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError

import pytest

import ambient_trust_engine as engine
import ambient_trust_schemas as schemas


# ===========================================================================
# Fixture builders
# ===========================================================================
def _exposure(concept_id: str = "envelope", count: int = 1) -> schemas.ConceptExposure:
    return schemas.ConceptExposure(concept_id=concept_id, count=count)


def _ctx(
    *,
    ability_level: int = 0,
    comprehension_level: int = 0,
    concept_exposures: tuple = (),
    hard_stop_count: int = 0,
    last_action_acknowledged: bool = True,
) -> schemas.SessionContext:
    return schemas.SessionContext(
        ability_level=ability_level,
        comprehension_level=comprehension_level,
        concept_exposures=concept_exposures,
        hard_stop_count=hard_stop_count,
        last_action_acknowledged=last_action_acknowledged,
    )


# ===========================================================================
# A. Enums
# ===========================================================================
class TestEnums:
    def test_repair_kind_values(self):
        assert {v.value for v in schemas.RepairKind} == {
            "none", "re_anchor", "slow_pace",
            "offer_choice", "narrow_scope",
        }

    def test_repair_kind_no_halt_member(self):
        """Invariant 10: gentle_repair never emits a halt-like directive.
        Structurally enforced by RepairKind having no halting member."""
        for v in schemas.RepairKind:
            assert "halt" not in v.value.lower()
            assert "stop" not in v.value.lower()
            assert "block" not in v.value.lower()


# ===========================================================================
# B. Schemas — frozen + instantiable
# ===========================================================================
class TestConceptExposure:
    def test_instantiable(self):
        e = _exposure()
        assert e.concept_id == "envelope"
        assert e.count == 1

    def test_frozen(self):
        e = _exposure()
        with pytest.raises(FrozenInstanceError):
            e.count = 9  # type: ignore[misc]


class TestSessionContext:
    def test_instantiable(self):
        c = _ctx(ability_level=1, comprehension_level=1)
        assert c.ability_level == 1

    def test_frozen(self):
        c = _ctx()
        with pytest.raises(FrozenInstanceError):
            c.ability_level = 3  # type: ignore[misc]

    def test_defaults(self):
        c = _ctx()
        assert c.hard_stop_count == 0
        assert c.last_action_acknowledged is True
        assert c.concept_exposures == ()


class TestTrustState:
    def test_instantiable(self):
        t = schemas.TrustState(
            understanding_gap=0, momentum_intact=True,
            trust_score=1.0, repair_needed=False,
        )
        assert t.trust_score == 1.0

    def test_frozen(self):
        t = schemas.TrustState(
            understanding_gap=0, momentum_intact=True,
            trust_score=1.0, repair_needed=False,
        )
        with pytest.raises(FrozenInstanceError):
            t.trust_score = 0.5  # type: ignore[misc]


class TestUnderstandingCheck:
    def test_instantiable(self):
        u = schemas.UnderstandingCheck(
            ability_level=2, comprehension_level=2,
            gap=0, passes_invariant=True,
        )
        assert u.passes_invariant is True

    def test_frozen(self):
        u = schemas.UnderstandingCheck(
            ability_level=2, comprehension_level=2,
            gap=0, passes_invariant=True,
        )
        with pytest.raises(FrozenInstanceError):
            u.gap = 1  # type: ignore[misc]


class TestMomentumCheck:
    def test_instantiable(self):
        m = schemas.MomentumCheck(
            hard_stop_count=0, last_action_acknowledged=True,
            hard_stop_detected=False, passes_invariant=True,
        )
        assert m.passes_invariant is True

    def test_frozen(self):
        m = schemas.MomentumCheck(
            hard_stop_count=0, last_action_acknowledged=True,
            hard_stop_detected=False, passes_invariant=True,
        )
        with pytest.raises(FrozenInstanceError):
            m.hard_stop_count = 1  # type: ignore[misc]


class TestRepairDirective:
    def test_instantiable(self):
        r = schemas.RepairDirective(
            kind=schemas.RepairKind.NONE, rationale="ok",
        )
        assert r.kind == schemas.RepairKind.NONE

    def test_frozen(self):
        r = schemas.RepairDirective(
            kind=schemas.RepairKind.NONE, rationale="ok",
        )
        with pytest.raises(FrozenInstanceError):
            r.rationale = "changed"  # type: ignore[misc]


# ===========================================================================
# C. Privacy contract — no forbidden fields in any Ambient Trust type
# ===========================================================================
class TestPrivacyContract:
    @pytest.mark.parametrize("cls_name", [
        "ConceptExposure", "SessionContext", "TrustState",
        "UnderstandingCheck", "MomentumCheck", "RepairDirective",
    ])
    @pytest.mark.parametrize("forbidden", [
        "text", "raw", "raw_text",
        "user", "user_id", "id",
        "name", "names", "email",
        "session", "session_id", "identity",
        "envelope_id", "author", "actor",
        "content", "body", "message",
    ])
    def test_no_forbidden_field(self, cls_name, forbidden):
        cls = getattr(schemas, cls_name)
        assert forbidden not in cls.__dataclass_fields__, (
            f"{cls_name}.{forbidden} would leak identity/text — forbidden"
        )

    def test_concept_exposure_canonical_fields(self):
        assert set(schemas.ConceptExposure.__dataclass_fields__.keys()) == {
            "concept_id", "count",
        }

    def test_session_context_canonical_fields(self):
        assert set(schemas.SessionContext.__dataclass_fields__.keys()) == {
            "ability_level", "comprehension_level", "concept_exposures",
            "hard_stop_count", "last_action_acknowledged",
        }

    def test_trust_state_canonical_fields(self):
        assert set(schemas.TrustState.__dataclass_fields__.keys()) == {
            "understanding_gap", "momentum_intact",
            "trust_score", "repair_needed",
        }

    def test_understanding_check_canonical_fields(self):
        assert set(schemas.UnderstandingCheck.__dataclass_fields__.keys()) == {
            "ability_level", "comprehension_level",
            "gap", "passes_invariant",
        }

    def test_momentum_check_canonical_fields(self):
        assert set(schemas.MomentumCheck.__dataclass_fields__.keys()) == {
            "hard_stop_count", "last_action_acknowledged",
            "hard_stop_detected", "passes_invariant",
        }

    def test_repair_directive_canonical_fields(self):
        assert set(schemas.RepairDirective.__dataclass_fields__.keys()) == {
            "kind", "rationale",
        }


# ===========================================================================
# D. Module-load runtime guards
# ===========================================================================
class TestRuntimeGuards:
    def test_privacy_guard_passes(self):
        schemas.assert_ambient_trust_privacy_contract()

    def test_field_set_guard_passes(self):
        schemas.assert_ambient_trust_field_sets_canonical()

    def test_repair_kinds_canonical(self):
        schemas.assert_repair_kinds_canonical()

    def test_concept_ids_canonical(self):
        schemas.assert_canonical_concept_ids()


# ===========================================================================
# E. Canonical concept ids
# ===========================================================================
class TestCanonicalConceptIds:
    def test_exact_set(self):
        assert schemas.CANONICAL_CONCEPT_IDS == (
            "envelope", "pressure", "geometry", "intention",
            "expression", "alignment", "halt_state",
            "trust", "momentum", "agency",
        )

    def test_is_canonical_concept_id_helper(self):
        for cid in schemas.CANONICAL_CONCEPT_IDS:
            assert schemas.is_canonical_concept_id(cid) is True
        assert schemas.is_canonical_concept_id("not_a_real_concept") is False

    def test_assess_rejects_non_canonical(self):
        bad = schemas.ConceptExposure(concept_id="not_canonical", count=1)
        ctx = _ctx(concept_exposures=(bad,))
        with pytest.raises(ValueError):
            engine.assess_trust_state(ctx)

    def test_assess_accepts_all_canonical(self):
        exposures = tuple(
            schemas.ConceptExposure(concept_id=cid, count=1)
            for cid in schemas.CANONICAL_CONCEPT_IDS
        )
        ctx = _ctx(concept_exposures=exposures)
        result = engine.assess_trust_state(ctx)
        assert isinstance(result, schemas.TrustState)


# ===========================================================================
# F. Trust score
# ===========================================================================
class TestTrustScore:
    def test_baseline_full_trust(self):
        ctx = _ctx(ability_level=2, comprehension_level=2)
        t = engine.assess_trust_state(ctx)
        assert t.trust_score == 1.0

    def test_gap_penalty(self):
        ctx = _ctx(ability_level=3, comprehension_level=1)  # gap=2
        t = engine.assess_trust_state(ctx)
        # 1.0 - 0.2*2 = 0.6
        assert t.trust_score == 0.6

    def test_unacknowledged_penalty(self):
        ctx = _ctx(
            ability_level=2, comprehension_level=2,
            last_action_acknowledged=False,
        )
        t = engine.assess_trust_state(ctx)
        # 1.0 - 0.2 = 0.8
        assert t.trust_score == 0.8

    def test_hard_stop_penalty(self):
        ctx = _ctx(
            ability_level=2, comprehension_level=2,
            hard_stop_count=1,
        )
        t = engine.assess_trust_state(ctx)
        # 1.0 - 0.1*1 = 0.9
        assert t.trust_score == 0.9

    def test_hard_stop_penalty_caps(self):
        """HARD_STOP_PENALTY_CAP_LEVELS caps the contribution at 2."""
        ctx = _ctx(
            ability_level=2, comprehension_level=2,
            hard_stop_count=10,  # would be -1.0 uncapped
        )
        t = engine.assess_trust_state(ctx)
        # 1.0 - 0.1*2 = 0.8 (capped at 2)
        assert t.trust_score == 0.8

    def test_score_floor_at_zero(self):
        ctx = _ctx(
            ability_level=3, comprehension_level=0,   # gap=3 → -0.6
            hard_stop_count=10,                       # capped → -0.2
            last_action_acknowledged=False,           # -0.2
        )
        t = engine.assess_trust_state(ctx)
        # 1.0 - 0.6 - 0.2 - 0.2 = 0.0
        assert t.trust_score == 0.0

    def test_score_in_unit_interval(self):
        for ability in range(schemas.MAX_LEVEL + 1):
            for comprehension in range(schemas.MAX_LEVEL + 1):
                for stops in (0, 1, 2, 5, 100):
                    for ack in (True, False):
                        ctx = _ctx(
                            ability_level=ability,
                            comprehension_level=comprehension,
                            hard_stop_count=stops,
                            last_action_acknowledged=ack,
                        )
                        t = engine.assess_trust_state(ctx)
                        assert 0.0 <= t.trust_score <= 1.0


# ===========================================================================
# G. Understanding gap
# ===========================================================================
class TestUnderstandingGap:
    def test_zero_gap_when_aligned(self):
        ctx = _ctx(ability_level=2, comprehension_level=2)
        t = engine.assess_trust_state(ctx)
        assert t.understanding_gap == 0

    def test_positive_gap_when_ability_ahead(self):
        ctx = _ctx(ability_level=3, comprehension_level=1)
        t = engine.assess_trust_state(ctx)
        assert t.understanding_gap == 2

    def test_clipped_to_zero_when_comprehension_ahead(self):
        """If comprehension > ability, gap is clipped to 0, not negative."""
        ctx = _ctx(ability_level=1, comprehension_level=3)
        t = engine.assess_trust_state(ctx)
        assert t.understanding_gap == 0


# ===========================================================================
# H. Momentum (invariant 1: trust gaps never stop momentum)
# ===========================================================================
class TestMomentum:
    def test_momentum_intact_when_no_hard_stops(self):
        ctx = _ctx(ability_level=2, comprehension_level=2)
        t = engine.assess_trust_state(ctx)
        assert t.momentum_intact is True

    def test_momentum_broken_only_by_hard_stop(self):
        ctx = _ctx(hard_stop_count=1)
        t = engine.assess_trust_state(ctx)
        assert t.momentum_intact is False

    def test_understanding_gap_does_not_break_momentum(self):
        """Invariant 1: trust gaps never stop momentum."""
        ctx = _ctx(ability_level=3, comprehension_level=0)  # gap=3
        t = engine.assess_trust_state(ctx)
        assert t.momentum_intact is True

    def test_unacknowledged_does_not_break_momentum(self):
        """Invariant 1: only hard stops break momentum."""
        ctx = _ctx(last_action_acknowledged=False)
        t = engine.assess_trust_state(ctx)
        assert t.momentum_intact is True


# ===========================================================================
# I. repair_needed semantics (SPEC § 6.2)
# ===========================================================================
class TestRepairNeeded:
    def test_no_repair_when_in_rhythm(self):
        ctx = _ctx(ability_level=2, comprehension_level=2)
        t = engine.assess_trust_state(ctx)
        assert t.repair_needed is False

    def test_repair_at_gap_tolerance_edge(self):
        """gap >= GAP_TOLERANCE triggers preventive repair."""
        ctx = _ctx(ability_level=2, comprehension_level=1)  # gap=1
        t = engine.assess_trust_state(ctx)
        assert t.repair_needed is True

    def test_repair_over_gap_tolerance(self):
        ctx = _ctx(ability_level=3, comprehension_level=1)  # gap=2
        t = engine.assess_trust_state(ctx)
        assert t.repair_needed is True

    def test_repair_when_unacknowledged(self):
        ctx = _ctx(last_action_acknowledged=False)
        t = engine.assess_trust_state(ctx)
        assert t.repair_needed is True

    def test_repair_when_hard_stop(self):
        ctx = _ctx(hard_stop_count=1)
        t = engine.assess_trust_state(ctx)
        assert t.repair_needed is True


# ===========================================================================
# J. verify_no_hard_stops
# ===========================================================================
class TestVerifyNoHardStops:
    def test_passes_when_no_hard_stops(self):
        ctx = _ctx()
        m = engine.verify_no_hard_stops(ctx)
        assert m.passes_invariant is True
        assert m.hard_stop_detected is False
        assert m.hard_stop_count == 0

    def test_fails_when_hard_stop_present(self):
        ctx = _ctx(hard_stop_count=1)
        m = engine.verify_no_hard_stops(ctx)
        assert m.passes_invariant is False
        assert m.hard_stop_detected is True
        assert m.hard_stop_count == 1

    def test_passthrough_of_ack_field(self):
        ctx = _ctx(last_action_acknowledged=False)
        m = engine.verify_no_hard_stops(ctx)
        assert m.last_action_acknowledged is False


# ===========================================================================
# K. verify_comprehension_leads_action (invariant 2)
# ===========================================================================
class TestVerifyComprehensionLeadsAction:
    def test_passes_when_comprehension_matches_ability(self):
        ctx = _ctx(ability_level=2, comprehension_level=2)
        u = engine.verify_comprehension_leads_action(ctx)
        assert u.passes_invariant is True
        assert u.gap == 0

    def test_passes_at_edge_gap_one(self):
        """comprehension == ability - 1 still satisfies invariant 2."""
        ctx = _ctx(ability_level=2, comprehension_level=1)
        u = engine.verify_comprehension_leads_action(ctx)
        assert u.passes_invariant is True
        assert u.gap == 1

    def test_fails_when_gap_exceeds_tolerance(self):
        ctx = _ctx(ability_level=3, comprehension_level=1)
        u = engine.verify_comprehension_leads_action(ctx)
        assert u.passes_invariant is False
        assert u.gap == 2

    def test_clipped_when_comprehension_ahead(self):
        ctx = _ctx(ability_level=0, comprehension_level=3)
        u = engine.verify_comprehension_leads_action(ctx)
        assert u.gap == 0
        assert u.passes_invariant is True


# ===========================================================================
# L. gentle_repair priority order (SPEC § 7)
# ===========================================================================
class TestGentleRepairPriority:
    def test_no_repair_short_circuits_to_none(self):
        ctx = _ctx(ability_level=2, comprehension_level=2)
        t = engine.assess_trust_state(ctx)
        r = engine.gentle_repair(t, ctx)
        assert r.kind == schemas.RepairKind.NONE

    def test_hard_stop_wins_over_everything(self):
        """Priority 1 — RE_ANCHOR fires even when other triggers also hold."""
        ctx = _ctx(
            ability_level=3, comprehension_level=0,  # gap=3
            last_action_acknowledged=False,
            hard_stop_count=2,
        )
        t = engine.assess_trust_state(ctx)
        r = engine.gentle_repair(t, ctx)
        assert r.kind == schemas.RepairKind.RE_ANCHOR

    def test_gap_over_tolerance_emits_slow_pace(self):
        """Priority 2 — SLOW_PACE when gap > GAP_TOLERANCE and no hard stop."""
        ctx = _ctx(ability_level=3, comprehension_level=1)  # gap=2
        t = engine.assess_trust_state(ctx)
        r = engine.gentle_repair(t, ctx)
        assert r.kind == schemas.RepairKind.SLOW_PACE

    def test_unacknowledged_emits_offer_choice(self):
        """Priority 3 — OFFER_CHOICE when ack=False and no higher trigger."""
        ctx = _ctx(
            ability_level=2, comprehension_level=2,
            last_action_acknowledged=False,
        )
        t = engine.assess_trust_state(ctx)
        r = engine.gentle_repair(t, ctx)
        assert r.kind == schemas.RepairKind.OFFER_CHOICE

    def test_gap_at_edge_emits_narrow_scope(self):
        """Priority 4 — NARROW_SCOPE when gap == GAP_TOLERANCE."""
        ctx = _ctx(ability_level=2, comprehension_level=1)  # gap=1
        t = engine.assess_trust_state(ctx)
        r = engine.gentle_repair(t, ctx)
        assert r.kind == schemas.RepairKind.NARROW_SCOPE

    def test_slow_pace_beats_offer_choice(self):
        """gap > tolerance overrides unacknowledged."""
        ctx = _ctx(
            ability_level=3, comprehension_level=1,  # gap=2
            last_action_acknowledged=False,
        )
        t = engine.assess_trust_state(ctx)
        r = engine.gentle_repair(t, ctx)
        assert r.kind == schemas.RepairKind.SLOW_PACE

    def test_offer_choice_beats_narrow_scope(self):
        """ack=False overrides gap-at-edge."""
        ctx = _ctx(
            ability_level=2, comprehension_level=1,   # gap=1
            last_action_acknowledged=False,
        )
        t = engine.assess_trust_state(ctx)
        r = engine.gentle_repair(t, ctx)
        assert r.kind == schemas.RepairKind.OFFER_CHOICE

    def test_rationale_is_canonical(self):
        """RepairDirective.rationale comes from the locked table."""
        ctx = _ctx(ability_level=3, comprehension_level=1)
        t = engine.assess_trust_state(ctx)
        r = engine.gentle_repair(t, ctx)
        assert r.rationale == engine._RATIONALE[r.kind]

    @pytest.mark.parametrize("kind", list(schemas.RepairKind))
    def test_every_kind_has_canonical_rationale(self, kind):
        assert kind in engine._RATIONALE
        assert isinstance(engine._RATIONALE[kind], str)
        assert len(engine._RATIONALE[kind]) > 0


# ===========================================================================
# M. Worked examples (SPEC § 9)
# ===========================================================================
class TestWorkedExamples:
    def test_91_in_rhythm(self):
        ctx = _ctx(
            ability_level=2, comprehension_level=2,
            concept_exposures=(
                _exposure("envelope", 3),
                _exposure("pressure", 2),
            ),
        )
        t = engine.assess_trust_state(ctx)
        r = engine.gentle_repair(t, ctx)
        assert t.understanding_gap == 0
        assert t.momentum_intact is True
        assert t.trust_score == 1.0
        assert t.repair_needed is False
        assert r.kind == schemas.RepairKind.NONE

    def test_92_ability_one_rank_ahead(self):
        ctx = _ctx(ability_level=2, comprehension_level=1)
        t = engine.assess_trust_state(ctx)
        u = engine.verify_comprehension_leads_action(ctx)
        r = engine.gentle_repair(t, ctx)
        assert u.passes_invariant is True   # gap=1 still passes
        assert t.understanding_gap == 1
        assert t.momentum_intact is True
        assert t.trust_score == 0.8
        assert t.repair_needed is True       # preventive
        assert r.kind == schemas.RepairKind.NARROW_SCOPE

    def test_93_ability_two_ranks_ahead(self):
        ctx = _ctx(ability_level=3, comprehension_level=1)
        t = engine.assess_trust_state(ctx)
        u = engine.verify_comprehension_leads_action(ctx)
        r = engine.gentle_repair(t, ctx)
        assert u.passes_invariant is False   # gap=2 breaks invariant
        assert t.understanding_gap == 2
        assert t.momentum_intact is True
        assert t.trust_score == 0.6
        assert t.repair_needed is True
        assert r.kind == schemas.RepairKind.SLOW_PACE

    def test_94_unacknowledged(self):
        ctx = _ctx(
            ability_level=2, comprehension_level=2,
            last_action_acknowledged=False,
        )
        t = engine.assess_trust_state(ctx)
        r = engine.gentle_repair(t, ctx)
        assert t.understanding_gap == 0
        assert t.momentum_intact is True
        assert t.trust_score == 0.8
        assert t.repair_needed is True
        assert r.kind == schemas.RepairKind.OFFER_CHOICE

    def test_95_hard_stop(self):
        ctx = _ctx(
            ability_level=2, comprehension_level=2,
            hard_stop_count=1,
        )
        t = engine.assess_trust_state(ctx)
        m = engine.verify_no_hard_stops(ctx)
        r = engine.gentle_repair(t, ctx)
        assert m.passes_invariant is False
        assert m.hard_stop_detected is True
        assert t.momentum_intact is False
        assert t.trust_score == 0.9
        assert t.repair_needed is True
        assert r.kind == schemas.RepairKind.RE_ANCHOR

    def test_96_compound_worst_case(self):
        ctx = _ctx(
            ability_level=3, comprehension_level=1,    # gap=2
            hard_stop_count=2,                          # -0.2 (capped)
            last_action_acknowledged=False,             # -0.2
        )
        t = engine.assess_trust_state(ctx)
        r = engine.gentle_repair(t, ctx)
        assert t.understanding_gap == 2
        assert t.momentum_intact is False
        # 1.0 - 0.4 - 0.2 - 0.2 = 0.2
        assert t.trust_score == 0.2
        assert t.repair_needed is True
        # Hard-stop has priority 1, beats SLOW_PACE/OFFER_CHOICE.
        assert r.kind == schemas.RepairKind.RE_ANCHOR


# ===========================================================================
# N. Determinism
# ===========================================================================
class TestDeterminism:
    def test_assess_byte_equal(self):
        ctx = _ctx(
            ability_level=3, comprehension_level=1,
            hard_stop_count=1, last_action_acknowledged=False,
        )
        t1 = engine.assess_trust_state(ctx)
        t2 = engine.assess_trust_state(ctx)
        assert t1 == t2

    def test_verify_no_hard_stops_byte_equal(self):
        ctx = _ctx(hard_stop_count=2)
        m1 = engine.verify_no_hard_stops(ctx)
        m2 = engine.verify_no_hard_stops(ctx)
        assert m1 == m2

    def test_verify_comprehension_leads_action_byte_equal(self):
        ctx = _ctx(ability_level=3, comprehension_level=0)
        u1 = engine.verify_comprehension_leads_action(ctx)
        u2 = engine.verify_comprehension_leads_action(ctx)
        assert u1 == u2

    def test_gentle_repair_byte_equal(self):
        ctx = _ctx(ability_level=3, comprehension_level=1)
        t = engine.assess_trust_state(ctx)
        r1 = engine.gentle_repair(t, ctx)
        r2 = engine.gentle_repair(t, ctx)
        assert r1 == r2

    def test_marker_in_concept_id_rejected(self):
        """Invariant 8: rationale never propagates user text.

        Concept ids are restricted to the canonical set, so even an
        attempt to inject a marker via concept_id is rejected at the
        engine boundary."""
        marker = "ZxYxQwertUniqueMarker7777"
        bad = schemas.ConceptExposure(concept_id=marker, count=1)
        ctx = _ctx(concept_exposures=(bad,))
        with pytest.raises(ValueError):
            engine.assess_trust_state(ctx)


# ===========================================================================
# O. Source-code invariants
# ===========================================================================
class TestSourceCodeInvariants:
    def _src(self, mod) -> str:
        return inspect.getsource(mod)

    def test_no_llm_imports_in_engine(self):
        src = self._src(engine)
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src, f"engine must not import {forbidden}"

    def test_no_llm_imports_in_schemas(self):
        src = self._src(schemas)
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_no_network_imports_in_engine(self):
        src = self._src(engine)
        for forbidden in ("import urllib", "import http",
                          "import requests", "import socket",
                          "from urllib", "from http", "from requests"):
            assert forbidden not in src

    def test_no_randomness_imports_in_engine(self):
        src = self._src(engine)
        for forbidden in ("import random", "from random",
                          "import secrets", "from secrets"):
            assert forbidden not in src

    def test_no_io_in_engine(self):
        src = self._src(engine)
        for forbidden in ("open(", "Path(", "pathlib", "os.path",
                          "json.load", "json.dump", "subprocess",
                          "exec(", "eval("):
            assert forbidden not in src

    def test_no_send_patterns_in_engine(self):
        """Invariant 12: Ambient Trust is advisory only — no send patterns."""
        src = self._src(engine)
        for forbidden in (".post(", ".put(", ".send(", "urlopen(",
                          "requests.", "smtplib"):
            assert forbidden not in src

    def test_engine_does_not_branch_on_exposure_count(self):
        """Invariant 3: concept exposure counters never gate behavior.

        We assert the engine source contains no comparison/branching
        directly off `.count` from ConceptExposure. This is a coarse
        check — the canonical guarantee is that no public function in
        the engine inspects `.count` for control flow.
        """
        src = self._src(engine)
        # Allowed: reading exposure.concept_id for validation.
        # Disallowed: any branch on exposure.count.
        for forbidden in ("exposure.count >", "exposure.count <",
                          "exposure.count ==", "exposure.count !=",
                          "exposure.count >=", "exposure.count <="):
            assert forbidden not in src, (
                f"engine must not branch on exposure.count: {forbidden}"
            )


# ===========================================================================
# P. Module surface
# ===========================================================================
class TestModuleSurface:
    def test_schemas_exports(self):
        for name in (
            # Constants
            "MAX_LEVEL", "GAP_TOLERANCE",
            "SCORE_PENALTY_PER_GAP_LEVEL",
            "SCORE_PENALTY_PER_HARD_STOP",
            "SCORE_PENALTY_UNACKNOWLEDGED",
            "HARD_STOP_PENALTY_CAP_LEVELS",
            "CANONICAL_CONCEPT_IDS",
            # Enums
            "RepairKind",
            # Types
            "ConceptExposure", "SessionContext",
            "TrustState", "UnderstandingCheck",
            "MomentumCheck", "RepairDirective",
            # Guards / helpers
            "assert_ambient_trust_privacy_contract",
            "assert_ambient_trust_field_sets_canonical",
            "assert_repair_kinds_canonical",
            "assert_canonical_concept_ids",
            "is_canonical_concept_id",
        ):
            assert hasattr(schemas, name), f"missing in schemas: {name}"

    def test_engine_exports(self):
        for name in (
            "assess_trust_state",
            "verify_no_hard_stops",
            "verify_comprehension_leads_action",
            "gentle_repair",
        ):
            assert hasattr(engine, name)
            assert callable(getattr(engine, name))


# ===========================================================================
# Q. Invariant cross-checks
# ===========================================================================
class TestInvariantCrossChecks:
    def test_invariant_1_trust_gaps_never_break_momentum(self):
        """For every combination of trust-gap conditions, momentum_intact
        depends ONLY on hard_stop_count."""
        for ability in range(schemas.MAX_LEVEL + 1):
            for comprehension in range(schemas.MAX_LEVEL + 1):
                for ack in (True, False):
                    ctx = _ctx(
                        ability_level=ability,
                        comprehension_level=comprehension,
                        last_action_acknowledged=ack,
                        hard_stop_count=0,
                    )
                    t = engine.assess_trust_state(ctx)
                    assert t.momentum_intact is True, (
                        f"momentum broken at ability={ability} "
                        f"comp={comprehension} ack={ack} (no hard stop)"
                    )

    def test_invariant_2_understanding_check_at_edge(self):
        """comprehension == ability - GAP_TOLERANCE is the edge; passes."""
        for ability in range(1, schemas.MAX_LEVEL + 1):
            ctx = _ctx(
                ability_level=ability,
                comprehension_level=ability - schemas.GAP_TOLERANCE,
            )
            u = engine.verify_comprehension_leads_action(ctx)
            assert u.passes_invariant is True

    def test_invariant_6_determinism(self):
        ctx = _ctx(
            ability_level=3, comprehension_level=1,
            hard_stop_count=1, last_action_acknowledged=False,
        )
        r1 = engine.assess_trust_state(ctx)
        r2 = engine.assess_trust_state(ctx)
        assert r1 == r2

    def test_invariant_9_score_in_unit_interval(self):
        """For every reachable input, trust_score ∈ [0, 1]."""
        for ability in range(schemas.MAX_LEVEL + 1):
            for comprehension in range(schemas.MAX_LEVEL + 1):
                for stops in (0, 1, 2, 100):
                    for ack in (True, False):
                        ctx = _ctx(
                            ability_level=ability,
                            comprehension_level=comprehension,
                            hard_stop_count=stops,
                            last_action_acknowledged=ack,
                        )
                        t = engine.assess_trust_state(ctx)
                        assert 0.0 <= t.trust_score <= 1.0

    def test_invariant_10_no_halt_emitted(self):
        """gentle_repair never emits a halt-like directive — for any
        SessionContext the returned RepairKind is one of the five
        canonical kinds, none of which halt."""
        for ability in range(schemas.MAX_LEVEL + 1):
            for comprehension in range(schemas.MAX_LEVEL + 1):
                for stops in (0, 1, 2):
                    for ack in (True, False):
                        ctx = _ctx(
                            ability_level=ability,
                            comprehension_level=comprehension,
                            hard_stop_count=stops,
                            last_action_acknowledged=ack,
                        )
                        t = engine.assess_trust_state(ctx)
                        r = engine.gentle_repair(t, ctx)
                        assert r.kind in schemas.RepairKind


# ===========================================================================
# R. Constant locks (changes here are deliberate spec changes)
# ===========================================================================
class TestConstantLocks:
    def test_max_level(self):
        assert schemas.MAX_LEVEL == 3

    def test_gap_tolerance(self):
        assert schemas.GAP_TOLERANCE == 1

    def test_score_penalty_per_gap_level(self):
        assert schemas.SCORE_PENALTY_PER_GAP_LEVEL == 0.2

    def test_score_penalty_per_hard_stop(self):
        assert schemas.SCORE_PENALTY_PER_HARD_STOP == 0.1

    def test_score_penalty_unacknowledged(self):
        assert schemas.SCORE_PENALTY_UNACKNOWLEDGED == 0.2

    def test_hard_stop_penalty_cap_levels(self):
        assert schemas.HARD_STOP_PENALTY_CAP_LEVELS == 2
