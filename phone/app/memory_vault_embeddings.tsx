// ClarityOS Mobile — Memory Vault embeddings screen (v46).
// List embeddings (key + dim), delete an embedding. Vector contents are
// not displayed to keep the surface small.

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View,
} from "react-native";
import {
  meVaultEmbeddings, meVaultEmbeddingsDelete,
  type V46VaultEmbedding,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";

export default function MemoryVaultEmbeddingsScreen() {
  const [embeddings, setEmbeddings] = useState<V46VaultEmbedding[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy("load"); setError(null);
    try {
      const r = await meVaultEmbeddings();
      setEmbeddings(r.embeddings);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const remove = useCallback(async (key: string) => {
    setBusy("del"); setError(null);
    try {
      await meVaultEmbeddingsDelete(key);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, [load]);

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>Embeddings</Text>
      <Text style={styles.subtitle}>
        v46 vault · {embeddings.length} entries · vectors not displayed
      </Text>

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
      )}

      {busy === "load" && embeddings.length === 0 && (
        <ActivityIndicator color={colors.accent} style={{ marginTop: space.s4 }} />
      )}

      <View style={styles.card}>
        {embeddings.length === 0 && (
          <Text style={styles.muted}>
            No embeddings stored yet. Send a vector to POST /me/vault/embeddings
            to add one.
          </Text>
        )}
        {embeddings.map((e) => (
          <View key={e.key} style={styles.row}>
            <View style={{ flex: 1 }}>
              <Text style={styles.key}>{e.key}</Text>
              <Text style={styles.muted}>dim: {e.dim}</Text>
            </View>
            <Pressable onPress={() => void remove(e.key)} disabled={busy !== null}>
              <Text style={styles.delete}>Delete</Text>
            </Pressable>
          </View>
        ))}
      </View>

      <Pressable onPress={() => void load()} disabled={busy !== null} style={styles.cta}>
        <Text style={styles.ctaLabel}>{busy === "load" ? "…" : "Refresh"}</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s4 },
  card: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.lg, padding: space.s4, marginBottom: space.s3,
  },
  row: {
    flexDirection: "row", paddingVertical: 6,
    borderBottomColor: colors.border, borderBottomWidth: 1, gap: space.s3,
    alignItems: "center",
  },
  key: { color: colors.accent, fontSize: 12, fontFamily: "Menlo" },
  muted: { color: colors.textTertiary, fontSize: 11 },
  delete: { color: "#ff8a8a", fontSize: 11 },
  cta: {
    backgroundColor: colors.bgElevated, borderColor: colors.border, borderWidth: 1,
    paddingVertical: 10, borderRadius: radius.pill, alignItems: "center",
    marginTop: space.s2,
  },
  ctaLabel: { color: colors.textPrimary, fontWeight: "600", fontSize: 13 },
  errorBox: {
    padding: space.s3, backgroundColor: "#3a1414",
    borderRadius: radius.md, marginBottom: space.s3,
  },
  errorText: { color: "#ff8a8a" },
});
