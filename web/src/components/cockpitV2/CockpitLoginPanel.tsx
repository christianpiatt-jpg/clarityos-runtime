/**
 * CockpitLoginPanel — auth gate for CockpitV2.
 * Reuses the real /login flow via cockpit.auth.actions.login (lib/api login
 * + lib/auth notifyLogin/syncProfile). Does not touch the global /login route.
 */
import { useState, type FormEvent } from "react";

import { useCockpit, cockpit } from "../../state/cockpitStore";

export default function CockpitLoginPanel() {
  const auth = useCockpit((s) => s.auth);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const busy = auth.status === "authing";

  function onSubmit(e: FormEvent): void {
    e.preventDefault();
    if (busy || !username.trim() || !password) return;
    void cockpit.auth.actions.login(username, password);
  }

  return (
    <form className="cv2-login" onSubmit={onSubmit}>
      <h1 className="cv2-login-title">ClarityOS Cockpit</h1>
      <p className="cv2-login-sub">Operator sign-in</p>

      <label className="cv2-field">
        <span>Username</span>
        <input
          className="cv2-input"
          value={username}
          autoComplete="username"
          disabled={busy}
          onChange={(e) => setUsername(e.target.value)}
        />
      </label>

      <label className="cv2-field">
        <span>Password</span>
        <input
          className="cv2-input"
          type="password"
          value={password}
          autoComplete="current-password"
          disabled={busy}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>

      {auth.status === "error" && auth.error ? (
        <p className="cv2-login-error" role="alert">
          {auth.error}
        </p>
      ) : null}

      <button className="cv2-btn cv2-btn-primary" type="submit" disabled={busy}>
        {busy ? "Authenticating…" : "Sign in"}
      </button>
    </form>
  );
}
