// Card 90 — Operator Meta-Essence (Phase-5 AO-14).
//
// The final card of the final Operator Advanced Operator cluster (AO-9
// through AO-14, Cards 85-90) and the terminal operator of the entire
// 69-90 chain. If distillation (89) isolates the essential signal,
// essence (90) isolates the invariant identity — the part of the system
// that cannot be reduced, compressed, extracted, or distilled any
// further. This is the capstone of the operator meta-layer.
//
// Card 90 reads the invariant identity across all thirteen meta-
// operators — meta-pattern (77), meta-stability (78), meta-resilience
// (79), meta-immunity (80), meta-integration (81), meta-alignment (82),
// meta-coherence (83), meta-synthesis (84), meta-consolidation (85),
// meta-compression (86), meta-reduction (87), meta-extraction (88), and
// meta-distillation (89). Each "X-Essence" dimension reads the level of
// the corresponding meta-layer:
//
//   [Meta-Essence Level]              LOW … VERY-HIGH
//   [Pattern-Essence]                 "<word> essence"
//   [Stability-Essence]               "<word> essence"
//   [Resilience-Essence]              "<word> essence"
//   [Immunity-Essence]                "<word> essence"
//   [Integration-Essence]             "<word> integration essence"
//   [Alignment-Essence]               "<word> alignment essence"
//   [Coherence-Essence]               "<word> coherence essence"
//   [Synthesis-Essence]               "<word> synthesis essence"
//   [Consolidation-Essence]           "<word> consolidation essence"
//   [Compression-Essence]             "<word> compression essence"
//   [Reduction-Essence]               "<word> reduction essence"
//   [Extraction-Essence]              "<word> extraction essence"
//   [Distillation-Essence]            "<word> distillation essence"
//   [Meta-Essence Trajectory]         prev → level → projected (state)
//   [Meta-Essence Drivers]
//   [Meta-Essence Inhibitors]
//   [Meta-Essence Risks]
//   [Meta-Essence Reinforcement]
//   [Meta-Essence Decay]
//   [Operator Meta-Essence Summary]
//
// As the terminal capstone, its level is elevated into the VERY-HIGH
// band and its projected trajectory can reach the PEAK band beyond it.
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

// Essence word scale (weak < partial < moderate < strong).
type EssenceWord = "weak" | "partial" | "moderate" | "strong";

// ----- Section parser (same pattern as Cards 62-89) -------------------

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

// Maps a meta-layer level to an essence word. HIGH (and above) and
// MEDIUM-HIGH read "strong", MEDIUM "moderate", LOW-MEDIUM "partial",
// LOW "weak".
function levelWord(level: Level): EssenceWord {
  const r = LEVEL_RANK[level];
  if (r >= 3) return "strong";    // HIGH / VERY-HIGH / PEAK / MEDIUM-HIGH
  if (r === 2) return "moderate"; // MEDIUM
  if (r === 1) return "partial";  // LOW-MEDIUM
  return "weak";                  // LOW
}

// ----- Derived level ---------------------------------------------------

// Meta-essence level is the floored average of the thirteen essence
// facet levels, elevated two bands as the terminal capstone (essence is
// the invariant identity that survives at the peak), capped at VERY-HIGH
// — only the projected trajectory can reach the PEAK band beyond it.
function metaEssenceLevelOf(levels: Level[]): Level {
  const sum = levels.reduce((acc, l) => acc + LEVEL_RANK[l], 0);
  const avg = Math.floor(sum / levels.length);
  return RANK_TO_LEVEL[Math.max(0, Math.min(5, avg + 2))];
}

// Trajectory walks prev → level → projected (centered, like Cards
// 72/76/79/81/83/84). Clamps to [0, 6] so an improving projection from
// VERY-HIGH can reach the PEAK band.
function buildTrajectory(level: Level, direction: Direction): string {
  const cur      = LEVEL_RANK[level];
  const slope    = direction === "improving" ? 1 : direction === "deteriorating" ? -1 : 0;
  const prevRank = Math.max(0, Math.min(6, cur - slope));
  const projRank = Math.max(0, Math.min(6, cur + slope));
  const prev = RANK_TO_LEVEL[prevRank];
  const proj = RANK_TO_LEVEL[projRank];
  const moves = prev !== level || level !== proj;
  const tail  = moves ? "(projected)" : "(stable)";
  return `${prev.toLowerCase()} → ${level.toLowerCase()} → ${proj.toLowerCase()} ${tail}`;
}

// ----- Drivers / Inhibitors / Risks / Reinforcement / Decay -----------

function collectDrivers(
  patternWord:    EssenceWord,
  resilienceWord: EssenceWord,
  synthesisWord:  EssenceWord,
): string[] {
  const out: string[] = [];
  if (patternWord === "strong")    out.push("strong pattern essence");
  if (resilienceWord === "strong") out.push("strong resilience essence");
  if (synthesisWord === "strong")  out.push("strong synthesis essence");
  return out;
}

function collectInhibitors(
  immunityWord:  EssenceWord,
  stabilityWord: EssenceWord,
  pressure:      PressureLevel,
): string[] {
  const out: string[] = [];
  if (immunityWord !== "strong")  out.push(`${immunityWord} immunity essence`);
  if (stabilityWord !== "strong") out.push(`${stabilityWord} stability essence`);
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
  immunityWord: EssenceWord,
  load:         LoadLevel,
): string[] {
  const out: string[] = [];
  if (clarity !== "weak") out.push("maintain clarity discipline");
  if (drift !== "high")   out.push("maintain drift control");
  // Immunity verb-shift: strong → maintain, else → strengthen. Always
  // emits so reinforcement stays wide.
  if (immunityWord === "strong") out.push("maintain immunity essence");
  else                           out.push("strengthen immunity essence");
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
  if (pressure !== "low")   out.push("pressure may disrupt essence");
  if (drift !== "low")      out.push("drift may re-emerge");
  if (clarity !== "strong") out.push("clarity may weaken");
  return out;
}

// ----- Summary ---------------------------------------------------------

// The terminal summary leads with the meta-essence strength (a level
// word) rather than a direction verb, then names its three primary
// facets (pattern / resilience / synthesis) by their shared word.
function buildSummary(
  level:          Level,
  patternWord:    EssenceWord,
  resilienceWord: EssenceWord,
  synthesisWord:  EssenceWord,
  immunityWord:   EssenceWord,
): string {
  const lead = levelWord(level);
  const allSame = patternWord === resilienceWord && resilienceWord === synthesisWord;
  const prs = allSame
    ? `${patternWord} pattern-, resilience-, and synthesis-essence`
    : `${patternWord} pattern-, ${resilienceWord} resilience-, and ${synthesisWord} synthesis-essence`;
  const s1 = `Operator meta-essence is ${lead}, with ${prs}.`;
  if (immunityWord !== "strong") {
    return `${s1} Immunity-essence remains ${immunityWord} and may disrupt overall essence.`;
  }
  return s1;
}

// ----- Entry point -----------------------------------------------------

export function buildOperatorMetaEssence(
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
  operatorMetaDistillation:  string,
): string {
  // Reserve the operator-core layers on the signature — Cards 71-76
  // stay on the contract for symmetry with the rest of the AO chain.
  // Card 90 reads the invariant identity across the thirteen meta-
  // layers (77-89), which already fold the operator core + system-
  // operator integration stack.
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

  // Parse the thirteen essence facet levels.
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
  const metaDistillationLevel  = parseLayerLevel(operatorMetaDistillation, "Meta-Distillation Level");

  // Per-dimension essence words.
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
  const distillationWord  = levelWord(metaDistillationLevel);

  // Derived fields.
  const level = metaEssenceLevelOf([
    metaPatternLevel, metaStabilityLevel, metaResilienceLevel, metaImmunityLevel,
    metaIntegrationLevel, metaAlignmentLevel, metaCoherenceLevel, metaSynthesisLevel,
    metaConsolidationLevel, metaCompressionLevel, metaReductionLevel, metaExtractionLevel,
    metaDistillationLevel,
  ]);
  const trajectory    = buildTrajectory(level, direction);
  const drivers       = collectDrivers(patternWord, resilienceWord, synthesisWord);
  const inhibitors    = collectInhibitors(immunityWord, stabilityWord, pressure);
  const risks         = collectRisks(pressure, clarity, load);
  const reinforcement = collectReinforcement(clarity, drift, immunityWord, load);
  const decay         = collectDecay(pressure, drift, clarity);
  const summary       = buildSummary(level, patternWord, resilienceWord, synthesisWord, immunityWord);

  const blocks: string[] = [];
  blocks.push("=== Operator Meta-Essence ===");
  blocks.push(`[Meta-Essence Level]\n${level}`);
  blocks.push(`[Pattern-Essence]\n${patternWord} essence`);
  blocks.push(`[Stability-Essence]\n${stabilityWord} essence`);
  blocks.push(`[Resilience-Essence]\n${resilienceWord} essence`);
  blocks.push(`[Immunity-Essence]\n${immunityWord} essence`);
  blocks.push(`[Integration-Essence]\n${integrationWord} integration essence`);
  blocks.push(`[Alignment-Essence]\n${alignmentWord} alignment essence`);
  blocks.push(`[Coherence-Essence]\n${coherenceWord} coherence essence`);
  blocks.push(`[Synthesis-Essence]\n${synthesisWord} synthesis essence`);
  blocks.push(`[Consolidation-Essence]\n${consolidationWord} consolidation essence`);
  blocks.push(`[Compression-Essence]\n${compressionWord} compression essence`);
  blocks.push(`[Reduction-Essence]\n${reductionWord} reduction essence`);
  blocks.push(`[Extraction-Essence]\n${extractionWord} extraction essence`);
  blocks.push(`[Distillation-Essence]\n${distillationWord} distillation essence`);
  blocks.push(`[Meta-Essence Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Meta-Essence Drivers]\n(none)`
      : `[Meta-Essence Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Meta-Essence Inhibitors]\n(none)`
      : `[Meta-Essence Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Meta-Essence Risks]\n(none)`
      : `[Meta-Essence Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Meta-Essence Reinforcement]\n(none)`
      : `[Meta-Essence Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Meta-Essence Decay]\n(none)`
      : `[Meta-Essence Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[Operator Meta-Essence Summary]\n${summary}`);

  return blocks.join("\n\n");
}
