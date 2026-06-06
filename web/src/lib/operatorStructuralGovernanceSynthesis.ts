// Card 67 — Structural governance synthesis engine (Phase-4, Tier-7).
//
// Final governance operator. Unifies Cards 61-66 into a single
// 12-section meta-governance state:
//
//   [Synthesis Level]              LOW … HIGH
//   [Governance Integration]       weak / partial / strong
//   [Governance Unification]       weak / moderate / strong
//   [Meta-Consistency]             weak / partial / strong
//   [Meta-Risk]                    low / moderate / elevated / high
//   [Meta-Trajectory]              gov → synthesis → projected (state)
//   [Synthesis Drivers]
//   [Synthesis Inhibitors]
//   [Synthesis Risks]
//   [Synthesis Reinforcement]
//   [Synthesis Decay]
//   [System-Level Governance Synthesis Summary]
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

// ----- Section parser (same pattern as Cards 62-66) -------------------

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

type Card63Coherence = "strong" | "partial" | "weak";

function parseCard63Coherence(stability: string): Card63Coherence {
  const body = parseSection(stability, "Governance Coherence");
  if (body === "strong") return "strong";
  if (body === "weak")   return "weak";
  return "partial";
}

type Integrity = "strong" | "moderate" | "weak";

function parseIntegrity(stability: string): Integrity {
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

// Synthesis floors on the weakest of the four upstream layers
// (stability / resilience / immunity / coherence) — the whole
// stack can't synthesize beyond the bottleneck. Penalties then
// apply on top for inhibitor density / threshold breach.
function synthesisLevelOf(
  stability:   Level,
  resilience:  Level,
  immunity:    Level,
  coherence:   Level,
  inhibitors:  string[],
  profile:     Profile,
): Level {
  let rank = Math.min(
    LEVEL_RANK[stability], LEVEL_RANK[resilience],
    LEVEL_RANK[immunity],  LEVEL_RANK[coherence],
  );
  if (inhibitors.length >= 4)               rank -= 1;
  if (strengthRank(profile.threshold) === 0) rank -= 1;
  rank = Math.max(0, Math.min(4, rank));
  return RANK_TO_LEVEL[rank];
}

type Integration = "weak" | "partial" | "strong";

function integrationOf(
  stability: Level, resilience: Level, immunity: Level, coherence: Level,
): Integration {
  const ranks = [
    LEVEL_RANK[stability], LEVEL_RANK[resilience],
    LEVEL_RANK[immunity],  LEVEL_RANK[coherence],
  ];
  const min = Math.min(...ranks);
  const max = Math.max(...ranks);
  const spread = max - min;
  if (spread === 0) {
    if (min >= 3) return "strong";
    if (min === 0) return "weak";
    return "partial";
  }
  if (spread === 1) return "partial";
  return "weak";
}

type Unification = "weak" | "moderate" | "strong";

function unificationOf(
  govLevel: Level, stability: Level, resilience: Level,
  immunity: Level, coherence: Level,
): Unification {
  const ranks = [
    LEVEL_RANK[govLevel],  LEVEL_RANK[stability], LEVEL_RANK[resilience],
    LEVEL_RANK[immunity],  LEVEL_RANK[coherence],
  ];
  const spread = Math.max(...ranks) - Math.min(...ranks);
  if (spread === 0) return "strong";
  if (spread === 1) return "moderate";
  return "weak";
}

type MetaConsistency = "weak" | "partial" | "strong";

function metaConsistencyOf(
  integrity:         Integrity,
  card63Coherence:   Card63Coherence,
  contradictionRisk: ContradictionRisk,
): MetaConsistency {
  if (integrity === "strong" && card63Coherence === "strong") return "strong";
  if (
    integrity === "weak" || card63Coherence === "weak" ||
    contradictionRisk === "high"
  ) {
    return "weak";
  }
  return "partial";
}

type MetaRisk = "low" | "moderate" | "elevated" | "high";

function metaRiskOf(
  inhibitorCount:    number,
  contradictionRisk: ContradictionRisk,
  profile:           Profile,
  layerSpread:       number,
): MetaRisk {
  if (contradictionRisk === "high" || layerSpread >= 3)   return "high";
  if (contradictionRisk === "elevated" || inhibitorCount >= 3 || layerSpread >= 2) {
    return "elevated";
  }
  if (
    contradictionRisk === "moderate" || inhibitorCount >= 1 ||
    strengthRank(profile.threshold) < 2
  ) {
    return "moderate";
  }
  return "low";
}

// Trajectory walks gov → synthesis → projected; tail mirrors Card 61's
// "(projected)" vs "(stable)" convention.
function buildMetaTrajectory(
  govLevel:  Level,
  synthesis: Level,
  slope:     number,
): string {
  const synRank  = LEVEL_RANK[synthesis];
  const projRank = Math.max(0, Math.min(4, synRank + slope));
  const proj     = RANK_TO_LEVEL[projRank];
  const moves    = govLevel !== synthesis || synthesis !== proj;
  const tail     = moves ? "(projected)" : "(stable)";
  return `${govLevel.toLowerCase()} → ${synthesis.toLowerCase()} → ${proj.toLowerCase()} ${tail}`;
}

// ----- Drivers / Inhibitors / Risks / Reinforcement / Decay -----------

function uniqPush(arr: string[], s: string): void {
  if (!arr.includes(s)) arr.push(s);
}

// Synthesis layer reports each upstream-layer's positive momentum
// when slope is positive — operators reading the synthesis pane
// see the whole stack pulling forward together.
function collectDrivers(slope: number): string[] {
  const out: string[] = [];
  if (slope > 0) {
    uniqPush(out, "improving coherence");
    uniqPush(out, "improving immunity trajectory");
    uniqPush(out, "improving resilience");
  }
  return out;
}

// Same pattern as Card 66: pull Card 61 inhibitors verbatim (no
// "persistent" prefix) plus profile-derived weaknesses.
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

// "partial" → "moderate" mapping for the summary line — same pattern
// as Card 66 (block vocab differs from summary vocab on the middle
// rung).
function summaryAlignmentWord(a: Alignment): string {
  return a === "partial" ? "moderate" : a;
}

function buildSummary(
  direction:   Direction,
  integration: Integration,
  alignment:   Alignment,
  inhibitors:  string[],
): string {
  const inhibitorKeys   = uniqArr(inhibitors.map(shortKey));
  const inhibitorPhrase = joinAnd(inhibitorKeys);

  let s1: string;
  if (direction === "improving") {
    s1 = inhibitors.length > 0
      ? `Governance synthesis is improving but remains vulnerable to ${inhibitorPhrase} instability.`
      : `Governance synthesis is improving with no remaining inhibitors.`;
  } else if (direction === "deteriorating") {
    s1 = inhibitors.length > 0
      ? `Governance synthesis is deteriorating under ${inhibitorPhrase} pressure.`
      : `Governance synthesis is deteriorating — reinforcement recommended.`;
  } else {
    s1 = inhibitors.length > 0
      ? `Governance synthesis is steady but constrained by ${inhibitorPhrase}.`
      : `Governance synthesis is steady with no material changes.`;
  }

  const s2 = `Integration is ${integration}, and cross-layer alignment is ${summaryAlignmentWord(alignment)}.`;
  return `${s1} ${s2}`;
}

// ----- Entry point -----------------------------------------------------

export function buildStructuralGovernanceSynthesis(
  governance:           string,
  governanceDiff:       string,
  governanceStability:  string,
  governanceResilience: string,
  governanceImmunity:   string,
  governanceCoherence:  string,
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
  const stability       = parseLevel(governanceStability, "Stability Level");
  const card63Coherence = parseCard63Coherence(governanceStability);
  const integrity       = parseIntegrity(governanceStability);

  // Parse Card 64 (resilience).
  const resilience = parseLevel(governanceResilience, "Resilience Level");

  // Parse Card 65 (immunity).
  const immunity  = parseLevel(governanceImmunity, "Immunity Level");
  const hardening = parseHardening(governanceImmunity);

  // Parse Card 66 (coherence).
  const coherence         = parseLevel(governanceCoherence, "Coherence Level");
  const alignment         = parseAlignment(governanceCoherence);
  const contradictionRisk = parseContradictionRisk(governanceCoherence);

  // Derived fields.
  const inhibitors    = collectInhibitors(govInhibitors, profile);
  const synthesis     = synthesisLevelOf(stability, resilience, immunity, coherence, inhibitors, profile);
  const integration   = integrationOf(stability, resilience, immunity, coherence);
  const unification   = unificationOf(govLevel, stability, resilience, immunity, coherence);
  const metaConsis    = metaConsistencyOf(integrity, card63Coherence, contradictionRisk);
  const layerRanks    = [
    LEVEL_RANK[govLevel],  LEVEL_RANK[stability], LEVEL_RANK[resilience],
    LEVEL_RANK[immunity],  LEVEL_RANK[coherence],
  ];
  const layerSpread   = Math.max(...layerRanks) - Math.min(...layerRanks);
  const metaRisk      = metaRiskOf(inhibitors.length, contradictionRisk, profile, layerSpread);
  const trajectory    = buildMetaTrajectory(govLevel, synthesis, slope);
  const drivers       = collectDrivers(slope);
  const risks         = collectRisks(layerSpread, profile, pressure, contradictionRisk);
  const reinforcement = collectReinforcement(profile, hardening, alignment);
  const decay         = collectDecay(profile, alignment);
  const summary       = buildSummary(direction, integration, alignment, inhibitors);

  const blocks: string[] = [];
  blocks.push("=== Structural Governance Synthesis ===");
  blocks.push(`[Synthesis Level]\n${synthesis}`);
  blocks.push(`[Governance Integration]\n${integration}`);
  blocks.push(`[Governance Unification]\n${unification}`);
  blocks.push(`[Meta-Consistency]\n${metaConsis}`);
  blocks.push(`[Meta-Risk]\n${metaRisk}`);
  blocks.push(`[Meta-Trajectory]\n${trajectory}`);
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
  blocks.push(`[System-Level Governance Synthesis Summary]\n${summary}`);

  return blocks.join("\n\n");
}
