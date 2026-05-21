// ClarityOS Mobile — Entity detail (v37).
// Shows the entity summary + neighbours; tap a neighbour to drill into it.

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View,
} from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import {
  elinsEntityNeighbors,
  type V37EntityNeighbor, type V37EntitySummary,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";

export default function EntityDetailScreen() {
  const params = useLocalSearchParams<{ entity?: string }>();
  const entity = (params.entity as string) || "";
  const [summary, setSummary] = useState<V37EntitySummary | null>(null);
  const [neighbors, setNeighbors] = useState<V37EntityNeighbor[]>([]);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!entity) return;
    setBusy(true); setError(null);
    try {
      const r = await elinsEntityNeighbors(entity, 30);
      setSummary(r.summary); setNeighbors(r.neighbors);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, [entity]);

  useEffect(() => { void load(); }, [load]);

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>{entity}</Text>
      <Pressable
        onPress={() => router.push({ pathname: "/entity_timeseries", params: { entity } })}
        style={styles.linkRow}
      >
        <Text style={styles.linkText}>EP timeseries →</Text>
      </Pressable>

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
      )}

      {summary && (
        <View style={styles.card}>
          <Text style={styles.h2}>Summary</Text>
          <Row k="Degree" v={String(summary.degree)} />
          <Row k="EP mean" v={summary.ep_mean.toFixed(3)} />
          <Row k="Clusters" v={(summary.clusters || []).join(", ") || "—"} />
          {Object.keys(summary.domains || {}).length > 0 && (
            <View style={{ marginTop: space.s2 }}>
              <Text style={styles.h3}>Top domains</Text>
              {Object.entries(summary.domains)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 6)
                .map(([k, v]) => (
                  <Row key={k} k={k} v={v.toFixed(2)} />
                ))}
            </View>
          )}
        </View>
      )}

      <View style={styles.card}>
        <Text style={styles.h2}>Neighbors ({neighbors.length})</Text>
        {busy && neighbors.length === 0 ? (
          <ActivityIndicator color={colors.accent} />
        ) : neighbors.length === 0 ? (
          <Text style={styles.empty}>None</Text>
        ) : (
          neighbors.map((n) => (
            <Pressable
              key={n.name}
              style={styles.neighbor}
              onPress={() =>
                router.push({ pathname: "/entity_detail", params: { entity: n.name } })
              }
            >
              <View style={styles.neighborHead}>
                <Text style={styles.neighborTitle}>{n.name}</Text>
                <Text style={styles.neighborMeta}>w {n.weight.toFixed(2)} · co {n.co_occurrences}</Text>
              </View>
              {n.top_domains.length > 0 && (
                <Text style={styles.neighborSub}>{n.top_domains.join(" · ")}</Text>
              )}
            </Pressable>
          ))
        )}
      </View>
    </ScrollView>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <View style={styles.kvRow}>
      <Text style={styles.kvKey}>{k}</Text>
      <Text style={styles.kvVal}>{v}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  h1: { color: colors.textPrimary, fontSize: 20, fontWeight: "700" },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600", marginBottom: space.s3 },
  h3: { color: colors.textSecondary, fontSize: 11, fontWeight: "600", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 4 },
  card: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.lg, padding: space.s4, marginBottom: space.s4,
  },
  kvRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 3 },
  kvKey: { color: colors.textSecondary, fontSize: 12 },
  kvVal: { color: colors.textPrimary, fontSize: 12, fontFamily: "Menlo" },
  neighbor: {
    paddingVertical: space.s2, borderTopColor: colors.border, borderTopWidth: 1,
  },
  neighborHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" },
  neighborTitle: { color: colors.textPrimary, fontSize: 12, fontWeight: "600", flex: 1 },
  neighborMeta: { color: colors.textTertiary, fontSize: 10, fontFamily: "Menlo" },
  neighborSub: { color: colors.textSecondary, fontSize: 10, marginTop: 2 },
  empty: { color: colors.textTertiary, fontSize: 11, fontStyle: "italic" },
  linkRow: { paddingVertical: space.s2, alignItems: "flex-start" },
  linkText: { color: colors.accent, fontSize: 13, fontWeight: "600" },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
