// ClarityOS Mobile — Macro-ELINS run list (v36).

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import {
  founderMacroRunsList, founderMacroRunNow,
  type V36MacroRun,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";

export default function MacroRunsScreen() {
  const [rows, setRows] = useState<V36MacroRun[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy("load"); setError(null);
    try {
      const r = await founderMacroRunsList(20);
      setRows(r.runs);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const runNow = useCallback(async () => {
    setBusy("run"); setError(null);
    try {
      const r = await founderMacroRunNow();
      if (r.summary.ran && r.summary.run_id) {
        router.push({ pathname: "/macro_run_detail", params: { run_id: r.summary.run_id } });
      }
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, [load]);

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={styles.container}
      refreshControl={<RefreshControl refreshing={busy === "load"} onRefresh={load} tintColor={colors.accent} />}
    >
      <Text style={styles.h1}>Macro-ELINS</Text>
      <Text style={styles.subtitle}>v36 scheduler · {rows.length} runs</Text>

      <View style={styles.row}>
        <Pressable
          onPress={() => void runNow()}
          disabled={busy !== null}
          style={[styles.cta, busy !== null && styles.disabled]}
        >
          <Text style={styles.ctaLabel}>
            {busy === "run" ? <ActivityIndicator color="#04121b" /> : "Run macro now"}
          </Text>
        </Pressable>
        <Pressable
          onPress={() => router.push("/macro_scheduler_config")}
          style={styles.btnGhost}
        >
          <Text style={styles.btnGhostLabel}>Scheduler config</Text>
        </Pressable>
      </View>

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
      )}

      {rows.length === 0 ? (
        <Text style={styles.empty}>{busy === "load" ? "Loading…" : "No macro runs yet."}</Text>
      ) : (
        rows.map((r) => {
          const date = new Date(r.ts * 1000).toISOString().replace("T", " ").slice(0, 19);
          return (
            <Pressable
              key={r.run_id}
              style={styles.card}
              onPress={() => router.push({ pathname: "/macro_run_detail", params: { run_id: r.run_id } })}
            >
              <Text style={styles.cardTitle}>{r.run_id}</Text>
              <Text style={styles.cardLine}>{date}</Text>
              <Text style={styles.cardLine}>
                {r.regions.length} regions · ESO <Text style={styles.cardEm}>{r.external_signal_mode || "—"}</Text>
              </Text>
            </Pressable>
          );
        })
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s4 },
  row: { flexDirection: "row", gap: space.s3, marginBottom: space.s4 },
  cta: {
    flex: 1, backgroundColor: colors.accent, paddingVertical: 12,
    borderRadius: radius.pill, alignItems: "center",
  },
  ctaLabel: { color: "#04121b", fontWeight: "700" },
  btnGhost: {
    flex: 1, borderColor: colors.border, borderWidth: 1,
    paddingVertical: 12, borderRadius: radius.pill, alignItems: "center",
  },
  btnGhostLabel: { color: colors.textPrimary, fontWeight: "600" },
  disabled: { opacity: 0.4 },
  card: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.md, padding: space.s4, marginBottom: space.s3,
  },
  cardTitle: { color: colors.textPrimary, fontSize: 13, fontWeight: "700", fontFamily: "Menlo" },
  cardLine: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
  cardEm: { color: colors.textPrimary, fontWeight: "600" },
  empty: { color: colors.textTertiary, fontSize: 12, textAlign: "center", marginTop: space.s5 },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
