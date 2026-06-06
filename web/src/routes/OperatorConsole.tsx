// Card 40 — Operator Console (Phase-1 minimal).
//
// First UI-facing operator-layer surface. Pure developer/operator
// diagnostic panel — no styling beyond raw HTML, no charts, no
// components, no navigation changes. The operator pastes a
// multi-run-context JSON, clicks Load, and gets back:
//   - the lineage map (Card 34)
//   - the hydraulic evolution map (Card 35)
//   - the system overlay (Card 36)
//   - the system regression diff (Card 37) between two run indices
//
// All wiring goes through the Card 39 EngineV1OperatorAPI so the
// console is decoupled from the individual helper exports.
//
// The "multi-run context" input is a JSON document shaped like the
// EngineV1MultiRunContext from Card 29 (i.e. { runs: [ctx, ctx, ...] }
// where each ctx is an EngineV1OperatorContext snapshot). That matches
// the shape the Card 29 createMultiRunContext factory wraps.

import { useEffect, useMemo, useState } from "react";

import {
  createEngineV1OperatorAPI,
  type EngineV1MultiRunContext,
} from "../lib/api";
import { getApiBase } from "../lib/config";
import {
  summarizeHydraulicEvolution,
  summarizeLineageMap,
  summarizeRegression,
  summarizeSystemOverlay,
} from "../lib/operatorSummaries";
import { buildEvolutionTimeline } from "../lib/operatorTimeline";
import { buildDiffView } from "../lib/operatorDiff";
import { buildStructuralDiagnostics } from "../lib/operatorDiagnostics";
import { buildMultiRunStructuralOverlay } from "../lib/operatorStructuralOverlay";
import { buildStructuralMatrix } from "../lib/operatorStructuralMatrix";
import { buildStructuralHeatmap } from "../lib/operatorStructuralHeatmap";
import { buildStructuralBands } from "../lib/operatorStructuralBands";
import {
  buildStructuralSignature,
  extractStructuralSignatures,
} from "../lib/operatorStructuralSignature";
import { buildSignatureDiff, computeSignatureDiff } from "../lib/operatorSignatureDiff";
import { buildSignatureOverlay } from "../lib/operatorSignatureOverlay";
import { buildStructuralTrajectory } from "../lib/operatorStructuralTrajectory";
import { buildStructuralRisk } from "../lib/operatorStructuralRisk";
import { buildStructuralHotspots } from "../lib/operatorStructuralHotspots";
import { buildStructuralCausality } from "../lib/operatorStructuralCausality";
import { buildStructuralInterventions } from "../lib/operatorStructuralInterventions";
import { buildStructuralStabilization } from "../lib/operatorStructuralStabilization";
import { buildStructuralResilience } from "../lib/operatorStructuralResilience";
import { buildStructuralImmunity } from "../lib/operatorStructuralImmunity";
import { buildStructuralGovernance } from "../lib/operatorStructuralGovernance";
import { buildStructuralGovernanceDiff } from "../lib/operatorStructuralGovernanceDiff";
import { buildStructuralGovernanceStability } from "../lib/operatorStructuralGovernanceStability";
import { buildStructuralGovernanceResilience } from "../lib/operatorStructuralGovernanceResilience";
import { buildStructuralGovernanceImmunity } from "../lib/operatorStructuralGovernanceImmunity";
import { buildStructuralGovernanceCoherence } from "../lib/operatorStructuralGovernanceCoherence";
import { buildStructuralGovernanceSynthesis } from "../lib/operatorStructuralGovernanceSynthesis";
import { buildSystemLevelGovernance } from "../lib/operatorSystemLevelGovernance";
import { buildOperatorState } from "../lib/operatorState";
import { buildOperatorDiff } from "../lib/operatorStateDiff";
import { buildOperatorStability } from "../lib/operatorStability";
import { buildOperatorResilience } from "../lib/operatorResilience";
import { buildOperatorImmunity } from "../lib/operatorImmunity";
import { buildOperatorCoherence } from "../lib/operatorCoherence";
import { buildOperatorSynthesis } from "../lib/operatorSynthesis";
import { buildSystemOperatorIntegration } from "../lib/systemOperatorIntegration";
import { buildOperatorMetaPattern } from "../lib/operatorMetaPattern";
import { buildOperatorMetaStability } from "../lib/operatorMetaStability";
import { buildOperatorMetaResilience } from "../lib/operatorMetaResilience";
import { buildOperatorMetaImmunity } from "../lib/operatorMetaImmunity";
import { buildOperatorMetaIntegration } from "../lib/operatorMetaIntegration";
import { buildOperatorMetaAlignment } from "../lib/operatorMetaAlignment";
import { buildOperatorMetaCoherence } from "../lib/operatorMetaCoherence";
import { buildOperatorMetaSynthesis } from "../lib/operatorMetaSynthesis";
import { buildOperatorMetaConsolidation } from "../lib/operatorMetaConsolidation";
import { buildOperatorMetaCompression } from "../lib/operatorMetaCompression";
import { buildOperatorMetaReduction } from "../lib/operatorMetaReduction";
import { buildOperatorMetaExtraction } from "../lib/operatorMetaExtraction";
import { buildOperatorMetaDistillation } from "../lib/operatorMetaDistillation";
import { buildOperatorMetaEssence } from "../lib/operatorMetaEssence";
import { runSuperstructure } from "../lib/superstructure";

const PLACEHOLDER = `{
  "runs": []
}`;

// Phase 7 (Card 7.2B) — read-only telemetry tile. Shape mirrors the
// GET /operator/telemetry payload (CARD 7.2A); the console only displays
// the latest record + history count — it never computes or writes telemetry.
interface Phase7Latest {
  drift: number | null;
  coherence_health: number | null;
  trust_band: string | null;
}
interface Phase7Analytics {
  drift_velocity: number;
  drift_acceleration: number;
  coherence_trend: number;
  stability_forecast: number;
  trajectory: string;
}
interface CausalFactor {
  action: string;
  correlation: number;
  contribution: number;
}
// Phase 8.5 — causal-chain + motif shapes mirror the Phase 8.3/8.4
// /operator/telemetry payload (causal_chains + causal_motifs). Read-only:
// the console never computes these — the backend owns the reasoning.
interface CausalChainNode {
  id: string;
  type: string;
  label: string;
  timestamp: number | null;
  value: number | null;
}
interface CausalChainEdge {
  source: string;
  target: string;
  weight: number;
}
interface CausalChainMotifFlags {
  passes_bottleneck: boolean;
  passes_attractor: boolean;
  in_feedback_loop: boolean;
}
interface CausalChain {
  nodes: CausalChainNode[];
  edges: CausalChainEdge[];
  score: number;
  motifs: CausalChainMotifFlags;
}
interface CausalMotifs {
  feedback_loops: string[][];
  bottlenecks: string[];
  attractors: string[];
}
// Phase 8.7 — causal stability forecast shape (causal_stability). Loops and
// chain signatures are node-id sequences (string[]), mirroring the 8.6/8.7
// backend; influence/bottleneck drivers are plain node ids (string).
interface CausalStabilityDrivers {
  rising_influence: string[];
  falling_influence: string[];
  new_bottlenecks: string[];
  resolved_bottlenecks: string[];
  new_loops: string[][];
  resolved_loops: string[][];
  chain_strengthening: string[][];
  chain_weakening: string[][];
}
interface CausalStability {
  stability_score: number;
  trend: string;
  drivers: CausalStabilityDrivers;
}
// Phase 9.5 (Card 9.5) — behavioral-motif shapes mirror the Phase 9.4
// /operator/telemetry payload (behavioral_motifs). action_loops +
// trigger_chains are node/label sequences (rendered "a → b"); habits /
// action_bottlenecks / action_attractors are action labels / node ids.
// Read-only: the console never computes these — the backend owns the
// Phase-9 behavioral reasoning.
interface BehavioralMotifs {
  action_loops: string[][];
  trigger_chains: string[][];
  habits: string[];
  action_bottlenecks: string[];
  action_attractors: string[];
}
// Phase 10.4 (Card 10.4) — behavioral forecast envelope: the read-only 10.0-10.3
// outputs surfaced from /operator/telemetry.behavioral_forecast. The console
// only renders these — the backend (Phase 10) owns all forecast / delta /
// stability / narrative computation. The 10.1 deltas surface via the narrative's
// per-change `delta` fields (no standalone deltas section).
interface BFNextAction { action_id: string; label: string; score: number; drivers: string[]; }
interface BFHabitChange { action_id: string; trend: string; delta: number; }
interface BFTriggerChange { chain: string[]; delta: number; }
interface BFLoopChange { loop: string[]; continuation_probability: number; }
interface BFStabilityDrivers {
  habit_stability: number;
  trigger_stability: number;
  loop_persistence: number;
  action_variance: number;
}
interface BFStability { score: number; drivers: BFStabilityDrivers; }
interface BFHighlight { action_id: string; score: number; drivers: string[]; }
interface BehavioralForecast {
  forecast: { next_actions: BFNextAction[]; loop_continuation: BFLoopChange[] };
  stability: BFStability;
  narrative: {
    summary: string;
    habit_changes: BFHabitChange[];
    trigger_changes: BFTriggerChange[];
    forecast_highlights: BFHighlight[];
  };
}
// Phase 11.2 (Card 11.2) — recommendation narrative envelope: the read-only 11.0
// recommendations + 11.1 narrative (which embeds the drivers + stability
// context), surfaced from /operator/telemetry.recommendation_narrative.
// Render-only — the backend (Phase 11) owns all recommendation / narrative
// computation.
interface RecItem { action_id: string; label: string; reason: string; score: number; explanation: string; }
interface RecDriverEntry { action_id: string; metric: number; reason: string; }
interface RecStabilityDrivers {
  habit_stability: number;
  trigger_stability: number;
  loop_persistence: number;
  action_variance: number;
}
interface RecStability { score: number; drivers: RecStabilityDrivers; }
interface RecommendationNarrative {
  summary: string;
  recommendations: RecItem[];
  drivers: {
    habit: RecDriverEntry[];
    triggers: RecDriverEntry[];
    loops: RecDriverEntry[];
    bottlenecks: RecDriverEntry[];
    attractors: RecDriverEntry[];
    forecast_alignment: RecDriverEntry[];
  };
  stability_context: RecStability;
}
interface Phase7Telemetry {
  history: unknown[];
  latest: Phase7Latest | null;
  analytics: Phase7Analytics | null;
  alerts: string[] | null;
  causal_factors: CausalFactor[] | null;
  narrative: string | null;
  causal_chains: CausalChain[] | null;
  causal_motifs: CausalMotifs | null;
  causal_stability: CausalStability | null;
  unified_narrative: string | null;
  behavioral_motifs: BehavioralMotifs | null;
  behavioral_forecast: BehavioralForecast | null;
  recommendation_narrative: RecommendationNarrative | null;
}

// Phase 8.7 default — the empty/neutral stability forecast rendered before the
// mount fetch resolves (or when the backend omits the block).
const EMPTY_STABILITY: CausalStability = {
  stability_score: 0,
  trend: "—",
  drivers: {
    rising_influence: [],
    falling_influence: [],
    new_bottlenecks: [],
    resolved_bottlenecks: [],
    new_loops: [],
    resolved_loops: [],
    chain_strengthening: [],
    chain_weakening: [],
  },
};

// Phase 9.5 (Card 9.5) — empty behavioral-motif set rendered before the mount
// fetch resolves (or when the backend omits the block). Every family empty →
// the tile shows only its heading (all sections collapse).
const EMPTY_BEHAVIORAL_MOTIFS: BehavioralMotifs = {
  action_loops: [],
  trigger_chains: [],
  habits: [],
  action_bottlenecks: [],
  action_attractors: [],
};

// Phase 9.5 — a behavioral-motif section with > 10 rows becomes independently
// scrollable (deterministic, no animation). Mirrors the desktop "scrollable if
// > 10 items" rule; harmless on web.
const BEHAVIORAL_SCROLL = { maxHeight: "20rem", overflowY: "auto" } as const;

function formatPhase7Float(n: number | null | undefined): string {
  return typeof n === "number" ? n.toFixed(2) : "—";
}

export default function OperatorConsole() {
  const api = useMemo(() => createEngineV1OperatorAPI(), []);

  const [jsonText,  setJsonText]  = useState<string>(PLACEHOLDER);
  const [context,   setContext]   = useState<EngineV1MultiRunContext | null>(null);
  const [parseErr,  setParseErr]  = useState<string | null>(null);

  const [fromIndex, setFromIndex] = useState<number>(0);
  const [toIndex,   setToIndex]   = useState<number>(1);

  // Card 44 — Diff Viewer keeps its own from/to so an operator can
  // pin a regression comparison in the Card 37 section while
  // independently scanning other pairs in the diff tree.
  const [diffFromIndex, setDiffFromIndex] = useState<number>(0);
  const [diffToIndex,   setDiffToIndex]   = useState<number>(1);

  // Card 51 — Signature Diff keeps its own independent from/to so
  // an operator can compare arbitrary run pairs at the identity level.
  const [sigFromIndex, setSigFromIndex] = useState<number>(0);
  const [sigToIndex,   setSigToIndex]   = useState<number>(1);

  // Phase 7 (Card 7.2B) — fetch the durable telemetry once on mount and
  // surface the latest drift / coherence-health / trust-band + history
  // count. Read-only: the console never writes telemetry (Phase 7.1 owns
  // recording). Fetch failures leave the tile blank rather than throwing.
  const [phase7, setPhase7] = useState<Phase7Telemetry | null>(null);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${getApiBase()}/operator/telemetry`);
        if (!res.ok) return;
        const data = (await res.json()) as Phase7Telemetry;
        if (!cancelled) setPhase7(data);
      } catch {
        /* read-only tile — leave unset on failure */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  function handleLoad() {
    setParseErr(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(jsonText);
    } catch (e) {
      setParseErr(`JSON parse error: ${(e as Error).message}`);
      setContext(null);
      return;
    }
    // Minimal shape check; full validation lives in Card 29+.
    if (
      !parsed ||
      typeof parsed !== "object" ||
      !Array.isArray((parsed as { runs?: unknown }).runs)
    ) {
      setParseErr('Expected an object with a "runs" array.');
      setContext(null);
      return;
    }
    setContext(parsed as EngineV1MultiRunContext);
  }

  const lineageMap = useMemo(
    () => (context ? api.buildLineageMap(context) : null),
    [api, context],
  );
  const hydraulicEvolution = useMemo(
    () => (lineageMap ? api.buildHydraulicEvolution(lineageMap) : null),
    [api, lineageMap],
  );
  const systemOverlay = useMemo(
    () => (context ? api.buildSystemOverlay(context) : null),
    [api, context],
  );
  const regressionDiff = useMemo(() => {
    if (!systemOverlay) return null;
    const runCount = systemOverlay.hydraulicEvolution.perRun.length;
    if (
      !Number.isInteger(fromIndex) || fromIndex < 0 || fromIndex >= runCount ||
      !Number.isInteger(toIndex)   || toIndex   < 0 || toIndex   >= runCount
    ) {
      return null;
    }
    try {
      return api.computeSystemRegression(systemOverlay, fromIndex, toIndex);
    } catch (e) {
      return { error: (e as Error).message };
    }
  }, [api, systemOverlay, fromIndex, toIndex]);

  // Card 43 — pure text-only evolution timeline. The regression
  // callback is bound to the currently-loaded overlay so the timeline
  // helper itself stays surface-agnostic.
  const evolutionTimeline = useMemo(() => {
    if (!systemOverlay) return null;
    return buildEvolutionTimeline(
      systemOverlay,
      (from, to) => api.computeSystemRegression(systemOverlay, from, to),
    );
  }, [api, systemOverlay]);

  // Card 44 — hierarchical text-only diff for the Diff Viewer's own
  // from/to selection. Resolves to null on out-of-bounds indices so
  // the section can render a sentinel rather than crashing.
  const diffViewText = useMemo(() => {
    if (!systemOverlay) return null;
    const runCount = systemOverlay.hydraulicEvolution.perRun.length;
    if (
      !Number.isInteger(diffFromIndex) || diffFromIndex < 0 || diffFromIndex >= runCount ||
      !Number.isInteger(diffToIndex)   || diffToIndex   < 0 || diffToIndex   >= runCount
    ) {
      return null;
    }
    try {
      const d = api.computeSystemRegression(systemOverlay, diffFromIndex, diffToIndex);
      return buildDiffView(d, systemOverlay.lineageMap);
    } catch (e) {
      return `(error: ${(e as Error).message})`;
    }
  }, [api, systemOverlay, diffFromIndex, diffToIndex]);

  // Card 45 — system-level structural diagnostics. Reads from the
  // already-computed overlay / lineage / hydraulic-evolution memos so
  // there's no double-work; timeline is passed for signature parity
  // with future expansion.
  const structuralDiagnostics = useMemo(() => {
    if (!systemOverlay || !lineageMap || !hydraulicEvolution) return null;
    return buildStructuralDiagnostics(
      systemOverlay,
      evolutionTimeline ?? "",
      lineageMap,
      hydraulicEvolution,
    );
  }, [systemOverlay, lineageMap, hydraulicEvolution, evolutionTimeline]);

  // Card 46 — multi-run structural overlay. Flattens overlay +
  // lineage + hydraulic evolution into a single text snapshot.
  const multiRunStructuralOverlay = useMemo(() => {
    if (!systemOverlay || !lineageMap || !hydraulicEvolution) return null;
    return buildMultiRunStructuralOverlay(
      systemOverlay,
      lineageMap,
      hydraulicEvolution,
    );
  }, [systemOverlay, lineageMap, hydraulicEvolution]);

  // Card 47 — structural matrix (primitive × run grid with L/T/U
  // regime + C/B zone + */!/~ markers).
  const structuralMatrix = useMemo(() => {
    if (!systemOverlay || !lineageMap || !hydraulicEvolution) return null;
    return buildStructuralMatrix(
      systemOverlay,
      lineageMap,
      hydraulicEvolution,
    );
  }, [systemOverlay, lineageMap, hydraulicEvolution]);

  // Card 48 — structural heatmap (compressed intensity map with
  // pressure-score symbols + C/B/!/~ overlay flags).
  const structuralHeatmap = useMemo(() => {
    if (!systemOverlay || !lineageMap || !hydraulicEvolution) return null;
    return buildStructuralHeatmap(
      systemOverlay,
      lineageMap,
      hydraulicEvolution,
    );
  }, [systemOverlay, lineageMap, hydraulicEvolution]);

  // Card 49 — banded structural signature (run-level bands + system-
  // level phase bands + primitive-level bucket summary).
  const structuralBands = useMemo(() => {
    if (!systemOverlay || !lineageMap || !hydraulicEvolution) return null;
    return buildStructuralBands(
      systemOverlay,
      lineageMap,
      hydraulicEvolution,
      structuralHeatmap ?? "",
    );
  }, [systemOverlay, lineageMap, hydraulicEvolution, structuralHeatmap]);

  // Card 50 — system-wide structural fingerprint (per-run tokens +
  // signature string + 5 count signatures + phase-transition labels).
  const structuralSignature = useMemo(() => {
    if (!systemOverlay || !lineageMap || !hydraulicEvolution) return null;
    return buildStructuralSignature(
      systemOverlay,
      lineageMap,
      hydraulicEvolution,
      structuralHeatmap ?? "",
      structuralBands ?? "",
    );
  }, [systemOverlay, lineageMap, hydraulicEvolution, structuralHeatmap, structuralBands]);

  // Card 51 — per-run signature objects used as input to the diff
  // engine. Cached alongside the text signature so both views stay
  // consistent against the same underlying state.
  const perRunSignatures = useMemo(() => {
    if (!lineageMap || !hydraulicEvolution) return null;
    return extractStructuralSignatures(lineageMap, hydraulicEvolution);
  }, [lineageMap, hydraulicEvolution]);

  const signatureDiffText = useMemo(() => {
    if (!perRunSignatures) return null;
    const n = perRunSignatures.length;
    if (
      !Number.isInteger(sigFromIndex) || sigFromIndex < 0 || sigFromIndex >= n ||
      !Number.isInteger(sigToIndex)   || sigToIndex   < 0 || sigToIndex   >= n
    ) {
      return null;
    }
    return buildSignatureDiff(perRunSignatures[sigFromIndex], perRunSignatures[sigToIndex]);
  }, [perRunSignatures, sigFromIndex, sigToIndex]);

  // Card 52 — adjacent-pair structured diffs + synthesized overlay
  // covering signatures, diffs, 6 component overlays, identity-shift
  // overlay, and system-level synthesis.
  const adjacentSignatureDiffs = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0) return null;
    return perRunSignatures.slice(0, -1).map((from, i) =>
      computeSignatureDiff(from, perRunSignatures[i + 1]),
    );
  }, [perRunSignatures]);

  const signatureOverlayText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildSignatureOverlay(perRunSignatures, adjacentSignatureDiffs);
  }, [perRunSignatures, adjacentSignatureDiffs]);

  // Card 53 — structural trajectory: extrapolation-based projections
  // for hydraulic / pressure / counts / phase / identity, plus rule-
  // based risks + opportunities + summary.
  const structuralTrajectoryText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildStructuralTrajectory(
      perRunSignatures,
      adjacentSignatureDiffs,
      signatureOverlayText ?? "",
    );
  }, [perRunSignatures, adjacentSignatureDiffs, signatureOverlayText]);

  // Card 54 — structural risk: per-run + system-level risk grading
  // with rule-based classification + summary.
  const structuralRiskText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildStructuralRisk(
      perRunSignatures,
      adjacentSignatureDiffs,
      structuralTrajectoryText ?? "",
    );
  }, [perRunSignatures, adjacentSignatureDiffs, structuralTrajectoryText]);

  // Card 55 — structural hotspots: localization layer ranking runs +
  // dimensions, plus hotspot evolution / trajectory / summary.
  const structuralHotspotsText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildStructuralHotspots(
      perRunSignatures,
      adjacentSignatureDiffs,
      structuralRiskText ?? "",
    );
  }, [perRunSignatures, adjacentSignatureDiffs, structuralRiskText]);

  // Card 56 — structural causality: explanation layer producing per-
  // run cause chains, per-dimension causality, identity-shift root,
  // and a synthesized causal narrative.
  const structuralCausalityText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildStructuralCausality(
      perRunSignatures,
      adjacentSignatureDiffs,
      structuralHotspotsText ?? "",
    );
  }, [perRunSignatures, adjacentSignatureDiffs, structuralHotspotsText]);

  // Card 57 — structural interventions: action layer recommending
  // per-run, per-dimension, identity, and system-level operator
  // actions based on causal chains.
  const structuralInterventionsText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildStructuralInterventions(
      perRunSignatures,
      adjacentSignatureDiffs,
      structuralCausalityText ?? "",
    );
  }, [perRunSignatures, adjacentSignatureDiffs, structuralCausalityText]);

  // Card 58 — structural stabilization: recovery layer scoring
  // intervention effectiveness + projecting the stabilization window.
  const structuralStabilizationText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildStructuralStabilization(
      perRunSignatures,
      adjacentSignatureDiffs,
      structuralInterventionsText ?? "",
    );
  }, [perRunSignatures, adjacentSignatureDiffs, structuralInterventionsText]);

  // Card 59 — structural resilience: durability layer scoring the
  // system's projected ability to resist future instability.
  const structuralResilienceText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildStructuralResilience(
      perRunSignatures,
      adjacentSignatureDiffs,
      structuralStabilizationText ?? "",
    );
  }, [perRunSignatures, adjacentSignatureDiffs, structuralStabilizationText]);

  // Card 60 — structural immunity: prevention layer scoring the
  // system's ability to prevent future instability before it begins.
  const structuralImmunityText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildStructuralImmunity(
      perRunSignatures,
      adjacentSignatureDiffs,
      structuralResilienceText ?? "",
    );
  }, [perRunSignatures, adjacentSignatureDiffs, structuralResilienceText]);

  // Card 61 — structural governance: rules layer scoring how well
  // the system is holding the invariants that define structural safety.
  const structuralGovernanceText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildStructuralGovernance(
      perRunSignatures,
      adjacentSignatureDiffs,
      structuralImmunityText ?? "",
    );
  }, [perRunSignatures, adjacentSignatureDiffs, structuralImmunityText]);

  // Card 62 — prior-run governance text used as the "prev" side of
  // the governance diff. Pattern mirrors Card 51's two-state pin:
  // here, prev = governance computed on signatures excluding the
  // most recent run, next = full-history governance above.
  const prevGovernanceText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length < 2 || !adjacentSignatureDiffs) return null;
    const prevSigs  = perRunSignatures.slice(0, -1);
    const prevDiffs = adjacentSignatureDiffs.slice(0, -1);
    return buildStructuralGovernance(prevSigs, prevDiffs, structuralImmunityText ?? "");
  }, [perRunSignatures, adjacentSignatureDiffs, structuralImmunityText]);

  // Card 62 — structural governance diff: governance deltas tracking
  // how governance strength changes between the two most recent
  // governance states.
  const governanceDiffText = useMemo(() => {
    if (!structuralGovernanceText || !prevGovernanceText) return null;
    return buildStructuralGovernanceDiff(prevGovernanceText, structuralGovernanceText);
  }, [prevGovernanceText, structuralGovernanceText]);

  // Card 63 — structural governance stability: evaluates whether
  // governance is holding, weakening, or strengthening across time
  // by combining Card 61's current governance state with Card 62's
  // transition delta.
  const governanceStabilityText = useMemo(() => {
    if (!structuralGovernanceText || !governanceDiffText) return null;
    return buildStructuralGovernanceStability(structuralGovernanceText, governanceDiffText);
  }, [structuralGovernanceText, governanceDiffText]);

  // Card 64 — structural governance resilience: durability layer
  // scoring how well governance can withstand pressure and recover
  // from instability. Combines Card 61 + Card 62 + Card 63.
  const governanceResilienceText = useMemo(() => {
    if (!structuralGovernanceText || !governanceDiffText || !governanceStabilityText) return null;
    return buildStructuralGovernanceResilience(
      structuralGovernanceText,
      governanceDiffText,
      governanceStabilityText,
    );
  }, [structuralGovernanceText, governanceDiffText, governanceStabilityText]);

  // Card 65 — structural governance immunity: prevention layer
  // scoring how well governance can prevent future degradation.
  // Combines Card 61 + Card 62 + Card 63 + Card 64.
  const governanceImmunityText = useMemo(() => {
    if (
      !structuralGovernanceText || !governanceDiffText ||
      !governanceStabilityText  || !governanceResilienceText
    ) return null;
    return buildStructuralGovernanceImmunity(
      structuralGovernanceText,
      governanceDiffText,
      governanceStabilityText,
      governanceResilienceText,
    );
  }, [structuralGovernanceText, governanceDiffText, governanceStabilityText, governanceResilienceText]);

  // Card 66 — structural governance coherence: alignment layer
  // evaluating cross-dimension consistency, contradiction, and
  // whether the governance stack agrees with itself. Combines
  // Cards 61 + 62 + 63 + 64 + 65.
  const governanceCoherenceText = useMemo(() => {
    if (
      !structuralGovernanceText  || !governanceDiffText ||
      !governanceStabilityText   || !governanceResilienceText ||
      !governanceImmunityText
    ) return null;
    return buildStructuralGovernanceCoherence(
      structuralGovernanceText,
      governanceDiffText,
      governanceStabilityText,
      governanceResilienceText,
      governanceImmunityText,
    );
  }, [
    structuralGovernanceText, governanceDiffText, governanceStabilityText,
    governanceResilienceText, governanceImmunityText,
  ]);

  // Card 67 — structural governance synthesis: meta-layer unifying
  // all governance operators into a single integrated state. Final
  // governance card; combines Cards 61 + 62 + 63 + 64 + 65 + 66.
  const governanceSynthesisText = useMemo(() => {
    if (
      !structuralGovernanceText  || !governanceDiffText ||
      !governanceStabilityText   || !governanceResilienceText ||
      !governanceImmunityText    || !governanceCoherenceText
    ) return null;
    return buildStructuralGovernanceSynthesis(
      structuralGovernanceText,
      governanceDiffText,
      governanceStabilityText,
      governanceResilienceText,
      governanceImmunityText,
      governanceCoherenceText,
    );
  }, [
    structuralGovernanceText, governanceDiffText, governanceStabilityText,
    governanceResilienceText, governanceImmunityText, governanceCoherenceText,
  ]);

  // Card 68 — system-level governance: Phase-4 capstone, unifies
  // the entire governance stack (Cards 61-67) into a single top-
  // level system-wide evaluation. The "governance of governance".
  const systemGovernanceText = useMemo(() => {
    if (
      !structuralGovernanceText  || !governanceDiffText ||
      !governanceStabilityText   || !governanceResilienceText ||
      !governanceImmunityText    || !governanceCoherenceText ||
      !governanceSynthesisText
    ) return null;
    return buildSystemLevelGovernance(
      structuralGovernanceText,
      governanceDiffText,
      governanceStabilityText,
      governanceResilienceText,
      governanceImmunityText,
      governanceCoherenceText,
      governanceSynthesisText,
    );
  }, [
    structuralGovernanceText, governanceDiffText, governanceStabilityText,
    governanceResilienceText, governanceImmunityText, governanceCoherenceText,
    governanceSynthesisText,
  ]);

  // Card 69 — operator state: first Phase-5 operator-meta card.
  // The raw textarea text is the Card 39 pipeline input — the helper
  // parses `key=value` tokens embedded in it (load/drift/clarity/
  // stability/pressure/direction) and emits a single-pass operator
  // state assessment. Defaults to all-optimal baseline when no
  // tokens are present.
  const operatorStateText = useMemo(() => {
    return buildOperatorState(jsonText);
  }, [jsonText]);

  // Card 70 — operator diff: compares an empty-input baseline state
  // (the operator at full HIGH) to the current operator state, so
  // the diff surfaces how far the live trajectory has moved from
  // that baseline. Same pattern Cards 62/64+ used to derive a prev
  // state for governance diffs.
  const prevOperatorStateText = useMemo(() => {
    return buildOperatorState("");
  }, []);

  const operatorDiffText = useMemo(() => {
    return buildOperatorDiff(prevOperatorStateText, operatorStateText);
  }, [prevOperatorStateText, operatorStateText]);

  // Card 71 — operator stability: third Phase-5 card. Combines Card
  // 69 (state) + Card 70 (diff) into a 14-section stability layer
  // that evaluates the operator's internal equilibrium across drift,
  // clarity, load, pressure, and volatility.
  const operatorStabilityText = useMemo(() => {
    return buildOperatorStability(operatorStateText, operatorDiffText);
  }, [operatorStateText, operatorDiffText]);

  // Card 72 — operator resilience: fourth Phase-5 card. Combines
  // Cards 69 + 70 + 71 into a 14-section resilience layer that
  // evaluates the operator's capacity to recover from instability,
  // drift, pressure, and volatility.
  const operatorResilienceText = useMemo(() => {
    return buildOperatorResilience(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
    );
  }, [operatorStateText, operatorDiffText, operatorStabilityText]);

  // Card 73 — operator immunity: fifth Phase-5 card. Combines
  // Cards 69 + 70 + 71 + 72 into a 14-section immunity layer that
  // evaluates the operator's resistance to destabilizing forces —
  // the protective capacity, not just the recovery capacity.
  const operatorImmunityText = useMemo(() => {
    return buildOperatorImmunity(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
    );
  }, [operatorStateText, operatorDiffText, operatorStabilityText, operatorResilienceText]);

  // Card 74 — operator coherence: sixth Phase-5 card. Combines
  // Cards 69 + 70 + 71 + 72 + 73 into a 14-section coherence layer
  // that evaluates the operator's internal alignment, consistency,
  // and integrative clarity.
  const operatorCoherenceText = useMemo(() => {
    return buildOperatorCoherence(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
      operatorImmunityText,
    );
  }, [
    operatorStateText, operatorDiffText, operatorStabilityText,
    operatorResilienceText, operatorImmunityText,
  ]);

  // Card 75 — operator synthesis: seventh Phase-5 card. Combines
  // Cards 69 + 70 + 71 + 72 + 73 + 74 into a 14-section synthesis
  // layer — the unified, integrated read of the operator. The
  // capstone of the Phase-5 single-operator stack before Card 76's
  // System-Operator Integration meta-layer.
  const operatorSynthesisText = useMemo(() => {
    return buildOperatorSynthesis(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
      operatorImmunityText,
      operatorCoherenceText,
    );
  }, [
    operatorStateText, operatorDiffText, operatorStabilityText,
    operatorResilienceText, operatorImmunityText, operatorCoherenceText,
  ]);

  // Card 76 — system-operator integration: Phase-5 capstone. Fuses
  // the Phase-3 system-level outputs (structural stabilization /
  // resilience / immunity) with the Phase-5 operator-level outputs
  // (Cards 69-75) into a single 11-section integrated read.
  const systemOperatorIntegrationText = useMemo(() => {
    return buildSystemOperatorIntegration(
      structuralDiagnostics ?? "",
      signatureDiffText     ?? "",
      structuralStabilizationText ?? "",
      structuralResilienceText    ?? "",
      structuralImmunityText      ?? "",
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
      operatorImmunityText,
      operatorCoherenceText,
      operatorSynthesisText,
    );
  }, [
    structuralDiagnostics, signatureDiffText,
    structuralStabilizationText, structuralResilienceText, structuralImmunityText,
    operatorStateText, operatorDiffText, operatorStabilityText,
    operatorResilienceText, operatorImmunityText, operatorCoherenceText, operatorSynthesisText,
  ]);

  // Card 77 — operator meta-pattern: first of the Operator Advanced
  // Operators (AO-1 through AO-14, Cards 77-90). Lighter than the
  // core operators — extends the meta-layer with higher-order
  // interpretive functions.
  const operatorMetaPatternText = useMemo(() => {
    return buildOperatorMetaPattern(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
      operatorImmunityText,
      operatorCoherenceText,
      operatorSynthesisText,
      systemOperatorIntegrationText,
    );
  }, [
    operatorStateText, operatorDiffText, operatorStabilityText,
    operatorResilienceText, operatorImmunityText, operatorCoherenceText,
    operatorSynthesisText, systemOperatorIntegrationText,
  ]);

  // Card 78 — operator meta-stability: second Operator Advanced
  // Operator (AO-2). Evaluates meta-stability across transitions,
  // loads, and pressures by fusing the operator core stack (69-75),
  // the system-operator integration (76), and the meta-pattern (77).
  const operatorMetaStabilityText = useMemo(() => {
    return buildOperatorMetaStability(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
      operatorImmunityText,
      operatorCoherenceText,
      operatorSynthesisText,
      systemOperatorIntegrationText,
      operatorMetaPatternText,
    );
  }, [
    operatorStateText, operatorDiffText, operatorStabilityText,
    operatorResilienceText, operatorImmunityText, operatorCoherenceText,
    operatorSynthesisText, systemOperatorIntegrationText, operatorMetaPatternText,
  ]);

  // Card 79 — operator meta-resilience: third Operator Advanced
  // Operator (AO-3). The higher-order resilience engine above Card 72;
  // evaluates meta-resilience across volatility, pressure, drift, and
  // load by fusing the operator core stack (69-75), the system-
  // operator integration (76), the meta-pattern (77), and the meta-
  // stability (78).
  const operatorMetaResilienceText = useMemo(() => {
    return buildOperatorMetaResilience(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
      operatorImmunityText,
      operatorCoherenceText,
      operatorSynthesisText,
      systemOperatorIntegrationText,
      operatorMetaPatternText,
      operatorMetaStabilityText,
    );
  }, [
    operatorStateText, operatorDiffText, operatorStabilityText,
    operatorResilienceText, operatorImmunityText, operatorCoherenceText,
    operatorSynthesisText, systemOperatorIntegrationText, operatorMetaPatternText,
    operatorMetaStabilityText,
  ]);

  // Card 80 — operator meta-immunity: fourth Operator Advanced
  // Operator (AO-4), final card of the first AO cluster (77-80). The
  // higher-order immunity engine above Card 73; evaluates meta-immunity
  // across clarity, drift, load, pressure, and volatility by fusing the
  // operator core stack (69-75), the system-operator integration (76),
  // and the meta-pattern / meta-stability / meta-resilience (77-79).
  const operatorMetaImmunityText = useMemo(() => {
    return buildOperatorMetaImmunity(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
      operatorImmunityText,
      operatorCoherenceText,
      operatorSynthesisText,
      systemOperatorIntegrationText,
      operatorMetaPatternText,
      operatorMetaStabilityText,
      operatorMetaResilienceText,
    );
  }, [
    operatorStateText, operatorDiffText, operatorStabilityText,
    operatorResilienceText, operatorImmunityText, operatorCoherenceText,
    operatorSynthesisText, systemOperatorIntegrationText, operatorMetaPatternText,
    operatorMetaStabilityText, operatorMetaResilienceText,
  ]);

  // Card 81 — operator meta-integration: fifth Operator Advanced
  // Operator (AO-5), first card of the meta-integration cluster
  // (81-84). The higher-order integration engine that folds every meta-
  // operator into one read — coherence (74), synthesis (75), meta-
  // pattern (77), meta-stability (78), meta-resilience (79), and meta-
  // immunity (80) — across the operator core stack + integration (76).
  const operatorMetaIntegrationText = useMemo(() => {
    return buildOperatorMetaIntegration(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
      operatorImmunityText,
      operatorCoherenceText,
      operatorSynthesisText,
      systemOperatorIntegrationText,
      operatorMetaPatternText,
      operatorMetaStabilityText,
      operatorMetaResilienceText,
      operatorMetaImmunityText,
    );
  }, [
    operatorStateText, operatorDiffText, operatorStabilityText,
    operatorResilienceText, operatorImmunityText, operatorCoherenceText,
    operatorSynthesisText, systemOperatorIntegrationText, operatorMetaPatternText,
    operatorMetaStabilityText, operatorMetaResilienceText, operatorMetaImmunityText,
  ]);

  // Card 82 — operator meta-alignment: sixth Operator Advanced Operator
  // (AO-6), second card of the meta-integration cluster. Evaluates how
  // well the meta-operators align with each other and with the system-
  // operator fusion layer; caps on the Card 81 meta-integration level.
  const operatorMetaAlignmentText = useMemo(() => {
    return buildOperatorMetaAlignment(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
      operatorImmunityText,
      operatorCoherenceText,
      operatorSynthesisText,
      systemOperatorIntegrationText,
      operatorMetaPatternText,
      operatorMetaStabilityText,
      operatorMetaResilienceText,
      operatorMetaImmunityText,
      operatorMetaIntegrationText,
    );
  }, [
    operatorStateText, operatorDiffText, operatorStabilityText,
    operatorResilienceText, operatorImmunityText, operatorCoherenceText,
    operatorSynthesisText, systemOperatorIntegrationText, operatorMetaPatternText,
    operatorMetaStabilityText, operatorMetaResilienceText, operatorMetaImmunityText,
    operatorMetaIntegrationText,
  ]);

  // Card 83 — operator meta-coherence: seventh Operator Advanced
  // Operator (AO-7), third card of the meta-integration cluster. The
  // highest-order coherence engine; harmonises synthesis (75) with the
  // five higher meta-layers — meta-stability (78), meta-resilience
  // (79), meta-immunity (80), meta-integration (81), meta-alignment (82).
  const operatorMetaCoherenceText = useMemo(() => {
    return buildOperatorMetaCoherence(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
      operatorImmunityText,
      operatorCoherenceText,
      operatorSynthesisText,
      systemOperatorIntegrationText,
      operatorMetaPatternText,
      operatorMetaStabilityText,
      operatorMetaResilienceText,
      operatorMetaImmunityText,
      operatorMetaIntegrationText,
      operatorMetaAlignmentText,
    );
  }, [
    operatorStateText, operatorDiffText, operatorStabilityText,
    operatorResilienceText, operatorImmunityText, operatorCoherenceText,
    operatorSynthesisText, systemOperatorIntegrationText, operatorMetaPatternText,
    operatorMetaStabilityText, operatorMetaResilienceText, operatorMetaImmunityText,
    operatorMetaIntegrationText, operatorMetaAlignmentText,
  ]);

  // Card 84 — operator meta-synthesis: eighth Operator Advanced
  // Operator (AO-8), capstone of the meta-integration cluster. The
  // highest-order synthesis engine; unifies all seven meta-layers —
  // meta-pattern (77), meta-stability (78), meta-resilience (79), meta-
  // immunity (80), meta-integration (81), meta-alignment (82), and
  // meta-coherence (83) — into a single read.
  const operatorMetaSynthesisText = useMemo(() => {
    return buildOperatorMetaSynthesis(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
      operatorImmunityText,
      operatorCoherenceText,
      operatorSynthesisText,
      systemOperatorIntegrationText,
      operatorMetaPatternText,
      operatorMetaStabilityText,
      operatorMetaResilienceText,
      operatorMetaImmunityText,
      operatorMetaIntegrationText,
      operatorMetaAlignmentText,
      operatorMetaCoherenceText,
    );
  }, [
    operatorStateText, operatorDiffText, operatorStabilityText,
    operatorResilienceText, operatorImmunityText, operatorCoherenceText,
    operatorSynthesisText, systemOperatorIntegrationText, operatorMetaPatternText,
    operatorMetaStabilityText, operatorMetaResilienceText, operatorMetaImmunityText,
    operatorMetaIntegrationText, operatorMetaAlignmentText, operatorMetaCoherenceText,
  ]);

  // Card 85 — operator meta-consolidation: ninth Operator Advanced
  // Operator (AO-9), first card of the final meta-consolidation cluster
  // (85-90). Consolidates all eight meta-operators (77-84) into a single
  // read.
  const operatorMetaConsolidationText = useMemo(() => {
    return buildOperatorMetaConsolidation(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
      operatorImmunityText,
      operatorCoherenceText,
      operatorSynthesisText,
      systemOperatorIntegrationText,
      operatorMetaPatternText,
      operatorMetaStabilityText,
      operatorMetaResilienceText,
      operatorMetaImmunityText,
      operatorMetaIntegrationText,
      operatorMetaAlignmentText,
      operatorMetaCoherenceText,
      operatorMetaSynthesisText,
    );
  }, [
    operatorStateText, operatorDiffText, operatorStabilityText,
    operatorResilienceText, operatorImmunityText, operatorCoherenceText,
    operatorSynthesisText, systemOperatorIntegrationText, operatorMetaPatternText,
    operatorMetaStabilityText, operatorMetaResilienceText, operatorMetaImmunityText,
    operatorMetaIntegrationText, operatorMetaAlignmentText, operatorMetaCoherenceText,
    operatorMetaSynthesisText,
  ]);

  // Card 86 — operator meta-compression: tenth Operator Advanced
  // Operator (AO-10), second card of the meta-consolidation cluster.
  // Compresses all nine meta-operators (77-85) into a unified, high-
  // density representation.
  const operatorMetaCompressionText = useMemo(() => {
    return buildOperatorMetaCompression(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
      operatorImmunityText,
      operatorCoherenceText,
      operatorSynthesisText,
      systemOperatorIntegrationText,
      operatorMetaPatternText,
      operatorMetaStabilityText,
      operatorMetaResilienceText,
      operatorMetaImmunityText,
      operatorMetaIntegrationText,
      operatorMetaAlignmentText,
      operatorMetaCoherenceText,
      operatorMetaSynthesisText,
      operatorMetaConsolidationText,
    );
  }, [
    operatorStateText, operatorDiffText, operatorStabilityText,
    operatorResilienceText, operatorImmunityText, operatorCoherenceText,
    operatorSynthesisText, systemOperatorIntegrationText, operatorMetaPatternText,
    operatorMetaStabilityText, operatorMetaResilienceText, operatorMetaImmunityText,
    operatorMetaIntegrationText, operatorMetaAlignmentText, operatorMetaCoherenceText,
    operatorMetaSynthesisText, operatorMetaConsolidationText,
  ]);

  // Card 87 — operator meta-reduction: eleventh Operator Advanced
  // Operator (AO-11), third card of the meta-consolidation cluster.
  // Reduces all ten meta-operators (77-86) to their irreducible core.
  const operatorMetaReductionText = useMemo(() => {
    return buildOperatorMetaReduction(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
      operatorImmunityText,
      operatorCoherenceText,
      operatorSynthesisText,
      systemOperatorIntegrationText,
      operatorMetaPatternText,
      operatorMetaStabilityText,
      operatorMetaResilienceText,
      operatorMetaImmunityText,
      operatorMetaIntegrationText,
      operatorMetaAlignmentText,
      operatorMetaCoherenceText,
      operatorMetaSynthesisText,
      operatorMetaConsolidationText,
      operatorMetaCompressionText,
    );
  }, [
    operatorStateText, operatorDiffText, operatorStabilityText,
    operatorResilienceText, operatorImmunityText, operatorCoherenceText,
    operatorSynthesisText, systemOperatorIntegrationText, operatorMetaPatternText,
    operatorMetaStabilityText, operatorMetaResilienceText, operatorMetaImmunityText,
    operatorMetaIntegrationText, operatorMetaAlignmentText, operatorMetaCoherenceText,
    operatorMetaSynthesisText, operatorMetaConsolidationText, operatorMetaCompressionText,
  ]);

  // Card 88 — operator meta-extraction: twelfth Operator Advanced
  // Operator (AO-12), fourth card of the meta-consolidation cluster.
  // Extracts the actionable core from all eleven meta-operators (77-87).
  const operatorMetaExtractionText = useMemo(() => {
    return buildOperatorMetaExtraction(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
      operatorImmunityText,
      operatorCoherenceText,
      operatorSynthesisText,
      systemOperatorIntegrationText,
      operatorMetaPatternText,
      operatorMetaStabilityText,
      operatorMetaResilienceText,
      operatorMetaImmunityText,
      operatorMetaIntegrationText,
      operatorMetaAlignmentText,
      operatorMetaCoherenceText,
      operatorMetaSynthesisText,
      operatorMetaConsolidationText,
      operatorMetaCompressionText,
      operatorMetaReductionText,
    );
  }, [
    operatorStateText, operatorDiffText, operatorStabilityText,
    operatorResilienceText, operatorImmunityText, operatorCoherenceText,
    operatorSynthesisText, systemOperatorIntegrationText, operatorMetaPatternText,
    operatorMetaStabilityText, operatorMetaResilienceText, operatorMetaImmunityText,
    operatorMetaIntegrationText, operatorMetaAlignmentText, operatorMetaCoherenceText,
    operatorMetaSynthesisText, operatorMetaConsolidationText, operatorMetaCompressionText,
    operatorMetaReductionText,
  ]);

  // Card 89 — operator meta-distillation: thirteenth Operator Advanced
  // Operator (AO-13), penultimate operator of the 69-90 chain. Distills
  // the essential, invariant signal from all twelve meta-operators
  // (77-88).
  const operatorMetaDistillationText = useMemo(() => {
    return buildOperatorMetaDistillation(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
      operatorImmunityText,
      operatorCoherenceText,
      operatorSynthesisText,
      systemOperatorIntegrationText,
      operatorMetaPatternText,
      operatorMetaStabilityText,
      operatorMetaResilienceText,
      operatorMetaImmunityText,
      operatorMetaIntegrationText,
      operatorMetaAlignmentText,
      operatorMetaCoherenceText,
      operatorMetaSynthesisText,
      operatorMetaConsolidationText,
      operatorMetaCompressionText,
      operatorMetaReductionText,
      operatorMetaExtractionText,
    );
  }, [
    operatorStateText, operatorDiffText, operatorStabilityText,
    operatorResilienceText, operatorImmunityText, operatorCoherenceText,
    operatorSynthesisText, systemOperatorIntegrationText, operatorMetaPatternText,
    operatorMetaStabilityText, operatorMetaResilienceText, operatorMetaImmunityText,
    operatorMetaIntegrationText, operatorMetaAlignmentText, operatorMetaCoherenceText,
    operatorMetaSynthesisText, operatorMetaConsolidationText, operatorMetaCompressionText,
    operatorMetaReductionText, operatorMetaExtractionText,
  ]);

  // Card 90 — operator meta-essence: fourteenth Operator Advanced
  // Operator (AO-14) and the terminal operator of the entire 69-90
  // chain. Reads the invariant identity across all thirteen meta-
  // operators (77-89). The capstone.
  const operatorMetaEssenceText = useMemo(() => {
    return buildOperatorMetaEssence(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
      operatorImmunityText,
      operatorCoherenceText,
      operatorSynthesisText,
      systemOperatorIntegrationText,
      operatorMetaPatternText,
      operatorMetaStabilityText,
      operatorMetaResilienceText,
      operatorMetaImmunityText,
      operatorMetaIntegrationText,
      operatorMetaAlignmentText,
      operatorMetaCoherenceText,
      operatorMetaSynthesisText,
      operatorMetaConsolidationText,
      operatorMetaCompressionText,
      operatorMetaReductionText,
      operatorMetaExtractionText,
      operatorMetaDistillationText,
    );
  }, [
    operatorStateText, operatorDiffText, operatorStabilityText,
    operatorResilienceText, operatorImmunityText, operatorCoherenceText,
    operatorSynthesisText, systemOperatorIntegrationText, operatorMetaPatternText,
    operatorMetaStabilityText, operatorMetaResilienceText, operatorMetaImmunityText,
    operatorMetaIntegrationText, operatorMetaAlignmentText, operatorMetaCoherenceText,
    operatorMetaSynthesisText, operatorMetaConsolidationText, operatorMetaCompressionText,
    operatorMetaReductionText, operatorMetaExtractionText, operatorMetaDistillationText,
  ]);

  // Phase 6 — Operator Superstructure. Re-derives the cross-layer
  // superstructure (pattern / integration / coherence / essence /
  // identity) from the meta-operator text outputs above. Consumes the
  // structured `[Meta-X Level]` lines (not a Python port). "operatorIdentity"
  // is a stable seed string for the operator-identity projection.
  const operatorSuperstructureText = useMemo(() => {
    const sup = runSuperstructure({
      pattern:       operatorMetaPatternText,
      stability:     operatorMetaStabilityText,
      resilience:    operatorMetaResilienceText,
      integration:   operatorMetaIntegrationText,
      alignment:     operatorMetaAlignmentText,
      coherence:     operatorMetaCoherenceText,
      essence:       operatorMetaEssenceText,
      consolidation: operatorMetaConsolidationText,
      compression:   operatorMetaCompressionText,
      reduction:     operatorMetaReductionText,
      extraction:    operatorMetaExtractionText,
      distillation:  operatorMetaDistillationText,
      operatorIdentity: "clarityos-operator",
    });
    return [
      "=== Operator Superstructure ===",
      `[Pattern Identity]\n${sup.pattern.patternIdentity}`,
      `[Integration Identity]\n${sup.integration.integrationIdentity}`,
      `[Coherence Identity]\n${sup.coherence.coherenceIdentity}`,
      `[Essence Invariant]\n${sup.essence.invariantIdentity}`,
      `[Operator Identity]\n${sup.identity.operatorIdentity}`,
    ].join("\n\n");
  }, [
    operatorMetaPatternText, operatorMetaStabilityText, operatorMetaResilienceText,
    operatorMetaIntegrationText, operatorMetaAlignmentText, operatorMetaCoherenceText,
    operatorMetaEssenceText, operatorMetaConsolidationText, operatorMetaCompressionText,
    operatorMetaReductionText, operatorMetaExtractionText, operatorMetaDistillationText,
  ]);

  return (
    <div data-testid="operator-console">
      <h1>Operator Console</h1>
      <p>Engine V1 — Phase-1 diagnostic panel.</p>

      <section>
        <h2>Input</h2>
        <textarea
          data-testid="oc-input"
          value={jsonText}
          onChange={(e) => setJsonText(e.target.value)}
          rows={12}
          cols={80}
        />
        <div>
          <button data-testid="oc-load" onClick={handleLoad}>Load</button>
        </div>
        {parseErr ? (
          <pre data-testid="oc-error">{parseErr}</pre>
        ) : null}
      </section>

      {/* Card 41 — collapsible structured views via native <details>.
          Each top-level section keeps the full JSON dump for tooling
          + adds per-primitive / per-run drill-ins beneath. Diff
          markers ([CHANGED], [ADDED], [REMOVED]) are text-only —
          no colours, no styling. */}

      <section data-testid="oc-lineage-map">
        <details>
          <summary>
            Lineage Map{lineageMap ? ` (${lineageMap.primitive_ids.length} primitives)` : ""}
          </summary>
          <pre>
            {lineageMap ? JSON.stringify(lineageMap, null, 2) : "(no context loaded)"}
          </pre>
          {lineageMap?.primitive_ids.map((id) => {
            const d = lineageMap.diffs[id];
            const changed =
              d.appearance.added.length   > 0 ||
              d.appearance.removed.length > 0 ||
              d.metadataChanges.length    > 0 ||
              d.hydraulicChanges.length   > 0 ||
              d.overlayChanges.length     > 0;
            return (
              <details key={id} data-testid={`oc-lineage-primitive-${id}`}>
                <summary>
                  {id}
                  {changed ? " [CHANGED]" : ""}
                </summary>
                <pre>{JSON.stringify(lineageMap.lineages[id], null, 2)}</pre>
              </details>
            );
          })}
        </details>
        {/* Card 42 — semantic summary sibling. Plain text, no styling. */}
        <details data-testid="oc-lineage-summary">
          <summary>Lineage Summary</summary>
          <pre>
            {lineageMap ? summarizeLineageMap(lineageMap) : "(no context loaded)"}
          </pre>
        </details>
      </section>

      <section data-testid="oc-hydraulic-evolution">
        <details>
          <summary>
            Hydraulic Evolution
            {hydraulicEvolution ? ` (${hydraulicEvolution.perRun.length} runs)` : ""}
          </summary>
          <pre>
            {hydraulicEvolution
              ? JSON.stringify(hydraulicEvolution, null, 2)
              : "(no context loaded)"}
          </pre>
          {hydraulicEvolution?.perRun.map((run) => (
            <details key={run.index} data-testid={`oc-hydraulic-run-${run.index}`}>
              <summary>Run {run.index}</summary>
              <pre>{JSON.stringify(run, null, 2)}</pre>
            </details>
          ))}
        </details>
        {/* Card 42 — semantic summary sibling. */}
        <details data-testid="oc-hydraulic-summary">
          <summary>Hydraulic Evolution Summary</summary>
          <pre>
            {hydraulicEvolution
              ? summarizeHydraulicEvolution(hydraulicEvolution)
              : "(no context loaded)"}
          </pre>
        </details>
      </section>

      <section data-testid="oc-system-overlay">
        <details>
          <summary>System Overlay</summary>
          <pre>
            {systemOverlay ? JSON.stringify(systemOverlay, null, 2) : "(no context loaded)"}
          </pre>
        </details>
        {/* Card 42 — semantic summary sibling. */}
        <details data-testid="oc-system-overlay-summary">
          <summary>System Overlay Summary</summary>
          <pre>
            {systemOverlay
              ? summarizeSystemOverlay(systemOverlay)
              : "(no context loaded)"}
          </pre>
        </details>
      </section>

      <section data-testid="oc-regression">
        <details>
          <summary>System Regression Diff</summary>
          <div>
            <label>
              fromIndex{" "}
              <input
                data-testid="oc-from-index"
                type="number"
                value={fromIndex}
                onChange={(e) => setFromIndex(Number(e.target.value))}
              />
            </label>
            <label>
              {" "}toIndex{" "}
              <input
                data-testid="oc-to-index"
                type="number"
                value={toIndex}
                onChange={(e) => setToIndex(Number(e.target.value))}
              />
            </label>
          </div>
          {regressionDiff && "primitiveChanges" in regressionDiff ? (
            <ul data-testid="oc-regression-markers">
              {regressionDiff.primitiveChanges.added.map((id) => (
                <li key={`add-${id}`}>{id} [ADDED]</li>
              ))}
              {regressionDiff.primitiveChanges.removed.map((id) => (
                <li key={`rem-${id}`}>{id} [REMOVED]</li>
              ))}
              {regressionDiff.primitiveChanges.changed.map((id) => (
                <li key={`chg-${id}`}>{id} [CHANGED]</li>
              ))}
            </ul>
          ) : null}
          <pre>
            {regressionDiff
              ? JSON.stringify(regressionDiff, null, 2)
              : "(load a context with at least 2 runs and valid indices)"}
          </pre>
        </details>
        {/* Card 42 — semantic summary sibling. */}
        <details data-testid="oc-regression-summary">
          <summary>Regression Summary</summary>
          <pre>
            {regressionDiff && "primitiveChanges" in regressionDiff
              ? summarizeRegression(regressionDiff)
              : "(load a context with at least 2 runs and valid indices)"}
          </pre>
        </details>
      </section>

      {/* Card 43 — Evolution Timeline. Single text-only block weaving
          per-run state with run-to-run transitions. */}
      <section data-testid="oc-evolution-timeline">
        <details>
          <summary>Evolution Timeline</summary>
          <pre>
            {evolutionTimeline ?? "(no context loaded)"}
          </pre>
        </details>
      </section>

      {/* Card 44 — Diff Viewer. Independent from/to selectors drive a
          hierarchical text-only diff tree. */}
      <section data-testid="oc-diff-viewer">
        <details>
          <summary>Diff Viewer</summary>
          <div>
            <label>
              From Run:{" "}
              <input
                data-testid="oc-diff-from-index"
                type="number"
                value={diffFromIndex}
                onChange={(e) => setDiffFromIndex(Number(e.target.value))}
              />
            </label>
            <label>
              {" "}To Run:{" "}
              <input
                data-testid="oc-diff-to-index"
                type="number"
                value={diffToIndex}
                onChange={(e) => setDiffToIndex(Number(e.target.value))}
              />
            </label>
          </div>
          <pre>
            {diffViewText ?? "(load a context with at least 2 runs and valid indices)"}
          </pre>
        </details>
      </section>

      {/* Card 45 — Structural Diagnostics. Single text-only report
          covering stability, churn, hydraulic volatility, anomalies
          and per-run outliers. */}
      <section data-testid="oc-structural-diagnostics">
        <details>
          <summary>Structural Diagnostics</summary>
          <pre>
            {structuralDiagnostics ?? "(no context loaded)"}
          </pre>
        </details>
      </section>

      {/* Card 46 — Multi-Run Structural Overlay. Per-primitive
          evolution sequences + system map + cross-run deltas + rule-
          based clusters. */}
      <section data-testid="oc-structural-overlay">
        <details>
          <summary>Structural Overlay (Multi-Run)</summary>
          <pre>
            {multiRunStructuralOverlay ?? "(no context loaded)"}
          </pre>
        </details>
      </section>

      {/* Card 47 — Structural Matrix. Primitive × run grid with
          regime / zone / change / volatility / drift markers. */}
      <section data-testid="oc-structural-matrix">
        <details>
          <summary>Structural Matrix</summary>
          <pre>
            {structuralMatrix ?? "(no context loaded)"}
          </pre>
        </details>
      </section>

      {/* Card 48 — Structural Heatmap. Compressed intensity grid
          with pressure-score symbols + overlay flags. */}
      <section data-testid="oc-structural-heatmap">
        <details>
          <summary>Structural Heatmap</summary>
          <pre>
            {structuralHeatmap ?? "(no context loaded)"}
          </pre>
        </details>
      </section>

      {/* Card 49 — Structural Bands. Per-run band line + detected
          phase transitions + primitive bucket summary. */}
      <section data-testid="oc-structural-bands">
        <details>
          <summary>Structural Bands</summary>
          <pre>
            {structuralBands ?? "(no context loaded)"}
          </pre>
        </details>
      </section>

      {/* Card 50 — Structural Signature. Compressed system-level
          fingerprint with per-run tokens + signature string +
          hydraulic / zone / volatility / drift / phase signatures. */}
      <section data-testid="oc-structural-signature">
        <details>
          <summary>Structural Signature</summary>
          <pre>
            {structuralSignature ?? "(no context loaded)"}
          </pre>
        </details>
      </section>

      {/* Card 51 — Signature Diff. Independent from/to selectors
          drive a reasoning-layer comparison between two run signatures
          with rule-based identity-shift classification. */}
      <section data-testid="oc-signature-diff">
        <details>
          <summary>Signature Diff</summary>
          <div>
            <label>
              From Run:{" "}
              <input
                data-testid="oc-sig-from-index"
                type="number"
                value={sigFromIndex}
                onChange={(e) => setSigFromIndex(Number(e.target.value))}
              />
            </label>
            <label>
              {" "}To Run:{" "}
              <input
                data-testid="oc-sig-to-index"
                type="number"
                value={sigToIndex}
                onChange={(e) => setSigToIndex(Number(e.target.value))}
              />
            </label>
          </div>
          <pre>
            {signatureDiffText ?? "(load a context with at least 2 runs and valid indices)"}
          </pre>
        </details>
      </section>

      {/* Card 52 — Signature Overlay. Unified multi-run synthesis of
          per-run signatures, adjacent-pair diffs, 6 component
          overlays, identity-shift overlay, and system-level
          structural synthesis. */}
      <section data-testid="oc-signature-overlay">
        <details>
          <summary>Signature Overlay</summary>
          <pre>
            {signatureOverlayText ?? "(no context loaded)"}
          </pre>
        </details>
      </section>

      {/* Card 53 — Structural Trajectory. Predictive projections for
          hydraulic / pressure / counts / phase / identity, plus
          rule-based structural risks + opportunities + summary. */}
      <section data-testid="oc-structural-trajectory">
        <details>
          <summary>Structural Trajectory</summary>
          <pre>
            {structuralTrajectoryText ?? "(no context loaded)"}
          </pre>
        </details>
      </section>

      {/* Card 54 — Structural Risk. Per-run + system-level risk
          grading with rule-based classification and summary. */}
      <section data-testid="oc-structural-risk">
        <details>
          <summary>Structural Risk</summary>
          <pre>
            {structuralRiskText ?? "(no context loaded)"}
          </pre>
        </details>
      </section>

      {/* Card 55 — Structural Hotspots. Localization layer ranking
          top runs and structural dimensions by risk concentration. */}
      <section data-testid="oc-structural-hotspots">
        <details>
          <summary>Structural Hotspots</summary>
          <pre>
            {structuralHotspotsText ?? "(no context loaded)"}
          </pre>
        </details>
      </section>

      {/* Card 56 — Structural Causality. Explanation layer producing
          run + dimension + identity cause chains plus a system-level
          causal narrative. */}
      <section data-testid="oc-structural-causality">
        <details>
          <summary>Structural Causality</summary>
          <pre>
            {structuralCausalityText ?? "(no context loaded)"}
          </pre>
        </details>
      </section>

      {/* Card 57 — Structural Interventions. Action layer recommending
          run / dimension / identity / system-level operator actions. */}
      <section data-testid="oc-structural-interventions">
        <details>
          <summary>Structural Interventions</summary>
          <pre>
            {structuralInterventionsText ?? "(no context loaded)"}
          </pre>
        </details>
      </section>

      {/* Card 58 — Structural Stabilization. Recovery layer scoring
          intervention effectiveness + projecting stabilization. */}
      <section data-testid="oc-structural-stabilization">
        <details>
          <summary>Structural Stabilization</summary>
          <pre>
            {structuralStabilizationText ?? "(no context loaded)"}
          </pre>
        </details>
      </section>

      {/* Card 59 — Structural Resilience. Durability layer scoring
          the system's projected resistance to future instability. */}
      <section data-testid="oc-structural-resilience">
        <details>
          <summary>Structural Resilience</summary>
          <pre>
            {structuralResilienceText ?? "(no context loaded)"}
          </pre>
        </details>
      </section>

      {/* Card 60 — Structural Immunity. Prevention layer scoring the
          system's ability to prevent future instability from beginning. */}
      <section data-testid="oc-structural-immunity">
        <details>
          <summary>Structural Immunity</summary>
          <pre>
            {structuralImmunityText ?? "(no context loaded)"}
          </pre>
        </details>
      </section>

      {/* Card 61 — Structural Governance. Rules layer evaluating
          adherence to the OS's structural invariants + thresholds. */}
      <section data-testid="oc-structural-governance">
        <details>
          <summary>Structural Governance</summary>
          <pre>
            {structuralGovernanceText ?? "(no context loaded)"}
          </pre>
        </details>
      </section>

      {/* Card 62 — Structural Governance Diff. Phase-4 Tier-2 delta
          comparing the two most recent governance states (delta,
          direction, slope, pressure, stability, risk + drivers /
          inhibitors / summary). */}
      <section data-testid="oc-structural-governance-diff">
        <details>
          <summary>Structural Governance Diff</summary>
          <pre>
            {governanceDiffText ?? "(load a context with at least 2 runs)"}
          </pre>
        </details>
      </section>

      {/* Card 63 — Structural Governance Stability. Phase-4 Tier-3
          stability layer (level / coherence / integrity / drift /
          volatility / stabilization trajectory + drivers /
          inhibitors / risks / reinforcement / decay / summary). */}
      <section data-testid="oc-structural-governance-stability">
        <details>
          <summary>Structural Governance Stability</summary>
          <pre>
            {governanceStabilityText ?? "(load a context with at least 2 runs)"}
          </pre>
        </details>
      </section>

      {/* Card 64 — Structural Governance Resilience. Phase-4 Tier-4
          durability layer (level / load-bearing capacity / recovery
          strength / fault tolerance / pressure response / trajectory
          + drivers / inhibitors / risks / reinforcement / decay /
          summary). */}
      <section data-testid="oc-structural-governance-resilience">
        <details>
          <summary>Structural Governance Resilience</summary>
          <pre>
            {governanceResilienceText ?? "(load a context with at least 2 runs)"}
          </pre>
        </details>
      </section>

      {/* Card 65 — Structural Governance Immunity. Phase-4 Tier-5
          prevention layer (level / future-resistance / hardening /
          vulnerability / trajectory + drivers / inhibitors /
          thresholds / breach conditions / reinforcement / decay /
          early-warning signals / summary). */}
      <section data-testid="oc-structural-governance-immunity">
        <details>
          <summary>Structural Governance Immunity</summary>
          <pre>
            {governanceImmunityText ?? "(load a context with at least 2 runs)"}
          </pre>
        </details>
      </section>

      {/* Card 66 — Structural Governance Coherence. Phase-4 Tier-6
          alignment layer (level / alignment / consistency / cross-
          dimension agreement / contradiction risk / trajectory +
          drivers / inhibitors / risks / reinforcement / decay /
          summary). */}
      <section data-testid="oc-structural-governance-coherence">
        <details>
          <summary>Structural Governance Coherence</summary>
          <pre>
            {governanceCoherenceText ?? "(load a context with at least 2 runs)"}
          </pre>
        </details>
      </section>

      {/* Card 67 — Structural Governance Synthesis. Phase-4 Tier-7
          final meta-governance layer (synthesis level / integration /
          unification / meta-consistency / meta-risk / meta-trajectory
          + drivers / inhibitors / risks / reinforcement / decay /
          summary). */}
      <section data-testid="oc-structural-governance-synthesis">
        <details>
          <summary>Structural Governance Synthesis</summary>
          <pre>
            {governanceSynthesisText ?? "(load a context with at least 2 runs)"}
          </pre>
        </details>
      </section>

      {/* Card 68 — System-Level Governance. Phase-4 Tier-8 capstone
          (system gov level / integrity / cohesion / robustness /
          meta-stability / meta-risk / system trajectory + drivers /
          inhibitors / risks / reinforcement / decay / summary). */}
      <section data-testid="oc-system-level-governance">
        <details>
          <summary>System-Level Governance</summary>
          <pre>
            {systemGovernanceText ?? "(load a context with at least 2 runs)"}
          </pre>
        </details>
      </section>

      {/* Card 69 — Operator State. Phase-5 Tier-1 (operator level /
          load / drift / clarity / stability / pressure / risk +
          drivers / inhibitors / summary). First card that models the
          operator as a structural entity. */}
      <section data-testid="oc-operator-state">
        <details>
          <summary>Operator State</summary>
          <pre>{operatorStateText}</pre>
        </details>
      </section>

      {/* Card 70 — Operator Diff. Phase-5 Tier-2 (operator slope +
          drift/clarity/load/pressure/stability/risk deltas + drivers
          / inhibitors / summary). Compares baseline operator state
          to the current trajectory. */}
      <section data-testid="oc-operator-diff">
        <details>
          <summary>Operator Diff</summary>
          <pre>{operatorDiffText}</pre>
        </details>
      </section>

      {/* Card 71 — Operator Stability. Phase-5 Tier-3 (stability
          level + equilibrium / volatility / per-dim stabilities +
          trajectory + drivers / inhibitors / risks / reinforcement /
          decay / summary). Evaluates operator internal equilibrium. */}
      <section data-testid="oc-operator-stability">
        <details>
          <summary>Operator Stability</summary>
          <pre>{operatorStabilityText}</pre>
        </details>
      </section>

      {/* Card 72 — Operator Resilience. Phase-5 Tier-4 (resilience
          level + recovery / rebound / per-dim recoveries + trajectory
          + drivers / inhibitors / risks / reinforcement / decay /
          summary). Evaluates operator capacity to bounce back. */}
      <section data-testid="oc-operator-resilience">
        <details>
          <summary>Operator Resilience</summary>
          <pre>{operatorResilienceText}</pre>
        </details>
      </section>

      {/* Card 73 — Operator Immunity. Phase-5 Tier-5 (immunity level
          + resistance / shielding / per-dim immunities + trajectory
          + drivers / inhibitors / risks / reinforcement / decay /
          summary). Evaluates operator protective capacity. */}
      <section data-testid="oc-operator-immunity">
        <details>
          <summary>Operator Immunity</summary>
          <pre>{operatorImmunityText}</pre>
        </details>
      </section>

      {/* Card 74 — Operator Coherence. Phase-5 Tier-6 (coherence
          level + alignment / integration / per-dim alignments +
          trajectory + drivers / inhibitors / risks / reinforcement /
          decay / summary). Evaluates operator internal alignment. */}
      <section data-testid="oc-operator-coherence">
        <details>
          <summary>Operator Coherence</summary>
          <pre>{operatorCoherenceText}</pre>
        </details>
      </section>

      {/* Card 75 — Operator Synthesis. Phase-5 Tier-7 (synthesis
          level + integration / unification / per-dim syntheses +
          trajectory + drivers / inhibitors / risks / reinforcement /
          decay / summary). Unified integrated read of the operator. */}
      <section data-testid="oc-operator-synthesis">
        <details>
          <summary>Operator Synthesis</summary>
          <pre>{operatorSynthesisText}</pre>
        </details>
      </section>

      {/* Card 76 — System-Operator Integration. Phase-5 Tier-8
          capstone (integration level + alignment / coherence /
          synthesis + trajectory + drivers / inhibitors / risks /
          reinforcement / decay / summary). Fuses system + operator
          stacks into a single unified read. */}
      <section data-testid="oc-system-operator-integration">
        <details>
          <summary>System-Operator Integration</summary>
          <pre>{systemOperatorIntegrationText}</pre>
        </details>
      </section>

      {/* Card 77 — Operator Meta-Pattern. Phase-5 AO-1 (meta-pattern
          level + alignment / drift detection / load + pressure
          interpretation + trajectory + drivers / inhibitors / risks
          / reinforcement / decay / summary). First Advanced Operator. */}
      <section data-testid="oc-operator-meta-pattern">
        <details>
          <summary>Operator Meta-Pattern</summary>
          <pre>{operatorMetaPatternText}</pre>
        </details>
      </section>

      {/* Card 78 — Operator Meta-Stability. Phase-5 AO-2 (meta-
          stability level + transition / load / pressure / drift
          stabilities + trajectory + drivers / inhibitors / risks /
          reinforcement / decay / summary). Second Advanced Operator. */}
      <section data-testid="oc-operator-meta-stability">
        <details>
          <summary>Operator Meta-Stability</summary>
          <pre>{operatorMetaStabilityText}</pre>
        </details>
      </section>

      {/* Card 79 — Operator Meta-Resilience. Phase-5 AO-3 (meta-
          resilience level + volatility / pressure / drift / load
          resiliences + trajectory + drivers / inhibitors / risks /
          reinforcement / decay / summary). Third Advanced Operator. */}
      <section data-testid="oc-operator-meta-resilience">
        <details>
          <summary>Operator Meta-Resilience</summary>
          <pre>{operatorMetaResilienceText}</pre>
        </details>
      </section>

      {/* Card 80 — Operator Meta-Immunity. Phase-5 AO-4 (meta-immunity
          level + clarity / drift / load / pressure / volatility
          immunities + trajectory + drivers / inhibitors / risks /
          reinforcement / decay / summary). Fourth Advanced Operator. */}
      <section data-testid="oc-operator-meta-immunity">
        <details>
          <summary>Operator Meta-Immunity</summary>
          <pre>{operatorMetaImmunityText}</pre>
        </details>
      </section>

      {/* Card 81 — Operator Meta-Integration. Phase-5 AO-5 (meta-
          integration level + coherence / synthesis / stability /
          resilience / immunity / pattern integrations + trajectory +
          drivers / inhibitors / risks / reinforcement / decay /
          summary). First card of the meta-integration cluster. */}
      <section data-testid="oc-operator-meta-integration">
        <details>
          <summary>Operator Meta-Integration</summary>
          <pre>{operatorMetaIntegrationText}</pre>
        </details>
      </section>

      {/* Card 82 — Operator Meta-Alignment. Phase-5 AO-6 (meta-
          alignment level + coherence / synthesis / stability /
          resilience / immunity / pattern alignments + trajectory +
          drivers / inhibitors / risks / reinforcement / decay /
          summary). Second card of the meta-integration cluster. */}
      <section data-testid="oc-operator-meta-alignment">
        <details>
          <summary>Operator Meta-Alignment</summary>
          <pre>{operatorMetaAlignmentText}</pre>
        </details>
      </section>

      {/* Card 83 — Operator Meta-Coherence. Phase-5 AO-7 (meta-
          coherence level + synthesis / stability / resilience /
          immunity / integration / alignment coherences + trajectory +
          drivers / inhibitors / risks / reinforcement / decay /
          summary). Third card of the meta-integration cluster. */}
      <section data-testid="oc-operator-meta-coherence">
        <details>
          <summary>Operator Meta-Coherence</summary>
          <pre>{operatorMetaCoherenceText}</pre>
        </details>
      </section>

      {/* Card 84 — Operator Meta-Synthesis. Phase-5 AO-8 (meta-synthesis
          level + coherence / stability / resilience / immunity /
          integration / alignment / pattern syntheses + trajectory +
          drivers / inhibitors / risks / reinforcement / decay /
          summary). Capstone of the meta-integration cluster. */}
      <section data-testid="oc-operator-meta-synthesis">
        <details>
          <summary>Operator Meta-Synthesis</summary>
          <pre>{operatorMetaSynthesisText}</pre>
        </details>
      </section>

      {/* Card 85 — Operator Meta-Consolidation. Phase-5 AO-9 (meta-
          consolidation level + pattern / stability / resilience /
          immunity / integration / alignment / coherence / synthesis
          consolidations + trajectory + drivers / inhibitors / risks /
          reinforcement / decay / summary). First card of the meta-
          consolidation cluster. */}
      <section data-testid="oc-operator-meta-consolidation">
        <details>
          <summary>Operator Meta-Consolidation</summary>
          <pre>{operatorMetaConsolidationText}</pre>
        </details>
      </section>

      {/* Card 86 — Operator Meta-Compression. Phase-5 AO-10 (meta-
          compression level + pattern / stability / resilience /
          immunity / integration / alignment / coherence / synthesis /
          consolidation compressions + trajectory + drivers /
          inhibitors / risks / reinforcement / decay / summary). Second
          card of the meta-consolidation cluster. */}
      <section data-testid="oc-operator-meta-compression">
        <details>
          <summary>Operator Meta-Compression</summary>
          <pre>{operatorMetaCompressionText}</pre>
        </details>
      </section>

      {/* Card 87 — Operator Meta-Reduction. Phase-5 AO-11 (meta-
          reduction level + pattern / stability / resilience / immunity
          / integration / alignment / coherence / synthesis /
          consolidation / compression reductions + trajectory + drivers
          / inhibitors / risks / reinforcement / decay / summary). Third
          card of the meta-consolidation cluster. */}
      <section data-testid="oc-operator-meta-reduction">
        <details>
          <summary>Operator Meta-Reduction</summary>
          <pre>{operatorMetaReductionText}</pre>
        </details>
      </section>

      {/* Card 88 — Operator Meta-Extraction. Phase-5 AO-12 (meta-
          extraction level + pattern / stability / resilience / immunity
          / integration / alignment / coherence / synthesis /
          consolidation / compression / reduction extractions +
          trajectory + drivers / inhibitors / risks / reinforcement /
          decay / summary). Fourth card of the meta-consolidation
          cluster. */}
      <section data-testid="oc-operator-meta-extraction">
        <details>
          <summary>Operator Meta-Extraction</summary>
          <pre>{operatorMetaExtractionText}</pre>
        </details>
      </section>

      {/* Card 89 — Operator Meta-Distillation. Phase-5 AO-13 (meta-
          distillation level + pattern / stability / resilience /
          immunity / integration / alignment / coherence / synthesis /
          consolidation / compression / reduction / extraction
          distillations + trajectory + drivers / inhibitors / risks /
          reinforcement / decay / summary). Penultimate operator. */}
      <section data-testid="oc-operator-meta-distillation">
        <details>
          <summary>Operator Meta-Distillation</summary>
          <pre>{operatorMetaDistillationText}</pre>
        </details>
      </section>

      {/* Card 90 — Operator Meta-Essence. Phase-5 AO-14 (meta-essence
          level + pattern / stability / resilience / immunity /
          integration / alignment / coherence / synthesis /
          consolidation / compression / reduction / extraction /
          distillation essences + trajectory + drivers / inhibitors /
          risks / reinforcement / decay / summary). The terminal
          operator of the entire AO architecture. */}
      <section data-testid="oc-operator-meta-essence">
        <details>
          <summary>Operator Meta-Essence</summary>
          <pre>{operatorMetaEssenceText}</pre>
        </details>
      </section>

      {/* Phase 6 — Operator Superstructure. Re-derived cross-layer view
          (pattern / integration / coherence / essence-invariant /
          operator identities) computed by runSuperstructure() from the
          meta-operator outputs above. Text-only, consistent with the
          rest of the console. */}
      <section data-testid="oc-operator-superstructure">
        <details>
          <summary>Operator Superstructure (Phase 6)</summary>
          <pre>{operatorSuperstructureText}</pre>
        </details>
      </section>

      {/* Phase 7 (Card 7.2B) — Operator Continuity tile. Read-only: shows
          the latest drift / coherence-health / trust-band + history count
          fetched from GET /operator/telemetry. No styling, no charts. */}
      <section data-testid="oc-operator-continuity">
        <h2>Operator Continuity (Phase 7)</h2>
        <p>Drift: {formatPhase7Float(phase7?.latest?.drift)}</p>
        <p>Coherence Health: {formatPhase7Float(phase7?.latest?.coherence_health)}</p>
        <p>Trust Band: {phase7?.latest?.trust_band ?? "—"}</p>
        <p>History Count: {phase7?.history?.length ?? 0}</p>
      </section>

      {/* Phase 7.5 — Operator Forecast tile. Read-only: the Phase 7.3 analytics
          (velocity / acceleration / coherence-trend / forecast / trajectory)
          from GET /operator/telemetry. No styling, no charts. */}
      <section data-testid="oc-operator-forecast">
        <h2>Operator Forecast (Phase 7 Analytics)</h2>
        <p>Drift Velocity: {formatPhase7Float(phase7?.analytics?.drift_velocity)}</p>
        <p>Drift Acceleration: {formatPhase7Float(phase7?.analytics?.drift_acceleration)}</p>
        <p>Coherence Trend: {formatPhase7Float(phase7?.analytics?.coherence_trend)}</p>
        <p>Stability Forecast: {formatPhase7Float(phase7?.analytics?.stability_forecast)}</p>
        <p>Trajectory: {phase7?.analytics?.trajectory ?? "—"}</p>
      </section>

      {/* Phase 7.6 — Operator Stability Alerts tile. Read-only guidance derived
          from the analytics; informational only. No styling, icons, or colors. */}
      <section data-testid="oc-operator-alerts">
        <h2>Operator Stability Alerts</h2>
        {(phase7?.alerts ?? []).map((alert, i) => (
          <p key={i}>- {alert}</p>
        ))}
      </section>

      {/* Phase 7.8 — Causal Drift Factors tile. Read-only: the Phase 7.7 causal
          mapping from GET /operator/telemetry; descriptive, not prescriptive.
          No styling, no charts. */}
      <section data-testid="oc-operator-causal">
        <h2>Causal Drift Factors</h2>
        {(() => {
          const factors = phase7?.causal_factors ?? [];
          if (factors.length === 1 && factors[0].action === "none") {
            return <p>No significant contributing actions detected</p>;
          }
          return (
            <ul>
              {factors.map((f, i) => (
                <li key={`${f.action}-${i}`}>
                  {f.action} (correlation: {f.correlation.toFixed(2)}, contribution: {f.contribution.toFixed(2)})
                </li>
              ))}
            </ul>
          );
        })()}
      </section>

      {/* Phase 7.10 — Causal Narrative tile. Read-only: the Phase 7.9
          deterministic narrative from GET /operator/telemetry. pre-wrap only. */}
      <section data-testid="oc-operator-narrative">
        <h2>Causal Narrative</h2>
        <pre style={{ whiteSpace: "pre-wrap" }}>{phase7?.narrative ?? ""}</pre>
      </section>

      {/* Phase 8.5 — Causal Chains tile. Read-only: the Phase 8.4 ranked
          multi-chain explanations from GET /operator/telemetry. Each chain
          lists its node labels (start → narrative) + score + motif flags.
          Text-only, no charts, no styling. */}
      <section data-testid="oc-operator-causal-chains">
        <h2>Causal Chains</h2>
        {(() => {
          const chains = phase7?.causal_chains ?? [];
          if (chains.length === 0) {
            return <p>No causal chains detected</p>;
          }
          return (
            <ul>
              {chains.map((c, i) => (
                <li key={i}>
                  Chain {i + 1} — score {c.score.toFixed(2)}
                  <ul>
                    {c.nodes.map((n) => (
                      <li key={n.id}>{n.label}</li>
                    ))}
                  </ul>
                  <p>
                    Motifs: bottleneck={c.motifs.passes_bottleneck ? "yes" : "no"},{" "}
                    attractor={c.motifs.passes_attractor ? "yes" : "no"},{" "}
                    loop={c.motifs.in_feedback_loop ? "yes" : "no"}
                  </p>
                </li>
              ))}
            </ul>
          );
        })()}
      </section>

      {/* Phase 8.5 — Structural Motifs tile. Read-only: the Phase 8.3 motif
          detection (feedback loops / bottlenecks / attractors) from
          GET /operator/telemetry. Text-only, no charts, no styling. */}
      <section data-testid="oc-operator-motifs">
        <h2>Structural Motifs</h2>
        {(() => {
          const motifs = phase7?.causal_motifs ?? {
            feedback_loops: [],
            bottlenecks: [],
            attractors: [],
          };
          return (
            <>
              <h3>Feedback Loops</h3>
              {motifs.feedback_loops.length === 0 ? (
                <p>None</p>
              ) : (
                <ul>
                  {motifs.feedback_loops.map((loop, i) => (
                    <li key={i}>{loop.join(" → ")}</li>
                  ))}
                </ul>
              )}
              <h3>Bottlenecks</h3>
              {motifs.bottlenecks.length === 0 ? (
                <p>None</p>
              ) : (
                <ul>
                  {motifs.bottlenecks.map((id) => (
                    <li key={id}>{id}</li>
                  ))}
                </ul>
              )}
              <h3>Attractors</h3>
              {motifs.attractors.length === 0 ? (
                <p>None</p>
              ) : (
                <ul>
                  {motifs.attractors.map((id) => (
                    <li key={id}>{id}</li>
                  ))}
                </ul>
              )}
            </>
          );
        })()}
      </section>

      {/* Phase 8.8 — Causal Stability tile. Read-only: the Phase 8.7 stability
          forecast from GET /operator/telemetry — score + trend + the drivers
          behind it. Loop / chain drivers are node-id sequences (rendered
          "a → b"); influence / bottleneck drivers are node ids. Text-only, no
          charts, no styling. */}
      <section data-testid="oc-operator-causal-stability">
        <h2>Causal Stability</h2>
        {(() => {
          const stability = phase7?.causal_stability ?? EMPTY_STABILITY;
          const drivers = stability.drivers;
          const idList = (items: string[]) =>
            items.length === 0 ? (
              <p>None</p>
            ) : (
              <ul>{items.map((id) => <li key={id}>{id}</li>)}</ul>
            );
          const seqList = (items: string[][]) =>
            items.length === 0 ? (
              <p>None</p>
            ) : (
              <ul>{items.map((seq) => <li key={seq.join("-")}>{seq.join(" → ")}</li>)}</ul>
            );
          return (
            <>
              <p>Stability Score: {stability.stability_score.toFixed(2)}</p>
              <p>Trend: {stability.trend}</p>
              <h3>Drivers</h3>
              <h4>Rising Influence</h4>
              {idList(drivers.rising_influence)}
              <h4>Falling Influence</h4>
              {idList(drivers.falling_influence)}
              <h4>New Bottlenecks</h4>
              {idList(drivers.new_bottlenecks)}
              <h4>Resolved Bottlenecks</h4>
              {idList(drivers.resolved_bottlenecks)}
              <h4>New Loops</h4>
              {seqList(drivers.new_loops)}
              <h4>Resolved Loops</h4>
              {seqList(drivers.resolved_loops)}
              <h4>Chain Strengthening</h4>
              {seqList(drivers.chain_strengthening)}
              <h4>Chain Weakening</h4>
              {seqList(drivers.chain_weakening)}
            </>
          );
        })()}
      </section>

      {/* Phase 8.11 — Unified Narrative tile. Read-only: the Phase 8.10 unified
          temporal-causal narrative from GET /operator/telemetry, rendered as a
          preformatted text block. No styling beyond pre-wrap. */}
      <section data-testid="oc-operator-unified-narrative">
        <h2>Unified Narrative</h2>
        <pre style={{ whiteSpace: "pre-wrap" }}>{phase7?.unified_narrative ?? ""}</pre>
      </section>

      {/* Phase 9.5 (Card 9.5) — Behavioral Motifs tile. Read-only: the Phase
          9.4 behavioral-motif detection (action loops / trigger chains / habits
          / action bottlenecks / action attractors) from GET /operator/telemetry
          → behavioral_motifs. Deterministic ordering (backend-sorted, rendered
          in array order); empty sections collapse (omitted entirely); a section
          over 10 rows scrolls. No charts, no styling, no inference / narrative
          text. */}
      <section data-testid="oc-operator-behavioral-motifs">
        <h2>Behavioral Motifs</h2>
        {(() => {
          const motifs = phase7?.behavioral_motifs ?? EMPTY_BEHAVIORAL_MOTIFS;
          // Each section collapses (renders nothing) when its motif set is
          // empty. Sequence sections ("a → b") cover loops + trigger chains;
          // label sections cover habits / bottlenecks / attractors.
          const seqSection = (testid: string, title: string, items: string[][]) =>
            items.length === 0 ? null : (
              <div key={testid}>
                <h3>{title}</h3>
                <ul data-testid={testid} style={items.length > 10 ? BEHAVIORAL_SCROLL : undefined}>
                  {items.map((seq, i) => (
                    <li key={i}>{seq.join(" → ")}</li>
                  ))}
                </ul>
              </div>
            );
          const labelSection = (testid: string, title: string, items: string[]) =>
            items.length === 0 ? null : (
              <div key={testid}>
                <h3>{title}</h3>
                <ul data-testid={testid} style={items.length > 10 ? BEHAVIORAL_SCROLL : undefined}>
                  {items.map((label, i) => (
                    <li key={`${label}-${i}`}>{label}</li>
                  ))}
                </ul>
              </div>
            );
          return (
            <>
              {seqSection("oc-behavioral-loops", "Action Loops", motifs.action_loops)}
              {seqSection("oc-behavioral-triggers", "Trigger Chains", motifs.trigger_chains)}
              {labelSection("oc-behavioral-habits", "Habits", motifs.habits)}
              {labelSection("oc-behavioral-bottlenecks", "Action Bottlenecks", motifs.action_bottlenecks)}
              {labelSection("oc-behavioral-attractors", "Action Attractors", motifs.action_attractors)}
            </>
          );
        })()}
      </section>

      {/* Phase 10.4 (Card 10.4) — Behavioral Forecast tile. Read-only: the Phase
          10.0-10.3 outputs from GET /operator/telemetry → behavioral_forecast
          (forecast / stability / narrative). Deterministic ordering (rendered in
          backend array order); empty sections collapse; a list over 10 rows
          scrolls. No charts, no animations, no inference / psychological text. */}
      <section data-testid="oc-operator-behavioral-forecast">
        <h2>Behavioral Forecast</h2>
        {(() => {
          const bf = phase7?.behavioral_forecast ?? null;
          const nextActions = bf?.forecast?.next_actions ?? [];
          const habitChanges = bf?.narrative?.habit_changes ?? [];
          const triggerChanges = (bf?.narrative?.trigger_changes ?? []).slice(0, 3);
          const loopChanges = (bf?.forecast?.loop_continuation ?? []).slice(0, 3);
          const stability = bf?.stability ?? null;
          const summary = bf?.narrative?.summary ?? "";
          const highlights = (bf?.narrative?.forecast_highlights ?? []).slice(0, 3);
          const driverTail = (d: string[]) => (d.length > 0 ? ` (${d.join(", ")})` : "");
          return (
            <>
              {/* A — Next Likely Actions (10.0) */}
              {nextActions.length > 0 ? (
                <div data-testid="oc-bf-next-actions">
                  <h3>Next Likely Actions</h3>
                  <ul style={nextActions.length > 10 ? BEHAVIORAL_SCROLL : undefined}>
                    {nextActions.map((a, i) => (
                      <li key={`${a.action_id}-${i}`}>
                        {a.label} — score {a.score.toFixed(2)}{driverTail(a.drivers)}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {/* B — Habit Trajectory (10.0 + 10.1) */}
              {habitChanges.length > 0 ? (
                <div data-testid="oc-bf-habits">
                  <h3>Habit Trajectory</h3>
                  <ul style={habitChanges.length > 10 ? BEHAVIORAL_SCROLL : undefined}>
                    {habitChanges.map((h, i) => (
                      <li key={`${h.action_id}-${i}`}>
                        {h.action_id} — {h.trend} (Δ {h.delta.toFixed(2)})
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {/* C — Trigger Likelihood (top 3, 10.3) */}
              {triggerChanges.length > 0 ? (
                <div data-testid="oc-bf-triggers">
                  <h3>Trigger Likelihood</h3>
                  <ul>
                    {triggerChanges.map((t, i) => (
                      <li key={i}>{t.chain.join(" → ")} (Δ {t.delta.toFixed(2)})</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {/* D — Loop Continuation (top 3, 10.0) */}
              {loopChanges.length > 0 ? (
                <div data-testid="oc-bf-loops">
                  <h3>Loop Continuation</h3>
                  <ul>
                    {loopChanges.map((l, i) => (
                      <li key={i}>{l.loop.join(" → ")} ({l.continuation_probability.toFixed(2)})</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {/* E — Stability (10.2) */}
              {stability && stability.drivers ? (
                <div data-testid="oc-bf-stability">
                  <h3>Stability</h3>
                  <p>Score: {stability.score.toFixed(2)}</p>
                  <ul>
                    <li>Habit stability: {stability.drivers.habit_stability.toFixed(2)}</li>
                    <li>Trigger stability: {stability.drivers.trigger_stability.toFixed(2)}</li>
                    <li>Loop persistence: {stability.drivers.loop_persistence.toFixed(2)}</li>
                    <li>Action variance: {stability.drivers.action_variance.toFixed(2)}</li>
                  </ul>
                </div>
              ) : null}
              {/* F — Narrative (10.3) */}
              {summary || highlights.length > 0 ? (
                <div data-testid="oc-bf-narrative">
                  <h3>Narrative</h3>
                  {summary ? <p>{summary}</p> : null}
                  {highlights.length > 0 ? (
                    <ul>
                      {highlights.map((h, i) => (
                        <li key={`${h.action_id}-${i}`}>
                          {h.action_id} — score {h.score.toFixed(2)}{driverTail(h.drivers)}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}
            </>
          );
        })()}
      </section>

      {/* Phase 11.2 (Card 11.2) — Recommendations tile. Read-only: the 11.0
          recommendations + 11.1 narrative from GET /operator/telemetry →
          recommendation_narrative (which embeds the drivers + stability
          context). Deterministic ordering (backend-sorted); empty sections
          collapse; a list over 10 rows scrolls. No charts, no animations, no
          inference / psychological text. */}
      <section data-testid="oc-operator-recommendations">
        <h2>Recommendations</h2>
        {(() => {
          const rn = phase7?.recommendation_narrative ?? null;
          const recs = rn?.recommendations ?? [];
          const drivers = rn?.drivers ?? null;
          const stability = rn?.stability_context ?? null;
          const summary = rn?.summary ?? "";
          const top3 = recs.slice(0, 3);
          const driverBuckets = drivers
            ? ([
                ["habit", "Habit", drivers.habit],
                ["triggers", "Triggers", drivers.triggers],
                ["loops", "Loops", drivers.loops],
                ["bottlenecks", "Bottlenecks", drivers.bottlenecks],
                ["attractors", "Attractors", drivers.attractors],
                ["forecast_alignment", "Forecast Alignment", drivers.forecast_alignment],
              ] as [string, string, RecDriverEntry[]][]).filter(([, , e]) => (e ?? []).length > 0)
            : [];
          return (
            <>
              {/* A — Top Recommendations (11.0) */}
              {recs.length > 0 ? (
                <div data-testid="oc-rec-top">
                  <h3>Top Recommendations</h3>
                  <ul style={recs.length > 10 ? BEHAVIORAL_SCROLL : undefined}>
                    {recs.map((r, i) => (
                      <li key={`${r.action_id}-${i}`}>{r.label} — {r.reason} (score {r.score.toFixed(2)})</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {/* B — Drivers (11.1) */}
              {driverBuckets.length > 0 ? (
                <div data-testid="oc-rec-drivers">
                  <h3>Drivers</h3>
                  {driverBuckets.map(([key, title, entries]) => (
                    <div key={key} data-testid={`oc-rec-driver-${key}`}>
                      <h4>{title}</h4>
                      <ul style={entries.length > 10 ? BEHAVIORAL_SCROLL : undefined}>
                        {entries.map((e, i) => (
                          <li key={`${e.action_id}-${i}`}>{e.action_id} — {e.reason} ({e.metric.toFixed(2)})</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              ) : null}
              {/* C — Stability Context (10.2) */}
              {stability && stability.drivers ? (
                <div data-testid="oc-rec-stability">
                  <h3>Stability Context</h3>
                  <p>Score: {stability.score.toFixed(2)}</p>
                  <ul>
                    <li>Habit stability: {stability.drivers.habit_stability.toFixed(2)}</li>
                    <li>Trigger stability: {stability.drivers.trigger_stability.toFixed(2)}</li>
                    <li>Loop persistence: {stability.drivers.loop_persistence.toFixed(2)}</li>
                    <li>Action variance: {stability.drivers.action_variance.toFixed(2)}</li>
                  </ul>
                </div>
              ) : null}
              {/* D — Narrative Summary (11.1) */}
              {summary || top3.length > 0 ? (
                <div data-testid="oc-rec-narrative">
                  <h3>Narrative Summary</h3>
                  {summary ? <p>{summary}</p> : null}
                  {top3.length > 0 ? (
                    <ul>
                      {top3.map((r, i) => (
                        <li key={`${r.action_id}-${i}`}>{r.label} — {r.explanation}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}
            </>
          );
        })()}
      </section>

      {/* Phase 12.3 (Card 12.3) — engine version footer. Read-only RC marker
          (engine cohort, distinct from the deployed product version). */}
      <footer data-testid="oc-engine-version" style={{ marginTop: "2rem", fontSize: "0.75rem", opacity: 0.6 }}>
        ClarityOS operator-intelligence engine — v1.0.0-rc1
      </footer>
    </div>
  );
}
