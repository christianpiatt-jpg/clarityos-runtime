// components/cockpit/SessionList.tsx — session metadata panel.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchSessions, type SessionMeta } from "../../services/sessions";

function fmtTs(ts: number): string {
  if (!ts) return "—";
  try { return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 19); }
  catch { return String(ts); }
}

export default function SessionList() {
  const [sessions, setSessions] = useState<SessionMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchSessions(50)
      .then((s) => { if (!cancelled) setSessions(s); })
      .catch((e) => { if (!cancelled) setError(e?.message || String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) return <div style={{ color: "#999" }}>Loading sessions…</div>;
  if (error) return <div style={{ color: "#922" }}>{error}</div>;

  return (
    <div style={{ fontSize: 13 }}>
      {sessions.length === 0 && <div style={{ color: "#999" }}>No sessions yet.</div>}
      {sessions.map((s) => (
        <div key={s.session_id} style={{
          display: "grid",
          gridTemplateColumns: "1fr auto auto",
          gap: 8,
          padding: "4px 0",
          borderBottom: "1px dotted #eee",
          fontSize: 12,
        }}>
          <code title={s.session_id}>{s.session_id.slice(0, 18)}…</code>
          <span style={{ color: "#666" }}>idx {s.latest_state_index} ({s.state_count})</span>
          <span style={{ color: "#999" }}>{fmtTs(s.latest_ts)}</span>
        </div>
      ))}
      <Link to="/sessions" style={{ display: "inline-block", marginTop: 8 }}>
        Open full Sessions view →
      </Link>
    </div>
  );
}
