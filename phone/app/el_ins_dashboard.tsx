// v70 / Unit 77 — Phone EL/INS dashboard (mobile-friendly summary).
//
// Compact mobile mirror of the web/desktop dashboard. Three sections:
//   - SUMMARY      : classification distribution + avg TSI + trend
//   - TSI TREND    : single SVG sparkline of recent TSI values
//   - RECENT       : compact list of the operator's last 20 records
//
// No chart libraries — pure react-native-svg sparkline.

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import Svg, { Circle, Polyline, Rect } from "react-native-svg";
import {
  ApiError,
  getElInsOperatorSummary,
  getElInsRecent,
  getUser,
  type ElInsOperatorSummaryResponse,
  type ElInsRecord,
  type ElInsTrend,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";
import AuthGate from "../components/AuthGate";

const SAMPLE = 20;

export default function ElInsDashboardScreen() {
  return (
    <AuthGate>
      <ElInsDashboardScreenInner />
    </AuthGate>
  );
}

function ElInsDashboardScreenInner() {
  const authedUser = getUser() || "";
  const [summary, setSummary] = useState<ElInsOperatorSummaryResponse | null>(null);
  const [records, setRecords] = useState<ElInsRecord[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, r] = await Promise.all([
        getElInsOperatorSummary(SAMPLE),
        getElInsRecent(SAMPLE),
      ]);
      setSummary(s);
      setRecords(r.records);
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetchAll(); }, [fetchAll]);

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.container}>
      <View style={styles.headerPanel}>
        <Text style={styles.h1}>EL/INS Dashboard</Text>
        <Text style={styles.muted}>
          Reasoning-stability snapshot for the last {SAMPLE} records.
        </Text>
        <Text style={styles.authedBadge}>
          Authed as <Text style={styles.authedBadgeName}>{authedUser}</Text>
        </Text>
      </View>

      {loading && !summary ? (
        <View style={styles.panel}>
          <ActivityIndicator color={colors.accent} />
        </View>
      ) : error ? (
        <View style={styles.panel}>
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        </View>
      ) : !summary ? (
        <View style={styles.panel}>
          <Text style={styles.empty}>No EL/INS data yet.</Text>
        </View>
      ) : (
        <>
          <View style={styles.panel}>
            <Text style={styles.h2}>SUMMARY</Text>
            <Row k="Sample size" v={String(summary.sample_size)} />
            <Row
              k="Trend"
              v={summary.trend.toUpperCase()}
              vColor={trendColor(summary.trend)}
            />
            <Row k="Avg TSI" v={`${summary.avg_tsi}/100`} mono />
            <Text style={[styles.muted, { marginTop: space.s3 }]}>
              CLASSIFICATION
            </Text>
            <Row
              k="balanced"
              v={String(summary.recent_classification_distribution.balanced)}
              vColor={colors.success}
              mono
            />
            <Row
              k="high_el"
              v={String(summary.recent_classification_distribution.high_el)}
              vColor={colors.danger}
              mono
            />
            <Row
              k="high_ins"
              v={String(summary.recent_classification_distribution.high_ins)}
              vColor={colors.warning}
              mono
            />
          </View>

          <View style={styles.panel}>
            <Text style={styles.h2}>TSI TREND</Text>
            <Sparkline values={tsiSeries(records || [])} />
          </View>

          <View style={styles.panel}>
            <Text style={styles.h2}>LAST {SAMPLE} RECORDS</Text>
            {!records || records.length === 0 ? (
              <Text style={styles.empty}>No records.</Text>
            ) : (
              records.slice(0, SAMPLE).map((rec, i) => (
                <View key={`${rec.timestamp}-${i}`} style={styles.recRow}>
                  <View style={styles.recHead}>
                    <View
                      style={[
                        styles.dot,
                        { backgroundColor: classColor(rec.result.analysis.ratio_classification) },
                      ]}
                    />
                    <Text style={styles.recCls}>
                      {rec.result.analysis.ratio_classification}
                    </Text>
                    <Text style={styles.recMeta}>
                      EL {rec.result.analysis.el_score.toFixed(2)} · INS{" "}
                      {rec.result.analysis.ins_score.toFixed(2)}
                      {typeof (rec as ElInsRecord & { tsi?: number }).tsi === "number"
                        ? ` · TSI ${(rec as ElInsRecord & { tsi: number }).tsi}`
                        : ""}
                    </Text>
                  </View>
                  <Text style={styles.recMetaMono}>
                    {formatTimestamp(rec.timestamp)} · {rec.thread_id || "no thread"}
                  </Text>
                </View>
              ))
            )}
          </View>

          <Pressable
            onPress={() => void fetchAll()}
            disabled={loading}
            style={[styles.cta, loading && styles.disabled]}
          >
            <Text style={styles.ctaLabel}>{loading ? "LOADING…" : "REFRESH"}</Text>
          </Pressable>
        </>
      )}
    </ScrollView>
  );
}

// ---------- sparkline ----------
function Sparkline({ values }: { values: number[] }) {
  const width = 280;
  const height = 80;
  const pad = 6;
  if (values.length === 0) {
    return (
      <View>
        <Svg width={width} height={height}>
          <Rect
            x={0} y={0} width={width} height={height}
            fill="none" stroke="rgba(255,255,255,0.08)"
          />
        </Svg>
        <Text style={styles.empty}>No TSI data.</Text>
      </View>
    );
  }
  const xs = values.length === 1
    ? [width / 2]
    : values.map((_, i) => pad + (i * (width - 2 * pad)) / (values.length - 1));
  const ys = values.map((v) => height - pad - ((v / 100) * (height - 2 * pad)));
  const points = xs.map((x, i) => `${x.toFixed(2)},${ys[i].toFixed(2)}`).join(" ");
  return (
    <Svg width={width} height={height}>
      <Rect
        x={0} y={0} width={width} height={height}
        fill="none" stroke="rgba(255,255,255,0.08)"
      />
      <Polyline fill="none" stroke={colors.accent} strokeWidth="1.5" points={points} />
      {xs.map((x, i) => (
        <Circle key={i} cx={x} cy={ys[i]} r={2} fill={colors.accent} />
      ))}
    </Svg>
  );
}

function Row({ k, v, vColor, mono }: { k: string; v: string; vColor?: string; mono?: boolean }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowK}>{k}</Text>
      <Text
        style={[
          styles.rowV,
          mono && { fontFamily: "Menlo" },
          vColor ? { color: vColor } : null,
        ]}
      >
        {v}
      </Text>
    </View>
  );
}

// ---------- helpers ----------
function tsiSeries(records: ElInsRecord[]): number[] {
  return [...records]
    .reverse()
    .map((r) => (r as ElInsRecord & { tsi?: number }).tsi)
    .filter((t): t is number => typeof t === "number");
}

function classColor(cls: string): string {
  if (cls === "high_el")  return colors.danger;
  if (cls === "high_ins") return colors.warning;
  return colors.success;
}

function trendColor(t: ElInsTrend): string {
  if (t === "improving") return colors.success;
  if (t === "declining") return colors.danger;
  return colors.textSecondary;
}

function formatTimestamp(ts: number): string {
  if (!ts) return "—";
  try {
    return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 19);
  } catch {
    return String(ts);
  }
}

function formatError(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.body === "object" && e.body && "detail" in (e.body as Record<string, unknown>)) {
      const d = (e.body as Record<string, unknown>).detail;
      if (typeof d === "string") return d;
    }
    return `${e.code}: ${e.message}`;
  }
  if (e instanceof Error) return e.message;
  return String(e);
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  headerPanel: {
    backgroundColor: colors.bgSurface,
    borderRadius: radius.lg,
    padding: space.s4,
    marginBottom: space.s3,
  },
  panel: {
    backgroundColor: colors.bgSurface,
    borderRadius: radius.lg,
    padding: space.s4,
    marginBottom: space.s3,
  },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600", marginBottom: space.s2 },
  muted: { color: colors.textSecondary, fontSize: 12 },
  authedBadge: {
    color: colors.textSecondary,
    fontSize: 11,
    marginTop: space.s3,
  },
  authedBadgeName: { color: colors.textPrimary, fontFamily: "Menlo" },
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 3 },
  rowK: { color: colors.textSecondary, fontSize: 12 },
  rowV: { color: colors.textPrimary, fontSize: 12, fontWeight: "600" },
  recRow: {
    paddingVertical: space.s2,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
  },
  recHead: { flexDirection: "row", alignItems: "center", gap: 8 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  recCls: { color: colors.textPrimary, fontWeight: "600", fontSize: 13 },
  recMeta: { color: colors.textSecondary, fontSize: 11, marginLeft: "auto" },
  recMetaMono: {
    color: colors.textTertiary,
    fontFamily: "Menlo",
    fontSize: 10,
    marginTop: 2,
  },
  cta: {
    backgroundColor: colors.accent,
    paddingVertical: 10,
    borderRadius: radius.pill,
    alignItems: "center",
    marginTop: space.s3,
  },
  ctaLabel: { color: "#04121b", fontWeight: "700", letterSpacing: 0.5 },
  disabled: { opacity: 0.4 },
  empty: { color: colors.textSecondary, fontStyle: "italic", marginTop: space.s2 },
  errorBox: {
    padding: space.s3,
    backgroundColor: "#3a1414",
    borderRadius: radius.md,
  },
  errorText: { color: "#ff8a8a", fontSize: 12 },
});
