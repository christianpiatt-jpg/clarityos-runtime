// ClarityOS Mobile — Dashboard global drill-in (v38).

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { elinsDashboard, type V38DashboardSection } from "../lib/api";
import { colors, radius, space } from "../lib/theme";

export default function DashboardGlobalScreen() {
  const [section, setSection] = useState<V38DashboardSection | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const r = await elinsDashboard();
      setSection(r.snapshot.global);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (busy && !section) {
    return <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>;
  }
  if (!section) {
    return <View style={styles.center}><Text style={styles.empty}>{error || "—"}</Text></View>;
  }

  const sortedDomains = Object.entries(section.domains || {})
    .sort((a, b) => b[1] - a[1]).slice(0, 6);
  const ymax = Math.max(0.001, ...sortedDomains.map(([, v]) => v));
  const fcastYmax = Math.max(0.001, ...section.forecast.map(Math.abs));

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>Global</Text>
      <Text style={styles.subtitle}>
        {section.day || "today"} · ESO <Text style={{ color: section.has_eso ? colors.accent : colors.textTertiary }}>
          {section.has_eso ? "on" : "off"}
        </Text>
      </Text>

      {!section.available ? (
        <Text style={styles.empty}>No global run yet</Text>
      ) : (
        <View>
          <View style={styles.card}>
            <Text style={styles.h2}>Summary</Text>
            <Row k="EP mean" v={section.ep_mean.toFixed(3)} />
            <Row k="Top primitive" v={section.top_primitives[0]?.key || "—"} />
            {section.scenario_id && <Row k="Scenario" v={section.scenario_id} mono />}
          </View>

          <View style={styles.card}>
            <Text style={styles.h2}>Top primitives</Text>
            {section.top_primitives.map((p) => (
              <View key={p.key} style={{ marginBottom: 4 }}>
                <View style={styles.kvRow}>
                  <Text style={styles.kvKey}>{p.key}</Text>
                  <Text style={[styles.kvVal, { fontFamily: "Menlo" }]}>{p.intensity.toFixed(3)}</Text>
                </View>
                <View style={styles.barTrack}>
                  <View style={[styles.barFill, { width: `${Math.min(100, p.intensity * 100)}%` }]} />
                </View>
              </View>
            ))}
          </View>

          {sortedDomains.length > 0 && (
            <View style={styles.card}>
              <Text style={styles.h2}>Domain vector</Text>
              {sortedDomains.map(([k, v]) => (
                <View key={k} style={{ marginBottom: 4 }}>
                  <View style={styles.kvRow}>
                    <Text style={styles.kvKey}>{k}</Text>
                    <Text style={[styles.kvVal, { fontFamily: "Menlo" }]}>{v.toFixed(2)}</Text>
                  </View>
                  <View style={styles.barTrack}>
                    <View style={[styles.barFill, { width: `${Math.min(100, (v / ymax) * 100)}%` }]} />
                  </View>
                </View>
              ))}
            </View>
          )}

          {section.forecast.length > 0 && (
            <View style={styles.card}>
              <Text style={styles.h2}>Multi-envelope forecast</Text>
              <View style={styles.forecastRow}>
                {section.forecast.map((v, i) => (
                  <View key={i} style={styles.fcastSlot}>
                    <View
                      style={[styles.fcastBar, {
                        height: Math.max(4, Math.round((Math.abs(v) / fcastYmax) * 60)),
                      }]}
                    />
                    <Text style={styles.fcastLabel}>D+{i}</Text>
                    <Text style={styles.fcastVal}>{v.toFixed(2)}</Text>
                  </View>
                ))}
              </View>
            </View>
          )}

          <Pressable style={styles.linkRow} onPress={() => router.push("/elins_inspector")}>
            <Text style={styles.linkText}>Open ELINS inspector →</Text>
          </Pressable>
        </View>
      )}
    </ScrollView>
  );
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <View style={styles.kvRow}>
      <Text style={styles.kvKey}>{k}</Text>
      <Text style={[styles.kvVal, mono && { fontFamily: "Menlo" }]}>{v}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bgDeep },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600", marginBottom: space.s3 },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s4 },
  card: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.lg, padding: space.s4, marginBottom: space.s3,
  },
  kvRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 2 },
  kvKey: { color: colors.textSecondary, fontSize: 12 },
  kvVal: { color: colors.textPrimary, fontSize: 12 },
  barTrack: { height: 6, backgroundColor: colors.bgDeep, borderRadius: 3, marginTop: 2 },
  barFill: { height: "100%", backgroundColor: colors.accent, borderRadius: 3 },
  forecastRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end", gap: 2 },
  fcastSlot: { flex: 1, alignItems: "center" },
  fcastBar: { width: "75%", backgroundColor: colors.accent, borderTopLeftRadius: radius.sm, borderTopRightRadius: radius.sm },
  fcastLabel: { color: colors.textTertiary, fontSize: 10, marginTop: 4, fontFamily: "Menlo" },
  fcastVal: { color: colors.textSecondary, fontSize: 9, fontFamily: "Menlo" },
  linkRow: { paddingVertical: space.s3, alignItems: "center" },
  linkText: { color: colors.accent, fontSize: 13, fontWeight: "600" },
  empty: { color: colors.textTertiary, fontSize: 12 },
});
