// web/src/routes/FounderAcceptance.tsx
//
// Founder-only dashboard for acceptance harness reports + P0/P1
// incident surveillance. Reads:
//   GET /founder/acceptance/incidents?since_hours=72
//   GET /founder/acceptance/runs
//   POST /founder/acceptance/incidents/{id}/resolve
//
// The route is wired in web/src/App.tsx under the existing /founder
// authenticated block.

import { useEffect, useState, useCallback } from "react";

interface Incident {
  id: string;
  severity: "P0" | "P1" | "P2" | "P3";
  surface: "web" | "phone" | "desktop" | "backend";
  os?: string | null;
  operator_id?: string | null;
  title: string;
  detail?: string | null;
  created_at: number;
  resolved_at?: number | null;
}

interface IncidentsResponse {
  since_hours: number;
  count: number;
  by_severity: Record<string, number>;
  open_p0_p1: number;
  stability_window_pass: boolean;
  incidents: Incident[];
}

interface ScenarioSummary {
  pass?: boolean;
  duration_ms?: number;
}

interface RunSummary {
  run_id: string;
  pass: boolean;
  finished_at: string;
  scenarios: Record<string, ScenarioSummary>;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...(init ?? {}),
  });
  if (!res.ok) {
    throw new Error(`${path} → ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export default function FounderAcceptance() {
  const [incidents, setIncidents] = useState<IncidentsResponse | null>(null);
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [windowHours, setWindowHours] = useState<number>(72);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [inc, r] = await Promise.all([
        api<IncidentsResponse>(
          `/founder/acceptance/incidents?since_hours=${windowHours}`,
        ),
        api<{ runs: RunSummary[] }>(`/founder/acceptance/runs`),
      ]);
      setIncidents(inc);
      setRuns(r.runs);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [windowHours]);

  useEffect(() => { void load(); }, [load]);

  const resolveOne = async (id: string) => {
    try {
      await api(
        `/founder/acceptance/incidents/${encodeURIComponent(id)}/resolve`,
        { method: "POST" },
      );
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  if (error) {
    return (
      <main className="founder-acceptance">
        <h1>Acceptance surveillance</h1>
        <p role="alert">error: {error}</p>
        <button onClick={() => void load()}>retry</button>
      </main>
    );
  }

  if (!incidents || !runs) {
    return (
      <main className="founder-acceptance">
        <h1>Acceptance surveillance</h1>
        <p>loading…</p>
      </main>
    );
  }

  return (
    <main className="founder-acceptance">
      <h1>Acceptance surveillance</h1>

      {/* Phase 3C — additive nav links to recent-runs and stability views.
          Existing UI below is unchanged. */}
      <nav className="founder-acceptance-nav" aria-label="acceptance views">
        <a href="/founder/acceptance/runs">Recent runs</a>
        {" · "}
        <a href="/founder/acceptance/stability">Stability metrics</a>
      </nav>

      <section>
        <h2>Stability window</h2>
        <p>
          window: last {incidents.since_hours}h ·
          {" "}P0: {incidents.by_severity.P0 ?? 0} ·
          {" "}P1: {incidents.by_severity.P1 ?? 0} ·
          {" "}open P0/P1: {incidents.open_p0_p1}
        </p>
        <p>
          <strong>
            72h stability window: {incidents.stability_window_pass ? "PASS" : "FAIL"}
          </strong>
        </p>
        <label>
          window (hours):
          {" "}
          <input
            type="number"
            min={1}
            max={720}
            value={windowHours}
            onChange={(e) => setWindowHours(Number(e.target.value))}
          />
        </label>
      </section>

      <section>
        <h2>Incidents ({incidents.incidents.length})</h2>
        {incidents.incidents.length === 0 ? (
          <p>no incidents in window</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>severity</th>
                <th>surface</th>
                <th>os</th>
                <th>title</th>
                <th>when</th>
                <th>state</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {incidents.incidents.map((inc) => (
                <tr key={inc.id} data-incident-id={inc.id}>
                  <td>{inc.severity}</td>
                  <td>{inc.surface}</td>
                  <td>{inc.os ?? "—"}</td>
                  <td>{inc.title}</td>
                  <td>{new Date(inc.created_at).toISOString()}</td>
                  <td>{inc.resolved_at ? "resolved" : "open"}</td>
                  <td>
                    {!inc.resolved_at && (
                      <button onClick={() => void resolveOne(inc.id)}>
                        resolve
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <h2>Runs ({runs.length})</h2>
        {runs.length === 0 ? (
          <p>no runs recorded</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>run id</th>
                <th>pass</th>
                <th>finished</th>
                <th>scenarios (pass / total)</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => {
                const total = Object.keys(r.scenarios).length;
                const pass = Object.values(r.scenarios).filter(
                  (s) => s.pass,
                ).length;
                return (
                  <tr key={r.run_id} data-run-id={r.run_id}>
                    <td>{r.run_id}</td>
                    <td>{r.pass ? "PASS" : "FAIL"}</td>
                    <td>{r.finished_at}</td>
                    <td>{pass} / {total}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
