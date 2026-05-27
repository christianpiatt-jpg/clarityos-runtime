import { FormEvent, useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";

import { login, ApiError } from "../api/client";
import Button from "../components/Button";
import Card from "../components/Card";
import ErrorBlock from "../components/Error";
import Input from "../components/Input";
import Loading from "../components/Loading";

interface NavState {
  from?: string;
}

/**
 * Pocket Login — v0.3.2.
 *
 * Single Card with username + password, primary submit at the
 * bottom. On success routes back to ``location.state.from`` or
 * ``/me`` by default.
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
      await login(username, password);
      navigate(fromPath, { replace: true });
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setError(new Error("Username or password is incorrect."));
      } else {
        setError(e instanceof Error ? e : new Error(String(e)));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <h1>Sign in</h1>
      <p className="pocket-muted" style={{ marginBottom: 24 }}>
        Sign in with your ClarityOS account to use{" "}
        <code>/me</code>, <code>/clarify</code>, and <code>/runs</code>.
      </p>

      <form
        onSubmit={onSubmit}
        style={{ display: "flex", flexDirection: "column", gap: 16 }}
      >
        <Input
          label="Username"
          type="text"
          autoComplete="username"
          autoCapitalize="off"
          autoCorrect="off"
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />

        <Input
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <Button
          type="submit"
          block
          disabled={submitting || !username || !password}
        >
          {submitting ? "Signing in…" : "Sign in"}
        </Button>

        {submitting ? <Loading label="Authenticating…" /> : null}
        <ErrorBlock error={error} title="Sign-in failed" />
      </form>

      <p
        className="pocket-faint"
        style={{ fontSize: 13, marginTop: 16, marginBottom: 0 }}
      >
        Already signed in elsewhere?{" "}
        <Link to="/me">Check session &rarr;</Link>
      </p>
    </Card>
  );
}
