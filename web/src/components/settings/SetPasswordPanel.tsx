// Set-a-password panel (pen ruling 2026-08-12 — members set their own password).
//
// Optional, never forced. The magic link stays the root of trust: this call
// only works while holding a session, and a session is only obtainable by
// clicking a link sent to the member's address. The password is a convenience
// layer on top of the link.
//
// There is deliberately no "reset" affordance here — a forgotten password is
// /enter → magic link → new session → set a new one.
import { useState } from "react";
import { ApiError, setPassword } from "../../lib/api";
import { markPasswordPromptSeen } from "./SetPasswordPrompt";

const MIN_LEN = 12;

export default function SetPasswordPanel() {
  const [pwd, setPwd] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tooShort = pwd.length > 0 && pwd.length < MIN_LEN;
  const mismatch = confirm.length > 0 && pwd !== confirm;
  const canSubmit = pwd.length >= MIN_LEN && pwd === confirm && !busy;

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await setPassword(pwd);
      markPasswordPromptSeen();   // never re-offer once one is set
      setDone(true);
      setPwd("");
      setConfirm("");
    } catch (e: unknown) {
      setError(
        e instanceof ApiError ? e.message : "Could not set the password",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel">
      <h2>SET A PASSWORD</h2>
      <p className="muted" style={{ marginBottom: 12, fontSize: "0.85rem" }}>
        Optional. You can always sign in with an emailed link — a password just
        saves you the trip to your inbox. Forgot it later? Request a link and
        set a new one.
      </p>

      {done ? (
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          Password set. You can now sign in with your email and password, or
          keep using the link.
        </p>
      ) : (
        <>
          <label className="muted" style={{ fontSize: "0.8rem" }} htmlFor="pw-new">
            New password ({MIN_LEN} characters or more)
          </label>
          <input
            id="pw-new"
            type="password"
            autoComplete="new-password"
            value={pwd}
            onChange={(e) => setPwd(e.target.value)}
            style={{ display: "block", width: "100%", margin: "6px 0 12px" }}
          />
          <label className="muted" style={{ fontSize: "0.8rem" }} htmlFor="pw-confirm">
            Confirm
          </label>
          <input
            id="pw-confirm"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            style={{ display: "block", width: "100%", margin: "6px 0 12px" }}
          />

          {tooShort && (
            <p className="muted" style={{ fontSize: "0.8rem" }}>
              At least {MIN_LEN} characters.
            </p>
          )}
          {mismatch && (
            <p className="muted" style={{ fontSize: "0.8rem" }}>
              The two entries do not match.
            </p>
          )}
          {error && (
            <p className="muted" style={{ fontSize: "0.8rem" }}>{error}</p>
          )}

          <button className="btn" disabled={!canSubmit} onClick={submit}>
            {busy ? "SAVING…" : "SET PASSWORD"}
          </button>
        </>
      )}
    </div>
  );
}
