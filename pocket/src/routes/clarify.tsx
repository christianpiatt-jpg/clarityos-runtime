import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import {
  clarify,
  AuthRequiredError,
  type MarkovResponse,
} from "../api/client";
import ErrorBlock from "../components/Error";
import Loading from "../components/Loading";

/**
 * Pocket Clarify screen.
 *
 * Posts free-form text to ``/markov`` (the closest backend endpoint
 * to the card's intended "/clarify" until a dedicated route lands).
 * Labelled honestly in the UI so the substitution is visible.
 *
 * Auth-required: a 401 routes the user to ``/login`` via the
 * inline gate below.
 */
export default function ClarifyRoute() {
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<MarkovResponse | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [needsAuth, setNeedsAuth] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (submitting || !text.trim()) return;
    setError(null);
    setResult(null);
    setNeedsAuth(false);
    setSubmitting(true);
    try {
      const data = await clarify(text);
      setResult(data);
    } catch (e) {
      if (e instanceof AuthRequiredError) {
        setNeedsAuth(true);
      } else {
        setError(e instanceof Error ? e : new Error(String(e)));
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (needsAuth) {
    return (
      <section className="pocket-clarify">
        <h1>Clarify</h1>
        <p>You need to sign in to use Clarify.</p>
        <p>
          <Link to="/login" state={{ from: "/clarify" }} className="pocket-btn">
            Sign in
          </Link>
        </p>
      </section>
    );
  }

  return (
    <section className="pocket-clarify">
      <h1>Clarify</h1>
      <p className="pocket-muted">
        Powered by <code>/markov</code> until a dedicated{" "}
        <code>/clarify</code> endpoint lands on the backend.
      </p>

      <form onSubmit={onSubmit} className="pocket-form">
        <label className="pocket-field">
          <span>Text</span>
          <textarea
            value={text}
            rows={6}
            placeholder="What do you want clarified?"
            onChange={(e) => setText(e.target.value)}
          />
        </label>

        <button
          type="submit"
          className="pocket-btn"
          disabled={submitting || !text.trim()}
        >
          {submitting ? "Asking…" : "Clarify"}
        </button>
      </form>

      {submitting ? <Loading label="Calling /markov…" /> : null}
      <ErrorBlock error={error} title="Request failed" />

      {result ? (
        <div className="pocket-result">
          <h2>Response</h2>
          <div className="pocket-result-meta">
            <span>
              <strong>surface:</strong> {result.surface}
            </span>
            <span>
              <strong>ok:</strong> {String(result.ok)}
            </span>
          </div>
          <pre className="pocket-pre">
            {JSON.stringify(result.payload, null, 2)}
          </pre>
        </div>
      ) : null}
    </section>
  );
}
