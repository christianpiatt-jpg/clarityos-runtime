// web/src/routes/FounderSurfaces.tsx
//
// Phase 10C addition. Renders the read-only surfaces unification view.
// Reads:
//   GET /founder/surfaces/unified
//
// No new libraries. Inline SVG for the coherence gauge.

import { useEffect, useState, useCallback } from "react";
import { Link, useLocation } from "react-router-dom";

interface SurfaceCounts {
  PHONE: number;
  WEB: number;
  OPERATOR: number;
  unknown: number;
  [key: string]: number;
}

interface SurfacesBlock {
  declared: string[];
  present: string[];
  counts: SurfaceCounts | Record<string, number>;
  last_runs: Record<string, string | null>;
  n_records: number;
}

interface CoherenceComponents {
  timing_delta_score: number;
  trust_delta_score: number;
  identity_delta_score: number;
}

interface CoherenceBlock {
  coherence_score: number;
  components: CoherenceComponents;
  deltas: {
    last_run_hours_per_surface?: Record<string, number | null>;
    trust_per_surface?: Record<string, number | null>;
    identity_per_surface?: Record<string, number | null>;
  };
  interpretation: string;
}

interface UnifiedResponse {
  surfaces: SurfacesBlock | Record<string, never>;
  coherence: CoherenceBlock | Record<string, never>;
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
      {" "}<code>/founder/surfaces/unified</code>; math is in
      {" "}<code>surfaces_unification.py</code> at repo root.
    </div>
  );
}

function CoherenceGauge({ block }: { block: CoherenceBlock | Record<string, never> }) {
  const score =
    "coherence_score" in block && typeof block.coherence_score === "number"
      ? block.coherence_score
      : null;
  const interp = "interpretation" in block ? block.interpretation : "—";
  if (score === null) {
    return <p style={{ opacity: 0.7 }}>no surfaces data yet.</p>;
  }
  const W = 360, H = 120;
  const padL = 24, padR = 24, padT = 16, padB = 32;
  const trackY = padT + (H - padT - padB) / 2;
  const trackH = 18;
  const xMin = padL;
  const xMax = W - padR;
  const xScore = xMin + (xMax - xMin) * (score / 100);
  const fiftyX = xMin + (xMax - xMin) * 0.5;
  const eightyX = xMin + (xMax - xMin) * 0.8;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="surface coherence gauge"
         style={{ width: "100%", maxWidth: 360, height: "auto" }}>
      <rect x={xMin} y={trackY - trackH / 2} width={xMax - xMin} height={trackH}
            fill="currentColor" fillOpacity="0.1" stroke="currentColor"
            strokeOpacity="0.3" />
      <line x1={fiftyX} x2={fiftyX} y1={trackY - trackH} y2={trackY + trackH}
            stroke="currentColor" strokeOpacity="0.4" strokeDasharray="3 3" />
      <line x1={eightyX} x2={eightyX} y1={trackY - trackH} y2={trackY + trackH}
            stroke="currentColor" strokeOpacity="0.4" strokeDasharray="3 3" />
      <circle cx={xScore} cy={trackY} r="9" fill="currentColor" />
      <text x={xMin} y={H - 12} fontSize="10" fill="currentColor" opacity="0.6">0</text>
      <text x={fiftyX} y={H - 12} fontSize="10" fill="currentColor"
            opacity="0.6" textAnchor="middle">50</text>
      <text x={eightyX} y={H - 12} fontSize="10" fill="currentColor"
            opacity="0.6" textAnchor="middle">80</text>
      <text x={xMax} y={H - 12} fontSize="10" fill="currentColor"
            opacity="0.6" textAnchor="end">100</text>
      <text x={xScore} y={trackY - 18} fontSize="13" fontWeight="600"
            fill="currentColor" textAnchor="middle">
        {score} · {interp}
      </text>
    </svg>
  );
}

function SurfacesTable({ surfaces }: { surfaces: SurfacesBlock | Record<string, never> }) {
  if (!("declared" in surfaces) || !surfaces.declared) {
    return <p style={{ opacity: 0.7 }}>no surface records yet.</p>;
  }
  const declared = surfaces.declared;
  const counts = surfaces.counts || {};
  const lastRuns = surfaces.last_runs || {};
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr>
          <th style={{ textAlign: "left" }}>surface</th>
          <th style={{ textAlign: "right" }}>count</th>
          <th style={{ textAlign: "left" }}>last run</th>
          <th style={{ textAlign: "left" }}>present</th>
        </tr>
      </thead>
      <tbody>
        {declared.map((s) => (
          <tr key={s}>
            <td><code>{s}</code></td>
            <td style={{ textAlign: "right" }}>{counts[s] ?? 0}</td>
            <td>{lastRuns[s] ?? "—"}</td>
            <td>{(surfaces.present || []).includes(s) ? "✓" : "—"}</td>
          </tr>
        ))}
        {("unknown" in counts) && counts.unknown > 0 && (
          <tr>
            <td><code>unknown</code></td>
            <td style={{ textAlign: "right" }}>{counts.unknown}</td>
            <td>—</td>
            <td>—</td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

function ComponentDetails({ block }: { block: CoherenceBlock | Record<string, never> }) {
  if (!("components" in block) || !block.components) return null;
  const c = block.components;
  return (
    <table style={{ marginTop: "0.75rem", width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr>
          <th style={{ textAlign: "left" }}>component</th>
          <th style={{ textAlign: "right" }}>score (0–1)</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>timing_delta_score</td>
          <td style={{ textAlign: "right" }}>{c.timing_delta_score?.toFixed?.(3) ?? "—"}</td>
        </tr>
        <tr>
          <td>trust_delta_score</td>
          <td style={{ textAlign: "right" }}>{c.trust_delta_score?.toFixed?.(3) ?? "—"}</td>
        </tr>
        <tr>
          <td>identity_delta_score</td>
          <td style={{ textAlign: "right" }}>{c.identity_delta_score?.toFixed?.(3) ?? "—"}</td>
        </tr>
      </tbody>
    </table>
  );
}

export default function FounderSurfaces() {
  const [data, setData] = useState<UnifiedResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const j = await api<UnifiedResponse>("/founder/surfaces/unified");
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
      <h1>Surfaces — Unified View</h1>
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
            <h2>Coherence</h2>
            <CoherenceGauge block={data.coherence} />
            <ComponentDetails block={data.coherence} />
            {"interpretation" in data.coherence && (
              <p style={{ opacity: 0.75, marginTop: "0.75rem" }}>
                <em>{data.coherence.interpretation}</em>
              </p>
            )}
          </section>
          <section style={{ marginTop: "2rem" }}>
            <h2>Surfaces</h2>
            <SurfacesTable surfaces={data.surfaces} />
            {"n_records" in data.surfaces && (
              <p style={{ opacity: 0.7, marginTop: "0.5rem" }}>
                {data.surfaces.n_records} acceptance record(s) examined.
              </p>
            )}
          </section>
          <section style={{ marginTop: "1.5rem", opacity: 0.75 }}>
            <h2>Interpretation</h2>
            <p>
              This view is read-only. It does not sync, merge, or write between
              surfaces. ≥ 80 = unified; 50–79 = aligned with deltas worth review;
              &lt; 50 = partial divergence.
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
