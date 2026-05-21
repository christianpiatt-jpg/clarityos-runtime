// v69 / Unit 74 — Phone EL/INS cockpit indicator.
//
// Compact card rendered in the phone home/cockpit. Reads the most
// recent EL/INS record for the authed operator and shows a one-glance
// stability label. Tapping routes to /el_ins for the full surface.
//
// Failures are silent — the cockpit shouldn't break because a
// diagnostic surface is unreachable.

import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { router, useFocusEffect } from "expo-router";
import { useCallback } from "react";
import {
  getElInsAnomalies,
  getElInsReasoningMode,
  getElInsRecent,
  type ElInsRecord,
  type ElInsReasoningModeLabel,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";

// v72 / Unit 80 — fire the red dot when at least one anomaly landed
// in the last 24h. No client-side last-seen state.
const ANOMALY_NEW_WINDOW_SECONDS = 60 * 60 * 24;

const LABELS: Record<string, string> = {
  balanced: "Balanced",
  high_el:  "High-EL",
  high_ins: "High-INS",
};

// v71 / Unit 79 — Phone reasoning-mode display labels.
const MODE_LABELS: Record<string, string> = {
  grounding:              "Grounding",
  analysis:               "Analysis",
  structured_reflection:  "Structured Reflection",
  stabilization:          "Stabilization",
  extended_reasoning:     "Extended Reasoning",
  normal:                 "Normal",
};

export default function ElInsIndicator() {
  const [latest, setLatest] = useState<ElInsRecord | null>(null);
  const [reasoningMode, setReasoningMode] = useState<ElInsReasoningModeLabel | null>(null);
  const [hasRecentAnomaly, setHasRecentAnomaly] = useState(false);
  const [hidden, setHidden] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [r, m, a] = await Promise.all([
        getElInsRecent(1),
        getElInsReasoningMode().catch(() => null),
        getElInsAnomalies(20).catch(() => null),
      ]);
      setLatest(r.records[0] ?? null);
      if (m) setReasoningMode(m.reasoning_mode);
      if (a) {
        const cutoff = Date.now() / 1000 - ANOMALY_NEW_WINDOW_SECONDS;
        setHasRecentAnomaly(a.anomalies.some((x) => x.timestamp >= cutoff));
      }
      setHidden(false);
    } catch {
      setHidden(true);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);
  // Refresh whenever the home screen re-focuses (e.g. after an analyze
  // round-trip from the el_ins screen).
  useFocusEffect(useCallback(() => { void refresh(); }, [refresh]));

  if (hidden) return null;

  const cls = latest?.result?.analysis?.ratio_classification || null;
  const label = cls ? (LABELS[cls] || cls) : "—";
  const sub = latest
    ? `EL ${latest.result.analysis.el_score.toFixed(2)} · INS ${latest.result.analysis.ins_score.toFixed(2)}`
    : "no EL/INS records yet";

  const modeLabel = reasoningMode ? (MODE_LABELS[reasoningMode] || reasoningMode) : null;

  return (
    <View>
      <Pressable onPress={() => router.push("/el_ins")} style={styles.card}>
        <View style={styles.row}>
          <View style={[styles.dot, { backgroundColor: classColor(cls) }]} />
          <Text style={styles.label}>Stability: <Text style={styles.labelStrong}>{label}</Text></Text>
          {hasRecentAnomaly ? (
            <View style={styles.anomalyDot} />
          ) : null}
        </View>
        <Text style={styles.sub}>{sub}</Text>
        {modeLabel ? (
          <Text style={styles.reasoningMode}>Reasoning Mode: <Text style={styles.reasoningModeStrong}>{modeLabel}</Text></Text>
        ) : null}
      </Pressable>
      <Pressable
        onPress={() => router.push("/el_ins_dashboard")}
        style={styles.dashboardBtn}
      >
        <Text style={styles.dashboardBtnLabel}>View Dashboard →</Text>
      </Pressable>
      <Pressable
        onPress={() => router.push("/el_ins_anomalies")}
        style={styles.dashboardBtn}
      >
        <Text style={styles.dashboardBtnLabel}>
          Anomalies →{hasRecentAnomaly ? "  (new)" : ""}
        </Text>
      </Pressable>
      <Pressable
        onPress={() => router.push("/el_ins_rollup")}
        style={styles.dashboardBtn}
      >
        <Text style={styles.dashboardBtnLabel}>Roll-Up →</Text>
      </Pressable>
      <Pressable
        onPress={() => router.push("/el_ins_export")}
        style={styles.dashboardBtn}
      >
        <Text style={styles.dashboardBtnLabel}>Export →</Text>
      </Pressable>
      <Pressable
        onPress={() => router.push("/timeline")}
        style={styles.dashboardBtn}
      >
        <Text style={styles.dashboardBtnLabel}>Timeline →</Text>
      </Pressable>
    </View>
  );
}

function classColor(cls: string | null): string {
  if (cls === "high_el")  return colors.danger;
  if (cls === "high_ins") return colors.warning;
  if (cls === "balanced") return colors.success;
  return colors.textTertiary;
}

const styles = StyleSheet.create({
  card: {
    marginTop: space.s5,
    paddingVertical: space.s3,
    paddingHorizontal: space.s4,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.bgSurface,
  },
  row: { flexDirection: "row", alignItems: "center", gap: 8 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  label: { color: colors.textSecondary, fontSize: 13 },
  labelStrong: { color: colors.textPrimary, fontWeight: "600" },
  sub: {
    color: colors.textTertiary,
    fontFamily: "Menlo",
    fontSize: 11,
    marginTop: 4,
  },
  dashboardBtn: {
    marginTop: space.s2,
    paddingVertical: space.s2,
    alignItems: "center",
  },
  dashboardBtnLabel: {
    color: colors.accent,
    fontSize: 12,
    fontWeight: "600",
  },
  reasoningMode: {
    color: colors.textTertiary,
    fontSize: 11,
    marginTop: 4,
  },
  reasoningModeStrong: {
    color: colors.textPrimary,
    fontWeight: "600",
  },
  anomalyDot: {
    marginLeft: 8,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.danger,
  },
});
