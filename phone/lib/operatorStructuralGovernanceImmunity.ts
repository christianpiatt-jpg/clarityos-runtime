// Card 65 — Structural governance immunity engine (Phase-4, Tier-5).
//
// Combines Card 61 (governance), Card 62 (governance diff), Card 63
// (governance stability), and Card 64 (governance resilience) text
// outputs into a 13-section immunity assessment:
//
//   [Immunity Level]              LOW … HIGH
//   [Future-Resistance]           weak / moderate / strong
//   [Governance Hardening]        weak / partial / strong
//   [Governance Vulnerability]    low / moderate / elevated / high
//   [Immunity Trajectory]         gov → immunity → projected (state)
//   [Immunity Drivers]
//   [Immunity Inhibitors]
//   [Immunity Thresholds]         static safe-operating bounds
//   [Immunity Breach Conditions]  forward-looking failure modes
//   [Immunity Reinforcement]      maintain-actions for active dims
//   [Immunity Decay]              forward-looking weakening risks
//   [Early-Warning Signals]       forward-looking indicators
//   [System-Level Immunity Summary]
//
// Mirrors Card 60 (Structural Immunity) but applied to governance.
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

const IMMUNITY_THRESHOLD_LINES = [
  "- CZ < 2",
  "- volatility < 2",
  "- drift < 1",
  "- upper-branch = 0",
];

// ----- Section parser (same pattern as Cards 62/63/64) ----------------

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

// Immunity uses the Card 64 resilience level as its base rank and
// only decrements — positive slope is already priced in by Card 63
// (stability) and Card 64 (resilience) upstream.
function immunityLevelOf(
  resilience:     Level,
  slope:          number,
  drift:          DriftLevel,
  volatility:     VolatilityLevel,
  inhibitorCount: number,
): Level {
  let rank = LEVEL_RANK[resilience];
  if (slope < 0)             rank -= 1;
  if (drift === "high")      rank -= 1;
  if (volatility === "high") rank -= 1;
  if (inhibitorCount >= 4)   rank -= 1;
  rank = Math.max(0, Math.min(4, rank));
  return RANK_TO_LEVEL[rank];
}

type FutureResistance = "weak" | "moderate" | "strong";

function futureResistanceOf(
  resilience: Level,
  integrity:  Integrity,
  pressure:   Pressure,
): FutureResistance {
  if (LEVEL_RANK[resilience] >= 3 && integrity === "strong" && pressure !== "high") {
    return "strong";
  }
  if (LEVEL_RANK[resilience] === 0 && integrity === "weak") {
    return "weak";
  }
  return "moderate";
}

type Hardening = "weak" | "partial" | "strong";

function hardeningOf(
  slope:        number,
  integrity:    Integrity,
  driversCount: number,
): Hardening {
  if (integrity === "strong" && slope >= 0)              return "strong";
  if (slope <= 0 && driversCount === 0 && integrity === "weak") return "weak";
  return "partial";
}

type Vulnerability = "low" | "moderate" | "elevated" | "high";

function vulnerabilityOf(inhibitorCount: number, profile: Profile): Vulnerability {
  const weakCount = [
    profile.invariant, profile.threshold, profile.upperBranch, profile.volatility,
  ].filter((d) => strengthRank(d) === 0).length;
  if (inhibitorCount >= 4 || weakCount >= 3) return "high";
  if (inhibitorCount >= 3 || weakCount >= 2) return "elevated";
  if (inhibitorCount >= 1 || weakCount >= 1) return "moderate";
  return "low";
}

// Trajectory walks gov → immunity → projected; tail mirrors Card 61's
// "(projected)" vs "(stable)" convention.
function buildImmunityTrajectory(
  govLevel: Level,
  immunity: Level,
  slope:    number,
): string {
  const immRank  = LEVEL_RANK[immunity];
  const projRank = Math.max(0, Math.min(4, immRank + slope));
  const proj     = RANK_TO_LEVEL[projRank];
  const moves    = govLevel !== immunity || immunity !== proj;
  const tail     = moves ? "(projected)" : "(stable)";
  return `${govLevel.toLowerCase()} → ${immunity.toLowerCase()} → ${proj.toLowerCase()} ${tail}`;
}

// ----- Drivers / Inhibitors / Breach / Reinforcement / Decay -----------

function uniqPush(arr: string[], s: string): void {
  if (!arr.includes(s)) arr.push(s);
}

function collectDrivers(slope: number, deltaDrivers: string[]): string[] {
  const out: string[] = [];
  if (slope > 0) uniqPush(out, "improving governance resilience");
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

function collectBreach(pressure: Pressure, profile: Profile): string[] {
  const out: string[] = [];
  if (pressure !== "low") uniqPush(out, "governance pressure escalation");
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

// Forward-looking signals an operator should watch for to catch
// degradation before it lands. Pressure / inhibitor density / a
// non-robust stability bucket are all leading indicators.
function collectEarlyWarning(
  pressure:       Pressure,
  inhibitorCount: number,
  stability:      Level,
): string[] {
  const out: string[] = [];
  if (pressure !== "low")            uniqPush(out, "rising governance pressure");
  if (inhibitorCount >= 2)           uniqPush(out, "increasing inhibitors");
  if (LEVEL_RANK[stability] <= 1)    uniqPush(out, "weakening stability");
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
  direction:     Direction,
  futureRes:     FutureResistance,
  vulnerability: Vulnerability,
  inhibitors:    string[],
): string {
  const inhibitorKeys   = uniqArr(inhibitors.map(shortKey));
  const inhibitorPhrase = joinAnd(inhibitorKeys);

  let s1: string;
  if (direction === "improving") {
    s1 = inhibitors.length > 0
      ? `Governance immunity is improving but remains vulnerable to ${inhibitorPhrase} instability.`
      : `Governance immunity is improving with no remaining inhibitors.`;
  } else if (direction === "deteriorating") {
    s1 = inhibitors.length > 0
      ? `Governance immunity is deteriorating under ${inhibitorPhrase} pressure.`
      : `Governance immunity is deteriorating — reinforcement recommended.`;
  } else {
    s1 = inhibitors.length > 0
      ? `Governance immunity is steady but constrained by ${inhibitorPhrase}.`
      : `Governance immunity is steady with no material changes.`;
  }

  const s2 = vulnerability === "low"
    ? `Future-resistance is ${futureRes}.`
    : `Future-resistance is ${futureRes}, but vulnerabilities persist.`;

  return `${s1} ${s2}`;
}

// ----- Entry point -----------------------------------------------------

export function buildStructuralGovernanceImmunity(
  governance:           string,
  governanceDiff:       string,
  governanceStability:  string,
  governanceResilience: string,
): string {
  // Parse Card 61 (current governance state).
  const govLevel = parseLevel(governance, "Governance Level");
  const profile  = parseProfile(governance);

  // Parse Card 62 (transition).
  const direction       = parseDirection(governanceDiff);
  const slope           = parseSlope(governanceDiff);
  const pressure        = parsePressure(governanceDiff);
  const deltaDrivers    = parseListSection(governanceDiff, "Governance Delta Drivers");
  const deltaInhibitors = parseListSection(governanceDiff, "Governance Delta Inhibitors");

  // Parse Card 63 (stability-layer derived signals).
  const stability  = parseLevel(governanceStability, "Stability Level");
  const integrity  = parseIntegrity(governanceStability);
  const drift      = parseDrift(governanceStability);
  const volatility = parseVolatility(governanceStability);
  // Coherence is parsed for parity with Card 64 but not currently
  // load-bearing — keep the call so the input contract stays stable.
  void parseCoherence(governanceStability);

  // Parse Card 64 (resilience layer).
  const resilience = parseLevel(governanceResilience, "Resilience Level");

  // Compute drivers / inhibitors first; their counts feed several
  // derived fields below.
  const drivers       = collectDrivers(slope, deltaDrivers);
  const inhibitors    = collectInhibitors(deltaInhibitors, profile);
  const immunity      = immunityLevelOf(resilience, slope, drift, volatility, inhibitors.length);
  const futureRes     = futureResistanceOf(resilience, integrity, pressure);
  const hardening     = hardeningOf(slope, integrity, drivers.length);
  const vulnerability = vulnerabilityOf(inhibitors.length, profile);
  const trajectory    = buildImmunityTrajectory(govLevel, immunity, slope);
  const breach        = collectBreach(pressure, profile);
  const reinforcement = collectReinforcement(profile);
  const decay         = collectDecay(profile);
  const earlyWarning  = collectEarlyWarning(pressure, inhibitors.length, stability);
  const summary       = buildSummary(direction, futureRes, vulnerability, inhibitors);

  const blocks: string[] = [];
  blocks.push("=== Structural Governance Immunity ===");
  blocks.push(`[Immunity Level]\n${immunity}`);
  blocks.push(`[Future-Resistance]\n${futureRes}`);
  blocks.push(`[Governance Hardening]\n${hardening}`);
  blocks.push(`[Governance Vulnerability]\n${vulnerability}`);
  blocks.push(`[Immunity Trajectory]\n${trajectory}`);
  blocks.push(
    drivers.length === 0
      ? `[Immunity Drivers]\n(none)`
      : `[Immunity Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Immunity Inhibitors]\n(none)`
      : `[Immunity Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(`[Immunity Thresholds]\n${IMMUNITY_THRESHOLD_LINES.join("\n")}`);
  blocks.push(
    breach.length === 0
      ? `[Immunity Breach Conditions]\n(none)`
      : `[Immunity Breach Conditions]\n${breach.map((b) => `- ${b}`).join("\n")}`,
  );
  blocks.push(
    reinforcement.length === 0
      ? `[Immunity Reinforcement]\n(none)`
      : `[Immunity Reinforcement]\n${reinforcement.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Immunity Decay]\n(none)`
      : `[Immunity Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    earlyWarning.length === 0
      ? `[Early-Warning Signals]\n(none)`
      : `[Early-Warning Signals]\n${earlyWarning.map((e) => `- ${e}`).join("\n")}`,
  );
  blocks.push(`[System-Level Immunity Summary]\n${summary}`);

  return blocks.join("\n\n");
}
