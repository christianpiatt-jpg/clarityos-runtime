// Card 48 — Structural heatmap (Phase-1 minimal).
//
// Desktop mirror of web/src/lib/operatorStructuralHeatmap.ts. Pure
// deterministic, client-side string builder rendering the system
// intensity map as a primitive × run grid.

import type {
  EngineV1HydraulicEvolutionMap,
  EngineV1LineageMap,
  EngineV1SystemOverlay,
} from "./api";

const LEGEND =
  "Legend:\n" +
  ". = no structural pressure\n" +
  "+ = low pressure\n" +
  "* = medium pressure\n" +
  "# = high pressure\n" +
  "! = volatility spike\n" +
  "~ = drift pressure\n" +
  "C = critical-zone pressure\n" +
  "B = upper-branch pressure";

const SEP          = " | ";
const HEADER_LABEL = "Primitive";

function pad(s: string, width: number): string {
  if (s.length >= width) return s;
  return s + " ".repeat(width - s.length);
}

function regimeIntensity(regime: string | undefined): number {
  switch (regime) {
    case "transitional": return 1;
    case "turbulent":    return 2;
    default:             return 0;
  }
}

function pressureSymbol(score: number): string {
  if (score <= 0) return ".";
  if (score === 1) return "+";
  if (score === 2) return "*";
  return "#";
}

interface HeatmapDerived {
  driftActive:  Record<string, boolean>;
  lastActiveIx: Record<string, number>;
}

function derive(
  lineageMap: EngineV1LineageMap,
  evo:        EngineV1HydraulicEvolutionMap,
): HeatmapDerived {
  const driftActive:  Record<string, boolean> = {};
  const lastActiveIx: Record<string, number>  = {};
  for (const id of lineageMap.primitive_ids) {
    const lineageRuns = lineageMap.lineages[id].runs;
    const evoRuns     = evo.perPrimitive[id]?.runs ?? [];
    const activeIxs   = lineageRuns
      .filter((r) => r.primitive !== null)
      .map((r)    => r.index);

    let drift = false;
    if (activeIxs.length >= 3) {
      const overlaysPresent = evoRuns.filter((r) => r.overlay !== null);
      if (overlaysPresent.length >= 1) {
        const first = overlaysPresent[0].overlay?.flow_regime;
        const last  = overlaysPresent[overlaysPresent.length - 1].overlay?.flow_regime;
        if (first && last && first !== last) drift = true;
      }
    }

    driftActive[id]  = drift;
    lastActiveIx[id] = activeIxs.length > 0 ? activeIxs[activeIxs.length - 1] : -1;
  }
  return { driftActive, lastActiveIx };
}

export function buildStructuralHeatmap(
  overlay:    EngineV1SystemOverlay,
  lineageMap: EngineV1LineageMap,
  evo:        EngineV1HydraulicEvolutionMap,
): string {
  void overlay;

  const primitive_ids = lineageMap.primitive_ids;
  const runCount      = evo.perRun.length;

  if (primitive_ids.length === 0) {
    return `=== Structural Heatmap ===\n\n${LEGEND}\n\n(no primitives)`;
  }
  if (runCount === 0) {
    return `=== Structural Heatmap ===\n\n${LEGEND}\n\n(no runs)`;
  }

  const { driftActive, lastActiveIx } = derive(lineageMap, evo);

  const allCells: string[][] = [];
  for (const id of primitive_ids) {
    const lineageRuns = lineageMap.lineages[id].runs;
    const evoRuns     = evo.perPrimitive[id]?.runs ?? [];

    const rowCells: string[] = [];
    for (let i = 0; i < runCount; i++) {
      const lineageRun = lineageRuns[i];
      if (!lineageRun || lineageRun.primitive === null) {
        rowCells.push("");
        continue;
      }

      const overlayHere = evoRuns[i]?.overlay ?? null;
      const inCrit      = overlayHere?.in_critical_zone ?? false;
      const upper       = overlayHere?.on_upper_branch  ?? false;
      const isDrifting  = driftActive[id] && i === lastActiveIx[id];

      let isVolatile = false;
      if (i > 0) {
        const prevOverlay = evoRuns[i - 1]?.overlay ?? null;
        if (
          prevOverlay &&
          overlayHere &&
          prevOverlay.flow_regime !== overlayHere.flow_regime
        ) {
          isVolatile = true;
        }
      }

      const score =
        regimeIntensity(overlayHere?.flow_regime) +
        (inCrit     ? 1 : 0) +
        (upper      ? 1 : 0) +
        (isVolatile ? 1 : 0) +
        (isDrifting ? 1 : 0);

      let cell = pressureSymbol(score);
      if (inCrit)     cell += "C";
      if (upper)      cell += "B";
      if (isVolatile) cell += "!";
      if (isDrifting) cell += "~";
      rowCells.push(cell);
    }
    allCells.push(rowCells);
  }

  const cellWidth = Math.max(
    2,
    ...allCells.flat().map((c) => c.length),
    ...Array.from({ length: runCount }, (_, i) => `R${i}`.length),
  );
  const primitiveWidth = Math.max(
    HEADER_LABEL.length,
    ...primitive_ids.map((id) => id.length),
  );

  const headerLabel = pad(HEADER_LABEL, primitiveWidth);
  const headerCells = Array.from(
    { length: runCount },
    (_, i) => pad(`R${i}`, cellWidth),
  );
  const headerRow  = headerLabel + SEP + headerCells.join(SEP);
  const sepRow     = "-".repeat(headerRow.length);

  const dataRows: string[] = primitive_ids.map((id, ix) =>
    pad(id, primitiveWidth) +
    SEP +
    allCells[ix].map((c) => pad(c, cellWidth)).join(SEP),
  );

  return (
    `=== Structural Heatmap ===\n\n` +
    LEGEND + "\n\n" +
    headerRow + "\n" +
    sepRow + "\n" +
    dataRows.join("\n")
  );
}
