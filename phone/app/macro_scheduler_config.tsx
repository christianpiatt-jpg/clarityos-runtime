// ClarityOS Mobile — Macro-ELINS scheduler config (v36).

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import {
  founderSchedulerConfig, founderSchedulerStatus,
  type V36Cadence, type V36SchedulerConfig, type V36SignalMode,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";

const CADENCES: V36Cadence[] = ["off", "daily", "3x_week", "weekly"];
const MODES: V36SignalMode[] = ["cloud_only", "cloud_perplexity"];

export default function MacroSchedulerConfigScreen() {
  const [cfg, setCfg] = useState<V36SchedulerConfig | null>(null);
  const [running, setRunning] = useState<boolean>(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy("load"); setError(null);
    try {
      const r = await founderSchedulerStatus();
      setCfg(r.config);
      setRunning(r.running);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const apply = useCallback(async (updates: Partial<V36SchedulerConfig>) => {
    setBusy("save"); setError(null);
    try {
      const r = await founderSchedulerConfig(updates);
      setCfg(r.config);
      setRunning(r.running);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  if (!cfg) {
    return (
      <View style={styles.center}>
        {busy === "load" ? <ActivityIndicator color={colors.accent} /> : (
          <Text style={styles.empty}>{error || "Scheduler unavailable"}</Text>
        )}
      </View>
    );
  }

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>Scheduler config</Text>
      <Text style={[styles.subtitle, { color: running ? colors.success : colors.textTertiary }]}>
        {running ? "● running" : "○ stopped"}
      </Text>

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
      )}

      <View style={styles.card}>
        <Text style={styles.h2}>Enabled</Text>
        <Pressable
          onPress={() => void apply({ enabled: !cfg.enabled })}
          disabled={busy !== null}
          style={[styles.toggle, cfg.enabled ? styles.toggleOn : styles.toggleOff]}
        >
          <Text style={[styles.toggleLabel, cfg.enabled && styles.toggleLabelOn]}>
            {cfg.enabled ? "Enabled" : "Disabled"}
          </Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.h2}>Cadence</Text>
        <View style={styles.row}>
          {CADENCES.map((c) => (
            <Pressable
              key={c}
              onPress={() => void apply({ cadence: c })}
              style={[styles.pill, cfg.cadence === c && styles.pillOn]}
            >
              <Text style={[styles.pillLabel, cfg.cadence === c && styles.pillLabelOn]}>{c}</Text>
            </Pressable>
          ))}
        </View>
      </View>

      <View style={styles.card}>
        <Text style={styles.h2}>External signal mode</Text>
        <View style={styles.row}>
          {MODES.map((m) => (
            <Pressable
              key={m}
              onPress={() => void apply({ external_signal_mode: m })}
              style={[styles.pill, cfg.external_signal_mode === m && styles.pillOn]}
            >
              <Text style={[styles.pillLabel, cfg.external_signal_mode === m && styles.pillLabelOn]}>{m}</Text>
            </Pressable>
          ))}
        </View>
      </View>

      <View style={styles.card}>
        <Text style={styles.h2}>Operator</Text>
        <Row k="System user" v={cfg.system_user} />
        <Row k="Last run" v={cfg.last_run_ts > 0 ? new Date(cfg.last_run_ts * 1000).toISOString().slice(0, 19) : "—"} />
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
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bgDeep },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  subtitle: { fontSize: 12, marginBottom: space.s4, fontFamily: "Menlo" },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600", marginBottom: space.s3 },
  card: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.lg, padding: space.s4, marginBottom: space.s3,
  },
  row: { flexDirection: "row", flexWrap: "wrap", gap: space.s2 },
  pill: {
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill,
    backgroundColor: colors.bgDeep, borderColor: colors.border, borderWidth: 1,
  },
  pillOn: { borderColor: colors.accent, backgroundColor: colors.bgElevated },
  pillLabel: { color: colors.textSecondary, fontSize: 12 },
  pillLabelOn: { color: colors.accent, fontWeight: "600" },
  toggle: {
    paddingVertical: 10, paddingHorizontal: 16, borderRadius: radius.pill,
    alignSelf: "flex-start", borderWidth: 1,
  },
  toggleOn: { backgroundColor: colors.accent, borderColor: colors.accent },
  toggleOff: { backgroundColor: colors.bgDeep, borderColor: colors.border },
  toggleLabel: { color: colors.textPrimary, fontWeight: "600" },
  toggleLabelOn: { color: "#04121b" },
  kvRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 3 },
  kvKey: { color: colors.textSecondary, fontSize: 12 },
  kvVal: { color: colors.textPrimary, fontSize: 12, fontFamily: "Menlo" },
  empty: { color: colors.textTertiary, fontSize: 12 },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
