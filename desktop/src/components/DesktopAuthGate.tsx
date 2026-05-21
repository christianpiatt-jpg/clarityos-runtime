// ClarityOS desktop — DesktopAuthGate (v68 / Unit 72).
//
// Per-shell auth gate that mirrors web/src/components/RequireAuth.tsx
// semantics. The desktop app already shows a full SignIn screen at the
// App.tsx level for cold-start unauth; this component handles the
// *mid-session* case where the renderer is already inside a shell when
// a 401 lands. Instead of bouncing the user back to the full SignIn
// (the pre-Unit-72 behaviour: `clearSession(); onSignOut();`), the
// shell wraps its content in DesktopAuthGate which surfaces an inline
// CTA so the user sees what surface they were on and chooses whether
// to re-authenticate.
//
// Contract:
//   - reads ``isAuthed()`` from ../lib/api
//   - when not authed → renders an inline panel with a SIGN IN button
//   - when authed → renders children unchanged (zero overhead)
//
// The SIGN IN button calls the ``onRequestSignIn`` prop, which each
// shell wires to its existing ``onSignOut`` flow. App.tsx flips to
// the ``signed_out`` state on receipt and renders the full SignIn
// form. This preserves the existing auth state machine — the gate
// is purely a UX layer.

import { ReactNode } from "react";
import { isAuthed } from "../lib/api";

interface Props {
  children: ReactNode;
  /** Invoked when the user clicks SIGN IN. Shells wire this to the
   *  same ``onSignOut`` callback the App.tsx auth flow already uses
   *  so we don't fork the auth state machine. */
  onRequestSignIn: () => void;
  /** Optional override for the body copy. */
  message?: string;
}

export default function DesktopAuthGate({
  children, onRequestSignIn, message,
}: Props) {
  if (isAuthed()) return <>{children}</>;
  return (
    <div style={rootStyle} data-testid="desktop-auth-cta">
      <div style={cardStyle}>
        <h1 style={h1Style}>Sign in required</h1>
        <p style={bodyStyle}>
          {message ?? "You need to sign in to start or resume sessions."}
        </p>
        <button
          type="button"
          onClick={onRequestSignIn}
          style={ctaStyle}
          data-testid="desktop-auth-cta-signin"
        >
          SIGN IN
        </button>
      </div>
    </div>
  );
}

const rootStyle: React.CSSProperties = {
  flex: 1,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: 24,
  background: "var(--color-bg-deep, #050810)",
};

const cardStyle: React.CSSProperties = {
  maxWidth: 480,
  width: "100%",
  background: "var(--color-bg-surface, #0c1220)",
  border: "1px solid rgba(255,255,255,0.1)",
  padding: 32,
  borderRadius: 4,
};

const h1Style: React.CSSProperties = {
  margin: 0,
  marginBottom: 8,
  fontSize: 22,
  color: "var(--color-text-primary, #e8ecf5)",
};

const bodyStyle: React.CSSProperties = {
  margin: 0,
  marginBottom: 20,
  color: "var(--color-text-secondary, #8893a8)",
  fontSize: 14,
  lineHeight: 1.5,
};

const ctaStyle: React.CSSProperties = {
  background: "var(--color-accent-cyan, #00F0FF)",
  color: "#04121b",
  border: "none",
  padding: "10px 16px",
  fontWeight: 700,
  letterSpacing: "0.5px",
  cursor: "pointer",
  borderRadius: 2,
};
