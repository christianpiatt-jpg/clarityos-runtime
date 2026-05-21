// Markov QC — single-shot tester for the /markov engine.
// Pushes the score to the global MQC indicator in the status bar.

import { useState } from "react";
import { ApiError, markov, type MarkovResult } from "../lib/api";
import { pushMarkovScore } from "../components/Layout";

interface RunRecord {
  ts: number;
  text: string;
  result: MarkovResult["data"];
}

export default function Markov() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<RunRecord[]>([]);

  async function run() {
    if (!text.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const r = await markov(text);
      pushMarkovScore(r.data.score);
      const rec: RunRecord = { ts: Date.now(), text: text.trim(), result: r.data };
      setHistory((h) => [rec, ...h].slice(0, 25));
    } catch (e: any) {
      const msg = e instanceof ApiError ? e.message : (e?.message || "Markov call failed");
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="panel">
        <h1>MARKOV QC</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Single-shot quality check against the runtime engine. Score → 0 (low signal) … 1 (high signal).
          The latest score is pinned to the status bar's MQC cell.
        </p>
      </div>

      {error ? <div className="banner err">{error}</div> : null}

      <div className="panel">
        <div className="field">
          <label htmlFor="mq-input">Input</label>
          <textarea
            id="mq-input"
            className="input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste a sentence or paragraph to QC."
            rows={6}
            disabled={busy}
          />
        </div>
        <div className="row">
          <button className="btn" onClick={run} disabled={busy || !text.trim()}>
            {busy ? <span className="spinner" /> : "RUN MARKOV"}
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setText("")}
            disabled={busy || !text}
          >
            CLEAR
          </button>
        </div>
      </div>

      {history.length === 0 ? (
        <div className="empty">No runs yet. Submit input above to populate history.</div>
      ) : (
        history.map((r, i) => (
          <div key={i} className="panel">
            <div className="row row-between" style={{ marginBottom: 8 }}>
              <span className="label">{new Date(r.ts).toLocaleString()}</span>
              <span
                className="mono"
                style={{
                  color: r.result.score > 0.5 ? "var(--os-focus)" : "var(--os-text-secondary)",
                  fontSize: "1rem",
                  fontWeight: 600,
                }}
              >
                {r.result.score.toFixed(3)}
              </span>
            </div>
            <pre className="output">{r.text}</pre>
            <div className="row" style={{ marginTop: 8 }}>
              {(r.result.tags || []).map((t, ix) => (
                <span key={ix} className="tag cyan">{t}</span>
              ))}
              {(r.result.tags || []).length === 0 ? (
                <span className="dim mono" style={{ fontSize: "0.75rem" }}>no tags</span>
              ) : null}
            </div>
            <p className="muted" style={{ marginTop: 12, fontSize: "0.85rem" }}>
              {r.result.interpretation}
            </p>
          </div>
        ))
      )}
    </div>
  );
}
