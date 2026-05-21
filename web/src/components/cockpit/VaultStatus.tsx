// components/cockpit/VaultStatus.tsx — Vault Status Indicator panel.
// Reads counts from the continuity snapshot (already loaded by the cockpit)
// to avoid pulling full vault items at the cockpit level.

import { Link } from "react-router-dom";
import type { ContinuitySnapshot } from "../../services/continuity";

export interface VaultStatusProps {
  snapshot: ContinuitySnapshot | null;
}

export default function VaultStatus({ snapshot }: VaultStatusProps) {
  const counts = snapshot?.counts ?? {};
  const entries = Object.entries(counts).sort();

  return (
    <div style={{ fontSize: 13 }}>
      {entries.length === 0 && <div style={{ color: "#999" }}>No counts available.</div>}
      {entries.map(([k, v]) => (
        <div key={k} style={{ display: "flex", justifyContent: "space-between" }}>
          <span style={{ color: "#666" }}>{k}</span>
          <strong>{v}</strong>
        </div>
      ))}
      <Link to="/vault" style={{ display: "inline-block", marginTop: 8 }}>
        Open Vault →
      </Link>
    </div>
  );
}
