// v69 / Unit 74 — Phone EL/INS surface.
//
// Compact mirror of web/OperatorElins. Single column scroll:
//   - ANALYZE form (text + provider mode + optional thread_id)
//   - RECENT list (newest-first)
//
// AuthGate-wrapped so unauthed visits get the same CTA as every other
// operator screen.

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  ApiError,
  getElInsRecent,
  getUser,
  postElInsAnalyze,
  type ElInsProviderMode,
  type ElInsRecord,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";
import AuthGate from "../components/AuthGate";

const PROVIDER_MODES: readonly ElInsProviderMode[] = [
  "auto", "llm", "deterministic",
] as const;

const LABELS: Record<string, string> = {
  balanced: "Balanced",
  high_el:  "High-EL",
  high_ins: "High-INS",
};

export default function ElInsScreen() {
  return (
    <AuthGate>
      <ElInsScreenInner />
    </AuthGate>
  );
}

function ElInsScreenInner() {
  const authedUser = getUser() || "";
  const [text, setText] = useState("");
  const [mode, setMode] = useState<ElInsProviderMode>("auto");
  const [threadId, setThreadId] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [records, setRecords] = useState<ElInsRecord[] | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchRecent = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await getElInsRecent(100);
      setRecords(r.records);
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetchRecent(); }, [fetchRecent]);

  const analyze = useCallback(async () => {
    if (!text.trim()) return;
    setAnalyzing(true);
    setError(null);
    try {
      await postElInsAnalyze(text, {
        provider_mode: mode,
        thread_id:     threadId.trim() || undefined,
      });
      setText("");
      await fetchRecent();
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setAnalyzing(false);
    }
  }, [text, mode, threadId, fetchRecent]);

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.container}>
      <View style={styles.headerPanel}>
        <Text style={styles.h1}>EL/INS</Text>
        <Text style={styles.muted}>
          Reasoning-stability diagnostic. Tap REFRESH after analyzing to
          see the latest record at the top of the list below.
        </Text>
        <Text style={styles.authedBadge}>
          Authed as <Text style={styles.authedBadgeName}>{authedUser}</Text>
        </Text>
      </View>

      <View style={styles.panel}>
        <Text style={styles.h2}>ANALYZE</Text>
        <TextInput
          value={text}
          onChangeText={setText}
          placeholder="Paste or type the text to score…"
          placeholderTextColor={colors.textSecondary}
          multiline
          editable={!analyzing}
          style={styles.textarea}
        />
        <Text style={[styles.muted, { marginTop: space.s3 }]}>Provider mode</Text>
        <View style={styles.modeRow}>
          {PROVIDER_MODES.map((m) => (
            <Pressable
              key={m}
              onPress={() => setMode(m)}
              disabled={analyzing}
              style={[styles.modeChip, mode === m && styles.modeChipActive]}
            >
              <Text style={[styles.modeChipLabel, mode === m && styles.modeChipLabelActive]}>
                {m}
              </Text>
            </Pressable>
          ))}
        </View>
        <Text style={[styles.muted, { marginTop: space.s3 }]}>Thread id (optional)</Text>
        <TextInput
          value={threadId}
          onChangeText={setThreadId}
          placeholder="(no thread)"
          placeholderTextColor={colors.textSecondary}
          editable={!analyzing}
          autoCapitalize="none"
          style={styles.input}
        />
        <Pressable
          onPress={() => void analyze()}
          disabled={analyzing || !text.trim()}
          style={[styles.cta, (analyzing || !text.trim()) && styles.disabled]}
        >
          <Text style={styles.ctaLabel}>{analyzing ? "ANALYZING…" : "ANALYZE"}</Text>
        </Pressable>
        {error ? (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}
      </View>

      <View style={styles.panel}>
        <View style={styles.rowBetween}>
          <Text style={styles.h2}>RECENT</Text>
          <Pressable
            onPress={() => void fetchRecent()}
            disabled={loading}
            style={styles.btnSecondary}
          >
            <Text style={styles.btnSecondaryLabel}>REFRESH</Text>
          </Pressable>
        </View>
        {loading && !records ? (
          <ActivityIndicator color={colors.accent} />
        ) : !records || records.length === 0 ? (
          <Text style={styles.empty}>No EL/INS records yet.</Text>
        ) : (
          records.map((rec, i) => (
            <View key={`${rec.timestamp}-${i}`} style={styles.recRow}>
              <View style={styles.recRowHead}>
                <View style={[styles.dot, { backgroundColor: classColor(rec.result.analysis.ratio_classification) }]} />
                <Text style={styles.recCls}>
                  {LABELS[rec.result.analysis.ratio_classification] ||
                    rec.result.analysis.ratio_classification}
                </Text>
                <Text style={styles.recMeta}>
                  EL {rec.result.analysis.el_score.toFixed(2)} · INS{" "}
                  {rec.result.analysis.ins_score.toFixed(2)}
                </Text>
              </View>
              <Text style={styles.recMetaMono}>
                {formatTimestamp(rec.timestamp)} · {rec.thread_id || "no thread"} ·{" "}
                {rec.source}
              </Text>
            </View>
          ))
        )}
      </View>
    </ScrollView>
  );
}

// ---------- helpers ----------
function classColor(cls: string): string {
  if (cls === "high_el")  return colors.danger;
  if (cls === "high_ins") return colors.warning;
  return colors.success;
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
  authedBadgeName: {
    color: colors.textPrimary,
    fontFamily: "Menlo",
  },
  textarea: {
    color: colors.textPrimary,
    backgroundColor: colors.bgDeep,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: space.s3,
    minHeight: 80,
    marginTop: space.s2,
    textAlignVertical: "top",
  },
  input: {
    color: colors.textPrimary,
    backgroundColor: colors.bgDeep,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.sm,
    padding: 8,
    marginTop: 4,
  },
  modeRow: { flexDirection: "row", flexWrap: "wrap", gap: space.s2, marginTop: space.s2 },
  modeChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.pill,
    borderColor: colors.border,
    borderWidth: 1,
    backgroundColor: colors.bgDeep,
  },
  modeChipActive: { borderColor: colors.accent, backgroundColor: colors.bgElevated },
  modeChipLabel: { color: colors.textSecondary, fontSize: 12 },
  modeChipLabelActive: { color: colors.accent, fontWeight: "600" },
  cta: {
    backgroundColor: colors.accent,
    paddingVertical: 10,
    borderRadius: radius.pill,
    alignItems: "center",
    marginTop: space.s4,
  },
  ctaLabel: { color: "#04121b", fontWeight: "700", letterSpacing: 0.5 },
  disabled: { opacity: 0.4 },
  rowBetween: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    marginBottom: space.s3,
  },
  btnSecondary: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: radius.pill,
    borderColor: colors.border,
    borderWidth: 1,
  },
  btnSecondaryLabel: { color: colors.textSecondary, fontSize: 11, fontWeight: "600" },
  empty: { color: colors.textSecondary, fontStyle: "italic" },
  recRow: {
    paddingVertical: space.s2,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
  },
  recRowHead: { flexDirection: "row", alignItems: "center", gap: 8 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  recCls: { color: colors.textPrimary, fontWeight: "600", fontSize: 13 },
  recMeta: { color: colors.textSecondary, fontSize: 11, marginLeft: "auto" },
  recMetaMono: {
    color: colors.textTertiary,
    fontFamily: "Menlo",
    fontSize: 10,
    marginTop: 2,
  },
  errorBox: {
    padding: space.s3,
    backgroundColor: "#3a1414",
    borderRadius: radius.md,
    marginTop: space.s3,
  },
  errorText: { color: "#ff8a8a", fontSize: 12 },
});
