// components/runtime/EnvelopeRenderer.tsx — deterministic 21-layer envelope walker.
//
// Renders every v6 → v27 envelope layer exactly as the backend provides it.
// No summarization. No embeddings. No inference. Just structured display.
//
// Vectors are pre-stripped server-side (in /runtime/envelope) and arrive as
// `{_vector: true, dim: N}` descriptors, which the renderer shows as a small
// badge. The renderer never reconstitutes or interprets vector floats.

import { useState } from "react";
import type { RuntimeEnvelope, VectorDescriptor } from "../../services/runtime";

interface LayerSpec {
  /** Stable id for keys + collapsed-state map. */
  id: string;
  /** Section heading shown in the UI (versioned for traceability). */
  title: string;
  /** Source field on the envelope. */
  field: keyof RuntimeEnvelope;
  /** Optional one-line note about provenance / spec version. */
  note?: string;
}

// Order matches the v6 → v27 evolve order (lowest → highest).
const LAYERS: LayerSpec[] = [
  { id: "events",                    title: "v6 events",                    field: "events" },
  { id: "episodes",                  title: "v6.5 episodes",                field: "episodes" },
  { id: "narratives",                title: "v7 narratives",                field: "narratives" },
  { id: "story_arcs",                title: "v7 story arcs",                field: "story_arcs" },
  { id: "identity",                  title: "v8 identity",                  field: "identity" },
  { id: "trajectory",                title: "v9 trajectory",                field: "trajectory" },
  { id: "elins",                     title: "v12 ELINS (+ v16 s_strategy)", field: "elins" },
  { id: "universal_physics",         title: "v13 universal_physics",        field: "universal_physics" },
  { id: "coherence",                 title: "v14 coherence",                field: "coherence" },
  { id: "external_context",          title: "v15 external_context",         field: "external_context" },
  { id: "physics_reasoning_context", title: "v17 physics_reasoning_context",field: "physics_reasoning_context" },
  { id: "reasoning_cues",            title: "v18 reasoning_cues",           field: "reasoning_cues" },
  { id: "reasoning_weights",         title: "v19 reasoning_weights",        field: "reasoning_weights" },
  { id: "memory_context",            title: "v20 memory_context",           field: "memory_context" },
  { id: "external_knowledge",        title: "v21 external_knowledge",       field: "external_knowledge" },
  { id: "cognitive_loop",            title: "v22 cognitive_loop",           field: "cognitive_loop" },
  { id: "reasoning_scaffold",        title: "v23 reasoning_scaffold",       field: "reasoning_scaffold" },
  { id: "response_shape",            title: "v24 response_shape",           field: "response_shape" },
  { id: "response_templates",        title: "v25 response_templates",       field: "response_templates" },
  { id: "sentence_operators",        title: "v26 sentence_operators",       field: "sentence_operators" },
  { id: "connective_ops",            title: "v27 connective_ops",           field: "connective_ops" },
];

function isVectorDescriptor(v: unknown): v is VectorDescriptor {
  return typeof v === "object" && v !== null && (v as any)._vector === true;
}

function fmtTs(ts: number | null | undefined): string {
  if (!ts) return "—";
  try { return new Date(Number(ts) * 1000).toISOString().replace("T", " ").slice(0, 19); }
  catch { return String(ts); }
}

function size(v: unknown): number | null {
  if (Array.isArray(v)) return v.length;
  if (v && typeof v === "object") return Object.keys(v as object).length;
  return null;
}

interface EnvelopeRendererProps {
  envelope: RuntimeEnvelope | null;
}

export default function EnvelopeRenderer({ envelope }: EnvelopeRendererProps) {
  if (!envelope) return <div style={{ color: "#999" }}>Loading envelope…</div>;
  return (
    <div className="envelope-renderer">
      <EnvelopeHeader env={envelope} />
      {LAYERS.map((spec) => (
        <LayerSection key={spec.id} spec={spec} value={envelope[spec.field]} />
      ))}
    </div>
  );
}

function EnvelopeHeader({ env }: { env: RuntimeEnvelope }) {
  const ed = env.envelope_decay_ts as number | undefined;
  const lr = env.envelope_last_replay_ts as number | undefined;
  const cu = env.last_centroid_update_ts as number | undefined;
  const drift = env.envelope_drift_events ?? 0;
  const updated = env.updated_at as number | undefined;
  return (
    <div style={{
      padding: 8,
      background: "#f0f0f3",
      borderRadius: 4,
      marginBottom: 12,
      fontSize: 12,
      display: "grid",
      gridTemplateColumns: "auto 1fr",
      gap: "2px 12px",
    }}>
      <span style={{ color: "#666" }}>updated_at</span><strong>{fmtTs(updated)}</strong>
      <span style={{ color: "#666" }}>envelope_decay_ts</span><span>{fmtTs(ed)}</span>
      <span style={{ color: "#666" }}>last_replay_ts</span><span>{fmtTs(lr)}</span>
      <span style={{ color: "#666" }}>last_centroid_update_ts</span><span>{fmtTs(cu)}</span>
      <span style={{ color: "#666" }}>envelope_vector</span>
      <VectorBadge v={env.envelope_vector} />
      <span style={{ color: "#666" }}>envelope_centroid</span>
      <VectorBadge v={env.envelope_centroid} />
      <span style={{ color: "#666" }}>drift_events</span><strong>{drift}</strong>
      <span style={{ color: "#666" }}>elins_briefs</span><strong>{(env.elins_briefs ?? []).length}</strong>
    </div>
  );
}

function VectorBadge({ v }: { v: unknown }) {
  if (v == null) return <span style={{ color: "#999" }}>—</span>;
  if (isVectorDescriptor(v)) {
    return (
      <span style={{
        display: "inline-block",
        padding: "1px 6px",
        background: "#dee",
        borderRadius: 3,
        fontSize: 10,
      }}>
        vector · {v.dim}-dim
      </span>
    );
  }
  return <span style={{ color: "#a55" }}>{String(v)}</span>;
}

function LayerSection({ spec, value }: { spec: LayerSpec; value: unknown }) {
  const [open, setOpen] = useState(false);
  const present = value !== undefined && value !== null;
  const sz = size(value);

  return (
    <details
      open={open}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
      style={{
        border: "1px solid #e0e0e0",
        borderRadius: 4,
        marginBottom: 6,
        background: present ? "#fff" : "#fafafa",
      }}
    >
      <summary style={{
        cursor: "pointer",
        padding: "6px 10px",
        fontSize: 13,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}>
        <span>
          <strong>{spec.title}</strong>
          {!present && <span style={{ color: "#bbb", marginLeft: 6 }}>(absent)</span>}
        </span>
        <span style={{ fontSize: 11, color: "#888" }}>
          {sz !== null ? `${sz} ${Array.isArray(value) ? "items" : "keys"}` : present ? "scalar" : ""}
        </span>
      </summary>
      {open && present && (
        <div style={{ padding: "8px 10px 10px" }}>
          <LayerBody value={value} />
        </div>
      )}
    </details>
  );
}

/**
 * LayerBody — generic structural renderer. For dicts of dicts, shows a small
 * key/scalar table; for arrays of dicts, shows a compact list of items;
 * otherwise falls through to a `<pre>` JSON dump (still deterministic — no
 * summarization). Vectors are always rendered as descriptor badges.
 */
function LayerBody({ value }: { value: unknown }) {
  if (Array.isArray(value)) {
    if (value.length === 0) return <em style={{ color: "#999" }}>(empty list)</em>;
    return (
      <div style={{ fontSize: 12 }}>
        <div style={{ color: "#666", marginBottom: 4 }}>{value.length} items</div>
        {value.slice(0, 25).map((v, i) => (
          <div key={i} style={{ borderBottom: "1px dotted #eee", padding: "2px 0" }}>
            <ScalarOrPreview value={v} />
          </div>
        ))}
        {value.length > 25 && <div style={{ color: "#999", marginTop: 4 }}>…{value.length - 25} more</div>}
      </div>
    );
  }

  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).sort();
    return (
      <div style={{
        display: "grid",
        gridTemplateColumns: "auto 1fr",
        gap: "2px 10px",
        fontSize: 12,
      }}>
        {entries.map(([k, v]) => (
          <span key={k} style={{ display: "contents" }}>
            <span style={{ color: "#666" }}>{k}</span>
            <span><ScalarOrPreview value={v} /></span>
          </span>
        ))}
      </div>
    );
  }

  return <ScalarOrPreview value={value} />;
}

function ScalarOrPreview({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span style={{ color: "#999" }}>—</span>;
  if (isVectorDescriptor(value)) return <VectorBadge v={value} />;
  if (typeof value === "boolean") {
    return (
      <span style={{
        display: "inline-block",
        padding: "0 6px",
        background: value ? "#e6f5ec" : "#fde2e2",
        color: value ? "#147" : "#922",
        borderRadius: 3,
        fontSize: 11,
      }}>
        {value ? "true" : "false"}
      </span>
    );
  }
  if (typeof value === "number") {
    // Heuristic: large numbers that look like POSIX seconds → render as ts.
    if (value > 1_000_000_000 && value < 4_000_000_000) {
      return <span title="POSIX seconds">{fmtTs(value)}</span>;
    }
    return <code>{value}</code>;
  }
  if (typeof value === "string") return <span>{value}</span>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <em style={{ color: "#999" }}>[]</em>;
    return (
      <span style={{ fontSize: 11 }}>
        [{value.slice(0, 6).map((v, i) => (
          <span key={i}>
            {i > 0 ? ", " : ""}<ScalarOrPreview value={v} />
          </span>
        ))}{value.length > 6 ? `, …(+${value.length - 6})` : ""}]
      </span>
    );
  }
  // dict — show one-line preview of the keys.
  const keys = Object.keys(value as object);
  return (
    <span style={{ fontSize: 11, color: "#444" }}>
      {`{ ${keys.slice(0, 4).join(", ")}${keys.length > 4 ? `, …(+${keys.length - 4})` : ""} }`}
    </span>
  );
}
