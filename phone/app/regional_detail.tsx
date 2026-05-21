// ClarityOS Mobile — Regional ELINS detail (v35).
// Runs /elins/regional/run for the selected region and displays the
// EP summary, top primitives, domain vector + ESO anchors. Links to
// regional_forecast for the full forecast view.

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import {
  elinsRegionalRun, V35_REGION_CODES,
  type V35RegionalELINS, type V35RegionCode,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";

export default function RegionalDetailScreen() {
  const params = useLocalSearchParams<{ region?: string }>();
  const initial = (params.region as V35RegionCode) || "US";
  const [region, setRegion] = useState<V35RegionCode>(
    V35_REGION_CODES.includes(initial) ? initial : "US",
  );
  const [topic, setTopic] = useState<string>("");
  const [elins, setElins] = useState<V35RegionalELINS | null>(null);
  const [esoPresent, setEsoPresent] = useState<boolean>(false);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const r = await elinsRegionalRun(region, topic.trim() || undefined);
      setElins(r.elins);
      setEsoPresent(r.eso_present);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, [region, topic]);

  useEffect(() => { void run(); /* run on mount + region change */
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [region]);

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>{region}</Text>
      <Text style={styles.subtitle}>Regional ELINS · v35</Text>

      <View style={styles.regionRow}>
        {V35_REGION_CODES.map((r) => (
          <Pressable
            key={r}
            onPress={() => setRegion(r)}
            style={[styles.regionPill, r === region && styles.regionPillActive]}
          >
            <Text style={[styles.regionLabel, r === region && styles.regionLabelActive]}>{r}</Text>
          </Pressable>
        ))}
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Topic hint (optional)</Text>
        <TextInput
          value={topic}
          onChangeText={setTopic}
          placeholder="e.g. Fed rate decision"
          placeholderTextColor={colors.textTertiary}
          style={styles.input}
          maxLength={2000}
        />
        <Pressable
          onPress={() => void run()}
          disabled={busy}
          style={[styles.cta, busy && styles.disabled]}
        >
          <Text style={styles.ctaLabel}>
            {busy ? <ActivityIndicator color="#04121b" /> : "Run regional pass"}
          </Text>
        </Pressable>
      </View>

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
      )}

      {elins && (
        <View style={styles.card}>
          <View style={styles.summaryHead}>
            <Text style={styles.h2}>{elins.region_code} · {elins.synthesis.signal}</Text>
            <View style={[styles.esoBadge, !esoPresent && styles.esoBadgeOff]}>
              <Text style={[styles.esoBadgeText, !esoPresent && styles.esoBadgeTextOff]}>
                {esoPresent ? (elins.external_signals.mock ? "ESO mock" : "ESO live") : "ESO off"}
              </Text>
            </View>
          </View>
          <Row k="EP intensity mean" v={elins.ep_field_summary.intensity_mean.toFixed(3)} />
          <Row k="Stress / Relief" v={`${elins.ep_field_summary.stress_total.toFixed(3)} / ${elins.ep_field_summary.relief_total.toFixed(3)}`} />
          <Row k="Top primitive" v={`${elins.synthesis.top_primitive} (${elins.synthesis.top_primitive_intensity.toFixed(3)})`} />
          <Row k="Domain" v={elins.synthesis.domain || "—"} />
          <Row k="Trend" v={elins.synthesis.trend} />

          <Text style={[styles.h3, { marginTop: space.s3 }]}>Primitives</Text>
          {Object.entries(elins.primitives.intensities)
            .sort((a, b) => b[1] - a[1])
            .map(([k, v]) => (
              <Row key={k} k={k} v={String(v.toFixed(3))} />
            ))}

          {elins.external_signals.present && elins.external_signals.anchors.length > 0 && (
            <View>
              <Text style={[styles.h3, { marginTop: space.s3 }]}>External anchors (ESO)</Text>
              {elins.external_signals.anchors.map((a) => (
                <Text key={a} style={styles.anchorLine}>• {a}</Text>
              ))}
            </View>
          )}

          <Pressable
            style={styles.linkRow}
            onPress={() =>
              router.push({ pathname: "/regional_forecast", params: { region: elins.region_code } })
            }
          >
            <Text style={styles.linkText}>Open forecast →</Text>
          </Pressable>
        </View>
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
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s4 },
  h2: { color: colors.textPrimary, fontSize: 16, fontWeight: "600" },
  h3: { color: colors.textSecondary, fontSize: 12, fontWeight: "600", textTransform: "uppercase", letterSpacing: 0.5 },
  label: { color: colors.textSecondary, fontSize: 12, marginBottom: 4 },
  card: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.lg, padding: space.s4, marginBottom: space.s4,
  },
  regionRow: { flexDirection: "row", flexWrap: "wrap", gap: space.s2, marginBottom: space.s4 },
  regionPill: {
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill,
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
  },
  regionPillActive: { borderColor: colors.accent, backgroundColor: colors.bgElevated },
  regionLabel: { color: colors.textPrimary, fontSize: 12 },
  regionLabelActive: { color: colors.accent, fontWeight: "600" },
  input: {
    backgroundColor: colors.bgDeep, borderColor: colors.borderStrong, borderWidth: 1,
    borderRadius: radius.md, padding: 12, color: colors.textPrimary, fontSize: 13,
    marginBottom: space.s3,
  },
  cta: {
    backgroundColor: colors.accent, paddingVertical: 12, borderRadius: radius.pill,
    alignItems: "center",
  },
  ctaLabel: { color: "#04121b", fontWeight: "700" },
  disabled: { opacity: 0.4 },
  summaryHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: space.s2 },
  esoBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: radius.pill, borderColor: colors.accent, borderWidth: 1 },
  esoBadgeOff: { borderColor: colors.textTertiary },
  esoBadgeText: { color: colors.accent, fontSize: 10, fontWeight: "600" },
  esoBadgeTextOff: { color: colors.textTertiary },
  kvRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 3 },
  kvKey: { color: colors.textSecondary, fontSize: 12 },
  kvVal: { color: colors.textPrimary, fontSize: 12, fontFamily: "Menlo" },
  anchorLine: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
  linkRow: { paddingVertical: space.s2, alignItems: "center", marginTop: space.s3 },
  linkText: { color: colors.accent, fontSize: 13, fontWeight: "600" },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
