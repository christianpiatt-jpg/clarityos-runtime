// Sessions = local conversation threads stored in localStorage under
// `clarityos.threads`. Same key the phone uses, so future sync would
// land them here as well. Read-only viewer for now.

import { useState } from "react";
import { listThreads, readThread, type LocalThread } from "../lib/continuity";

export default function Sessions() {
  const [threads] = useState<LocalThread[]>(() => listThreads());
  const [active, setActive] = useState<LocalThread | null>(null);

  return (
    <div>
      <div className="panel">
        <h1>SESSIONS</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Local conversation threads. Stored on this device only. Nothing is synced.
        </p>
      </div>

      {threads.length === 0 ? (
        <div className="empty">
          No threads yet on this browser. Threads created in the phone app stay on the phone —
          web threads will appear here once a chat surface lands on web.
        </div>
      ) : (
        <div className="panel-grid">
          <div>
            <h2 style={{ marginBottom: 12 }}>THREADS  ·  {threads.length}</h2>
            {threads.map((t) => (
              <button
                key={t.id}
                className="list-item"
                style={{
                  width: "100%",
                  textAlign: "left",
                  background: active?.id === t.id ? "var(--os-elevated)" : undefined,
                  borderColor: active?.id === t.id ? "var(--os-focus)" : undefined,
                  cursor: "pointer",
                }}
                onClick={() => setActive(readThread(t.id))}
              >
                <div className="title">{t.title || "(untitled)"}</div>
                <div className="meta">
                  {new Date(t.created).toLocaleString()}  ·  {t.log?.length ?? 0} msgs
                </div>
              </button>
            ))}
          </div>

          <div>
            <h2 style={{ marginBottom: 12 }}>DETAIL</h2>
            {!active ? (
              <div className="empty">Pick a thread to view its log.</div>
            ) : (
              <div className="panel" style={{ marginBottom: 0 }}>
                <div className="row row-between" style={{ marginBottom: 12 }}>
                  <span className="mono">{active.title || "(untitled)"}</span>
                  <span className="dim mono" style={{ fontSize: "0.75rem" }}>
                    {new Date(active.created).toLocaleString()}
                  </span>
                </div>
                {(active.log || []).map((line, i) => (
                  <div key={i} style={{ paddingBottom: 8, borderBottom: "1px solid var(--os-line)", marginBottom: 8 }}>
                    <div className="dim mono" style={{ fontSize: "0.7rem" }}>
                      {new Date(line.ts).toLocaleTimeString()}  ·  {line.kind}
                    </div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.85rem", marginTop: 4 }}>
                      {line.text}
                    </div>
                  </div>
                ))}
                {(active.log || []).length === 0 ? (
                  <div className="dim">empty thread</div>
                ) : null}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
