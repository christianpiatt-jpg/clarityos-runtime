// ClarityOS Mobile — Founder analytics (v43).
// Founder-only summary of users / billing / intelligence metrics.

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, Pressable, RefreshControl,
  ScrollView, StyleSheet, Text, View,
} from "react-native";
import {
  founderAnalyticsSummary,
  type V43FounderAnalyticsSummary,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";

export default function FounderAnalyticsScreen() {
  const [data, setData] = useState<V43FounderAnalyticsSummary | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const r = await founderAnalyticsSummary();
      setData(r.summary);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={styles.container}
      refreshControl={<RefreshControl refreshing={busy} onRefresh={load} tintColor={colors.accent} />}
    >
      <Text style={styles.h1}>Founder analytics</Text>
      <Text style={styles.subtitle}>v43 · users · billing · intelligence</Text>

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
      )}

      {!data && busy && (
        <ActivityIndicator color={colors.accent} style={{ marginTop: space.s4 }} />
      )}

      {data && (
        <View>
          <View style={styles.card}>
            <Text style={styles.h2}>Users</Text>
            <Row k="Total" v={String(data.users.total)} />
            <BarRow label="Active 7d" value={data.users.active_7d} max={Math.max(1, data.users.total)} />
            <BarRow label="Active 30d" value={data.users.active_30d} max={Math.max(1, data.users.total)} />
          </View>

          <View style={styles.card}>
            <View style={styles.headerRow}>
              <Text style={styles.h2}>Billing</Text>
              <ModePill mode={data.billing.mode} />
            </View>
            <Row k="Active subs" v={String(data.billing.active_subscriptions)} />
            <Row k="Past due" v={String(data.billing.past_due)} warn={data.billing.past_due > 0} />
            <Row k="Canceled" v={String(data.billing.canceled)} />
          </View>

          <View style={styles.card}>
            <Text style={styles.h2}>Intelligence (7d)</Text>
            <Row k="ELINS runs" v={String(data.intelligence.elins_runs_7d)} />
            <Row k="#G runs" v={String(data.intelligence.g_runs_7d)} />
            <Row k="Macro runs" v={String(data.intelligence.macro_runs_7d)} />
            <RateBar label="ESO usage" rate={data.intelligence.eso_usage_rate_7d} />
          </View>

          <Text style={styles.metaText}>
            v43 · {new Date(data.ts * 1000).toISOString().slice(0, 19).replace("T", " ")}
          </Text>
        </View>
      )}
    </ScrollView>
  );
}

function Row({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <View style={styles.kvRow}>
      <Text style={styles.kvKey}>{k}</Text>
      <Text style={[
        styles.kvVal,
        warn && { color: colors.danger, fontWeight: "600" },
      ]}>{v}</Text>
    </View>
  );
}

function BarRow({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = Math.min(100, Math.round((value / Math.max(1, max)) * 100));
  return (
    <View style={{ marginVertical: 4 }}>
      <View style={styles.kvRow}>
        <Text style={styles.kvKey}>{label}</Text>
        <Text style={styles.kvVal}>{value} <Text style={styles.muted}>/ {max}</Text></Text>
      </View>
      <View style={styles.barTrack}>
        <View style={[styles.barFill, { width: `${pct}%` }]} />
      </View>
    </View>
  );
}

function RateBar({ label, rate }: { label: string; rate: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, rate)) * 100);
  return (
    <View style={{ marginVertical: 4 }}>
      <View style={styles.kvRow}>
        <Text style={styles.kvKey}>{label}</Text>
        <Text style={styles.kvVal}>{pct}%</Text>
      </View>
      <View style={styles.barTrack}>
        <View style={[styles.barFill, { width: `${pct}%`, backgroundColor: "#fbbf24" }]} />
      </View>
    </View>
  );
}

function ModePill({ mode }: { mode: "test" | "live" | "disabled" }) {
  const palette: Record<string, [string, string]> = {
    live: ["#dc2626", "#fff"],
    test: ["#2563eb", "#fff"],
    disabled: ["#6b7280", "#fff"],
  };
  const [bg, fg] = palette[mode] || palette.disabled;
  return (
    <View style={{
      backgroundColor: bg, paddingHorizontal: 10, paddingVertical: 3,
      borderRadius: radius.pill,
    }}>
      <Text style={{ color: fg, fontSize: 10, fontWeight: "700", letterSpacing: 0.5 }}>
        {mode.toUpperCase()}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s4 },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600", marginBottom: space.s3 },
  card: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.lg, padding: space.s4, marginBottom: space.s3,
  },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: space.s2 },
  kvRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 2 },
  kvKey: { color: colors.textSecondary, fontSize: 12 },
  kvVal: { color: colors.textPrimary, fontSize: 12, fontFamily: "Menlo" },
  muted: { color: colors.textTertiary },
  barTrack: { height: 5, backgroundColor: colors.bgDeep, borderRadius: 3, marginTop: 2 },
  barFill: { height: "100%", backgroundColor: colors.accent, borderRadius: 3 },
  metaText: {
    color: colors.textTertiary, fontSize: 10, fontFamily: "Menlo",
    textAlign: "right", marginTop: space.s2,
  },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
