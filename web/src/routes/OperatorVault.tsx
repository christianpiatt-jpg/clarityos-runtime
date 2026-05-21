// OperatorVault — read-only inspector over /operator/vault/{operator_id}.
//
// Route is /operator-vault rather than /vault because the v1 storage
// layer already owns /vault (Vault.tsx for the legacy GCS-backed file
// vault). This route's "vault" is the runtime ELINS vault from the
// v60 persistence layer — different concept, different storage.
//
// UI: operator-id input + REFRESH + collapsible JSON viewer +
// last_updated stamp. No mutation, no save.

import { useEffect, useState } from "react";
import {
  ApiError,
  getOperatorVault,
  getUser,
  type VaultInspectorResponse,
} from "../lib/api";

export default function OperatorVault() {
  // v64 / Unit 66 — operator_id determined server-side from authed
  // session. Shown read-only.
  const operatorId = getUser() || "(not signed in)";
  const [data, setData] = useState<VaultInspectorResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const r = await getOperatorVault(operatorId);
        if (!cancelled) setData(r);
      } catch (e: unknown) {
        if (!cancelled) setError(formatError(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [operatorId]);

  function refresh() {
    setLoading(true);
    void (async () => {
      try {
        const r = await getOperatorVault(operatorId);
        setData(r);
      } catch (e: unknown) {
        setError(formatError(e));
      } finally {
        setLoading(false);
      }
    })();
  }

  return (
    <div>
      <div className="panel">
        <h1>OPERATOR VAULT</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Read-only snapshot of the operator's runtime vault — the ELINS
          long-arc state that <code>session_loop.step_session</code>
          persists between steps. Distinct from the legacy{" "}
          <code>/vault</code> file-storage surface.
        </p>
        <div className="row" style={{ marginTop: 12, gap: 8, alignItems: "center" }}>
          <div style={{ flex: 1, fontSize: "0.85rem" }}>
            <span className="muted">authed as </span>
            <span style={{ fontFamily: "var(--font-mono)" }}>{operatorId}</span>
          </div>
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={refresh}
            disabled={loading}
          >
            REFRESH
          </button>
        </div>
        {error ? (
          <div className="banner err" style={{ marginTop: 8 }}>{error}</div>
        ) : null}
      </div>

      <div className="panel">
        <div className="row row-between" style={{ marginBottom: 8 }}>
          <h2 style={{ margin: 0 }}>VAULT</h2>
          <span className="muted" style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}>
            {data?.last_updated ? `updated ${data.last_updated}` : "never updated"}
          </span>
        </div>
        {loading ? (
          <div><span className="spinner" /> Loading…</div>
        ) : !data || data.vault === null ? (
          <div className="empty">
            No vault recorded for this operator yet. Run a /session step
            to populate.
          </div>
        ) : (
          <JsonTree value={data.vault} depth={0} />
        )}
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------
// Tiny collapsible JSON viewer — recursive, click-to-toggle on object
// and array nodes. Primitive values render inline. Doesn't depend on
// any library; the existing /web tree has no JSON-tree dep and we
// don't want to add one for this single surface.
// ----------------------------------------------------------------------
interface JsonTreeProps {
  value:  unknown;
  depth:  number;
  label?: string;
}

function JsonTree({ value, depth, label }: JsonTreeProps) {
  const pad = depth * 16;
  const labelEl = label !== undefined ? (
    <span style={{ color: "var(--os-text-secondary, #888)" }}>{label}: </span>
  ) : null;

  if (value === null) {
    return (
      <div style={{ marginLeft: pad, fontFamily: "var(--font-mono)" }}>
        {labelEl}<span style={{ color: "var(--os-warn, #f59e0b)" }}>null</span>
      </div>
    );
  }
  if (typeof value === "string") {
    return (
      <div style={{ marginLeft: pad, fontFamily: "var(--font-mono)" }}>
        {labelEl}<span style={{ color: "var(--os-ok, #10b981)" }}>"{value}"</span>
      </div>
    );
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return (
      <div style={{ marginLeft: pad, fontFamily: "var(--font-mono)" }}>
        {labelEl}<span style={{ color: "var(--os-focus, #00f0ff)" }}>{String(value)}</span>
      </div>
    );
  }
  if (Array.isArray(value)) {
    return <ArrayNode value={value} depth={depth} label={label} />;
  }
  if (typeof value === "object") {
    return <ObjectNode value={value as Record<string, unknown>} depth={depth} label={label} />;
  }
  return (
    <div style={{ marginLeft: pad }}>
      {labelEl}<span>{String(value)}</span>
    </div>
  );
}

function ObjectNode({
  value, depth, label,
}: { value: Record<string, unknown>; depth: number; label?: string }) {
  // Default: top level open, deeper levels closed.
  const [open, setOpen] = useState<boolean>(depth < 1);
  const keys = Object.keys(value);
  const pad = depth * 16;
  return (
    <div style={{ marginLeft: pad, fontFamily: "var(--font-mono)" }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          background: "transparent",
          border: "none",
          color: "inherit",
          cursor: "pointer",
          padding: 0,
          font: "inherit",
        }}
        aria-expanded={open}
      >
        <span style={{ color: "var(--os-text-secondary, #888)" }}>
          {open ? "▾" : "▸"}{" "}
        </span>
        {label !== undefined ? (
          <span style={{ color: "var(--os-text-secondary, #888)" }}>{label}: </span>
        ) : null}
        <span>{`{ ${keys.length} key${keys.length === 1 ? "" : "s"} }`}</span>
      </button>
      {open ? (
        <div>
          {keys.map((k) => (
            <JsonTree key={k} value={value[k]} depth={depth + 1} label={k} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ArrayNode({
  value, depth, label,
}: { value: unknown[]; depth: number; label?: string }) {
  const [open, setOpen] = useState<boolean>(depth < 1);
  const pad = depth * 16;
  return (
    <div style={{ marginLeft: pad, fontFamily: "var(--font-mono)" }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          background: "transparent",
          border: "none",
          color: "inherit",
          cursor: "pointer",
          padding: 0,
          font: "inherit",
        }}
        aria-expanded={open}
      >
        <span style={{ color: "var(--os-text-secondary, #888)" }}>
          {open ? "▾" : "▸"}{" "}
        </span>
        {label !== undefined ? (
          <span style={{ color: "var(--os-text-secondary, #888)" }}>{label}: </span>
        ) : null}
        <span>{`[ ${value.length} item${value.length === 1 ? "" : "s"} ]`}</span>
      </button>
      {open ? (
        <div>
          {value.map((v, i) => (
            <JsonTree key={i} value={v} depth={depth + 1} label={String(i)} />
          ))}
        </div>
      ) : null}
    </div>
  );
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
