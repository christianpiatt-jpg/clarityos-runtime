// Card 82 — Operator Meta-Alignment (Phase-5 AO-6).
//
// Second card of the meta-integration cluster (AO-5 through AO-8,
// Cards 81-84). Same weight class as Cards 77-81: a lighter, higher-
// order interpretive layer over the operator meta-stack.
//
// Card 82 sits directly above the Card 81 meta-integration. Where
// meta-integration measures how well each facet is folded into the
// whole, meta-alignment measures how well the facets agree with each
// other and with the system-operator fusion layer. Each "X-Alignment"
// dimension reads the level of the corresponding upstream meta-layer:
//
//   [Meta-Alignment Level]            LOW … HIGH
//   [Coherence-Alignment]             "<word> alignment"
//   [Synthesis-Alignment]             "<word> alignment"
//   [Stability-Alignment]             "<word> alignment"
//   [Resilience-Alignment]            "<word> alignment"
//   [Immunity-Alignment]              "<word> alignment"
//   [Pattern-Alignment]               "<word> pattern alignment"
//   [Meta-Alignment Trajectory]       curr → next → projected (state)
//   [Meta-Alignment Drivers]
//   [Meta-Alignment Inhibitors]
//   [Meta-Alignment Risks]
//   [Meta-Alignment Reinforcement]
//   [Meta-Alignment Decay]
//   [Operator Meta-Alignment Summary]
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

// Alignment word scale (weak < partial < moderate < strong).
type AlignmentWord = "weak" | "partial" | "moderate" | "strong";

// How the upstream meta-pattern is holding (derived from Card 77 level).
type PatternWord = "stable" | "shifting" | "unstable";

// ----- Section parser (same pattern as Cards 62-81) -------------------

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

// ----- Level → word mappings ------------------------------------------

// Maps an upstream meta-layer level to an alignment word. HIGH and
// MEDIUM-HIGH both read "strong", MEDIUM "moderate", LOW-MEDIUM
// "partial", LOW "weak".
function levelWord(level: Level): AlignmentWord {
  const r = LEVEL_RANK[level];
  if (r >= 3) return "strong";    // HIGH, MEDIUM-HIGH
  if (r === 2) return "moderate"; // MEDIUM
  if (r === 1) return "partial";  // LOW-MEDIUM
  return "weak";                  // LOW
}

// Whether the upstream meta-pattern (Card 77 level) is holding. Reads
// lenient — MEDIUM and up are "stable" (matches Cards 78-81).
function patternWordOf(metaPatternLevel: Level): PatternWord {
  const r = LEVEL_RANK[metaPatternLevel];
  if (r >= 2) return "stable";    // MEDIUM, MEDIUM-HIGH, HIGH
  if (r >= 1) return "shifting";  // LOW-MEDIUM
  return "unstable";              // LOW
}

// ----- Derived level ---------------------------------------------------

function avgLevel(levels: Level[]): Level {
  const sum = levels.reduce((acc, l) => acc + LEVEL_RANK[l], 0);
  const avg = Math.floor(sum / levels.length);
  return RANK_TO_LEVEL[Math.max(0, Math.min(4, avg))];
}

// Meta-alignment level is the floored average of the six aligned facet
// levels, capped by the meta-integration level (Card 81) — the facets
// can't be more aligned than the system is integrated.
function metaAlignmentLevelOf(facetLevels: Level[], metaIntegrationLevel: Level): Level {
  const facetAvg = avgLevel(facetLevels);
  const rank = Math.min(LEVEL_RANK[facetAvg], LEVEL_RANK[metaIntegrationLevel]);
  return RANK_TO_LEVEL[Math.max(0, Math.min(4, rank))];
}

// Trajectory walks curr → next → projected (forward, like Cards
// 78/80) — alignment reads as a forward projection of agreement.
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
  synthesisWord:  AlignmentWord,
  resilienceWord: AlignmentWord,
  patternWord:    PatternWord,
): string[] {
  const out: string[] = [];
  if (synthesisWord === "strong")  out.push("strong synthesis alignment");
  if (resilienceWord === "strong") out.push("strong resilience alignment");
  if (patternWord === "stable")    out.push("stable pattern alignment");
  return out;
}

function collectInhibitors(
  immunityWord:  AlignmentWord,
  stabilityWord: AlignmentWord,
  pressure:      PressureLevel,
): string[] {
  const out: string[] = [];
  if (immunityWord !== "strong")  out.push(`${immunityWord} immunity alignment`);
  if (stabilityWord !== "strong") out.push(`${stabilityWord} stability alignment`);
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
  immunityWord: AlignmentWord,
  load:         LoadLevel,
): string[] {
  const out: string[] = [];
  if (clarity !== "weak") out.push("maintain clarity discipline");
  if (drift !== "high")   out.push("maintain drift control");
  // Immunity verb-shift: strong → maintain, else → strengthen. Always
  // emits so reinforcement stays wide.
  if (immunityWord === "strong") out.push("maintain immunity alignment");
  else                           out.push("strengthen immunity alignment");
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
  if (pressure !== "low")   out.push("pressure may disrupt alignment");
  if (drift !== "low")      out.push("drift may re-emerge");
  if (clarity !== "strong") out.push("clarity may weaken");
  return out;
}

// ----- Summary ---------------------------------------------------------

function buildSummary(
  direction:      Direction,
  synthesisWord:  AlignmentWord,
  resilienceWord: AlignmentWord,
  immunityWord:   AlignmentWord,
): string {
  const lead =
    direction === "improving"     ? "strengthening" :
    direction === "deteriorating" ? "weakening" :
    "steady";
  // Collapse the shared adjective when synthesis- and resilience-
  // alignment read the same word ("strong synthesis- and resilience-
  // alignment"), otherwise name both explicitly.
  const sr = synthesisWord === resilienceWord
    ? `${synthesisWord} synthesis- and resilience-alignment`
    : `${synthesisWord} synthesis- and ${resilienceWord} resilience-alignment`;
  const s1 = `Operator meta-alignment is ${lead}, with ${sr}.`;
  if (immunityWord !== "strong") {
    return `${s1} Immunity-alignment remains ${immunityWord} and may disrupt overall alignment.`;
  }
  return s1;
}

// ----- Entry point -----------------------------------------------------

export function buildOperatorMetaAlignment(
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
): string {
  // Reserve upstream layers on the signature — Cards 71/72/73 + 76 stay
  // on the contract so future AOs can read operator stability /
  // resilience / immunity / system-operator integration without
  // changing callers. Card 82 aligns the meta-layer levels directly
  // (coherence 74, synthesis 75, meta-pattern 77, meta-stability 78,
  // meta-resilience 79, meta-immunity 80) and caps on meta-integration
  // (81), which already fold the 71/72/73/76 stack.
  void operatorStability;
  void operatorResilience;
  void operatorImmunity;
  void systemOperatorIntegration;

  // Parse operator-state dims (Card 69) + direction (Card 70).
  const load      = parseLoad(operatorState);
  const drift     = parseDrift(operatorState);
  const clarity   = parseClarity(operatorState);
  const pressure  = parsePressure(operatorState);
  const direction = parseDirection(operatorDiff);

  // Parse the aligned meta-layer levels + the integration cap.
  const coherenceLevel      = parseLayerLevel(operatorCoherence, "Coherence Level");
  const synthesisLevel      = parseLayerLevel(operatorSynthesis, "Synthesis Level");
  const metaPatternLevel    = parseLayerLevel(operatorMetaPattern, "Meta-Pattern Level");
  const metaStabilityLevel  = parseLayerLevel(operatorMetaStability, "Meta-Stability Level");
  const metaResilienceLevel = parseLayerLevel(operatorMetaResilience, "Meta-Resilience Level");
  const metaImmunityLevel   = parseLayerLevel(operatorMetaImmunity, "Meta-Immunity Level");
  const metaIntegrationLevel = parseLayerLevel(operatorMetaIntegration, "Meta-Integration Level");

  // Per-dimension alignment words.
  const coherenceWord  = levelWord(coherenceLevel);
  const synthesisWord  = levelWord(synthesisLevel);
  const stabilityWord  = levelWord(metaStabilityLevel);
  const resilienceWord = levelWord(metaResilienceLevel);
  const immunityWord   = levelWord(metaImmunityLevel);
  const patternWord    = patternWordOf(metaPatternLevel);

  // Derived fields.
  const level = metaAlignmentLevelOf(
    [coherenceLevel, synthesisLevel, metaStabilityLevel, metaResilienceLevel, metaImmunityLevel, metaPatternLevel],
    metaIntegrationLevel,
  );
  const trajectory    = buildTrajectory(level, direction);
  const drivers       = collectDrivers(synthesisWord, resilienceWord, patternWord);
  const inhibitors    = collectInhibitors(immunityWord, stabilityWord, pressure);
  const risks         = collectRisks(pressure, clarity, load);
  const reinforcement = collectReinforcement(clarity, drift, immunityWord, load);
  const decay         = collectDecay(pressure, drift, clarity);
  const summary       = buildSummary(direction, synthesisWord, resilienceWord, immunityWord);

  const blocks: string[] = [];
  blocks.push("=== Operator Meta-Alignment ===");
  blocks.push(`[Meta-Alignment Level]\n${level}`);
  blocks.push(`[Coherence-Alignment]\n${coherenceWord} alignment`);
  blocks.push(`[Synthesis-Alignment]\n${synthesisWord} alignment`);
  blocks.push(`[Stability-Alignment]\n${stabilityWord} alignment`);
  blocks.push(`[Resilience-Alignment]\n${resilienceWord} alignment`);
  blocks.push(`[Immunity-Alignment]\n${immunityWord} alignment`);
  blocks.push(`[Pattern-Alignment]\n${patternWord} pattern alignment`);
  blocks.push(`[Meta-Alignment Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Meta-Alignment Drivers]\n(none)`
      : `[Meta-Alignment Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Meta-Alignment Inhibitors]\n(none)`
      : `[Meta-Alignment Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Meta-Alignment Risks]\n(none)`
      : `[Meta-Alignment Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Meta-Alignment Reinforcement]\n(none)`
      : `[Meta-Alignment Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Meta-Alignment Decay]\n(none)`
      : `[Meta-Alignment Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[Operator Meta-Alignment Summary]\n${summary}`);

  return blocks.join("\n\n");
}
