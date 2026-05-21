// ClarityOS Mobile — #cmt comment generator (v33).

import { useCallback, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { cmtGenerate, type V33CommentResult } from "../lib/api";
import { colors, radius, space } from "../lib/theme";

const DOMAINS = [
  "", "legal", "institutional", "economic", "geopolitical",
  "social", "personal", "technological", "ecological",
];

export default function CommentGeneratorScreen() {
  const [text, setText] = useState("");
  const [domain, setDomain] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<V33CommentResult | null>(null);

  const run = useCallback(async () => {
    if (!text.trim()) return;
    setBusy(true); setError(null); setResult(null);
    try {
      const r = await cmtGenerate(text.trim(), domain || undefined);
      setResult(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, [text, domain]);

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>#cmt — Comment generator</Text>
      <View style={styles.card}>
        <Text style={styles.label}>Input</Text>
        <TextInput
          value={text}
          onChangeText={setText}
          placeholder="Paste the post / quote / statement to comment on"
          placeholderTextColor={colors.textTertiary}
          multiline
          maxLength={8000}
          style={[styles.input, { minHeight: 100 }]}
        />
        <Text style={styles.label}>Domain hint</Text>
        <View style={styles.chipRow}>
          {DOMAINS.map((d) => (
            <Pressable
              key={d || "_auto"}
              onPress={() => setDomain(d)}
              style={[styles.chip, domain === d && styles.chipActive]}
            >
              <Text style={[styles.chipText, domain === d && styles.chipTextActive]}>
                {d || "auto"}
              </Text>
            </Pressable>
          ))}
        </View>
        <Pressable
          onPress={() => void run()}
          disabled={busy || !text.trim()}
          style={[styles.cta, (busy || !text.trim()) && styles.disabled]}
        >
          <Text style={styles.ctaLabel}>
            {busy ? <ActivityIndicator color="#04121b" /> : "Generate"}
          </Text>
        </Pressable>
      </View>

      {error && <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>}

      {result && (
        <>
          <View style={styles.card}>
            <Text style={styles.h2}>Comment</Text>
            <Text style={styles.body}>{result.comment}</Text>
          </View>
          <View style={styles.card}>
            <Text style={styles.h2}>Detection</Text>
            <Row k="Attractor" v={result.detection.attractor} />
            <Row k="Domain" v={result.detection.domain || "—"} />
            <Row k="Tone" v={result.detection.tone} />
          </View>
          <View style={styles.card}>
            <Text style={styles.h2}>Construction</Text>
            <Text style={styles.subKey}>Structural reframe</Text>
            <Text style={styles.subVal}>{result.construction.structural_reframe}</Text>
            <Text style={styles.subKey}>Domain alignment</Text>
            <Text style={styles.subVal}>{result.construction.domain_alignment}</Text>
            <Text style={styles.subKey}>Identity move</Text>
            <Text style={styles.subVal}>{result.construction.identity_move}</Text>
            <Text style={styles.subKey}>Stabilizing close</Text>
            <Text style={styles.subVal}>{result.construction.stabilizing_close}</Text>
          </View>
          <View style={styles.card}>
            <Text style={styles.h2}>Activation</Text>
            <Row k="Low emotion" v={String(result.activation.low_emotion)} />
            <Row k="Noun density" v={String(result.activation.noun_density)} />
            <Row k="Char count" v={String(result.activation.char_count)} />
          </View>
        </>
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
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700", marginBottom: space.s4 },
  h2: { color: colors.textPrimary, fontSize: 16, fontWeight: "600", marginBottom: space.s3 },
  label: { color: colors.textSecondary, fontSize: 12, marginBottom: 4 },
  body: { color: colors.textPrimary, fontSize: 14, lineHeight: 20 },
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
    padding: 10,
    color: colors.textPrimary,
    fontSize: 13,
    marginBottom: space.s3,
    textAlignVertical: "top",
  },
  chipRow: { flexDirection: "row", gap: space.s2, marginBottom: space.s3, flexWrap: "wrap" },
  chip: {
    paddingHorizontal: 10, paddingVertical: 5,
    backgroundColor: colors.bgElevated, borderRadius: radius.pill,
    borderWidth: 1, borderColor: colors.border,
  },
  chipActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  chipText: { color: colors.textPrimary, fontSize: 11 },
  chipTextActive: { color: "#04121b", fontWeight: "700" },
  cta: {
    backgroundColor: colors.accent,
    paddingVertical: 12,
    borderRadius: radius.pill,
    alignItems: "center",
  },
  ctaLabel: { color: "#04121b", fontWeight: "700" },
  disabled: { opacity: 0.4 },
  kvRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 3 },
  kvKey: { color: colors.textSecondary, fontSize: 12 },
  kvVal: { color: colors.textPrimary, fontSize: 12, fontFamily: "Menlo" },
  subKey: { color: colors.textSecondary, fontSize: 12, marginTop: 6 },
  subVal: { color: colors.textPrimary, fontSize: 13 },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
