"""
Structural tests for the Minimal Orchestrator schema module
(Phase 3 design).

These verify the C/D/G/I/S contract, dataclass shapes, enum values,
and skeleton invariants WITHOUT depending on any implementation.

The minimal-orchestrator contract is enforced STRUCTURALLY here — any
future PR that:
    * drops a C/D/G/I/S field from PropagationState
    * drops constraints/identity/drift/geometry from ContextEnvelope
    * introduces mutable global state in any orchestrator module
fails this suite.

Behavior tests (routing logic, drift computation, checkpoint stream,
etc.) land when the real implementations ship in subsequent units.
"""
from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone

import pytest

import orchestrator_context
import orchestrator_routing
import orchestrator_schemas as schemas
import orchestrator_workflows


# ===========================================================================
# Enums — canonical values locked
# ===========================================================================
class TestEnums:
    def test_severity_values(self):
        assert {v.value for v in schemas.Severity} == {
            "advisory", "required", "absolute",
        }

    def test_enforcement_mode_values(self):
        assert {v.value for v in schemas.EnforcementMode} == {
            "allow_with_warning", "halt", "require_human_override",
        }

    def test_drift_axis_values(self):
        assert {v.value for v in schemas.DriftAxis} == {
            "intent", "tone", "scope", "identity", "timeline",
        }

    def test_actor_kind_values(self):
        assert {v.value for v in schemas.ActorKind} == {
            "user", "agent", "system",
        }

    def test_sovereignty_level_values(self):
        assert {v.value for v in schemas.SovereigntyLevel} == {
            "user_owned", "delegated", "agent_only",
        }

    def test_authorization_tier_values(self):
        assert {v.value for v in schemas.AuthorizationTier} == {
            "read", "observe", "propose", "execute",
        }

    def test_workflow_status_values(self):
        assert {v.value for v in schemas.WorkflowStatus} == {
            "pending", "running", "completed", "halted",
            "pending_human_review",
        }


# ===========================================================================
# Constants
# ===========================================================================
class TestConstants:
    def test_default_drift_threshold_is_float_in_range(self):
        thr = schemas.DEFAULT_DRIFT_THRESHOLD
        assert isinstance(thr, float)
        assert 0.0 < thr <= 1.0

    def test_invariants_canonical_includes_cdgi(self):
        names = set(schemas.INVARIANTS_CANONICAL)
        # The canonical invariant list MUST cover C/D/G/I.
        assert "constitutional_constraints_intact" in names
        assert "drift_within_bounds"               in names
        assert "geometry_within_stability_budget"  in names
        assert "identity_unchanged_or_delegated"   in names
        assert "no_constraint_dropped"             in names


# ===========================================================================
# C — ConstitutionalConstraint
# ===========================================================================
def _make_constraint() -> schemas.ConstitutionalConstraint:
    return schemas.ConstitutionalConstraint(
        rule_id="C1",
        statement="No upload of raw text outside user-authorized boundaries",
        severity=schemas.Severity.ABSOLUTE,
        enforcement=schemas.EnforcementMode.HALT,
        scope=("elins_run", "azimuth"),
        rationale="Privacy boundary",
    )


class TestConstitutionalConstraint:
    def test_instantiable(self):
        c = _make_constraint()
        assert c.rule_id == "C1"
        assert c.severity == schemas.Severity.ABSOLUTE

    def test_frozen(self):
        c = _make_constraint()
        with pytest.raises(FrozenInstanceError):
            c.severity = schemas.Severity.ADVISORY  # type: ignore[misc]

    def test_minimal_required_fields_present(self):
        names = set(schemas.ConstitutionalConstraint.__dataclass_fields__.keys())
        for required in ("rule_id", "statement", "severity",
                         "enforcement", "scope", "rationale"):
            assert required in names


# ===========================================================================
# D — DriftState
# ===========================================================================
def _make_drift(magnitude: float = 0.18, in_bounds: bool = True) -> schemas.DriftState:
    return schemas.DriftState(
        axis=schemas.DriftAxis.INTENT,
        magnitude=magnitude,
        direction="slight broadening of scope",
        baseline_anchor="session_start",
        in_bounds=in_bounds,
        measured_at=datetime.now(timezone.utc),
    )


class TestDriftState:
    def test_instantiable(self):
        d = _make_drift()
        assert d.magnitude == 0.18
        assert d.in_bounds is True

    def test_frozen(self):
        d = _make_drift()
        with pytest.raises(FrozenInstanceError):
            d.magnitude = 0.5  # type: ignore[misc]

    def test_minimal_required_fields_present(self):
        names = set(schemas.DriftState.__dataclass_fields__.keys())
        for required in ("axis", "magnitude", "direction",
                         "baseline_anchor", "in_bounds", "measured_at"):
            assert required in names


# ===========================================================================
# G — GeometryProfile
# ===========================================================================
def _make_geometry(stability: float = 0.82) -> schemas.GeometryProfile:
    return schemas.GeometryProfile(
        depth=1,
        breadth=1,
        pressure_load=0.2,
        stability_score=stability,
        captured_at=datetime.now(timezone.utc),
    )


class TestGeometryProfile:
    def test_instantiable(self):
        g = _make_geometry()
        assert g.depth == 1
        assert g.stability_score == 0.82

    def test_frozen(self):
        g = _make_geometry()
        with pytest.raises(FrozenInstanceError):
            g.stability_score = 0.0  # type: ignore[misc]


# ===========================================================================
# I — IdentityProfile
# ===========================================================================
def _make_identity() -> schemas.IdentityProfile:
    return schemas.IdentityProfile(
        actor="alice",
        actor_kind=schemas.ActorKind.USER,
        sovereignty_level=schemas.SovereigntyLevel.USER_OWNED,
        authorization_tier=schemas.AuthorizationTier.EXECUTE,
        session_id="sess_local_test",
    )


class TestIdentityProfile:
    def test_instantiable(self):
        i = _make_identity()
        assert i.actor == "alice"
        assert i.authorization_tier == schemas.AuthorizationTier.EXECUTE

    def test_frozen(self):
        i = _make_identity()
        with pytest.raises(FrozenInstanceError):
            i.actor = "bob"  # type: ignore[misc]

    def test_session_id_is_local_only(self):
        """The schema documents session_id as local-only; the test
        asserts it's a plain string field (no upload mechanism baked
        into the type)."""
        f = {f.name: f for f in fields(schemas.IdentityProfile)}["session_id"]
        assert f.type is str or f.type == "str"


# ===========================================================================
# S — PropagationState — THE C/D/G/I/S CONTRACT
# ===========================================================================
def _make_propagation() -> schemas.PropagationState:
    return schemas.PropagationState(
        from_step="s1",
        to_step="s2",
        active_constraints=(_make_constraint(),),
        drift_state=_make_drift(),
        geometry_profile=_make_geometry(),
        identity_profile=_make_identity(),
        invariants_preserved=("constitutional_constraints_intact",
                              "drift_within_bounds"),
    )


class TestPropagationStateCDGIS:
    """The single most important contract in the orchestrator:
    PropagationState MUST carry C, D, G, I, S references."""

    def test_active_constraints_field_present_C(self):
        assert "active_constraints" in schemas.PropagationState.__dataclass_fields__

    def test_drift_state_field_present_D(self):
        assert "drift_state" in schemas.PropagationState.__dataclass_fields__

    def test_geometry_profile_field_present_G(self):
        assert "geometry_profile" in schemas.PropagationState.__dataclass_fields__

    def test_identity_profile_field_present_I(self):
        assert "identity_profile" in schemas.PropagationState.__dataclass_fields__

    def test_invariants_preserved_field_present_S(self):
        assert "invariants_preserved" in schemas.PropagationState.__dataclass_fields__

    def test_runtime_guard_passes(self):
        schemas.assert_propagation_contract()  # must not raise

    def test_required_field_set_matches_canonical(self):
        required = schemas._REQUIRED_PROPAGATION_FIELDS
        actual = set(schemas.PropagationState.__dataclass_fields__.keys())
        assert required.issubset(actual), (
            f"Missing C/D/G/I/S fields: {required - actual}"
        )

    def test_instantiable(self):
        p = _make_propagation()
        assert p.from_step == "s1"
        assert p.propagation_id  # auto-generated

    def test_frozen(self):
        p = _make_propagation()
        with pytest.raises(FrozenInstanceError):
            p.from_step = "x"  # type: ignore[misc]

    def test_propagation_id_unique_per_instance(self):
        p1 = _make_propagation()
        p2 = _make_propagation()
        assert p1.propagation_id != p2.propagation_id


# ===========================================================================
# ContextEnvelope — C/D/G/I contract
# ===========================================================================
def _make_request() -> schemas.RoutingRequest:
    return schemas.RoutingRequest(
        request_id="req_test",
        request_type="elins_run",
        payload={"text": "ignored by tests"},
        identity=_make_identity(),
        arrived_at=datetime.now(timezone.utc),
    )


def _make_plan() -> schemas.ExecutionPlan:
    return schemas.ExecutionPlan(
        plan_id="plan_test",
        steps=(
            schemas.ExecutionStep(
                step_id="s1", action="prepare",
                inputs={}, constraints=(_make_constraint(),),
            ),
        ),
        overall_constraints=(_make_constraint(),),
        created_at=datetime.now(timezone.utc),
    )


def _make_context() -> schemas.ContextEnvelope:
    return schemas.ContextEnvelope(
        request=_make_request(),
        plan=_make_plan(),
        constraints=(_make_constraint(),),
        identity=_make_identity(),
        drift=_make_drift(),
        geometry=_make_geometry(),
    )


class TestContextEnvelopeContract:
    def test_constraints_field_present(self):
        assert "constraints" in schemas.ContextEnvelope.__dataclass_fields__

    def test_identity_field_present(self):
        assert "identity" in schemas.ContextEnvelope.__dataclass_fields__

    def test_drift_field_present(self):
        assert "drift" in schemas.ContextEnvelope.__dataclass_fields__

    def test_geometry_field_present(self):
        assert "geometry" in schemas.ContextEnvelope.__dataclass_fields__

    def test_runtime_guard_passes(self):
        schemas.assert_context_contract()  # must not raise

    def test_instantiable(self):
        ctx = _make_context()
        assert ctx.identity.actor == "alice"

    def test_frozen(self):
        ctx = _make_context()
        with pytest.raises(FrozenInstanceError):
            ctx.identity = _make_identity()  # type: ignore[misc]


# ===========================================================================
# Supporting types — RoutingDecision, ExecutionPlan, HaltState, etc.
# ===========================================================================
class TestRoutingDecision:
    def test_instantiable_and_frozen(self):
        d = schemas.RoutingDecision(
            request_id="req_test",
            selected_agent="elins_agent",
            rationale="capability match + ABSOLUTE satisfied",
            constraints_attached=(_make_constraint(),),
            decided_at=datetime.now(timezone.utc),
        )
        assert d.selected_agent == "elins_agent"
        with pytest.raises(FrozenInstanceError):
            d.selected_agent = "x"  # type: ignore[misc]


class TestExecutionPlan:
    def test_overall_constraints_present(self):
        plan = _make_plan()
        assert len(plan.overall_constraints) >= 1


class TestViolationAndHaltState:
    def test_violation_instantiable(self):
        v = schemas.Violation(
            constraint_id="C1",
            severity=schemas.Severity.ABSOLUTE,
            detected_at_step="s2",
            description="scope exceeded",
            detected_at=datetime.now(timezone.utc),
        )
        assert v.severity == schemas.Severity.ABSOLUTE

    def test_halt_state_carries_propagation(self):
        h = schemas.HaltState(
            workflow_id="wf_test",
            halted_at_step="s2",
            violation=schemas.Violation(
                constraint_id="C1",
                severity=schemas.Severity.ABSOLUTE,
                detected_at_step="s2",
                description="x",
                detected_at=datetime.now(timezone.utc),
            ),
            propagation_at_halt=_make_propagation(),
            requires_human_override=True,
            halted_at=datetime.now(timezone.utc),
        )
        assert h.requires_human_override is True
        # The halt-state's propagation carries C/D/G/I/S
        prop_fields = set(h.propagation_at_halt.__dataclass_fields__.keys())
        for cdgis in schemas._REQUIRED_PROPAGATION_FIELDS:
            assert cdgis in prop_fields


class TestCheckpointToken:
    def test_carries_propagation_state(self):
        token = schemas.CheckpointToken(
            workflow_id="wf_test",
            step_id="s1",
            propagation=_make_propagation(),
        )
        assert token.snapshot_id  # auto-generated
        # Propagation carries C/D/G/I/S
        assert token.propagation.active_constraints
        assert token.propagation.drift_state is not None
        assert token.propagation.geometry_profile is not None
        assert token.propagation.identity_profile is not None


class TestWorkflowResult:
    def test_completed_result(self):
        r = schemas.WorkflowResult(
            workflow_id="wf_test",
            status=schemas.WorkflowStatus.COMPLETED,
            final_propagation=_make_propagation(),
            checkpoints=(),
            completed_at=datetime.now(timezone.utc),
        )
        assert r.status == schemas.WorkflowStatus.COMPLETED
        assert r.halt_state is None

    def test_halted_result(self):
        halt = schemas.HaltState(
            workflow_id="wf_test",
            halted_at_step="s2",
            violation=schemas.Violation(
                constraint_id="C1",
                severity=schemas.Severity.REQUIRED,
                detected_at_step="s2",
                description="x",
                detected_at=datetime.now(timezone.utc),
            ),
            propagation_at_halt=_make_propagation(),
            requires_human_override=True,
            halted_at=datetime.now(timezone.utc),
        )
        r = schemas.WorkflowResult(
            workflow_id="wf_test",
            status=schemas.WorkflowStatus.HALTED,
            final_propagation=_make_propagation(),
            checkpoints=(),
            halt_state=halt,
        )
        assert r.halt_state is not None
        assert r.halt_state.requires_human_override is True


# ===========================================================================
# Composite runtime guard
# ===========================================================================
class TestRuntimeGuards:
    def test_assert_minimal_orchestrator_contract_passes(self):
        schemas.assert_minimal_orchestrator_contract()

    def test_assert_propagation_contract_independent(self):
        schemas.assert_propagation_contract()

    def test_assert_context_contract_independent(self):
        schemas.assert_context_contract()


# ===========================================================================
# Skeleton invariants — every function raises NotImplementedError
# ===========================================================================
class TestSkeletonsRaise:
    def test_routing_route_request_skeleton(self):
        with pytest.raises(NotImplementedError):
            orchestrator_routing.route_request(
                _make_request(), (), (),
            )

    def test_routing_select_agent_skeleton(self):
        with pytest.raises(NotImplementedError):
            orchestrator_routing.select_agent(
                "elins_run", _make_identity(), (), (),
            )

    def test_routing_build_execution_plan_skeleton(self):
        decision = schemas.RoutingDecision(
            request_id="r", selected_agent="a",
            rationale="", constraints_attached=(),
            decided_at=datetime.now(timezone.utc),
        )
        with pytest.raises(NotImplementedError):
            orchestrator_routing.build_execution_plan(decision)

    def test_context_assemble_skeleton(self):
        with pytest.raises(NotImplementedError):
            orchestrator_context.assemble_context(
                _make_request(), _make_plan(), _make_identity(),
                _make_drift(), _make_geometry(),
            )

    def test_context_attach_constraints_skeleton(self):
        with pytest.raises(NotImplementedError):
            orchestrator_context.attach_constraints(_make_context(), ())

    def test_context_load_drift_state_skeleton(self):
        with pytest.raises(NotImplementedError):
            orchestrator_context.load_drift_state(
                "alice", (), "session_start",
            )

    def test_workflows_run_workflow_skeleton(self):
        with pytest.raises(NotImplementedError):
            orchestrator_workflows.run_workflow(
                _make_plan(), _make_context(),
                lambda step, ctx: {},  # dummy runner
            )

    def test_workflows_checkpoint_skeleton(self):
        with pytest.raises(NotImplementedError):
            orchestrator_workflows.checkpoint({})

    def test_workflows_halt_for_violation_skeleton(self):
        v = schemas.Violation(
            constraint_id="C1",
            severity=schemas.Severity.ABSOLUTE,
            detected_at_step="s1",
            description="x",
            detected_at=datetime.now(timezone.utc),
        )
        with pytest.raises(NotImplementedError):
            orchestrator_workflows.halt_for_violation({}, v)


# ===========================================================================
# Module surface — every documented symbol importable
# ===========================================================================
class TestModuleSurface:
    def test_schemas_exports(self):
        for name in (
            # Enums
            "Severity", "EnforcementMode", "DriftAxis", "ActorKind",
            "SovereigntyLevel", "AuthorizationTier", "WorkflowStatus",
            # C/D/G/I/S core types
            "ConstitutionalConstraint", "DriftState", "GeometryProfile",
            "IdentityProfile", "PropagationState",
            # Supporting types
            "RoutingRequest", "RoutingDecision", "AgentBinding",
            "ExecutionStep", "ExecutionPlan", "ContextEnvelope",
            "Violation", "CheckpointToken", "HaltState", "WorkflowResult",
            # Constants + guards
            "DEFAULT_DRIFT_THRESHOLD", "INVARIANTS_CANONICAL",
            "assert_propagation_contract", "assert_context_contract",
            "assert_minimal_orchestrator_contract",
        ):
            assert hasattr(schemas, name), f"missing in schemas: {name}"

    def test_routing_module_exports(self):
        for name in ("route_request", "select_agent", "build_execution_plan"):
            assert hasattr(orchestrator_routing, name)

    def test_context_module_exports(self):
        for name in ("assemble_context", "attach_constraints", "load_drift_state"):
            assert hasattr(orchestrator_context, name)

    def test_workflows_module_exports(self):
        for name in ("run_workflow", "checkpoint", "halt_for_violation"):
            assert hasattr(orchestrator_workflows, name)


# ===========================================================================
# Minimal-orchestrator invariants
# ===========================================================================
class TestMinimalOrchestratorInvariants:
    """Asserts what the orchestrator MUST NOT do."""

    def _module_source(self, mod) -> str:
        return inspect.getsource(mod)

    def test_no_llm_imports_in_routing(self):
        src = self._module_source(orchestrator_routing)
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src, (
                f"orchestrator_routing must not import {forbidden}"
            )

    def test_no_llm_imports_in_context(self):
        src = self._module_source(orchestrator_context)
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src, (
                f"orchestrator_context must not import {forbidden}"
            )

    def test_no_llm_imports_in_workflows(self):
        src = self._module_source(orchestrator_workflows)
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src, (
                f"orchestrator_workflows must not import {forbidden}"
            )

    def test_no_llm_imports_in_schemas(self):
        src = self._module_source(schemas)
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src, (
                f"orchestrator_schemas must not import {forbidden}"
            )

    def test_no_network_imports_in_orchestrator(self):
        for mod in (schemas, orchestrator_routing,
                    orchestrator_context, orchestrator_workflows):
            src = self._module_source(mod)
            for forbidden in ("import urllib", "import http",
                              "import requests", "import socket",
                              "from urllib", "from http",
                              "from requests"):
                assert forbidden not in src, (
                    f"{mod.__name__} must not import network libs ({forbidden})"
                )

    def test_no_module_level_mutable_state(self):
        """Module-level state must be tuples / frozensets / constants —
        no list / dict / set globals that could be mutated."""
        for mod in (orchestrator_routing, orchestrator_context,
                    orchestrator_workflows):
            for name, value in vars(mod).items():
                if name.startswith("_") or callable(value):
                    continue
                # Allow modules, type aliases, classes
                if inspect.ismodule(value) or inspect.isclass(value):
                    continue
                assert not isinstance(value, (list, dict, set)), (
                    f"{mod.__name__}.{name} is mutable global state ({type(value).__name__})"
                )

    def test_schemas_module_load_runs_guards(self):
        """The schemas module runs the structural guards at load.
        Reaching this point means the guards already passed once."""
        # If the module loaded, the guards passed. This test just
        # confirms the function exists and is callable.
        assert callable(schemas.assert_minimal_orchestrator_contract)


# ===========================================================================
# Cross-module type compatibility
# ===========================================================================
class TestCrossModuleTypes:
    def test_propagation_in_checkpoint_in_halt_in_result(self):
        """The full chain — Propagation → Checkpoint → HaltState →
        WorkflowResult — round-trips through the type system."""
        prop = _make_propagation()
        token = schemas.CheckpointToken(
            workflow_id="wf", step_id="s1", propagation=prop,
        )
        v = schemas.Violation(
            constraint_id="C1", severity=schemas.Severity.REQUIRED,
            detected_at_step="s2", description="x",
            detected_at=datetime.now(timezone.utc),
        )
        halt = schemas.HaltState(
            workflow_id="wf", halted_at_step="s2",
            violation=v, propagation_at_halt=prop,
            requires_human_override=True,
            halted_at=datetime.now(timezone.utc),
        )
        result = schemas.WorkflowResult(
            workflow_id="wf",
            status=schemas.WorkflowStatus.HALTED,
            final_propagation=prop,
            checkpoints=(token,),
            halt_state=halt,
        )
        # End-to-end C/D/G/I/S preserved through all hops
        assert result.final_propagation.active_constraints == prop.active_constraints
        assert result.halt_state.propagation_at_halt.identity_profile == prop.identity_profile
        assert result.checkpoints[0].propagation.drift_state == prop.drift_state
