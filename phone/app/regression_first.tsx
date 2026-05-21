// ClarityOS Mobile — v80 Regression-First packet runner.

import { useCallback, useState } from "react";
import {
  ActivityIndicator, Pressable, ScrollView, StyleSheet,
  Text, TextInput, View,
} from "react-native";
import {
  postRegressionFirstPacket,
  replayRegressionFirstChain,
  type RegressionFirstChain,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";

const EXAMPLE_PACKET = `{
  "EL": 2,
  "INS": 3,
  "ratio": "0.67",
  "el_signals": ["something is wrong"],
  "ins_signals": ["page", "scaffold"],
  "classification": "structure-dominant",
  "operator_intent": "Identify root cause of rendering failure.",
  "regression_required": true,
  "regression_chain": [
    {
      "layer": 1,
      "name": "Domain & Routing",
      "question": "Which page is set as homepage?",
      "location": "Settings → Reading → Homepage",
      "goal": "Correct page selected"
    }
  ],
  "recommended_system_action": "Pause and request operator verification."
}`;

export default function RegressionFirstScreen() {
  const [packetText, setPacketText] = useState(EXAMPLE_PACKET);
  const [busy, setBusy]     = useState(false);
  const [error, setError]   = useState<string | null>(null);
  const [chain, setChain]   = useState<RegressionFirstChain | null>(null);
  const [source, setSource] = useState<"packet" | "replay" | null>(null);

  const run = useCallback(async () => {
    setBusy(true); setError(null); setChain(null); setSource(null);
    let parsed: Record<string, unknown>;
    try {
      const raw = JSON.parse(packetText);
      if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
        throw new Error("packet must be a JSON object");
      }
      parsed = raw as Record<string, unknown>;
    } catch (e) {
      setError(
        e instanceof Error ? `invalid_json: ${e.message}` : String(e),
      );
      setBusy(false);
      return;
    }
    try {
      const result = await postRegressionFirstPacket(parsed);
      setChain(result);
      setSource("packet");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [packetText]);

  const rerun = useCallback(async () => {
    if (!chain) return;
    const id = chain.chain_id;
    setBusy(true); setError(null);
    try {
      const result = await replayRegressionFirstChain(id);
      setChain(result);
      setSource("replay");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [chain]);

  const seeded = chain && chain.layers.length > 0
    ? chain.layers[chain.layers.length - 1]
    : null;

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>Regression First</Text>
      <Text style={styles.subhead}>v80 — packet runner</Text>

      <View style={styles.card}>
        <Text style={styles.label}>Cognitive packet (JSON)</Text>
        <TextInput
          value={packetText}
          onChangeText={setPacketText}
          placeholder="Paste a packet emitted under the bundle prompt"
          placeholderTextColor={colors.textTertiary}
          multiline
          autoCorrect={false}
          autoCapitalize="none"
          spellCheck={false}
          style={[styles.input, styles.code, { minHeight: 220 }]}
        />
        <Pressable
          onPress={() => void run()}
          disabled={busy}
          style={[styles.cta, busy && styles.disabled]}
        >
          {busy
            ? <ActivityIndicator color="#04121b" />
            : <Text style={styles.ctaLabel}>Run Regression First</Text>}
        </Pressable>
      </View>

      {error && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {chain && (
        <View style={styles.card}>
          <Text style={styles.h2}>
            Chain {source === "replay" ? "(replay)" : ""}
          </Text>
          <Row k="Title"     v={chain.title} />
          <Row k="Chain id"  v={chain.chain_id} />
          <Row
            k="State"
            v={`${chain.closed_at ? "closed" : "open"} · layers=${chain.layers.length} · tags=${Object.keys(chain.tags).length}`}
          />
          {seeded && (
            <Row
              k="Seeded layer"
              v={`index ${seeded.layer_index} · status ${seeded.status}`}
            />
          )}
          <Pressable
            onPress={() => void rerun()}
            disabled={busy}
            style={[styles.ctaSecondary, busy && styles.disabled]}
          >
            <Text style={styles.ctaSecondaryLabel}>Rerun regression</Text>
          </Pressable>
        </View>
      )}
    </ScrollView>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.k}>{k}</Text>
      <Text style={styles.v}>{v}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bg },
  container: { padding: space.md, paddingBottom: space.xxl, gap: space.md },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "600" },
  subhead: { color: colors.textTertiary, fontSize: 12 },
  h2: {
    color: colors.textPrimary, fontSize: 16, fontWeight: "600",
    marginBottom: space.sm,
  },
  card: {
    backgroundColor: colors.surface, borderRadius: radius.md,
    padding: space.md, gap: space.sm,
  },
  label: { color: colors.textSecondary, fontSize: 12 },
  input: {
    backgroundColor: colors.bg, color: colors.textPrimary,
    borderRadius: radius.sm, padding: space.sm, fontSize: 13,
  },
  code: { fontFamily: "Menlo" },
  cta: {
    backgroundColor: colors.accent, borderRadius: radius.sm,
    paddingVertical: space.sm, alignItems: "center",
  },
  ctaLabel: { color: "#04121b", fontWeight: "600" },
  ctaSecondary: {
    backgroundColor: colors.bgElevated, borderRadius: radius.sm,
    paddingVertical: space.sm, alignItems: "center", marginTop: space.sm,
  },
  ctaSecondaryLabel: { color: colors.textPrimary, fontWeight: "500" },
  disabled: { opacity: 0.5 },
  errorBox: {
    backgroundColor: "rgba(255,69,58,0.15)",
    borderRadius: radius.sm, padding: space.sm,
  },
  errorText: { color: "#ff4538", fontSize: 12 },
  row: { flexDirection: "row", alignItems: "flex-start", gap: space.sm },
  k: { color: colors.textSecondary, fontSize: 12, minWidth: 110 },
  v: { color: colors.textPrimary, fontSize: 13, flex: 1 },
});
