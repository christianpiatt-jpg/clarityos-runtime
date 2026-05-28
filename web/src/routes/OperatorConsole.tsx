// Card 40 — Operator Console (Phase-1 minimal).
//
// First UI-facing operator-layer surface. Pure developer/operator
// diagnostic panel — no styling beyond raw HTML, no charts, no
// components, no navigation changes. The operator pastes a
// multi-run-context JSON, clicks Load, and gets back:
//   - the lineage map (Card 34)
//   - the hydraulic evolution map (Card 35)
//   - the system overlay (Card 36)
//   - the system regression diff (Card 37) between two run indices
//
// All wiring goes through the Card 39 EngineV1OperatorAPI so the
// console is decoupled from the individual helper exports.
//
// The "multi-run context" input is a JSON document shaped like the
// EngineV1MultiRunContext from Card 29 (i.e. { runs: [ctx, ctx, ...] }
// where each ctx is an EngineV1OperatorContext snapshot). That matches
// the shape the Card 29 createMultiRunContext factory wraps.

import { useMemo, useState } from "react";

import {
  createEngineV1OperatorAPI,
  type EngineV1MultiRunContext,
} from "../lib/api";

const PLACEHOLDER = `{
  "runs": []
}`;

export default function OperatorConsole() {
  const api = useMemo(() => createEngineV1OperatorAPI(), []);

  const [jsonText,  setJsonText]  = useState<string>(PLACEHOLDER);
  const [context,   setContext]   = useState<EngineV1MultiRunContext | null>(null);
  const [parseErr,  setParseErr]  = useState<string | null>(null);

  const [fromIndex, setFromIndex] = useState<number>(0);
  const [toIndex,   setToIndex]   = useState<number>(1);

  function handleLoad() {
    setParseErr(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(jsonText);
    } catch (e) {
      setParseErr(`JSON parse error: ${(e as Error).message}`);
      setContext(null);
      return;
    }
    // Minimal shape check; full validation lives in Card 29+.
    if (
      !parsed ||
      typeof parsed !== "object" ||
      !Array.isArray((parsed as { runs?: unknown }).runs)
    ) {
      setParseErr('Expected an object with a "runs" array.');
      setContext(null);
      return;
    }
    setContext(parsed as EngineV1MultiRunContext);
  }

  const lineageMap = useMemo(
    () => (context ? api.buildLineageMap(context) : null),
    [api, context],
  );
  const hydraulicEvolution = useMemo(
    () => (lineageMap ? api.buildHydraulicEvolution(lineageMap) : null),
    [api, lineageMap],
  );
  const systemOverlay = useMemo(
    () => (context ? api.buildSystemOverlay(context) : null),
    [api, context],
  );
  const regressionDiff = useMemo(() => {
    if (!systemOverlay) return null;
    const runCount = systemOverlay.hydraulicEvolution.perRun.length;
    if (
      !Number.isInteger(fromIndex) || fromIndex < 0 || fromIndex >= runCount ||
      !Number.isInteger(toIndex)   || toIndex   < 0 || toIndex   >= runCount
    ) {
      return null;
    }
    try {
      return api.computeSystemRegression(systemOverlay, fromIndex, toIndex);
    } catch (e) {
      return { error: (e as Error).message };
    }
  }, [api, systemOverlay, fromIndex, toIndex]);

  return (
    <div data-testid="operator-console">
      <h1>Operator Console</h1>
      <p>Engine V1 — Phase-1 diagnostic panel.</p>

      <section>
        <h2>Input</h2>
        <textarea
          data-testid="oc-input"
          value={jsonText}
          onChange={(e) => setJsonText(e.target.value)}
          rows={12}
          cols={80}
        />
        <div>
          <button data-testid="oc-load" onClick={handleLoad}>Load</button>
        </div>
        {parseErr ? (
          <pre data-testid="oc-error">{parseErr}</pre>
        ) : null}
      </section>

      {/* Card 41 — collapsible structured views via native <details>.
          Each top-level section keeps the full JSON dump for tooling
          + adds per-primitive / per-run drill-ins beneath. Diff
          markers ([CHANGED], [ADDED], [REMOVED]) are text-only —
          no colours, no styling. */}

      <section data-testid="oc-lineage-map">
        <details>
          <summary>
            Lineage Map{lineageMap ? ` (${lineageMap.primitive_ids.length} primitives)` : ""}
          </summary>
          <pre>
            {lineageMap ? JSON.stringify(lineageMap, null, 2) : "(no context loaded)"}
          </pre>
          {lineageMap?.primitive_ids.map((id) => {
            const d = lineageMap.diffs[id];
            const changed =
              d.appearance.added.length   > 0 ||
              d.appearance.removed.length > 0 ||
              d.metadataChanges.length    > 0 ||
              d.hydraulicChanges.length   > 0 ||
              d.overlayChanges.length     > 0;
            return (
              <details key={id} data-testid={`oc-lineage-primitive-${id}`}>
                <summary>
                  {id}
                  {changed ? " [CHANGED]" : ""}
                </summary>
                <pre>{JSON.stringify(lineageMap.lineages[id], null, 2)}</pre>
              </details>
            );
          })}
        </details>
      </section>

      <section data-testid="oc-hydraulic-evolution">
        <details>
          <summary>
            Hydraulic Evolution
            {hydraulicEvolution ? ` (${hydraulicEvolution.perRun.length} runs)` : ""}
          </summary>
          <pre>
            {hydraulicEvolution
              ? JSON.stringify(hydraulicEvolution, null, 2)
              : "(no context loaded)"}
          </pre>
          {hydraulicEvolution?.perRun.map((run) => (
            <details key={run.index} data-testid={`oc-hydraulic-run-${run.index}`}>
              <summary>Run {run.index}</summary>
              <pre>{JSON.stringify(run, null, 2)}</pre>
            </details>
          ))}
        </details>
      </section>

      <section data-testid="oc-system-overlay">
        <details>
          <summary>System Overlay</summary>
          <pre>
            {systemOverlay ? JSON.stringify(systemOverlay, null, 2) : "(no context loaded)"}
          </pre>
        </details>
      </section>

      <section data-testid="oc-regression">
        <details>
          <summary>System Regression Diff</summary>
          <div>
            <label>
              fromIndex{" "}
              <input
                data-testid="oc-from-index"
                type="number"
                value={fromIndex}
                onChange={(e) => setFromIndex(Number(e.target.value))}
              />
            </label>
            <label>
              {" "}toIndex{" "}
              <input
                data-testid="oc-to-index"
                type="number"
                value={toIndex}
                onChange={(e) => setToIndex(Number(e.target.value))}
              />
            </label>
          </div>
          {regressionDiff && "primitiveChanges" in regressionDiff ? (
            <ul data-testid="oc-regression-markers">
              {regressionDiff.primitiveChanges.added.map((id) => (
                <li key={`add-${id}`}>{id} [ADDED]</li>
              ))}
              {regressionDiff.primitiveChanges.removed.map((id) => (
                <li key={`rem-${id}`}>{id} [REMOVED]</li>
              ))}
              {regressionDiff.primitiveChanges.changed.map((id) => (
                <li key={`chg-${id}`}>{id} [CHANGED]</li>
              ))}
            </ul>
          ) : null}
          <pre>
            {regressionDiff
              ? JSON.stringify(regressionDiff, null, 2)
              : "(load a context with at least 2 runs and valid indices)"}
          </pre>
        </details>
      </section>
    </div>
  );
}
