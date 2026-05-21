// ClarityOS Mobile — ELINS dashboard (v38).
// Single-screen intelligence overview. Pulls /elins/dashboard, shows
// compact cards, and routes into the dedicated drill-in surfaces.

import { useCallback, useEffect, useState } from "react";
import {
  Pressable, RefreshControl,
  ScrollView, StyleSheet, Text, View,
} from "react-native";
import { router } from "expo-router";
import { elinsDashboard, type V38DashboardSnapshot } from "../lib/api";
import { colors, radius, space } from "../lib/theme";

const REGION_ORDER = ["US", "EU", "MEA", "APAC", "Markets", "Tech"];

export default function DashboardScreen() {
  const [snapshot, setSnapshot] = useState<V38DashboardSnapshot | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const r = await elinsDashboard();
      setSnapshot(r.snapshot);
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
      <Text style={styles.h1}>ELINS dashboard</Text>
      <Text style={styles.subtitle}>
        v38 · {snapshot ? snapshot.date : "—"} ·
        {snapshot ? ` ${new Date(snapshot.ts * 1000).toISOString().slice(11, 19)}Z` : ""}
      </Text>

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
      )}

      {!snapshot && busy && <DashboardSkeleton />}

      {snapshot && (
        <View>
          {/* Global */}
          <Pressable
            style={styles.card}
            onPress={() => router.push("/dashboard_global")}
          >
            <View style={styles.cardHead}>
              <Text style={styles.cardTitle}>Global</Text>
              <View style={[styles.esoBadge, !snapshot.global.has_eso && styles.esoBadgeOff]}>
                <Text style={[styles.esoText, !snapshot.global.has_eso && styles.esoTextOff]}>
                  {snapshot.global.has_eso ? "ESO" : "ESO off"}
                </Text>
              </View>
            </View>
            {snapshot.global.available ? (
              <View>
                <Row k="EP mean" v={snapshot.global.ep_mean.toFixed(3)} />
                <Row k="Top primitive" v={snapshot.global.top_primitives[0]?.key || "—"} />
                {snapshot.global.forecast.length > 0 && (
                  <MiniBars values={snapshot.global.forecast} />
                )}
              </View>
            ) : (
              <Text style={styles.empty}>No global run yet</Text>
            )}
            <Text style={styles.linkText}>Inspector →</Text>
          </Pressable>

          {/* Regional */}
          <Pressable
            style={styles.card}
            onPress={() => router.push("/dashboard_regional")}
          >
            <Text style={styles.cardTitle}>Regional</Text>
            <View style={styles.regionalGrid}>
              {REGION_ORDER.map((region) => {
                const s = snapshot.regional[region];
                if (!s) return null;
                return (
                  <View key={region} style={styles.regionTile}>
                    <View style={styles.regionTileHead}>
                      <Text style={styles.regionTileName}>{region}</Text>
                      {s.has_eso && <View style={styles.esoDot} />}
                    </View>
                    {s.available ? (
                      <Text style={styles.regionTileVal}>{s.ep_mean.toFixed(2)}</Text>
                    ) : (
                      <Text style={styles.regionTileEmpty}>—</Text>
                    )}
                  </View>
                );
              })}
            </View>
            <Text style={styles.linkText}>Detail →</Text>
          </Pressable>

          {/* Macro */}
          <Pressable
            style={styles.card}
            onPress={() => router.push("/macro_runs")}
          >
            <Text style={styles.cardTitle}>Macro-ELINS</Text>
            {snapshot.macro.last_run_id ? (
              <View>
                <Row k="Last run" v={String(snapshot.macro.last_run_id)} mono />
                <Row k="ESO mode" v={snapshot.macro.external_signal_mode || "—"} />
                <Row k="Regions" v={String(snapshot.macro.regions_count ?? "—")} mono />
              </View>
            ) : (
              <Text style={styles.empty}>No macro runs yet</Text>
            )}
            <Text style={styles.linkText}>All runs →</Text>
          </Pressable>

          {/* Entity graph */}
          <Pressable
            style={styles.card}
            onPress={() => router.push("/dashboard_entities")}
          >
            <Text style={styles.cardTitle}>Entity graph</Text>
            {snapshot.entity_graph.available ? (
              <View>
                <Row k="Entities" v={String(snapshot.entity_graph.entity_count)} mono />
                <Row k="Edges" v={String(snapshot.entity_graph.edge_count)} mono />
                <Text style={[styles.h3, { marginTop: space.s2 }]}>Top entities</Text>
                {snapshot.entity_graph.top_entities.slice(0, 4).map((e) => (
                  <Text key={e.name} style={styles.entityLine}>
                    • {e.name}
                    <Text style={styles.entityMeta}>  deg {e.degree} · ep {e.ep_mean.toFixed(3)}</Text>
                  </Text>
                ))}
              </View>
            ) : (
              <Text style={styles.empty}>No graph yet</Text>
            )}
            <Text style={styles.linkText}>Open graph →</Text>
          </Pressable>
        </View>
      )}
    </ScrollView>
  );
}

function MiniBars({ values }: { values: number[] }) {
  const ymax = Math.max(0.001, ...values.map(Math.abs));
  return (
    <View style={styles.miniBars}>
      {values.map((v, i) => (
        <View
          key={i}
          style={[styles.miniBar, {
            height: Math.max(2, Math.round((Math.abs(v) / ymax) * 24)),
            backgroundColor: colors.accent,
          }]}
        />
      ))}
    </View>
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

function DashboardSkeleton() {
  return (
    <View>
      {[0, 1, 2, 3].map((i) => (
        <View key={i} style={[styles.card, { paddingVertical: space.s4 }]}>
          <View style={skeletonStyles.titleBar} />
          <View style={skeletonStyles.line1} />
          <View style={skeletonStyles.line2} />
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s4, fontFamily: "Menlo" },
  h3: { color: colors.textSecondary, fontSize: 11, fontWeight: "600", textTransform: "uppercase", letterSpacing: 0.5 },
  card: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.lg, padding: space.s4, marginBottom: space.s3,
  },
  cardHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: space.s2 },
  cardTitle: { color: colors.textPrimary, fontSize: 14, fontWeight: "700", marginBottom: space.s2 },
  kvRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 2 },
  kvKey: { color: colors.textSecondary, fontSize: 12 },
  kvVal: { color: colors.textPrimary, fontSize: 12 },
  miniBars: { flexDirection: "row", alignItems: "flex-end", gap: 2, height: 28, marginTop: space.s2 },
  miniBar: { flex: 1, borderTopLeftRadius: radius.sm, borderTopRightRadius: radius.sm },
  regionalGrid: { flexDirection: "row", flexWrap: "wrap", gap: space.s2, marginTop: space.s2 },
  regionTile: {
    flexBasis: "30%", flexGrow: 1,
    backgroundColor: colors.bgDeep, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.sm, padding: space.s2,
  },
  regionTileHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 2 },
  regionTileName: { color: colors.textPrimary, fontSize: 12, fontWeight: "700" },
  regionTileVal: { color: colors.textPrimary, fontSize: 13, fontFamily: "Menlo" },
  regionTileEmpty: { color: colors.textTertiary, fontSize: 11 },
  esoDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.accent },
  esoBadge: {
    paddingHorizontal: 8, paddingVertical: 2, borderRadius: radius.pill,
    borderColor: colors.accent, borderWidth: 1,
  },
  esoBadgeOff: { borderColor: colors.textTertiary },
  esoText: { color: colors.accent, fontSize: 9, fontWeight: "600" },
  esoTextOff: { color: colors.textTertiary },
  entityLine: { color: colors.textPrimary, fontSize: 11, marginTop: 2 },
  entityMeta: { color: colors.textTertiary, fontFamily: "Menlo" },
  linkText: { color: colors.accent, fontSize: 12, fontWeight: "600", marginTop: space.s2 },
  empty: { color: colors.textTertiary, fontSize: 11, fontStyle: "italic" },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});

const skeletonStyles = StyleSheet.create({
  titleBar: { height: 14, width: "30%", backgroundColor: colors.bgDeep, borderRadius: 3, marginBottom: 8 },
  line1: { height: 10, width: "70%", backgroundColor: colors.bgDeep, borderRadius: 3, marginBottom: 6 },
  line2: { height: 10, width: "50%", backgroundColor: colors.bgDeep, borderRadius: 3 },
});
