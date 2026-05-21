// components/public/WaitlistForm.tsx — public waitlist signup form.
//
// Posts to /waitlist/join (no auth required). Renders an inline form with
// email + optional name + optional "How did you hear about this?" select.
// On success shows a confirmation message; never creates an account.

import { useCallback, useState } from "react";
import {
  waitlistJoin,
  type V32WaitlistSource,
  type V32WaitlistStatus,
} from "../../lib/api";

const SOURCE_OPTIONS: ReadonlyArray<{ value: V32WaitlistSource; label: string }> = [
  { value: "website", label: "From this website" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "facebook", label: "Facebook" },
  { value: "manual", label: "Other / from a person" },
];

interface Props {
  /** Adapts the success message to the cohort fill state. */
  cohortFull?: boolean;
}

export default function WaitlistForm({ cohortFull }: Props) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [source, setSource] = useState<V32WaitlistSource>("website");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<{ status: V32WaitlistStatus } | null>(null);

  const submit = useCallback(async (ev: React.FormEvent) => {
    ev.preventDefault();
    setError(null);
    setSuccess(null);
    if (!email.trim()) {
      setError("Email is required.");
      return;
    }
    setBusy(true);
    try {
      const r = await waitlistJoin({
        email: email.trim(),
        name: name.trim() || undefined,
        source,
        note: note.trim() || undefined,
      });
      setSuccess({ status: r.status });
      // Don't reset the form fields immediately so the user sees what they
      // submitted; the form is replaced by the success card below.
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [email, name, source, note]);

  if (success) {
    return (
      <div
        role="status"
        style={{
          padding: 16,
          background: "var(--os-surface, #fafafa)",
          border: "1px solid var(--os-border, #ccc)",
          borderRadius: 6,
          fontSize: 14,
          lineHeight: 1.5,
        }}
      >
        <strong>You're on the list.</strong>{" "}
        {cohortFull
          ? "We'll reach out as soon as a Founding 500 spot opens."
          : "We'll reach out before the Founding Cohort opens on May 15."}
        <div style={{ color: "var(--os-text-secondary, #666)", marginTop: 6, fontSize: 12 }}>
          No account was created and no login is required.
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={submit} style={{ display: "grid", gap: 8 }}>
      <label style={{ display: "block", fontSize: 13 }}>
        Email
        <input
          type="email"
          required
          autoComplete="email"
          inputMode="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          style={inputStyle}
          aria-label="Email"
        />
      </label>
      <label style={{ display: "block", fontSize: 13 }}>
        Name <span style={{ color: "#888" }}>(optional)</span>
        <input
          type="text"
          autoComplete="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Your name"
          style={inputStyle}
          aria-label="Name"
        />
      </label>
      <label style={{ display: "block", fontSize: 13 }}>
        How did you hear about this? <span style={{ color: "#888" }}>(optional)</span>
        <select
          value={source}
          onChange={(e) => setSource(e.target.value as V32WaitlistSource)}
          style={inputStyle}
          aria-label="How did you hear about this?"
        >
          {SOURCE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </label>
      <label style={{ display: "block", fontSize: 13 }}>
        Anything else? <span style={{ color: "#888" }}>(optional, 1000 chars)</span>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="A sentence or two about what you're hoping for, if you'd like."
          rows={3}
          maxLength={1000}
          style={{ ...inputStyle, resize: "vertical", minHeight: 60 }}
          aria-label="Anything else"
        />
      </label>

      {error && (
        <div
          role="alert"
          style={{
            padding: 8,
            background: "#fee",
            border: "1px solid #f99",
            borderRadius: 4,
            fontSize: 12,
          }}
        >
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={busy || !email.trim()}
        style={{
          padding: "10px 16px",
          fontSize: 14,
          fontWeight: 600,
          cursor: busy ? "default" : "pointer",
          opacity: busy ? 0.6 : 1,
        }}
      >
        {busy
          ? "Sending…"
          : cohortFull
            ? "Join the Waitlist"
            : "Join the Founding Cohort"}
      </button>
    </form>
  );
}

const inputStyle: React.CSSProperties = {
  display: "block",
  width: "100%",
  padding: "8px 10px",
  fontSize: 14,
  border: "1px solid var(--os-border, #ccc)",
  borderRadius: 4,
  marginTop: 4,
  background: "var(--os-bg, #fff)",
  color: "var(--os-text, #111)",
  boxSizing: "border-box",
};
