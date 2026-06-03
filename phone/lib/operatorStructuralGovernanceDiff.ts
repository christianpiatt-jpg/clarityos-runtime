// Card 62 — Structural governance diff engine (Phase-4, Tier-2).
//
// Compares two Card 61 governance text outputs (prev, next) and
// produces a text-only governance delta covering 9 sub-blocks:
//
//   [Governance Delta]              LOW → LOW-MEDIUM
//   [Governance Direction]          improving / stable / deteriorating
//   [Governance Slope]              +1 / 0 / -1
//   [Governance Pressure]           low / moderate / high
//   [Governance Stability]          strong / partial / weak
//   [Governance Risk]               low / moderate / elevated / high
//   [Governance Delta Drivers]      dims that improved
//   [Governance Delta Inhibitors]   dims that worsened or persist as risks
//   [Governance Delta Summary]      one deterministic paragraph
//
// The inputs are the *text* outputs of Card 61 — this helper parses
// them, derives the delta, and emits a new text block. No backend,
// no styling, no new dependencies — pure deterministic string IO.

const LEVELS = ["LOW", "LOW-MEDIUM", "MEDIUM", "MEDIUM-HIGH", "HIGH"] as const;
type GovernanceLevel = typeof LEVELS[number];

const LEVEL_RANK: Record<GovernanceLevel, number> = {
  LOW: 0, "LOW-MEDIUM": 1, MEDIUM: 2, "MEDIUM-HIGH": 3, HIGH: 4,
};

interface GovernanceProfile {
  invariant:   string;  // full / partial / weak
  threshold:   string;  // strong / moderate / weak
  upperBranch: string;  // strong / moderate / weak
  volatility:  string;  // strong / moderate / weak
}

interface ParsedGovernance {
  level:      GovernanceLevel;
  profile:    GovernanceProfile;
  inhibitors: string[];
}

const DEFAULT_PROFILE: GovernanceProfile = {
  invariant: "weak", threshold: "weak", upperBranch: "weak", volatility: "weak",
};

// ----- Parsing ---------------------------------------------------------

// Pull the body of a `[Header]` block from a Card 61 text dump,
// stopping at the next `[...]` block or end-of-string.
function parseSection(text: string, header: string): string {
  const re = new RegExp(`\\[${header}\\]\\s*\\n([\\s\\S]*?)(?=\\n\\[|$)`);
  const m  = text.match(re);
  return m ? m[1].trim() : "";
}

function parseLevel(text: string): GovernanceLevel {
  const body = parseSection(text, "Governance Level");
  // Longer alternatives first so "MEDIUM-HIGH" wins over "MEDIUM".
  const m = body.match(/^(LOW-MEDIUM|MEDIUM-HIGH|LOW|MEDIUM|HIGH)/);
  return (m ? m[1] : "LOW") as GovernanceLevel;
}

function parseProfile(text: string): GovernanceProfile {
  const body  = parseSection(text, "Governance Profile");
  const lines = body.split("\n").filter((l) => l.startsWith("- "));
  const out: GovernanceProfile = { ...DEFAULT_PROFILE };
  for (const l of lines) {
    const word = l.match(/^-\s+(\w+)/)?.[1] ?? "weak";
    if      (l.includes("invariant compliance"))      out.invariant   = word;
    else if (l.includes("threshold adherence"))       out.threshold   = word;
    else if (l.includes("upper-branch containment"))  out.upperBranch = word;
    else if (l.includes("volatility control"))        out.volatility  = word;
  }
  return out;
}

function parseInhibitors(text: string): string[] {
  const body  = parseSection(text, "Governance Inhibitors");
  const lines = body.split("\n");
  const out: string[] = [];
  for (const l of lines) {
    if (l.startsWith("- ")) out.push(l.slice(2).trim());
  }
  return out;
}

function parseGovernance(text: string): ParsedGovernance {
  if (!text.trim()) {
    return { level: "LOW", profile: DEFAULT_PROFILE, inhibitors: [] };
  }
  return {
    level:      parseLevel(text),
    profile:    parseProfile(text),
    inhibitors: parseInhibitors(text),
  };
}

// ----- Strength rank ---------------------------------------------------

// Both vocabularies (full/strong = 2, partial/moderate = 1, weak = 0)
// collapse onto a single ordinal so we can compare any two profile
// dims regardless of which word set Card 61 chose.
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

// ----- Direction / Slope / Pressure / Stability / Risk ----------------

type Direction = "improving" | "stable" | "deteriorating";

function directionOf(prev: GovernanceLevel, next: GovernanceLevel): Direction {
  const d = LEVEL_RANK[next] - LEVEL_RANK[prev];
  if (d > 0) return "improving";
  if (d < 0) return "deteriorating";
  return "stable";
}

// Slope is the *sign* of the rank delta — the spec only enumerates
// {+1, 0, -1}, so multi-bucket jumps collapse to the same direction.
function slopeOf(prev: GovernanceLevel, next: GovernanceLevel): number {
  return Math.sign(LEVEL_RANK[next] - LEVEL_RANK[prev]);
}

type Pressure = "low" | "moderate" | "high";

function pressureOf(nextInhibitors: string[]): Pressure {
  const n = nextInhibitors.length;
  if (n === 0) return "low";
  if (n <= 2)  return "moderate";
  return "high";
}

type Stability = "strong" | "partial" | "weak";

function stabilityOf(p: GovernanceProfile): Stability {
  const ranks = [
    strengthRank(p.invariant),
    strengthRank(p.threshold),
    strengthRank(p.upperBranch),
    strengthRank(p.volatility),
  ];
  const weakCount   = ranks.filter((r) => r === 0).length;
  const strongCount = ranks.filter((r) => r >= 2).length;
  if (strongCount === 4) return "strong";
  if (weakCount >= 2)    return "weak";
  return "partial";
}

type Risk = "low" | "moderate" | "elevated" | "high";

function riskOf(pressure: Pressure, slope: number): Risk {
  if (pressure === "high")                      return "high";
  if (pressure === "moderate" && slope < 0)     return "high";
  if (pressure === "moderate")                  return "elevated";
  // low pressure
  if (slope < 0) return "moderate";
  return "low";
}

// ----- Drivers + Inhibitors -------------------------------------------

// Per-dim driver/inhibitor labels. Order chosen so the spec demo
// surfaces drivers as "volatility ... drift ..." (mild dims first)
// and inhibitors retain Card 61's CZ-first severity ordering through
// the parsed `nextInhibitors` array.
const DIM_ORDER: (keyof GovernanceProfile)[] = [
  "volatility",
  "threshold",
  "invariant",
  "upperBranch",
];

const DIM_LABELS: Record<keyof GovernanceProfile, { driver: string; inhibitor: string }> = {
  invariant:   { driver: "improved invariant compliance",     inhibitor: "weakening invariant compliance" },
  threshold:   { driver: "improved drift suppression",        inhibitor: "weakening drift suppression" },
  upperBranch: { driver: "improved upper-branch containment", inhibitor: "weakening upper-branch containment" },
  volatility:  { driver: "improved volatility control",       inhibitor: "weakening volatility control" },
};

function collectDrivers(prev: GovernanceProfile, next: GovernanceProfile): string[] {
  const out: string[] = [];
  for (const key of DIM_ORDER) {
    if (strengthRank(next[key]) > strengthRank(prev[key])) {
      out.push(DIM_LABELS[key].driver);
    }
  }
  return out;
}

function collectInhibitors(
  prevInhibitors: string[],
  nextInhibitors: string[],
  prevProfile:    GovernanceProfile,
  nextProfile:    GovernanceProfile,
): string[] {
  const out: string[] = [];
  // Persistent / new inhibitors carried over from Card 61's parsed
  // inhibitor list. "persistent" prefix when the same string was
  // present in prev.
  for (const i of nextInhibitors) {
    out.push(prevInhibitors.includes(i) ? `persistent ${i}` : i);
  }
  // Worsening profile dims surface as additional inhibitor lines so
  // a dim that wasn't tracked in nextInhibitors but lost strength
  // doesn't go silent.
  for (const key of DIM_ORDER) {
    if (strengthRank(nextProfile[key]) < strengthRank(prevProfile[key])) {
      out.push(DIM_LABELS[key].inhibitor);
    }
  }
  return out;
}

// ----- Summary ---------------------------------------------------------

function shortDriverKey(d: string): string {
  if (d.includes("volatility")) return "volatility";
  if (d.includes("drift"))      return "drift";
  if (d.includes("invariant"))  return "CZ";
  if (d.includes("upper"))      return "upper-branch";
  return d;
}

function shortInhibitorKey(i: string): string {
  if (i.includes("CZ"))         return "CZ";
  if (i.includes("upper"))      return "upper-branch";
  if (i.includes("drift"))      return "drift";
  if (i.includes("volatility")) return "volatility";
  return i;
}

function joinAnd(items: string[]): string {
  if (items.length === 0) return "";
  if (items.length === 1) return items[0];
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}

function uniq(items: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const i of items) {
    if (!seen.has(i)) { seen.add(i); out.push(i); }
  }
  return out;
}

function buildSummary(
  dir:        Direction,
  drivers:    string[],
  inhibitors: string[],
): string {
  const driverJoined    = joinAnd(uniq(drivers.map(shortDriverKey)));
  const inhibitorJoined = joinAnd(uniq(inhibitors.map(shortInhibitorKey)));

  if (dir === "improving") {
    if (drivers.length > 0 && inhibitors.length > 0) {
      return `Governance shows a modest improvement driven by ${driverJoined} stabilization, but ${inhibitorJoined} vulnerabilities continue to limit overall stability.`;
    }
    if (drivers.length > 0) {
      return `Governance shows a modest improvement driven by ${driverJoined} stabilization.`;
    }
    return `Governance is improving, with no specific drivers identified.`;
  }

  if (dir === "deteriorating") {
    if (inhibitors.length > 0) {
      return `Governance shows a modest deterioration as ${inhibitorJoined} vulnerabilities expand.`;
    }
    return `Governance is deteriorating — reinforcement recommended.`;
  }

  // stable
  if (inhibitors.length > 0) {
    return `Governance remains stable with persistent ${inhibitorJoined} vulnerabilities.`;
  }
  return `Governance remains stable with no material change.`;
}

// ----- Entry point -----------------------------------------------------

export function buildStructuralGovernanceDiff(
  prevGovernance: string,
  nextGovernance: string,
): string {
  const prev = parseGovernance(prevGovernance);
  const next = parseGovernance(nextGovernance);

  const dir        = directionOf(prev.level, next.level);
  const slope      = slopeOf(prev.level, next.level);
  const pressure   = pressureOf(next.inhibitors);
  const stability  = stabilityOf(next.profile);
  const risk       = riskOf(pressure, slope);
  const drivers    = collectDrivers(prev.profile, next.profile);
  const inhibitors = collectInhibitors(
    prev.inhibitors, next.inhibitors,
    prev.profile,    next.profile,
  );

  const slopeStr = slope > 0 ? `+${slope}` : `${slope}`;

  const blocks: string[] = [];
  blocks.push("=== Structural Governance Diff ===");
  blocks.push(`[Governance Delta]\n${prev.level} → ${next.level}`);
  blocks.push(`[Governance Direction]\n${dir}`);
  blocks.push(`[Governance Slope]\n${slopeStr}`);
  blocks.push(`[Governance Pressure]\n${pressure}`);
  blocks.push(`[Governance Stability]\n${stability}`);
  blocks.push(`[Governance Risk]\n${risk}`);
  blocks.push(
    drivers.length === 0
      ? `[Governance Delta Drivers]\n(none)`
      : `[Governance Delta Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Governance Delta Inhibitors]\n(none)`
      : `[Governance Delta Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(`[Governance Delta Summary]\n${buildSummary(dir, drivers, inhibitors)}`);

  return blocks.join("\n\n");
}
