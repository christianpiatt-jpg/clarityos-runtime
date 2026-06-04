// Card 44 — Operator diff viewer (Phase-1 minimal).
//
// Pure deterministic, client-side string builder that produces a
// hierarchical, text-only diff tree between two runs. Combines the
// Card 37 system-level regression (added / removed / changed +
// hydraulic deltas) with the Card 32 per-primitive field-level diffs
// (metadata / hydraulic_state / overlay) for every primitive in the
// `changed` set.
//
// Output layout (no colours, no styling, indentation via spaces only):
//
//   === Diff: Run X → Run Y ===
//
//   [Primitives]
//   + Added: [...]
//   - Removed: [...]
//   ~ Changed: [...]
//
//   [Hydraulic]
//   laminar: +N
//   transitional: -N
//   turbulent: 0
//   critical-zone: +N
//   upper-branch: 0
//
//   [Primitive Details]
//   <id>:
//     metadata changes:
//       - <field>: <old> → <new>
//     hydraulic changes:
//       - <field>: <old> → <new>
//     overlay changes:
//       - <field>: <old> → <new>

import type {
  EngineV1LineageMap,
  EngineV1SystemRegressionDiff,
} from "./api";

function fmtDelta(n: number): string {
  if (n > 0) return `+${n}`;
  return `${n}`;
}

function listOrNone(ids: string[]): string {
  return ids.length === 0 ? "(none)" : `[${ids.join(", ")}]`;
}

// JSON.stringify-based value formatter so strings get quoted (`"foo"`),
// numbers / booleans / null print plainly, and nested structures
// collapse to a single compact line. Matches the spec example
// (`name: "foo" → "foo2"`, `critical-zone: false → true`).
function fmtValue(v: unknown): string {
  return JSON.stringify(v) ?? "undefined";
}

// Generic field-level diff: returns one indented line per field whose
// JSON-stringified value differs between the two objects. Field
// enumeration is the union of the two key sets, so additions /
// removals show up alongside in-place edits.
function diffObjectFields(
  from: Record<string, unknown> | null | undefined,
  to:   Record<string, unknown> | null | undefined,
): string[] {
  if (!from || !to) return [];
  const fields = new Set([...Object.keys(from), ...Object.keys(to)]);
  const lines: string[] = [];
  for (const f of fields) {
    if (fmtValue(from[f]) !== fmtValue(to[f])) {
      lines.push(`    - ${f}: ${fmtValue(from[f])} → ${fmtValue(to[f])}`);
    }
  }
  return lines;
}

export function buildDiffView(
  diff:       EngineV1SystemRegressionDiff,
  lineageMap: EngineV1LineageMap,
): string {
  const blocks: string[] = [];

  blocks.push(`=== Diff: Run ${diff.fromIndex} → Run ${diff.toIndex} ===`);

  blocks.push(
    `[Primitives]\n` +
    `+ Added: ${listOrNone(diff.primitiveChanges.added)}\n` +
    `- Removed: ${listOrNone(diff.primitiveChanges.removed)}\n` +
    `~ Changed: ${listOrNone(diff.primitiveChanges.changed)}`,
  );

  blocks.push(
    `[Hydraulic]\n` +
    `laminar: ${fmtDelta(diff.hydraulic.laminarDelta)}\n` +
    `transitional: ${fmtDelta(diff.hydraulic.transitionalDelta)}\n` +
    `turbulent: ${fmtDelta(diff.hydraulic.turbulentDelta)}\n` +
    `critical-zone: ${fmtDelta(diff.hydraulic.criticalZoneDelta)}\n` +
    `upper-branch: ${fmtDelta(diff.hydraulic.upperBranchDelta)}`,
  );

  // Per-primitive detail blocks for the `changed` set. Added /
  // removed primitives don't get field diffs — their entry on one
  // side is null and field-level comparison is meaningless.
  const detailBlocks: string[] = [];
  for (const id of diff.primitiveChanges.changed) {
    const primDiff = lineageMap.diffs[id];
    if (!primDiff) continue;

    const matches = <T extends { indexFrom: number; indexTo: number }>(c: T) =>
      c.indexFrom === diff.fromIndex && c.indexTo === diff.toIndex;

    const metaC = primDiff.metadataChanges.find(matches);
    const hydC  = primDiff.hydraulicChanges.find(matches);
    const ovC   = primDiff.overlayChanges.find(matches);

    const lines: string[] = [`${id}:`];

    if (metaC) {
      const fieldLines = diffObjectFields(
        metaC.from?.metadata as Record<string, unknown> | undefined,
        metaC.to?.metadata   as Record<string, unknown> | undefined,
      );
      if (fieldLines.length > 0) {
        lines.push(`  metadata changes:`);
        lines.push(...fieldLines);
      }
    }

    if (hydC) {
      const fieldLines = diffObjectFields(
        hydC.from?.hydraulic_state as Record<string, unknown> | undefined,
        hydC.to?.hydraulic_state   as Record<string, unknown> | undefined,
      );
      if (fieldLines.length > 0) {
        lines.push(`  hydraulic changes:`);
        lines.push(...fieldLines);
      }
    }

    if (ovC) {
      const fieldLines = diffObjectFields(
        ovC.from as Record<string, unknown> | null | undefined,
        ovC.to   as Record<string, unknown> | null | undefined,
      );
      if (fieldLines.length > 0) {
        lines.push(`  overlay changes:`);
        lines.push(...fieldLines);
      }
    }

    if (lines.length > 1) detailBlocks.push(lines.join("\n"));
  }

  if (detailBlocks.length > 0) {
    blocks.push(`[Primitive Details]\n${detailBlocks.join("\n\n")}`);
  } else {
    blocks.push(`[Primitive Details]\n(no per-primitive field changes)`);
  }

  return blocks.join("\n\n");
}
