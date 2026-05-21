// ClarityOS Mobile — Forecast (v34).
// Renders the v34 forecast engine output on a single scrollable screen.
// Defaults to the static example from /elins/forecast/example so the
// screen renders without any prior ELINS run.

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import {
  elinsForecastExample,
  type V34ForecastBlock,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";
import PrimitiveEnvelope from "./primitive_envelope";
import MultiEnvelope from "./multi_envelope";
import DomainEnvelope from "./domain_envelope";
import ChainEnvelope from "./chain_envelope";

export default function ForecastScreen() {
  const [block, setBlock] = useState<V34ForecastBlock | null>(null);
  const [label, setLabel] = useState<string>("Example");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadExample = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await elinsForecastExample();
      setBlock(r.example.forecast);
      setLabel(r.example.label || "Example");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { void loadExample(); }, [loadExample]);

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>Forecast engine</Text>
      <Text style={styles.subtitle}>{label} · v34 multi-primitive envelope</Text>

      <View style={styles.row}>
        <Pressable
          onPress={() => void loadExample()}
          disabled={loading}
          style={[styles.cta, loading && styles.disabled]}
        >
          <Text style={styles.ctaLabel}>
            {loading ? <ActivityIndicator color="#04121b" /> : "Reload example"}
          </Text>
        </Pressable>
      </View>

      {error && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {block && (
        <View>
          <Section title="Multi-primitive envelope">
            <MultiEnvelope values={block.multi_envelope} />
          </Section>
          <Section title="Per-primitive envelopes">
            <PrimitiveEnvelope envelopes={block.primitive_envelopes} />
          </Section>
          <Section title="Domain envelopes">
            <DomainEnvelope domains={block.domain_envelopes} />
          </Section>
          <Section title="Causal-chain envelope">
            <ChainEnvelope values={block.chain_envelope} chain={block.chain} />
          </Section>
        </View>
      )}
    </ScrollView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.h2}>{title}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s4 },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600", marginBottom: space.s3 },
  row: { flexDirection: "row", gap: space.s3, marginBottom: space.s4 },
  cta: {
    backgroundColor: colors.accent, paddingVertical: 10, paddingHorizontal: 16,
    borderRadius: radius.pill, alignItems: "center",
  },
  ctaLabel: { color: "#04121b", fontWeight: "700" },
  disabled: { opacity: 0.4 },
  section: {
    backgroundColor: colors.bgSurface, borderColor: colors.border,
    borderWidth: 1, borderRadius: radius.lg, padding: space.s4,
    marginBottom: space.s4,
  },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
