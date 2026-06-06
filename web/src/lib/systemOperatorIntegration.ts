// Card 76 — System-Operator Integration Engine (Phase-5, Tier-8).
//
// Phase-5 capstone. Fuses the system-level Phase-2/Phase-3 outputs
// with the operator-level Phase-5 outputs (Cards 69-75) into a
// single unified read — the OS sees system + operator as one
// integrated entity instead of two parallel stacks.
//
// Emits 11 sub-blocks:
//
//   [Integration Level]              LOW … HIGH
//   [System-Operator Alignment]      "<word> alignment"  (weak/partial/strong)
//   [System-Operator Coherence]      "<word> coherence"  (weak/moderate/strong)
//   [System-Operator Synthesis]      "<word> synthesis"  (weak/moderate/strong)
//   [Integration Trajectory]         prev → integration → projected (state)
//   [Integration Drivers]
//   [Integration Inhibitors]
//   [Integration Risks]
//   [Integration Reinforcement]
//   [Integration Decay]
//   [System-Operator Integration Summary]
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

// ----- Section parser (same pattern as Cards 62-75) -------------------

function parseSection(text: string, header: string): string {
  const re = new RegExp(`\\[${header}\\]\\s*\\n([\\s\\S]*?)(?=\\n\\[|$)`);
  const m  = text.match(re);
  return m ? m[1].trim() : "";
}

// Try each candidate header in order; return the first level found.
// Defaults to HIGH (the no-signal baseline) so a missing section
// doesn't drag the integration score down unfairly.
function parseLevelMulti(text: string, headers: readonly string[]): Level {
  for (const h of headers) {
    const body = parseSection(text, h);
    const m = body.match(/^(LOW-MEDIUM|MEDIUM-HIGH|LOW|MEDIUM|HIGH)/);
    if (m) return m[1] as Level;
  }
  return "HIGH";
}

// Operator-state dim parsers (same as Cards 71-75).

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

// Direction inferred from the operator diff summary (same pattern
// as Cards 71-75). Falls back to stable when no signal is present.
function parseDirection(diffText: string): Direction {
  const summary = parseSection(diffText, "Operator Diff Summary");
  if (summary.includes("improving"))     return "improving";
  if (summary.includes("deteriorating")) return "deteriorating";
  return "stable";
}

// ----- Derived fields --------------------------------------------------

type AlignmentWord = "weak" | "partial" | "strong";
type CoherenceWord = "weak" | "moderate" | "strong";
type SynthesisWord = "weak" | "moderate" | "strong";

// Integration Level = average of the top-tier system layer (immunity)
// and the top-tier operator layer (synthesis), rounded down. The
// unified state can't outrun whichever side is the bottleneck.
function integrationLevelOf(sysImmunity: Level, opSynthesis: Level): Level {
  const avg = Math.floor((LEVEL_RANK[sysImmunity] + LEVEL_RANK[opSynthesis]) / 2);
  return RANK_TO_LEVEL[Math.max(0, Math.min(4, avg))];
}

// System-Operator Alignment: strong only when both top layers fire
// at HIGH; weak when either drops to LOW or when they diverge by
// 2+ levels; partial otherwise.
function alignmentOf(sysImmunity: Level, opSynthesis: Level): AlignmentWord {
  const s = LEVEL_RANK[sysImmunity];
  const o = LEVEL_RANK[opSynthesis];
  if (s === 4 && o === 4)        return "strong";
  if (s === 0 || o === 0)        return "weak";
  if (Math.abs(s - o) >= 2)      return "weak";
  return "partial";
}

// Coherence reads strict — only HIGH coherence reads as "strong", so
// the integration view can distinguish a HIGH-only stack from a
// MEDIUM-HIGH-ish stack where synthesis still fires at "strong".
function coherenceWordOf(opCoherence: Level): CoherenceWord {
  if (LEVEL_RANK[opCoherence] === 4) return "strong";
  if (LEVEL_RANK[opCoherence] >= 2)  return "moderate";
  return "weak";
}

// Synthesis reads lenient — MEDIUM-HIGH and HIGH both read as
// "strong", reflecting that synthesis is the high-water mark of the
// operator stack.
function synthesisWordOf(opSynthesis: Level): SynthesisWord {
  if (LEVEL_RANK[opSynthesis] >= 3) return "strong";
  if (LEVEL_RANK[opSynthesis] >= 2) return "moderate";
  return "weak";
}

// Trajectory walks prev → integration → projected (symmetric, like
// Cards 71-73/75).
function buildTrajectory(integration: Level, direction: Direction): string {
  const intRank  = LEVEL_RANK[integration];
  const slope    = direction === "improving" ? 1 : direction === "deteriorating" ? -1 : 0;
  const prevRank = Math.max(0, Math.min(4, intRank - slope));
  const projRank = Math.max(0, Math.min(4, intRank + slope));
  const prev = RANK_TO_LEVEL[prevRank];
  const proj = RANK_TO_LEVEL[projRank];
  const moves = prev !== integration || integration !== proj;
  const tail = moves ? "(projected)" : "(stable)";
  return `${prev.toLowerCase()} → ${integration.toLowerCase()} → ${proj.toLowerCase()} ${tail}`;
}

// ----- Drivers / Inhibitors / Risks / Reinforcement / Decay -----------

function collectDrivers(
  direction:    Direction,
  synthesis:    SynthesisWord,
  sysResilience: Level,
  coherence:    CoherenceWord,
): string[] {
  const out: string[] = [];
  if (synthesis === "strong")             out.push("strong operator synthesis");
  if (LEVEL_RANK[sysResilience] >= 3)      out.push("stable system resilience");
  if (direction === "improving" && coherence !== "weak") {
    out.push("improving coherence");
  } else if (coherence === "strong") {
    out.push("steady coherence");
  }
  return out;
}

function collectInhibitors(
  alignment: AlignmentWord,
  pressure:  PressureLevel,
  load:      LoadLevel,
): string[] {
  const out: string[] = [];
  if      (alignment === "partial") out.push("partial alignment");
  else if (alignment === "weak")    out.push("weak alignment");
  if (pressure !== "low") out.push("pressure sensitivity");
  if (load     !== "low") out.push("load imbalance");
  return out;
}

function collectRisks(
  pressure:  PressureLevel,
  alignment: AlignmentWord,
  clarity:   ClarityLevel,
): string[] {
  const out: string[] = [];
  if (pressure !== "low")     out.push("fragmentation under pressure");
  if (alignment !== "strong") out.push("misalignment between system and operator");
  if (clarity  !== "strong" || alignment !== "strong") {
    out.push("clarity degradation");
  }
  return out;
}

function collectReinforcement(
  clarity:   ClarityLevel,
  drift:     DriftLevel,
  alignment: AlignmentWord,
  load:      LoadLevel,
): string[] {
  const out: string[] = [];
  if (clarity !== "weak") out.push("maintain clarity discipline");
  if (drift   !== "high") out.push("maintain drift control");
  // Alignment verb-shift: strong → maintain, partial/weak →
  // strengthen. Always emits a line so reinforcement stays 4 wide.
  if (alignment === "strong") out.push("maintain alignment");
  else                        out.push("strengthen alignment");
  if (load !== "high") out.push("balance load");
  return out;
}

function collectDecay(
  pressure: PressureLevel,
  drift:    DriftLevel,
  clarity:  ClarityLevel,
): string[] {
  const out: string[] = [];
  if (pressure !== "low")    out.push("pressure may disrupt integration");
  if (drift    !== "low")    out.push("drift may re-emerge");
  if (clarity  !== "strong") out.push("clarity may weaken");
  return out;
}

// ----- Summary ---------------------------------------------------------

function buildSummary(
  direction: Direction,
  synthesis: SynthesisWord,
  coherence: CoherenceWord,
  alignment: AlignmentWord,
): string {
  let s1: string;
  if (direction === "improving") {
    s1 = `System-operator integration is strengthening, with ${synthesis} synthesis and ${coherence} coherence.`;
  } else if (direction === "deteriorating") {
    s1 = `System-operator integration is weakening, with ${synthesis} synthesis and ${coherence} coherence.`;
  } else {
    s1 = `System-operator integration is steady, with ${synthesis} synthesis and ${coherence} coherence.`;
  }

  if      (alignment === "partial") return `${s1} Alignment remains partial and may disrupt overall integration.`;
  else if (alignment === "weak")    return `${s1} Alignment is weak and may disrupt overall integration.`;
  return s1;
}

// ----- Entry point -----------------------------------------------------

export function buildSystemOperatorIntegration(
  systemState:        string,
  systemDiff:         string,
  systemStability:    string,
  systemResilience:   string,
  systemImmunity:     string,
  operatorState:      string,
  operatorDiff:       string,
  operatorStability:  string,
  operatorResilience: string,
  operatorImmunity:   string,
  operatorCoherence:  string,
  operatorSynthesis:  string,
): string {
  // Suppress unused-parameter warnings — these are reserved on the
  // signature for future system-side extensions (e.g., a future
  // system-coherence layer can be parsed without changing callers).
  void systemState;
  void systemDiff;
  void operatorStability;
  void operatorResilience;
  void operatorImmunity;

  // Parse top-tier system scores. Card 58 (stabilization) uses
  // "Stabilization Probability"; Cards 59/60 use "Resilience Score"
  // and "Immunity Score" respectively.
  const sysStability  = parseLevelMulti(systemStability,  ["Stabilization Probability", "Stability Level"]);
  const sysResilience = parseLevelMulti(systemResilience, ["Resilience Score", "Resilience Level"]);
  const sysImmunity   = parseLevelMulti(systemImmunity,   ["Immunity Score", "Immunity Level"]);
  void sysStability; // reserved for future stability-side derivation

  // Parse operator dim signals.
  const load     = parseLoad(operatorState);
  const drift    = parseDrift(operatorState);
  const clarity  = parseClarity(operatorState);
  const pressure = parsePressure(operatorState);

  // Parse operator top-tier levels.
  const opCoherence = parseLevelMulti(operatorCoherence, ["Coherence Level"]);
  const opSynthesis = parseLevelMulti(operatorSynthesis, ["Synthesis Level"]);

  // Parse direction from operator diff.
  const direction = parseDirection(operatorDiff);

  // Derived fields.
  const integration   = integrationLevelOf(sysImmunity, opSynthesis);
  const alignment     = alignmentOf(sysImmunity, opSynthesis);
  const coherence     = coherenceWordOf(opCoherence);
  const synthesis     = synthesisWordOf(opSynthesis);
  const trajectory    = buildTrajectory(integration, direction);
  const drivers       = collectDrivers(direction, synthesis, sysResilience, coherence);
  const inhibitors    = collectInhibitors(alignment, pressure, load);
  const risks         = collectRisks(pressure, alignment, clarity);
  const reinforcement = collectReinforcement(clarity, drift, alignment, load);
  const decay         = collectDecay(pressure, drift, clarity);
  const summary       = buildSummary(direction, synthesis, coherence, alignment);

  const blocks: string[] = [];
  blocks.push("=== System-Operator Integration ===");
  blocks.push(`[Integration Level]\n${integration}`);
  blocks.push(`[System-Operator Alignment]\n${alignment} alignment`);
  blocks.push(`[System-Operator Coherence]\n${coherence} coherence`);
  blocks.push(`[System-Operator Synthesis]\n${synthesis} synthesis`);
  blocks.push(`[Integration Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Integration Drivers]\n(none)`
      : `[Integration Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Integration Inhibitors]\n(none)`
      : `[Integration Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Integration Risks]\n(none)`
      : `[Integration Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Integration Reinforcement]\n(none)`
      : `[Integration Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Integration Decay]\n(none)`
      : `[Integration Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[System-Operator Integration Summary]\n${summary}`);

  return blocks.join("\n\n");
}
