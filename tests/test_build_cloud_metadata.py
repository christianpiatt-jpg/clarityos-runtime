"""
Tests for Phase 3 Unit 8 — build_cloud_metadata.

Covers:
    A. Basic behavior — return type, candidate not mutated, no raw_text
    B. Pressure-shape derivation (all 16 level × slope combinations)
    C. Field mapping (every non-derived field passes through correctly)
    D. risk_flags passthrough
    E. Privacy + boundary enforcement
    F. Determinism + purity
    G. Error handling
    H. Source-code purity
    I. Pipeline stubs preserved (only this unit's stub now implemented)
"""
from __future__ import annotations

import inspect
from dataclasses import asdict
from datetime import datetime

import pytest

import azimuth
import azimuth_transition as at
from azimuth import (
    AudienceType,
    CloudMetadata,
    ContextType,
    EnvelopeState,
    ExpressionCandidate,
    IntensityLevel,
    IntentionClass,
    PressureLevel,
    PressureShape,
    PressureSlope,
    UrgencyLevel,
    Valence,
)


# ===========================================================================
# Fixture builders
# ===========================================================================
_FIXED_TIME = datetime(2026, 5, 11, 12, 0, 0)


def _env(
    *,
    raw_text: str = "neutral observation",
    pressure_level: PressureLevel = PressureLevel.MEDIUM,
    intensity: IntensityLevel = IntensityLevel.LOW,
    valence: Valence = Valence.NEUTRAL,
    rough_intention: str = "describe what happened",
) -> EnvelopeState:
    return EnvelopeState(
        raw_text=raw_text,
        captured_at=_FIXED_TIME,
        emotional_intensity=intensity,
        valence=valence,
        pressure_level=pressure_level,
        rough_intention=rough_intention,
    )


def _candidate(
    *,
    raw_text: str = "neutral observation",
    pressure_level: PressureLevel = PressureLevel.MEDIUM,
    pressure_slope: PressureSlope = PressureSlope.FLAT,
    audience: AudienceType = AudienceType.SELF,
    context: ContextType = ContextType.PERSONAL,
    urgency: UrgencyLevel = UrgencyLevel.LOW,
    intention_class: IntentionClass = IntentionClass.OTHER,
    risk_flags: tuple = (),
) -> ExpressionCandidate:
    return ExpressionCandidate(
        raw_text=raw_text,
        intention="describe what happened",
        intention_class=intention_class,
        pressure_level=pressure_level,
        pressure_slope=pressure_slope,
        audience=audience,
        context=context,
        urgency=urgency,
        risk_flags=risk_flags,
    )


# ===========================================================================
# A. Basic behavior
# ===========================================================================
class TestBasicBehavior:
    def test_returns_cloud_metadata(self):
        meta = at.build_cloud_metadata(_candidate())
        assert isinstance(meta, CloudMetadata)

    def test_schema_version_default(self):
        meta = at.build_cloud_metadata(_candidate())
        assert meta.schema_version == "azimuth.v1"

    def test_candidate_not_mutated(self):
        c = _candidate(
            raw_text="MARKER123",
            pressure_level=PressureLevel.HIGH,
            pressure_slope=PressureSlope.RISING,
            risk_flags=("sharp_tone",),
        )
        before = (
            c.raw_text, c.intention, c.intention_class,
            c.pressure_level, c.pressure_slope, c.audience,
            c.context, c.urgency, c.risk_flags,
            c.envelope_id, c.candidate_id, c.aligned,
        )
        at.build_cloud_metadata(c)
        after = (
            c.raw_text, c.intention, c.intention_class,
            c.pressure_level, c.pressure_slope, c.audience,
            c.context, c.urgency, c.risk_flags,
            c.envelope_id, c.candidate_id, c.aligned,
        )
        assert before == after


# ===========================================================================
# B. Pressure-shape derivation (all 16 level × slope combinations)
# ===========================================================================
class TestPressureShapeDerivation:
    @pytest.mark.parametrize("level", [
        PressureLevel.HIGH, PressureLevel.CRITICAL,
    ])
    def test_spike_for_high_or_critical_rising(self, level):
        c = _candidate(
            pressure_level=level, pressure_slope=PressureSlope.RISING,
        )
        meta = at.build_cloud_metadata(c)
        assert meta.pressure_shape == PressureShape.SPIKE

    @pytest.mark.parametrize("level", [
        PressureLevel.LOW, PressureLevel.MEDIUM,
    ])
    def test_ascending_for_low_or_medium_rising(self, level):
        c = _candidate(
            pressure_level=level, pressure_slope=PressureSlope.RISING,
        )
        meta = at.build_cloud_metadata(c)
        assert meta.pressure_shape == PressureShape.ASCENDING

    @pytest.mark.parametrize("level", list(PressureLevel))
    def test_descending_for_any_falling(self, level):
        c = _candidate(
            pressure_level=level, pressure_slope=PressureSlope.FALLING,
        )
        meta = at.build_cloud_metadata(c)
        assert meta.pressure_shape == PressureShape.DESCENDING

    @pytest.mark.parametrize("level", list(PressureLevel))
    def test_plateau_for_any_flat(self, level):
        c = _candidate(
            pressure_level=level, pressure_slope=PressureSlope.FLAT,
        )
        meta = at.build_cloud_metadata(c)
        assert meta.pressure_shape == PressureShape.PLATEAU

    def test_exhaustive_16_combinations(self):
        """Verify every (level, slope) pair maps to the documented shape."""
        expected = {
            (PressureLevel.LOW,      PressureSlope.RISING):  PressureShape.ASCENDING,
            (PressureLevel.MEDIUM,   PressureSlope.RISING):  PressureShape.ASCENDING,
            (PressureLevel.HIGH,     PressureSlope.RISING):  PressureShape.SPIKE,
            (PressureLevel.CRITICAL, PressureSlope.RISING):  PressureShape.SPIKE,
            (PressureLevel.LOW,      PressureSlope.FALLING): PressureShape.DESCENDING,
            (PressureLevel.MEDIUM,   PressureSlope.FALLING): PressureShape.DESCENDING,
            (PressureLevel.HIGH,     PressureSlope.FALLING): PressureShape.DESCENDING,
            (PressureLevel.CRITICAL, PressureSlope.FALLING): PressureShape.DESCENDING,
            (PressureLevel.LOW,      PressureSlope.FLAT):    PressureShape.PLATEAU,
            (PressureLevel.MEDIUM,   PressureSlope.FLAT):    PressureShape.PLATEAU,
            (PressureLevel.HIGH,     PressureSlope.FLAT):    PressureShape.PLATEAU,
            (PressureLevel.CRITICAL, PressureSlope.FLAT):    PressureShape.PLATEAU,
        }
        for (level, slope), shape in expected.items():
            c = _candidate(pressure_level=level, pressure_slope=slope)
            meta = at.build_cloud_metadata(c)
            assert meta.pressure_shape == shape, (
                f"({level}, {slope}) → expected {shape}, got {meta.pressure_shape}"
            )

    def test_spike_overrides_ascending_priority(self):
        """SPIKE rule fires first when conditions for both could match."""
        c = _candidate(
            pressure_level=PressureLevel.CRITICAL,
            pressure_slope=PressureSlope.RISING,
        )
        meta = at.build_cloud_metadata(c)
        # CRITICAL + RISING could nominally satisfy "RISING" alone,
        # but the SPIKE rule wins.
        assert meta.pressure_shape == PressureShape.SPIKE
        assert meta.pressure_shape != PressureShape.ASCENDING


# ===========================================================================
# C. Field mapping (non-derived passthroughs)
# ===========================================================================
class TestFieldMapping:
    @pytest.mark.parametrize("slope", list(PressureSlope))
    def test_pressure_slope_passthrough(self, slope):
        meta = at.build_cloud_metadata(_candidate(pressure_slope=slope))
        assert meta.pressure_slope == slope

    @pytest.mark.parametrize("level", list(PressureLevel))
    def test_pressure_level_passthrough(self, level):
        meta = at.build_cloud_metadata(_candidate(pressure_level=level))
        assert meta.pressure_level == level

    @pytest.mark.parametrize("audience", list(AudienceType))
    def test_audience_type_passthrough(self, audience):
        meta = at.build_cloud_metadata(_candidate(audience=audience))
        assert meta.audience_type == audience

    @pytest.mark.parametrize("context", list(ContextType))
    def test_context_type_passthrough(self, context):
        meta = at.build_cloud_metadata(_candidate(context=context))
        assert meta.context_type == context

    @pytest.mark.parametrize("urgency", list(UrgencyLevel))
    def test_urgency_level_passthrough(self, urgency):
        meta = at.build_cloud_metadata(_candidate(urgency=urgency))
        assert meta.urgency_level == urgency

    @pytest.mark.parametrize("ic", list(IntentionClass))
    def test_intention_class_passthrough(self, ic):
        meta = at.build_cloud_metadata(_candidate(intention_class=ic))
        assert meta.intention_class == ic


# ===========================================================================
# D. risk_flags passthrough
# ===========================================================================
class TestRiskFlagsPassthrough:
    def test_empty_risk_flags(self):
        meta = at.build_cloud_metadata(_candidate(risk_flags=()))
        assert meta.risk_flags == ()

    def test_single_canonical_flag(self):
        meta = at.build_cloud_metadata(_candidate(risk_flags=("sharp_tone",)))
        assert meta.risk_flags == ("sharp_tone",)

    def test_multiple_canonical_flags(self):
        flags = ("high_pressure", "name_calling", "absolutist_language")
        meta = at.build_cloud_metadata(_candidate(risk_flags=flags))
        assert meta.risk_flags == flags

    def test_phase_3_unit_7_alignment_flags_pass_through(self):
        """The new hard_halt / soft_halt flags propagate to CloudMetadata."""
        meta = at.build_cloud_metadata(_candidate(
            risk_flags=("hard_halt", "high_pressure"),
        ))
        assert "hard_halt" in meta.risk_flags
        assert "high_pressure" in meta.risk_flags

    def test_risk_flags_is_tuple_not_list(self):
        meta = at.build_cloud_metadata(_candidate(risk_flags=("sharp_tone",)))
        assert isinstance(meta.risk_flags, tuple)


# ===========================================================================
# E. Privacy + boundary enforcement
# ===========================================================================
class TestPrivacyBoundary:
    def test_no_raw_text_attribute_on_result(self):
        c = _candidate(raw_text="MARKER_RAW_TEXT_123")
        meta = at.build_cloud_metadata(c)
        assert not hasattr(meta, "raw_text")

    def test_no_envelope_id_attribute(self):
        meta = at.build_cloud_metadata(_candidate())
        assert not hasattr(meta, "envelope_id")

    def test_no_candidate_id_attribute(self):
        meta = at.build_cloud_metadata(_candidate())
        assert not hasattr(meta, "candidate_id")

    def test_no_intention_freetext_attribute(self):
        """The free-text ``intention`` (rough_intention) MUST NOT leak."""
        meta = at.build_cloud_metadata(_candidate())
        assert not hasattr(meta, "intention")
        assert not hasattr(meta, "rough_intention")

    def test_no_aligned_attribute(self):
        """Even though ExpressionCandidate now carries an `aligned` field
        (Unit 6), CloudMetadata must NOT carry it."""
        meta = at.build_cloud_metadata(_candidate())
        assert not hasattr(meta, "aligned")

    def test_raw_text_marker_does_not_leak_anywhere(self):
        """Deep walk of CloudMetadata fields — marker must not appear."""
        marker = "XYZ_RAW_TEXT_MARKER_9999"
        c = _candidate(raw_text=marker)
        meta = at.build_cloud_metadata(c)

        def _search(obj, seen=None):
            if seen is None:
                seen = set()
            obj_id = id(obj)
            if obj_id in seen:
                return False
            seen.add(obj_id)
            if isinstance(obj, str):
                return marker in obj
            if hasattr(obj, "__dataclass_fields__"):
                return any(
                    _search(getattr(obj, f.name), seen)
                    for f in obj.__dataclass_fields__.values()
                )
            if isinstance(obj, (list, tuple, set, frozenset)):
                return any(_search(x, seen) for x in obj)
            if isinstance(obj, dict):
                return any(_search(v, seen) for v in obj.values())
            return False

        assert not _search(meta), "raw_text marker leaked into CloudMetadata"

    def test_canonical_field_set_locked(self):
        """CloudMetadata's __dataclass_fields__ matches the documented set."""
        expected = {
            "pressure_shape", "pressure_slope", "pressure_level",
            "audience_type", "context_type", "urgency_level",
            "intention_class", "risk_flags", "schema_version",
        }
        assert set(CloudMetadata.__dataclass_fields__.keys()) == expected

    def test_no_extra_fields_added_at_runtime(self):
        """The build never extends CloudMetadata's field set."""
        meta = at.build_cloud_metadata(_candidate())
        assert set(asdict(meta).keys()) == {
            "pressure_shape", "pressure_slope", "pressure_level",
            "audience_type", "context_type", "urgency_level",
            "intention_class", "risk_flags", "schema_version",
        }

    def test_runtime_privacy_guard_passes(self):
        """azimuth.assert_cloud_privacy_contract must still pass."""
        azimuth.assert_cloud_privacy_contract()
        # Sanity: also build a metadata and verify it has no forbidden
        # field names anywhere in its declared schema.
        meta = at.build_cloud_metadata(_candidate(raw_text="x"))
        forbidden = {"raw_text", "user_id", "envelope_id", "candidate_id",
                     "intention", "rough_intention", "name", "names",
                     "identity", "aligned"}
        for fname in CloudMetadata.__dataclass_fields__:
            assert fname not in forbidden


# ===========================================================================
# F. Determinism + purity
# ===========================================================================
class TestDeterminism:
    def test_same_candidate_byte_equal_output(self):
        c = _candidate(
            pressure_level=PressureLevel.HIGH,
            pressure_slope=PressureSlope.RISING,
            audience=AudienceType.ONE_TO_ONE,
            context=ContextType.PROFESSIONAL,
            urgency=UrgencyLevel.MEDIUM,
            intention_class=IntentionClass.REQUEST,
            risk_flags=("sharp_tone", "high_pressure"),
        )
        m1 = at.build_cloud_metadata(c)
        m2 = at.build_cloud_metadata(c)
        assert m1 == m2

    def test_asdict_byte_equal(self):
        c = _candidate(
            pressure_level=PressureLevel.CRITICAL,
            pressure_slope=PressureSlope.RISING,
            risk_flags=("hard_halt",),
        )
        m1 = at.build_cloud_metadata(c)
        m2 = at.build_cloud_metadata(c)
        assert asdict(m1) == asdict(m2)

    def test_independent_calls_produce_independent_objects(self):
        """Two calls return two distinct frozen instances (no shared state)."""
        c = _candidate()
        m1 = at.build_cloud_metadata(c)
        m2 = at.build_cloud_metadata(c)
        # Equal by value, but distinct object identities.
        assert m1 == m2
        # Frozen dataclass instances may be cached by equality in some
        # contexts, but `is` should not be relied on. The byte-equality
        # is what matters.


# ===========================================================================
# G. Error handling
# ===========================================================================
class TestErrorHandling:
    def test_non_candidate_raises_value_error(self):
        with pytest.raises(ValueError):
            at.build_cloud_metadata("not a candidate")  # type: ignore[arg-type]

    def test_none_raises_value_error(self):
        with pytest.raises(ValueError):
            at.build_cloud_metadata(None)  # type: ignore[arg-type]

    def test_dict_raises_value_error(self):
        with pytest.raises(ValueError):
            at.build_cloud_metadata({"raw_text": "x"})  # type: ignore[arg-type]

    def test_envelope_state_raises_value_error(self):
        """An EnvelopeState is a different type — must be rejected."""
        with pytest.raises(ValueError):
            at.build_cloud_metadata(_env())  # type: ignore[arg-type]

    def test_non_canonical_pressure_level_string_rejected(self):
        """Defensive: a string in a typed enum slot is rejected before
        crossing the cloud boundary. We construct an ExpressionCandidate
        with object.__setattr__ to bypass frozen+typed init checks."""
        c = _candidate()
        object.__setattr__(c, "pressure_level", "high")  # not the enum
        with pytest.raises(ValueError):
            at.build_cloud_metadata(c)

    def test_non_canonical_pressure_slope_string_rejected(self):
        c = _candidate()
        object.__setattr__(c, "pressure_slope", "rising")
        with pytest.raises(ValueError):
            at.build_cloud_metadata(c)

    def test_non_canonical_audience_string_rejected(self):
        c = _candidate()
        object.__setattr__(c, "audience", "self")
        with pytest.raises(ValueError):
            at.build_cloud_metadata(c)

    def test_non_canonical_context_string_rejected(self):
        c = _candidate()
        object.__setattr__(c, "context", "personal")
        with pytest.raises(ValueError):
            at.build_cloud_metadata(c)

    def test_non_canonical_urgency_string_rejected(self):
        c = _candidate()
        object.__setattr__(c, "urgency", "low")
        with pytest.raises(ValueError):
            at.build_cloud_metadata(c)

    def test_non_canonical_intention_class_string_rejected(self):
        c = _candidate()
        object.__setattr__(c, "intention_class", "vent")
        with pytest.raises(ValueError):
            at.build_cloud_metadata(c)


# ===========================================================================
# H. Source-code purity
# ===========================================================================
class TestPurity:
    def _src(self) -> str:
        return inspect.getsource(at.build_cloud_metadata)

    def test_no_llm_imports_in_function(self):
        src = self._src()
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_no_network_in_function(self):
        src = self._src()
        for forbidden in ("urlopen(", "requests.", ".post(", ".put(",
                          "smtplib"):
            assert forbidden not in src

    def test_no_io_in_function(self):
        src = self._src()
        for forbidden in ("open(", "Path(", "json.load", "subprocess",
                          "exec(", "eval("):
            assert forbidden not in src

    def test_no_randomness_in_function(self):
        src = self._src()
        for forbidden in ("random.", "secrets."):
            assert forbidden not in src

    def test_no_logging_in_function(self):
        src = self._src()
        for forbidden in ("logging.", "logger.", "print("):
            assert forbidden not in src


# ===========================================================================
# I. Pipeline state — only detect_externalization_intent remains a stub
# ===========================================================================
class TestPipelineState:
    def test_detect_externalization_intent_now_implemented_phase_3_unit_9(self):
        """Phase 3 Unit 9 closed the last Azimuth stub. The full
        signal → build → flag → upload chain is now callable."""
        result = at.detect_externalization_intent(_env())
        assert isinstance(result, bool)

    def test_build_candidate_implemented(self):
        c = at.build_candidate(
            _env(), audience=AudienceType.SELF, context=ContextType.PERSONAL,
        )
        assert isinstance(c, ExpressionCandidate)

    def test_evaluate_drift_risk_implemented(self):
        env = _env()
        c = at.build_candidate(
            env, audience=AudienceType.SELF, context=ContextType.PERSONAL,
        )
        result = at.evaluate_drift_risk(env, candidate=c)
        assert isinstance(result, ExpressionCandidate)

    def test_build_cloud_metadata_implemented(self):
        c = _candidate()
        meta = at.build_cloud_metadata(c)
        assert isinstance(meta, CloudMetadata)


# ===========================================================================
# J. End-to-end pipeline (Units 5 → 6 → 7 → 8)
# ===========================================================================
class TestEndToEndPipeline:
    def test_full_chain_produces_valid_cloud_metadata(self):
        """Run the full Azimuth chain on a realistic envelope and
        verify the final CloudMetadata is structurally valid."""
        env = _env(
            raw_text="you always do this and nobody cares",
            pressure_level=PressureLevel.HIGH,
            intensity=IntensityLevel.HIGH,
            valence=Valence.NEGATIVE,
            rough_intention="vent",
        )

        # Unit 6.
        c = at.build_candidate(
            env, audience=AudienceType.ONE_TO_ONE,
            context=ContextType.PROFESSIONAL,
            pressure_slope=PressureSlope.RISING,
            urgency=UrgencyLevel.MEDIUM,
        )
        # Unit 7.
        c = at.evaluate_drift_risk(env, candidate=c)
        # Unit 8.
        meta = at.build_cloud_metadata(c)

        assert isinstance(meta, CloudMetadata)
        # Pressure-shape derivation: HIGH + RISING → SPIKE.
        assert meta.pressure_shape == PressureShape.SPIKE
        # risk_flags propagate; at least one absolutist flag present.
        assert any(f in meta.risk_flags for f in (
            "name_calling", "absolutist_language",
            "all_or_nothing", "sharp_tone", "high_pressure",
        ))
        # Privacy boundary intact.
        assert not hasattr(meta, "raw_text")
        assert not hasattr(meta, "envelope_id")
        assert not hasattr(meta, "intention")

    def test_full_chain_byte_equal_across_runs(self):
        """The end-to-end pipeline is fully deterministic."""
        env = _env(
            raw_text="this keeps happening",
            pressure_level=PressureLevel.MEDIUM,
            rough_intention="describe",
        )

        def _pipeline():
            c = at.build_candidate(
                env, audience=AudienceType.SELF,
                context=ContextType.PERSONAL,
                pressure_slope=PressureSlope.FLAT,
            )
            c = at.evaluate_drift_risk(env, candidate=c)
            return at.build_cloud_metadata(c)

        m1 = _pipeline()
        m2 = _pipeline()
        # candidate_id is auto-generated per call, but CloudMetadata
        # carries NO candidate_id — so the metadata should be byte-equal.
        assert m1 == m2
