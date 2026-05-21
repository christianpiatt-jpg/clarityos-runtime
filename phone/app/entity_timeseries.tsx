// ClarityOS Mobile — Entity EP timeseries (v37).
// Bar series of EP-mean per appearance. Uses RN View bars (no SVG dep).

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { elinsEntityTimeseries, type V37EntityAppearance } from "../lib/api";
import { colors, radius, space } from "../lib/theme";

export default function EntityTimeseriesScreen() {
  const params = useLocalSearchParams<{ entity?: string }>();
  const entity = (params.entity as string) || "";
  const [series, setSeries] = useState<V37EntityAppearance[]>([]);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!entity) return;
    setBusy(true); setError(null);
    try {
      const r = await elinsEntityTimeseries(entity);
      setSeries(r.timeseries);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, [entity]);

  useEffect(() => { void load(); }, [load]);

  const ymax = Math.max(0.001, ...series.map((s) => s.ep_mean));

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>{entity}</Text>
      <Text style={styles.subtitle}>EP timeseries · {series.length} appearances</Text>

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
      )}

      {busy && series.length === 0 && <ActivityIndicator color={colors.accent} />}

      {series.length > 0 && (
        <View style={styles.card}>
          <Text style={styles.h2}>EP-mean per appearance</Text>
          <View style={styles.bars}>
            {series.map((s, i) => (
              <View key={`${s.ts}-${i}`} style={styles.slot}>
                <View
                  style={[styles.bar, {
                    height: Math.max(4, Math.round((s.ep_mean / ymax) * 60)),
                    backgroundColor: colors.accent,
                  }]}
                />
                <Text style={styles.barTick}>{i + 1}</Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {series.slice().reverse().map((a, i) => (
        <View key={i} style={styles.appCard}>
          <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
            <Text style={styles.appTs}>{fmtTs(a.ts)}</Text>
            <Text style={styles.appCluster}>[{a.cluster}]</Text>
          </View>
          <Text style={styles.appEp}>ep_mean {a.ep_mean.toFixed(3)}</Text>
          {Object.keys(a.domains).length > 0 && (
            <Text style={styles.appDomains}>
              {Object.keys(a.domains).slice(0, 4).join(" · ")}
            </Text>
          )}
        </View>
      ))}
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
  h1: { color: colors.textPrimary, fontSize: 20, fontWeight: "700" },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s4 },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600", marginBottom: space.s3 },
  card: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.lg, padding: space.s4, marginBottom: space.s3,
  },
  appCard: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.md, padding: space.s3, marginBottom: space.s2,
  },
  bars: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end", gap: 2 },
  slot: { flex: 1, alignItems: "center" },
  bar: { width: "75%", borderTopLeftRadius: radius.sm, borderTopRightRadius: radius.sm },
  barTick: { color: colors.textTertiary, fontSize: 9, marginTop: 4, fontFamily: "Menlo" },
  appTs: { color: colors.textSecondary, fontSize: 11, fontFamily: "Menlo" },
  appCluster: { color: colors.textTertiary, fontSize: 11 },
  appEp: { color: colors.textPrimary, fontSize: 12, fontFamily: "Menlo", marginTop: 2 },
  appDomains: { color: colors.textTertiary, fontSize: 10, marginTop: 2 },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
