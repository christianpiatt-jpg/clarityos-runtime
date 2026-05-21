import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  clearInterrupted,
  getResumeOptions,
  type ResumeOption,
} from "../lib/continuity";

export default function Continuity() {
  const navigate = useNavigate();
  const [options, setOptions] = useState<ResumeOption[]>([]);

  useEffect(() => { setOptions(getResumeOptions()); }, []);

  function resume(opt: ResumeOption) {
    if (opt.kind === "interrupted-session") {
      clearInterrupted();
      navigate("/sessions");
      return;
    }
    if (opt.kind === "last-thread") {
      navigate("/sessions");
      return;
    }
  }

  function startFresh() {
    clearInterrupted();
    setOptions(getResumeOptions());
  }

  return (
    <div>
      <div className="panel">
        <h1>CONTINUITY</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Resume options surfaced from local state: interrupted sessions, pending vault items,
          most recent thread. Local-only — no backend route.
        </p>
      </div>

      {options.length === 0 ? (
        <div className="empty">Nothing to resume on this device.</div>
      ) : (
        options.map((opt, i) => (
          <button
            key={`${opt.kind}-${i}`}
            className="list-item"
            style={{ width: "100%", textAlign: "left", cursor: "pointer" }}
            onClick={() => resume(opt)}
          >
            <div className="title" style={{ color: "var(--os-focus)", fontFamily: "var(--font-mono)" }}>
              {labelFor(opt)}
            </div>
            <div className="meta">{detailFor(opt)}</div>
          </button>
        ))
      )}

      <div style={{ marginTop: 16 }}>
        <button className="btn btn-secondary" onClick={startFresh}>
          CLEAR INTERRUPTED FLAG
        </button>
      </div>
    </div>
  );
}

function labelFor(o: ResumeOption): string {
  if (o.kind === "interrupted-session") return "INTERRUPTED SESSION";
  if (o.kind === "last-thread") return "LAST THREAD";
  return "";
}

function detailFor(o: ResumeOption): string {
  if (o.kind === "interrupted-session") {
    return `Thread ${o.threadId} · interrupted ${new Date(o.lastEditedAt).toLocaleString()}`;
  }
  if (o.kind === "last-thread") {
    return o.title || `Thread ${o.threadId}`;
  }
  return "";
}
