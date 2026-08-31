// web/src/components/v1/EmotionalPhysicsView/EmotionalPhysicsView.tsx
//
// Web mirror of desktop EmotionalPhysicsView.tsx. Verbatim copy — the
// relative imports (../../../lib/emotionalPhysics, ../../../lib/api)
// resolve identically in both projects.
//
// Compact Emotional Physics view for the v1 InsightsPanel. Renders the
// four layers (field_curvature / edge_pressure / relational_primitives /
// external_expression) returned by /me/emotional_physics/analyze (v52)
// as a structural summary — not a debug dump. 320px-width compatible.

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

/** Is this rendered value prose rather than a reading?
 *
 *  .paramValue carries tabular numerals, right alignment and
 *  white-space: nowrap + text-overflow: ellipsis. That is correct for
 *  "0.847" and "high". On a sentence it cuts mid-word -- CT-1 saw
 *  next_step render as "Deliver a complete, organized r" -- while a
 *  full-width column sat empty to its left.
 *
 *  Enum members never contain a space ("partially_aligned"), and the
 *  array joiner packs one-to-three bullet sentences into a single
 *  value, so length plus a space separates the two cleanly. Both
 *  classes already exist; this only chooses between them. */
function isProse(v: string): boolean {
  return /\s/.test(v) && v.length > 28;
}

/** When was this reading ANALYSED — not when was it fetched.
 *
 *  ★★ THE BUG THIS REPLACES. The state below was initialised with
 *  `response ? Date.now() : null`. ThreadInsightsPanel mounts this view only
 *  while its Physics tab is selected, so tabbing away and back UNMOUNTS and
 *  REMOUNTS it, the initialiser re-fires, and a reading up to four turns old
 *  is stamped "updated just now". Looking at the panel is what required the
 *  tab, so the false timestamp appeared every single time anyone checked.
 *
 *  ★ `_meta.ts_ms` is the kernel's own stamp, set at
 *  intelligence_kernel.py:1877 as `int(time.time() * 1000)` and returned in
 *  every response. VERIFIED POPULATED by generation 2026-08-28 against a live
 *  run: a real epoch-ms integer matching wall clock. It survives caching and
 *  remounting because it travels with the reading.
 *
 *  Returns null when the response carries no stamp — the caller then shows
 *  nothing rather than inventing a time. ★ A missing timestamp and a fresh
 *  one must not render the same. */
function analysedAtMs(resp: EmotionalPhysicsResponse | null | undefined): number | null {
  const raw = resp?._meta?.ts_ms;
  return typeof raw === "number" && Number.isFinite(raw) && raw > 0 ? raw : null;
}

export default function EmotionalPhysicsView({ response, text, onAnalyze }: Props) {
  const [view, setView] = useState<EmotionalPhysicsResponse | null>(response ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // ★ NOT Date.now(). See analysedAtMs above — stamping the clock here is
  // exactly what made a four-turn-old reading claim to be current.
  const [updatedAtMs, setUpdatedAtMs] = useState<number | null>(
    analysedAtMs(response),
  );

  const canRerun = typeof text === "string" && text.trim().length > 0;

  const doRun = useCallback(async () => {
    if (!canRerun || !text) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await analyzeEmotionalPhysics({ text });
      setView(resp);
      // Even on a genuinely fresh run the reading's own stamp is preferable:
      // it is the time the ANALYSIS happened, not the time the promise
      // resolved. Date.now() is the fallback only when the kernel sent none.
      setUpdatedAtMs(analysedAtMs(resp) ?? Date.now());
      onAnalyze?.(resp);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [canRerun, text, onAnalyze]);

  useEffect(() => {
    if (response || !canRerun) return;
    void doRun();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (response) {
      setView(response);
      // ★ This fires whenever the parent hands back a CACHED reading. Using
      // the clock here re-dated stale physics on every tab switch.
      setUpdatedAtMs(analysedAtMs(response));
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
        {/* ★ No stamp renders nothing at all, rather than a reassuring
            "updated just now". A missing timestamp is not a fresh one. */}
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

  let narrative: string | null = null;
  for (const k of NARRATIVE_KEYS) {
    const v = data[k];
    if (typeof v === "string" && v.trim().length > 0) {
      narrative = v.trim();
      break;
    }
  }

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
              <dd
                className={isProse(v) ? styles.narrative : styles.paramValue}
                title={v}
              >
                {v}
              </dd>
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
