import { useState } from "react";
import { Link } from "react-router-dom";

import {
  getBackendUrl,
  isBackendUrlFromEnv,
  health,
  type HealthResponse,
} from "../api/client";
import ErrorBlock from "../components/Error";
import Loading from "../components/Loading";

/**
 * Pocket Runtime screen — v0.3.1.
 *
 * PHONE-native runtime view. Surfaces Pocket's OWN deploy metadata
 * (build version + backend URL it was wired to) AND a live ping to
 * the Python ``clarity-engine`` ``/health`` endpoint.
 *
 * Still NOT a DOM embed of the cockpit's Node runtime panel and NOT
 * an API mirror of it. The cockpit's Node runtime panel reads its
 * own Cloud Run env vars (K_SERVICE / K_REVISION). Pocket lives on
 * a different Cloud Run service and surfaces ITS build-time injected
 * metadata + ITS view of backend liveness.
 */
export default function RuntimeRoute() {
  const backendUrl = getBackendUrl();
  const backendUrlFromEnv = isBackendUrlFromEnv();
  const buildVersion =
    (import.meta.env.VITE_BUILD_VERSION as string | undefined) ?? "";

  const [pinging, setPinging] = useState(false);
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<Error | null>(null);

  async function onPing() {
    if (pinging) return;
    setPinging(true);
    setHealthError(null);
    try {
      const d = await health();
      setHealthData(d);
    } catch (e) {
      setHealthError(e instanceof Error ? e : new Error(String(e)));
      setHealthData(null);
    } finally {
      setPinging(false);
    }
  }

  return (
    <section className="pocket-runtime">
      <h1>Runtime</h1>
      <p className="pocket-status">
        <span className="pocket-status-dot" /> runtime OK
      </p>

      <dl>
        <dt>Build version</dt>
        <dd>{buildVersion || "(unset)"}</dd>

        <dt>Backend URL</dt>
        <dd>
          {backendUrl}{" "}
          <span className="pocket-muted">
            ({backendUrlFromEnv ? "from env" : "fallback"})
          </span>
        </dd>
      </dl>

      <h2>Backend health</h2>
      <p>
        <button
          type="button"
          className="pocket-btn"
          onClick={onPing}
          disabled={pinging}
        >
          {pinging ? "Pinging…" : "Ping backend"}
        </button>
      </p>

      {pinging ? <Loading label="Calling /health…" /> : null}
      <ErrorBlock
        error={healthError}
        onRetry={onPing}
        title="Backend ping failed"
      />

      {healthData ? (
        <dl>
          <dt>ok</dt>
          <dd>{String(healthData.ok)}</dd>

          <dt>status</dt>
          <dd>{healthData.status}</dd>

          <dt>version</dt>
          <dd>{healthData.version}</dd>
        </dl>
      ) : null}

      <p>
        <Link to="/">&larr; Home</Link>
      </p>
    </section>
  );
}
