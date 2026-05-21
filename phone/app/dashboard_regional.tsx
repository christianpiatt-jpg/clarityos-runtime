// ClarityOS Mobile — Dashboard regional drill-in (v38).

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { elinsDashboard, type V38DashboardSection } from "../lib/api";
import { colors, radius, space } from "../lib/theme";

const REGION_ORDER = ["US", "EU", "MEA", "APAC", "Markets", "Tech"];

export default function DashboardRegionalScreen() {
  const [regional, setRegional] = useState<Record<string, V38DashboardSection> | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const r = await elinsDashboard();
      setRegional(r.snapshot.regional);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (busy && !regional) {
    return <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>;
  }

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>Regional</Text>
      <Text style={styles.subtitle}>v38 · 6 basins</Text>

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
      )}

      {regional && REGION_ORDER.map((region) => {
        const s = regional[region];
        if (!s) return null;
        const ymax = Math.max(0.001, ...s.forecast.map(Math.abs));
        return (
          <Pressable
            key={region}
            style={styles.card}
            onPress={() =>
              router.push({ pathname: "/regional_detail", params: { region } })
            }
          >
            <View style={styles.cardHead}>
              <Text style={styles.cardTitle}>{region}</Text>
              {s.has_eso && (
                <View style={styles.esoBadge}>
                  <Text style={styles.esoText}>ESO</Text>
                </View>
              )}
            </View>
            {s.available ? (
              <View>
                <Row k="EP mean" v={s.ep_mean.toFixed(3)} />
                <Row k="Top primitive" v={s.top_primitives[0]?.key || "—"} />
                <Row k="Day" v={s.day || "—"} mono />
                {s.forecast.length > 0 && (
                  <View style={styles.miniBars}>
                    {s.forecast.map((v, i) => (
                      <View
                        key={i}
                        style={[styles.miniBar, {
                          height: Math.max(2, Math.round((Math.abs(v) / ymax) * 28)),
                        }]}
                      />
                    ))}
                  </View>
                )}
              </View>
            ) : (
              <Text style={styles.empty}>No runs yet</Text>
            )}
            <Text style={styles.linkText}>Detail →</Text>
          </Pressable>
        );
      })}
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
  subtitle: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s4 },
  card: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.lg, padding: space.s4, marginBottom: space.s3,
  },
  cardHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: space.s2 },
  cardTitle: { color: colors.textPrimary, fontSize: 15, fontWeight: "700" },
  kvRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 2 },
  kvKey: { color: colors.textSecondary, fontSize: 12 },
  kvVal: { color: colors.textPrimary, fontSize: 12 },
  miniBars: { flexDirection: "row", alignItems: "flex-end", gap: 2, height: 32, marginTop: space.s2 },
  miniBar: { flex: 1, backgroundColor: colors.accent, borderTopLeftRadius: radius.sm, borderTopRightRadius: radius.sm },
  esoBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: radius.pill, borderColor: colors.accent, borderWidth: 1 },
  esoText: { color: colors.accent, fontSize: 9, fontWeight: "600" },
  linkText: { color: colors.accent, fontSize: 12, fontWeight: "600", marginTop: space.s2 },
  empty: { color: colors.textTertiary, fontSize: 11, fontStyle: "italic" },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
