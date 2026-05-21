import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ApiError, login } from "../lib/api";
import { notifyLogin, syncProfile } from "../lib/auth";

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as { from?: string } | null)?.from || "/operator";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      await login(username.trim(), password);
      notifyLogin();
      await syncProfile();
      navigate(from, { replace: true });
    } catch (e: any) {
      const msg =
        e instanceof ApiError
          ? (e.code === "bad_credentials"
              ? "Username or password incorrect."
              : e.message)
          : (e?.message || "Sign in failed");
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 420, margin: "0 auto" }}>
      <div className="panel">
        <h2>SIGN IN</h2>
        <p className="muted" style={{ marginTop: 4, marginBottom: 16 }}>
          ClarityOS operator credentials. Founders + invited operators only.
        </p>

        {error ? <div className="banner err">{error}</div> : null}

        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="u">Username</label>
            <input
              id="u"
              className="input"
              type="text"
              autoCapitalize="none"
              autoCorrect="off"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>

          <div className="field">
            <label htmlFor="p">Password</label>
            <input
              id="p"
              className="input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <button className="btn btn-block" type="submit" disabled={busy}>
            {busy ? <span className="spinner" /> : "SIGN IN"}
          </button>
        </form>
      </div>
    </div>
  );
}
