// components/founder/macro/MacroRunDetail.tsx
// Detail view for one macro run: global ELINS reference + regional
// constituents (linked rows). Loads /founder/elins/macro/run/{run_id}.

import { useCallback, useEffect, useState } from "react";
import {
  founderMacroRunDetail,
  type V36MacroRunDetail,
} from "../../../lib/api";

export interface MacroRunDetailProps {
  runId: string | null;
}

export default function MacroRunDetail({ runId }: MacroRunDetailProps) {
  const [run, setRun] = useState<V36MacroRunDetail | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!runId) return;
    setBusy(true); setError(null); setRun(null);
    try {
      const r = await founderMacroRunDetail(runId);
      setRun(r.run);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, [runId]);

  useEffect(() => { void load(); }, [load]);

  if (!runId) {
    return <Empty message="Select a macro run" />;
  }
  if (busy) {
    return <Empty message="Loading…" />;
  }
  if (error) {
    return <div style={errorStyle}>{error}</div>;
  }
  if (!run) {
    return <Empty message="Run not found" />;
  }

  const date = new Date(run.ts * 1000);
  const regional = run.regional_runs || {};
  const regionalKeys = Object.keys(regional);

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <strong style={{ fontSize: 13, fontFamily: "var(--font-mono, monospace)" }}>{run.run_id}</strong>
        <div style={{ fontSize: 11, color: "var(--os-text-tertiary, #585858)" }}>
          {date.toISOString().replace("T", " ").slice(0, 19)}
        </div>
        <div style={{ fontSize: 11, color: "var(--os-text-secondary, #A0A0A0)", marginTop: 4 }}>
          {run.notes || "—"}
        </div>
      </div>

      <Section title="Global run">
        <Row label="run_id">
          <code>{run.global_run_ref?.run_id || "—"}</code>
        </Row>
        <Row label="scenario_id">
          <code>{run.global_run_ref?.scenario_id || "—"}</code>
        </Row>
        {run.global_run && (
          <Row label="summary">
            <code>{(run.global_run.summary as { top_primitive?: string })?.top_primitive || "—"}</code>
          </Row>
        )}
      </Section>

      <Section title={`Regional runs (${regionalKeys.length})`}>
        {regionalKeys.length === 0 ? (
          <div style={{ fontSize: 11, color: "var(--os-text-tertiary, #585858)" }}>None</div>
        ) : (
          regionalKeys.map((region) => {
            const r = regional[region];
            const summary = (r?.summary as Record<string, unknown> | undefined) || {};
            return (
              <div key={region} style={regionalRowStyle}>
                <div>
                  <strong style={{ fontSize: 12 }}>{region}</strong>
                  <span style={{ marginLeft: 8, fontSize: 10, color: "var(--os-text-secondary, #A0A0A0)" }}>
                    top: {String(summary.top_primitive ?? "—")} · signal: {String(summary.signal ?? "—")}
                  </span>
                </div>
                <code style={{ fontSize: 10, color: "var(--os-text-tertiary, #585858)" }}>
                  {String((r as { id?: string } | null)?.id || "—")}
                </code>
              </div>
            );
          })
        )}
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginTop: 10 }}>
      <div style={subHeader}>{title}</div>
      {children}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "2px 0", fontSize: 11 }}>
      <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>{label}</span>
      <span style={{ fontFamily: "var(--font-mono, monospace)", color: "var(--os-text-primary, #fff)" }}>{children}</span>
    </div>
  );
}

function Empty({ message }: { message: string }) {
  return (
    <div style={{ fontSize: 12, color: "var(--os-text-tertiary, #585858)", padding: 8 }}>{message}</div>
  );
}

const subHeader: React.CSSProperties = {
  fontSize: 11, marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.5,
  color: "var(--os-text-secondary, #A0A0A0)", fontWeight: 600,
};

const regionalRowStyle: React.CSSProperties = {
  display: "flex", justifyContent: "space-between",
  padding: "4px 6px", marginBottom: 3,
  border: "1px solid var(--os-line, rgba(255,255,255,0.06))",
  borderRadius: "var(--radius-sm, 4px)",
};

const errorStyle: React.CSSProperties = {
  padding: 6,
  background: "rgba(224, 32, 32, 0.1)",
  border: "1px solid var(--os-boundary, #E02020)",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 12, color: "#fca5a5",
};
