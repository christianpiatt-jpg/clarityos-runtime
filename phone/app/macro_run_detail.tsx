// ClarityOS Mobile — Macro-ELINS run detail (v36).

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { founderMacroRunDetail, type V36MacroRunDetail } from "../lib/api";
import { colors, radius, space } from "../lib/theme";

export default function MacroRunDetailScreen() {
  const params = useLocalSearchParams<{ run_id?: string }>();
  const runId = (params.run_id as string) || "";
  const [run, setRun] = useState<V36MacroRunDetail | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!runId) return;
    setBusy(true); setError(null);
    try {
      const r = await founderMacroRunDetail(runId);
      setRun(r.run);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, [runId]);

  useEffect(() => { void load(); }, [load]);

  if (busy && !run) {
    return (
      <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>
    );
  }

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>Macro run</Text>
      <Text style={styles.subtitle}>{runId}</Text>

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
      )}

      {run && (
        <View>
          <View style={styles.card}>
            <Text style={styles.h2}>Summary</Text>
            <Row k="ts" v={new Date(run.ts * 1000).toISOString().replace("T", " ").slice(0, 19)} />
            <Row k="regions" v={String(run.regions.length)} />
            <Row k="ESO mode" v={String(run.external_signal_mode || "—")} />
            {run.notes && <Row k="notes" v={run.notes} />}
          </View>

          <View style={styles.card}>
            <Text style={styles.h2}>Global run</Text>
            <Row k="run_id" v={String(run.global_run_ref?.run_id || "—")} />
            <Row k="scenario_id" v={String(run.global_run_ref?.scenario_id || "—")} />
          </View>

          <View style={styles.card}>
            <Text style={styles.h2}>Regional runs</Text>
            {Object.keys(run.regional_runs || {}).length === 0 ? (
              <Text style={styles.empty}>None</Text>
            ) : (
              Object.entries(run.regional_runs || {}).map(([region, r]) => {
                const summary = (r?.summary as Record<string, unknown> | undefined) || {};
                return (
                  <View key={region} style={styles.regionalRow}>
                    <Text style={styles.regionalKey}>{region}</Text>
                    <Text style={styles.regionalLine}>
                      top: <Text style={styles.regionalEm}>{String(summary.top_primitive ?? "—")}</Text>
                    </Text>
                    <Text style={styles.regionalLine}>
                      signal: <Text style={styles.regionalEm}>{String(summary.signal ?? "—")}</Text>
                    </Text>
                  </View>
                );
              })
            )}
          </View>
        </View>
      )}
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
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bgDeep },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s4, fontFamily: "Menlo" },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600", marginBottom: space.s3 },
  card: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.lg, padding: space.s4, marginBottom: space.s4,
  },
  kvRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 3 },
  kvKey: { color: colors.textSecondary, fontSize: 12 },
  kvVal: { color: colors.textPrimary, fontSize: 12, fontFamily: "Menlo" },
  regionalRow: {
    paddingVertical: space.s2, borderTopColor: colors.border, borderTopWidth: 1,
  },
  regionalKey: { color: colors.textPrimary, fontSize: 13, fontWeight: "700" },
  regionalLine: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
  regionalEm: { color: colors.textPrimary, fontWeight: "600" },
  empty: { color: colors.textTertiary, fontSize: 11, fontStyle: "italic" },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
