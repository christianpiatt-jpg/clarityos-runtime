// components/founder/CreateMemberBox.tsx — #150: the founder types an email
// and the account exists. Same birth path as a magic-link click, an optional
// founder grant by the same body as Activate, and the person's link by the
// same throttled sender. The server never returns a token or a link; this
// box shows only what happened.

import { useEffect, useState } from "react";
import { founderMembersCreate, type FounderMemberCreateResult } from "../../lib/api";

interface Props {
  /** Prefill from a Member-search miss ("No account yet for X — create one?") */
  prefill?: string;
  /** bump so the SAME address can be prefilled again after the box was edited */
  prefillKey?: number;
  onCreated?: (email: string, result: FounderMemberCreateResult) => void;
}

export function resultLine(r: FounderMemberCreateResult): string {
  const parts: string[] = [];
  if (r.created) {
    parts.push("created");
    if (r.activated) parts.push("activated");
    if (r.sent) parts.push("link sent");
  } else {
    parts.push("already existed");
    if (r.activated) parts.push("activated");
    if (r.sent) parts.push("link resent");
  }
  if (r.activate_error) parts.push(`activate failed: ${r.activate_error}`);
  if (r.link_throttled) parts.push("link throttled — try again in a few minutes");
  return parts.join(" · ");
}

export default function CreateMemberBox({ prefill, prefillKey = 0, onCreated }: Props) {
  const [email, setEmail] = useState(prefill ?? "");
  const [activate, setActivate] = useState(false);
  const [sendLink, setSendLink] = useState(true);
  const [busy, setBusy] = useState(false);
  const [line, setLine] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { if (prefill) { setEmail(prefill); setLine(null); setError(null); } }, [prefill, prefillKey]);

  const canSubmit = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()) && !busy;

  async function submit(ev: React.FormEvent) {
    ev.preventDefault();
    if (!canSubmit) return;
    setBusy(true); setError(null); setLine(null);
    try {
      const r = await founderMembersCreate({ email: email.trim(), activate, send_link: sendLink });
      setLine(resultLine(r));
      onCreated?.(email.trim().toLowerCase(), r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section style={panelStyle} data-testid="create-member">
      <h2 style={{ margin: 0, fontSize: 16, marginBottom: 8 }}>Create member</h2>
      <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="email"
          aria-label="Email"
          data-testid="create-member-email"
          style={inputStyle}
          disabled={busy}
        />
        <label style={checkStyle}>
          <input type="checkbox" checked={activate} onChange={(e) => setActivate(e.target.checked)}
                 data-testid="create-member-activate" disabled={busy} />
          activate now (founder grant, no charge)
        </label>
        <label style={checkStyle}>
          <input type="checkbox" checked={sendLink} onChange={(e) => setSendLink(e.target.checked)}
                 data-testid="create-member-sendlink" disabled={busy} />
          send link
        </label>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button type="submit" disabled={!canSubmit} data-testid="create-member-submit">
            {busy ? "…" : "CREATE"}
          </button>
          {line && <span data-testid="create-member-result" style={{ fontSize: 12 }}>{line}</span>}
        </div>
      </form>
      {error && <div style={errorStyle} data-testid="create-member-error">{error}</div>}
    </section>
  );
}

const panelStyle: React.CSSProperties = {
  border: "1px solid #ddd", borderRadius: 6, padding: 12, background: "#fff", marginBottom: 12,
};
const inputStyle: React.CSSProperties = {
  padding: "6px 8px", fontSize: 13, border: "1px solid #ccc", borderRadius: 4,
};
const checkStyle: React.CSSProperties = { fontSize: 12, display: "flex", gap: 6, alignItems: "center" };
const errorStyle: React.CSSProperties = {
  marginTop: 8, padding: 6, background: "#fee", border: "1px solid #f99", borderRadius: 4, fontSize: 12,
};
