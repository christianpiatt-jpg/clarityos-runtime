// components/runtime/EnvelopeRenderer.tsx (phone) — deterministic 21-layer
// envelope walker. Mirrors web/src/components/runtime/EnvelopeRenderer.tsx.
// No summarization, no embeddings, no inference.

import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type { RuntimeEnvelope, VectorDescriptor } from "../../lib/services/runtime";
import { colors, geometry, spacing, typography } from "../../lib/designSystem";

interface LayerSpec {
  id: string;
  title: string;
  field: keyof RuntimeEnvelope;
}

const LAYERS: LayerSpec[] = [
  { id: "events",                    title: "v6 events",                    field: "events" },
  { id: "episodes",                  title: "v6.5 episodes",                field: "episodes" },
  { id: "narratives",                title: "v7 narratives",                field: "narratives" },
  { id: "story_arcs",                title: "v7 story arcs",                field: "story_arcs" },
  { id: "identity",                  title: "v8 identity",                  field: "identity" },
  { id: "trajectory",                title: "v9 trajectory",                field: "trajectory" },
  { id: "elins",                     title: "v12 ELINS (+ v16)",            field: "elins" },
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

function sizeOf(v: unknown): number | null {
  if (Array.isArray(v)) return v.length;
  if (v && typeof v === "object") return Object.keys(v as object).length;
  return null;
}

function fmtTs(ts: number | null | undefined): string {
  if (!ts) return "—";
  try { return new Date(Number(ts) * 1000).toISOString().replace("T", " ").slice(0, 19); }
  catch { return String(ts); }
}

export interface EnvelopeRendererProps { envelope: RuntimeEnvelope | null; }

export default function EnvelopeRenderer({ envelope }: EnvelopeRendererProps) {
  if (!envelope) return <Text style={styles.dim}>Loading envelope…</Text>;
  return (
    <ScrollView style={{ maxHeight: 600 }}>
      <View style={styles.headerBox}>
        <KV k="updated_at" v={fmtTs(envelope.updated_at as number | undefined)} />
        <KV k="envelope_decay_ts" v={fmtTs(envelope.envelope_decay_ts)} />
        <KV k="envelope_vector" v={vectorBadge(envelope.envelope_vector)} />
        <KV k="envelope_centroid" v={vectorBadge(envelope.envelope_centroid)} />
        <KV k="drift_events" v={String(envelope.envelope_drift_events ?? 0)} />
        <KV k="elins_briefs" v={String((envelope.elins_briefs ?? []).length)} />
      </View>
      {LAYERS.map((spec) => (
        <LayerSection key={spec.id} spec={spec} value={envelope[spec.field]} />
      ))}
    </ScrollView>
  );
}

function KV({ k, v }: { k: string; v: string }) {
  return (
    <View style={styles.kvRow}>
      <Text style={styles.kvKey}>{k}</Text>
      <Text style={styles.kvVal}>{v}</Text>
    </View>
  );
}

function vectorBadge(v: unknown): string {
  if (v == null) return "—";
  if (isVectorDescriptor(v)) return `vector · ${v.dim}-dim`;
  return String(v);
}

function LayerSection({ spec, value }: { spec: LayerSpec; value: unknown }) {
  const [open, setOpen] = useState(false);
  const present = value !== undefined && value !== null;
  const sz = sizeOf(value);
  const subtitle = sz !== null
    ? `${sz} ${Array.isArray(value) ? "items" : "keys"}`
    : present ? "scalar" : "(absent)";

  return (
    <View style={[styles.layer, !present && styles.layerAbsent]}>
      <Pressable onPress={() => setOpen((o) => !o)} style={styles.layerHeader}>
        <Text style={styles.layerTitle}>{spec.title}</Text>
        <Text style={styles.layerSub}>{subtitle}</Text>
      </Pressable>
      {open && present && <LayerBody value={value} />}
    </View>
  );
}

function LayerBody({ value }: { value: unknown }) {
  if (Array.isArray(value)) {
    if (value.length === 0) return <Text style={styles.dim}>(empty list)</Text>;
    return (
      <View style={styles.body}>
        <Text style={styles.dim}>{value.length} items</Text>
        {value.slice(0, 10).map((v, i) => (
          <View key={i} style={styles.bodyRow}>
            <Text style={styles.body12}>{previewLine(v)}</Text>
          </View>
        ))}
        {value.length > 10 && <Text style={styles.dim}>…{value.length - 10} more</Text>}
      </View>
    );
  }
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).sort();
    return (
      <View style={styles.body}>
        {entries.map(([k, v]) => (
          <View key={k} style={styles.kvRow}>
            <Text style={styles.kvKey}>{k}</Text>
            <Text style={styles.kvVal}>{previewLine(v)}</Text>
          </View>
        ))}
      </View>
    );
  }
  return <Text style={styles.body12}>{previewLine(value)}</Text>;
}

function previewLine(v: unknown): string {
  if (v == null) return "—";
  if (isVectorDescriptor(v)) return `vector · ${v.dim}-dim`;
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number") {
    if (v > 1_000_000_000 && v < 4_000_000_000) return fmtTs(v);
    return String(v);
  }
  if (typeof v === "string") return v;
  if (Array.isArray(v)) {
    if (v.length === 0) return "[]";
    return "[" + v.slice(0, 4).map(previewLine).join(", ") + (v.length > 4 ? `, …(+${v.length - 4})` : "") + "]";
  }
  const keys = Object.keys(v as object);
  return "{ " + keys.slice(0, 4).join(", ") + (keys.length > 4 ? `, …(+${keys.length - 4})` : "") + " }";
}

const styles = StyleSheet.create({
  dim: { ...typography.body16, color: colors.darkGrey, fontSize: 12 },
  headerBox: {
    padding: spacing.gridGap,
    backgroundColor: colors.deepGrey,
    borderRadius: geometry.radius4,
    marginBottom: spacing.gridGap,
  },
  kvRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 1 },
  kvKey: { ...typography.body16, color: colors.lightGrey, fontSize: 11 },
  kvVal: { ...typography.body16, color: colors.white, fontSize: 11, fontFamily: "monospace" },
  layer: {
    borderWidth: 1,
    borderColor: colors.neutralGrey,
    borderRadius: geometry.radius4,
    marginBottom: 4,
    backgroundColor: colors.deepGrey,
  },
  layerAbsent: { opacity: 0.5 },
  layerHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: spacing.gridGap,
  },
  layerTitle: { ...typography.body16, color: colors.white, fontSize: 13, fontWeight: "600" },
  layerSub: { ...typography.body16, color: colors.darkGrey, fontSize: 11 },
  body: { padding: spacing.gridGap, paddingTop: 0 },
  bodyRow: { paddingVertical: 1 },
  body12: { ...typography.body16, color: colors.white, fontSize: 12 },
});
