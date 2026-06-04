// Card 47 — Multi-run structural matrix (Phase-1 minimal).
//
// Pure deterministic, client-side string builder that renders the
// entire system structure as a primitive × run grid. Cells are
// text-only token bags:
//
//   regime letter   L / T / U      laminar / transitional / turbulent
//   zone flag       C              in_critical_zone === true
//   branch flag     B              on_upper_branch === true
//   change marker   *              any structural change from prev run
//   volatility      !              regime change at this transition
//   drift marker    ~              first vs last overlay regime differ
//                                  AND primitive active ≥ 3 runs
//
// Absent primitives display "(absent)" on inactive runs. Column widths
// are deterministic so that pipe-separated cells line up under any
// monospace renderer.

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

// Cell width is the longest possible token bag ("U C B * ! ~" = 11
// chars) padded to 13 so column gutters stay readable.
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
  // The overlay is the canonical Card 36 artifact, but the matrix
  // reads directly from lineageMap + evo. Kept in the signature for
  // future-proofing.
  void overlay;

  const primitive_ids = lineageMap.primitive_ids;
  const runCount      = evo.perRun.length;

  if (primitive_ids.length === 0) {
    return `=== Structural Matrix ===\n\n${LEGEND}\n\n(no primitives)`;
  }
  if (runCount === 0) {
    return `=== Structural Matrix ===\n\n${LEGEND}\n\n(no runs)`;
  }

  // Primitive column auto-grows to fit the longest id; floor at 9
  // ("Primitive" header is 9 chars).
  const primitiveWidth = Math.max(
    HEADER_LABEL.length,
    ...primitive_ids.map((id) => id.length),
  );

  // Build the header + separator rows up front.
  const headerLabel = pad(HEADER_LABEL, primitiveWidth);
  const headerCells = Array.from(
    { length: runCount },
    (_, i) => pad(`R${i}`, CELL_WIDTH),
  );
  const headerRow  = headerLabel + SEP + headerCells.join(SEP);
  const sepRow     = "-".repeat(headerRow.length);

  // Data rows.
  const dataRows: string[] = [];
  for (const id of primitive_ids) {
    const lineageRuns = lineageMap.lineages[id].runs;
    const evoRuns     = evo.perPrimitive[id]?.runs ?? [];
    const diff        = lineageMap.diffs[id];

    // Drift detection (per-primitive flag, marker shown only on the
    // primitive's last active run).
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

      // Structural-change + volatility markers — both are
      // transition-scoped, so they only apply for i > 0.
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
