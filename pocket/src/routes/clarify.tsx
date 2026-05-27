import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import {
  clarify,
  AuthRequiredError,
  type MarkovResponse,
} from "../api/client";
import Button from "../components/Button";
import Card from "../components/Card";
import ErrorBlock from "../components/Error";
import Loading from "../components/Loading";
import SectionTitle from "../components/SectionTitle";
import Textarea from "../components/Textarea";

/**
 * Pocket Clarify — v0.3.2.
 *
 * Full-width textarea, primary submit at the bottom, response
 * surfaces in a second card. Labelled honestly: the backend
 * endpoint is /markov until a dedicated /clarify endpoint lands.
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
      if (e instanceof AuthRequiredError) setNeedsAuth(true);
      else setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setSubmitting(false);
    }
  }

  if (needsAuth) {
    return (
      <Card>
        <h1>Clarify</h1>
        <p className="pocket-muted">You need to sign in to use Clarify.</p>
        <Link
          to="/login"
          state={{ from: "/clarify" }}
          className="pkt-btn pkt-btn--primary pkt-btn--md is-block"
          style={{ marginTop: 16 }}
        >
          Sign in
        </Link>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <h1>Clarify</h1>
        <p className="pocket-faint" style={{ fontSize: 13, marginBottom: 16 }}>
          Powered by <code>/markov</code> until a dedicated{" "}
          <code>/clarify</code> endpoint lands.
        </p>

        <form
          onSubmit={onSubmit}
          style={{ display: "flex", flexDirection: "column", gap: 16 }}
        >
          <Textarea
            label="Text"
            value={text}
            rows={6}
            placeholder="What do you want clarified?"
            onChange={(e) => setText(e.target.value)}
          />
          <Button type="submit" block disabled={submitting || !text.trim()}>
            {submitting ? "Asking…" : "Clarify"}
          </Button>
        </form>

        {submitting ? (
          <div style={{ marginTop: 12 }}>
            <Loading label="Calling /markov…" />
          </div>
        ) : null}

        {error ? (
          <div style={{ marginTop: 12 }}>
            <ErrorBlock error={error} title="Request failed" />
          </div>
        ) : null}
      </Card>

      {result ? (
        <>
          <SectionTitle>Response</SectionTitle>
          <Card>
            <div className="pkt-result-meta">
              <span>
                <strong>surface:</strong> {result.surface}
              </span>
              <span>
                <strong>ok:</strong> {String(result.ok)}
              </span>
            </div>
            <pre className="pkt-pre">
              {JSON.stringify(result.payload, null, 2)}
            </pre>
          </Card>
        </>
      ) : null}
    </>
  );
}
