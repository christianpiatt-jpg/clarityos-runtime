import { useState } from "react";

import {
  getBackendUrl,
  isBackendUrlFromEnv,
  health,
  type HealthResponse,
} from "../api/client";
import Button from "../components/Button";
import Card from "../components/Card";
import ErrorBlock from "../components/Error";
import Loading from "../components/Loading";
import SectionTitle from "../components/SectionTitle";

/**
 * Pocket Runtime — v0.3.2.
 *
 * Centered card with deploy metadata + a live ping to the Python
 * clarity-engine ``/health`` endpoint. PHONE-native; this surface
 * reads its own VITE_BUILD_VERSION + VITE_CLARITY_ENGINE_URL (NOT
 * the cockpit's K_SERVICE / K_REVISION — those live on a different
 * Cloud Run service).
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
    <>
      <Card>
        <h1>Runtime</h1>
        <p className="pkt-status">
          <span className="pkt-status-dot" /> runtime OK
        </p>

        <dl className="pkt-dl" style={{ marginTop: 16 }}>
          <dt>Build</dt>
          <dd>{buildVersion || "(unset)"}</dd>

          <dt>Backend</dt>
          <dd>
            {backendUrl}{" "}
            <span className="pocket-faint" style={{ fontSize: 12 }}>
              ({backendUrlFromEnv ? "from env" : "fallback"})
            </span>
          </dd>
        </dl>
      </Card>

      <SectionTitle description="Live probe of the Python clarity-engine">
        Backend health
      </SectionTitle>

      <Card>
        <Button block onClick={onPing} disabled={pinging}>
          {pinging ? "Pinging…" : "Ping backend"}
        </Button>

        {pinging ? (
          <div style={{ marginTop: 12 }}>
            <Loading label="Calling /health…" />
          </div>
        ) : null}

        {healthError ? (
          <div style={{ marginTop: 12 }}>
            <ErrorBlock
              error={healthError}
              onRetry={onPing}
              title="Backend ping failed"
            />
          </div>
        ) : null}

        {healthData ? (
          <dl className="pkt-dl" style={{ marginTop: 16 }}>
            <dt>ok</dt>
            <dd>{String(healthData.ok)}</dd>

            <dt>status</dt>
            <dd>{healthData.status}</dd>

            <dt>version</dt>
            <dd>{healthData.version}</dd>
          </dl>
        ) : null}
      </Card>
    </>
  );
}
