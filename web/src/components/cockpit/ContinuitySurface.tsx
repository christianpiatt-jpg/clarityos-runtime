// components/cockpit/ContinuitySurface.tsx — cross-session metadata view
// + mesh device list. Pure metadata; no event content.

import type { ContinuitySnapshot } from "../../services/continuity";
import type { MeshState } from "../../services/mesh";

function fmtTs(ts: number | null | undefined): string {
  if (!ts) return "—";
  try { return new Date(Number(ts) * 1000).toISOString().replace("T", " ").slice(0, 19); }
  catch { return String(ts); }
}

export interface ContinuitySurfaceProps {
  snapshot: ContinuitySnapshot | null;
  mesh: MeshState | null;
}

export default function ContinuitySurface({ snapshot, mesh }: ContinuitySurfaceProps) {
  if (!snapshot) return <div style={{ color: "#999" }}>—</div>;

  const lts = snapshot.last_updated_ts ?? {};
  const flags = snapshot.coherence_flags ?? {};
  const devices = mesh?.devices ?? {};

  return (
    <div style={{ fontSize: 13 }}>
      <div style={{ marginBottom: 6 }}>
        <strong>Layer freshness</strong> (per-layer last_updated_ts):
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "2px 8px" }}>
        {Object.entries(lts).sort().map(([k, v]) => (
          <span key={k} style={{ display: "contents", fontSize: 12 }}>
            <span style={{ color: "#666" }}>{k}</span>
            <span style={{ fontFamily: "monospace" }}>{fmtTs(v as number)}</span>
          </span>
        ))}
      </div>

      <div style={{ marginTop: 10, marginBottom: 4 }}><strong>Coherence flags:</strong></div>
      {Object.entries(flags).sort().map(([k, v]) => (
        <span key={k} style={{
          display: "inline-block",
          margin: "2px 4px 0 0",
          padding: "1px 6px",
          background: v ? "#e6f5ec" : "#fde2e2",
          color: v ? "#147" : "#922",
          borderRadius: 3,
          fontSize: 11,
        }}>
          {k}: {v ? "ok" : "fail"}
        </span>
      ))}

      <div style={{ marginTop: 12 }}><strong>Mesh devices:</strong> {Object.keys(devices).length}</div>
      {Object.entries(devices).map(([id, d]) => (
        <div key={id} style={{ fontSize: 11, color: "#555", marginTop: 2 }}>
          <code>{id}</code> — last_seen {fmtTs(d.last_seen_ts)}
        </div>
      ))}
    </div>
  );
}
