// ClarityOS Mobile — Regional ELINS forecast (v35).
// Per-region forecast view: re-runs /elins/regional/run for the
// requested region and shows the v34 forecast charts.

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import {
  elinsRegionalRun, V35_REGION_CODES,
  type V35RegionalELINS, type V35RegionCode,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";
import PrimitiveEnvelope from "./primitive_envelope";
import MultiEnvelope from "./multi_envelope";
import DomainEnvelope from "./domain_envelope";
import ChainEnvelope from "./chain_envelope";

export default function RegionalForecastScreen() {
  const params = useLocalSearchParams<{ region?: string }>();
  const initial = (params.region as V35RegionCode) || "US";
  const region: V35RegionCode = V35_REGION_CODES.includes(initial) ? initial : "US";
  const [elins, setElins] = useState<V35RegionalELINS | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const r = await elinsRegionalRun(region);
      setElins(r.elins);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, [region]);

  useEffect(() => { void run(); }, [run]);

  const block = elins?.forecast_engine || null;

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>{region} forecast</Text>
      <Text style={styles.subtitle}>v35 regional · v34 forecast engine</Text>

      {busy && !block && <ActivityIndicator color={colors.accent} style={{ marginTop: space.s4 }} />}

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
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
          {elins?.external_signals?.present && (
            <Section title="External anchors (ESO)">
              {elins.external_signals.anchors.map((a) => (
                <Text key={a} style={styles.anchorLine}>• {a}</Text>
              ))}
            </Section>
          )}
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
  section: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.lg, padding: space.s4, marginBottom: space.s4,
  },
  anchorLine: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
