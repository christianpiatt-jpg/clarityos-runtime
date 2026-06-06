// Card 47 — Multi-run structural matrix (Phase-1 minimal).
//
// Desktop mirror of web/src/lib/operatorStructuralMatrix.ts. Pure
// deterministic, client-side string builder rendering the system
// structure as a primitive × run grid.

import type {
  EngineV1HydraulicEvolutionMap,
  EngineV1LineageMap,
  EngineV1SystemOverlay,
} from "./api";

const LEGEND =
  "Legend:\n" +
  "L = laminar\n" +
  "T = transitional\n" +
  "U = turbulent\n" +
  "C = critical-zone\n" +
  "B = upper-branch\n" +
  "* = structural change\n" +
  "! = volatility marker\n" +
  "~ = drift marker";

const CELL_WIDTH      = 13;
const SEP             = " | ";
const HEADER_LABEL    = "Primitive";

function regimeLetter(regime: string | undefined): string {
  switch (regime) {
    case "laminar":      return "L";
    case "transitional": return "T";
    case "turbulent":    return "U";
    default:             return "";
  }
}

function pad(s: string, width: number): string {
  if (s.length >= width) return s;
  return s + " ".repeat(width - s.length);
}

export function buildStructuralMatrix(
  overlay:    EngineV1SystemOverlay,
  lineageMap: EngineV1LineageMap,
  evo:        EngineV1HydraulicEvolutionMap,
): string {
  void overlay;

  const primitive_ids = lineageMap.primitive_ids;
  const runCount      = evo.perRun.length;

  if (primitive_ids.length === 0) {
    return `=== Structural Matrix ===\n\n${LEGEND}\n\n(no primitives)`;
  }
  if (runCount === 0) {
    return `=== Structural Matrix ===\n\n${LEGEND}\n\n(no runs)`;
  }

  const primitiveWidth = Math.max(
    HEADER_LABEL.length,
    ...primitive_ids.map((id) => id.length),
  );

  const headerLabel = pad(HEADER_LABEL, primitiveWidth);
  const headerCells = Array.from(
    { length: runCount },
    (_, i) => pad(`R${i}`, CELL_WIDTH),
  );
  const headerRow  = headerLabel + SEP + headerCells.join(SEP);
  const sepRow     = "-".repeat(headerRow.length);

  const dataRows: string[] = [];
  for (const id of primitive_ids) {
    const lineageRuns = lineageMap.lineages[id].runs;
    const evoRuns     = evo.perPrimitive[id]?.runs ?? [];
    const diff        = lineageMap.diffs[id];

    const activeIxs   = lineageRuns
      .filter((r) => r.primitive !== null)
      .map((r)    => r.index);
    let driftActive   = false;
    if (activeIxs.length >= 3) {
      const overlaysWithRuns = evoRuns
        .filter((r) => r.overlay !== null);
      if (overlaysWithRuns.length >= 1) {
        const firstRegime = overlaysWithRuns[0].overlay?.flow_regime;
        const lastRegime  = overlaysWithRuns[overlaysWithRuns.length - 1].overlay?.flow_regime;
        if (firstRegime && lastRegime && firstRegime !== lastRegime) {
          driftActive = true;
        }
      }
    }
    const lastActiveIx = activeIxs.length > 0
      ? activeIxs[activeIxs.length - 1]
      : -1;

    const cells: string[] = [];
    for (let i = 0; i < runCount; i++) {
      const lineageRun = lineageRuns[i];
      if (!lineageRun || lineageRun.primitive === null) {
        cells.push("(absent)");
        continue;
      }

      const overlayHere = evoRuns[i]?.overlay ?? null;
      const tokens: string[] = [];
      const letter = regimeLetter(overlayHere?.flow_regime);
      if (letter) tokens.push(letter);
      if (overlayHere?.in_critical_zone) tokens.push("C");
      if (overlayHere?.on_upper_branch)  tokens.push("B");

      if (i > 0) {
        const matchesPair = (c: { indexFrom: number; indexTo: number }) =>
          c.indexFrom === i - 1 && c.indexTo === i;
        const hasChange =
          diff.appearance.added.includes(i)   ||
          diff.appearance.removed.includes(i) ||
          diff.metadataChanges.some(matchesPair)  ||
          diff.hydraulicChanges.some(matchesPair) ||
          diff.overlayChanges.some(matchesPair);
        if (hasChange) tokens.push("*");

        const prevOverlay = evoRuns[i - 1]?.overlay ?? null;
        if (
          prevOverlay &&
          overlayHere &&
          prevOverlay.flow_regime !== overlayHere.flow_regime
        ) {
          tokens.push("!");
        }
      }

      if (driftActive && i === lastActiveIx) tokens.push("~");

      cells.push(tokens.join(" "));
    }

    dataRows.push(
      pad(id, primitiveWidth) + SEP +
      cells.map((c) => pad(c, CELL_WIDTH)).join(SEP),
    );
  }

  return (
    `=== Structural Matrix ===\n\n` +
    LEGEND + "\n\n" +
    headerRow + "\n" +
    sepRow + "\n" +
    dataRows.join("\n")
  );
}
