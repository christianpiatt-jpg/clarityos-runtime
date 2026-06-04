// Card 63 — Structural governance stability engine (Phase-4, Tier-3).
//
// Combines the Card 61 governance text and the Card 62 governance
// diff text into a 12-section stability assessment:
//
//   [Stability Level]              LOW … HIGH
//   [Governance Coherence]         strong / partial / weak
//   [Governance Integrity]         strong / moderate / weak
//   [Governance Drift]             low / moderate / high
//   [Governance Volatility]        low / moderate / high
//   [Stabilization Trajectory]     gov → stability → projected (state)
//   [Stability Drivers]            forward-supporting actions / signals
//   [Stability Inhibitors]         active risks limiting stability
//   [Stability Risks]              forward-looking risk classes
//   [Stability Reinforcement]      maintain-actions for active dims
//   [Stability Decay]              forward-looking weakening risks
//   [System-Level Stability Summary]
//
// Mirrors the structural pattern of Card 55 (Stabilization) and
// Card 59 (Resilience), but applied to governance rather than
// structural state. Pure deterministic string IO — no backend, no
// styling, no new dependencies.

const LEVELS = ["LOW", "LOW-MEDIUM", "MEDIUM", "MEDIUM-HIGH", "HIGH"] as const;
type Level = typeof LEVELS[number];

const LEVEL_RANK: Record<Level, number> = {
  LOW: 0, "LOW-MEDIUM": 1, MEDIUM: 2, "MEDIUM-HIGH": 3, HIGH: 4,
};
const RANK_TO_LEVEL: Record<number, Level> = {
  0: "LOW", 1: "LOW-MEDIUM", 2: "MEDIUM", 3: "MEDIUM-HIGH", 4: "HIGH",
};

// ----- Section parser (same pattern as Card 62) -----------------------

function parseSection(text: string, header: string): string {
  const re = new RegExp(`\\[${header}\\]\\s*\\n([\\s\\S]*?)(?=\\n\\[|$)`);
  const m  = text.match(re);
  return m ? m[1].trim() : "";
}

function parseLevel(text: string): Level {
  const body = parseSection(text, "Governance Level");
  const m = body.match(/^(LOW-MEDIUM|MEDIUM-HIGH|LOW|MEDIUM|HIGH)/);
  return (m ? m[1] : "LOW") as Level;
}

interface Profile {
  invariant:   string;  // full / partial / weak
  threshold:   string;  // strong / moderate / weak
  upperBranch: string;  // strong / moderate / weak
  volatility:  string;  // strong / moderate / weak
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
  const body    = parseSection(diff, "Governance Slope").trim();
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

type Risk = "low" | "moderate" | "elevated" | "high";

function parseRisk(diff: string): Risk {
  const body = parseSection(diff, "Governance Risk");
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

function stabilityLevelOf(
  govLevel:       Level,
  slope:          number,
  pressure:       Pressure,
  inhibitorCount: number,
): Level {
  let rank = LEVEL_RANK[govLevel];
  if (slope > 0 && pressure !== "high") rank += 1;
  if (slope < 0)                        rank -= 1;
  if (pressure === "high")              rank -= 1;
  if (inhibitorCount >= 4)              rank -= 1;
  rank = Math.max(0, Math.min(4, rank));
  return RANK_TO_LEVEL[rank];
}

type Coherence = "strong" | "partial" | "weak";

function coherenceOf(p: Profile): Coherence {
  const ranks = [
    strengthRank(p.invariant),
    strengthRank(p.threshold),
    strengthRank(p.upperBranch),
    strengthRank(p.volatility),
  ];
  const min = Math.min(...ranks);
  const max = Math.max(...ranks);
  if (max === 0) return "weak";
  if (min === 2) return "strong";
  return "partial";
}

type Integrity = "strong" | "moderate" | "weak";

function integrityOf(p: Profile): Integrity {
  const inv = strengthRank(p.invariant);
  const thr = strengthRank(p.threshold);
  if (inv >= 2 && thr >= 2) return "strong";
  if (inv === 0 && thr === 0) return "weak";
  return "moderate";
}

type DriftLevel = "low" | "moderate" | "high";

function driftLevelOf(
  inhibitors: string[],
  slope:      number,
  profile:    Profile,
): DriftLevel {
  const hasDrift = inhibitors.some((i) => i.toLowerCase().includes("drift"));
  const weakThr  = strengthRank(profile.threshold) === 0;
  if (hasDrift && slope < 0)   return "high";
  if (hasDrift || weakThr)     return "moderate";
  return "low";
}

type VolatilityLevel = "low" | "moderate" | "high";

function volatilityLevelOf(
  pressure:   Pressure,
  slope:      number,
  inhibitors: string[],
): VolatilityLevel {
  const hasVol = inhibitors.some((i) => i.toLowerCase().includes("volatility"));
  if (pressure === "high")                       return "high";
  if (pressure === "moderate" || hasVol)         return "moderate";
  if (slope < 0)                                 return "moderate";
  return "low";
}

// Trajectory walks gov → stability → projected so the operator can
// see "where we were", "where stability has landed", and "where it
// is heading" in one line. Tail mirrors Card 61's "(projected)" vs
// "(stable)" convention.
function buildStabilizationTrajectory(
  govLevel:  Level,
  stability: Level,
  slope:     number,
): string {
  const stbRank  = LEVEL_RANK[stability];
  const projRank = Math.max(0, Math.min(4, stbRank + slope));
  const proj     = RANK_TO_LEVEL[projRank];
  const moves    = govLevel !== stability || stability !== proj;
  const tail     = moves ? "(projected)" : "(stable)";
  return `${govLevel.toLowerCase()} → ${stability.toLowerCase()} → ${proj.toLowerCase()} ${tail}`;
}

// ----- Drivers / Inhibitors / Risks / Reinforcement / Decay -----------

function uniqPush(arr: string[], s: string): void {
  if (!arr.includes(s)) arr.push(s);
}

function collectDrivers(slope: number, deltaDrivers: string[]): string[] {
  const out: string[] = [];
  if (slope > 0) uniqPush(out, "improving governance slope");
  for (const d of deltaDrivers) {
    const lower = d.toLowerCase();
    if (lower.includes("drift")) {
      uniqPush(out, "reduced drift");
      uniqPush(out, "improved threshold adherence");
    } else if (lower.includes("volatility")) {
      uniqPush(out, "reduced volatility");
    } else if (lower.includes("invariant")) {
      uniqPush(out, "improved invariant compliance");
    } else if (lower.includes("upper")) {
      uniqPush(out, "improved upper-branch containment");
    }
  }
  return out;
}

function collectInhibitors(
  deltaInhibitors: string[],
  profile:         Profile,
): string[] {
  const out: string[] = [];
  for (const i of deltaInhibitors) uniqPush(out, i);
  // Profile-derived: surface any dim that isn't strong/full so a
  // currently-weak governance dim doesn't go silent if Card 62
  // didn't flag it as a delta inhibitor.
  if (profile.invariant === "partial") uniqPush(out, "partial invariant compliance");
  if (profile.invariant === "weak")    uniqPush(out, "weak invariant compliance");
  if (profile.threshold === "weak")    uniqPush(out, "weak threshold adherence");
  if (
    profile.upperBranch === "weak" &&
    !deltaInhibitors.some((i) => i.toLowerCase().includes("upper"))
  ) {
    uniqPush(out, "weak upper-branch containment");
  }
  if (
    profile.volatility === "weak" &&
    !deltaInhibitors.some((i) => i.toLowerCase().includes("volatility"))
  ) {
    uniqPush(out, "weak volatility control");
  }
  return out;
}

function collectRisks(
  pressure: Pressure,
  risk:     Risk,
  profile:  Profile,
): string[] {
  const out: string[] = [];
  if (pressure !== "low" || risk !== "low") {
    uniqPush(out, "governance erosion under pressure");
  }
  if (strengthRank(profile.threshold) < 2) uniqPush(out, "drift reactivation");
  if (strengthRank(profile.threshold) < 2) uniqPush(out, "threshold breach");
  if (pressure === "high" || strengthRank(profile.volatility) === 0) {
    uniqPush(out, "volatility spike");
  }
  return out;
}

function collectReinforcement(profile: Profile): string[] {
  const out: string[] = [];
  if (strengthRank(profile.invariant)   > 0) uniqPush(out, "maintain invariant compliance");
  if (strengthRank(profile.threshold)   > 0) uniqPush(out, "maintain drift suppression");
  if (strengthRank(profile.volatility)  > 0) uniqPush(out, "maintain volatility control");
  if (strengthRank(profile.upperBranch) > 0) uniqPush(out, "maintain upper-branch containment");
  return out;
}

function collectDecay(profile: Profile): string[] {
  const out: string[] = [];
  if (strengthRank(profile.threshold)  < 2) uniqPush(out, "thresholds may weaken under load");
  if (strengthRank(profile.threshold)  < 2) uniqPush(out, "drift may re-emerge");
  if (strengthRank(profile.volatility) < 2) uniqPush(out, "volatility may spike");
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

function buildSummary(
  direction:  Direction,
  drift:      DriftLevel,
  integrity:  Integrity,
  inhibitors: string[],
): string {
  const inhibitorKeys   = uniqArr(inhibitors.map(shortKey));
  const inhibitorPhrase = joinAnd(inhibitorKeys);

  let s1: string;
  if (direction === "improving") {
    s1 = inhibitors.length > 0
      ? `Governance stability is improving but remains vulnerable to ${inhibitorPhrase} instability.`
      : `Governance stability is improving with no remaining inhibitors.`;
  } else if (direction === "deteriorating") {
    s1 = inhibitors.length > 0
      ? `Governance stability is deteriorating under ${inhibitorPhrase} pressure.`
      : `Governance stability is deteriorating — reinforcement recommended.`;
  } else {
    s1 = inhibitors.length > 0
      ? `Governance stability is steady but constrained by ${inhibitorPhrase}.`
      : `Governance stability is steady with no material changes.`;
  }

  const driftWord =
    drift === "low"      ? "controlled" :
    drift === "moderate" ? "partially controlled" :
                           "uncontrolled";
  const integrityClause =
    integrity === "strong"   ? " and invariants are fully held" :
    integrity === "moderate" ? ", but threshold adherence is only partial" :
                               ", and invariants are weakly held";
  const s2 = `Drift is ${driftWord}${integrityClause}.`;

  return `${s1} ${s2}`;
}

// ----- Entry point -----------------------------------------------------

export function buildStructuralGovernanceStability(
  governance:     string,
  governanceDiff: string,
): string {
  // Parse Card 61 (governance) and Card 62 (governanceDiff).
  const govLevel      = parseLevel(governance);
  const profile       = parseProfile(governance);
  const govInhibitors = parseListSection(governance, "Governance Inhibitors");

  const direction       = parseDirection(governanceDiff);
  const slope           = parseSlope(governanceDiff);
  const pressure        = parsePressure(governanceDiff);
  const risk            = parseRisk(governanceDiff);
  const deltaDrivers    = parseListSection(governanceDiff, "Governance Delta Drivers");
  const deltaInhibitors = parseListSection(governanceDiff, "Governance Delta Inhibitors");

  // Combined view for drift / volatility detection. Drift / vol
  // signals can live in either the Card 61 inhibitor block (current
  // state) or the Card 62 delta inhibitor block (transition signal).
  const allInhibitors = [...govInhibitors, ...deltaInhibitors];

  const stabilityLevel = stabilityLevelOf(govLevel, slope, pressure, deltaInhibitors.length);
  const coherence      = coherenceOf(profile);
  const integrity      = integrityOf(profile);
  const drift          = driftLevelOf(allInhibitors, slope, profile);
  const volatility     = volatilityLevelOf(pressure, slope, allInhibitors);
  const trajectory     = buildStabilizationTrajectory(govLevel, stabilityLevel, slope);
  const drivers        = collectDrivers(slope, deltaDrivers);
  const inhibitors     = collectInhibitors(deltaInhibitors, profile);
  const risks          = collectRisks(pressure, risk, profile);
  const reinforcement  = collectReinforcement(profile);
  const decay          = collectDecay(profile);
  const summary        = buildSummary(direction, drift, integrity, inhibitors);

  const blocks: string[] = [];
  blocks.push("=== Structural Governance Stability ===");
  blocks.push(`[Stability Level]\n${stabilityLevel}`);
  blocks.push(`[Governance Coherence]\n${coherence}`);
  blocks.push(`[Governance Integrity]\n${integrity}`);
  blocks.push(`[Governance Drift]\n${drift}`);
  blocks.push(`[Governance Volatility]\n${volatility}`);
  blocks.push(`[Stabilization Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Stability Drivers]\n(none)`
      : `[Stability Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Stability Inhibitors]\n(none)`
      : `[Stability Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Stability Risks]\n(none)`
      : `[Stability Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Stability Reinforcement]\n(none)`
      : `[Stability Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Stability Decay]\n(none)`
      : `[Stability Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[System-Level Stability Summary]\n${summary}`);

  return blocks.join("\n\n");
}
