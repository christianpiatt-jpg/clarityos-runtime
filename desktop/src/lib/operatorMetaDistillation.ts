// Card 89 — Operator Meta-Distillation (Phase-5 AO-13).
//
// Fifth card of the final Operator Advanced Operator cluster (AO-9
// through AO-14, Cards 85-90) and the penultimate operator of the
// entire 69-90 chain. If extraction (88) isolates the actionable core,
// distillation (89) isolates the essential signal — the part of the
// structure that remains invariant under pressure, drift, load, or
// transformation. Same weight class as Cards 77-88.
//
// Card 89 distills the essential signal from all twelve meta-operators
// — meta-pattern (77), meta-stability (78), meta-resilience (79), meta-
// immunity (80), meta-integration (81), meta-alignment (82), meta-
// coherence (83), meta-synthesis (84), meta-consolidation (85), meta-
// compression (86), meta-reduction (87), and meta-extraction (88). Each
// "X-Distillation" dimension reads the level of the corresponding
// meta-layer:
//
//   [Meta-Distillation Level]         LOW … HIGH
//   [Pattern-Distillation]            "<word> distillation"
//   [Stability-Distillation]          "<word> distillation"
//   [Resilience-Distillation]         "<word> distillation"
//   [Immunity-Distillation]           "<word> distillation"
//   [Integration-Distillation]        "<word> integration distillation"
//   [Alignment-Distillation]          "<word> alignment distillation"
//   [Coherence-Distillation]          "<word> coherence distillation"
//   [Synthesis-Distillation]          "<word> synthesis distillation"
//   [Consolidation-Distillation]      "<word> consolidation distillation"
//   [Compression-Distillation]        "<word> compression distillation"
//   [Reduction-Distillation]          "<word> reduction distillation"
//   [Extraction-Distillation]         "<word> extraction distillation"
//   [Meta-Distillation Trajectory]    curr → next → projected (state)
//   [Meta-Distillation Drivers]
//   [Meta-Distillation Inhibitors]
//   [Meta-Distillation Risks]
//   [Meta-Distillation Reinforcement]
//   [Meta-Distillation Decay]
//   [Operator Meta-Distillation Summary]
//
// As the penultimate operator, its projected trajectory can reach a
// PEAK band beyond VERY-HIGH — the highest projection in the stack.
//
// Pure deterministic string IO — no backend, no styling, no new
// dependencies.

type Level = "LOW" | "LOW-MEDIUM" | "MEDIUM" | "MEDIUM-HIGH" | "HIGH" | "VERY-HIGH" | "PEAK";

const LEVEL_RANK: Record<Level, number> = {
  LOW: 0, "LOW-MEDIUM": 1, MEDIUM: 2, "MEDIUM-HIGH": 3, HIGH: 4, "VERY-HIGH": 5, PEAK: 6,
};
const RANK_TO_LEVEL: Record<number, Level> = {
  0: "LOW", 1: "LOW-MEDIUM", 2: "MEDIUM", 3: "MEDIUM-HIGH", 4: "HIGH", 5: "VERY-HIGH", 6: "PEAK",
};

type LoadLevel     = "low" | "moderate" | "high";
type DriftLevel    = "low" | "moderate" | "high";
type ClarityLevel  = "weak" | "partial" | "strong";
type PressureLevel = "low" | "moderate" | "elevated" | "high";
type Direction     = "improving" | "stable" | "deteriorating";

// Distillation word scale (weak < partial < moderate < strong).
type DistillationWord = "weak" | "partial" | "moderate" | "strong";

// ----- Section parser (same pattern as Cards 62-88) -------------------

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

// Parses a meta-layer level. Matches VERY-HIGH / PEAK before the
// shorter alternatives so they are not truncated.
function parseLayerLevel(text: string, header: string): Level {
  const body = parseSection(text, header);
  const m = body.match(/^(VERY-HIGH|PEAK|LOW-MEDIUM|MEDIUM-HIGH|LOW|MEDIUM|HIGH)/);
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

// Maps a meta-layer level to a distillation word. HIGH (and above) and
// MEDIUM-HIGH read "strong", MEDIUM "moderate", LOW-MEDIUM "partial",
// LOW "weak".
function levelWord(level: Level): DistillationWord {
  const r = LEVEL_RANK[level];
  if (r >= 3) return "strong";    // HIGH / VERY-HIGH / PEAK / MEDIUM-HIGH
  if (r === 2) return "moderate"; // MEDIUM
  if (r === 1) return "partial";  // LOW-MEDIUM
  return "weak";                  // LOW
}

// ----- Derived level ---------------------------------------------------

// Meta-distillation level is the floored average of the twelve
// distilled facet levels, capped at HIGH (the level itself never reads
// VERY-HIGH/PEAK — only the projected trajectory can reach those bands).
function metaDistillationLevelOf(levels: Level[]): Level {
  const sum = levels.reduce((acc, l) => acc + LEVEL_RANK[l], 0);
  const avg = Math.floor(sum / levels.length);
  return RANK_TO_LEVEL[Math.max(0, Math.min(4, avg))];
}

// Trajectory walks curr → next → projected (forward, like Cards
// 78/80/82/85-88). Clamps to [0, 6] so an improving projection from
// HIGH can reach VERY-HIGH and then the PEAK band.
function buildTrajectory(level: Level, direction: Direction): string {
  const cur   = LEVEL_RANK[level];
  const slope = direction === "improving" ? 1 : direction === "deteriorating" ? -1 : 0;
  const next  = Math.max(0, Math.min(6, cur + slope));
  const proj  = Math.max(0, Math.min(6, cur + 2 * slope));
  const nextL = RANK_TO_LEVEL[next];
  const projL = RANK_TO_LEVEL[proj];
  const moves = level !== nextL || nextL !== projL;
  const tail  = moves ? "(projected)" : "(stable)";
  return `${level.toLowerCase()} → ${nextL.toLowerCase()} → ${projL.toLowerCase()} ${tail}`;
}

// ----- Drivers / Inhibitors / Risks / Reinforcement / Decay -----------

function collectDrivers(
  patternWord:    DistillationWord,
  resilienceWord: DistillationWord,
  synthesisWord:  DistillationWord,
): string[] {
  const out: string[] = [];
  if (patternWord === "strong")    out.push("strong pattern distillation");
  if (resilienceWord === "strong") out.push("strong resilience distillation");
  if (synthesisWord === "strong")  out.push("strong synthesis distillation");
  return out;
}

function collectInhibitors(
  immunityWord:  DistillationWord,
  stabilityWord: DistillationWord,
  pressure:      PressureLevel,
): string[] {
  const out: string[] = [];
  if (immunityWord !== "strong")  out.push(`${immunityWord} immunity distillation`);
  if (stabilityWord !== "strong") out.push(`${stabilityWord} stability distillation`);
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
  immunityWord: DistillationWord,
  load:         LoadLevel,
): string[] {
  const out: string[] = [];
  if (clarity !== "weak") out.push("maintain clarity discipline");
  if (drift !== "high")   out.push("maintain drift control");
  // Immunity verb-shift: strong → maintain, else → strengthen. Always
  // emits so reinforcement stays wide.
  if (immunityWord === "strong") out.push("maintain immunity distillation");
  else                           out.push("strengthen immunity distillation");
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
  if (pressure !== "low")   out.push("pressure may disrupt distillation");
  if (drift !== "low")      out.push("drift may re-emerge");
  if (clarity !== "strong") out.push("clarity may weaken");
  return out;
}

// ----- Summary ---------------------------------------------------------

// As a late-stage capstone, the summary leads with the meta-
// distillation strength (a level word) rather than a direction verb,
// then names its three primary facets (pattern / resilience / synthesis)
// by their shared word.
function buildSummary(
  level:          Level,
  patternWord:    DistillationWord,
  resilienceWord: DistillationWord,
  synthesisWord:  DistillationWord,
  immunityWord:   DistillationWord,
): string {
  const lead = levelWord(level);
  const allSame = patternWord === resilienceWord && resilienceWord === synthesisWord;
  const prs = allSame
    ? `${patternWord} pattern-, resilience-, and synthesis-distillation`
    : `${patternWord} pattern-, ${resilienceWord} resilience-, and ${synthesisWord} synthesis-distillation`;
  const s1 = `Operator meta-distillation is ${lead}, with ${prs}.`;
  if (immunityWord !== "strong") {
    return `${s1} Immunity-distillation remains ${immunityWord} and may disrupt overall distillation.`;
  }
  return s1;
}

// ----- Entry point -----------------------------------------------------

export function buildOperatorMetaDistillation(
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
  operatorMetaCoherence:     string,
  operatorMetaSynthesis:     string,
  operatorMetaConsolidation: string,
  operatorMetaCompression:   string,
  operatorMetaReduction:     string,
  operatorMetaExtraction:    string,
): string {
  // Reserve the operator-core layers on the signature — Cards 71-76
  // stay on the contract so future AOs can read them without changing
  // callers. Card 89 distills the twelve meta-layers (77-88), which
  // already fold the operator core + system-operator integration stack.
  void operatorStability;
  void operatorResilience;
  void operatorImmunity;
  void operatorCoherence;
  void operatorSynthesis;
  void systemOperatorIntegration;

  // Parse operator-state dims (Card 69) + direction (Card 70).
  const load      = parseLoad(operatorState);
  const drift     = parseDrift(operatorState);
  const clarity   = parseClarity(operatorState);
  const pressure  = parsePressure(operatorState);
  const direction = parseDirection(operatorDiff);

  // Parse the twelve distilled meta-layer levels.
  const metaPatternLevel       = parseLayerLevel(operatorMetaPattern, "Meta-Pattern Level");
  const metaStabilityLevel     = parseLayerLevel(operatorMetaStability, "Meta-Stability Level");
  const metaResilienceLevel    = parseLayerLevel(operatorMetaResilience, "Meta-Resilience Level");
  const metaImmunityLevel      = parseLayerLevel(operatorMetaImmunity, "Meta-Immunity Level");
  const metaIntegrationLevel   = parseLayerLevel(operatorMetaIntegration, "Meta-Integration Level");
  const metaAlignmentLevel     = parseLayerLevel(operatorMetaAlignment, "Meta-Alignment Level");
  const metaCoherenceLevel     = parseLayerLevel(operatorMetaCoherence, "Meta-Coherence Level");
  const metaSynthesisLevel     = parseLayerLevel(operatorMetaSynthesis, "Meta-Synthesis Level");
  const metaConsolidationLevel = parseLayerLevel(operatorMetaConsolidation, "Meta-Consolidation Level");
  const metaCompressionLevel   = parseLayerLevel(operatorMetaCompression, "Meta-Compression Level");
  const metaReductionLevel     = parseLayerLevel(operatorMetaReduction, "Meta-Reduction Level");
  const metaExtractionLevel    = parseLayerLevel(operatorMetaExtraction, "Meta-Extraction Level");

  // Per-dimension distillation words.
  const patternWord       = levelWord(metaPatternLevel);
  const stabilityWord     = levelWord(metaStabilityLevel);
  const resilienceWord    = levelWord(metaResilienceLevel);
  const immunityWord      = levelWord(metaImmunityLevel);
  const integrationWord   = levelWord(metaIntegrationLevel);
  const alignmentWord     = levelWord(metaAlignmentLevel);
  const coherenceWord     = levelWord(metaCoherenceLevel);
  const synthesisWord     = levelWord(metaSynthesisLevel);
  const consolidationWord = levelWord(metaConsolidationLevel);
  const compressionWord   = levelWord(metaCompressionLevel);
  const reductionWord     = levelWord(metaReductionLevel);
  const extractionWord    = levelWord(metaExtractionLevel);

  // Derived fields.
  const level = metaDistillationLevelOf([
    metaPatternLevel, metaStabilityLevel, metaResilienceLevel, metaImmunityLevel,
    metaIntegrationLevel, metaAlignmentLevel, metaCoherenceLevel, metaSynthesisLevel,
    metaConsolidationLevel, metaCompressionLevel, metaReductionLevel, metaExtractionLevel,
  ]);
  const trajectory    = buildTrajectory(level, direction);
  const drivers       = collectDrivers(patternWord, resilienceWord, synthesisWord);
  const inhibitors    = collectInhibitors(immunityWord, stabilityWord, pressure);
  const risks         = collectRisks(pressure, clarity, load);
  const reinforcement = collectReinforcement(clarity, drift, immunityWord, load);
  const decay         = collectDecay(pressure, drift, clarity);
  const summary       = buildSummary(level, patternWord, resilienceWord, synthesisWord, immunityWord);

  const blocks: string[] = [];
  blocks.push("=== Operator Meta-Distillation ===");
  blocks.push(`[Meta-Distillation Level]\n${level}`);
  blocks.push(`[Pattern-Distillation]\n${patternWord} distillation`);
  blocks.push(`[Stability-Distillation]\n${stabilityWord} distillation`);
  blocks.push(`[Resilience-Distillation]\n${resilienceWord} distillation`);
  blocks.push(`[Immunity-Distillation]\n${immunityWord} distillation`);
  blocks.push(`[Integration-Distillation]\n${integrationWord} integration distillation`);
  blocks.push(`[Alignment-Distillation]\n${alignmentWord} alignment distillation`);
  blocks.push(`[Coherence-Distillation]\n${coherenceWord} coherence distillation`);
  blocks.push(`[Synthesis-Distillation]\n${synthesisWord} synthesis distillation`);
  blocks.push(`[Consolidation-Distillation]\n${consolidationWord} consolidation distillation`);
  blocks.push(`[Compression-Distillation]\n${compressionWord} compression distillation`);
  blocks.push(`[Reduction-Distillation]\n${reductionWord} reduction distillation`);
  blocks.push(`[Extraction-Distillation]\n${extractionWord} extraction distillation`);
  blocks.push(`[Meta-Distillation Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Meta-Distillation Drivers]\n(none)`
      : `[Meta-Distillation Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Meta-Distillation Inhibitors]\n(none)`
      : `[Meta-Distillation Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Meta-Distillation Risks]\n(none)`
      : `[Meta-Distillation Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Meta-Distillation Reinforcement]\n(none)`
      : `[Meta-Distillation Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Meta-Distillation Decay]\n(none)`
      : `[Meta-Distillation Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[Operator Meta-Distillation Summary]\n${summary}`);

  return blocks.join("\n\n");
}
