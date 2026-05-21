// web/src/routes/FounderConsole.tsx
//
// Phase 9B addition. Read-only console: four compact widgets
// summarizing run-quality, trust signal, identity coherence, and
// the latest run, plus links to the detailed views.
//
// Consumes existing endpoints in parallel:
//   GET /founder/acceptance/runs/recent?limit=1
//   GET /founder/analytics/quality
//   GET /founder/telemetry
//   GET /founder/identity
//
// (`/founder/console/summary` from Phase 9C is a sibling fan-out
// endpoint; this page chooses the per-endpoint approach so each
// widget renders independently when one source is offline.)
//
// No new libraries.

import { useEffect, useState, useCallback } from "react";
import { Link, useLocation } from "react-router-dom";

interface RecentRun {
  run_id: string;
  pass?: boolean;
  finished_at?: string;
  mode?: string;
}

interface QualityResp {
  summary?: {
    mean?: number | null;
    latest?: number | null;
    trend?: string;
    n_healthy?: number;
    n_warning?: number;
    n_critical_fail?: number;
  };
  n_runs?: number;
}

interface TelemetryResp {
  trust_signal?: {
    signal_score?: number;
    level?: "stable" | "degrading" | "critical";
  };
  drift_score?: number;
}

interface IdentityResp {
  profile?: {
    score?: number | null;
    n_runs?: number;
  };
}

interface RecentResp {
  runs?: RecentRun[];
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
      Verification Mode — <code>?verify=1</code> active. The four
      widgets below are reading live from
      {" "}<code>/founder/acceptance/runs/recent</code>,
      {" "}<code>/founder/analytics/quality</code>,
      {" "}<code>/founder/telemetry</code>, and
      {" "}<code>/founder/identity</code> in parallel.
    </div>
  );
}

interface WidgetProps {
  title: string;
  primary: string;
  secondary?: string;
  hint?: string;
  link: string;
  linkLabel: string;
}

function Widget({ title, primary, secondary, hint, link, linkLabel }: WidgetProps) {
  return (
    <div
      style={{
        padding: "1rem", border: "1px solid currentColor",
        borderColor: "rgba(127,127,127,0.3)",
        flex: "1 1 220px", minWidth: 220, margin: "0.5rem",
      }}
    >
      <div style={{ fontSize: "0.8rem", opacity: 0.7,
                    textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {title}
      </div>
      <div style={{ fontSize: "1.4rem", fontWeight: 600, marginTop: "0.25rem" }}>
        {primary}
      </div>
      {secondary && (
        <div style={{ fontSize: "0.95rem", opacity: 0.85,
                      marginTop: "0.25rem" }}>
          {secondary}
        </div>
      )}
      {hint && (
        <div style={{ fontSize: "0.8rem", opacity: 0.6,
                      marginTop: "0.5rem" }}>
          {hint}
        </div>
      )}
      <div style={{ marginTop: "0.5rem" }}>
        <Link to={link}>{linkLabel} →</Link>
      </div>
    </div>
  );
}

export default function FounderConsole() {
  const [recent, setRecent] = useState<RecentResp | null>(null);
  const [quality, setQuality] = useState<QualityResp | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetryResp | null>(null);
  const [identity, setIdentity] = useState<IdentityResp | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    const out: Record<string, string> = {};
    // Parallel fetches; each failure logged but does not block the others.
    const settled = await Promise.allSettled([
      api<RecentResp>("/founder/acceptance/runs/recent?limit=1"),
      api<QualityResp>("/founder/analytics/quality"),
      api<TelemetryResp>("/founder/telemetry"),
      api<IdentityResp>("/founder/identity"),
    ]);
    if (settled[0].status === "fulfilled") setRecent(settled[0].value);
    else out["recent"] = settled[0].reason instanceof Error
      ? settled[0].reason.message
      : String(settled[0].reason);
    if (settled[1].status === "fulfilled") setQuality(settled[1].value);
    else out["quality"] = settled[1].reason instanceof Error
      ? settled[1].reason.message
      : String(settled[1].reason);
    if (settled[2].status === "fulfilled") setTelemetry(settled[2].value);
    else out["telemetry"] = settled[2].reason instanceof Error
      ? settled[2].reason.message
      : String(settled[2].reason);
    if (settled[3].status === "fulfilled") setIdentity(settled[3].value);
    else out["identity"] = settled[3].reason instanceof Error
      ? settled[3].reason.message
      : String(settled[3].reason);
    setErrors(out);
  }, []);

  useEffect(() => { void load(); }, [load]);

  const runRow = recent?.runs?.[0];
  const lastQual = quality?.summary?.latest;
  const trustLevel = telemetry?.trust_signal?.level;
  const trustScore = telemetry?.trust_signal?.signal_score;
  const driftScore = telemetry?.drift_score;
  const identityScore = identity?.profile?.score;
  const identityRuns = identity?.profile?.n_runs;

  const fmt = (v: number | null | undefined) =>
    typeof v === "number" ? v.toFixed(1) : "—";

  return (
    <main className="founder-console">
      <h1>Founder console</h1>
      <VerificationBanner />

      <p>
        <Link to="/founder/acceptance">surveillance</Link>
        {" · "}
        <Link to="/founder/acceptance/runs">recent runs</Link>
        {" · "}
        <Link to="/founder/acceptance/stability">aggregate stability</Link>
        {" · "}
        <Link to="/founder/acceptance/curve">stability curve</Link>
        {" · "}
        <Link to="/founder/analytics/quality">run quality</Link>
        {" · "}
        <Link to="/founder/telemetry">telemetry</Link>
        {" · "}
        <Link to="/founder/identity">identity</Link>
      </p>

      {Object.keys(errors).length > 0 && (
        <p role="alert" style={{ opacity: 0.8 }}>
          partial load — failed:{" "}
          {Object.entries(errors)
            .map(([k, v]) => `${k} (${v})`)
            .join("; ")}
        </p>
      )}

      <section style={{ display: "flex", flexWrap: "wrap" }}>
        <Widget
          title="Last run"
          primary={runRow ? runRow.run_id : "—"}
          secondary={
            runRow
              ? `${runRow.mode ?? "—"} · ${
                  runRow.pass === true ? "PASS"
                    : runRow.pass === false ? "FAIL"
                    : "—"
                }`
              : "no runs ingested yet"
          }
          hint={runRow?.finished_at ?? undefined}
          link="/founder/acceptance/runs"
          linkLabel="open runs"
        />
        <Widget
          title="Run quality"
          primary={fmt(lastQual)}
          secondary={`trend: ${quality?.summary?.trend ?? "—"}`}
          hint={
            quality?.summary
              ? `${quality.summary.n_healthy ?? 0} healthy · ${
                  quality.summary.n_warning ?? 0
                } warn · ${quality.summary.n_critical_fail ?? 0} critical`
              : undefined
          }
          link="/founder/analytics/quality"
          linkLabel="open quality"
        />
        <Widget
          title="Trust signal"
          primary={trustLevel ?? "—"}
          secondary={
            typeof trustScore === "number"
              ? `${trustScore.toFixed(1)} / 100`
              : "—"
          }
          hint={
            typeof driftScore === "number"
              ? `narrative drift score: ${driftScore.toFixed(3)}`
              : undefined
          }
          link="/founder/telemetry"
          linkLabel="open telemetry"
        />
        <Widget
          title="Identity coherence"
          primary={fmt(identityScore)}
          secondary={
            identityScore == null
              ? "—"
              : identityScore >= 80 ? "high coherence"
              : identityScore >= 50 ? "medium coherence"
              : "low coherence"
          }
          hint={
            typeof identityRuns === "number"
              ? `over ${identityRuns} runs`
              : undefined
          }
          link="/founder/identity"
          linkLabel="open identity"
        />
      </section>

      <section style={{ marginTop: "1.5rem" }}>
        <h2>What to do here</h2>
        <ol>
          <li>
            If <strong>last run</strong> shows FAIL: click through to
            recent runs and read the failing scenario's <code>messages</code>.
          </li>
          <li>
            If <strong>run quality</strong> trend is <code>degrading</code>:
            click through to inspect the latest critical_fail or warning
            entries.
          </li>
          <li>
            If <strong>trust signal</strong> is <code>degrading</code> or
            <code> critical</code>: click through to telemetry and look at
            which component dropped (quality / stability / cadence).
          </li>
          <li>
            If <strong>identity coherence</strong> dropped without a
            corresponding red flag elsewhere: read the dimension table on
            the identity page; usually <code>tone</code> or
            <code> escalation_style</code> moved first.
          </li>
        </ol>
        <p style={{ fontSize: "0.85rem", opacity: 0.7 }}>
          The console does not auto-incident. Read{" "}
          <code>tests/acceptance/operator_playbook_f500.md</code> and{" "}
          <code>tests/acceptance/failure_modes.md</code> for the manual
          escalation procedure.
        </p>
      </section>
    </main>
  );
}
