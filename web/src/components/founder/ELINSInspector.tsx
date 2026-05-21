// components/founder/ELINSInspector.tsx — run the canonical 10-layer
// pipeline against arbitrary text + render every layer + run S_ELINS QC.

import { useCallback, useEffect, useState } from "react";
import {
  elinsPreview, elinsQC, founderMacroRunsList, meOperatorState,
  type V33ELINSObject, type V33SELINSResult, type V36MacroRun,
  type V39ElinsHistoryEntry,
} from "../../lib/api";
import ForecastPanel from "./forecast/ForecastPanel";
import RegionalPanel from "./regional/RegionalPanel";

export default function ELINSInspector() {
  const [text, setText] = useState("");
  const [domainHint, setDomainHint] = useState("");
  const [obj, setObj] = useState<V33ELINSObject | null>(null);
  const [qc, setQc] = useState<V33SELINSResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"scenario" | "regional">("scenario");
  const [latestMacro, setLatestMacro] = useState<V36MacroRun | null>(null);
  const [recentRuns, setRecentRuns] = useState<V39ElinsHistoryEntry[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await founderMacroRunsList(1);
        if (!cancelled) setLatestMacro(r.runs[0] || null);
      } catch {
        // founder gate may reject; that's fine — just hide the link.
      }
    })();
    (async () => {
      try {
        const s = await meOperatorState();
        if (!cancelled) setRecentRuns(s.state.elins_history.slice(-6).reverse());
      } catch {
        // Auth gate may reject for non-session paths; ignore.
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const run = useCallback(async () => {
    if (!text.trim()) return;
    setBusy("preview");
    setError(null);
    setObj(null);
    setQc(null);
    try {
      const r = await elinsPreview(text.trim(), domainHint || undefined);
      setObj(r.elins);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }, [text, domainHint]);

  const runQC = useCallback(async () => {
    if (!obj) return;
    setBusy("qc");
    setError(null);
    try {
      const r = await elinsQC(obj);
      setQc(r.s_elins);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }, [obj]);

  return (
    <section style={panelStyle}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>ELINS inspector</h2>
        <div style={{ display: "flex", gap: 4 }}>
          <button
            type="button"
            onClick={() => setTab("scenario")}
            style={tabStyle(tab === "scenario")}
          >Scenario</button>
          <button
            type="button"
            onClick={() => setTab("regional")}
            style={tabStyle(tab === "regional")}
          >Regional</button>
        </div>
      </div>
      {latestMacro && (
        <div style={{ marginBottom: 8, fontSize: 11, color: "var(--os-text-secondary, #A0A0A0)" }}>
          Latest macro run: <code>{latestMacro.run_id}</code> · {latestMacro.regions.length} regions ·
          {" "}{new Date(latestMacro.ts * 1000).toISOString().slice(0, 16).replace("T", " ")}
        </div>
      )}

      {tab === "regional" ? <RegionalPanel /> : null}
      {tab === "scenario" && <>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Scenario text"
        rows={3}
        maxLength={8000}
        style={{ ...inputStyle, resize: "vertical" }}
        aria-label="Scenario text"
      />
      <div style={{ display: "flex", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
        <select
          value={domainHint}
          onChange={(e) => setDomainHint(e.target.value)}
          style={{ padding: "4px 6px", fontSize: 12 }}
          aria-label="Domain hint"
        >
          <option value="">(no hint)</option>
          {["legal","institutional","economic","geopolitical","social","personal","technological","ecological"].map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        <button onClick={() => void run()} disabled={busy === "preview" || !text.trim()}>
          {busy === "preview" ? "Running…" : "Run /elins/preview"}
        </button>
        <button onClick={() => void runQC()} disabled={busy === "qc" || !obj}>
          {busy === "qc" ? "QC…" : "Run S_ELINS QC"}
        </button>
      </div>

      {error && (
        <div style={errorStyle}>{error}</div>
      )}

      {obj && (
        <div style={{ marginTop: 12 }}>
          <h3 style={{ fontSize: 13, margin: "0 0 6px 0" }}>Synthesis</h3>
          <pre style={preStyle}>{JSON.stringify(obj.synthesis, null, 2)}</pre>
          <h3 style={{ fontSize: 13, margin: "8px 0 6px 0" }}>Primitives</h3>
          <pre style={preStyle}>{JSON.stringify(obj.primitives.intensities, null, 2)}</pre>
          <h3 style={{ fontSize: 13, margin: "8px 0 6px 0" }}>5-day forecast</h3>
          <pre style={preStyle}>{JSON.stringify(obj.forecast_5day.days, null, 2)}</pre>
          <h3 style={{ fontSize: 13, margin: "8px 0 6px 0" }}>Causal chain</h3>
          <pre style={preStyle}>{JSON.stringify(obj.causal_chain, null, 2)}</pre>
          {obj.synthesis?.external_anchors && obj.synthesis.external_anchors.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <h3 style={{ fontSize: 13, margin: "0 0 6px 0" }}>Anchors → entity graph</h3>
              <ul style={{ margin: 0, paddingLeft: 16, fontSize: 11 }}>
                {obj.synthesis.external_anchors.map((a) => (
                  <li key={a}>
                    <a
                      href={`/elins/entities/${encodeURIComponent(a)}/neighbors`}
                      onClick={(e) => e.preventDefault()}
                      style={{ color: "var(--os-focus, #00F0FF)", textDecoration: "none" }}
                    >{a}</a>
                  </li>
                ))}
              </ul>
              <div style={{ marginTop: 4, fontSize: 10, color: "var(--os-text-tertiary, #585858)" }}>
                Anchor names match entity-graph nodes when present.
              </div>
            </div>
          )}

          {recentRuns.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <h3 style={{ fontSize: 13, margin: "0 0 6px 0" }}>Related past runs</h3>
              <ul style={{ margin: 0, paddingLeft: 16, fontSize: 11 }}>
                {recentRuns.map((entry, i) => (
                  <li key={`${entry.ts}-${i}`}>
                    <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>
                      [{entry.region || entry.kind}]
                    </span>
                    {" "}
                    <span>{entry.topic || entry.elins_id || "—"}</span>
                    <span style={{ color: "var(--os-text-tertiary, #585858)", marginLeft: 6 }}>
                      {new Date(entry.ts * 1000).toISOString().slice(0, 10)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {qc && (
        <div style={{
          marginTop: 12,
          padding: 8,
          background: qc.passed ? "#e6f5ec" : "#fde2e2",
          border: `1px solid ${qc.passed ? "#9c9" : "#f99"}`,
          borderRadius: 4,
        }}>
          <strong>S_ELINS QC: {qc.passed ? "PASS" : "FAIL"}</strong>
          <div style={{ fontSize: 12, marginTop: 4 }}>
            alignment: <code>{qc.alignment_score}</code> · max delta: <code>{qc.max_delta}</code>
          </div>
        </div>
      )}

      {obj?.forecast_engine && (
        <div style={{ marginTop: 12 }}>
          <ForecastPanel block={obj.forecast_engine} title="Forecast engine (v34)" compact />
        </div>
      )}
      </>}
    </section>
  );
}

function tabStyle(active: boolean): React.CSSProperties {
  return {
    fontSize: 11, padding: "3px 10px",
    border: `1px solid ${active ? "var(--os-focus, #00F0FF)" : "var(--os-line-strong, rgba(255,255,255,0.16))"}`,
    background: active ? "var(--os-elevated, #1a1a1a)" : "var(--os-surface, #111)",
    color: active ? "var(--os-focus, #00F0FF)" : "var(--os-text-primary, #fff)",
    borderRadius: "var(--radius-pill, 999px)",
    cursor: "pointer",
    fontWeight: active ? 600 : 400,
  };
}

const panelStyle: React.CSSProperties = {
  border: "1px solid #ddd",
  borderRadius: 6,
  padding: 12,
  background: "#fff",
  marginBottom: 12,
};

const inputStyle: React.CSSProperties = {
  display: "block",
  width: "100%",
  padding: "6px 8px",
  fontSize: 13,
  border: "1px solid #ccc",
  borderRadius: 4,
  boxSizing: "border-box",
};

const preStyle: React.CSSProperties = {
  background: "#fafafa",
  padding: 6,
  fontSize: 11,
  overflow: "auto",
  maxHeight: 200,
  margin: 0,
};

const errorStyle: React.CSSProperties = {
  padding: 6,
  background: "#fee",
  border: "1px solid #f99",
  borderRadius: 4,
  fontSize: 12,
  marginTop: 8,
};
