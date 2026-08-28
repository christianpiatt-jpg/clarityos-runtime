// Markov QC — single-shot tester for the /markov engine.
//
// ★ RENDER FIX 2026-08-28. This page read `score` / `tags` / `interpretation`.
// markov_adapter stopped emitting those when the v2.1 stub was replaced by the
// v81 P-series recast (app.py:1031 records the replacement); it now returns
// `model` / `provider` / `output` / `mock` / `user` / `primitives` /
// `primitives_formatted` / `primitives_meta` / `recast`. Every field this page
// displayed was `undefined`, and the P-series decomposition — which crosses
// the wire on every call — was discarded on arrival.
//
// ★★ NOTHING NEW IS COMPUTED HERE. The adapter is untouched. This renames the
// reads to what already arrives.
//
// ★★★ THE MQC STATUS-BAR CELL LOST ITS PRODUCER, AND IT WAS WORSE THAN BLANK.
// `pushMarkovScore(r.data.score)` pushed `undefined`. Layout.tsx:176 guards
// with `mqc.score !== null` — which `undefined` PASSES — and then calls
// `.toFixed(2)` on it. That is a render crash, not an empty cell. The push is
// removed rather than fed a substitute: inventing a score here would be a
// computation, and the adapter emits nothing score-shaped. The cell now shows
// its idle "—", which is the honest state. Reported for CT-1.

import { useState } from "react";
import { ApiError, markov, type MarkovResult } from "../lib/api";

interface RunRecord {
  ts: number;
  text: string;
  result: MarkovResult["data"];
}

/** Render a value the adapter may not have sent. ★ Never blank — an empty
 *  string is indistinguishable from a field that arrived empty on purpose. */
function present(v: unknown): string {
  if (v === null || v === undefined) return "(absent)";
  if (typeof v === "string") return v.trim() === "" ? "(absent)" : v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  return "(absent)";
}

const COUNT_ORDER = ["P1", "P2", "P3", "P4", "Ts", "Te", "M", "hydronic"] as const;

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
          Single-shot run against the runtime engine. Returns the deterministic
          P-series decomposition of the input plus the model's recast of it.
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
        <div className="row" style={{ marginTop: 8 }}>
          <button className="btn" onClick={run} disabled={busy || !text.trim()}>
            {busy ? "RUNNING…" : "RUN"}
          </button>
        </div>
      </div>

      {history.length === 0 ? (
        <div className="panel">
          <p className="muted">No runs yet.</p>
        </div>
      ) : (
        history.map((r, i) => (
          <div key={i} className="panel" data-testid="markov-run">
            <div className="row row-between" style={{ marginBottom: 8 }}>
              <span className="label">{new Date(r.ts).toLocaleString()}</span>
              <span className="mono dim" style={{ fontSize: "0.75rem" }}>
                {present(r.result?.model)}
                {r.result?.mock ? " · mock" : ""}
              </span>
            </div>

            <pre className="output">{r.text}</pre>

            {/* The 8-category distribution. This already crossed the wire on
                every call and was thrown away. */}
            <div className="row" style={{ marginTop: 8 }} data-testid="markov-counts">
              {COUNT_ORDER.map((k) => {
                const n = r.result?.primitives_meta?.counts?.[k];
                return (
                  <span key={k} className="tag cyan" title={`${k} occurrences`}>
                    {k}: {n === undefined || n === null ? "(absent)" : n}
                  </span>
                );
              })}
            </div>

            <p className="label" style={{ marginTop: 12 }}>RECAST</p>
            <p className="muted" style={{ fontSize: "0.85rem" }} data-testid="markov-recast">
              {present(r.result?.recast ?? r.result?.output)}
            </p>

            {/* ★ primitives_formatted is the module's own canonical Markdown
                rendering (P1 → P2 → P3 → P4 → Tensions → Hydronic), and it
                never omits a section — an empty one renders "_(none
                detected)_". Shown verbatim rather than re-laid-out here,
                because re-formatting it would be authoring a second
                presentation of the same object. */}
            <details style={{ marginTop: 12 }}>
              <summary className="label" style={{ cursor: "pointer" }}>
                P-SERIES DECOMPOSITION
              </summary>
              <pre className="output" data-testid="markov-formatted">
                {present(r.result?.primitives_formatted)}
              </pre>
            </details>
          </div>
        ))
      )}
    </div>
  );
}
