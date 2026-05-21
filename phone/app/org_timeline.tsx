// v73 / Unit 83 — Phone org timeline.
//
// Three collapsible sections (24h / 7d / 30d), text-only. No modal.
// Founder-cohort gated server-side; non-founder users see an inline
// 403 error banner.

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import {
  ApiError,
  getOrgTimeline,
  getUser,
  type OrgTimelineEntry,
  type OrgTimelineWindow,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";
import AuthGate from "../components/AuthGate";

const WINDOWS: readonly OrgTimelineWindow[] = ["24h", "7d", "30d"] as const;
const LABELS: Record<OrgTimelineWindow, string> = {
  "24h": "Last 24h", "7d": "Last 7d", "30d": "Last 30d",
};

export default function OrgTimelineScreen() {
  return (
    <AuthGate>
      <OrgTimelineScreenInner />
    </AuthGate>
  );
}

function OrgTimelineScreenInner() {
  const authedUser = getUser() || "";
  const [data, setData] = useState<Record<OrgTimelineWindow, OrgTimelineEntry[] | null>>({
    "24h": null, "7d": null, "30d": null,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<OrgTimelineWindow, boolean>>({
    "24h": true, "7d": false, "30d": false,
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const results = await Promise.all(WINDOWS.map((w) => getOrgTimeline(w)));
      const next: Record<OrgTimelineWindow, OrgTimelineEntry[] | null> = {
        "24h": null, "7d": null, "30d": null,
      };
      WINDOWS.forEach((w, i) => { next[w] = results[i].entries; });
      setData(next);
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const toggle = (w: OrgTimelineWindow) => {
    setExpanded((prev) => ({ ...prev, [w]: !prev[w] }));
  };

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.container}>
      <View style={styles.headerPanel}>
        <Text style={styles.h1}>Org Timeline</Text>
        <Text style={styles.muted}>
          Read-only aggregated view. Operator IDs masked; payloads
          summarised. Founder cohort required.
        </Text>
        <Text style={styles.authedBadge}>
          Authed as <Text style={styles.authedBadgeName}>{authedUser}</Text>
        </Text>
      </View>

      {error ? (
        <View style={styles.panel}>
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        </View>
      ) : null}

      {loading && !data["24h"] ? (
        <View style={styles.panel}>
          <ActivityIndicator color={colors.accent} />
        </View>
      ) : (
        WINDOWS.map((w) => (
          <Section
            key={w}
            label={LABELS[w]}
            expanded={expanded[w]}
            onToggle={() => toggle(w)}
            entries={data[w]}
          />
        ))
      )}

      <Pressable
        onPress={() => void load()}
        disabled={loading}
        style={[styles.cta, loading && styles.disabled]}
      >
        <Text style={styles.ctaLabel}>{loading ? "LOADING…" : "REFRESH"}</Text>
      </Pressable>
    </ScrollView>
  );
}

function Section({ label, expanded, onToggle, entries }: {
  label: string; expanded: boolean; onToggle: () => void; entries: OrgTimelineEntry[] | null;
}) {
  return (
    <View style={styles.panel}>
      <Pressable onPress={onToggle} style={styles.sectionHead}>
        <Text style={styles.h2}>{label}</Text>
        <Text style={styles.toggle}>{expanded ? "▼" : "▶"}</Text>
      </Pressable>
      {expanded ? (
        !entries || entries.length === 0 ? (
          <Text style={styles.empty}>No events in this window.</Text>
        ) : (
          entries.map((e, i) => (
            <View key={`${e.timestamp_ms}-${i}`} style={styles.recRow}>
              <View style={styles.recHead}>
                <View style={[styles.dot, { backgroundColor: typeColor(e.event_type) }]} />
                <Text style={styles.recType}>{e.event_type}</Text>
                <Text style={styles.recOp}>{e.operator_id}</Text>
              </View>
              <Text style={styles.recSummary}>{summariseOrgEntry(e)}</Text>
              <Text style={styles.recTs}>{formatTimestamp(e.timestamp_ms)}</Text>
            </View>
          ))
        )
      ) : null}
    </View>
  );
}

function summariseOrgEntry(e: OrgTimelineEntry): string {
  const p = e.payload_summary || {};
  if (e.event_type === "record") {
    const el = typeof p.el === "number" ? (p.el as number).toFixed(2) : "—";
    const ins = typeof p.ins === "number" ? (p.ins as number).toFixed(2) : "—";
    const tsi = typeof p.tsi === "number" ? p.tsi : "—";
    return `EL ${el} · INS ${ins} · TSI ${tsi}`;
  }
  if (e.event_type === "anomaly") {
    const sev = typeof p.severity === "number" ? p.severity : "?";
    const rule = typeof p.rule === "string" ? p.rule : "?";
    return `${rule} · sev ${sev}`;
  }
  if (e.event_type === "rollup") {
    const w = typeof p.window === "string" ? p.window : "?";
    const el = typeof p.avg_el === "number" ? (p.avg_el as number).toFixed(2) : "—";
    const ins = typeof p.avg_ins === "number" ? (p.avg_ins as number).toFixed(2) : "—";
    return `${w} · EL ${el} · INS ${ins}`;
  }
  return "system";
}

function typeColor(t: string): string {
  if (t === "anomaly") return colors.danger;
  if (t === "rollup")  return colors.warning;
  if (t === "record")  return colors.accent;
  return colors.textTertiary;
}

function formatTimestamp(ts_ms: number): string {
  if (!ts_ms) return "—";
  try { return new Date(ts_ms).toISOString().replace("T", " ").slice(0, 19); }
  catch { return String(ts_ms); }
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

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  headerPanel: { backgroundColor: colors.bgSurface, borderRadius: radius.lg, padding: space.s4, marginBottom: space.s3 },
  panel: { backgroundColor: colors.bgSurface, borderRadius: radius.lg, padding: space.s4, marginBottom: space.s3 },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  muted: { color: colors.textSecondary, fontSize: 12, marginTop: 4 },
  authedBadge: { color: colors.textSecondary, fontSize: 11, marginTop: space.s3 },
  authedBadgeName: { color: colors.textPrimary, fontFamily: "Menlo" },
  sectionHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  toggle: { color: colors.textSecondary, fontSize: 12 },
  empty: { color: colors.textSecondary, fontStyle: "italic", marginTop: space.s2 },
  recRow: { paddingVertical: space.s2, borderBottomColor: colors.border, borderBottomWidth: 1 },
  recHead: { flexDirection: "row", alignItems: "center", gap: 8 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  recType: { color: colors.textPrimary, fontWeight: "600", fontSize: 13 },
  recOp: { color: colors.textTertiary, fontFamily: "Menlo", fontSize: 10, marginLeft: "auto" },
  recSummary: { color: colors.textSecondary, fontSize: 12, marginTop: 2 },
  recTs: { color: colors.textTertiary, fontFamily: "Menlo", fontSize: 10, marginTop: 2 },
  cta: { backgroundColor: colors.accent, paddingVertical: 10, borderRadius: radius.pill, alignItems: "center", marginTop: space.s3 },
  ctaLabel: { color: "#04121b", fontWeight: "700", letterSpacing: 0.5 },
  disabled: { opacity: 0.4 },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md },
  errorText: { color: "#ff8a8a", fontSize: 12 },
});
