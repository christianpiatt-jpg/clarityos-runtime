// v72 / Unit 81 — Phone roll-up screen.
//
// Three collapsible sections (24h / 7d / 30d). Text-only summary per
// spec — no charts on phone (kept compact for mobile).

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import {
  ApiError,
  getElInsRollup,
  getUser,
  type ElInsRollupResult,
  type ElInsRollupWindow,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";
import AuthGate from "../components/AuthGate";

const WINDOWS: readonly ElInsRollupWindow[] = ["24h", "7d", "30d"] as const;
const LABELS: Record<ElInsRollupWindow, string> = {
  "24h": "Last 24h",
  "7d":  "Last 7 days",
  "30d": "Last 30 days",
};

export default function ElInsRollupScreen() {
  return (
    <AuthGate>
      <ElInsRollupScreenInner />
    </AuthGate>
  );
}

function ElInsRollupScreenInner() {
  const authedUser = getUser() || "";
  const [data, setData] = useState<Record<ElInsRollupWindow, ElInsRollupResult | null>>({
    "24h": null, "7d": null, "30d": null,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<ElInsRollupWindow, boolean>>({
    "24h": true, "7d": false, "30d": false,
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const results = await Promise.all(WINDOWS.map((w) => getElInsRollup(w)));
      const next: Record<ElInsRollupWindow, ElInsRollupResult | null> = {
        "24h": null, "7d": null, "30d": null,
      };
      WINDOWS.forEach((w, i) => { next[w] = results[i]; });
      setData(next);
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const toggle = (w: ElInsRollupWindow) => {
    setExpanded((prev) => ({ ...prev, [w]: !prev[w] }));
  };

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.container}>
      <View style={styles.headerPanel}>
        <Text style={styles.h1}>EL/INS Roll-Up</Text>
        <Text style={styles.muted}>
          Aggregate stats over three rolling windows. Text-only on phone.
        </Text>
        <Text style={styles.authedBadge}>
          Authed as <Text style={styles.authedBadgeName}>{authedUser}</Text>
        </Text>
      </View>

      {error ? (
        <View style={styles.panel}>
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        </View>
      ) : null}

      {loading && !data["24h"] ? (
        <View style={styles.panel}>
          <ActivityIndicator color={colors.accent} />
        </View>
      ) : (
        WINDOWS.map((w) => (
          <Section
            key={w}
            label={LABELS[w]}
            expanded={expanded[w]}
            onToggle={() => toggle(w)}
            result={data[w]}
          />
        ))
      )}

      <Pressable
        onPress={() => void load()}
        disabled={loading}
        style={[styles.cta, loading && styles.disabled]}
      >
        <Text style={styles.ctaLabel}>{loading ? "LOADING…" : "REFRESH"}</Text>
      </Pressable>
    </ScrollView>
  );
}

function Section({
  label, expanded, onToggle, result,
}: {
  label: string; expanded: boolean; onToggle: () => void; result: ElInsRollupResult | null;
}) {
  return (
    <View style={styles.panel}>
      <Pressable onPress={onToggle} style={styles.sectionHead}>
        <Text style={styles.h2}>{label}</Text>
        <Text style={styles.toggle}>{expanded ? "▼" : "▶"}</Text>
      </Pressable>
      {expanded ? (
        !result ? (
          <Text style={styles.empty}>—</Text>
        ) : (
          <View style={{ marginTop: space.s2 }}>
            <Row k="records" v={String(result.record_count)} mono />
            <Row k="avg EL" v={result.avg_el.toFixed(2)} mono />
            <Row k="avg INS" v={result.avg_ins.toFixed(2)} mono />
            <Row k="avg TSI" v={`${result.avg_tsi}/100`} mono />
            <Text style={[styles.muted, { marginTop: space.s3, fontSize: 11, letterSpacing: 0.5 }]}>
              REASONING MODES
            </Text>
            {Object.keys(result.reasoning_mode_distribution).length === 0 ? (
              <Text style={styles.empty}>no records</Text>
            ) : (
              Object.entries(result.reasoning_mode_distribution)
                .sort((a, b) => b[1] - a[1])
                .map(([mode, count]) => (
                  <Row key={mode} k={mode} v={String(count)} mono />
                ))
            )}
          </View>
        )
      ) : null}
    </View>
  );
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowK}>{k}</Text>
      <Text style={[styles.rowV, mono && { fontFamily: "Menlo" }]}>{v}</Text>
    </View>
  );
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
  headerPanel: { backgroundColor: colors.bgSurface, borderRadius: radius.lg, padding: space.s4, marginBottom: space.s3 },
  panel: { backgroundColor: colors.bgSurface, borderRadius: radius.lg, padding: space.s4, marginBottom: space.s3 },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  muted: { color: colors.textSecondary, fontSize: 12 },
  authedBadge: { color: colors.textSecondary, fontSize: 11, marginTop: space.s3 },
  authedBadgeName: { color: colors.textPrimary, fontFamily: "Menlo" },
  sectionHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  toggle: { color: colors.textSecondary, fontSize: 12 },
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 3 },
  rowK: { color: colors.textSecondary, fontSize: 12 },
  rowV: { color: colors.textPrimary, fontSize: 12, fontWeight: "600" },
  empty: { color: colors.textSecondary, fontStyle: "italic", marginTop: space.s2 },
  cta: { backgroundColor: colors.accent, paddingVertical: 10, borderRadius: radius.pill, alignItems: "center", marginTop: space.s3 },
  ctaLabel: { color: "#04121b", fontWeight: "700", letterSpacing: 0.5 },
  disabled: { opacity: 0.4 },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md },
  errorText: { color: "#ff8a8a", fontSize: 12 },
});
