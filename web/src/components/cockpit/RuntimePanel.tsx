// components/cockpit/RuntimePanel.tsx — wraps the deterministic
// EnvelopeRenderer with refresh + status chrome.

import { useEnvelope } from "../../hooks/useEnvelope";
import EnvelopeRenderer from "../runtime/EnvelopeRenderer";

export default function RuntimePanel() {
  const { envelope, loading, error, refresh } = useEnvelope();

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <span style={{ fontSize: 12, color: "#666" }}>
          {loading ? "Loading…" : envelope ? "Envelope loaded" : "No envelope yet"}
        </span>
        <button onClick={() => void refresh()} disabled={loading}>Refresh</button>
      </div>
      {error && (
        <div style={{ color: "#922", padding: 6, background: "#fee", marginBottom: 8 }}>
          {error}
        </div>
      )}
      <EnvelopeRenderer envelope={envelope} />
    </div>
  );
}
