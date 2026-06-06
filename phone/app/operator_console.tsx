// Card 40 — Operator Console (phone screen).
//
// Phase-1 minimal diagnostic panel mirroring web's OperatorConsole
// and desktop's OperatorConsoleShell. React Native primitives only
// (no DOM): TextInput multiline / Pressable / ScrollView / Text.
//
// Body: textarea-equivalent JSON input → LOAD → 4 result panes
// (lineage map / hydraulic evolution / system overlay / regression
// diff). All wiring through the Card 39 EngineV1OperatorAPI.

import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from "react-native";

import {
  createEngineV1OperatorAPI,
  getApiBase,
  type EngineV1MultiRunContext,
} from "../lib/api";
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
// fetch resolves (or when the backend omits the block). Each page then shows
// its "None" sentinel.
const EMPTY_BEHAVIORAL_MOTIFS: BehavioralMotifs = {
  action_loops: [],
  trigger_chains: [],
  habits: [],
  action_bottlenecks: [],
  action_attractors: [],
};

function formatPhase7Float(n: number | null | undefined): string {
  return typeof n === "number" ? n.toFixed(2) : "—";
}

export default function OperatorConsoleScreen() {
  const api = useMemo(() => createEngineV1OperatorAPI(), []);

  // Phase 9.5 — viewport width for the Behavior tile's one-section-per-screen
  // horizontal pager. Page width = viewport − 24 (the scrollContent's 12px
  // left+right padding), so each page snaps to exactly one full screen.
  const { width: viewportWidth } = useWindowDimensions();

  const [jsonText,  setJsonText]  = useState<string>(PLACEHOLDER);
  const [context,   setContext]   = useState<EngineV1MultiRunContext | null>(null);
  const [parseErr,  setParseErr]  = useState<string | null>(null);

  const [fromIndexText, setFromIndexText] = useState<string>("0");
  const [toIndexText,   setToIndexText]   = useState<string>("1");

  const fromIndex = Number(fromIndexText);
  const toIndex   = Number(toIndexText);

  // Card 44 — independent Diff Viewer selection.
  const [diffFromIndexText, setDiffFromIndexText] = useState<string>("0");
  const [diffToIndexText,   setDiffToIndexText]   = useState<string>("1");

  const diffFromIndex = Number(diffFromIndexText);
  const diffToIndex   = Number(diffToIndexText);

  // Card 51 — independent Signature Diff selection.
  const [sigFromIndexText, setSigFromIndexText] = useState<string>("0");
  const [sigToIndexText,   setSigToIndexText]   = useState<string>("1");

  const sigFromIndex = Number(sigFromIndexText);
  const sigToIndex   = Number(sigToIndexText);

  // Phase 7 (Card 7.2B) — fetch the durable telemetry once on mount and
  // surface the latest drift / coherence-health / trust-band + history
  // count. Read-only: the console never writes telemetry (Phase 7.1 owns
  // recording). getApiBase() is async on phone; fetch failures leave the
  // tile blank rather than throwing.
  const [phase7, setPhase7] = useState<Phase7Telemetry | null>(null);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const base = await getApiBase();
        const res = await fetch(`${base}/operator/telemetry`);
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

  // Card 43 — pure text-only evolution timeline.
  const evolutionTimeline = useMemo(() => {
    if (!systemOverlay) return null;
    return buildEvolutionTimeline(
      systemOverlay,
      (from, to) => api.computeSystemRegression(systemOverlay, from, to),
    );
  }, [api, systemOverlay]);

  // Card 44 — hierarchical text-only diff for the Diff Viewer's
  // independent from/to selection.
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

  // Card 45 — system-level structural diagnostics.
  const structuralDiagnostics = useMemo(() => {
    if (!systemOverlay || !lineageMap || !hydraulicEvolution) return null;
    return buildStructuralDiagnostics(
      systemOverlay,
      evolutionTimeline ?? "",
      lineageMap,
      hydraulicEvolution,
    );
  }, [systemOverlay, lineageMap, hydraulicEvolution, evolutionTimeline]);

  // Card 46 — multi-run structural overlay.
  const multiRunStructuralOverlay = useMemo(() => {
    if (!systemOverlay || !lineageMap || !hydraulicEvolution) return null;
    return buildMultiRunStructuralOverlay(
      systemOverlay,
      lineageMap,
      hydraulicEvolution,
    );
  }, [systemOverlay, lineageMap, hydraulicEvolution]);

  // Card 47 — structural matrix.
  const structuralMatrix = useMemo(() => {
    if (!systemOverlay || !lineageMap || !hydraulicEvolution) return null;
    return buildStructuralMatrix(
      systemOverlay,
      lineageMap,
      hydraulicEvolution,
    );
  }, [systemOverlay, lineageMap, hydraulicEvolution]);

  // Card 48 — structural heatmap.
  const structuralHeatmap = useMemo(() => {
    if (!systemOverlay || !lineageMap || !hydraulicEvolution) return null;
    return buildStructuralHeatmap(
      systemOverlay,
      lineageMap,
      hydraulicEvolution,
    );
  }, [systemOverlay, lineageMap, hydraulicEvolution]);

  // Card 49 — structural bands.
  const structuralBands = useMemo(() => {
    if (!systemOverlay || !lineageMap || !hydraulicEvolution) return null;
    return buildStructuralBands(
      systemOverlay,
      lineageMap,
      hydraulicEvolution,
      structuralHeatmap ?? "",
    );
  }, [systemOverlay, lineageMap, hydraulicEvolution, structuralHeatmap]);

  // Card 50 — structural signature.
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

  // Card 51 — per-run signatures + diff text.
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

  // Card 52 — multi-run signature overlay.
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

  // Card 53 — structural trajectory engine.
  const structuralTrajectoryText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildStructuralTrajectory(
      perRunSignatures,
      adjacentSignatureDiffs,
      signatureOverlayText ?? "",
    );
  }, [perRunSignatures, adjacentSignatureDiffs, signatureOverlayText]);

  // Card 54 — structural risk engine.
  const structuralRiskText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildStructuralRisk(
      perRunSignatures,
      adjacentSignatureDiffs,
      structuralTrajectoryText ?? "",
    );
  }, [perRunSignatures, adjacentSignatureDiffs, structuralTrajectoryText]);

  // Card 55 — structural hotspot engine.
  const structuralHotspotsText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildStructuralHotspots(
      perRunSignatures,
      adjacentSignatureDiffs,
      structuralRiskText ?? "",
    );
  }, [perRunSignatures, adjacentSignatureDiffs, structuralRiskText]);

  // Card 56 — structural causality engine.
  const structuralCausalityText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildStructuralCausality(
      perRunSignatures,
      adjacentSignatureDiffs,
      structuralHotspotsText ?? "",
    );
  }, [perRunSignatures, adjacentSignatureDiffs, structuralHotspotsText]);

  // Card 57 — structural intervention engine.
  const structuralInterventionsText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildStructuralInterventions(
      perRunSignatures,
      adjacentSignatureDiffs,
      structuralCausalityText ?? "",
    );
  }, [perRunSignatures, adjacentSignatureDiffs, structuralCausalityText]);

  // Card 58 — structural stabilization engine.
  const structuralStabilizationText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildStructuralStabilization(
      perRunSignatures,
      adjacentSignatureDiffs,
      structuralInterventionsText ?? "",
    );
  }, [perRunSignatures, adjacentSignatureDiffs, structuralInterventionsText]);

  // Card 59 — structural resilience engine.
  const structuralResilienceText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildStructuralResilience(
      perRunSignatures,
      adjacentSignatureDiffs,
      structuralStabilizationText ?? "",
    );
  }, [perRunSignatures, adjacentSignatureDiffs, structuralStabilizationText]);

  // Card 60 — structural immunity engine.
  const structuralImmunityText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildStructuralImmunity(
      perRunSignatures,
      adjacentSignatureDiffs,
      structuralResilienceText ?? "",
    );
  }, [perRunSignatures, adjacentSignatureDiffs, structuralResilienceText]);

  // Card 61 — structural governance engine.
  const structuralGovernanceText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length === 0 || !adjacentSignatureDiffs) return null;
    return buildStructuralGovernance(
      perRunSignatures,
      adjacentSignatureDiffs,
      structuralImmunityText ?? "",
    );
  }, [perRunSignatures, adjacentSignatureDiffs, structuralImmunityText]);

  // Card 62 — prior-run governance + governance diff (delta layer
  // tracking how governance strength changes between the two most
  // recent states).
  const prevGovernanceText = useMemo(() => {
    if (!perRunSignatures || perRunSignatures.length < 2 || !adjacentSignatureDiffs) return null;
    const prevSigs  = perRunSignatures.slice(0, -1);
    const prevDiffs = adjacentSignatureDiffs.slice(0, -1);
    return buildStructuralGovernance(prevSigs, prevDiffs, structuralImmunityText ?? "");
  }, [perRunSignatures, adjacentSignatureDiffs, structuralImmunityText]);

  const governanceDiffText = useMemo(() => {
    if (!structuralGovernanceText || !prevGovernanceText) return null;
    return buildStructuralGovernanceDiff(prevGovernanceText, structuralGovernanceText);
  }, [prevGovernanceText, structuralGovernanceText]);

  // Card 63 — structural governance stability engine.
  const governanceStabilityText = useMemo(() => {
    if (!structuralGovernanceText || !governanceDiffText) return null;
    return buildStructuralGovernanceStability(structuralGovernanceText, governanceDiffText);
  }, [structuralGovernanceText, governanceDiffText]);

  // Card 64 — structural governance resilience engine.
  const governanceResilienceText = useMemo(() => {
    if (!structuralGovernanceText || !governanceDiffText || !governanceStabilityText) return null;
    return buildStructuralGovernanceResilience(
      structuralGovernanceText,
      governanceDiffText,
      governanceStabilityText,
    );
  }, [structuralGovernanceText, governanceDiffText, governanceStabilityText]);

  // Card 65 — structural governance immunity engine.
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

  // Card 66 — structural governance coherence engine.
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

  // Card 67 — structural governance synthesis engine.
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

  // Card 68 — system-level governance engine (Phase-4 capstone).
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

  // Card 69 — operator state engine (Phase-5 Tier-1).
  const operatorStateText = useMemo(() => {
    return buildOperatorState(jsonText);
  }, [jsonText]);

  // Card 70 — operator diff engine (Phase-5 Tier-2).
  const prevOperatorStateText = useMemo(() => {
    return buildOperatorState("");
  }, []);

  const operatorDiffText = useMemo(() => {
    return buildOperatorDiff(prevOperatorStateText, operatorStateText);
  }, [prevOperatorStateText, operatorStateText]);

  // Card 71 — operator stability engine (Phase-5 Tier-3).
  const operatorStabilityText = useMemo(() => {
    return buildOperatorStability(operatorStateText, operatorDiffText);
  }, [operatorStateText, operatorDiffText]);

  // Card 72 — operator resilience engine (Phase-5 Tier-4).
  const operatorResilienceText = useMemo(() => {
    return buildOperatorResilience(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
    );
  }, [operatorStateText, operatorDiffText, operatorStabilityText]);

  // Card 73 — operator immunity engine (Phase-5 Tier-5).
  const operatorImmunityText = useMemo(() => {
    return buildOperatorImmunity(
      operatorStateText,
      operatorDiffText,
      operatorStabilityText,
      operatorResilienceText,
    );
  }, [operatorStateText, operatorDiffText, operatorStabilityText, operatorResilienceText]);

  // Card 74 — operator coherence engine (Phase-5 Tier-6).
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

  // Card 75 — operator synthesis engine (Phase-5 Tier-7).
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

  // Card 76 — system-operator integration engine (Phase-5 capstone).
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

  // Card 77 — operator meta-pattern engine (Phase-5 AO-1).
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

  // Card 78 — operator meta-stability engine (Phase-5 AO-2).
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

  // Card 79 — operator meta-resilience engine (Phase-5 AO-3).
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

  // Card 80 — operator meta-immunity engine (Phase-5 AO-4).
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

  // Card 81 — operator meta-integration engine (Phase-5 AO-5).
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

  // Card 82 — operator meta-alignment engine (Phase-5 AO-6).
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

  // Card 83 — operator meta-coherence engine (Phase-5 AO-7).
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

  // Card 84 — operator meta-synthesis engine (Phase-5 AO-8).
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

  // Card 85 — operator meta-consolidation engine (Phase-5 AO-9).
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

  // Card 86 — operator meta-compression engine (Phase-5 AO-10).
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

  // Card 87 — operator meta-reduction engine (Phase-5 AO-11).
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

  // Card 88 — operator meta-extraction engine (Phase-5 AO-12).
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

  // Card 89 — operator meta-distillation engine (Phase-5 AO-13).
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

  // Card 90 — operator meta-essence engine (Phase-5 AO-14, capstone).
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

  // Phase 6 — Operator Superstructure (cross-layer re-derive from the
  // meta-operator outputs above). Mirrors the web console wiring.
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
    <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
      <Text style={styles.h1}>Operator Console</Text>
      <Text>Engine V1 — Phase-1 diagnostic panel.</Text>

      <View style={styles.section}>
        <Text style={styles.h2}>Input</Text>
        <TextInput
          value={jsonText}
          onChangeText={setJsonText}
          multiline
          numberOfLines={12}
          style={styles.input}
          autoCorrect={false}
          autoCapitalize="none"
        />
        <Pressable onPress={handleLoad} style={styles.button}>
          <Text>LOAD</Text>
        </Pressable>
        {parseErr ? <Text style={styles.error}>{parseErr}</Text> : null}
      </View>

      {/* Card 41 — RN equivalent of <details>: a Pressable header
          that toggles open state, with the body rendered only when
          open. Per-primitive + per-run drill-ins below each top-
          level Collapsible. Diff markers ([CHANGED]/[ADDED]/
          [REMOVED]) are text-only. */}

      <Collapsible
        label={`Lineage Map${lineageMap ? ` (${lineageMap.primitive_ids.length} primitives)` : ""}`}
      >
        <Text style={styles.pre}>
          {lineageMap ? JSON.stringify(lineageMap, null, 2) : "(no context loaded)"}
        </Text>
        {lineageMap?.primitive_ids.map((id) => {
          const d = lineageMap.diffs[id];
          const changed =
            d.appearance.added.length   > 0 ||
            d.appearance.removed.length > 0 ||
            d.metadataChanges.length    > 0 ||
            d.hydraulicChanges.length   > 0 ||
            d.overlayChanges.length     > 0;
          return (
            <Collapsible key={id} label={`${id}${changed ? " [CHANGED]" : ""}`}>
              <Text style={styles.pre}>
                {JSON.stringify(lineageMap.lineages[id], null, 2)}
              </Text>
            </Collapsible>
          );
        })}
      </Collapsible>

      {/* Card 42 — semantic summary sibling. */}
      <Collapsible label="Lineage Summary">
        <Text style={styles.pre}>
          {lineageMap ? summarizeLineageMap(lineageMap) : "(no context loaded)"}
        </Text>
      </Collapsible>

      <Collapsible
        label={`Hydraulic Evolution${hydraulicEvolution ? ` (${hydraulicEvolution.perRun.length} runs)` : ""}`}
      >
        <Text style={styles.pre}>
          {hydraulicEvolution
            ? JSON.stringify(hydraulicEvolution, null, 2)
            : "(no context loaded)"}
        </Text>
        {hydraulicEvolution?.perRun.map((run) => (
          <Collapsible key={run.index} label={`Run ${run.index}`}>
            <Text style={styles.pre}>{JSON.stringify(run, null, 2)}</Text>
          </Collapsible>
        ))}
      </Collapsible>

      {/* Card 42 — semantic summary sibling. */}
      <Collapsible label="Hydraulic Evolution Summary">
        <Text style={styles.pre}>
          {hydraulicEvolution
            ? summarizeHydraulicEvolution(hydraulicEvolution)
            : "(no context loaded)"}
        </Text>
      </Collapsible>

      <Collapsible label="System Overlay">
        <Text style={styles.pre}>
          {systemOverlay ? JSON.stringify(systemOverlay, null, 2) : "(no context loaded)"}
        </Text>
      </Collapsible>

      {/* Card 42 — semantic summary sibling. */}
      <Collapsible label="System Overlay Summary">
        <Text style={styles.pre}>
          {systemOverlay ? summarizeSystemOverlay(systemOverlay) : "(no context loaded)"}
        </Text>
      </Collapsible>

      <Collapsible label="System Regression Diff">
        <View style={styles.row}>
          <Text>fromIndex </Text>
          <TextInput
            value={fromIndexText}
            onChangeText={setFromIndexText}
            keyboardType="number-pad"
            style={styles.indexInput}
          />
          <Text>  toIndex </Text>
          <TextInput
            value={toIndexText}
            onChangeText={setToIndexText}
            keyboardType="number-pad"
            style={styles.indexInput}
          />
        </View>
        {regressionDiff && "primitiveChanges" in regressionDiff ? (
          <View>
            {regressionDiff.primitiveChanges.added.map((id) => (
              <Text key={`add-${id}`}>{id} [ADDED]</Text>
            ))}
            {regressionDiff.primitiveChanges.removed.map((id) => (
              <Text key={`rem-${id}`}>{id} [REMOVED]</Text>
            ))}
            {regressionDiff.primitiveChanges.changed.map((id) => (
              <Text key={`chg-${id}`}>{id} [CHANGED]</Text>
            ))}
          </View>
        ) : null}
        <Text style={styles.pre}>
          {regressionDiff
            ? JSON.stringify(regressionDiff, null, 2)
            : "(load a context with at least 2 runs and valid indices)"}
        </Text>
      </Collapsible>

      {/* Card 42 — semantic summary sibling. */}
      <Collapsible label="Regression Summary">
        <Text style={styles.pre}>
          {regressionDiff && "primitiveChanges" in regressionDiff
            ? summarizeRegression(regressionDiff)
            : "(load a context with at least 2 runs and valid indices)"}
        </Text>
      </Collapsible>

      {/* Card 43 — Evolution Timeline. */}
      <Collapsible label="Evolution Timeline">
        <Text style={styles.pre}>
          {evolutionTimeline ?? "(no context loaded)"}
        </Text>
      </Collapsible>

      {/* Card 44 — Diff Viewer. */}
      <Collapsible label="Diff Viewer">
        <View style={styles.row}>
          <Text>From Run: </Text>
          <TextInput
            value={diffFromIndexText}
            onChangeText={setDiffFromIndexText}
            keyboardType="number-pad"
            style={styles.indexInput}
          />
          <Text>  To Run: </Text>
          <TextInput
            value={diffToIndexText}
            onChangeText={setDiffToIndexText}
            keyboardType="number-pad"
            style={styles.indexInput}
          />
        </View>
        <Text style={styles.pre}>
          {diffViewText ?? "(load a context with at least 2 runs and valid indices)"}
        </Text>
      </Collapsible>

      {/* Card 45 — Structural Diagnostics. */}
      <Collapsible label="Structural Diagnostics">
        <Text style={styles.pre}>
          {structuralDiagnostics ?? "(no context loaded)"}
        </Text>
      </Collapsible>

      {/* Card 46 — Multi-Run Structural Overlay. */}
      <Collapsible label="Structural Overlay (Multi-Run)">
        <Text style={styles.pre}>
          {multiRunStructuralOverlay ?? "(no context loaded)"}
        </Text>
      </Collapsible>

      {/* Card 47 — Structural Matrix. */}
      <Collapsible label="Structural Matrix">
        <Text style={styles.pre}>
          {structuralMatrix ?? "(no context loaded)"}
        </Text>
      </Collapsible>

      {/* Card 48 — Structural Heatmap. */}
      <Collapsible label="Structural Heatmap">
        <Text style={styles.pre}>
          {structuralHeatmap ?? "(no context loaded)"}
        </Text>
      </Collapsible>

      {/* Card 49 — Structural Bands. */}
      <Collapsible label="Structural Bands">
        <Text style={styles.pre}>
          {structuralBands ?? "(no context loaded)"}
        </Text>
      </Collapsible>

      {/* Card 50 — Structural Signature. */}
      <Collapsible label="Structural Signature">
        <Text style={styles.pre}>
          {structuralSignature ?? "(no context loaded)"}
        </Text>
      </Collapsible>

      {/* Card 51 — Signature Diff. */}
      <Collapsible label="Signature Diff">
        <View style={styles.row}>
          <Text>From Run: </Text>
          <TextInput
            value={sigFromIndexText}
            onChangeText={setSigFromIndexText}
            keyboardType="number-pad"
            style={styles.indexInput}
          />
          <Text>  To Run: </Text>
          <TextInput
            value={sigToIndexText}
            onChangeText={setSigToIndexText}
            keyboardType="number-pad"
            style={styles.indexInput}
          />
        </View>
        <Text style={styles.pre}>
          {signatureDiffText ?? "(load a context with at least 2 runs and valid indices)"}
        </Text>
      </Collapsible>

      {/* Card 52 — Signature Overlay. */}
      <Collapsible label="Signature Overlay">
        <Text style={styles.pre}>
          {signatureOverlayText ?? "(no context loaded)"}
        </Text>
      </Collapsible>

      {/* Card 53 — Structural Trajectory. */}
      <Collapsible label="Structural Trajectory">
        <Text style={styles.pre}>
          {structuralTrajectoryText ?? "(no context loaded)"}
        </Text>
      </Collapsible>

      {/* Card 54 — Structural Risk. */}
      <Collapsible label="Structural Risk">
        <Text style={styles.pre}>
          {structuralRiskText ?? "(no context loaded)"}
        </Text>
      </Collapsible>

      {/* Card 55 — Structural Hotspots. */}
      <Collapsible label="Structural Hotspots">
        <Text style={styles.pre}>
          {structuralHotspotsText ?? "(no context loaded)"}
        </Text>
      </Collapsible>

      {/* Card 56 — Structural Causality. */}
      <Collapsible label="Structural Causality">
        <Text style={styles.pre}>
          {structuralCausalityText ?? "(no context loaded)"}
        </Text>
      </Collapsible>

      {/* Card 57 — Structural Interventions. */}
      <Collapsible label="Structural Interventions">
        <Text style={styles.pre}>
          {structuralInterventionsText ?? "(no context loaded)"}
        </Text>
      </Collapsible>

      {/* Card 58 — Structural Stabilization. */}
      <Collapsible label="Structural Stabilization">
        <Text style={styles.pre}>
          {structuralStabilizationText ?? "(no context loaded)"}
        </Text>
      </Collapsible>

      {/* Card 59 — Structural Resilience. */}
      <Collapsible label="Structural Resilience">
        <Text style={styles.pre}>
          {structuralResilienceText ?? "(no context loaded)"}
        </Text>
      </Collapsible>

      {/* Card 60 — Structural Immunity. */}
      <Collapsible label="Structural Immunity">
        <Text style={styles.pre}>
          {structuralImmunityText ?? "(no context loaded)"}
        </Text>
      </Collapsible>

      {/* Card 61 — Structural Governance. */}
      <Collapsible label="Structural Governance">
        <Text style={styles.pre}>
          {structuralGovernanceText ?? "(no context loaded)"}
        </Text>
      </Collapsible>

      {/* Card 62 — Structural Governance Diff. */}
      <Collapsible label="Structural Governance Diff">
        <Text style={styles.pre}>
          {governanceDiffText ?? "(load a context with at least 2 runs)"}
        </Text>
      </Collapsible>

      {/* Card 63 — Structural Governance Stability. */}
      <Collapsible label="Structural Governance Stability">
        <Text style={styles.pre}>
          {governanceStabilityText ?? "(load a context with at least 2 runs)"}
        </Text>
      </Collapsible>

      {/* Card 64 — Structural Governance Resilience. */}
      <Collapsible label="Structural Governance Resilience">
        <Text style={styles.pre}>
          {governanceResilienceText ?? "(load a context with at least 2 runs)"}
        </Text>
      </Collapsible>

      {/* Card 65 — Structural Governance Immunity. */}
      <Collapsible label="Structural Governance Immunity">
        <Text style={styles.pre}>
          {governanceImmunityText ?? "(load a context with at least 2 runs)"}
        </Text>
      </Collapsible>

      {/* Card 66 — Structural Governance Coherence. */}
      <Collapsible label="Structural Governance Coherence">
        <Text style={styles.pre}>
          {governanceCoherenceText ?? "(load a context with at least 2 runs)"}
        </Text>
      </Collapsible>

      {/* Card 67 — Structural Governance Synthesis. */}
      <Collapsible label="Structural Governance Synthesis">
        <Text style={styles.pre}>
          {governanceSynthesisText ?? "(load a context with at least 2 runs)"}
        </Text>
      </Collapsible>

      {/* Card 68 — System-Level Governance (Phase-4 capstone). */}
      <Collapsible label="System-Level Governance">
        <Text style={styles.pre}>
          {systemGovernanceText ?? "(load a context with at least 2 runs)"}
        </Text>
      </Collapsible>

      {/* Card 69 — Operator State (Phase-5 Tier-1). */}
      <Collapsible label="Operator State">
        <Text style={styles.pre}>{operatorStateText}</Text>
      </Collapsible>

      {/* Card 70 — Operator Diff (Phase-5 Tier-2). */}
      <Collapsible label="Operator Diff">
        <Text style={styles.pre}>{operatorDiffText}</Text>
      </Collapsible>

      {/* Card 71 — Operator Stability (Phase-5 Tier-3). */}
      <Collapsible label="Operator Stability">
        <Text style={styles.pre}>{operatorStabilityText}</Text>
      </Collapsible>

      {/* Card 72 — Operator Resilience (Phase-5 Tier-4). */}
      <Collapsible label="Operator Resilience">
        <Text style={styles.pre}>{operatorResilienceText}</Text>
      </Collapsible>

      {/* Card 73 — Operator Immunity (Phase-5 Tier-5). */}
      <Collapsible label="Operator Immunity">
        <Text style={styles.pre}>{operatorImmunityText}</Text>
      </Collapsible>

      {/* Card 74 — Operator Coherence (Phase-5 Tier-6). */}
      <Collapsible label="Operator Coherence">
        <Text style={styles.pre}>{operatorCoherenceText}</Text>
      </Collapsible>

      {/* Card 75 — Operator Synthesis (Phase-5 Tier-7). */}
      <Collapsible label="Operator Synthesis">
        <Text style={styles.pre}>{operatorSynthesisText}</Text>
      </Collapsible>

      {/* Card 76 — System-Operator Integration (Phase-5 capstone). */}
      <Collapsible label="System-Operator Integration">
        <Text style={styles.pre}>{systemOperatorIntegrationText}</Text>
      </Collapsible>

      {/* Card 77 — Operator Meta-Pattern (Phase-5 AO-1). */}
      <Collapsible label="Operator Meta-Pattern">
        <Text style={styles.pre}>{operatorMetaPatternText}</Text>
      </Collapsible>

      {/* Card 78 — Operator Meta-Stability (Phase-5 AO-2). */}
      <Collapsible label="Operator Meta-Stability">
        <Text style={styles.pre}>{operatorMetaStabilityText}</Text>
      </Collapsible>

      {/* Card 79 — Operator Meta-Resilience (Phase-5 AO-3). */}
      <Collapsible label="Operator Meta-Resilience">
        <Text style={styles.pre}>{operatorMetaResilienceText}</Text>
      </Collapsible>

      {/* Card 80 — Operator Meta-Immunity (Phase-5 AO-4). */}
      <Collapsible label="Operator Meta-Immunity">
        <Text style={styles.pre}>{operatorMetaImmunityText}</Text>
      </Collapsible>

      {/* Card 81 — Operator Meta-Integration (Phase-5 AO-5). */}
      <Collapsible label="Operator Meta-Integration">
        <Text style={styles.pre}>{operatorMetaIntegrationText}</Text>
      </Collapsible>

      {/* Card 82 — Operator Meta-Alignment (Phase-5 AO-6). */}
      <Collapsible label="Operator Meta-Alignment">
        <Text style={styles.pre}>{operatorMetaAlignmentText}</Text>
      </Collapsible>

      {/* Card 83 — Operator Meta-Coherence (Phase-5 AO-7). */}
      <Collapsible label="Operator Meta-Coherence">
        <Text style={styles.pre}>{operatorMetaCoherenceText}</Text>
      </Collapsible>

      {/* Card 84 — Operator Meta-Synthesis (Phase-5 AO-8). */}
      <Collapsible label="Operator Meta-Synthesis">
        <Text style={styles.pre}>{operatorMetaSynthesisText}</Text>
      </Collapsible>

      {/* Card 85 — Operator Meta-Consolidation (Phase-5 AO-9). */}
      <Collapsible label="Operator Meta-Consolidation">
        <Text style={styles.pre}>{operatorMetaConsolidationText}</Text>
      </Collapsible>

      {/* Card 86 — Operator Meta-Compression (Phase-5 AO-10). */}
      <Collapsible label="Operator Meta-Compression">
        <Text style={styles.pre}>{operatorMetaCompressionText}</Text>
      </Collapsible>

      {/* Card 87 — Operator Meta-Reduction (Phase-5 AO-11). */}
      <Collapsible label="Operator Meta-Reduction">
        <Text style={styles.pre}>{operatorMetaReductionText}</Text>
      </Collapsible>

      {/* Card 88 — Operator Meta-Extraction (Phase-5 AO-12). */}
      <Collapsible label="Operator Meta-Extraction">
        <Text style={styles.pre}>{operatorMetaExtractionText}</Text>
      </Collapsible>

      {/* Card 89 — Operator Meta-Distillation (Phase-5 AO-13). */}
      <Collapsible label="Operator Meta-Distillation">
        <Text style={styles.pre}>{operatorMetaDistillationText}</Text>
      </Collapsible>

      {/* Card 90 — Operator Meta-Essence (Phase-5 AO-14, capstone). */}
      <Collapsible label="Operator Meta-Essence">
        <Text style={styles.pre}>{operatorMetaEssenceText}</Text>
      </Collapsible>

      {/* Phase 6 — Operator Superstructure (cross-layer re-derive). */}
      <Collapsible label="Operator Superstructure (Phase 6)">
        <Text style={styles.pre}>{operatorSuperstructureText}</Text>
      </Collapsible>

      {/* Phase 7 (Card 7.2B) — Operator Continuity tile. Read-only: the
          latest drift / coherence-health / trust-band + history count
          fetched from GET /operator/telemetry. Layout styles only, no charts. */}
      <View style={styles.section}>
        <Text style={styles.h2}>Operator Continuity (Phase 7)</Text>
        <Text>Drift: {formatPhase7Float(phase7?.latest?.drift)}</Text>
        <Text>Coherence Health: {formatPhase7Float(phase7?.latest?.coherence_health)}</Text>
        <Text>Trust Band: {phase7?.latest?.trust_band ?? "—"}</Text>
        <Text>History Count: {phase7?.history?.length ?? 0}</Text>
      </View>

      {/* Phase 7.5 — Operator Forecast tile. Read-only: the Phase 7.3 analytics
          (velocity / acceleration / coherence-trend / forecast / trajectory)
          from GET /operator/telemetry. Layout styles only, no charts. */}
      <View style={styles.section}>
        <Text style={styles.h2}>Operator Forecast (Phase 7 Analytics)</Text>
        <Text>Drift Velocity: {formatPhase7Float(phase7?.analytics?.drift_velocity)}</Text>
        <Text>Drift Acceleration: {formatPhase7Float(phase7?.analytics?.drift_acceleration)}</Text>
        <Text>Coherence Trend: {formatPhase7Float(phase7?.analytics?.coherence_trend)}</Text>
        <Text>Stability Forecast: {formatPhase7Float(phase7?.analytics?.stability_forecast)}</Text>
        <Text>Trajectory: {phase7?.analytics?.trajectory ?? "—"}</Text>
      </View>

      {/* Phase 7.6 — Operator Stability Alerts tile. Read-only guidance derived
          from the analytics; informational only. Layout styles only. */}
      <View style={styles.section}>
        <Text style={styles.h2}>Operator Stability Alerts</Text>
        {(phase7?.alerts ?? []).map((alert, i) => (
          <Text key={i}>- {alert}</Text>
        ))}
      </View>

      {/* Phase 7.8 — Causal Drift Factors tile. Read-only: the Phase 7.7 causal
          mapping from GET /operator/telemetry; descriptive, not prescriptive.
          Layout styles only. */}
      <View style={styles.section}>
        <Text style={styles.h2}>Causal Drift Factors</Text>
        {(() => {
          const factors = phase7?.causal_factors ?? [];
          if (factors.length === 1 && factors[0].action === "none") {
            return <Text>No significant contributing actions detected</Text>;
          }
          return factors.map((f, i) => (
            <Text key={`${f.action}-${i}`}>
              - {f.action} (correlation: {f.correlation.toFixed(2)}, contribution: {f.contribution.toFixed(2)})
            </Text>
          ));
        })()}
      </View>

      {/* Phase 7.10 — Causal Narrative tile. Read-only: the Phase 7.9
          deterministic narrative from GET /operator/telemetry. Monospace only. */}
      <View style={styles.section}>
        <Text style={styles.h2}>Causal Narrative</Text>
        <Text style={styles.pre}>{phase7?.narrative ?? ""}</Text>
      </View>

      {/* Phase 8.5 — Causal Chains tile. Read-only: the Phase 8.4 ranked
          multi-chain explanations from GET /operator/telemetry. Each chain
          lists its node labels (start → narrative) + score + motif flags.
          Phone-friendly text rows, no charts, layout styles only. */}
      <View style={styles.section}>
        <Text style={styles.h2}>Causal Chains</Text>
        {(() => {
          const chains = phase7?.causal_chains ?? [];
          if (chains.length === 0) {
            return <Text>No causal chains detected</Text>;
          }
          return chains.map((c, i) => (
            <View key={i} style={styles.section}>
              <Text>Chain {i + 1} — score {c.score.toFixed(2)}</Text>
              {c.nodes.map((n) => (
                <Text key={n.id}>  - {n.label}</Text>
              ))}
              <Text>
                Motifs: bottleneck={c.motifs.passes_bottleneck ? "yes" : "no"},{" "}
                attractor={c.motifs.passes_attractor ? "yes" : "no"},{" "}
                loop={c.motifs.in_feedback_loop ? "yes" : "no"}
              </Text>
            </View>
          ));
        })()}
      </View>

      {/* Phase 8.5 — Structural Motifs tile. Read-only: the Phase 8.3 motif
          detection (feedback loops / bottlenecks / attractors) from
          GET /operator/telemetry. Phone-friendly text rows, layout styles only. */}
      <View style={styles.section}>
        <Text style={styles.h2}>Structural Motifs</Text>
        {(() => {
          const motifs = phase7?.causal_motifs ?? {
            feedback_loops: [],
            bottlenecks: [],
            attractors: [],
          };
          return (
            <>
              <Text style={styles.h2}>Feedback Loops</Text>
              {motifs.feedback_loops.length === 0 ? (
                <Text>None</Text>
              ) : (
                motifs.feedback_loops.map((loop, i) => (
                  <Text key={i}>{loop.join(" → ")}</Text>
                ))
              )}
              <Text style={styles.h2}>Bottlenecks</Text>
              {motifs.bottlenecks.length === 0 ? (
                <Text>None</Text>
              ) : (
                motifs.bottlenecks.map((id) => <Text key={id}>{id}</Text>)
              )}
              <Text style={styles.h2}>Attractors</Text>
              {motifs.attractors.length === 0 ? (
                <Text>None</Text>
              ) : (
                motifs.attractors.map((id) => <Text key={id}>{id}</Text>)
              )}
            </>
          );
        })()}
      </View>

      {/* Phase 8.8 — Causal Stability tile. Read-only: the Phase 8.7 stability
          forecast from GET /operator/telemetry — score + trend + the drivers
          behind it. Loop / chain drivers are node-id sequences (rendered
          "a → b"); influence / bottleneck drivers are node ids. Phone-friendly
          text rows, layout styles only. */}
      <View style={styles.section}>
        <Text style={styles.h2}>Causal Stability</Text>
        {(() => {
          const stability = phase7?.causal_stability ?? EMPTY_STABILITY;
          const drivers = stability.drivers;
          const idRows = (items: string[]) =>
            items.length === 0
              ? <Text>None</Text>
              : items.map((id) => <Text key={id}>{id}</Text>);
          const seqRows = (items: string[][]) =>
            items.length === 0
              ? <Text>None</Text>
              : items.map((seq) => <Text key={seq.join("-")}>{seq.join(" → ")}</Text>);
          return (
            <>
              <Text>Stability Score: {stability.stability_score.toFixed(2)}</Text>
              <Text>Trend: {stability.trend}</Text>
              <Text style={styles.h2}>Drivers</Text>
              <Text style={styles.h2}>Rising Influence</Text>
              {idRows(drivers.rising_influence)}
              <Text style={styles.h2}>Falling Influence</Text>
              {idRows(drivers.falling_influence)}
              <Text style={styles.h2}>New Bottlenecks</Text>
              {idRows(drivers.new_bottlenecks)}
              <Text style={styles.h2}>Resolved Bottlenecks</Text>
              {idRows(drivers.resolved_bottlenecks)}
              <Text style={styles.h2}>New Loops</Text>
              {seqRows(drivers.new_loops)}
              <Text style={styles.h2}>Resolved Loops</Text>
              {seqRows(drivers.resolved_loops)}
              <Text style={styles.h2}>Chain Strengthening</Text>
              {seqRows(drivers.chain_strengthening)}
              <Text style={styles.h2}>Chain Weakening</Text>
              {seqRows(drivers.chain_weakening)}
            </>
          );
        })()}
      </View>

      {/* Phase 8.11 — Unified Narrative tile. Read-only: the Phase 8.10 unified
          temporal-causal narrative from GET /operator/telemetry, rendered as a
          monospace text block. No styling beyond monospace. */}
      <View style={styles.section}>
        <Text style={styles.h2}>Unified Narrative</Text>
        <Text style={styles.pre}>{phase7?.unified_narrative ?? ""}</Text>
      </View>

      {/* Phase 9.5 (Card 9.5) — Behavior tile. Read-only: the Phase 9.4
          behavioral motifs from GET /operator/telemetry → behavioral_motifs.
          One section per screen via a horizontal paging ScrollView (swipe to
          navigate the five sections); deterministic ordering (backend-sorted,
          rendered in array order); no animations, no inference text. */}
      <View style={styles.section}>
        <Text style={styles.h2}>Behavior</Text>
        <Text style={styles.behaviorHint}>‹ swipe to navigate sections ›</Text>
        {(() => {
          const motifs = phase7?.behavioral_motifs ?? EMPTY_BEHAVIORAL_MOTIFS;
          const seqRows = (items: string[][]) =>
            items.length === 0
              ? <Text>None</Text>
              : items.map((seq, i) => <Text key={i}>{seq.join(" → ")}</Text>);
          const labelRows = (items: string[]) =>
            items.length === 0
              ? <Text>None</Text>
              : items.map((label, i) => <Text key={`${label}-${i}`}>{label}</Text>);
          // One section per page; swipe horizontally to move between them.
          const pages: { title: string; body: ReactNode }[] = [
            { title: "Loops",       body: seqRows(motifs.action_loops) },
            { title: "Triggers",    body: seqRows(motifs.trigger_chains) },
            { title: "Habits",      body: labelRows(motifs.habits) },
            { title: "Bottlenecks", body: labelRows(motifs.action_bottlenecks) },
            { title: "Attractors",  body: labelRows(motifs.action_attractors) },
          ];
          return (
            <ScrollView
              horizontal
              pagingEnabled
              showsHorizontalScrollIndicator={false}
              style={styles.behaviorPager}
            >
              {pages.map((page) => (
                <View key={page.title} style={[styles.behaviorPage, { width: viewportWidth - 24 }]}>
                  <Text style={styles.h2}>{page.title}</Text>
                  {page.body}
                </View>
              ))}
            </ScrollView>
          );
        })()}
      </View>

      {/* Phase 10.4 (Card 10.4) — Behavioral Forecast tile. Read-only: the Phase
          10.0-10.3 outputs from GET /operator/telemetry → behavioral_forecast.
          One section per screen via a horizontal paging ScrollView (swipe to
          navigate the six sections); deterministic ordering; no animations, no
          inference text. Titled "Behavioral Forecast" to distinguish it from the
          9.5 "Behavior" (motifs) tile above. */}
      <View style={styles.section}>
        <Text style={styles.h2}>Behavioral Forecast</Text>
        <Text style={styles.behaviorHint}>‹ swipe to navigate sections ›</Text>
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
          const pages: { title: string; body: ReactNode }[] = [
            {
              title: "Next Actions",
              body: nextActions.length === 0
                ? <Text>None</Text>
                : nextActions.map((a, i) => (
                    <Text key={i}>{a.label} — {a.score.toFixed(2)}{driverTail(a.drivers)}</Text>
                  )),
            },
            {
              title: "Habits",
              body: habitChanges.length === 0
                ? <Text>None</Text>
                : habitChanges.map((h, i) => (
                    <Text key={i}>{h.action_id} — {h.trend} (Δ {h.delta.toFixed(2)})</Text>
                  )),
            },
            {
              title: "Triggers",
              body: triggerChanges.length === 0
                ? <Text>None</Text>
                : triggerChanges.map((t, i) => (
                    <Text key={i}>{t.chain.join(" → ")} (Δ {t.delta.toFixed(2)})</Text>
                  )),
            },
            {
              title: "Loops",
              body: loopChanges.length === 0
                ? <Text>None</Text>
                : loopChanges.map((l, i) => (
                    <Text key={i}>{l.loop.join(" → ")} ({l.continuation_probability.toFixed(2)})</Text>
                  )),
            },
            {
              title: "Stability",
              body: stability && stability.drivers
                ? (
                    <>
                      <Text>Score: {stability.score.toFixed(2)}</Text>
                      <Text>Habit stability: {stability.drivers.habit_stability.toFixed(2)}</Text>
                      <Text>Trigger stability: {stability.drivers.trigger_stability.toFixed(2)}</Text>
                      <Text>Loop persistence: {stability.drivers.loop_persistence.toFixed(2)}</Text>
                      <Text>Action variance: {stability.drivers.action_variance.toFixed(2)}</Text>
                    </>
                  )
                : <Text>None</Text>,
            },
            {
              title: "Narrative",
              body: (
                <>
                  <Text>{summary || "None"}</Text>
                  {highlights.map((h, i) => (
                    <Text key={i}>{h.action_id} — {h.score.toFixed(2)}{driverTail(h.drivers)}</Text>
                  ))}
                </>
              ),
            },
          ];
          return (
            <ScrollView
              horizontal
              pagingEnabled
              showsHorizontalScrollIndicator={false}
              style={styles.behaviorPager}
            >
              {pages.map((page) => (
                <View key={page.title} style={[styles.behaviorPage, { width: viewportWidth - 24 }]}>
                  <Text style={styles.h2}>{page.title}</Text>
                  {page.body}
                </View>
              ))}
            </ScrollView>
          );
        })()}
      </View>

      {/* Phase 11.2 (Card 11.2) — Actions tile. Read-only: the 11.0
          recommendations + 11.1 narrative from GET /operator/telemetry →
          recommendation_narrative. One section per screen via a horizontal
          paging ScrollView (swipe to navigate the four sections); deterministic
          ordering; no animations, no inference text. */}
      <View style={styles.section}>
        <Text style={styles.h2}>Actions</Text>
        <Text style={styles.behaviorHint}>‹ swipe to navigate sections ›</Text>
        {(() => {
          const rn = phase7?.recommendation_narrative ?? null;
          const recs = rn?.recommendations ?? [];
          const drivers = rn?.drivers ?? null;
          const stability = rn?.stability_context ?? null;
          const summary = rn?.summary ?? "";
          const top3 = recs.slice(0, 3);
          const driverBuckets = drivers
            ? ([
                ["Habit", drivers.habit],
                ["Triggers", drivers.triggers],
                ["Loops", drivers.loops],
                ["Bottlenecks", drivers.bottlenecks],
                ["Attractors", drivers.attractors],
                ["Forecast Alignment", drivers.forecast_alignment],
              ] as [string, RecDriverEntry[]][]).filter(([, e]) => (e ?? []).length > 0)
            : [];
          const pages: { title: string; body: ReactNode }[] = [
            {
              title: "Recommendations",
              body: recs.length === 0
                ? <Text>None</Text>
                : recs.map((r, i) => (
                    <Text key={i}>{r.label} — {r.reason} ({r.score.toFixed(2)})</Text>
                  )),
            },
            {
              title: "Drivers",
              body: driverBuckets.length === 0
                ? <Text>None</Text>
                : driverBuckets.map(([title, entries]) => (
                    <View key={title}>
                      <Text style={styles.h2}>{title}</Text>
                      {entries.map((e, i) => (
                        <Text key={i}>{e.action_id} — {e.reason} ({e.metric.toFixed(2)})</Text>
                      ))}
                    </View>
                  )),
            },
            {
              title: "Stability",
              body: stability && stability.drivers
                ? (
                    <>
                      <Text>Score: {stability.score.toFixed(2)}</Text>
                      <Text>Habit stability: {stability.drivers.habit_stability.toFixed(2)}</Text>
                      <Text>Trigger stability: {stability.drivers.trigger_stability.toFixed(2)}</Text>
                      <Text>Loop persistence: {stability.drivers.loop_persistence.toFixed(2)}</Text>
                      <Text>Action variance: {stability.drivers.action_variance.toFixed(2)}</Text>
                    </>
                  )
                : <Text>None</Text>,
            },
            {
              title: "Narrative",
              body: (
                <>
                  <Text>{summary || "None"}</Text>
                  {top3.map((r, i) => (
                    <Text key={i}>{r.label} — {r.explanation}</Text>
                  ))}
                </>
              ),
            },
          ];
          return (
            <ScrollView
              horizontal
              pagingEnabled
              showsHorizontalScrollIndicator={false}
              style={styles.behaviorPager}
            >
              {pages.map((page) => (
                <View key={page.title} style={[styles.behaviorPage, { width: viewportWidth - 24 }]}>
                  <Text style={styles.h2}>{page.title}</Text>
                  {page.body}
                </View>
              ))}
            </ScrollView>
          );
        })()}
      </View>

      {/* Phase 12.3 (Card 12.3) — engine version footer (read-only RC marker). */}
      <Text style={{ marginTop: 16, fontSize: 11, color: "#888" }}>
        ClarityOS operator-intelligence engine — v1.0.0-rc1
      </Text>
    </ScrollView>
  );
}

// Card 41 — minimal RN equivalent of HTML <details>/<summary>.
// Pressable header (▶ / ▼ indicator) + conditionally rendered body.
// Defined in-file rather than as a shared component to honour the
// card's "no new components" spirit while keeping the body of the
// console screen readable.
interface CollapsibleProps {
  label:    string;
  children: ReactNode;
}

function Collapsible({ label, children }: CollapsibleProps) {
  const [open, setOpen] = useState<boolean>(false);
  return (
    <View style={styles.section}>
      <Pressable onPress={() => setOpen((v) => !v)}>
        <Text style={styles.h2}>{open ? "▼ " : "▶ "}{label}</Text>
      </Pressable>
      {open ? <View>{children}</View> : null}
    </View>
  );
}

// Minimal layout-only styles. No theme tokens, no colours beyond
// monospace + borders — keeps the spec's "zero styling" rule honest
// while staying RN-renderable (RN won't display a bare nested Text
// inside a ScrollView without at least flex defaults).
const styles = StyleSheet.create({
  scroll:        { flex: 1 },
  scrollContent: { padding: 12 },
  h1:            { fontSize: 20, fontWeight: "600", marginBottom: 4 },
  h2:            { fontSize: 16, fontWeight: "600", marginTop: 12, marginBottom: 4 },
  section:       { marginTop: 12 },
  input:         {
    borderWidth: 1,
    borderColor: "#888",
    fontFamily:  "Courier",
    minHeight:   180,
    padding:     8,
  },
  button:        {
    borderWidth: 1,
    borderColor: "#888",
    paddingVertical:   6,
    paddingHorizontal: 12,
    alignSelf:    "flex-start",
    marginTop:    8,
  },
  error:         { color: "#a00", marginTop: 8 },
  pre:           {
    fontFamily: "Courier",
    fontSize:   12,
  },
  row:           { flexDirection: "row", alignItems: "center", flexWrap: "wrap" },
  indexInput:    {
    borderWidth: 1,
    borderColor: "#888",
    padding:     4,
    minWidth:    50,
  },
  // Phase 9.5 — Behavior tile pager + per-section page + swipe affordance.
  behaviorPager: { marginTop: 4 },
  behaviorPage:  { paddingVertical: 4, paddingRight: 12 },
  behaviorHint:  { fontSize: 11, color: "#888", marginBottom: 4 },
});
