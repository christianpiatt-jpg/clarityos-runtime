// Card 75 — Operator Synthesis Engine (Phase-5, Tier-7).
//
// Seventh operator-meta card. Combines Card 69 (state), Card 70
// (diff), Card 71 (stability), Card 72 (resilience), Card 73
// (immunity), and Card 74 (coherence) into a single 14-section
// synthesis layer — the unified, integrated read of the operator.
// Mirrors the structural pattern of Card 67 (Governance Synthesis)
// but applied to the operator.
//
// Emits 14 sub-blocks:
//
//   [Synthesis Level]              LOW … HIGH
//   [Operator Integration]         "<word> integration"   (weak/moderate/strong)
//   [Operator Unification]         "<word> unification"   (weak/partial/strong)
//   [Clarity-Synthesis]            weak / partial / strong
//   [Drift-Synthesis]              active / drifting / stable
//   [Load-Synthesis]               weak / moderate / strong
//   [Pressure-Synthesis]           weak / moderate / strong
//   [Synthesis Trajectory]         prev → synthesis → projected (state)
//   [Synthesis Drivers]
//   [Synthesis Inhibitors]
//   [Synthesis Risks]
//   [Synthesis Reinforcement]
//   [Synthesis Decay]
//   [Operator Synthesis Summary]
//
// Pure deterministic string IO — no backend, no styling, no new
// dependencies.

type Level = "LOW" | "LOW-MEDIUM" | "MEDIUM" | "MEDIUM-HIGH" | "HIGH";

const LEVEL_RANK: Record<Level, number> = {
  LOW: 0, "LOW-MEDIUM": 1, MEDIUM: 2, "MEDIUM-HIGH": 3, HIGH: 4,
};
const RANK_TO_LEVEL: Record<number, Level> = {
  0: "LOW", 1: "LOW-MEDIUM", 2: "MEDIUM", 3: "MEDIUM-HIGH", 4: "HIGH",
};

type LoadLevel     = "low" | "moderate" | "high";
type DriftLevel    = "low" | "moderate" | "high";
type ClarityLevel  = "weak" | "partial" | "strong";
type PressureLevel = "low" | "moderate" | "elevated" | "high";
type Direction     = "improving" | "stable" | "deteriorating";

// ----- Section parser (same pattern as Cards 62-74) -------------------

function parseSection(text: string, header: string): string {
  const re = new RegExp(`\\[${header}\\]\\s*\\n([\\s\\S]*?)(?=\\n\\[|$)`);
  const m  = text.match(re);
  return m ? m[1].trim() : "";
}

function parseLoad(text: string): LoadLevel {
  const body = parseSection(text, "Operator Load");
  if (body === "moderate") return "moderate";
  if (body === "high")     return "high";
  return "low";
}

function parseDrift(text: string): DriftLevel {
  const body = parseSection(text, "Operator Drift");
  if (body === "moderate") return "moderate";
  if (body === "high")     return "high";
  return "low";
}

function parseClarity(text: string): ClarityLevel {
  const body = parseSection(text, "Operator Clarity");
  if (body === "weak")    return "weak";
  if (body === "partial") return "partial";
  return "strong";
}

function parsePressure(text: string): PressureLevel {
  const body = parseSection(text, "Operator Pressure");
  if (body === "high")     return "high";
  if (body === "elevated") return "elevated";
  if (body === "moderate") return "moderate";
  return "low";
}

function parseLayerLevel(text: string, header: string): Level {
  const body = parseSection(text, header);
  const m = body.match(/^(LOW-MEDIUM|MEDIUM-HIGH|LOW|MEDIUM|HIGH)/);
  return (m ? m[1] : "HIGH") as Level;
}

// Direction inferred from Card 70's summary — same pattern as Cards 71-74.
function parseDirection(diffText: string): Direction {
  const summary = parseSection(diffText, "Operator Diff Summary");
  if (summary.includes("improving"))     return "improving";
  if (summary.includes("deteriorating")) return "deteriorating";
  return "stable";
}

// ----- Per-dim synthesis ----------------------------------------------

type ClaritySynthesis  = "weak" | "partial" | "strong";
type DriftSynthesis    = "active" | "drifting" | "stable";
type LoadSynthesis     = "weak" | "moderate" | "strong";
type PressureSynthesis = "weak" | "moderate" | "strong";

function claritySynthesisOf(c: ClarityLevel): ClaritySynthesis {
  if (c === "strong")  return "strong";
  if (c === "partial") return "partial";
  return "weak";
}

function driftSynthesisOf(d: DriftLevel): DriftSynthesis {
  if (d === "low")      return "stable";
  if (d === "moderate") return "drifting";
  return "active";
}

function loadSynthesisOf(l: LoadLevel): LoadSynthesis {
  if (l === "low")      return "strong";
  if (l === "moderate") return "moderate";
  return "weak";
}

function pressureSynthesisOf(p: PressureLevel): PressureSynthesis {
  if (p === "low")      return "strong";
  if (p === "moderate") return "moderate";
  return "weak"; // elevated / high
}

// ----- Overall integration + unification ------------------------------

type Integration = "weak" | "moderate" | "strong";
type Unification = "weak" | "partial" | "strong";

// Integration mirrors Card 74's vocab but uses the three upstream
// stability/resilience/immunity layers directly: all at MEDIUM-HIGH
// or above → strong, all at LOW → weak, anything mixed → moderate.
function integrationOf(
  stability:  Level,
  resilience: Level,
  immunity:   Level,
): Integration {
  const ranks       = [LEVEL_RANK[stability], LEVEL_RANK[resilience], LEVEL_RANK[immunity]];
  const strongCount = ranks.filter((r) => r >= 3).length;
  const weakCount   = ranks.filter((r) => r === 0).length;
  if (strongCount === 3) return "strong";
  if (weakCount   === 3) return "weak";
  return "moderate";
}

// Unification measures whether the four upstream layers (stability /
// resilience / immunity / coherence) are all firing at peak. All at
// HIGH = strong; any at LOW = weak; anything else partial. This
// formulation is more useful than spread-based unification because
// chained helpers tend to track together at the same rank, so
// "spread" would always be 0 in practice.
function unificationOf(
  stability:  Level,
  resilience: Level,
  immunity:   Level,
  coherence:  Level,
): Unification {
  const ranks = [
    LEVEL_RANK[stability], LEVEL_RANK[resilience],
    LEVEL_RANK[immunity],  LEVEL_RANK[coherence],
  ];
  const min = Math.min(...ranks);
  const max = Math.max(...ranks);
  if (max === 4 && min === 4) return "strong";
  if (min === 0)              return "weak";
  return "partial";
}

// ----- Synthesis level + trajectory -----------------------------------

// Synthesis = max of (coherence, stability, resilience, immunity).
// The unified layer represents the highest-functioning view of the
// operator — it can't be lower than its strongest upstream signal.
function synthesisLevelOf(
  stability:  Level,
  resilience: Level,
  immunity:   Level,
  coherence:  Level,
): Level {
  const max = Math.max(
    LEVEL_RANK[stability], LEVEL_RANK[resilience],
    LEVEL_RANK[immunity],  LEVEL_RANK[coherence],
  );
  return RANK_TO_LEVEL[Math.max(0, Math.min(4, max))];
}

// Trajectory walks prev → synthesis → projected (symmetric, like
// Cards 71-73). Unlike Card 74's all-forward trajectory, Card 75
// shows the synthesis as a centered checkpoint with history-and-
// projection on either side.
function buildTrajectory(synthesis: Level, direction: Direction): string {
  const synRank  = LEVEL_RANK[synthesis];
  const slope    = direction === "improving" ? 1 : direction === "deteriorating" ? -1 : 0;
  const prevRank = Math.max(0, Math.min(4, synRank - slope));
  const projRank = Math.max(0, Math.min(4, synRank + slope));
  const prev = RANK_TO_LEVEL[prevRank];
  const proj = RANK_TO_LEVEL[projRank];
  const moves = prev !== synthesis || synthesis !== proj;
  const tail = moves ? "(projected)" : "(stable)";
  return `${prev.toLowerCase()} → ${synthesis.toLowerCase()} → ${proj.toLowerCase()} ${tail}`;
}

// ----- Drivers / Inhibitors / Risks / Reinforcement / Decay -----------

function collectDrivers(
  direction:    Direction,
  clarity:      ClaritySynthesis,
  drift:        DriftSynthesis,
  integration:  Integration,
): string[] {
  const out: string[] = [];
  if (clarity === "strong")             out.push("strong clarity synthesis");
  if (drift   === "stable")             out.push("stable drift synthesis");
  if (direction === "improving" && integration !== "weak") {
    out.push("improving integration");
  } else if (integration === "strong") {
    out.push("steady integration");
  }
  // For non-improving directions with non-strong integration, no
  // forward-supporting driver fires — the layer is holding, not
  // moving.
  return out;
}

function collectInhibitors(
  pressureSynth: PressureSynthesis,
  unification:   Unification,
  load:          LoadLevel,
): string[] {
  const out: string[] = [];
  if (pressureSynth === "weak")     out.push("weak pressure synthesis");
  if (pressureSynth === "moderate") out.push("moderate pressure synthesis");
  if      (unification === "partial") out.push("partial unification");
  else if (unification === "weak")    out.push("weak unification");
  if (load !== "low") out.push("load imbalance");
  return out;
}

function collectRisks(
  pressure: PressureLevel,
  clarity:  ClarityLevel,
  drift:    DriftLevel,
): string[] {
  const out: string[] = [];
  if (pressure !== "low") out.push("fragmentation under pressure");
  if (clarity  !== "strong" || pressure !== "low") {
    out.push("clarity degradation");
  }
  if (drift !== "low" || pressure !== "low") {
    out.push("drift reactivation");
  }
  return out;
}

function collectReinforcement(
  clarity:     ClarityLevel,
  drift:       DriftLevel,
  unification: Unification,
  load:        LoadLevel,
): string[] {
  const out: string[] = [];
  if (clarity !== "weak") out.push("maintain clarity discipline");
  if (drift   !== "high") out.push("maintain drift control");
  // Unification gets a verb-shift: strong → maintain, partial/weak →
  // strengthen. Always emits a line so the reinforcement block stays
  // four lines wide.
  if (unification === "strong") out.push("maintain unification");
  else                          out.push("strengthen unification");
  if (load !== "high") out.push("balance load");
  return out;
}

function collectDecay(
  pressure: PressureLevel,
  drift:    DriftLevel,
  clarity:  ClarityLevel,
): string[] {
  const out: string[] = [];
  if (pressure !== "low") out.push("pressure may disrupt synthesis");
  if (drift    !== "low") out.push("drift may re-emerge");
  if (clarity  !== "strong") out.push("clarity may weaken");
  return out;
}

// ----- Summary ---------------------------------------------------------

function buildSummary(
  direction:        Direction,
  claritySynth:     ClaritySynthesis,
  driftSynth:       DriftSynthesis,
  pressureSynth:    PressureSynthesis,
): string {
  let s1: string;
  if (direction === "improving") {
    s1 = `Operator synthesis is strengthening, with ${claritySynth} clarity-synthesis and ${driftSynth} drift-synthesis.`;
  } else if (direction === "deteriorating") {
    s1 = `Operator synthesis is weakening, with ${claritySynth} clarity-synthesis and ${driftSynth} drift-synthesis.`;
  } else {
    s1 = `Operator synthesis is steady, with ${claritySynth} clarity-synthesis and ${driftSynth} drift-synthesis.`;
  }

  if (pressureSynth === "weak") {
    return `${s1} Pressure-synthesis remains weak and may disrupt overall synthesis.`;
  }
  return s1;
}

// ----- Entry point -----------------------------------------------------

export function buildOperatorSynthesis(
  operatorState:      string,
  operatorDiff:       string,
  operatorStability:  string,
  operatorResilience: string,
  operatorImmunity:   string,
  operatorCoherence:  string,
): string {
  // Parse state dims.
  const load     = parseLoad(operatorState);
  const drift    = parseDrift(operatorState);
  const clarity  = parseClarity(operatorState);
  const pressure = parsePressure(operatorState);

  // Parse upstream layer levels.
  const stability  = parseLayerLevel(operatorStability,  "Stability Level");
  const resilience = parseLayerLevel(operatorResilience, "Resilience Level");
  const immunity   = parseLayerLevel(operatorImmunity,   "Immunity Level");
  const coherence  = parseLayerLevel(operatorCoherence,  "Coherence Level");

  // Parse Card 70 direction.
  const direction = parseDirection(operatorDiff);

  // Derive per-dim synthesis.
  const claritySynth  = claritySynthesisOf(clarity);
  const driftSynth    = driftSynthesisOf(drift);
  const loadSynth     = loadSynthesisOf(load);
  const pressureSynth = pressureSynthesisOf(pressure);

  // Derive overall fields.
  const integration   = integrationOf(stability, resilience, immunity);
  const unification   = unificationOf(stability, resilience, immunity, coherence);
  const synthesis     = synthesisLevelOf(stability, resilience, immunity, coherence);
  const trajectory    = buildTrajectory(synthesis, direction);
  const drivers       = collectDrivers(direction, claritySynth, driftSynth, integration);
  const inhibitors    = collectInhibitors(pressureSynth, unification, load);
  const risks         = collectRisks(pressure, clarity, drift);
  const reinforcement = collectReinforcement(clarity, drift, unification, load);
  const decay         = collectDecay(pressure, drift, clarity);
  const summary       = buildSummary(direction, claritySynth, driftSynth, pressureSynth);

  const blocks: string[] = [];
  blocks.push("=== Operator Synthesis ===");
  blocks.push(`[Synthesis Level]\n${synthesis}`);
  blocks.push(`[Operator Integration]\n${integration} integration`);
  blocks.push(`[Operator Unification]\n${unification} unification`);
  blocks.push(`[Clarity-Synthesis]\n${claritySynth}`);
  blocks.push(`[Drift-Synthesis]\n${driftSynth}`);
  blocks.push(`[Load-Synthesis]\n${loadSynth}`);
  blocks.push(`[Pressure-Synthesis]\n${pressureSynth}`);
  blocks.push(`[Synthesis Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Synthesis Drivers]\n(none)`
      : `[Synthesis Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Synthesis Inhibitors]\n(none)`
      : `[Synthesis Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Synthesis Risks]\n(none)`
      : `[Synthesis Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Synthesis Reinforcement]\n(none)`
      : `[Synthesis Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Synthesis Decay]\n(none)`
      : `[Synthesis Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[Operator Synthesis Summary]\n${summary}`);

  return blocks.join("\n\n");
}
