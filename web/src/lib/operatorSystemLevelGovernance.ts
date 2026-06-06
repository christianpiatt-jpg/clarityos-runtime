// Card 68 — System-Level Governance engine (Phase-4, Tier-8 — FINAL).
//
// Phase-4 capstone. Unifies Cards 61-67 into a single top-level,
// system-wide governance evaluation — the "governance of governance".
//
// Emits 13 sub-blocks:
//
//   [System Governance Level]      LOW … HIGH
//   [Governance Integrity]         weak / partial / strong
//   [Governance Cohesion]          weak / moderate / strong
//   [Governance Robustness]        weak / partial / strong
//   [Governance Meta-Stability]    weak / moderate / strong
//   [Governance Meta-Risk]         low / moderate / elevated / high
//   [System Governance Trajectory] gov → systemLevel → projected (state)
//   [System Governance Drivers]
//   [System Governance Inhibitors]
//   [System Governance Risks]
//   [System Governance Reinforcement]
//   [System Governance Decay]
//   [System-Level Governance Summary]
//
// Pure deterministic string IO — no backend, no styling, no new
// dependencies.

const LEVELS = ["LOW", "LOW-MEDIUM", "MEDIUM", "MEDIUM-HIGH", "HIGH"] as const;
type Level = typeof LEVELS[number];

const LEVEL_RANK: Record<Level, number> = {
  LOW: 0, "LOW-MEDIUM": 1, MEDIUM: 2, "MEDIUM-HIGH": 3, HIGH: 4,
};
const RANK_TO_LEVEL: Record<number, Level> = {
  0: "LOW", 1: "LOW-MEDIUM", 2: "MEDIUM", 3: "MEDIUM-HIGH", 4: "HIGH",
};

// ----- Section parser (same pattern as Cards 62-67) -------------------

function parseSection(text: string, header: string): string {
  const re = new RegExp(`\\[${header}\\]\\s*\\n([\\s\\S]*?)(?=\\n\\[|$)`);
  const m  = text.match(re);
  return m ? m[1].trim() : "";
}

function parseLevel(text: string, header: string): Level {
  const body = parseSection(text, header);
  const m = body.match(/^(LOW-MEDIUM|MEDIUM-HIGH|LOW|MEDIUM|HIGH)/);
  return (m ? m[1] : "LOW") as Level;
}

interface Profile {
  invariant:   string;
  threshold:   string;
  upperBranch: string;
  volatility:  string;
}

const DEFAULT_PROFILE: Profile = {
  invariant: "weak", threshold: "weak", upperBranch: "weak", volatility: "weak",
};

function parseProfile(text: string): Profile {
  const body  = parseSection(text, "Governance Profile");
  const lines = body.split("\n").filter((l) => l.startsWith("- "));
  const out: Profile = { ...DEFAULT_PROFILE };
  for (const l of lines) {
    const word = l.match(/^-\s+(\w+)/)?.[1] ?? "weak";
    if      (l.includes("invariant compliance"))      out.invariant   = word;
    else if (l.includes("threshold adherence"))       out.threshold   = word;
    else if (l.includes("upper-branch containment"))  out.upperBranch = word;
    else if (l.includes("volatility control"))        out.volatility  = word;
  }
  return out;
}

function parseListSection(text: string, header: string): string[] {
  const body = parseSection(text, header);
  const out: string[] = [];
  for (const l of body.split("\n")) {
    if (l.startsWith("- ")) out.push(l.slice(2).trim());
  }
  return out;
}

function parseSlope(diff: string): number {
  const body     = parseSection(diff, "Governance Slope").trim();
  const stripped = body.replace(/^\+/, "");
  const n = Number(stripped);
  return Number.isFinite(n) ? n : 0;
}

type Direction = "improving" | "stable" | "deteriorating";

function parseDirection(diff: string): Direction {
  const body = parseSection(diff, "Governance Direction");
  if (body === "improving")     return "improving";
  if (body === "deteriorating") return "deteriorating";
  return "stable";
}

type Pressure = "low" | "moderate" | "high";

function parsePressure(diff: string): Pressure {
  const body = parseSection(diff, "Governance Pressure");
  if (body === "high")     return "high";
  if (body === "moderate") return "moderate";
  return "low";
}

type Card63Integrity = "strong" | "moderate" | "weak";

function parseCard63Integrity(stability: string): Card63Integrity {
  const body = parseSection(stability, "Governance Integrity");
  if (body === "strong") return "strong";
  if (body === "weak")   return "weak";
  return "moderate";
}

type Hardening = "weak" | "partial" | "strong";

function parseHardening(imm: string): Hardening {
  const body = parseSection(imm, "Governance Hardening");
  if (body === "strong") return "strong";
  if (body === "weak")   return "weak";
  return "partial";
}

type Alignment = "weak" | "partial" | "strong";

function parseAlignment(coh: string): Alignment {
  const body = parseSection(coh, "Governance Alignment");
  if (body === "strong") return "strong";
  if (body === "weak")   return "weak";
  return "partial";
}

type ContradictionRisk = "low" | "moderate" | "elevated" | "high";

function parseContradictionRisk(coh: string): ContradictionRisk {
  const body = parseSection(coh, "Contradiction Risk");
  if (body === "high")     return "high";
  if (body === "elevated") return "elevated";
  if (body === "moderate") return "moderate";
  return "low";
}

type Integration = "weak" | "partial" | "strong";

function parseIntegration(syn: string): Integration {
  const body = parseSection(syn, "Governance Integration");
  if (body === "strong") return "strong";
  if (body === "weak")   return "weak";
  return "partial";
}

type Unification = "weak" | "moderate" | "strong";

function parseUnification(syn: string): Unification {
  const body = parseSection(syn, "Governance Unification");
  if (body === "strong") return "strong";
  if (body === "weak")   return "weak";
  return "moderate";
}

type MetaConsistency = "weak" | "partial" | "strong";

function parseMetaConsistency(syn: string): MetaConsistency {
  const body = parseSection(syn, "Meta-Consistency");
  if (body === "strong") return "strong";
  if (body === "weak")   return "weak";
  return "partial";
}

type SynthesisMetaRisk = "low" | "moderate" | "elevated" | "high";

function parseSynthesisMetaRisk(syn: string): SynthesisMetaRisk {
  const body = parseSection(syn, "Meta-Risk");
  if (body === "high")     return "high";
  if (body === "elevated") return "elevated";
  if (body === "moderate") return "moderate";
  return "low";
}

// ----- Strength rank ---------------------------------------------------

function strengthRank(s: string): number {
  switch (s.toLowerCase()) {
    case "weak":     return 0;
    case "partial":  return 1;
    case "moderate": return 1;
    case "full":     return 2;
    case "strong":   return 2;
    default:         return 0;
  }
}

// ----- Derived fields --------------------------------------------------

// System governance floors on the weakest of the five upstream
// layers (stability / resilience / immunity / coherence / synthesis)
// — the meta-state can't outrun the slowest layer. Inhibitor density
// and weak threshold trigger further decrements.
function systemGovernanceLevelOf(
  stability:  Level,
  resilience: Level,
  immunity:   Level,
  coherence:  Level,
  synthesis:  Level,
  inhibitors: string[],
  profile:    Profile,
): Level {
  let rank = Math.min(
    LEVEL_RANK[stability], LEVEL_RANK[resilience],
    LEVEL_RANK[immunity],  LEVEL_RANK[coherence],
    LEVEL_RANK[synthesis],
  );
  if (inhibitors.length >= 4)               rank -= 1;
  if (strengthRank(profile.threshold) === 0) rank -= 1;
  rank = Math.max(0, Math.min(4, rank));
  return RANK_TO_LEVEL[rank];
}

type GovernanceIntegrity = "weak" | "partial" | "strong";

function governanceIntegrityOf(
  card63Integrity:   Card63Integrity,
  contradictionRisk: ContradictionRisk,
): GovernanceIntegrity {
  if (card63Integrity === "strong" && contradictionRisk === "low") return "strong";
  if (card63Integrity === "weak"   || contradictionRisk === "high") return "weak";
  return "partial";
}

type GovernanceCohesion = "weak" | "moderate" | "strong";

function governanceCohesionOf(
  govLevel:   Level, stability: Level, resilience: Level,
  immunity:   Level, coherence: Level, synthesis:  Level,
): GovernanceCohesion {
  const ranks = [
    LEVEL_RANK[govLevel],  LEVEL_RANK[stability], LEVEL_RANK[resilience],
    LEVEL_RANK[immunity],  LEVEL_RANK[coherence], LEVEL_RANK[synthesis],
  ];
  const spread = Math.max(...ranks) - Math.min(...ranks);
  if (spread === 0) return "strong";
  if (spread === 1) return "moderate";
  return "weak";
}

type GovernanceRobustness = "weak" | "partial" | "strong";

function governanceRobustnessOf(
  hardening:         Hardening,
  card63Integrity:   Card63Integrity,
  layerSpread:       number,
  contradictionRisk: ContradictionRisk,
): GovernanceRobustness {
  if (hardening === "strong" && card63Integrity === "strong" && layerSpread === 0) {
    return "strong";
  }
  if (hardening === "weak" || card63Integrity === "weak" || contradictionRisk === "high") {
    return "weak";
  }
  return "partial";
}

type MetaStability = "weak" | "moderate" | "strong";

function metaStabilityOf(
  integration:     Integration,
  unification:     Unification,
  metaConsistency: MetaConsistency,
): MetaStability {
  if (
    integration === "strong" && unification === "strong" && metaConsistency === "strong"
  ) {
    return "strong";
  }
  if (
    integration === "weak" || unification === "weak" || metaConsistency === "weak"
  ) {
    return "weak";
  }
  return "moderate";
}

type MetaRisk = "low" | "moderate" | "elevated" | "high";

// Composite meta-risk — escalates on the worst of the inputs.
// Synthesis already encodes most of these signals; we re-check
// contradiction + spread + threshold so a deteriorating upstream
// state can't hide.
function systemMetaRiskOf(
  inhibitorCount:    number,
  contradictionRisk: ContradictionRisk,
  profile:           Profile,
  layerSpread:       number,
  synthesisMetaRisk: SynthesisMetaRisk,
): MetaRisk {
  if (
    synthesisMetaRisk === "high" || contradictionRisk === "high" || layerSpread >= 3
  ) {
    return "high";
  }
  if (
    synthesisMetaRisk === "elevated" || contradictionRisk === "elevated" ||
    inhibitorCount >= 3 || layerSpread >= 2
  ) {
    return "elevated";
  }
  if (
    synthesisMetaRisk === "moderate" || contradictionRisk === "moderate" ||
    inhibitorCount >= 1 || strengthRank(profile.threshold) < 2
  ) {
    return "moderate";
  }
  return "low";
}

// Trajectory walks gov → systemLevel → projected; tail mirrors
// Card 61's "(projected)" vs "(stable)" convention.
function buildSystemTrajectory(
  govLevel:    Level,
  systemLevel: Level,
  slope:       number,
): string {
  const sysRank  = LEVEL_RANK[systemLevel];
  const projRank = Math.max(0, Math.min(4, sysRank + slope));
  const proj     = RANK_TO_LEVEL[projRank];
  const moves    = govLevel !== systemLevel || systemLevel !== proj;
  const tail     = moves ? "(projected)" : "(stable)";
  return `${govLevel.toLowerCase()} → ${systemLevel.toLowerCase()} → ${proj.toLowerCase()} ${tail}`;
}

// ----- Drivers / Inhibitors / Risks / Reinforcement / Decay -----------

function uniqPush(arr: string[], s: string): void {
  if (!arr.includes(s)) arr.push(s);
}

// Drivers report each upstream-layer's positive momentum when slope
// is positive. The system-level pane sees the whole stack pulling
// forward in three voices.
function collectDrivers(slope: number): string[] {
  const out: string[] = [];
  if (slope > 0) {
    uniqPush(out, "improving synthesis");
    uniqPush(out, "improving coherence");
    uniqPush(out, "improving immunity trajectory");
  }
  return out;
}

function collectInhibitors(govInhibitors: string[], profile: Profile): string[] {
  const out: string[] = [];
  for (const i of govInhibitors) uniqPush(out, i);
  if (profile.invariant === "partial") uniqPush(out, "partial invariant compliance");
  if (profile.invariant === "weak")    uniqPush(out, "weak invariant compliance");
  if (profile.threshold === "weak")    uniqPush(out, "weak threshold adherence");
  if (
    profile.upperBranch === "weak" &&
    !govInhibitors.some((i) => i.toLowerCase().includes("upper"))
  ) {
    uniqPush(out, "weak upper-branch containment");
  }
  if (
    profile.volatility === "weak" &&
    !govInhibitors.some((i) => i.toLowerCase().includes("volatility"))
  ) {
    uniqPush(out, "weak volatility control");
  }
  return out;
}

function collectRisks(
  layerSpread:       number,
  profile:           Profile,
  pressure:          Pressure,
  contradictionRisk: ContradictionRisk,
): string[] {
  const out: string[] = [];
  if (layerSpread >= 1)                       uniqPush(out, "cross-layer divergence");
  if (strengthRank(profile.threshold) < 2)    uniqPush(out, "threshold misalignment");
  if (pressure !== "low" || contradictionRisk !== "low") {
    uniqPush(out, "governance contradiction under pressure");
  }
  return out;
}

function collectReinforcement(
  profile:   Profile,
  hardening: Hardening,
  alignment: Alignment,
): string[] {
  const out: string[] = [];
  if (strengthRank(profile.invariant)   > 0) uniqPush(out, "maintain invariant compliance");
  if (strengthRank(profile.threshold)   > 0) uniqPush(out, "maintain drift suppression");
  if (strengthRank(profile.volatility)  > 0) uniqPush(out, "maintain volatility control");
  if (strengthRank(profile.upperBranch) > 0) uniqPush(out, "maintain upper-branch containment");
  if (hardening !== "weak")                  uniqPush(out, "maintain governance hardening");
  if (alignment !== "weak")                  uniqPush(out, "maintain cross-layer alignment");
  return out;
}

function collectDecay(profile: Profile, alignment: Alignment): string[] {
  const out: string[] = [];
  if (strengthRank(profile.threshold)  < 2) uniqPush(out, "drift may re-emerge");
  if (strengthRank(profile.volatility) < 2) uniqPush(out, "volatility may spike");
  if (strengthRank(profile.threshold)  < 2) uniqPush(out, "thresholds may weaken under load");
  if (alignment !== "strong")               uniqPush(out, "coherence may degrade");
  return out;
}

// ----- Summary ---------------------------------------------------------

function shortKey(s: string): string {
  const l = s.toLowerCase();
  if (l.includes("cz") || l.includes("invariant"))   return "CZ";
  if (l.includes("upper"))                            return "upper-branch";
  if (l.includes("drift") || l.includes("threshold")) return "drift";
  if (l.includes("volatility"))                       return "volatility";
  return s;
}

function joinAnd(items: string[]): string {
  if (items.length === 0) return "";
  if (items.length === 1) return items[0];
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}

function uniqArr(items: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const i of items) {
    if (!seen.has(i)) { seen.add(i); out.push(i); }
  }
  return out;
}

// "moderate" → "partial" mapping for the meta-stability summary
// clause, matching the spec demo: the block reads "moderate" while
// the trailing sentence says "partial". Inverse of Cards 66/67's
// partial→moderate mapping.
function summaryMetaStabilityWord(m: MetaStability): string {
  return m === "moderate" ? "partial" : m;
}

function buildSummary(
  direction:     Direction,
  cohesion:      GovernanceCohesion,
  metaStability: MetaStability,
  inhibitors:    string[],
): string {
  const inhibitorKeys   = uniqArr(inhibitors.map(shortKey));
  const inhibitorPhrase = joinAnd(inhibitorKeys);

  let s1: string;
  if (direction === "improving") {
    s1 = inhibitors.length > 0
      ? `System-level governance is improving but remains vulnerable to ${inhibitorPhrase} instability.`
      : `System-level governance is improving with no remaining inhibitors.`;
  } else if (direction === "deteriorating") {
    s1 = inhibitors.length > 0
      ? `System-level governance is deteriorating under ${inhibitorPhrase} pressure.`
      : `System-level governance is deteriorating — reinforcement recommended.`;
  } else {
    s1 = inhibitors.length > 0
      ? `System-level governance is steady but constrained by ${inhibitorPhrase}.`
      : `System-level governance is steady with no material changes.`;
  }

  const s2 = `Cohesion is ${cohesion}, and meta-stability is ${summaryMetaStabilityWord(metaStability)}.`;
  return `${s1} ${s2}`;
}

// ----- Entry point -----------------------------------------------------

export function buildSystemLevelGovernance(
  governance:           string,
  governanceDiff:       string,
  governanceStability:  string,
  governanceResilience: string,
  governanceImmunity:   string,
  governanceCoherence:  string,
  governanceSynthesis:  string,
): string {
  // Parse Card 61 (governance state).
  const govLevel      = parseLevel(governance, "Governance Level");
  const profile       = parseProfile(governance);
  const govInhibitors = parseListSection(governance, "Governance Inhibitors");

  // Parse Card 62 (transition).
  const direction = parseDirection(governanceDiff);
  const slope     = parseSlope(governanceDiff);
  const pressure  = parsePressure(governanceDiff);

  // Parse Card 63 (stability).
  const stability        = parseLevel(governanceStability, "Stability Level");
  const card63Integrity  = parseCard63Integrity(governanceStability);

  // Parse Card 64 (resilience).
  const resilience = parseLevel(governanceResilience, "Resilience Level");

  // Parse Card 65 (immunity).
  const immunity  = parseLevel(governanceImmunity, "Immunity Level");
  const hardening = parseHardening(governanceImmunity);

  // Parse Card 66 (coherence).
  const coherence         = parseLevel(governanceCoherence, "Coherence Level");
  const alignment         = parseAlignment(governanceCoherence);
  const contradictionRisk = parseContradictionRisk(governanceCoherence);

  // Parse Card 67 (synthesis).
  const synthesis         = parseLevel(governanceSynthesis, "Synthesis Level");
  const integration       = parseIntegration(governanceSynthesis);
  const unification       = parseUnification(governanceSynthesis);
  const metaConsistency   = parseMetaConsistency(governanceSynthesis);
  const synthesisMetaRisk = parseSynthesisMetaRisk(governanceSynthesis);

  // Derived fields.
  const inhibitors    = collectInhibitors(govInhibitors, profile);
  const systemLevel   = systemGovernanceLevelOf(
    stability, resilience, immunity, coherence, synthesis, inhibitors, profile,
  );
  const integrity     = governanceIntegrityOf(card63Integrity, contradictionRisk);
  const cohesion      = governanceCohesionOf(
    govLevel, stability, resilience, immunity, coherence, synthesis,
  );
  const layerRanks    = [
    LEVEL_RANK[govLevel],  LEVEL_RANK[stability], LEVEL_RANK[resilience],
    LEVEL_RANK[immunity],  LEVEL_RANK[coherence], LEVEL_RANK[synthesis],
  ];
  const layerSpread   = Math.max(...layerRanks) - Math.min(...layerRanks);
  const robustness    = governanceRobustnessOf(
    hardening, card63Integrity, layerSpread, contradictionRisk,
  );
  const metaStability = metaStabilityOf(integration, unification, metaConsistency);
  const metaRisk      = systemMetaRiskOf(
    inhibitors.length, contradictionRisk, profile, layerSpread, synthesisMetaRisk,
  );
  const trajectory    = buildSystemTrajectory(govLevel, systemLevel, slope);
  const drivers       = collectDrivers(slope);
  const risks         = collectRisks(layerSpread, profile, pressure, contradictionRisk);
  const reinforcement = collectReinforcement(profile, hardening, alignment);
  const decay         = collectDecay(profile, alignment);
  const summary       = buildSummary(direction, cohesion, metaStability, inhibitors);

  const blocks: string[] = [];
  blocks.push("=== System-Level Governance ===");
  blocks.push(`[System Governance Level]\n${systemLevel}`);
  blocks.push(`[Governance Integrity]\n${integrity}`);
  blocks.push(`[Governance Cohesion]\n${cohesion}`);
  blocks.push(`[Governance Robustness]\n${robustness}`);
  blocks.push(`[Governance Meta-Stability]\n${metaStability}`);
  blocks.push(`[Governance Meta-Risk]\n${metaRisk}`);
  blocks.push(`[System Governance Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[System Governance Drivers]\n(none)`
      : `[System Governance Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[System Governance Inhibitors]\n(none)`
      : `[System Governance Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[System Governance Risks]\n(none)`
      : `[System Governance Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[System Governance Reinforcement]\n(none)`
      : `[System Governance Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[System Governance Decay]\n(none)`
      : `[System Governance Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[System-Level Governance Summary]\n${summary}`);

  return blocks.join("\n\n");
}
