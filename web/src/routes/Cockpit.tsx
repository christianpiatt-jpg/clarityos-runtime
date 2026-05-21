// ClarityOS Cockpit (v29-hardened) — composes the split panels under
// components/cockpit/*. Adds:
//   * /v29/flags gating (v28 surfaces hidden when off)
//   * Onboarding wizard (hidden once /v29/onboarding/state.done)
//   * "What's new in v28" panel
//   * Loading + error chrome at every panel boundary, with a manual retry
//
// All state lives in hooks/* so this route is just layout + wiring. No
// summarization, no embeddings, no inference at the surface layer; backend
// envelope blocks are rendered as-is.

import { useState } from "react";
import { Link } from "react-router-dom";
import type { EngineId } from "../services/engines";
import { useContinuity } from "../hooks/useContinuity";
import { useDeviceId } from "../hooks/useDeviceId";
import { useFlags } from "../hooks/useFlags";
import { useMesh } from "../hooks/useMesh";
import SessionList from "../components/cockpit/SessionList";
import RuntimePanel from "../components/cockpit/RuntimePanel";
import VaultStatus from "../components/cockpit/VaultStatus";
import EngineSelector from "../components/cockpit/EngineSelector";
import SettingsPanel from "../components/cockpit/SettingsPanel";
import ContinuitySurface from "../components/cockpit/ContinuitySurface";
import OnboardingWizard from "../components/cockpit/OnboardingWizard";
import WhatsNewPanel from "../components/cockpit/WhatsNewPanel";
import ElinsQuicklook from "../components/cockpit/ElinsQuicklook";
import ElInsIndicator from "../components/cockpit/ElInsIndicator";
import RegressionFirstPanel from "../components/cockpit/RegressionFirstPanel";

export default function Cockpit() {
  const deviceId = useDeviceId();
  const { flags, loading: flagsLoading } = useFlags();
  const {
    snapshot,
    error: snapshotError,
    loading: snapshotLoading,
    refresh: refreshSnapshot,
  } = useContinuity();
  const {
    mesh,
    error: meshError,
    loading: meshLoading,
    refresh: refreshMesh,
  } = useMesh({ deviceId, pushOnSnapshot: snapshot });
  const [engine, setEngine] = useState<EngineId>("markov");

  const refreshAll = () => {
    void refreshSnapshot();
    void refreshMesh();
  };

  // v29 — gate v28-only surfaces. While flags are loading we show a dimmed
  // shell (NOT a hard block) so a slow /v29/flags doesn't blank the cockpit.
  const v28Enabled = flags.v28_surfaces === true;
  const showOnboarding = flags.onboarding_v1 === true;
  const showWhatsNew = flags.whats_new_v28 === true;

  return (
    <div className="cockpit">
      <header style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "baseline",
        marginBottom: 16,
      }}>
        <h1 style={{ margin: 0 }}>Cockpit</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {flagsLoading && (
            <span style={{ fontSize: 11, color: "#888" }}>checking access…</span>
          )}
          {(snapshotLoading || meshLoading) && (
            <span style={{ fontSize: 11, color: "#888" }}>refreshing…</span>
          )}
          <button onClick={refreshAll} disabled={snapshotLoading || meshLoading}>
            Refresh
          </button>
          {v28Enabled && (
            <Link to="/dashboard">
              <button title="Unified intelligence view: global, regional, macro, entities">
                Open ELINS →
              </button>
            </Link>
          )}
          {v28Enabled && (
            <Link to="/elins">
              <button title="Daily delivery feed (legacy)">Feed</button>
            </Link>
          )}
          {flags.membership_ui_enabled === true && (
            <Link to="/membership"><button>Membership →</button></Link>
          )}
        </div>
      </header>

      {showOnboarding && <OnboardingWizard />}

      <div className="panel" data-testid="el-ins-cockpit-panel">
        <ElInsIndicator />
      </div>

      {v28Enabled && <ElinsQuicklook />}

      {snapshotError && (
        <ErrorBanner
          message={snapshotError}
          onRetry={() => void refreshSnapshot()}
          label="Continuity snapshot"
        />
      )}
      {meshError && (
        <ErrorBanner
          message={meshError}
          onRetry={() => void refreshMesh()}
          label="Mesh state"
        />
      )}

      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 2fr",
        gap: 16,
        alignItems: "start",
      }}>
        <Panel title="Session list">
          <SessionList />
        </Panel>

        <Panel title="Runtime — envelope viewer (deterministic)">
          <RuntimePanel />
        </Panel>

        <Panel title="Vault status">
          <VaultStatus snapshot={snapshot} />
        </Panel>

        <Panel title="Engine selector">
          <EngineSelector value={engine} onChange={setEngine} />
        </Panel>

        <Panel title="Settings">
          <SettingsPanel deviceId={deviceId} />
        </Panel>

        <Panel title={v28Enabled ? "Continuity surface (v28)" : "Continuity surface (v28) — disabled"}>
          {v28Enabled ? (
            <ContinuitySurface snapshot={snapshot} mesh={mesh} />
          ) : (
            <div style={{ color: "#888", fontSize: 12 }}>
              v28 surfaces are not enabled for your account.
            </div>
          )}
        </Panel>

        {showWhatsNew && (
          <Panel title="What's new">
            <WhatsNewPanel />
          </Panel>
        )}

        <Panel title="Regression First (v80) — packet runner">
          <RegressionFirstPanel />
        </Panel>
      </div>
    </div>
  );
}

function ErrorBanner({
  message,
  onRetry,
  label,
}: {
  message: string;
  onRetry: () => void;
  label: string;
}) {
  return (
    <div style={{
      padding: 8,
      background: "#fee",
      border: "1px solid #f99",
      marginBottom: 12,
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
    }}>
      <span style={{ fontSize: 13 }}>
        <strong>{label}:</strong> {message}
      </span>
      <button onClick={onRetry}>Retry</button>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{
      border: "1px solid #ddd",
      borderRadius: 6,
      padding: 12,
      background: "#fafafa",
    }}>
      <h2 style={{
        margin: 0,
        marginBottom: 8,
        fontSize: 14,
        color: "#666",
        textTransform: "uppercase",
        letterSpacing: "0.05em",
      }}>
        {title}
      </h2>
      <ErrorBoundary>{children}</ErrorBoundary>
    </section>
  );
}

import React from "react";

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(_error: Error, _info: React.ErrorInfo) {
    // No remote logging — surface the error inline instead.
  }

  reset = () => this.setState({ error: null });

  render() {
    if (this.state.error) {
      return (
        <div style={{ color: "#922", fontSize: 12 }}>
          <div><strong>Panel error:</strong> {this.state.error.message}</div>
          <button onClick={this.reset} style={{ marginTop: 4 }}>Try again</button>
        </div>
      );
    }
    return <>{this.props.children}</>;
  }
}
