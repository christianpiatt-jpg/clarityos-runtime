// v72 / Unit 81 — Roll-up route.
//
// Three cards (24h / 7d / 30d). Each card carries avg EL / avg INS /
// avg TSI, a reasoning-mode pie chart, and a record count.

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  getElInsRollup,
  type ElInsRollupResult,
  type ElInsRollupWindow,
} from "../lib/api";

const WINDOWS: readonly ElInsRollupWindow[] = ["24h", "7d", "30d"] as const;

export default function OperatorElinsRollup() {
  const [data, setData] = useState<Record<ElInsRollupWindow, ElInsRollupResult | null>>({
    "24h": null, "7d": null, "30d": null,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const results = await Promise.all(WINDOWS.map((w) => getElInsRollup(w)));
      const next: Record<ElInsRollupWindow, ElInsRollupResult | null> = {
        "24h": null, "7d": null, "30d": null,
      };
      WINDOWS.forEach((w, i) => { next[w] = results[i]; });
      setData(next);
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <div>
      <div className="panel">
        <h1>EL/INS ROLL-UP</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Aggregate EL/INS + reasoning-mode statistics over three
          rolling windows. Deterministic — no LLM. Records without a
          TSI are still counted toward distribution but excluded from
          the TSI average.
        </p>
        <div className="row" style={{ marginTop: 8, gap: 8 }}>
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={() => void load()}
            disabled={loading}
            data-testid="el-ins-rollup-refresh"
          >
            REFRESH
          </button>
        </div>
        {error ? (
          <div className="banner err" style={{ marginTop: 8 }} data-testid="el-ins-rollup-error">
            {error}
          </div>
        ) : null}
      </div>

      <div
        className="panel"
        data-testid="el-ins-rollup-cards"
        style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}
      >
        {WINDOWS.map((w) => (
          <RollupCard key={w} window={w} result={data[w]} loading={loading} />
        ))}
      </div>
    </div>
  );
}

function RollupCard({
  window: window_,
  result,
  loading,
}: {
  window: ElInsRollupWindow;
  result: ElInsRollupResult | null;
  loading: boolean;
}) {
  return (
    <div
      data-testid={`el-ins-rollup-card-${window_}`}
      style={{
        background: "var(--os-bg-elev, rgba(255,255,255,0.04))",
        padding: 12,
      }}
    >
      <h3 style={{ margin: 0, fontSize: 14, letterSpacing: "0.5px" }}>
        Last {window_}
      </h3>
      {loading && !result ? (
        <div className="muted" style={{ marginTop: 8 }}>Loading…</div>
      ) : !result ? (
        <div className="muted" style={{ marginTop: 8 }}>—</div>
      ) : (
        <>
          <div className="kv" style={{ marginTop: 8 }}>
            <div className="k">records</div>
            <div className="v">{result.record_count}</div>
            <div className="k">avg EL</div>
            <div className="v">{result.avg_el.toFixed(2)}</div>
            <div className="k">avg INS</div>
            <div className="v">{result.avg_ins.toFixed(2)}</div>
            <div className="k">avg TSI</div>
            <div className="v">{result.avg_tsi}/100</div>
          </div>
          <h4 style={{ margin: "12px 0 4px", fontSize: 11, letterSpacing: "0.5px", color: "var(--os-text-muted, #888)" }}>
            REASONING MODES
          </h4>
          <ReasoningModePie distribution={result.reasoning_mode_distribution} />
        </>
      )}
    </div>
  );
}

function ReasoningModePie({ distribution }: { distribution: Record<string, number> }) {
  const total = Object.values(distribution).reduce((acc, v) => acc + v, 0);
  if (total === 0) {
    return <div className="muted" style={{ fontSize: 11 }}>no records</div>;
  }
  // Sort by count desc.
  const entries = Object.entries(distribution).sort((a, b) => b[1] - a[1]);
  const palette: Record<string, string> = {
    grounding:              "var(--os-err, #ef4444)",
    analysis:               "var(--os-warn, #f59e0b)",
    structured_reflection:  "var(--os-accent, #00f0ff)",
    stabilization:          "var(--os-text-muted, #888)",
    extended_reasoning:     "var(--os-ok, #10b981)",
    normal:                 "var(--os-text, #ccc)",
  };
  const size = 120;
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 4;
  let angle = -Math.PI / 2;
  const paths: React.ReactElement[] = [];
  for (const [mode, value] of entries) {
    if (value <= 0) continue;
    const sweep = (value / total) * Math.PI * 2;
    const x1 = cx + r * Math.cos(angle);
    const y1 = cy + r * Math.sin(angle);
    angle += sweep;
    const x2 = cx + r * Math.cos(angle);
    const y2 = cy + r * Math.sin(angle);
    const largeArc = sweep > Math.PI ? 1 : 0;
    paths.push(
      <path
        key={mode}
        d={`M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} Z`}
        fill={palette[mode] || "var(--os-text, #ccc)"}
      />,
    );
  }
  return (
    <div>
      <svg width={size} height={size} role="img" aria-label="reasoning mode distribution">
        {paths}
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.08)" />
      </svg>
      <ul style={{ listStyle: "none", padding: 0, margin: "4px 0 0", fontSize: 11 }}>
        {entries.map(([mode, value]) => (
          <li key={mode} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
            <span style={{
              display: "inline-block", width: 8, height: 8,
              background: palette[mode] || "var(--os-text, #ccc)",
            }} />
            <span style={{ fontFamily: "var(--font-mono)" }}>{mode}: {value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function formatError(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.body === "object" && e.body && "detail" in (e.body as Record<string, unknown>)) {
      const d = (e.body as Record<string, unknown>).detail;
      if (typeof d === "string") return d;
    }
    return `${e.code}: ${e.message}`;
  }
  if (e instanceof Error) return e.message;
  return String(e);
}
