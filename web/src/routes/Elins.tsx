// ClarityOS ELINS surface (v29-hardened) — #G runner + daily delivered feed.
// Adds:
//   * /v29/flags gating (hard block when v28 surfaces are disabled)
//   * Loading states (initial fetch, action-in-flight)
//   * Error banners with manual retry
//   * Defensive rendering that never throws on missing analysis fields
//   * Idle-while-disabled empty state (no scary errors, just guidance)
//
// Deterministic backend output rendered verbatim; no scenario text persists
// past delivery.

import { useCallback, useState } from "react";
import { useElinsFeed } from "../hooks/useElinsFeed";
import { useFlags } from "../hooks/useFlags";
import {
  isSuccessfulAnalysis,
  queueDailyReport,
  runPersonalElins,
  type ElinsDeliveredReport,
  type GElinsAnalysis,
} from "../services/elins";

function fmtTs(ts: number | null | undefined): string {
  if (!ts) return "—";
  try { return new Date(Number(ts) * 1000).toISOString().replace("T", " ").slice(0, 19); }
  catch { return String(ts); }
}

const SCENARIO_MAX_LEN = 8000;

export default function Elins() {
  const { flags, loading: flagsLoading } = useFlags();
  const [scenario, setScenario] = useState("");
  const [analysis, setAnalysis] = useState<GElinsAnalysis | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [queueResult, setQueueResult] = useState<{ report_id: string; scheduled_for_ts: number } | null>(null);
  const { feed, loading: feedLoading, error: feedError, refresh: refreshFeed } = useElinsFeed(50);

  const v28Enabled = flags.v28_surfaces === true;

  const runG = useCallback(async () => {
    const text = scenario.trim();
    if (!text) {
      setError("Scenario must be non-empty.");
      return;
    }
    if (text.length > SCENARIO_MAX_LEN) {
      setError(`Scenario must be at most ${SCENARIO_MAX_LEN} characters.`);
      return;
    }
    setRunning(true);
    setError(null);
    setAnalysis(null);
    try {
      const a = await runPersonalElins(text);
      setAnalysis(a);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }, [scenario]);

  const queueDaily = useCallback(async () => {
    const text = scenario.trim();
    if (!text) {
      setError("Scenario must be non-empty.");
      return;
    }
    if (text.length > SCENARIO_MAX_LEN) {
      setError(`Scenario must be at most ${SCENARIO_MAX_LEN} characters.`);
      return;
    }
    setError(null);
    try {
      const r = await queueDailyReport({
        scenario_text: text,
        deliver_email: false,
        deliver_feed: true,
      });
      setQueueResult(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [scenario]);

  if (flagsLoading) {
    return (
      <div className="elins">
        <h1 style={{ marginTop: 0 }}>ELINS</h1>
        <p style={{ color: "#666" }}>Checking access…</p>
      </div>
    );
  }

  if (!v28Enabled) {
    return (
      <div className="elins">
        <h1 style={{ marginTop: 0 }}>ELINS</h1>
        <p style={{ color: "#666" }}>
          v28 surfaces (#G + daily feed) are not enabled for your account yet.
          Contact an admin to opt in.
        </p>
      </div>
    );
  }

  return (
    <div className="elins">
      <h1 style={{ marginTop: 0 }}>ELINS</h1>
      <p style={{ color: "#666", marginTop: -8 }}>
        #G runs use existing primitives only. No scenario text is persisted —
        only Dewey membership metadata. Daily reports deliver at 05:00 local.
      </p>

      <section style={{ border: "1px solid #ddd", padding: 12, borderRadius: 6, marginBottom: 16 }}>
        <h2 style={{ marginTop: 0, fontSize: 16 }}>Scenario</h2>
        <textarea
          value={scenario}
          onChange={(e) => setScenario(e.target.value)}
          placeholder="Describe the scenario (e.g. 'us-china trade tensions and energy supply')"
          rows={4}
          maxLength={SCENARIO_MAX_LEN}
          style={{ width: "100%", fontFamily: "inherit", fontSize: 14, padding: 8 }}
          aria-label="Scenario text"
        />
        <div style={{ fontSize: 11, color: "#888", textAlign: "right" }}>
          {scenario.length}/{SCENARIO_MAX_LEN}
        </div>
        <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
          <button onClick={runG} disabled={running || !scenario.trim()}>
            {running ? "Running…" : "Run #G now"}
          </button>
          <button onClick={queueDaily} disabled={!scenario.trim()}>
            Queue for next 05:00
          </button>
        </div>
        {queueResult && (
          <div style={{ marginTop: 8, padding: 6, background: "#eef" }}>
            Queued <code>{queueResult.report_id}</code> for {fmtTs(queueResult.scheduled_for_ts)}.
          </div>
        )}
        {error && (
          <div style={{
            marginTop: 8,
            padding: 6,
            background: "#fee",
            border: "1px solid #f99",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}>
            <span>{error}</span>
            <button onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}
      </section>

      {analysis && (
        <section style={{ border: "1px solid #ddd", padding: 12, borderRadius: 6, marginBottom: 16 }}>
          <h2 style={{ marginTop: 0, fontSize: 16 }}>Latest #G analysis</h2>
          <AnalysisRender a={analysis} />
        </section>
      )}

      <section style={{ border: "1px solid #ddd", padding: 12, borderRadius: 6 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0, fontSize: 16 }}>Daily feed ({feed.length})</h2>
          <button onClick={() => void refreshFeed()} disabled={feedLoading}>
            {feedLoading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
        {feedError && (
          <div style={{
            marginTop: 8,
            padding: 6,
            background: "#fee",
            border: "1px solid #f99",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}>
            <span>{feedError}</span>
            <button onClick={() => void refreshFeed()}>Retry</button>
          </div>
        )}
        {feed.length === 0 && !feedLoading && !feedError && (
          <div style={{ color: "#999", marginTop: 8 }}>No delivered reports yet.</div>
        )}
        {feed.map((r) => <FeedRow key={r.report_id} report={r} />)}
      </section>
    </div>
  );
}

function FeedRow({ report }: { report: ElinsDeliveredReport }) {
  return (
    <details style={{ marginTop: 8, padding: 8, background: "#fafafa", borderRadius: 4 }}>
      <summary style={{ cursor: "pointer" }}>
        <strong>{fmtTs(report.delivered_at)}</strong> — <code>{report.scenario_id ?? "—"}</code>
      </summary>
      <div style={{ marginTop: 8 }}>
        {isSuccessfulAnalysis(report.analysis) ? (
          <AnalysisRender a={report.analysis} />
        ) : (
          <pre style={{ fontSize: 11 }}>{JSON.stringify(report.analysis, null, 2)}</pre>
        )}
      </div>
    </details>
  );
}

function AnalysisRender({ a }: { a: GElinsAnalysis }) {
  // v29 — every accessor is defensive: backend may return partial blocks
  // when an upstream layer is empty (new account, no Dewey neighborhoods).
  const neighborhoods = Array.isArray(a?.neighborhoods) ? a.neighborhoods : [];
  const pressure = a?.qc_summary?.pressure;
  const universal = a?.universal_physics;
  const elinsPhysics = a?.elins_physics;
  return (
    <div style={{ fontSize: 13 }}>
      <div>
        <strong>QC pressure:</strong>{" "}
        <code>{typeof pressure === "number" ? pressure.toFixed(4) : "—"}</code>
        {" · "}
        <strong>Membership id:</strong>{" "}
        <code>{a?.persisted_membership_id || "(none)"}</code>
      </div>
      <div style={{ marginTop: 6 }}>
        <strong>Top neighborhoods:</strong>
        {neighborhoods.length === 0 && <span style={{ color: "#999" }}> (none)</span>}
        <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
          {neighborhoods.map((nb) => (
            <li key={String(nb.neighborhood_id)} style={{ fontSize: 12 }}>
              <code>{nb.neighborhood_id ?? "—"}</code> — {nb.name || "(unnamed)"}{" · "}
              sim={typeof nb.similarity === "number" ? nb.similarity.toFixed(3) : "—"}
              {nb.curvature !== null && nb.curvature !== undefined
                ? `, curvature=${(nb.curvature as number).toFixed(3)}`
                : ""}
            </li>
          ))}
        </ul>
      </div>
      {universal && (
        <details style={{ marginTop: 6 }}>
          <summary style={{ cursor: "pointer", color: "#555" }}>Universal physics block</summary>
          <pre style={{ background: "#fff", padding: 6, fontSize: 11, overflow: "auto", maxHeight: 200 }}>
            {JSON.stringify(universal, null, 2)}
          </pre>
        </details>
      )}
      {elinsPhysics && Object.keys(elinsPhysics).length > 0 && (
        <details style={{ marginTop: 6 }}>
          <summary style={{ cursor: "pointer", color: "#555" }}>ELINS physics_block</summary>
          <pre style={{ background: "#fff", padding: 6, fontSize: 11, overflow: "auto", maxHeight: 200 }}>
            {JSON.stringify(elinsPhysics, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}
