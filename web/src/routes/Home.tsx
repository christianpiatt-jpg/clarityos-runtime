// routes/Home.tsx — the door.
//
// clarity.pro-mediations.com is MEMBERS-ONLY. No price, no buy button.
// Selling lives on pro-mediations.com. One purpose per host.
//
// Replaces the v32 marketing landing (May 15 timeline, WaitlistForm,
// "Founding 500 cohort is currently full", and the ungated nav that
// exposed internal route names to anyone who loaded the page).
//
// WHY THERE IS NO PASSWORD FIELD ON THE PRIMARY PATH
//   auth_magiclink.py:364 — a new account gets an unusable random bcrypt
//   password that is never recorded, by design. app.py:1247
//   /auth/password/set takes the password from the SESSION only, so you
//   must already be signed in to set one. The magic link IS the reset
//   path, which collapses new / returning / forgotten into one action.
//
// WHY BOTH DOORS ARE SHOWN TO EVERYONE
//   app.py:1198 — /auth/enter returns {"status":"ok"} for ANY syntactically
//   valid address whether or not an account exists. It is enumeration-safe
//   by design, so this surface CANNOT know which case it is in and must not
//   branch on it. Present both paths; let the person resolve it.
import { useState } from "react";
import { Link } from "react-router-dom";
import { getApiBase } from "../lib/config";

const SUBSCRIBE_URL = "https://pro-mediations.com";
const HELP_EMAIL = "christian@pro-mediations.com";

function helpMailto(address: string): string {
  const subject = encodeURIComponent("ClarityOS access");
  const body = encodeURIComponent(
    `I tried to sign in with: ${address || "(no address entered)"}`,
  );
  return `mailto:${HELP_EMAIL}?subject=${subject}&body=${body}`;
}

export default function Home() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const address = email.trim();
    if (!address) return;
    setBusy(true);
    setError(null);
    try {
      // /auth/enter takes FORM-ENCODED fields (app.py:1194 — email/source are
      // Form(...)), not JSON. The shared request() helper sends JSON, so this
      // posts directly.
      const res = await fetch(`${getApiBase()}/auth/enter`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ email: address, source: "clarity-door" }),
      });
      if (res.status === 400) {
        setError("Enter a valid email address.");
        return;
      }
      // A 200 means the request was accepted. It is NOT delivery confirmation
      // and carries no signal about whether an account exists.
      setSent(address);
    } catch {
      setError("Could not reach the server. Try again in a moment.");
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <main style={wrap}>
        <h1 style={brand}>ClarityOS</h1>
        <h2 style={heading}>Check your email</h2>
        <p style={body}>
          A secure sign-in link is on its way to that address.
        </p>

        <div style={divider} />

        <p style={muted}>
          Didn&rsquo;t get one? It may not be a member address yet.
        </p>
        <ul style={list}>
          <li>
            <a href={SUBSCRIBE_URL} style={link}>Subscribe &rarr;</a>
          </li>
          <li>
            <button type="button" style={linkButton} onClick={() => setSent(null)}>
              Wrong email? &rarr;
            </button>
          </li>
          <li>
            Need help? <a href={helpMailto(sent)} style={link}>{HELP_EMAIL}</a>
          </li>
        </ul>
      </main>
    );
  }

  return (
    <main style={wrap}>
      <h1 style={brand}>ClarityOS</h1>

      <form onSubmit={submit} style={{ marginTop: 28 }}>
        <label htmlFor="door-email" style={srOnly}>Email address</label>
        <input
          id="door-email"
          type="email"
          autoComplete="email"
          autoFocus
          placeholder="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={input}
        />
        <button type="submit" disabled={busy || !email.trim()} style={button}>
          {busy ? "Sending…" : "Continue"}
        </button>
      </form>

      <p style={muted}>We&rsquo;ll email you a secure sign-in link.</p>
      {error && <p style={{ ...muted, color: "#922" }}>{error}</p>}

      <div style={divider} />

      <ul style={list}>
        <li>
          Not a member yet? <a href={SUBSCRIBE_URL} style={link}>Subscribe &rarr;</a>
        </li>
        <li>
          Have a password? <Link to="/login" style={link}>Sign in &rarr;</Link>
        </li>
        <li>
          Need help? <a href={helpMailto(email)} style={link}>{HELP_EMAIL}</a>
        </li>
      </ul>
    </main>
  );
}

// ---------- inline styles (no dependency on the marketing stylesheet) ----------
const wrap: React.CSSProperties = {
  maxWidth: 420,
  margin: "12vh auto",
  padding: "0 24px",
  fontFamily:
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
  lineHeight: 1.5,
};
const brand: React.CSSProperties = {
  margin: 0,
  fontSize: 22,
  fontWeight: 600,
  letterSpacing: "0.01em",
};
const heading: React.CSSProperties = { margin: "28px 0 8px", fontSize: 20 };
const body: React.CSSProperties = { margin: "0 0 4px" };
const input: React.CSSProperties = {
  display: "block",
  width: "100%",
  padding: "12px 14px",
  fontSize: 16,
  borderRadius: 8,
  border: "1px solid var(--os-line, #ccc)",
  marginBottom: 10,
  boxSizing: "border-box",
};
const button: React.CSSProperties = {
  display: "block",
  width: "100%",
  padding: "12px 14px",
  fontSize: 16,
  fontWeight: 600,
  borderRadius: 8,
  border: "1px solid transparent",
  cursor: "pointer",
};
const muted: React.CSSProperties = {
  marginTop: 12,
  fontSize: 14,
  opacity: 0.75,
};
const divider: React.CSSProperties = {
  height: 1,
  background: "var(--os-line, #ddd)",
  margin: "28px 0 18px",
};
const list: React.CSSProperties = {
  listStyle: "none",
  padding: 0,
  margin: 0,
  fontSize: 14,
  display: "grid",
  gap: 10,
};
const link: React.CSSProperties = { textDecoration: "underline" };
const linkButton: React.CSSProperties = {
  background: "none",
  border: 0,
  padding: 0,
  font: "inherit",
  cursor: "pointer",
  textDecoration: "underline",
};
const srOnly: React.CSSProperties = {
  position: "absolute",
  width: 1,
  height: 1,
  overflow: "hidden",
  clip: "rect(0 0 0 0)",
  whiteSpace: "nowrap",
};
