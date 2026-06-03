// Card 77 — Operator Meta-Pattern (Phase-5 AO-1).
//
// First of the Operator Advanced Operators (AO-1 through AO-14,
// Cards 77-90). These are lighter than the core operators (69-76):
// they extend the meta-layer with higher-order interpretive
// functions rather than introducing new structural engines.
//
// Card 77 fuses the seven operator core outputs (Cards 69-75) and
// the system-operator integration (Card 76) into a single 12-section
// meta-pattern read:
//
//   [Meta-Pattern Level]              LOW … HIGH
//   [Meta-Alignment]                  "<word> alignment"  (weak/partial/strong)
//   [Meta-Drift Detection]            "<word> drift detected"  (low/moderate/high)
//   [Meta-Load Interpretation]        "<word> load"  (low/moderate/high)
//   [Meta-Pressure Interpretation]    "<word> pressure"  (low/moderate/elevated/high)
//   [Meta-Trajectory]                 curr → next → projected (state)
//   [Meta-Pattern Drivers]
//   [Meta-Pattern Inhibitors]
//   [Meta-Pattern Risks]
//   [Meta-Pattern Reinforcement]
//   [Meta-Pattern Decay]
//   [Operator Meta-Pattern Summary]
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

type AlignmentWord = "weak" | "partial" | "strong";
type CoherenceWord = "weak" | "moderate" | "strong";
type SynthesisWord = "weak" | "moderate" | "strong";

// ----- Section parser (same pattern as Cards 62-76) -------------------

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

// Direction inferred from Card 70's diff summary.
function parseDirection(diffText: string): Direction {
  const summary = parseSection(diffText, "Operator Diff Summary");
  if (summary.includes("improving"))     return "improving";
  if (summary.includes("deteriorating")) return "deteriorating";
  return "stable";
}

// Parse the leading word of a Card 76 `<word> alignment` block.
function parseAlignmentWord(integrationText: string): AlignmentWord {
  const body = parseSection(integrationText, "System-Operator Alignment");
  if (body.startsWith("strong"))  return "strong";
  if (body.startsWith("weak"))    return "weak";
  if (body.startsWith("partial")) return "partial";
  return "strong";
}

function parseCoherenceWord(integrationText: string): CoherenceWord {
  const body = parseSection(integrationText, "System-Operator Coherence");
  if (body.startsWith("strong"))   return "strong";
  if (body.startsWith("weak"))     return "weak";
  if (body.startsWith("moderate")) return "moderate";
  return "strong";
}

function parseSynthesisWord(integrationText: string): SynthesisWord {
  const body = parseSection(integrationText, "System-Operator Synthesis");
  if (body.startsWith("strong"))   return "strong";
  if (body.startsWith("weak"))     return "weak";
  if (body.startsWith("moderate")) return "moderate";
  return "strong";
}

// ----- Derived fields --------------------------------------------------

// Meta-pattern level floors on integration with single-step penalties
// for elevated/high pressure and non-strong alignment. Mirrors the
// way Card 73/76 used composite penalties.
function metaPatternLevelOf(
  integration: Level,
  pressure:    PressureLevel,
  alignment:   AlignmentWord,
): Level {
  let rank = LEVEL_RANK[integration];
  if (pressure === "elevated" || pressure === "high") rank -= 1;
  if (alignment === "weak")                           rank -= 1;
  rank = Math.max(0, Math.min(4, rank));
  return RANK_TO_LEVEL[rank];
}

// Trajectory walks curr → next → projected (forward, like Card 74)
// — meta-pattern reads as a projection, not a centered checkpoint.
function buildTrajectory(level: Level, direction: Direction): string {
  const cur   = LEVEL_RANK[level];
  const slope = direction === "improving" ? 1 : direction === "deteriorating" ? -1 : 0;
  const next  = Math.max(0, Math.min(4, cur + slope));
  const proj  = Math.max(0, Math.min(4, cur + 2 * slope));
  const nextL = RANK_TO_LEVEL[next];
  const projL = RANK_TO_LEVEL[proj];
  const moves = level !== nextL || nextL !== projL;
  const tail  = moves ? "(projected)" : "(stable)";
  return `${level.toLowerCase()} → ${nextL.toLowerCase()} → ${projL.toLowerCase()} ${tail}`;
}

// ----- Drivers / Inhibitors / Risks / Reinforcement / Decay -----------

function collectDrivers(
  synthesis: SynthesisWord,
  direction: Direction,
  coherence: CoherenceWord,
  drift:     DriftLevel,
): string[] {
  const out: string[] = [];
  if (synthesis === "strong")             out.push("strong synthesis");
  if (direction === "improving" && coherence !== "weak") {
    out.push("improving coherence");
  } else if (coherence === "strong") {
    out.push("steady coherence");
  }
  if (drift === "low") out.push("stable drift profile");
  return out;
}

function collectInhibitors(
  pressure:  PressureLevel,
  alignment: AlignmentWord,
  load:      LoadLevel,
): string[] {
  const out: string[] = [];
  if      (pressure === "high")     out.push("high pressure");
  else if (pressure === "elevated") out.push("elevated pressure");
  else if (pressure === "moderate") out.push("moderate pressure");
  if      (alignment === "partial") out.push("partial alignment");
  else if (alignment === "weak")    out.push("weak alignment");
  if (load !== "low") out.push("load imbalance");
  return out;
}

function collectRisks(
  pressure:  PressureLevel,
  alignment: AlignmentWord,
  clarity:   ClarityLevel,
): string[] {
  const out: string[] = [];
  if (pressure !== "low" || alignment !== "strong") {
    out.push("pattern fragmentation");
  }
  if (pressure !== "low") out.push("pressure-induced drift");
  if (clarity !== "strong" || alignment !== "strong") {
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
  // strengthen. Always emits to keep reinforcement 4 wide.
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
  if (pressure !== "low")    out.push("pressure may disrupt pattern stability");
  if (drift    !== "low")    out.push("drift may re-emerge");
  if (clarity  !== "strong") out.push("clarity may weaken");
  return out;
}

// ----- Summary ---------------------------------------------------------

function buildSummary(
  direction: Direction,
  synthesis: SynthesisWord,
  drift:     DriftLevel,
  pressure:  PressureLevel,
): string {
  const driftWord = drift === "low" ? "stable" : drift === "moderate" ? "drifting" : "active";

  let s1: string;
  if (direction === "improving") {
    s1 = `Operator meta-pattern stability is improving, with ${synthesis} synthesis and ${driftWord} drift.`;
  } else if (direction === "deteriorating") {
    s1 = `Operator meta-pattern stability is weakening, with ${synthesis} synthesis and ${driftWord} drift.`;
  } else {
    s1 = `Operator meta-pattern stability is steady, with ${synthesis} synthesis and ${driftWord} drift.`;
  }

  if (pressure === "elevated") {
    return `${s1} Pressure remains elevated and may disrupt overall pattern integrity.`;
  }
  if (pressure === "high") {
    return `${s1} Pressure is high and may disrupt overall pattern integrity.`;
  }
  return s1;
}

// ----- Entry point -----------------------------------------------------

export function buildOperatorMetaPattern(
  operatorState:             string,
  operatorDiff:              string,
  operatorStability:         string,
  operatorResilience:        string,
  operatorImmunity:          string,
  operatorCoherence:         string,
  operatorSynthesis:         string,
  systemOperatorIntegration: string,
): string {
  // Reserve unused inputs on the signature — Cards 71-73 stay on
  // the contract so future AOs can read upstream stability/resilience/
  // immunity layers without changing callers.
  void operatorStability;
  void operatorResilience;
  void operatorImmunity;

  // Parse operator-state dims.
  const load     = parseLoad(operatorState);
  const drift    = parseDrift(operatorState);
  const clarity  = parseClarity(operatorState);
  const pressure = parsePressure(operatorState);

  // Parse direction from Card 70.
  const direction = parseDirection(operatorDiff);

  // Parse the operator-coherence + synthesis levels (used to assess
  // the meta-pattern's directional momentum).
  void parseLayerLevel(operatorCoherence, "Coherence Level");
  void parseLayerLevel(operatorSynthesis, "Synthesis Level");

  // Parse Card 76 outputs.
  const integration = parseLayerLevel(systemOperatorIntegration, "Integration Level");
  const alignment   = parseAlignmentWord(systemOperatorIntegration);
  const coherence   = parseCoherenceWord(systemOperatorIntegration);
  const synthesis   = parseSynthesisWord(systemOperatorIntegration);

  // Derived fields.
  const level         = metaPatternLevelOf(integration, pressure, alignment);
  const trajectory    = buildTrajectory(level, direction);
  const drivers       = collectDrivers(synthesis, direction, coherence, drift);
  const inhibitors    = collectInhibitors(pressure, alignment, load);
  const risks         = collectRisks(pressure, alignment, clarity);
  const reinforcement = collectReinforcement(clarity, drift, alignment, load);
  const decay         = collectDecay(pressure, drift, clarity);
  const summary       = buildSummary(direction, synthesis, drift, pressure);

  // Render with the demo's "<word> X" detection/interpretation
  // formatting for the single-line tier blocks.
  const blocks: string[] = [];
  blocks.push("=== Operator Meta-Pattern ===");
  blocks.push(`[Meta-Pattern Level]\n${level}`);
  blocks.push(`[Meta-Alignment]\n${alignment} alignment`);
  blocks.push(`[Meta-Drift Detection]\n${drift} drift detected`);
  blocks.push(`[Meta-Load Interpretation]\n${load} load`);
  blocks.push(`[Meta-Pressure Interpretation]\n${pressure} pressure`);
  blocks.push(`[Meta-Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Meta-Pattern Drivers]\n(none)`
      : `[Meta-Pattern Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Meta-Pattern Inhibitors]\n(none)`
      : `[Meta-Pattern Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Meta-Pattern Risks]\n(none)`
      : `[Meta-Pattern Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Meta-Pattern Reinforcement]\n(none)`
      : `[Meta-Pattern Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Meta-Pattern Decay]\n(none)`
      : `[Meta-Pattern Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[Operator Meta-Pattern Summary]\n${summary}`);

  return blocks.join("\n\n");
}
