// web/src/routes/FounderLaunch.tsx
//
// Phase 12C addition. Renders the read-only launch readiness view.
// Reads:
//   GET /founder/launch/readiness
//
// No new libraries. Inline SVG for the readiness gauge.

import { useEffect, useState, useCallback } from "react";
import { Link, useLocation } from "react-router-dom";

type Band = "green" | "yellow" | "red";

interface ReadinessDimensions {
  stability: number;
  trust: number;
  identity: number;
  surfaces: number;
  operator: number;
}

interface ReadinessBlock {
  readiness_score: number;
  band: Band;
  dimensions: ReadinessDimensions;
  weights: ReadinessDimensions;
  notes: string[];
}

interface ReadinessPayload {
  readiness: ReadinessBlock;
  last_run: string | null;
}

interface LaunchResponse {
  readiness: ReadinessPayload;
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
      {" "}<code>/founder/launch/readiness</code>; math is in
      {" "}<code>launch_readiness.py</code> at repo root, composed from
      {" "}<code>stability_math</code>, <code>run_quality</code>,
      {" "}<code>trust_center_math</code>, <code>identity_engine</code>,
      {" "}<code>surfaces_unification</code>, <code>operator_mode</code>.
    </div>
  );
}

function ReadinessGauge({ block }: { block: ReadinessBlock | null }) {
  if (!block) {
    return <p style={{ opacity: 0.7 }}>no readiness payload yet.</p>;
  }
  const score = block.readiness_score;
  const band = block.band;
  const W = 360, H = 120;
  const padL = 24, padR = 24, padT = 16, padB = 32;
  const trackY = padT + (H - padT - padB) / 2;
  const trackH = 18;
  const xMin = padL;
  const xMax = W - padR;
  const xScore = xMin + (xMax - xMin) * (score / 100);
  const yellowX = xMin + (xMax - xMin) * 0.5;
  const greenX = xMin + (xMax - xMin) * 0.8;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="launch readiness gauge"
         style={{ width: "100%", maxWidth: 360, height: "auto" }}>
      <rect x={xMin} y={trackY - trackH / 2} width={xMax - xMin} height={trackH}
            fill="currentColor" fillOpacity="0.1" stroke="currentColor"
            strokeOpacity="0.3" />
      <line x1={yellowX} x2={yellowX} y1={trackY - trackH} y2={trackY + trackH}
            stroke="currentColor" strokeOpacity="0.4" strokeDasharray="3 3" />
      <line x1={greenX} x2={greenX} y1={trackY - trackH} y2={trackY + trackH}
            stroke="currentColor" strokeOpacity="0.4" strokeDasharray="3 3" />
      <circle cx={xScore} cy={trackY} r="9" fill="currentColor" />
      <text x={xMin} y={H - 12} fontSize="10" fill="currentColor" opacity="0.6">0</text>
      <text x={yellowX} y={H - 12} fontSize="10" fill="currentColor"
            opacity="0.6" textAnchor="middle">50</text>
      <text x={greenX} y={H - 12} fontSize="10" fill="currentColor"
            opacity="0.6" textAnchor="middle">80</text>
      <text x={xMax} y={H - 12} fontSize="10" fill="currentColor"
            opacity="0.6" textAnchor="end">100</text>
      <text x={xScore} y={trackY - 18} fontSize="13" fontWeight="600"
            fill="currentColor" textAnchor="middle">
        {score} · {band}
      </text>
    </svg>
  );
}

function DimensionTable({ block }: { block: ReadinessBlock | null }) {
  if (!block) return null;
  const dims = block.dimensions;
  const ws = block.weights;
  const order: (keyof ReadinessDimensions)[] = [
    "stability", "trust", "identity", "surfaces", "operator",
  ];
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr>
          <th style={{ textAlign: "left" }}>dimension</th>
          <th style={{ textAlign: "right" }}>score (0–1)</th>
          <th style={{ textAlign: "right" }}>weight</th>
          <th style={{ textAlign: "right" }}>contribution</th>
        </tr>
      </thead>
      <tbody>
        {order.map((k) => {
          const s = dims[k];
          const w = ws[k];
          const c = (typeof s === "number" && typeof w === "number") ? s * w : 0;
          return (
            <tr key={k}>
              <td><code>{k}</code></td>
              <td style={{ textAlign: "right" }}>{s?.toFixed?.(3) ?? "—"}</td>
              <td style={{ textAlign: "right" }}>{w?.toFixed?.(2) ?? "—"}</td>
              <td style={{ textAlign: "right" }}>{c.toFixed(3)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function NotesList({ notes }: { notes: string[] }) {
  if (!notes || notes.length === 0) {
    return <p style={{ opacity: 0.7 }}>no notes — all dimensions nominal or unobservable.</p>;
  }
  return (
    <ul style={{ paddingLeft: "1.25rem" }}>
      {notes.map((n, i) => (
        <li key={i} style={{ marginBottom: "0.25rem", fontSize: "0.9rem" }}>
          <code style={{ fontSize: "0.85rem" }}>{n}</code>
        </li>
      ))}
    </ul>
  );
}

export default function FounderLaunch() {
  const [data, setData] = useState<LaunchResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const j = await api<LaunchResponse>("/founder/launch/readiness");
      setData(j);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const block: ReadinessBlock | null =
    data && data.readiness && data.readiness.readiness ? data.readiness.readiness : null;
  const lastRun = data?.readiness?.last_run ?? null;

  return (
    <main style={{ padding: "1.5rem", maxWidth: 960, margin: "0 auto" }}>
      <p style={{ marginBottom: "1rem" }}>
        <Link to="/founder">← founder console</Link>
      </p>
      <h1>Launch Readiness</h1>
      <VerificationBanner />
      {loading && <p>loading…</p>}
      {err && (
        <p role="alert" style={{ color: "crimson" }}>
          error: {err}
        </p>
      )}
      {data && (
        <>
          <section style={{ marginTop: "1.5rem" }}>
            <h2>Readiness</h2>
            <ReadinessGauge block={block} />
            <p style={{ marginTop: "0.5rem", opacity: 0.85 }}>
              last_run: <code>{lastRun ?? "—"}</code>
            </p>
          </section>

          <section style={{ marginTop: "1.5rem" }}>
            <h2>Dimensions</h2>
            <DimensionTable block={block} />
          </section>

          <section style={{ marginTop: "1.5rem" }}>
            <h2>Notes</h2>
            <NotesList notes={block?.notes ?? []} />
          </section>

          <section style={{ marginTop: "1.5rem", opacity: 0.75 }}>
            <h2>Interpretation</h2>
            <p>
              Bands: <strong>green ≥ 80</strong>, <strong>yellow 50–79</strong>,
              {" "}<strong>red &lt; 50</strong>. The score is descriptive only —
              this view does not gate launches, schedule them, predict them, or
              notify anyone. The operator decides whether to act on the read.
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
