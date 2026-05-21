// components/founder/CohortList.tsx — read-only cohort fill stats.
//
// Lightweight panel that reads /public/cohort_status (no founder gate
// needed) to show active/cap/remaining/waitlist counts.

import { useEffect, useState } from "react";
import { publicCohortStatus, type V32CohortStatus } from "../../lib/api";

export default function CohortList() {
  const [status, setStatus] = useState<V32CohortStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    publicCohortStatus()
      .then((s) => { if (active) setStatus(s); })
      .catch((e: unknown) => {
        if (active) setError(e instanceof Error ? e.message : String(e));
      });
    return () => { active = false; };
  }, []);

  return (
    <section style={panelStyle}>
      <h2 style={{ margin: 0, fontSize: 16, marginBottom: 8 }}>Cohort fill</h2>
      {error && (
        <div style={errorStyle}>{error}</div>
      )}
      {status ? (
        <div style={{
          display: "grid",
          gridTemplateColumns: "auto 1fr",
          gap: "4px 16px",
          fontSize: 13,
        }}>
          <span style={mutedStyle}>cohort</span>
          <code>{status.cohort}</code>
          <span style={mutedStyle}>active</span>
          <strong>{status.active_count}</strong>
          <span style={mutedStyle}>cap</span>
          <span>{status.cap ?? "—"}</span>
          <span style={mutedStyle}>remaining</span>
          <span>{status.remaining ?? "—"}</span>
          <span style={mutedStyle}>waitlist</span>
          <span>{status.waitlist_count}</span>
          <span style={mutedStyle}>full?</span>
          <span style={{ color: status.is_full ? "#922" : "#147" }}>
            {status.is_full ? "yes" : "no"}
          </span>
        </div>
      ) : (
        !error && <div style={mutedStyle}>Loading…</div>
      )}
    </section>
  );
}

const panelStyle: React.CSSProperties = {
  border: "1px solid #ddd",
  borderRadius: 6,
  padding: 12,
  background: "#fff",
  marginBottom: 12,
};

const mutedStyle: React.CSSProperties = { color: "#666" };

const errorStyle: React.CSSProperties = {
  padding: 6,
  background: "#fee",
  border: "1px solid #f99",
  borderRadius: 4,
  fontSize: 12,
  marginBottom: 6,
};
