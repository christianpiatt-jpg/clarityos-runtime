// routes/OperatorProfile.tsx — v39 founder operator detail.
// Reads /founder/operator/{user_id}/state and renders the timeline +
// inferred preferences. The route is mounted under RequireAuth; the
// API enforces the founder cohort gate.

import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { founderOperatorState, type V39OperatorState } from "../lib/api";
import OperatorTimeline from "../components/founder/operator/OperatorTimeline";
import OperatorProfilePanel from "../components/founder/operator/OperatorProfilePanel";

export default function OperatorProfile() {
  const { user_id = "" } = useParams<{ user_id?: string }>();
  const [state, setState] = useState<V39OperatorState | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!user_id) return;
    setBusy(true); setError(null); setState(null);
    try {
      const r = await founderOperatorState(user_id);
      setState(r.state);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, [user_id]);

  useEffect(() => { void load(); }, [load]);

  return (
    <div style={{ maxWidth: 1080, margin: "0 auto" }}>
      <header style={{ marginBottom: 12 }}>
        <h1 style={{ margin: 0 }}>Operator profile</h1>
        <div style={{ marginTop: 4, fontSize: 13, color: "var(--os-text-secondary, #A0A0A0)" }}>
          <code>{user_id}</code>
          {" · "}
          <Link to="/founder" style={{ color: "var(--os-focus, #00F0FF)" }}>← Founder console</Link>
        </div>
      </header>

      {error && (
        <div style={errorStyle}>{error}</div>
      )}

      {busy && !state && (
        <div style={{ fontSize: 13, color: "var(--os-text-tertiary, #585858)" }}>Loading operator state…</div>
      )}

      {state && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 12, alignItems: "start" }}>
          <OperatorProfilePanel state={state} />
          <OperatorTimeline state={state} />
        </div>
      )}
    </div>
  );
}

const errorStyle: React.CSSProperties = {
  padding: 8, marginBottom: 12,
  background: "rgba(224, 32, 32, 0.1)",
  border: "1px solid var(--os-boundary, #E02020)",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 12, color: "#fca5a5",
};
