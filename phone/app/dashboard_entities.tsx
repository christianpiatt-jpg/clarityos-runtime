// ClarityOS Mobile — Dashboard entity-graph drill-in (v38).

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { elinsDashboard, type V38DashboardSnapshot } from "../lib/api";
import { colors, radius, space } from "../lib/theme";

export default function DashboardEntitiesScreen() {
  const [graph, setGraph] = useState<V38DashboardSnapshot["entity_graph"] | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const r = await elinsDashboard();
      setGraph(r.snapshot.entity_graph);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (busy && !graph) {
    return <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>;
  }

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>Entity graph</Text>
      <Text style={styles.subtitle}>
        v38 · top entities {graph?.entity_count ?? 0} · edges {graph?.edge_count ?? 0}
      </Text>

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
      )}

      <Pressable
        style={styles.linkRow}
        onPress={() => router.push("/entities")}
      >
        <Text style={styles.linkText}>Open full graph search →</Text>
      </Pressable>

      {graph?.available ? (
        <View>
          <Text style={[styles.h2, { marginTop: space.s4 }]}>Top entities</Text>
          {graph.top_entities.map((e) => (
            <Pressable
              key={e.name}
              style={styles.card}
              onPress={() =>
                router.push({ pathname: "/entity_detail", params: { entity: e.name } })
              }
            >
              <View style={styles.cardHead}>
                <Text style={styles.cardTitle}>{e.name}</Text>
                <Text style={styles.cardMeta}>deg {e.degree}</Text>
              </View>
              <Text style={styles.cardLine}>ep {e.ep_mean.toFixed(3)}</Text>
              {e.top_domains.length > 0 && (
                <Text style={styles.cardSub}>{e.top_domains.join(" · ")}</Text>
              )}
            </Pressable>
          ))}
          {graph.top_entities.length === 0 && (
            <Text style={styles.empty}>No entities yet</Text>
          )}
        </View>
      ) : (
        <Text style={styles.empty}>No graph snapshot yet</Text>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bgDeep },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s4 },
  card: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.md, padding: space.s4, marginBottom: space.s3, marginTop: space.s2,
  },
  cardHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" },
  cardTitle: { color: colors.textPrimary, fontSize: 13, fontWeight: "700", flex: 1, marginRight: space.s2 },
  cardMeta: { color: colors.textTertiary, fontSize: 11, fontFamily: "Menlo" },
  cardLine: { color: colors.textSecondary, fontSize: 11, marginTop: 2, fontFamily: "Menlo" },
  cardSub: { color: colors.textTertiary, fontSize: 10, marginTop: 2 },
  linkRow: { paddingVertical: space.s2, alignItems: "flex-start" },
  linkText: { color: colors.accent, fontSize: 13, fontWeight: "600" },
  empty: { color: colors.textTertiary, fontSize: 12 },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
