// ClarityOS Mobile — operator timeline (v39).
// ELINS + #G history (metadata-only) for the current user.
//
// v66 / Unit 70 — wrapped in AuthGate so unauthed visits show an
// inline CTA instead of a 401 banner.

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, RefreshControl,
  ScrollView, StyleSheet, Text, View,
} from "react-native";
import { meOperatorState, type V39OperatorState } from "../lib/api";
import { colors, radius, space } from "../lib/theme";
import AuthGate from "../components/AuthGate";

export default function OperatorTimelineScreen() {
  return (
    <AuthGate>
      <OperatorTimelineScreenInner />
    </AuthGate>
  );
}

function OperatorTimelineScreenInner() {
  const [state, setState] = useState<V39OperatorState | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const r = await meOperatorState();
      setState(r.state);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (busy && !state) {
    return <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>;
  }
  const elinsRows = state ? [...state.elins_history].sort((a, b) => b.ts - a.ts) : [];
  const gRows = state ? [...state.g_history].sort((a, b) => b.ts - a.ts) : [];

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={styles.container}
      refreshControl={<RefreshControl refreshing={busy} onRefresh={load} tintColor={colors.accent} />}
    >
      <Text style={styles.h1}>Timeline</Text>
      <Text style={styles.subtitle}>{elinsRows.length} ELINS · {gRows.length} #G</Text>

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
      )}

      <Text style={styles.sectionHeader}>ELINS</Text>
      {elinsRows.length === 0 ? (
        <Text style={styles.empty}>No ELINS interactions yet</Text>
      ) : (
        elinsRows.map((row, i) => (
          <View key={`e-${row.ts}-${i}`} style={styles.card}>
            <View style={styles.cardHead}>
              <Text style={styles.cardTitle}>{row.region || "global"}</Text>
              <Text style={styles.cardMeta}>{fmtTs(row.ts)}</Text>
            </View>
            {!!row.topic && <Text style={styles.cardTopic}>{row.topic}</Text>}
            <Text style={styles.cardCode}>{row.kind} · {row.elins_id || "—"}</Text>
          </View>
        ))
      )}

      <Text style={[styles.sectionHeader, { marginTop: space.s4 }]}>#G</Text>
      {gRows.length === 0 ? (
        <Text style={styles.empty}>No #G runs yet</Text>
      ) : (
        gRows.map((row, i) => (
          <View key={`g-${row.ts}-${i}`} style={styles.card}>
            <View style={styles.cardHead}>
              <Text style={styles.cardTitle}>#{row.mode}</Text>
              <Text style={styles.cardMeta}>{fmtTs(row.ts)}</Text>
            </View>
            {!!row.topic && <Text style={styles.cardTopic}>{row.topic}</Text>}
            {!!row.g_id && <Text style={styles.cardCode}>{row.g_id}</Text>}
          </View>
        ))
      )}
    </ScrollView>
  );
}

function fmtTs(ts: number): string {
  if (!ts || ts <= 0) return "—";
  return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 19);
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bgDeep },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s4 },
  sectionHeader: { color: colors.textSecondary, fontSize: 11, fontWeight: "600", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: space.s2 },
  card: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.md, padding: space.s3, marginBottom: space.s2,
  },
  cardHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" },
  cardTitle: { color: colors.textPrimary, fontSize: 13, fontWeight: "700" },
  cardMeta: { color: colors.textTertiary, fontSize: 10, fontFamily: "Menlo" },
  cardTopic: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
  cardCode: { color: colors.textTertiary, fontSize: 10, marginTop: 2 },
  empty: { color: colors.textTertiary, fontSize: 12, fontStyle: "italic", marginBottom: space.s3 },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
