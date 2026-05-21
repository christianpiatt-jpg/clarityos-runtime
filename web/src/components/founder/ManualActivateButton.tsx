// components/founder/ManualActivateButton.tsx — founder manual ops on a
// selected user: activate / cancel / grant credits / revoke credits.

import { useState } from "react";
import {
  founderMembershipActivate,
  founderMembershipCancel,
  founderMembershipCredits,
} from "../../lib/api";

interface Props {
  user: string;
  onChanged?: () => void;
}

export default function ManualActivateButton({ user, onChanged }: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [delta, setDelta] = useState("1");
  const [reason, setReason] = useState("");

  const wrap = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label);
    setError(null);
    setInfo(null);
    try {
      await fn();
      setInfo(`${label} succeeded`);
      onChanged?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <section style={panelStyle}>
      <h2 style={{ margin: 0, fontSize: 16, marginBottom: 8 }}>Manual ops</h2>
      {!user && <div style={mutedStyle}>Select a user above first.</div>}
      {user && (
        <>
          <div style={{ fontSize: 13, marginBottom: 8 }}>
            User: <code>{user}</code>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              onClick={() => void wrap("activate", () => founderMembershipActivate(user, { note: "manual" }))}
              disabled={busy !== null}
            >
              {busy === "activate" ? "Activating…" : "Activate (founding $50)"}
            </button>
            <button
              onClick={() => void wrap("cancel", () => founderMembershipCancel(user, "manual"))}
              disabled={busy !== null}
              style={{ background: "#fee", color: "#922", borderColor: "#f99" }}
            >
              {busy === "cancel" ? "Cancelling…" : "Cancel"}
            </button>
          </div>

          <div style={{
            marginTop: 12, paddingTop: 12, borderTop: "1px solid #eee",
          }}>
            <div style={{ fontSize: 13, marginBottom: 6 }}>#G credits</div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <input
                type="number"
                value={delta}
                onChange={(e) => setDelta(e.target.value)}
                style={{ width: 80, padding: "4px 6px", fontSize: 13 }}
                aria-label="Delta"
              />
              <input
                type="text"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="reason (optional)"
                style={{ flex: 1, minWidth: 120, padding: "4px 6px", fontSize: 13 }}
                aria-label="Reason"
              />
              <button
                onClick={() => void wrap(
                  "credits",
                  () => founderMembershipCredits(user, parseInt(delta, 10) || 0, reason || undefined),
                )}
                disabled={busy !== null}
              >
                {busy === "credits" ? "Working…" : "Adjust credits"}
              </button>
            </div>
          </div>

          {info && (
            <div style={{
              marginTop: 8, padding: 6, background: "#e6f5ec",
              border: "1px solid #9c9", borderRadius: 4, fontSize: 12,
            }}>{info}</div>
          )}
          {error && (
            <div style={{
              marginTop: 8, padding: 6, background: "#fee",
              border: "1px solid #f99", borderRadius: 4, fontSize: 12,
            }}>{error}</div>
          )}
        </>
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

const mutedStyle: React.CSSProperties = { color: "#666", fontSize: 13 };
