// ClarityOS Mobile — ELINS inspector (v33).
// Run /elins/preview + /elins/qc against arbitrary text.

import { useCallback, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { router } from "expo-router";
import { elinsPreview, elinsQC, type V33ELINSObject, type V33SELINSResult } from "../lib/api";
import { colors, radius, space } from "../lib/theme";
import MultiEnvelope from "./multi_envelope";

export default function ELINSInspectorScreen() {
  const [text, setText] = useState("");
  const [obj, setObj] = useState<V33ELINSObject | null>(null);
  const [qc, setQc] = useState<V33SELINSResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    if (!text.trim()) return;
    setBusy("preview"); setError(null); setObj(null); setQc(null);
    try {
      const r = await elinsPreview(text.trim());
      setObj(r.elins);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, [text]);

  const runQC = useCallback(async () => {
    if (!obj) return;
    setBusy("qc"); setError(null);
    try {
      const r = await elinsQC(obj);
      setQc(r.s_elins);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, [obj]);

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>ELINS inspector</Text>
      <View style={styles.card}>
        <Text style={styles.label}>Scenario text</Text>
        <TextInput
          value={text}
          onChangeText={setText}
          placeholder="Paste scenario text"
          placeholderTextColor={colors.textTertiary}
          multiline
          style={[styles.input, { minHeight: 100 }]}
          maxLength={8000}
        />
        <View style={styles.row}>
          <Pressable
            onPress={() => void run()}
            disabled={busy !== null || !text.trim()}
            style={[styles.cta, (busy !== null || !text.trim()) && styles.disabled]}
          >
            <Text style={styles.ctaLabel}>
              {busy === "preview" ? <ActivityIndicator color="#04121b" /> : "Run preview"}
            </Text>
          </Pressable>
          <Pressable
            onPress={() => void runQC()}
            disabled={busy !== null || !obj}
            style={[styles.btnGhost, (busy !== null || !obj) && styles.disabled]}
          >
            <Text style={styles.btnGhostLabel}>{busy === "qc" ? "QC…" : "Run QC"}</Text>
          </Pressable>
        </View>
      </View>

      {error && <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>}

      {obj && (
        <View style={styles.card}>
          <Text style={styles.h2}>Synthesis</Text>
          <Row k="Top primitive" v={obj.synthesis.top_primitive} />
          <Row k="Domain" v={obj.synthesis.domain || "—"} />
          <Row k="Signal" v={obj.synthesis.signal} />
          <Row k="Trend" v={obj.synthesis.trend} />
          <Row k="Stress / Relief" v={`${obj.synthesis.stress_score} / ${obj.synthesis.relief_score}`} />
          <Text style={[styles.h2, { marginTop: space.s4 }]}>Primitives</Text>
          {Object.entries(obj.primitives.intensities).map(([k, v]) => (
            <Row key={k} k={k} v={String(v)} />
          ))}
          {obj.synthesis.external_anchors && obj.synthesis.external_anchors.length > 0 && (
            <View>
              <Text style={[styles.h2, { marginTop: space.s4 }]}>Anchors → entity graph</Text>
              {obj.synthesis.external_anchors.map((a) => (
                <Pressable
                  key={a}
                  onPress={() => router.push({ pathname: "/entity_detail", params: { entity: a } })}
                  style={styles.linkRow}
                >
                  <Text style={styles.linkText}>{a} →</Text>
                </Pressable>
              ))}
            </View>
          )}
        </View>
      )}

      {qc && (
        <View style={[styles.card, qc.passed ? styles.passBg : styles.failBg]}>
          <Text style={[styles.h2, { color: qc.passed ? "#7CD992" : "#ff8a8a" }]}>
            S_ELINS QC: {qc.passed ? "PASS" : "FAIL"}
          </Text>
          <Row k="Alignment" v={String(qc.alignment_score)} />
          <Row k="Max delta" v={String(qc.max_delta)} />
        </View>
      )}

      {obj?.forecast_engine && (
        <View style={styles.card}>
          <Text style={styles.h2}>Forecast (v34) · multi-envelope</Text>
          <MultiEnvelope values={obj.forecast_engine.multi_envelope} />
          <Pressable onPress={() => router.push("/forecast")} style={styles.linkRow}>
            <Text style={styles.linkText}>Open full forecast →</Text>
          </Pressable>
        </View>
      )}

      {!obj && (
        <Pressable onPress={() => router.push("/forecast")} style={styles.linkRow}>
          <Text style={styles.linkText}>Open forecast example →</Text>
        </Pressable>
      )}

      <Pressable onPress={() => router.push("/regional")} style={styles.linkRow}>
        <Text style={styles.linkText}>Open regional ELINS →</Text>
      </Pressable>
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
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700", marginBottom: space.s4 },
  h2: { color: colors.textPrimary, fontSize: 16, fontWeight: "600", marginBottom: space.s3 },
  label: { color: colors.textSecondary, fontSize: 12, marginBottom: 4 },
  card: {
    backgroundColor: colors.bgSurface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: space.s5,
    marginBottom: space.s4,
  },
  input: {
    backgroundColor: colors.bgDeep,
    borderColor: colors.borderStrong,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 12,
    color: colors.textPrimary,
    textAlignVertical: "top",
    fontSize: 13,
    marginBottom: space.s3,
  },
  row: { flexDirection: "row", gap: space.s3 },
  cta: {
    flex: 1,
    backgroundColor: colors.accent,
    paddingVertical: 12,
    borderRadius: radius.pill,
    alignItems: "center",
  },
  ctaLabel: { color: "#04121b", fontWeight: "700" },
  btnGhost: {
    flex: 1,
    backgroundColor: "transparent",
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: 12,
    borderRadius: radius.pill,
    alignItems: "center",
  },
  btnGhostLabel: { color: colors.textPrimary, fontWeight: "600" },
  disabled: { opacity: 0.4 },
  passBg: { backgroundColor: "#15301f" },
  failBg: { backgroundColor: "#3a1414" },
  kvRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 3 },
  kvKey: { color: colors.textSecondary, fontSize: 12 },
  kvVal: { color: colors.textPrimary, fontSize: 12, fontFamily: "Menlo" },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
  linkRow: { paddingVertical: space.s2, alignItems: "center" },
  linkText: { color: colors.accent, fontSize: 13, fontWeight: "600" },
});
