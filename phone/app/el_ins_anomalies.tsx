// v72 / Unit 80 — Phone anomalies screen.
//
// Tap-to-expand list of detected anomalies. AuthGate-wrapped.

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
  getElInsAnomalies,
  getUser,
  type ElInsAnomaly,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";
import AuthGate from "../components/AuthGate";

export default function ElInsAnomaliesScreen() {
  return (
    <AuthGate>
      <ElInsAnomaliesScreenInner />
    </AuthGate>
  );
}

function ElInsAnomaliesScreenInner() {
  const authedUser = getUser() || "";
  const [anomalies, setAnomalies] = useState<ElInsAnomaly[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await getElInsAnomalies(100);
      setAnomalies(r.anomalies);
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
        <Text style={styles.h1}>EL/INS Anomalies</Text>
        <Text style={styles.muted}>
          Tap a row to expand. Triggered by EL &gt; 7.5, INS &lt; 2.0,
          TSI &gt; 85, or a quadrant jump.
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
        {loading && !anomalies ? (
          <ActivityIndicator color={colors.accent} />
        ) : !anomalies || anomalies.length === 0 ? (
          <Text style={styles.empty}>No anomalies on record.</Text>
        ) : (
          anomalies.map((a) => (
            <Pressable
              key={a.id}
              onPress={() => toggle(a.id)}
              style={styles.recRow}
            >
              <View style={styles.recHead}>
                <View style={[styles.sevDot, { backgroundColor: sevColor(a.severity) }]} />
                <Text style={styles.recType}>{a.type}</Text>
                <Text style={styles.recSev}>sev {a.severity}</Text>
              </View>
              <Text style={styles.recMessage}>{a.message}</Text>
              {expanded.has(a.id) ? (
                <View style={styles.expanded}>
                  <Text style={styles.recMono}>timestamp · {formatTimestamp(a.timestamp)}</Text>
                  <Text style={styles.recMono}>thread · {a.thread_id || "none"}</Text>
                  <Text style={styles.recMono}>record · {a.record_id}</Text>
                  <Text style={styles.recMono}>id · {a.id}</Text>
                </View>
              ) : null}
            </Pressable>
          ))
        )}
      </View>
    </ScrollView>
  );
}

function sevColor(n: number): string {
  if (n >= 5) return colors.danger;
  if (n >= 4) return colors.warning;
  return colors.success;
}

function formatTimestamp(ts: number): string {
  if (!ts) return "—";
  try { return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 19); }
  catch { return String(ts); }
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
  sevDot: { width: 8, height: 8, borderRadius: 4 },
  recType: { color: colors.textPrimary, fontWeight: "600", fontSize: 13 },
  recSev: { color: colors.textSecondary, fontSize: 11, marginLeft: "auto" },
  recMessage: { color: colors.textSecondary, fontSize: 12, marginTop: 4 },
  expanded: { marginTop: 6, paddingTop: 6, borderTopColor: colors.border, borderTopWidth: 1 },
  recMono: { color: colors.textTertiary, fontFamily: "Menlo", fontSize: 10, marginTop: 2 },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md },
  errorText: { color: "#ff8a8a", fontSize: 12 },
});
