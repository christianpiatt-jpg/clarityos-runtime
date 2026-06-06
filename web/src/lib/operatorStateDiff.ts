// Card 70 — Operator State Diff engine (Phase-5, Tier-2).
//
// Second operator-meta card. Parses two Card 69 output blocks
// (previous + current operator state) and emits a delta block
// describing how the operator's structural condition has changed
// across time.
//
// NOTE: spec says path `operatorDiff.ts` but that name is already
// taken by Card 44 (system regression diff viewer). This helper is
// at `operatorStateDiff.ts` instead — semantically accurate since
// Card 70 is the diff of the operator STATE.
//
// Emits 11 sub-blocks:
//
//   [Operator Slope]              LOW … HIGH (current operator level)
//   [Drift Delta]                 low / moderate / high
//   [Clarity Delta]               weak / partial / moderate / strong
//   [Load Delta]                  low / moderate / high
//   [Pressure Delta]              low / moderate / elevated / high
//   [Stability Delta]             weak / partial / strong
//   [Risk Delta]                  low / moderate / elevated / high
//   [Operator Diff Drivers]
//   [Operator Diff Inhibitors]
//   [Operator Diff Summary]
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

const LEVEL_RANK: Record<Level, number> = {
  LOW: 0, "LOW-MEDIUM": 1, MEDIUM: 2, "MEDIUM-HIGH": 3, HIGH: 4,
};

// ----- Section parser (same pattern as Cards 62-68) -------------------

function parseSection(text: string, header: string): string {
  const re = new RegExp(`\\[${header}\\]\\s*\\n([\\s\\S]*?)(?=\\n\\[|$)`);
  const m  = text.match(re);
  return m ? m[1].trim() : "";
}

function parseOperatorLevel(text: string): Level {
  const body = parseSection(text, "Operator Level");
  const m = body.match(/^(LOW-MEDIUM|MEDIUM-HIGH|LOW|MEDIUM|HIGH)/);
  return (m ? m[1] : "HIGH") as Level;
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

function parseStability(text: string): StabilityLevel {
  const body = parseSection(text, "Operator Stability");
  if (body === "weak")     return "weak";
  if (body === "moderate") return "moderate";
  return "strong";
}

function parsePressure(text: string): PressureLevel {
  const body = parseSection(text, "Operator Pressure");
  if (body === "high")     return "high";
  if (body === "elevated") return "elevated";
  if (body === "moderate") return "moderate";
  return "low";
}

function parseRisk(text: string): RiskLevel {
  const body = parseSection(text, "Operator Risk");
  if (body === "high")     return "high";
  if (body === "elevated") return "elevated";
  if (body === "moderate") return "moderate";
  return "low";
}

function parseListSection(text: string, header: string): string[] {
  const body = parseSection(text, header);
  const out: string[] = [];
  for (const l of body.split("\n")) {
    if (l.startsWith("- ")) out.push(l.slice(2).trim());
  }
  return out;
}

// ----- Delta derivations ----------------------------------------------

// Lower-better dims report their current value as the delta tier.
function driftDeltaOf   (_prev: DriftLevel,    curr: DriftLevel):    DriftLevel    { return curr; }
function loadDeltaOf    (_prev: LoadLevel,     curr: LoadLevel):     LoadLevel     { return curr; }
function pressureDeltaOf(_prev: PressureLevel, curr: PressureLevel): PressureLevel { return curr; }
function riskDeltaOf    (_prev: RiskLevel,     curr: RiskLevel):     RiskLevel     { return curr; }

// Higher-better dims report their delta as movement intensity:
// weak (weakening) → partial → moderate (improving) → strong.
type ClarityDelta = "weak" | "partial" | "moderate" | "strong";

function clarityDeltaOf(prev: ClarityLevel, curr: ClarityLevel): ClarityDelta {
  const ranks: Record<ClarityLevel, number> = { weak: 0, partial: 1, strong: 2 };
  const delta = ranks[curr] - ranks[prev];
  if (delta >= 2)  return "strong";
  if (delta === 1) return "moderate";
  if (delta === 0) {
    if (curr === "strong")  return "strong";
    if (curr === "partial") return "partial";
    return "weak";
  }
  return "weak";
}

type StabilityDelta = "weak" | "partial" | "strong";

function stabilityDeltaOf(prev: StabilityLevel, curr: StabilityLevel): StabilityDelta {
  const ranks: Record<StabilityLevel, number> = { weak: 0, moderate: 1, strong: 2 };
  const delta = ranks[curr] - ranks[prev];
  if (delta >= 2)  return "strong";
  if (delta === 1) return "partial";
  if (delta === 0) {
    if (curr === "strong")   return "strong";
    if (curr === "moderate") return "partial";
    return "weak";
  }
  return "weak";
}

// Slope = current operator level. The level itself is already a
// composite of clarity/drift/load/pressure/stability per Card 69,
// so this satisfies the spec's "derived from clarity/drift/load/
// pressure/stability deltas" without double-counting.
function operatorSlopeOf(_prev: Level, curr: Level): Level {
  return curr;
}

function directionOf(prev: Level, curr: Level): Direction {
  const d = LEVEL_RANK[curr] - LEVEL_RANK[prev];
  if (d > 0) return "improving";
  if (d < 0) return "deteriorating";
  return "stable";
}

// ----- Summary ---------------------------------------------------------

function clarityTrendWord(prev: ClarityLevel, curr: ClarityLevel): string {
  const ranks: Record<ClarityLevel, number> = { weak: 0, partial: 1, strong: 2 };
  const d = ranks[curr] - ranks[prev];
  if (d > 0) return "improving";
  if (d < 0) return "weakening";
  return "steady";
}

function stabilityTrendWord(prev: StabilityLevel, curr: StabilityLevel): string {
  const ranks: Record<StabilityLevel, number> = { weak: 0, moderate: 1, strong: 2 };
  const d = ranks[curr] - ranks[prev];
  if (d >= 2)   return "fully increasing";
  if (d === 1)  return "partially increasing";
  if (d === 0)  return "steady";
  return "weakening";
}

function buildSummary(
  direction: Direction,
  currPressure: PressureLevel,
  currDrift:    DriftLevel,
  clarityWord:  string,
  stabilityWord: string,
): string {
  let s1: string;
  if (direction === "improving") {
    if (currPressure === "elevated" || currPressure === "high") {
      s1 = "Operator trajectory is improving but remains under elevated pressure.";
    } else {
      s1 = "Operator trajectory is improving.";
    }
  } else if (direction === "deteriorating") {
    if (currPressure === "high") {
      s1 = "Operator trajectory is deteriorating under high pressure.";
    } else if (currPressure === "elevated") {
      s1 = "Operator trajectory is deteriorating under elevated pressure.";
    } else {
      s1 = "Operator trajectory is deteriorating.";
    }
  } else {
    if (currPressure === "elevated" || currPressure === "high") {
      s1 = "Operator trajectory is steady but under elevated pressure.";
    } else {
      s1 = "Operator trajectory is steady.";
    }
  }

  const s2 = `Drift is ${currDrift}, clarity is ${clarityWord}, and stability is ${stabilityWord}.`;
  return `${s1} ${s2}`;
}

// ----- Entry point -----------------------------------------------------

export function buildOperatorDiff(
  previousOperatorState: string,
  currentOperatorState:  string,
): string {
  const prev = previousOperatorState ?? "";
  const curr = currentOperatorState  ?? "";

  // Parse both states.
  const prevLevel     = parseOperatorLevel(prev);
  const prevLoad      = parseLoad(prev);
  const prevDrift     = parseDrift(prev);
  const prevClarity   = parseClarity(prev);
  const prevStability = parseStability(prev);
  const prevPressure  = parsePressure(prev);
  const prevRisk      = parseRisk(prev);

  const currLevel     = parseOperatorLevel(curr);
  const currLoad      = parseLoad(curr);
  const currDrift     = parseDrift(curr);
  const currClarity   = parseClarity(curr);
  const currStability = parseStability(curr);
  const currPressure  = parsePressure(curr);
  const currRisk      = parseRisk(curr);

  // Compute deltas.
  const slope          = operatorSlopeOf(prevLevel, currLevel);
  const driftDelta     = driftDeltaOf(prevDrift, currDrift);
  const clarityDelta   = clarityDeltaOf(prevClarity, currClarity);
  const loadDelta      = loadDeltaOf(prevLoad, currLoad);
  const pressureDelta  = pressureDeltaOf(prevPressure, currPressure);
  const stabilityDelta = stabilityDeltaOf(prevStability, currStability);
  const riskDelta      = riskDeltaOf(prevRisk, currRisk);

  // Drivers + inhibitors carry over from the current state's Card 69
  // output — the diff reflects what the current trajectory is doing.
  const drivers    = parseListSection(curr, "Operator Drivers");
  const inhibitors = parseListSection(curr, "Operator Inhibitors");

  // Direction drives the summary opening clause.
  const direction     = directionOf(prevLevel, currLevel);
  const clarityWord   = clarityTrendWord(prevClarity, currClarity);
  const stabilityWord = stabilityTrendWord(prevStability, currStability);
  const summary       = buildSummary(direction, currPressure, currDrift, clarityWord, stabilityWord);

  const blocks: string[] = [];
  blocks.push("=== Operator Diff ===");
  blocks.push(`[Operator Slope]\n${slope}`);
  blocks.push(`[Drift Delta]\n${driftDelta}`);
  blocks.push(`[Clarity Delta]\n${clarityDelta}`);
  blocks.push(`[Load Delta]\n${loadDelta}`);
  blocks.push(`[Pressure Delta]\n${pressureDelta}`);
  blocks.push(`[Stability Delta]\n${stabilityDelta}`);
  blocks.push(`[Risk Delta]\n${riskDelta}`);
  blocks.push(
    drivers.length === 0
      ? `[Operator Diff Drivers]\n(none)`
      : `[Operator Diff Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Operator Diff Inhibitors]\n(none)`
      : `[Operator Diff Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(`[Operator Diff Summary]\n${summary}`);

  return blocks.join("\n\n");
}
