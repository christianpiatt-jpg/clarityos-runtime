// Phase 6 — Operator Superstructure (re-derived from the real meta-operator
// chain, Cards 77-90).
//
// Grounding note: the operator meta-operators do NOT emit typed
// `{ level, summary, text }` objects — each `buildOperatorMetaX(...)`
// (operatorMetaPattern.ts … operatorMetaEssence.ts) returns a single
// text block whose level lives on a `[Meta-X Level]` line, drawn from the
// 7-band vocabulary LOW | LOW-MEDIUM | MEDIUM | MEDIUM-HIGH | HIGH |
// VERY-HIGH | PEAK. This module therefore consumes those text strings
// directly (the `operatorMeta*Text` memos already computed in
// OperatorConsole) and parses the level with the same regex style the
// Card helpers use, mapping rank/6 → [0, 1].
//
// Pure + deterministic: no randomness, no timestamps, all floats ∈ [0, 1],
// identity strings stable.

// ----- Level vocabulary (matches Cards 77-90) -------------------------

type Level =
  | "LOW"
  | "LOW-MEDIUM"
  | "MEDIUM"
  | "MEDIUM-HIGH"
  | "HIGH"
  | "VERY-HIGH"
  | "PEAK";

const LEVEL_RANK: Record<Level, number> = {
  LOW: 0,
  "LOW-MEDIUM": 1,
  MEDIUM: 2,
  "MEDIUM-HIGH": 3,
  HIGH: 4,
  "VERY-HIGH": 5,
  PEAK: 6,
};

// Parse the `[<header>]` level line out of a meta-operator text block.
// Matches the longer tokens first so VERY-HIGH / PEAK / *-MEDIUM are not
// truncated. Absent / malformed input reads as LOW (no signal) so the
// derived floats stay honest rather than defaulting high.
function parseLevel(text: string, header: string): Level {
  const re = new RegExp(
    `\\[${header}\\]\\s*\\n\\s*(VERY-HIGH|PEAK|LOW-MEDIUM|MEDIUM-HIGH|LOW|MEDIUM|HIGH)`,
  );
  const m = text.match(re);
  return (m ? m[1] : "LOW") as Level;
}

// 7-band level → [0, 1].
function levelToNumber(level: Level): number {
  return LEVEL_RANK[level] / 6;
}

// ----- Output contracts (verbatim from the Phase 6 spec) --------------

export interface SuperPatternState {
  dominantPattern: string;
  patternStrength: number;
  patternStability: number;
  patternCoherence: number;
  patternIdentity: string;
}

export interface SuperIntegrationState {
  integrationStrength: number;
  crossLayerAlignment: number;
  integrationIdentity: string;
}

export interface SuperCoherenceState {
  coherenceLevel: number;
  driftResistance: number;
  loadResilience: number;
  coherenceIdentity: string;
}

export interface SuperEssenceState {
  essenceSignal: number;
  invariantIdentity: string;
  essenceClarity: number;
}

export interface SuperIdentityState {
  operatorIdentity: string;
  identityStrength: number;
  identityStability: number;
  identityProjection: number;
}

export interface SuperstructureState {
  pattern: SuperPatternState;
  integration: SuperIntegrationState;
  coherence: SuperCoherenceState;
  essence: SuperEssenceState;
  identity: SuperIdentityState;
}

// The real inputs: the text outputs of the meta-operators this
// superstructure re-derives from, plus the operator identity string.
// (Subset referenced by the spec — immunity/synthesis are not consumed.)
export interface MetaBundle {
  pattern: string;
  stability: string;
  resilience: string;
  integration: string;
  alignment: string;
  coherence: string;
  essence: string;
  consolidation: string;
  compression: string;
  reduction: string;
  extraction: string;
  distillation: string;
  operatorIdentity: string;
}

// Parsed numeric levels (each ∈ [0, 1]) — parsed once, threaded down.
interface MetaLevels {
  pattern: number;
  stability: number;
  resilience: number;
  integration: number;
  alignment: number;
  coherence: number;
  essence: number;
  consolidation: number;
  compression: number;
  reduction: number;
  extraction: number;
  distillation: number;
}

function parseLevels(meta: MetaBundle): MetaLevels {
  return {
    pattern:       levelToNumber(parseLevel(meta.pattern, "Meta-Pattern Level")),
    stability:     levelToNumber(parseLevel(meta.stability, "Meta-Stability Level")),
    resilience:    levelToNumber(parseLevel(meta.resilience, "Meta-Resilience Level")),
    integration:   levelToNumber(parseLevel(meta.integration, "Meta-Integration Level")),
    alignment:     levelToNumber(parseLevel(meta.alignment, "Meta-Alignment Level")),
    coherence:     levelToNumber(parseLevel(meta.coherence, "Meta-Coherence Level")),
    essence:       levelToNumber(parseLevel(meta.essence, "Meta-Essence Level")),
    consolidation: levelToNumber(parseLevel(meta.consolidation, "Meta-Consolidation Level")),
    compression:   levelToNumber(parseLevel(meta.compression, "Meta-Compression Level")),
    reduction:     levelToNumber(parseLevel(meta.reduction, "Meta-Reduction Level")),
    extraction:    levelToNumber(parseLevel(meta.extraction, "Meta-Extraction Level")),
    distillation:  levelToNumber(parseLevel(meta.distillation, "Meta-Distillation Level")),
  };
}

// ----------------------------
// Super-Pattern
// ----------------------------
function computeSuperPattern(levels: MetaLevels): SuperPatternState {
  const patternStrength =
    (levels.pattern +
      levels.consolidation +
      levels.compression +
      levels.extraction +
      levels.distillation) /
    5;

  const patternStability = levels.stability;
  const patternCoherence = levels.coherence;

  // Deterministic arg-max: first candidate wins on ties (strict >).
  const candidates: [string, number][] = [
    ["pattern", levels.pattern],
    ["consolidation", levels.consolidation],
    ["compression", levels.compression],
    ["extraction", levels.extraction],
    ["distillation", levels.distillation],
  ];
  let dominant = candidates[0];
  for (const c of candidates) {
    if (c[1] > dominant[1]) dominant = c;
  }
  const dominantPattern = dominant[0];

  const patternIdentity = `${dominantPattern}:${patternStrength.toFixed(2)}`;

  return {
    dominantPattern,
    patternStrength,
    patternStability,
    patternCoherence,
    patternIdentity,
  };
}

// ----------------------------
// Super-Integration
// ----------------------------
function computeSuperIntegration(levels: MetaLevels): SuperIntegrationState {
  const integrationStrength = levels.integration;
  const crossLayerAlignment = levels.alignment;

  const integrationIdentity = `int-${integrationStrength.toFixed(2)}-align-${crossLayerAlignment.toFixed(2)}`;

  return {
    integrationStrength,
    crossLayerAlignment,
    integrationIdentity,
  };
}

// ----------------------------
// Super-Coherence
// ----------------------------
function computeSuperCoherence(levels: MetaLevels): SuperCoherenceState {
  const coherenceLevel = levels.coherence;
  const driftResistance = levels.stability;
  const loadResilience = levels.resilience;

  const coherenceIdentity = `coh-${coherenceLevel.toFixed(2)}-drift-${driftResistance.toFixed(2)}-load-${loadResilience.toFixed(2)}`;

  return {
    coherenceLevel,
    driftResistance,
    loadResilience,
    coherenceIdentity,
  };
}

// ----------------------------
// Super-Essence
// ----------------------------
function computeSuperEssence(levels: MetaLevels): SuperEssenceState {
  const essenceSignal = levels.essence;
  const essenceClarity = levels.distillation;
  const stability = levels.stability;

  const invariantIdentity = `stable-${stability.toFixed(2)}-ess-${essenceSignal.toFixed(2)}`;

  return {
    essenceSignal,
    invariantIdentity,
    essenceClarity,
  };
}

// ----------------------------
// Super-Identity
// ----------------------------
function computeSuperIdentity(
  pattern: SuperPatternState,
  integration: SuperIntegrationState,
  coherence: SuperCoherenceState,
  essence: SuperEssenceState,
  meta: MetaBundle,
): SuperIdentityState {
  const identityStrength =
    (pattern.patternStrength +
      integration.integrationStrength +
      coherence.coherenceLevel +
      essence.essenceSignal) /
    4;

  const identityStability =
    (pattern.patternStability + coherence.driftResistance) / 2;

  const identityProjection =
    (identityStrength +
      identityStability +
      coherence.loadResilience +
      essence.essenceClarity) /
    4;

  const operatorIdentity = `${meta.operatorIdentity}:s${identityStrength.toFixed(2)}-c${coherence.coherenceLevel.toFixed(2)}`;

  return {
    operatorIdentity,
    identityStrength,
    identityStability,
    identityProjection,
  };
}

// ----------------------------
// Pipeline
// ----------------------------
export function runSuperstructure(meta: MetaBundle): SuperstructureState {
  const levels = parseLevels(meta);
  const pattern = computeSuperPattern(levels);
  const integration = computeSuperIntegration(levels);
  const coherence = computeSuperCoherence(levels);
  const essence = computeSuperEssence(levels);
  const identity = computeSuperIdentity(pattern, integration, coherence, essence, meta);

  return {
    pattern,
    integration,
    coherence,
    essence,
    identity,
  };
}
