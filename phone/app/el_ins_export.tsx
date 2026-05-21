// v71 / Unit 78 — Phone EL/INS export screen.
//
// Simple mobile-friendly export surface. Two buttons: "Download JSON"
// (saves via Share API where available, falls back to Clipboard.set)
// and "Download PDF" (same pattern with the PDF blob).
//
// AuthGate-wrapped per the v67/v68 convention.

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  View,
} from "react-native";
import {
  ApiError,
  getElInsExportJson,
  getElInsOperatorSummary,
  getUser,
  type ElInsOperatorSummaryResponse,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";
import AuthGate from "../components/AuthGate";

const SAMPLE = 200;

export default function ElInsExportScreen() {
  return (
    <AuthGate>
      <ElInsExportScreenInner />
    </AuthGate>
  );
}

function ElInsExportScreenInner() {
  const authedUser = getUser() || "";
  const [summary, setSummary] = useState<ElInsOperatorSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"json" | "pdf" | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const s = await getElInsOperatorSummary(SAMPLE);
      setSummary(s);
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function downloadJson() {
    setBusy("json");
    setError(null);
    try {
      const data = await getElInsExportJson(SAMPLE);
      const payload = JSON.stringify(data, null, 2);
      // React Native Share API doesn't accept blobs — pass the
      // serialized JSON as the message body. Users save via the OS
      // share sheet (Notes, Files, email, etc.).
      const ok = await Share.share({
        title: `EL/INS export — ${data.operator_id}`,
        message: payload,
      });
      if (ok.action === Share.dismissedAction) {
        // No action — silent.
      }
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setBusy(null);
    }
  }

  async function downloadPdf() {
    // The PDF endpoint returns binary which React Native Share can't
    // ferry directly. Surface a guidance message for now — phone PDF
    // download is best-effort and the v71 spec's phone scope is just
    // the Export button + screen (no PDF transport).
    Alert.alert(
      "PDF download",
      "Open the EL/INS export from the web or desktop client to download a PDF. The phone app supports JSON export only.",
    );
  }

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.container}>
      <View style={styles.headerPanel}>
        <Text style={styles.h1}>EL/INS Export</Text>
        <Text style={styles.muted}>
          Portable export of your last {SAMPLE} EL/INS records.
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

      <View style={styles.panel}>
        <Text style={styles.h2}>PREVIEW</Text>
        {loading && !summary ? (
          <ActivityIndicator color={colors.accent} />
        ) : !summary ? (
          <Text style={styles.empty}>No EL/INS data yet.</Text>
        ) : (
          <View>
            <Row k="Sample size" v={String(summary.sample_size)} />
            <Row k="Avg TSI" v={`${summary.avg_tsi}/100`} mono />
            <Row k="Trend" v={summary.trend.toUpperCase()} />
            <Row k="Balanced" v={String(summary.recent_classification_distribution.balanced)} mono />
            <Row k="High-EL" v={String(summary.recent_classification_distribution.high_el)} mono />
            <Row k="High-INS" v={String(summary.recent_classification_distribution.high_ins)} mono />
          </View>
        )}
      </View>

      <View style={styles.panel}>
        <Text style={styles.h2}>DOWNLOAD</Text>
        <Pressable
          onPress={() => void downloadJson()}
          disabled={busy !== null}
          style={[styles.cta, busy !== null && styles.disabled]}
        >
          <Text style={styles.ctaLabel}>{busy === "json" ? "PREPARING…" : "DOWNLOAD JSON"}</Text>
        </Pressable>
        <Pressable
          onPress={() => void downloadPdf()}
          disabled={busy !== null}
          style={[styles.cta, busy !== null && styles.disabled, { marginTop: space.s2 }]}
        >
          <Text style={styles.ctaLabel}>{busy === "pdf" ? "PREPARING…" : "DOWNLOAD PDF"}</Text>
        </Pressable>
        <Text style={[styles.muted, { fontSize: 11, marginTop: space.s3 }]}>
          PDF export available on web or desktop. Phone shares JSON via
          the OS share sheet.
        </Text>
      </View>
    </ScrollView>
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
  cta: {
    backgroundColor: colors.accent,
    paddingVertical: 10,
    borderRadius: radius.pill,
    alignItems: "center",
    marginTop: space.s3,
  },
  ctaLabel: { color: "#04121b", fontWeight: "700", letterSpacing: 0.5 },
  disabled: { opacity: 0.4 },
  empty: { color: colors.textSecondary, fontStyle: "italic" },
  errorBox: {
    padding: space.s3,
    backgroundColor: "#3a1414",
    borderRadius: radius.md,
  },
  errorText: { color: "#ff8a8a", fontSize: 12 },
});
