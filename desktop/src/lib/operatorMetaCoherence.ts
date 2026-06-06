// Card 83 — Operator Meta-Coherence (Phase-5 AO-7).
//
// Third card of the meta-integration cluster (AO-5 through AO-8,
// Cards 81-84). Same weight class as Cards 77-82: a lighter, higher-
// order interpretive layer over the operator meta-stack.
//
// Card 83 is the highest-order coherence engine in the operator meta-
// layer. Where Card 74 measured the operator's own internal coherence,
// meta-coherence measures how coherently the *meta-operators* hold
// together — across synthesis (75), meta-stability (78), meta-
// resilience (79), meta-immunity (80), meta-integration (81), and
// meta-alignment (82). Each "X-Coherence" dimension reads the level of
// the corresponding upstream layer:
//
//   [Meta-Coherence Level]            LOW … HIGH
//   [Synthesis-Coherence]             "<word> coherence"
//   [Stability-Coherence]             "<word> coherence"
//   [Resilience-Coherence]            "<word> coherence"
//   [Immunity-Coherence]              "<word> coherence"
//   [Integration-Coherence]           "<word> integration coherence"
//   [Alignment-Coherence]             "<word> alignment coherence"
//   [Meta-Coherence Trajectory]       prev → level → projected (state)
//   [Meta-Coherence Drivers]
//   [Meta-Coherence Inhibitors]
//   [Meta-Coherence Risks]
//   [Meta-Coherence Reinforcement]
//   [Meta-Coherence Decay]
//   [Operator Meta-Coherence Summary]
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

// Coherence word scale (weak < partial < moderate < strong).
type CoherenceWord = "weak" | "partial" | "moderate" | "strong";

// ----- Section parser (same pattern as Cards 62-82) -------------------

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

// ----- Level → word mapping -------------------------------------------

// Maps an upstream meta-layer level to a coherence word. HIGH and
// MEDIUM-HIGH both read "strong", MEDIUM "moderate", LOW-MEDIUM
// "partial", LOW "weak".
function levelWord(level: Level): CoherenceWord {
  const r = LEVEL_RANK[level];
  if (r >= 3) return "strong";    // HIGH, MEDIUM-HIGH
  if (r === 2) return "moderate"; // MEDIUM
  if (r === 1) return "partial";  // LOW-MEDIUM
  return "weak";                  // LOW
}

// ----- Derived level ---------------------------------------------------

// Meta-coherence level is the floored average of the six coherence
// facet levels — the unified read can't sit above the mean of the
// facets it harmonises.
function metaCoherenceLevelOf(levels: Level[]): Level {
  const sum = levels.reduce((acc, l) => acc + LEVEL_RANK[l], 0);
  const avg = Math.floor(sum / levels.length);
  return RANK_TO_LEVEL[Math.max(0, Math.min(4, avg))];
}

// Trajectory walks prev → level → projected (centered, like Cards
// 72/76/79/81).
function buildTrajectory(level: Level, direction: Direction): string {
  const cur      = LEVEL_RANK[level];
  const slope    = direction === "improving" ? 1 : direction === "deteriorating" ? -1 : 0;
  const prevRank = Math.max(0, Math.min(4, cur - slope));
  const projRank = Math.max(0, Math.min(4, cur + slope));
  const prev = RANK_TO_LEVEL[prevRank];
  const proj = RANK_TO_LEVEL[projRank];
  const moves = prev !== level || level !== proj;
  const tail  = moves ? "(projected)" : "(stable)";
  return `${prev.toLowerCase()} → ${level.toLowerCase()} → ${proj.toLowerCase()} ${tail}`;
}

// ----- Drivers / Inhibitors / Risks / Reinforcement / Decay -----------

function collectDrivers(
  synthesisWord:   CoherenceWord,
  resilienceWord:  CoherenceWord,
  integrationWord: CoherenceWord,
): string[] {
  const out: string[] = [];
  if (synthesisWord === "strong")   out.push("strong synthesis coherence");
  if (resilienceWord === "strong")  out.push("strong resilience coherence");
  if (integrationWord === "strong") out.push("strong integration coherence");
  return out;
}

function collectInhibitors(
  immunityWord:  CoherenceWord,
  stabilityWord: CoherenceWord,
  pressure:      PressureLevel,
): string[] {
  const out: string[] = [];
  if (immunityWord !== "strong")  out.push(`${immunityWord} immunity coherence`);
  if (stabilityWord !== "strong") out.push(`${stabilityWord} stability coherence`);
  if (pressure === "elevated" || pressure === "high") out.push("elevated pressure");
  return out;
}

function collectRisks(
  pressure: PressureLevel,
  clarity:  ClarityLevel,
  load:     LoadLevel,
): string[] {
  const out: string[] = [];
  if (pressure !== "low")   out.push("pressure-induced fragmentation");
  if (clarity !== "strong") out.push("clarity degradation");
  if (load !== "low")       out.push("load imbalance");
  return out;
}

function collectReinforcement(
  clarity:      ClarityLevel,
  drift:        DriftLevel,
  immunityWord: CoherenceWord,
  load:         LoadLevel,
): string[] {
  const out: string[] = [];
  if (clarity !== "weak") out.push("maintain clarity discipline");
  if (drift !== "high")   out.push("maintain drift control");
  // Immunity verb-shift: strong → maintain, else → strengthen. Always
  // emits so reinforcement stays wide.
  if (immunityWord === "strong") out.push("maintain immunity coherence");
  else                           out.push("strengthen immunity coherence");
  // Load verb-shift: low → maintain, else → balance.
  if (load === "low") out.push("maintain load balance");
  else                out.push("balance load");
  return out;
}

function collectDecay(
  pressure: PressureLevel,
  drift:    DriftLevel,
  clarity:  ClarityLevel,
): string[] {
  const out: string[] = [];
  if (pressure !== "low")   out.push("pressure may disrupt coherence");
  if (drift !== "low")      out.push("drift may re-emerge");
  if (clarity !== "strong") out.push("clarity may weaken");
  return out;
}

// ----- Summary ---------------------------------------------------------

function buildSummary(
  direction:       Direction,
  synthesisWord:   CoherenceWord,
  resilienceWord:  CoherenceWord,
  integrationWord: CoherenceWord,
  immunityWord:    CoherenceWord,
): string {
  const lead =
    direction === "improving"     ? "strengthening" :
    direction === "deteriorating" ? "weakening" :
    "steady";
  // Collapse the shared adjective when synthesis-, resilience-, and
  // integration-coherence all read the same word, otherwise name each.
  const allSame = synthesisWord === resilienceWord && resilienceWord === integrationWord;
  const sri = allSame
    ? `${synthesisWord} synthesis-, resilience-, and integration-coherence`
    : `${synthesisWord} synthesis-, ${resilienceWord} resilience-, and ${integrationWord} integration-coherence`;
  const s1 = `Operator meta-coherence is ${lead}, with ${sri}.`;
  if (immunityWord !== "strong") {
    return `${s1} Immunity-coherence remains ${immunityWord} and may disrupt overall coherence.`;
  }
  return s1;
}

// ----- Entry point -----------------------------------------------------

export function buildOperatorMetaCoherence(
  operatorState:             string,
  operatorDiff:              string,
  operatorStability:         string,
  operatorResilience:        string,
  operatorImmunity:          string,
  operatorCoherence:         string,
  operatorSynthesis:         string,
  systemOperatorIntegration: string,
  operatorMetaPattern:       string,
  operatorMetaStability:     string,
  operatorMetaResilience:    string,
  operatorMetaImmunity:      string,
  operatorMetaIntegration:   string,
  operatorMetaAlignment:     string,
): string {
  // Reserve upstream layers on the signature — Cards 71/72/73 +
  // operator coherence (74) + system-operator integration (76) + meta-
  // pattern (77) stay on the contract so future AOs can read them
  // without changing callers. Card 83 harmonises synthesis (75) with
  // the five higher meta-layers (78-82), which already fold the rest.
  void operatorStability;
  void operatorResilience;
  void operatorImmunity;
  void operatorCoherence;
  void systemOperatorIntegration;
  void operatorMetaPattern;

  // Parse operator-state dims (Card 69) + direction (Card 70).
  const load      = parseLoad(operatorState);
  const drift     = parseDrift(operatorState);
  const clarity   = parseClarity(operatorState);
  const pressure  = parsePressure(operatorState);
  const direction = parseDirection(operatorDiff);

  // Parse the six coherence facet levels.
  const synthesisLevel      = parseLayerLevel(operatorSynthesis, "Synthesis Level");
  const metaStabilityLevel  = parseLayerLevel(operatorMetaStability, "Meta-Stability Level");
  const metaResilienceLevel = parseLayerLevel(operatorMetaResilience, "Meta-Resilience Level");
  const metaImmunityLevel   = parseLayerLevel(operatorMetaImmunity, "Meta-Immunity Level");
  const metaIntegrationLevel = parseLayerLevel(operatorMetaIntegration, "Meta-Integration Level");
  const metaAlignmentLevel   = parseLayerLevel(operatorMetaAlignment, "Meta-Alignment Level");

  // Per-dimension coherence words.
  const synthesisWord   = levelWord(synthesisLevel);
  const stabilityWord   = levelWord(metaStabilityLevel);
  const resilienceWord  = levelWord(metaResilienceLevel);
  const immunityWord    = levelWord(metaImmunityLevel);
  const integrationWord = levelWord(metaIntegrationLevel);
  const alignmentWord   = levelWord(metaAlignmentLevel);

  // Derived fields.
  const level = metaCoherenceLevelOf([
    synthesisLevel, metaStabilityLevel, metaResilienceLevel,
    metaImmunityLevel, metaIntegrationLevel, metaAlignmentLevel,
  ]);
  const trajectory    = buildTrajectory(level, direction);
  const drivers       = collectDrivers(synthesisWord, resilienceWord, integrationWord);
  const inhibitors    = collectInhibitors(immunityWord, stabilityWord, pressure);
  const risks         = collectRisks(pressure, clarity, load);
  const reinforcement = collectReinforcement(clarity, drift, immunityWord, load);
  const decay         = collectDecay(pressure, drift, clarity);
  const summary       = buildSummary(direction, synthesisWord, resilienceWord, integrationWord, immunityWord);

  const blocks: string[] = [];
  blocks.push("=== Operator Meta-Coherence ===");
  blocks.push(`[Meta-Coherence Level]\n${level}`);
  blocks.push(`[Synthesis-Coherence]\n${synthesisWord} coherence`);
  blocks.push(`[Stability-Coherence]\n${stabilityWord} coherence`);
  blocks.push(`[Resilience-Coherence]\n${resilienceWord} coherence`);
  blocks.push(`[Immunity-Coherence]\n${immunityWord} coherence`);
  blocks.push(`[Integration-Coherence]\n${integrationWord} integration coherence`);
  blocks.push(`[Alignment-Coherence]\n${alignmentWord} alignment coherence`);
  blocks.push(`[Meta-Coherence Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Meta-Coherence Drivers]\n(none)`
      : `[Meta-Coherence Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Meta-Coherence Inhibitors]\n(none)`
      : `[Meta-Coherence Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Meta-Coherence Risks]\n(none)`
      : `[Meta-Coherence Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Meta-Coherence Reinforcement]\n(none)`
      : `[Meta-Coherence Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Meta-Coherence Decay]\n(none)`
      : `[Meta-Coherence Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[Operator Meta-Coherence Summary]\n${summary}`);

  return blocks.join("\n\n");
}
