// components/cockpit/WhatsNewPanel.tsx — "What's new in v28/v29" surface.
// Reads /v29/whats_new and renders the static entry list.

import { useEffect, useState } from "react";
import { v29WhatsNew, type V29WhatsNew } from "../../lib/api";

export default function WhatsNewPanel() {
  const [data, setData] = useState<V29WhatsNew | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    v29WhatsNew()
      .then((d) => { if (active) setData(d); })
      .catch((e: unknown) => {
        if (active) setError(e instanceof Error ? e.message : String(e));
      });
    return () => { active = false; };
  }, []);

  if (error) {
    return <div style={{ color: "#922", fontSize: 12 }}>What's new: {error}</div>;
  }
  if (!data) {
    return <div style={{ color: "#999", fontSize: 12 }}>Loading what's new…</div>;
  }
  if (!data.enabled) return null;

  return (
    <div>
      {data.entries.map((entry) => (
        <details key={entry.id} style={{
          background: "#fff",
          border: "1px solid #ddd",
          borderRadius: 4,
          padding: "6px 10px",
          marginBottom: 8,
        }}>
          <summary style={{ cursor: "pointer", fontSize: 13 }}>
            <strong>{entry.title}</strong>
            <span style={{ color: "#888", fontSize: 11, marginLeft: 8 }}>
              {entry.released_at}
            </span>
          </summary>
          <ul style={{ margin: "6px 0 0 18px", padding: 0, fontSize: 12 }}>
            {entry.highlights.map((h, i) => <li key={i}>{h}</li>)}
          </ul>
        </details>
      ))}
    </div>
  );
}
