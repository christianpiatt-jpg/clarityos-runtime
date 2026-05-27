import { FormEvent, useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";

import { login, ApiError } from "../api/client";
import ErrorBlock from "../components/Error";
import Loading from "../components/Loading";

interface NavState {
  from?: string;
}

/**
 * Pocket Login screen.
 *
 * Calls ``POST /login`` with username + password, stores the returned
 * ``session_id`` in localStorage (handled inside ``api/client.ts``),
 * then routes to wherever the user was trying to go before being
 * bounced here (``location.state.from``), defaulting to ``/me``.
 */
export default function LoginRoute() {
  const navigate = useNavigate();
  const location = useLocation();
  const fromPath = (location.state as NavState | null)?.from ?? "/me";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      const data = await login(username, password);
      // Successful login — head to where the user was going, or /me.
      navigate(fromPath, { replace: true });
      // touch ``data`` so noUnusedLocals stays happy
      void data;
    } catch (e) {
      const err = e instanceof Error ? e : new Error(String(e));
      // 401 from /login means bad credentials — surface a clean
      // message rather than the generic "Not signed in" from the
      // AuthRequiredError path.
      if (e instanceof ApiError && e.status === 401) {
        setError(new Error("Username or password is incorrect."));
      } else {
        setError(err);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="pocket-login">
      <h1>Sign in</h1>
      <p>
        Sign in with your ClarityOS account to use <code>/me</code>,{" "}
        <code>/clarify</code>, and <code>/runs</code>.
      </p>

      <form onSubmit={onSubmit} className="pocket-form">
        <label className="pocket-field">
          <span>Username</span>
          <input
            type="text"
            value={username}
            autoComplete="username"
            autoCapitalize="off"
            autoCorrect="off"
            required
            onChange={(e) => setUsername(e.target.value)}
          />
        </label>

        <label className="pocket-field">
          <span>Password</span>
          <input
            type="password"
            value={password}
            autoComplete="current-password"
            required
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>

        <button
          type="submit"
          className="pocket-btn"
          disabled={submitting || !username || !password}
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>

        {submitting ? <Loading label="Authenticating…" /> : null}
        <ErrorBlock error={error} title="Sign-in failed" />
      </form>

      <p className="pocket-muted">
        Already signed in elsewhere? <Link to="/me">Check session</Link>.
      </p>
    </section>
  );
}
