// components/cockpit/RegressionFirstPanel.tsx — v80 packet runner.
//
// Operator pastes a cognitive packet (EL/INS + regression_chain
// skeleton, as emitted upstream under the canonical bundle prompt)
// and runs it through ``POST /me/regression_first/packet``. On
// success, renders a one-line summary of the resulting chain (title,
// seeded layer index + status, vault-stored chain id).
//
// Auth gating is delegated to the surrounding Cockpit route (which
// already lives under ``<RequireAuth>``). This component does NOT
// re-check auth — that would duplicate state.

import { useCallback, useId, useMemo, useState } from "react";
import {
  ApiError,
  postRegressionFirstPacket,
  replayRegressionFirstChain,
  type RegressionFirstChain,
} from "../../lib/api";

type RunState =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "ok"; chain: RegressionFirstChain; source: "packet" | "replay" }
  | { kind: "error"; code: string; message: string };

const EXAMPLE_PACKET = `{
  "EL": 2,
  "INS": 3,
  "ratio": "0.67",
  "el_signals": ["something is wrong"],
  "ins_signals": ["page", "scaffold"],
  "classification": "structure-dominant",
  "operator_intent": "Identify root cause of rendering failure.",
  "regression_required": true,
  "regression_chain": [
    {
      "layer": 1,
      "name": "Domain & Routing",
      "question": "Which page is set as homepage?",
      "location": "Settings → Reading → Homepage",
      "goal": "Correct page selected"
    }
  ],
  "recommended_system_action": "Pause and request operator verification."
}`;

export default function RegressionFirstPanel() {
  const editorId = useId();
  const [packetText, setPacketText] = useState<string>(EXAMPLE_PACKET);
  const [run, setRun] = useState<RunState>({ kind: "idle" });

  const onRun = useCallback(async () => {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(packetText);
    } catch (e) {
      setRun({
        kind: "error",
        code: "invalid_json",
        message: "Packet body is not valid JSON.",
      });
      return;
    }
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      setRun({
        kind: "error",
        code: "invalid_json",
        message: "Packet must be a JSON object.",
      });
      return;
    }
    setRun({ kind: "running" });
    try {
      const chain = await postRegressionFirstPacket(parsed);
      setRun({ kind: "ok", chain, source: "packet" });
    } catch (e) {
      if (e instanceof ApiError) {
        setRun({
          kind: "error",
          code: e.code || "error",
          message: e.message || "Packet rejected by the kernel.",
        });
      } else {
        setRun({
          kind: "error",
          code: "unknown",
          message: e instanceof Error ? e.message : String(e),
        });
      }
    }
  }, [packetText]);

  const onRerun = useCallback(async () => {
    if (run.kind !== "ok") return;
    const chainId = run.chain.chain_id;
    setRun({ kind: "running" });
    try {
      const chain = await replayRegressionFirstChain(chainId);
      setRun({ kind: "ok", chain, source: "replay" });
    } catch (e) {
      if (e instanceof ApiError) {
        setRun({
          kind: "error",
          code: e.code || "error",
          message: e.message || "Replay rejected.",
        });
      } else {
        setRun({
          kind: "error",
          code: "unknown",
          message: e instanceof Error ? e.message : String(e),
        });
      }
    }
  }, [run]);

  const seededLayer = useMemo(() => {
    if (run.kind !== "ok") return null;
    const layers = run.chain.layers || [];
    if (layers.length === 0) return null;
    return layers[layers.length - 1];
  }, [run]);

  return (
    <div style={{ fontSize: 13 }}>
      <label
        htmlFor={editorId}
        style={{ display: "block", color: "#555", marginBottom: 4 }}
      >
        Cognitive packet (JSON)
      </label>
      <textarea
        id={editorId}
        data-testid="regression-first-packet-editor"
        value={packetText}
        onChange={(e) => setPacketText(e.target.value)}
        spellCheck={false}
        rows={12}
        style={{
          width: "100%",
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
          fontSize: 12,
          padding: 8,
          border: "1px solid #ddd",
          borderRadius: 4,
          resize: "vertical",
          boxSizing: "border-box",
        }}
      />
      <div
        style={{
          marginTop: 8,
          display: "flex",
          gap: 8,
          alignItems: "center",
        }}
      >
        <button
          type="button"
          data-testid="regression-first-run"
          onClick={onRun}
          disabled={run.kind === "running"}
          style={{
            padding: "6px 12px",
            fontSize: 13,
            cursor: run.kind === "running" ? "wait" : "pointer",
          }}
        >
          {run.kind === "running" ? "Running…" : "Run Regression First"}
        </button>
        {run.kind === "ok" && (
          <span
            data-testid="regression-first-ok"
            style={{ color: "#080", fontSize: 12 }}
          >
            Chain persisted.
          </span>
        )}
        {run.kind === "error" && (
          <span
            data-testid="regression-first-error"
            style={{ color: "#a00", fontSize: 12 }}
          >
            {run.code}: {run.message}
          </span>
        )}
      </div>

      {run.kind === "ok" && (
        <div
          data-testid="regression-first-summary"
          style={{
            marginTop: 12,
            padding: 12,
            border: "1px solid #ccc",
            borderRadius: 4,
            background: "#fafafa",
          }}
        >
          <div style={{ marginBottom: 4 }}>
            <strong>Title:</strong> {run.chain.title}
            {run.source === "replay" && (
              <span
                data-testid="regression-first-source-replay"
                style={{
                  marginLeft: 8, padding: "1px 6px", fontSize: 11,
                  background: "#eef", color: "#225", borderRadius: 2,
                }}
              >
                replay
              </span>
            )}
          </div>
          <div style={{ marginBottom: 4, color: "#666", fontSize: 12 }}>
            <strong>Chain id:</strong>{" "}
            <code>{run.chain.chain_id}</code>
          </div>
          <div style={{ marginBottom: 4, fontSize: 12 }}>
            <strong>Status:</strong>{" "}
            {run.chain.closed_at ? "closed" : "open"} · layers ={" "}
            {run.chain.layers.length} · tags ={" "}
            {Object.keys(run.chain.tags).length}
          </div>
          {seededLayer && (
            <div style={{ fontSize: 12, color: "#444", marginBottom: 8 }}>
              <strong>Seeded layer:</strong> index{" "}
              {seededLayer.layer_index} · status{" "}
              <code>{seededLayer.status}</code>
            </div>
          )}
          <button
            type="button"
            data-testid="regression-first-rerun"
            onClick={onRerun}
            style={{
              padding: "4px 10px",
              fontSize: 12,
              cursor: "pointer",
              border: "1px solid #88a",
              background: "#f5f5fa",
            }}
          >
            Rerun regression
          </button>
        </div>
      )}
    </div>
  );
}
