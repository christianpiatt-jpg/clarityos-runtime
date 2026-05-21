// v73 / Unit 82 — Phone operator timeline.
//
// Tap-to-expand event list. AuthGate-wrapped. No modal — inline
// expansion only per spec.

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
  getTimeline,
  getUser,
  type TimelineEvent,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";
import AuthGate from "../components/AuthGate";

export default function TimelineScreen() {
  return (
    <AuthGate>
      <TimelineScreenInner />
    </AuthGate>
  );
}

function TimelineScreenInner() {
  const authedUser = getUser() || "";
  const [events, setEvents] = useState<TimelineEvent[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await getTimeline(200);
      setEvents(r.events);
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const toggle = (id: string) => {
    const next = new Set(expanded);
    if (next.has(id)) next.delete(id); else next.add(id);
    setExpanded(next);
  };

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.container}>
      <View style={styles.headerPanel}>
        <Text style={styles.h1}>Timeline</Text>
        <Text style={styles.muted}>
          Chronological log of EL/INS records, anomalies, and roll-ups.
          Tap a row to expand the payload.
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

      <View style={styles.panel}>
        <View style={styles.rowBetween}>
          <Text style={styles.h2}>RECENT</Text>
          <Pressable
            onPress={() => void load()}
            disabled={loading}
            style={styles.btnSecondary}
          >
            <Text style={styles.btnSecondaryLabel}>REFRESH</Text>
          </Pressable>
        </View>
        {loading && !events ? (
          <ActivityIndicator color={colors.accent} />
        ) : !events || events.length === 0 ? (
          <Text style={styles.empty}>No timeline events yet.</Text>
        ) : (
          events.map((e) => (
            <Pressable
              key={e.id}
              onPress={() => toggle(e.id)}
              style={styles.recRow}
            >
              <View style={styles.recHead}>
                <View style={[styles.dot, { backgroundColor: typeColor(e.event_type) }]} />
                <Text style={styles.recType}>{e.event_type}</Text>
                <Text style={styles.recTs}>{formatTimestamp(e.timestamp_ms)}</Text>
              </View>
              <Text style={styles.recSummary}>{summariseEvent(e)}</Text>
              {expanded.has(e.id) ? (
                <View style={styles.expanded}>
                  <Text style={styles.recMono} numberOfLines={20}>
                    {JSON.stringify(e.payload, null, 2)}
                  </Text>
                </View>
              ) : null}
            </Pressable>
          ))
        )}
      </View>
    </ScrollView>
  );
}

function summariseEvent(e: TimelineEvent): string {
  const p = e.payload || {};
  if (e.event_type === "record") {
    const el = typeof p.el === "number" ? (p.el as number).toFixed(2) : "—";
    const ins = typeof p.ins === "number" ? (p.ins as number).toFixed(2) : "—";
    const tsi = typeof p.tsi === "number" ? p.tsi : null;
    const parts = [`EL ${el}`, `INS ${ins}`];
    if (tsi !== null) parts.push(`TSI ${tsi}`);
    return parts.join(" · ");
  }
  if (e.event_type === "anomaly") {
    const sev = typeof p.severity === "number" ? p.severity : "?";
    const t = typeof p.type === "string" ? p.type : "?";
    return `${t} · sev ${sev}`;
  }
  if (e.event_type === "rollup") {
    const w = typeof p.window === "string" ? p.window : "?";
    const el = typeof p.avg_el === "number" ? (p.avg_el as number).toFixed(2) : "—";
    const ins = typeof p.avg_ins === "number" ? (p.avg_ins as number).toFixed(2) : "—";
    return `${w} · EL ${el} · INS ${ins}`;
  }
  return "system event";
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
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: space.s3 },
  btnSecondary: { paddingVertical: 6, paddingHorizontal: 10, borderRadius: radius.pill, borderColor: colors.border, borderWidth: 1 },
  btnSecondaryLabel: { color: colors.textSecondary, fontSize: 11, fontWeight: "600" },
  empty: { color: colors.textSecondary, fontStyle: "italic" },
  recRow: { paddingVertical: space.s2, borderBottomColor: colors.border, borderBottomWidth: 1 },
  recHead: { flexDirection: "row", alignItems: "center", gap: 8 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  recType: { color: colors.textPrimary, fontWeight: "600", fontSize: 13 },
  recTs: { color: colors.textSecondary, fontFamily: "Menlo", fontSize: 10, marginLeft: "auto" },
  recSummary: { color: colors.textSecondary, fontSize: 12, marginTop: 4 },
  expanded: { marginTop: 6, paddingTop: 6, borderTopColor: colors.border, borderTopWidth: 1 },
  recMono: { color: colors.textTertiary, fontFamily: "Menlo", fontSize: 10 },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md },
  errorText: { color: "#ff8a8a", fontSize: 12 },
});
