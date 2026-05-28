// Card 40 — Operator Console (desktop shell).
//
// Phase-1 minimal diagnostic panel mirroring web/src/routes/
// OperatorConsole.tsx. Wraps the same UI primitives in the desktop
// DesktopShell + DesktopAuthGate chrome.
//
// Body: textarea for JSON input → Load → 4 pre blocks (lineage map /
// hydraulic evolution / system overlay / regression diff). All
// wiring through the Card 39 EngineV1OperatorAPI.

import { useMemo, useState } from "react";

import {
  createEngineV1OperatorAPI,
  type EngineV1MultiRunContext,
} from "./lib/api";
import DesktopShell from "./DesktopShell";

const PLACEHOLDER = `{
  "runs": []
}`;

interface Props {
  onSignOut:  () => void;
  onNavigate: (label: string) => void;
}

export default function OperatorConsoleShell({ onSignOut, onNavigate }: Props) {
  const api = useMemo(() => createEngineV1OperatorAPI(), []);

  const [jsonText, setJsonText] = useState<string>(PLACEHOLDER);
  const [context,  setContext]  = useState<EngineV1MultiRunContext | null>(null);
  const [parseErr, setParseErr] = useState<string | null>(null);

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

  const body = (
    <div>
      <h1>Operator Console</h1>
      <p>Engine V1 — Phase-1 diagnostic panel.</p>

      <section>
        <h2>Input</h2>
        <textarea
          value={jsonText}
          onChange={(e) => setJsonText(e.target.value)}
          rows={12}
          cols={80}
        />
        <div>
          <button onClick={handleLoad}>Load</button>
          <button onClick={() => { onSignOut(); }}>Sign out</button>
        </div>
        {parseErr ? <pre>{parseErr}</pre> : null}
      </section>

      <section>
        <h2>Lineage Map</h2>
        <pre>
          {lineageMap ? JSON.stringify(lineageMap, null, 2) : "(no context loaded)"}
        </pre>
      </section>

      <section>
        <h2>Hydraulic Evolution</h2>
        <pre>
          {hydraulicEvolution
            ? JSON.stringify(hydraulicEvolution, null, 2)
            : "(no context loaded)"}
        </pre>
      </section>

      <section>
        <h2>System Overlay</h2>
        <pre>
          {systemOverlay ? JSON.stringify(systemOverlay, null, 2) : "(no context loaded)"}
        </pre>
      </section>

      <section>
        <h2>System Regression Diff</h2>
        <div>
          <label>
            fromIndex{" "}
            <input
              type="number"
              value={fromIndex}
              onChange={(e) => setFromIndex(Number(e.target.value))}
            />
          </label>
          <label>
            {" "}toIndex{" "}
            <input
              type="number"
              value={toIndex}
              onChange={(e) => setToIndex(Number(e.target.value))}
            />
          </label>
        </div>
        <pre>
          {regressionDiff
            ? JSON.stringify(regressionDiff, null, 2)
            : "(load a context with at least 2 runs and valid indices)"}
        </pre>
      </section>
    </div>
  );

  return (
    <DesktopShell
      sidebar={null}
      center={body}
      insights={null}
      onNavigate={onNavigate}
      activeNav="Operator Console"
    />
  );
}
