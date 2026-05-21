// components/cockpit/EngineSelector.tsx — engine catalog picker.

import { useEffect, useState } from "react";
import { fetchEngines, type EngineDescriptor, type EngineId } from "../../services/engines";

export interface EngineSelectorProps {
  value: EngineId;
  onChange: (id: EngineId) => void;
}

export default function EngineSelector({ value, onChange }: EngineSelectorProps) {
  const [engines, setEngines] = useState<EngineDescriptor[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchEngines()
      .then((e) => { if (!cancelled) setEngines(e); })
      .catch((e) => { if (!cancelled) setError(e?.message || String(e)); });
    return () => { cancelled = true; };
  }, []);

  if (error) return <div style={{ color: "#922" }}>{error}</div>;

  return (
    <div style={{ fontSize: 13 }}>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {engines.map((e) => (
          <button key={e.id}
            onClick={() => onChange(e.id)}
            title={`${e.description} · POST ${e.route}`}
            style={{
              padding: "4px 10px",
              background: value === e.id ? "#222" : "#eee",
              color: value === e.id ? "#fff" : "#333",
              border: "1px solid #ccc",
              borderRadius: 4,
              cursor: "pointer",
            }}>
            {e.label}
          </button>
        ))}
      </div>
      <p style={{ margin: "6px 0 0", color: "#666" }}>
        Selected: <code>{value}</code>. Engine selection is metadata-only;
        the envelope cascade runs identically for every engine.
      </p>
    </div>
  );
}
