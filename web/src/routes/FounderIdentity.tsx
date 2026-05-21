// web/src/routes/FounderIdentity.tsx
//
// Phase 8C addition. Renders the descriptive identity-coherence layer
// from `/founder/identity`. Inline SVG gauge for the overall score,
// table for the five dimensions, table for the cross-surface
// comparison.
//
// No new libraries.

import { useEffect, useState, useCallback } from "react";
import { Link, useLocation } from "react-router-dom";

interface Dimension {
  score: number | null;
  descriptor: string;
}

interface Profile {
  score: number | null;
  dimensions: Record<string, Dimension>;
  notes: string[];
  n_runs: number;
}

interface CrossSurfaceDelta {
  n_surfaces: number;
  max_score: number | null;
  min_score: number | null;
  spread: number | null;
  interpretation: string;
}

interface SurfacesBlock {
  per_surface: Record<string, Profile>;
  cross_surface_delta: CrossSurfaceDelta | null;
}

interface IdentityResponse {
  profile: Profile | Record<string, never>;
  surfaces: SurfacesBlock | Record<string, never>;
  error?: string;
}

async function api<T>(path: string): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
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
      {" "}<code>/founder/identity</code>; math is in
      {" "}<code>identity_engine.py</code> at repo root.
    </div>
  );
}

function bandLabel(score: number | null): string {
  if (score == null) return "—";
  if (score >= 80) return "high coherence";
  if (score >= 50) return "medium coherence";
  return "low coherence";
}

function CoherenceGauge({ score }: { score: number | null }) {
  if (score == null) {
    return <p style={{ opacity: 0.7 }}>no coherence data yet.</p>;
  }
  const W = 360, H = 120;
  const padL = 24, padR = 24, padT = 16, padB = 32;
  const trackY = padT + (H - padT - padB) / 2;
  const trackH = 18;
  const xMin = padL;
  const xMax = W - padR;
  const xScore = xMin + (xMax - xMin) * (score / 100);
  const x50 = xMin + (xMax - xMin) * 0.5;
  const x80 = xMin + (xMax - xMin) * 0.8;
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="identity coherence gauge"
      style={{ width: "100%", maxWidth: 360, height: "auto" }}
    >
      <rect x={xMin} y={trackY - trackH / 2} width={xMax - xMin} height={trackH}
            fill="currentColor" fillOpacity="0.1" stroke="currentColor"
            strokeOpacity="0.3" />
      <line x1={x50} x2={x50} y1={trackY - trackH} y2={trackY + trackH}
            stroke="currentColor" strokeOpacity="0.4" strokeDasharray="3 3" />
      <line x1={x80} x2={x80} y1={trackY - trackH} y2={trackY + trackH}
            stroke="currentColor" strokeOpacity="0.4" strokeDasharray="3 3" />
      <circle cx={xScore} cy={trackY} r="9" fill="currentColor" />
      <text x={xMin} y={H - 12} fontSize="10" fill="currentColor"
            opacity="0.6">0</text>
      <text x={x50} y={H - 12} fontSize="10" fill="currentColor"
            opacity="0.6" textAnchor="middle">50</text>
      <text x={x80} y={H - 12} fontSize="10" fill="currentColor"
            opacity="0.6" textAnchor="middle">80</text>
      <text x={xMax} y={H - 12} fontSize="10" fill="currentColor"
            opacity="0.6" textAnchor="end">100</text>
      <text x={xScore} y={trackY - 18} fontSize="13" fontWeight="600"
            fill="currentColor" textAnchor="middle">
        {score.toFixed(1)} · {bandLabel(score)}
      </text>
    </svg>
  );
}

function DimensionTable({ dimensions }: { dimensions: Record<string, Dimension> }) {
  const rows = Object.entries(dimensions);
  if (rows.length === 0) {
    return <p style={{ opacity: 0.7 }}>no dimensions reported</p>;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>dimension</th>
          <th>score</th>
          <th>descriptor</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([name, d]) => (
          <tr key={name}>
            <td><code>{name}</code></td>
            <td>{d.score == null ? "—" : d.score.toFixed(1)}</td>
            <td>{d.descriptor}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SurfacesTable({ surfaces }: { surfaces: SurfacesBlock | Record<string, never> }) {
  if (!("per_surface" in surfaces) || !surfaces.per_surface) {
    return <p>no per-surface data</p>;
  }
  const entries = Object.entries(surfaces.per_surface);
  if (entries.length === 0) {
    return <p>no per-surface data</p>;
  }
  return (
    <>
      <table>
        <thead>
          <tr>
            <th>surface</th>
            <th>score</th>
            <th>tone</th>
            <th>timing</th>
            <th>decision</th>
            <th>escalation</th>
            <th>trust</th>
            <th>n_runs</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([name, prof]) => (
            <tr key={name}>
              <td><code>{name}</code></td>
              <td>{prof.score == null ? "—" : prof.score.toFixed(1)}</td>
              <td>{prof.dimensions?.tone?.descriptor ?? "—"}</td>
              <td>{prof.dimensions?.timing?.descriptor ?? "—"}</td>
              <td>{prof.dimensions?.decision_style?.descriptor ?? "—"}</td>
              <td>{prof.dimensions?.escalation_style?.descriptor ?? "—"}</td>
              <td>{prof.dimensions?.trust_posture?.descriptor ?? "—"}</td>
              <td>{prof.n_runs}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {surfaces.cross_surface_delta && (
        <p style={{ marginTop: "0.5rem", fontSize: "0.9rem" }}>
          cross-surface: {surfaces.cross_surface_delta.n_surfaces} surface(s) ·
          spread: {surfaces.cross_surface_delta.spread == null
            ? "—"
            : surfaces.cross_surface_delta.spread.toFixed(1)} ·
          {" "}<strong>{surfaces.cross_surface_delta.interpretation}</strong>
        </p>
      )}
    </>
  );
}

export default function FounderIdentity() {
  const [data, setData] = useState<IdentityResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const r = await api<IdentityResponse>("/founder/identity");
      setData(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (error) {
    return (
      <main className="founder-identity">
        <h1>Founder identity — coherence</h1>
        <p role="alert">error: {error}</p>
        <button onClick={() => void load()}>retry</button>
        <p><Link to="/founder/acceptance">back to surveillance</Link></p>
      </main>
    );
  }
  if (!data) {
    return (
      <main className="founder-identity">
        <h1>Founder identity — coherence</h1>
        <p>loading…</p>
      </main>
    );
  }

  const profile: Profile | Record<string, never> = data.profile ?? {};
  const surfaces: SurfacesBlock | Record<string, never> = data.surfaces ?? {};
  const overallScore = "score" in profile && profile.score != null
    ? profile.score
    : null;

  return (
    <main className="founder-identity">
      <h1>Founder identity — coherence</h1>
      <VerificationBanner />

      <p>
        <Link to="/founder/console">← console</Link>
        {" · "}
        <Link to="/founder/telemetry">telemetry</Link>
        {" · "}
        <Link to="/founder/analytics/quality">run quality</Link>
        {" · "}
        <Link to="/founder/acceptance">surveillance</Link>
      </p>

      {data.error && (
        <p role="alert" style={{ opacity: 0.8 }}>
          identity_engine error: {data.error}
        </p>
      )}

      <section>
        <h2>Coherence (0–100)</h2>
        <CoherenceGauge score={overallScore} />
        {"n_runs" in profile && (
          <p style={{ fontSize: "0.85rem", opacity: 0.7 }}>
            {profile.n_runs} runs ingested · band: <strong>{bandLabel(overallScore)}</strong>
          </p>
        )}
        {"notes" in profile && profile.notes && profile.notes.length > 0 && (
          <ul style={{ marginTop: "0.5rem" }}>
            {profile.notes.map((n: string, i: number) => <li key={i}>{n}</li>)}
          </ul>
        )}
      </section>

      <section>
        <h2>Dimensions</h2>
        {"dimensions" in profile && profile.dimensions ? (
          <DimensionTable dimensions={profile.dimensions} />
        ) : (
          <p>no dimensions</p>
        )}
        <p style={{ fontSize: "0.8rem", opacity: 0.7, marginTop: "0.5rem" }}>
          See <code>tests/acceptance/identity_coherence.md</code> for the
          dimension definitions and the explicit "what this model does NOT
          do" boundary.
        </p>
      </section>

      <section>
        <h2>Cross-surface comparison</h2>
        <SurfacesTable surfaces={surfaces} />
        <p style={{ fontSize: "0.8rem", opacity: 0.7, marginTop: "0.5rem" }}>
          Today's JSONL records do not carry a per-record <code>surface</code>{" "}
          field; all records group under <code>global</code>. The table is
          shaped for a future schema that may carry per-surface records.
        </p>
      </section>
    </main>
  );
}
