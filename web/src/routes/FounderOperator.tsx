// web/src/routes/FounderOperator.tsx
//
// Phase 11C addition. Renders the read-only operator-mode posture
// view. Reads:
//   GET /founder/operator/state
//
// No new libraries. Inline SVG for the 5-state posture gauge.

import { useEffect, useState, useCallback } from "react";
import { Link, useLocation } from "react-router-dom";

type Posture = "steady" | "cautious" | "corrective" | "degraded" | "offline";

interface OperatorVotes {
  telemetry: Posture;
  identity: Posture;
  quality: Posture;
}

interface OperatorState {
  last_run: string | null;
  last_quality: Record<string, unknown> | null;
  last_trust: Record<string, unknown> | null;
  last_identity: Record<string, unknown> | null;
  stale: boolean;
  posture: Posture;
  reasons: string[];
  votes: OperatorVotes;
}

interface OperatorResponse {
  state: OperatorState;
  errors?: Record<string, string>;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...(init ?? {}),
  });
  if (!res.ok) throw new Error(`${path} → ${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

function VerificationBanner() {
  const loc = useLocation();
  if (new URLSearchParams(loc.search).get("verify") !== "1") return null;
  return (
    <div
      role="status"
      className="acceptance-verify-banner"
      style={{
        padding: "0.5rem 0.75rem", marginBottom: "1rem",
        border: "1px solid currentColor", fontSize: "0.85rem",
      }}
    >
      Verification Mode — <code>?verify=1</code> active. Reading
      {" "}<code>/founder/operator/state</code>; math is in
      {" "}<code>operator_mode.py</code> at repo root.
    </div>
  );
}

const POSTURES: Posture[] = ["steady", "cautious", "corrective", "degraded", "offline"];

function PostureGauge({ posture }: { posture: Posture }) {
  const idx = POSTURES.indexOf(posture);
  const safeIdx = idx < 0 ? POSTURES.length - 1 : idx;
  const W = 480, H = 110;
  const padL = 24, padR = 24, padT = 16, padB = 36;
  const yMid = padT + (H - padT - padB) / 2;
  const cellW = (W - padL - padR) / POSTURES.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="operator posture gauge"
         style={{ width: "100%", maxWidth: 480, height: "auto" }}>
      {POSTURES.map((p, i) => {
        const x = padL + i * cellW;
        const selected = i === safeIdx;
        return (
          <g key={p}>
            <rect x={x} y={yMid - 14} width={cellW - 4} height={28}
                  fill="currentColor"
                  fillOpacity={selected ? 0.85 : 0.08}
                  stroke="currentColor"
                  strokeOpacity={selected ? 1 : 0.3} />
            <text x={x + (cellW - 4) / 2} y={yMid + 4}
                  fontSize="11"
                  fontWeight={selected ? "700" : "400"}
                  fill={selected ? "white" : "currentColor"}
                  textAnchor="middle">
              {p}
            </text>
          </g>
        );
      })}
      <text x={padL} y={H - 10} fontSize="10" fill="currentColor"
            opacity="0.6">nominal</text>
      <text x={W - padR} y={H - 10} fontSize="10" fill="currentColor"
            opacity="0.6" textAnchor="end">degraded → offline</text>
    </svg>
  );
}

function ReasonsList({ reasons }: { reasons: string[] }) {
  if (!reasons || reasons.length === 0) {
    return <p style={{ opacity: 0.7 }}>no reasons recorded.</p>;
  }
  return (
    <ul style={{ paddingLeft: "1.25rem" }}>
      {reasons.map((r, i) => (
        <li key={i} style={{ marginBottom: "0.25rem", fontSize: "0.9rem" }}>
          <code style={{ fontSize: "0.85rem" }}>{r}</code>
        </li>
      ))}
    </ul>
  );
}

function LastRunSummary({ s }: { s: OperatorState }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <tbody>
        <tr>
          <td style={{ width: "30%" }}>last_run</td>
          <td><code>{s.last_run ?? "—"}</code></td>
        </tr>
        <tr>
          <td>stale</td>
          <td>{s.stale ? "yes (≥ 24h since last record)" : "no"}</td>
        </tr>
        <tr>
          <td>last_quality</td>
          <td><code style={{ fontSize: "0.8rem" }}>
            {s.last_quality ? JSON.stringify(s.last_quality) : "—"}
          </code></td>
        </tr>
        <tr>
          <td>last_trust</td>
          <td><code style={{ fontSize: "0.8rem" }}>
            {s.last_trust ? JSON.stringify(s.last_trust) : "—"}
          </code></td>
        </tr>
        <tr>
          <td>last_identity</td>
          <td><code style={{ fontSize: "0.8rem" }}>
            {s.last_identity ? JSON.stringify(s.last_identity) : "—"}
          </code></td>
        </tr>
      </tbody>
    </table>
  );
}

function InterpretationTable() {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
      <thead>
        <tr>
          <th style={{ textAlign: "left" }}>posture</th>
          <th style={{ textAlign: "left" }}>operator may do</th>
          <th style={{ textAlign: "left" }}>operator should not do</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><code>steady</code></td>
          <td>normal cadence; cautious scope expansion</td>
          <td>skip a scheduled run because "things look fine"</td>
        </tr>
        <tr>
          <td><code>cautious</code></td>
          <td>read more carefully; hold scope; extra acceptance pass</td>
          <td>expand scope; sign off on a new feature</td>
        </tr>
        <tr>
          <td><code>corrective</code></td>
          <td>run the known fix; verify quality recovers</td>
          <td>ignore the fix; run new scenarios</td>
        </tr>
        <tr>
          <td><code>degraded</code></td>
          <td>pause new work; investigate root cause; runbook</td>
          <td>ship anything; mark anything green</td>
        </tr>
        <tr>
          <td><code>offline</code></td>
          <td>restart ingest; verify harness; nothing else</td>
          <td>read posture from cached records</td>
        </tr>
      </tbody>
    </table>
  );
}

export default function FounderOperator() {
  const [data, setData] = useState<OperatorResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const j = await api<OperatorResponse>("/founder/operator/state");
      setData(j);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <main style={{ padding: "1.5rem", maxWidth: 960, margin: "0 auto" }}>
      <p style={{ marginBottom: "1rem" }}>
        <Link to="/founder">← founder console</Link>
      </p>
      <h1>Operator Mode — Posture</h1>
      <VerificationBanner />
      {loading && <p>loading…</p>}
      {err && (
        <p role="alert" style={{ color: "crimson" }}>
          error: {err}
        </p>
      )}
      {data && data.state && (
        <>
          <section style={{ marginTop: "1.5rem" }}>
            <h2>Posture</h2>
            <PostureGauge posture={data.state.posture} />
            <p style={{ marginTop: "0.5rem" }}>
              Current posture: <strong>{data.state.posture}</strong>
              {data.state.stale && (
                <span style={{ opacity: 0.7 }}> (stale signal — decayed to offline)</span>
              )}
            </p>
          </section>

          <section style={{ marginTop: "1.5rem" }}>
            <h2>Reasons</h2>
            <ReasonsList reasons={data.state.reasons} />
          </section>

          <section style={{ marginTop: "1.5rem" }}>
            <h2>Last-run summary</h2>
            <LastRunSummary s={data.state} />
          </section>

          <section style={{ marginTop: "1.5rem" }}>
            <h2>Interpretation</h2>
            <InterpretationTable />
            <p style={{ opacity: 0.7, marginTop: "0.5rem" }}>
              Operator Mode is descriptive. It does not enforce, gate, or
              automate. Movement discipline is the operator's responsibility.
            </p>
          </section>

          {data.errors && (
            <section style={{ marginTop: "1rem", color: "crimson" }}>
              <h3>Errors</h3>
              <pre style={{ fontSize: "0.85rem" }}>
                {JSON.stringify(data.errors, null, 2)}
              </pre>
            </section>
          )}
        </>
      )}
    </main>
  );
}
