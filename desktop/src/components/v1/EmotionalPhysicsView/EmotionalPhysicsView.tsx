// desktop/src/components/v1/EmotionalPhysicsView/EmotionalPhysicsView.tsx
//
// Compact Emotional Physics view for the v1 InsightsPanel. Renders the
// four layers (field / trajectory / stress / relief) returned by
// /me/emotional_physics/analyze (v52) as a structural summary — not a
// debug dump. 320px-width compatible (no fixed widths, no horizontal
// scroll, no large numbers).
//
// Two modes:
//   - controlled:   caller passes `response` directly (e.g., from an
//                   already-stored ingestion-bus output). Component
//                   renders and offers Re-analyze if `text` is also
//                   given.
//   - uncontrolled: caller passes `text` only. Component fetches on
//                   mount and on every Re-analyze click.
//
// Layer field shapes are intentionally permissive in the API client
// (Record<string, unknown>) because the model layers evolve. The
// renderer here normalizes that into:
//   - a key/value list of primitive params, and
//   - one optional short narrative line picked from a small set of
//     reserved keys (note / interpretation / summary / description /
//     narrative). First match wins; the chosen key is suppressed from
//     the param list to avoid duplication.
//
// No new charting libraries.

import { Fragment, useCallback, useEffect, useState } from "react";
import {
  analyzeEmotionalPhysics,
  type EmotionalPhysicsResponse,
} from "../../../lib/emotionalPhysics";
import { ApiError } from "../../../lib/api";
import styles from "./EmotionalPhysicsView.module.css";

interface Props {
  /** Pre-computed response (controlled mode). */
  response?: EmotionalPhysicsResponse | null;
  /** Text to analyze. If omitted, component is controlled-only. */
  text?: string | null;
  /** Optional callback fired on every successful analysis. */
  onAnalyze?: (resp: EmotionalPhysicsResponse) => void;
}

// Canonical v52 layer keys. Must match the backend's
// _EMOTIONAL_PHYSICS_KEYS in intelligence_kernel.py exactly.
const LAYER_ORDER = [
  "field_curvature",
  "edge_pressure",
  "relational_primitives",
  "external_expression",
] as const;
type LayerKey = (typeof LAYER_ORDER)[number];

const LAYER_LABEL: Record<LayerKey, string> = {
  field_curvature:       "Field curvature",
  edge_pressure:         "Edge pressure",
  relational_primitives: "Relational primitives",
  external_expression:   "External expression",
};

// Reserved keys that, when present in a layer object, are rendered as
// the layer's short interpretive text. First match in this order wins.
//
// ``notes`` is the canonical narrative field per the v52 prompt schema
// (every layer in the spec ends with "notes: <plain-language summary>").
// The others are tolerant fallbacks for shape drift.
const NARRATIVE_KEYS = [
  "notes",
  "note",
  "interpretation",
  "summary",
  "description",
  "narrative",
] as const;
const NARRATIVE_KEY_SET: ReadonlySet<string> = new Set(NARRATIVE_KEYS);

export default function EmotionalPhysicsView({ response, text, onAnalyze }: Props) {
  const [view, setView] = useState<EmotionalPhysicsResponse | null>(response ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatedAtMs, setUpdatedAtMs] = useState<number | null>(
    response ? Date.now() : null,
  );

  const canRerun = typeof text === "string" && text.trim().length > 0;

  const doRun = useCallback(async () => {
    if (!canRerun || !text) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await analyzeEmotionalPhysics({ text });
      setView(resp);
      setUpdatedAtMs(Date.now());
      onAnalyze?.(resp);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [canRerun, text, onAnalyze]);

  // Auto-fetch on mount when uncontrolled.
  useEffect(() => {
    if (response || !canRerun) return;
    void doRun();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-sync when response prop changes.
  useEffect(() => {
    if (response) {
      setView(response);
      setUpdatedAtMs(Date.now());
      setError(null);
    }
  }, [response]);

  if (!view && loading) {
    return (
      <section className={styles.root} aria-label="Emotional Physics view loading">
        <Heading title="Emotional Physics" subtitle="analyzing…" />
      </section>
    );
  }

  if (!view) {
    return (
      <section className={styles.root} aria-label="Emotional Physics view">
        <Heading title="Emotional Physics" subtitle={error ?? "no payload"} />
        {canRerun ? (
          <button
            type="button"
            className={styles.actionBtn}
            onClick={doRun}
            disabled={loading}
          >
            {loading ? "analyzing…" : "Analyze"}
          </button>
        ) : null}
      </section>
    );
  }

  const meta = view._meta ?? {};
  const modelId = typeof meta.model_id === "string" ? meta.model_id : null;
  const parseError = typeof meta.parse_error === "string" ? meta.parse_error : null;

  return (
    <section className={styles.root} aria-label="Emotional Physics view">
      <Heading
        title="Emotional Physics"
        subtitle={modelId ? `model: ${modelId}` : undefined}
      />

      {parseError ? (
        <div role="status" className={styles.warning}>
          parse error: {parseError}
        </div>
      ) : null}

      {LAYER_ORDER.map((key) => (
        <LayerBlock
          key={key}
          label={LAYER_LABEL[key]}
          data={view[key] as Record<string, unknown> | undefined}
        />
      ))}

      <footer className={styles.footer}>
        {updatedAtMs ? (
          <span className={styles.updatedAt}>
            updated {relativeTime(updatedAtMs)}
          </span>
        ) : null}
        {canRerun ? (
          <button
            type="button"
            className={styles.actionBtn}
            onClick={doRun}
            disabled={loading}
            aria-label="Re-analyze emotional physics"
          >
            {loading ? "analyzing…" : "Re-analyze"}
          </button>
        ) : null}
      </footer>

      {error ? (
        <div role="alert" className={styles.error}>
          {error}
        </div>
      ) : null}
    </section>
  );
}

// -----------------------------------------------------------------
// Sub-blocks
// -----------------------------------------------------------------

function Heading({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className={styles.heading}>
      <span className={styles.title}>{title}</span>
      {subtitle ? <span className={styles.subtitle}>{subtitle}</span> : null}
    </header>
  );
}

function LayerBlock({
  label, data,
}: {
  label: string;
  data: Record<string, unknown> | undefined;
}) {
  if (!data) {
    return (
      <div className={styles.layer}>
        <div className={styles.layerLabel}>{label}</div>
        <div className={styles.empty}>—</div>
      </div>
    );
  }

  // Resolve a single narrative string (first match wins).
  let narrative: string | null = null;
  for (const k of NARRATIVE_KEYS) {
    const v = data[k];
    if (typeof v === "string" && v.trim().length > 0) {
      narrative = v.trim();
      break;
    }
  }

  // Collect primitive param rows, skipping the chosen narrative key
  // and rendering nested-object/array keys as terse cardinality stubs.
  const params: Array<[string, string]> = [];
  for (const [k, v] of Object.entries(data)) {
    if (NARRATIVE_KEY_SET.has(k)) continue;
    if (v === null || v === undefined) continue;
    if (typeof v === "string") {
      params.push([k, v]);
    } else if (typeof v === "number") {
      params.push([k, formatNumber(v)]);
    } else if (typeof v === "boolean") {
      params.push([k, v ? "true" : "false"]);
    } else if (Array.isArray(v)) {
      // Short primitive arrays inline as comma-joined; everything else
      // collapses to a cardinality stub. Matches PersonalElinsShell's
      // renderValue heuristic so the two surfaces read the same.
      const allPrim = v.every(
        (x) => typeof x === "string" || typeof x === "number" || typeof x === "boolean",
      );
      if (allPrim && v.length > 0 && v.length <= 4) {
        params.push([k, v.map(String).join(", ")]);
      } else {
        params.push([k, `[${v.length}]`]);
      }
    } else if (typeof v === "object") {
      const keys = Object.keys(v as Record<string, unknown>);
      params.push([k, `{${keys.length}}`]);
    }
  }

  if (params.length === 0 && !narrative) {
    return (
      <div className={styles.layer}>
        <div className={styles.layerLabel}>{label}</div>
        <div className={styles.empty}>—</div>
      </div>
    );
  }

  return (
    <div className={styles.layer}>
      <div className={styles.layerLabel}>{label}</div>
      {params.length > 0 ? (
        <dl className={styles.paramGrid}>
          {params.map(([k, v]) => (
            <Fragment key={k}>
              <dt className={styles.paramKey}>{k}</dt>
              <dd className={styles.paramValue} title={v}>{v}</dd>
            </Fragment>
          ))}
        </dl>
      ) : null}
      {narrative ? (
        <div className={styles.narrative}>{narrative}</div>
      ) : null}
    </div>
  );
}

// -----------------------------------------------------------------
// Utils
// -----------------------------------------------------------------

function formatNumber(n: number): string {
  if (!isFinite(n)) return "—";
  if (Number.isInteger(n)) return String(n);
  const abs = Math.abs(n);
  if (abs >= 1000) return n.toFixed(0);
  if (abs >= 100)  return n.toFixed(1);
  if (abs >= 10)   return n.toFixed(2);
  return n.toFixed(3);
}

function relativeTime(tsMs: number): string {
  const diff = Date.now() - tsMs;
  if (diff < 0) return "just now";
  const s = Math.floor(diff / 1000);
  if (s < 5)  return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}
