// Card 64 — Structural governance resilience engine (Phase-4, Tier-4).
//
// Combines Card 61 (governance), Card 62 (governance diff), and
// Card 63 (governance stability) text outputs into a 12-section
// resilience assessment:
//
//   [Resilience Level]             LOW … HIGH
//   [Load-Bearing Capacity]        weak / moderate / strong
//   [Recovery Strength]            weak / partial / strong
//   [Fault Tolerance]              weak / moderate / strong
//   [Pressure Response]            weak / moderate / strong
//   [Resilience Trajectory]        gov → resilience → projected (state)
//   [Resilience Drivers]
//   [Resilience Inhibitors]
//   [Resilience Risks]
//   [Resilience Reinforcement]
//   [Resilience Decay]
//   [System-Level Resilience Summary]
//
// Mirrors Card 59 (Structural Resilience) but applied to governance.
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

// ----- Section parser (same pattern as Cards 62/63) --------------------

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

type Risk = "low" | "moderate" | "elevated" | "high";

function parseRisk(diff: string): Risk {
  const body = parseSection(diff, "Governance Risk");
  if (body === "high")     return "high";
  if (body === "elevated") return "elevated";
  if (body === "moderate") return "moderate";
  return "low";
}

type Coherence = "strong" | "partial" | "weak";

function parseCoherence(stability: string): Coherence {
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

type DriftLevel = "low" | "moderate" | "high";

function parseDrift(stability: string): DriftLevel {
  const body = parseSection(stability, "Governance Drift");
  if (body === "high")     return "high";
  if (body === "moderate") return "moderate";
  return "low";
}

type VolatilityLevel = "low" | "moderate" | "high";

function parseVolatility(stability: string): VolatilityLevel {
  const body = parseSection(stability, "Governance Volatility");
  if (body === "high")     return "high";
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

// Resilience uses the Card 63 stability level as its base rank and
// only ever decrements: any positive bump has already been priced
// in by Card 63's stabilityLevelOf, so adding another would double-
// count the slope signal.
function resilienceLevelOf(
  stability:  Level,
  slope:      number,
  drift:      DriftLevel,
  volatility: VolatilityLevel,
): Level {
  let rank = LEVEL_RANK[stability];
  if (slope < 0)           rank -= 1;
  if (drift === "high")    rank -= 1;
  if (volatility === "high") rank -= 1;
  rank = Math.max(0, Math.min(4, rank));
  return RANK_TO_LEVEL[rank];
}

type LoadCapacity = "weak" | "moderate" | "strong";

function loadBearingCapacityOf(
  govLevel:  Level,
  integrity: Integrity,
  pressure:  Pressure,
): LoadCapacity {
  if (LEVEL_RANK[govLevel] >= 3 && integrity === "strong" && pressure !== "high") {
    return "strong";
  }
  if (LEVEL_RANK[govLevel] === 0 && integrity === "weak") {
    return "weak";
  }
  return "moderate";
}

type RecoveryStrength = "weak" | "partial" | "strong";

function recoveryStrengthOf(
  slope:        number,
  integrity:    Integrity,
  driversCount: number,
): RecoveryStrength {
  if (integrity === "strong" && slope >= 0)            return "strong";
  if (slope < 0 && driversCount === 0)                 return "weak";
  return "partial";
}

type FaultTolerance = "weak" | "moderate" | "strong";

function faultToleranceOf(
  coherence:      Coherence,
  integrity:      Integrity,
  inhibitorCount: number,
): FaultTolerance {
  if (coherence === "strong" && integrity === "strong")          return "strong";
  if (inhibitorCount >= 3 || coherence === "weak")               return "weak";
  return "moderate";
}

type PressureResponse = "weak" | "moderate" | "strong";

function pressureResponseOf(
  pressure:   Pressure,
  volatility: VolatilityLevel,
  slope:      number,
): PressureResponse {
  if (pressure === "high" && volatility === "high")              return "weak";
  if (pressure === "low" && volatility === "low" && slope >= 0)  return "strong";
  return "moderate";
}

// Trajectory walks gov → resilience → projected; tail mirrors
// Card 61's "(projected)" vs "(stable)" convention.
function buildResilienceTrajectory(
  govLevel:   Level,
  resilience: Level,
  slope:      number,
): string {
  const resRank  = LEVEL_RANK[resilience];
  const projRank = Math.max(0, Math.min(4, resRank + slope));
  const proj     = RANK_TO_LEVEL[projRank];
  const moves    = govLevel !== resilience || resilience !== proj;
  const tail     = moves ? "(projected)" : "(stable)";
  return `${govLevel.toLowerCase()} → ${resilience.toLowerCase()} → ${proj.toLowerCase()} ${tail}`;
}

// ----- Drivers / Inhibitors / Risks / Reinforcement / Decay -----------

function uniqPush(arr: string[], s: string): void {
  if (!arr.includes(s)) arr.push(s);
}

function collectDrivers(slope: number, deltaDrivers: string[]): string[] {
  const out: string[] = [];
  if (slope > 0) uniqPush(out, "improving governance stability");
  for (const d of deltaDrivers) {
    const lower = d.toLowerCase();
    if (lower.includes("drift")) {
      uniqPush(out, "reduced governance drift");
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
    uniqPush(out, "governance collapse under pressure");
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
  direction:    Direction,
  recovery:     RecoveryStrength,
  loadCapacity: LoadCapacity,
  inhibitors:   string[],
): string {
  const inhibitorKeys   = uniqArr(inhibitors.map(shortKey));
  const inhibitorPhrase = joinAnd(inhibitorKeys);

  let s1: string;
  if (direction === "improving") {
    s1 = inhibitors.length > 0
      ? `Governance resilience is improving but remains vulnerable to ${inhibitorPhrase} instability.`
      : `Governance resilience is improving with no remaining inhibitors.`;
  } else if (direction === "deteriorating") {
    s1 = inhibitors.length > 0
      ? `Governance resilience is deteriorating under ${inhibitorPhrase} pressure.`
      : `Governance resilience is deteriorating — reinforcement recommended.`;
  } else {
    s1 = inhibitors.length > 0
      ? `Governance resilience is steady but constrained by ${inhibitorPhrase}.`
      : `Governance resilience is steady with no material changes.`;
  }

  const s2 = `Recovery strength is ${recovery}, and load-bearing capacity is ${loadCapacity}.`;
  return `${s1} ${s2}`;
}

// ----- Entry point -----------------------------------------------------

export function buildStructuralGovernanceResilience(
  governance:          string,
  governanceDiff:      string,
  governanceStability: string,
): string {
  // Parse Card 61 (current governance state).
  const govLevel = parseLevel(governance, "Governance Level");
  const profile  = parseProfile(governance);

  // Parse Card 62 (transition).
  const direction       = parseDirection(governanceDiff);
  const slope           = parseSlope(governanceDiff);
  const pressure        = parsePressure(governanceDiff);
  const risk            = parseRisk(governanceDiff);
  const deltaDrivers    = parseListSection(governanceDiff, "Governance Delta Drivers");
  const deltaInhibitors = parseListSection(governanceDiff, "Governance Delta Inhibitors");

  // Parse Card 63 (stability-layer derived signals).
  const stability  = parseLevel(governanceStability, "Stability Level");
  const coherence  = parseCoherence(governanceStability);
  const integrity  = parseIntegrity(governanceStability);
  const drift      = parseDrift(governanceStability);
  const volatility = parseVolatility(governanceStability);

  // Derived fields. Drivers / inhibitors are computed first because
  // their counts feed recovery + fault-tolerance.
  const drivers       = collectDrivers(slope, deltaDrivers);
  const inhibitors    = collectInhibitors(deltaInhibitors, profile);
  const resilience    = resilienceLevelOf(stability, slope, drift, volatility);
  const loadCapacity  = loadBearingCapacityOf(govLevel, integrity, pressure);
  const recovery      = recoveryStrengthOf(slope, integrity, drivers.length);
  const faultTol      = faultToleranceOf(coherence, integrity, inhibitors.length);
  const pressureResp  = pressureResponseOf(pressure, volatility, slope);
  const trajectory    = buildResilienceTrajectory(govLevel, resilience, slope);
  const risks         = collectRisks(pressure, risk, profile);
  const reinforcement = collectReinforcement(profile);
  const decay         = collectDecay(profile);
  const summary       = buildSummary(direction, recovery, loadCapacity, inhibitors);

  const blocks: string[] = [];
  blocks.push("=== Structural Governance Resilience ===");
  blocks.push(`[Resilience Level]\n${resilience}`);
  blocks.push(`[Load-Bearing Capacity]\n${loadCapacity}`);
  blocks.push(`[Recovery Strength]\n${recovery}`);
  blocks.push(`[Fault Tolerance]\n${faultTol}`);
  blocks.push(`[Pressure Response]\n${pressureResp}`);
  blocks.push(`[Resilience Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Resilience Drivers]\n(none)`
      : `[Resilience Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Resilience Inhibitors]\n(none)`
      : `[Resilience Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    risks.length === 0
      ? `[Resilience Risks]\n(none)`
      : `[Resilience Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Resilience Reinforcement]\n(none)`
      : `[Resilience Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Resilience Decay]\n(none)`
      : `[Resilience Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[System-Level Resilience Summary]\n${summary}`);

  return blocks.join("\n\n");
}
