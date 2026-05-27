import { FormEvent, useEffect, useState } from "react";

import {
  operatorState,
  setOperatorToken,
  clearOperatorToken,
  hasOperatorToken,
  ApiError,
  AuthRequiredError,
  type OperatorState,
} from "../api/client";
import Button from "../components/Button";
import Card from "../components/Card";
import ErrorBlock from "../components/Error";
import Input from "../components/Input";
import Loading from "../components/Loading";
import SectionTitle from "../components/SectionTitle";

/**
 * Pocket Operator State — Card 17.
 *
 * Operator-only diagnostic console backed by the engine's
 * ``GET /operator/state`` endpoint (Card 16). Two states:
 *
 *   1. No operator token in memory -> render a paste form. The
 *      token is stored ONLY in module-local memory in
 *      ``api/client.ts`` (not localStorage, not sessionStorage).
 *      That means it dies on page reload — by design.
 *
 *   2. Token present -> fetch ``/operator/state`` and render the
 *      engine_revision, vault_status, active_sessions,
 *      uptime_seconds, backend, version, and CORS allow-list.
 *
 * On 401 from the backend (wrong token), the in-memory token is
 * cleared and the paste form re-appears with an inline error. The
 * apiFetch path for this endpoint sets ``skipAuthRedirect`` so a
 * bad operator token does NOT log the user out of their normal
 * session OR bounce the SPA to /login.
 */
export default function OperatorStateRoute() {
  const [hasToken, setHasToken] = useState<boolean>(hasOperatorToken());
  const [tokenDraft, setTokenDraft] = useState("");
  const [data, setData] = useState<OperatorState | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  async function load() {
    if (!hasOperatorToken()) {
      setData(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const d = await operatorState();
      setData(d);
    } catch (e) {
      if (e instanceof AuthRequiredError) {
        // Wrong / expired token. Clear it locally so the form
        // re-appears, surface a clean message.
        clearOperatorToken();
        setHasToken(false);
        setData(null);
        setError(
          new Error(
            "Operator token rejected by engine. Paste a valid token.",
          ),
        );
      } else if (e instanceof ApiError && e.code === "no_operator_token") {
        // Defensive — race between hasOperatorToken check and call.
        setHasToken(false);
        setData(null);
      } else {
        setError(e instanceof Error ? e : new Error(String(e)));
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasToken]);

  function onSubmitToken(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const t = tokenDraft.trim();
    if (!t) return;
    setOperatorToken(t);
    setTokenDraft("");
    setHasToken(true);
    setError(null);
  }

  function onForgetToken() {
    clearOperatorToken();
    setHasToken(false);
    setData(null);
    setError(null);
  }

  if (!hasToken) {
    return (
      <Card>
        <h1>Operator State</h1>
        <p className="pocket-muted">
          This endpoint requires an Operator token. The token is held
          in memory only (no localStorage, no sessionStorage) so a
          page reload clears it. Paste it again whenever you need
          access.
        </p>
        <form
          onSubmit={onSubmitToken}
          style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 16 }}
        >
          <Input
            label="Operator token"
            type="password"
            autoComplete="off"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            value={tokenDraft}
            onChange={(e) => setTokenDraft(e.target.value)}
            placeholder="paste 64-char hex token"
          />
          <Button type="submit" block disabled={!tokenDraft.trim()}>
            Unlock operator state
          </Button>
        </form>
        <ErrorBlock error={error} title="Operator token rejected" />
        <p className="pocket-faint" style={{ fontSize: 13, marginTop: 16 }}>
          The token comes from Google Secret Manager:{" "}
          <code>clarityos-operator-token</code>. Run{" "}
          <code>gcloud secrets versions access latest --secret=clarityos-operator-token</code>{" "}
          locally to fetch it.
        </p>
      </Card>
    );
  }

  if (loading) {
    return (
      <Card>
        <h1>Operator State</h1>
        <Loading label="Calling /operator/state…" />
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <h1>Operator State</h1>
        <ErrorBlock error={error} onRetry={load} title="Could not load /operator/state" />
        <p style={{ marginTop: 16 }}>
          <Button variant="ghost" onClick={onForgetToken}>
            Forget operator token
          </Button>
        </p>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <h1>Operator State</h1>
        <p className="pocket-faint" style={{ fontSize: 13 }}>
          Source: <code>/operator/state</code> on{" "}
          <code>clarity-engine</code>
        </p>
      </Card>

      <SectionTitle>Engine</SectionTitle>
      <Card>
        <dl className="pkt-dl">
          <dt>Revision</dt>
          <dd>{data.engine_revision}</dd>

          <dt>Backend</dt>
          <dd>{data.backend}</dd>

          <dt>Version</dt>
          <dd>{data.version}</dd>

          <dt>Uptime</dt>
          <dd>{formatUptime(data.uptime_seconds)}</dd>

          <dt>Active sessions</dt>
          <dd>{String(data.active_sessions)}</dd>
        </dl>
      </Card>

      <SectionTitle>Vault</SectionTitle>
      <Card>
        <p className="pkt-status">
          <span
            className={`pkt-vault-dot ${
              data.vault_status === "ready"
                ? "pkt-vault-dot--ready"
                : "pkt-vault-dot--degraded"
            }`}
          />
          {data.vault_status === "ready" ? "Vault Ready" : "Vault Degraded"}
        </p>
      </Card>

      <SectionTitle description={`${data.cors_origins.length} entries`}>
        CORS allow-list
      </SectionTitle>
      <Card padded={false} style={{ padding: 16 }}>
        <ul className="pkt-cors-list">
          {data.cors_origins.map((o) => (
            <li key={o}>
              <code>{o}</code>
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <Button variant="secondary" block onClick={load}>
          Refresh
        </Button>
      </Card>

      <Card>
        <Button variant="ghost" block onClick={onForgetToken}>
          Forget operator token
        </Button>
      </Card>
    </>
  );
}

function formatUptime(seconds: number): string {
  const totalSec = Math.max(0, Math.floor(seconds));
  const days = Math.floor(totalSec / 86400);
  const hours = Math.floor((totalSec % 86400) / 3600);
  const mins = Math.floor((totalSec % 3600) / 60);
  const secs = totalSec % 60;
  if (days > 0) return `${days}d ${hours}h ${mins}m`;
  if (hours > 0) return `${hours}h ${mins}m`;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}
