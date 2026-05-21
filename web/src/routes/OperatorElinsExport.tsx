// v71 / Unit 78 — EL/INS export route.
//
// Two download buttons (JSON + PDF) plus a preview of the latest
// summary stats and the running build + backend version footer.
// Authgated via RequireAuth at the App.tsx route layer.

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  config,
  fetchElInsExportPdfBlob,
  getElInsExportJson,
  getElInsOperatorSummary,
  type ElInsOperatorSummaryResponse,
} from "../lib/api";

const DEFAULT_LIMIT = 200;

export default function OperatorElinsExport() {
  const [summary, setSummary] = useState<ElInsOperatorSummaryResponse | null>(null);
  const [version, setVersion] = useState<string>("…");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<"json" | "pdf" | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, c] = await Promise.all([
        getElInsOperatorSummary(DEFAULT_LIMIT),
        config().catch(() => null),
      ]);
      setSummary(s);
      // /config returns { data: { version, ... } }. Either version
      // is acceptable in the footer; pick whichever lands.
      const cfg = c?.data;
      if (cfg?.version) setVersion(cfg.version);
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, []);

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
      triggerDownload(blob, `el_ins_export.pdf`);
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div>
      <div className="panel">
        <h1>EL/INS EXPORT</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Portable per-operator export of the last {DEFAULT_LIMIT} EL/INS
          records. JSON for programmatic consumption; PDF for review,
          coaching, and onboarding packets.
        </p>
        {error ? (
          <div className="banner err" style={{ marginTop: 8 }} data-testid="el-ins-export-error">
            {error}
          </div>
        ) : null}
      </div>

      <div className="panel" data-testid="el-ins-export-summary">
        <h2>PREVIEW</h2>
        {loading && !summary ? (
          <div><span className="spinner" /> Loading…</div>
        ) : !summary ? (
          <div className="empty">No EL/INS data yet for this operator.</div>
        ) : (
          <div className="kv">
            <div className="k">sample size</div>
            <div className="v">{summary.sample_size}</div>
            <div className="k">avg TSI</div>
            <div className="v">{summary.avg_tsi}/100</div>
            <div className="k">trend</div>
            <div className="v">{summary.trend}</div>
            <div className="k">balanced</div>
            <div className="v">{summary.recent_classification_distribution.balanced}</div>
            <div className="k">high_el</div>
            <div className="v">{summary.recent_classification_distribution.high_el}</div>
            <div className="k">high_ins</div>
            <div className="v">{summary.recent_classification_distribution.high_ins}</div>
          </div>
        )}
      </div>

      <div className="panel">
        <h2>DOWNLOAD</h2>
        <div className="row" style={{ gap: 12, marginTop: 8 }}>
          <button
            type="button"
            className="btn"
            onClick={() => void downloadJson()}
            disabled={downloading !== null}
            data-testid="el-ins-export-json-btn"
          >
            {downloading === "json" ? "PREPARING…" : "DOWNLOAD JSON"}
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => void downloadPdf()}
            disabled={downloading !== null}
            data-testid="el-ins-export-pdf-btn"
          >
            {downloading === "pdf" ? "PREPARING…" : "DOWNLOAD PDF"}
          </button>
        </div>
        <p className="muted" style={{ marginTop: 12, fontSize: 11 }}>
          ClarityOS backend version <code data-testid="el-ins-export-version">{version}</code>.
          Exports limited to the {DEFAULT_LIMIT} most-recent records.
        </p>
      </div>
    </div>
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
  // Revoke after a tick so the browser has time to start the download.
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
