// Card 69 — Operator State Engine (Phase-5, Tier-1).
//
// First operator-meta card. Phase-3 modeled the system; Phase-4
// modeled governance; Phase-5 models the operator. This is the
// foundation — a single-pass evaluation of the operator's current
// structural condition.
//
// Input is text (whatever the Card 39 pipeline hands over). The
// helper looks for explicit `key=value` tokens (load, drift, clarity,
// stability, pressure, direction) that an operator harness can embed
// in the input text. Anything else is ignored — defaults are the
// "no signal" baseline (everything strong/low) so a vanilla JSON
// context still produces a well-formed state.
//
// Emits 10 sub-blocks:
//
//   [Operator Level]      LOW … HIGH
//   [Operator Load]       low / moderate / high
//   [Operator Drift]      low / moderate / high
//   [Operator Clarity]    weak / partial / strong
//   [Operator Stability]  weak / moderate / strong
//   [Operator Pressure]   low / moderate / elevated / high
//   [Operator Risk]       low / moderate / elevated / high
//   [Operator Drivers]
//   [Operator Inhibitors]
//   [Operator Summary]
//
// Pure deterministic string IO — no backend, no styling, no new
// dependencies.

type Level = "LOW" | "LOW-MEDIUM" | "MEDIUM" | "MEDIUM-HIGH" | "HIGH";

type LoadLevel      = "low" | "moderate" | "high";
type DriftLevel     = "low" | "moderate" | "high";
type ClarityLevel   = "weak" | "partial" | "strong";
type StabilityLevel = "weak" | "moderate" | "strong";
type PressureLevel  = "low" | "moderate" | "elevated" | "high";
type RiskLevel      = "low" | "moderate" | "elevated" | "high";
type Direction      = "improving" | "stable" | "deteriorating";

const LOAD_LEVELS:      readonly LoadLevel[]      = ["low", "moderate", "high"]                            as const;
const DRIFT_LEVELS:     readonly DriftLevel[]     = ["low", "moderate", "high"]                            as const;
const CLARITY_LEVELS:   readonly ClarityLevel[]   = ["weak", "partial", "strong"]                          as const;
const STABILITY_LEVELS: readonly StabilityLevel[] = ["weak", "moderate", "strong"]                         as const;
const PRESSURE_LEVELS:  readonly PressureLevel[]  = ["low", "moderate", "elevated", "high"]                as const;
const DIRECTIONS:       readonly Direction[]      = ["improving", "stable", "deteriorating"]               as const;

// ----- Token parser ----------------------------------------------------

// Look for `key=value` (case-insensitive) anywhere in the input. The
// regex requires `=` so that JSON `"pressure": 5` style content never
// false-matches.
function parseToken<T extends string>(
  text:         string,
  key:          string,
  allowed:      readonly T[],
  defaultValue: T,
): T {
  const re = new RegExp(`\\b${key}\\s*=\\s*([A-Za-z_-]+)`, "i");
  const m  = text.match(re);
  if (m) {
    const v = m[1].toLowerCase();
    if ((allowed as readonly string[]).includes(v)) return v as T;
  }
  return defaultValue;
}

// ----- Derived fields --------------------------------------------------

// Composite score: each non-optimal dimension chips at the operator
// level. Pressure carries an extra weight at "high" so a single
// high-pressure spike already moves the needle.
function operatorLevelOf(
  load:      LoadLevel,
  drift:     DriftLevel,
  clarity:   ClarityLevel,
  stability: StabilityLevel,
  pressure:  PressureLevel,
): Level {
  let score = 0;

  const loadW:      Record<LoadLevel,      number> = { low: 0, moderate: -1, high: -2 };
  const driftW:     Record<DriftLevel,     number> = { low: 0, moderate: -1, high: -2 };
  const clarityW:   Record<ClarityLevel,   number> = { strong: 0, partial: -1, weak: -2 };
  const stabilityW: Record<StabilityLevel, number> = { strong: 0, moderate: -1, weak: -2 };
  const pressureW:  Record<PressureLevel,  number> = { low: 0, moderate: -1, elevated: -2, high: -3 };

  score += loadW[load];
  score += driftW[drift];
  score += clarityW[clarity];
  score += stabilityW[stability];
  score += pressureW[pressure];

  if (score >= 0)   return "HIGH";
  if (score >= -2)  return "MEDIUM-HIGH";
  if (score >= -4)  return "MEDIUM";
  if (score >= -6)  return "LOW-MEDIUM";
  return "LOW";
}

// Risk = count of "critical" dimensions, tiered.
function operatorRiskOf(
  load:      LoadLevel,
  drift:     DriftLevel,
  clarity:   ClarityLevel,
  stability: StabilityLevel,
  pressure:  PressureLevel,
): RiskLevel {
  let critical = 0;
  if (load     === "high")                                   critical++;
  if (drift    === "high")                                   critical++;
  if (clarity  === "weak")                                   critical++;
  if (stability === "weak")                                  critical++;
  if (pressure === "elevated" || pressure === "high")        critical++;

  if (critical >= 3) return "high";
  if (critical >= 2) return "elevated";
  if (critical >= 1) return "moderate";
  return "low";
}

// ----- Drivers + Inhibitors --------------------------------------------

// Drivers only fire when the operator is in an improving direction —
// they describe forward-supporting trends, not steady-state strengths.
function collectDrivers(
  load:      LoadLevel,
  drift:     DriftLevel,
  clarity:   ClarityLevel,
  direction: Direction,
): string[] {
  const out: string[] = [];
  if (direction !== "improving") return out;
  if (clarity !== "weak")  out.push("improving clarity");
  if (drift   === "low")   out.push("reduced drift");
  if (load    !== "high")  out.push("improved load distribution");
  return out;
}

// Inhibitors mirror demo wording: specific labels per dimension, plus
// "residual drift" as a secondary effect when drift is low but
// pressure is elevated/high (the residue of past pressure).
function collectInhibitors(
  load:      LoadLevel,
  drift:     DriftLevel,
  clarity:   ClarityLevel,
  stability: StabilityLevel,
  pressure:  PressureLevel,
): string[] {
  const out: string[] = [];
  if      (pressure === "high")     out.push("high pressure");
  else if (pressure === "elevated") out.push("elevated pressure");
  else if (pressure === "moderate") out.push("moderate pressure");

  if      (clarity === "weak")    out.push("weak clarity");
  else if (clarity === "partial") out.push("partial clarity");

  if      (drift === "high")                                          out.push("active drift");
  else if (drift === "moderate")                                      out.push("residual drift");
  else if (pressure === "elevated" || pressure === "high")            out.push("residual drift");

  if (load === "high")      out.push("load saturation");
  if (stability === "weak") out.push("weak stability");

  return out;
}

// ----- Summary ---------------------------------------------------------

function buildSummary(
  direction: Direction,
  pressure:  PressureLevel,
  clarity:   ClarityLevel,
  drift:     DriftLevel,
  stability: StabilityLevel,
): string {
  let s1: string;
  if (direction === "improving") {
    if (pressure === "elevated" || pressure === "high") {
      s1 = "Operator state is improving but remains under elevated pressure.";
    } else {
      s1 = "Operator state is improving.";
    }
  } else if (direction === "deteriorating") {
    if (pressure === "high") {
      s1 = "Operator state is deteriorating under high pressure.";
    } else if (pressure === "elevated") {
      s1 = "Operator state is deteriorating under elevated pressure.";
    } else {
      s1 = "Operator state is deteriorating.";
    }
  } else {
    if (pressure === "elevated" || pressure === "high") {
      s1 = "Operator state is steady but under elevated pressure.";
    } else {
      s1 = "Operator state is steady.";
    }
  }

  const s2 = `Clarity is ${clarity}, drift is ${drift}, and stability is ${stability}.`;
  return `${s1} ${s2}`;
}

// ----- Entry point -----------------------------------------------------

export function buildOperatorState(operatorInput: string): string {
  const input = operatorInput ?? "";

  const load      = parseToken<LoadLevel>     (input, "load",      LOAD_LEVELS,      "low");
  const drift     = parseToken<DriftLevel>    (input, "drift",     DRIFT_LEVELS,     "low");
  const clarity   = parseToken<ClarityLevel>  (input, "clarity",   CLARITY_LEVELS,   "strong");
  const stability = parseToken<StabilityLevel>(input, "stability", STABILITY_LEVELS, "strong");
  const pressure  = parseToken<PressureLevel> (input, "pressure",  PRESSURE_LEVELS,  "low");
  const direction = parseToken<Direction>     (input, "direction", DIRECTIONS,       "stable");

  const level       = operatorLevelOf(load, drift, clarity, stability, pressure);
  const risk        = operatorRiskOf(load, drift, clarity, stability, pressure);
  const drivers     = collectDrivers(load, drift, clarity, direction);
  const inhibitors  = collectInhibitors(load, drift, clarity, stability, pressure);
  const summary     = buildSummary(direction, pressure, clarity, drift, stability);

  const blocks: string[] = [];
  blocks.push("=== Operator State ===");
  blocks.push(`[Operator Level]\n${level}`);
  blocks.push(`[Operator Load]\n${load}`);
  blocks.push(`[Operator Drift]\n${drift}`);
  blocks.push(`[Operator Clarity]\n${clarity}`);
  blocks.push(`[Operator Stability]\n${stability}`);
  blocks.push(`[Operator Pressure]\n${pressure}`);
  blocks.push(`[Operator Risk]\n${risk}`);
  blocks.push(
    drivers.length === 0
      ? `[Operator Drivers]\n(none)`
      : `[Operator Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Operator Inhibitors]\n(none)`
      : `[Operator Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(`[Operator Summary]\n${summary}`);

  return blocks.join("\n\n");
}
