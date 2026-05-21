// v71 / Unit 78 — EL/INS export (desktop).

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  clearSession,
  fetchElInsExportPdfBlob,
  getElInsExportJson,
  getElInsOperatorSummary,
  getUser,
  health,
  type ElInsOperatorSummaryResponse,
} from "./lib/api";
import DesktopShell from "./DesktopShell";
import DesktopAuthGate from "./components/DesktopAuthGate";

const DEFAULT_LIMIT = 200;

interface Props {
  onSignOut: () => void;
  onNavigate: (label: string) => void;
}

export default function OperatorElinsExportShell({ onSignOut, onNavigate }: Props) {
  const userName = getUser();
  const [summary, setSummary] = useState<ElInsOperatorSummaryResponse | null>(null);
  const [version, setVersion] = useState<string>("…");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<"json" | "pdf" | null>(null);

  const handleAuthError = useCallback((e: unknown): boolean => {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      clearSession();
      onSignOut();
      return true;
    }
    return false;
  }, [onSignOut]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, h] = await Promise.all([
        getElInsOperatorSummary(DEFAULT_LIMIT),
        health().catch(() => null),
      ]);
      setSummary(s);
      if (h?.version) setVersion(h.version);
    } catch (e: unknown) {
      if (handleAuthError(e)) return;
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, [handleAuthError]);

  useEffect(() => { void load(); }, [load]);

  async function downloadJson() {
    setDownloading("json");
    setError(null);
    try {
      const data = await getElInsExportJson(DEFAULT_LIMIT);
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      triggerDownload(blob, `el_ins_export_${data.operator_id}.json`);
    } catch (e: unknown) {
      if (handleAuthError(e)) return;
      setError(formatError(e));
    } finally {
      setDownloading(null);
    }
  }

  async function downloadPdf() {
    setDownloading("pdf");
    setError(null);
    try {
      const blob = await fetchElInsExportPdfBlob(DEFAULT_LIMIT);
      triggerDownload(blob, "el_ins_export.pdf");
    } catch (e: unknown) {
      if (handleAuthError(e)) return;
      setError(formatError(e));
    } finally {
      setDownloading(null);
    }
  }

  const handleSignOut = () => { clearSession(); onSignOut(); };

  return (
    <DesktopShell
      userName={userName}
      onNavigate={onNavigate}
      activeNav="EL/INS Export"
      sidebar={
        <div style={signOutContainerStyle}>
          <button type="button" onClick={handleSignOut} style={signOutBtnStyle}>
            Sign out
          </button>
        </div>
      }
      center={
        <DesktopAuthGate onRequestSignIn={handleSignOut}>
        <div style={containerStyle}>
          <div style={panelStyle}>
            <h1 style={h1Style}>EL/INS EXPORT</h1>
            <p style={mutedStyle}>
              Portable per-operator export of the last {DEFAULT_LIMIT} EL/INS
              records. JSON for programmatic consumption; PDF for review,
              coaching, and onboarding packets.
            </p>
            {userName ? (
              <div style={authedBadgeStyle}>
                Authed as <span style={authedBadgeNameStyle}>{userName}</span>
              </div>
            ) : null}
            {error ? <div style={bannerStyle}>{error}</div> : null}
          </div>

          <div style={panelStyle}>
            <h2 style={h2Style}>PREVIEW</h2>
            {loading && !summary ? (
              <div>Loading…</div>
            ) : !summary ? (
              <div style={emptyStyle}>No EL/INS data yet for this operator.</div>
            ) : (
              <div style={kvGrid}>
                <div style={kvK}>sample size</div>
                <div style={kvV}>{summary.sample_size}</div>
                <div style={kvK}>avg TSI</div>
                <div style={kvV}>{summary.avg_tsi}/100</div>
                <div style={kvK}>trend</div>
                <div style={kvV}>{summary.trend}</div>
                <div style={kvK}>balanced</div>
                <div style={kvV}>{summary.recent_classification_distribution.balanced}</div>
                <div style={kvK}>high_el</div>
                <div style={kvV}>{summary.recent_classification_distribution.high_el}</div>
                <div style={kvK}>high_ins</div>
                <div style={kvV}>{summary.recent_classification_distribution.high_ins}</div>
              </div>
            )}
          </div>

          <div style={panelStyle}>
            <h2 style={h2Style}>DOWNLOAD</h2>
            <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
              <button
                type="button"
                onClick={() => void downloadJson()}
                disabled={downloading !== null}
                style={btnPrimary}
              >
                {downloading === "json" ? "PREPARING…" : "DOWNLOAD JSON"}
              </button>
              <button
                type="button"
                onClick={() => void downloadPdf()}
                disabled={downloading !== null}
                style={btnPrimary}
              >
                {downloading === "pdf" ? "PREPARING…" : "DOWNLOAD PDF"}
              </button>
            </div>
            <p style={{ ...mutedStyle, fontSize: 11, marginTop: 12 }}>
              ClarityOS backend version <span style={mono}>{version}</span>.
              Exports limited to the {DEFAULT_LIMIT} most-recent records.
            </p>
          </div>
        </div>
        </DesktopAuthGate>
      }
      insights={null}
    />
  );
}

// ---------- helpers ----------
function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function formatError(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.body === "object" && e.body && "detail" in (e.body as Record<string, unknown>)) {
      const d = (e.body as Record<string, unknown>).detail;
      if (typeof d === "string") return d;
    }
    return `${e.code}: ${e.message}`;
  }
  if (e instanceof Error) return e.message;
  return String(e);
}

// ---------- styles ----------
const containerStyle: React.CSSProperties = {
  flex: 1, padding: 24, overflowY: "auto",
  display: "flex", flexDirection: "column", gap: 16,
};
const panelStyle: React.CSSProperties = {
  background: "var(--color-bg-surface)", padding: 16,
};
const h1Style: React.CSSProperties = {
  margin: 0, fontSize: 18, color: "var(--color-text-primary)",
};
const h2Style: React.CSSProperties = {
  margin: "0 0 8px", fontSize: 14, color: "var(--color-text-primary)",
};
const mutedStyle: React.CSSProperties = {
  margin: "4px 0", color: "var(--color-text-secondary)", fontSize: 13,
};
const mono: React.CSSProperties = {
  fontFamily: "monospace", color: "var(--color-text-primary)",
};
const authedBadgeStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--color-text-secondary)", marginTop: 8, letterSpacing: "0.5px",
};
const authedBadgeNameStyle: React.CSSProperties = {
  color: "var(--color-text-primary)", fontFamily: "var(--font-mono)",
};
const btnPrimary: React.CSSProperties = {
  padding: "8px 16px", background: "var(--color-accent-cyan, #00f0ff)",
  border: "none", color: "#000", fontSize: 12, fontWeight: 700, cursor: "pointer",
};
const bannerStyle: React.CSSProperties = {
  marginTop: 8, padding: 8,
  background: "rgba(239,68,68,0.12)", color: "#ef4444", fontSize: 12,
};
const emptyStyle: React.CSSProperties = {
  color: "var(--color-text-secondary)", fontStyle: "italic",
};
const kvGrid: React.CSSProperties = {
  display: "grid", gridTemplateColumns: "auto 1fr", rowGap: 4, columnGap: 12,
  fontSize: 13,
};
const kvK: React.CSSProperties = {
  color: "var(--color-text-secondary)", fontSize: 12,
};
const kvV: React.CSSProperties = {
  color: "var(--color-text-primary)", fontFamily: "var(--font-mono)", fontSize: 12,
};
const signOutContainerStyle: React.CSSProperties = {
  marginTop: "auto", padding: 10,
  borderTop: "1px solid rgba(255,255,255,0.15)",
  display: "flex", justifyContent: "flex-end",
};
const signOutBtnStyle: React.CSSProperties = {
  background: "transparent",
  border: "1px solid var(--color-text-secondary)",
  color: "var(--color-text-secondary)",
  padding: "4px 10px", fontSize: 11, cursor: "pointer", borderRadius: 0,
};
