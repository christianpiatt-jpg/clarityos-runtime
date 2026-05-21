// ClarityOS Mobile — Entity graph search (v37).

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator, Pressable, RefreshControl,
  ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import { router } from "expo-router";
import { elinsEntitiesSearch, type V37EntitySearchHit } from "../lib/api";
import { colors, radius, space } from "../lib/theme";

export default function EntitiesScreen() {
  const [q, setQ] = useState<string>("");
  const [rows, setRows] = useState<V37EntitySearchHit[]>([]);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [graphTs, setGraphTs] = useState<number>(0);
  const reqId = useRef<number>(0);

  const load = useCallback(async (query: string) => {
    const myId = ++reqId.current;
    setBusy(true); setError(null);
    try {
      const r = await elinsEntitiesSearch(query, 50);
      if (myId !== reqId.current) return;
      setRows(r.entities); setGraphTs(r.graph_updated_ts);
    } catch (e: unknown) {
      if (myId !== reqId.current) return;
      setError(e instanceof Error ? e.message : String(e));
    } finally { if (myId === reqId.current) setBusy(false); }
  }, []);

  useEffect(() => { void load(""); }, [load]);
  useEffect(() => {
    const t = setTimeout(() => void load(q), 200);
    return () => clearTimeout(t);
  }, [q, load]);

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={styles.container}
      refreshControl={<RefreshControl refreshing={busy} onRefresh={() => load(q)} tintColor={colors.accent} />}
    >
      <Text style={styles.h1}>Entity graph</Text>
      <Text style={styles.subtitle}>
        v37 cross-cluster · {graphTs > 0 ? new Date(graphTs * 1000).toISOString().slice(0, 19) : "no graph yet"}
      </Text>

      <TextInput
        value={q}
        onChangeText={setQ}
        placeholder="Search entities (e.g. Iran, Federal Reserve)…"
        placeholderTextColor={colors.textTertiary}
        style={styles.input}
        maxLength={200}
      />

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
      )}

      {busy && rows.length === 0 ? (
        <ActivityIndicator color={colors.accent} style={{ marginTop: space.s4 }} />
      ) : rows.length === 0 ? (
        <Text style={styles.empty}>{q ? "No matches" : "No entities yet"}</Text>
      ) : (
        rows.map((r) => (
          <Pressable
            key={r.name}
            style={styles.card}
            onPress={() =>
              router.push({ pathname: "/entity_detail", params: { entity: r.name } })
            }
          >
            <View style={styles.cardHead}>
              <Text style={styles.cardTitle}>{r.name}</Text>
              <Text style={styles.cardMeta}>deg {r.degree} · ep {r.ep_mean.toFixed(3)}</Text>
            </View>
            {(r.top_domains.length > 0 || r.clusters.length > 0) && (
              <Text style={styles.cardSub}>
                {r.top_domains.join(" · ")}
                {r.top_domains.length > 0 && r.clusters.length > 0 ? "  ·  " : ""}
                {r.clusters.length > 0 ? `[${r.clusters.join(",")}]` : ""}
              </Text>
            )}
          </Pressable>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s4, fontFamily: "Menlo" },
  input: {
    backgroundColor: colors.bgSurface, borderColor: colors.borderStrong, borderWidth: 1,
    borderRadius: radius.md, padding: 12, color: colors.textPrimary, fontSize: 13,
    marginBottom: space.s3,
  },
  card: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.md, padding: space.s4, marginBottom: space.s3,
  },
  cardHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" },
  cardTitle: { color: colors.textPrimary, fontSize: 13, fontWeight: "700", flex: 1, marginRight: space.s2 },
  cardMeta: { color: colors.textTertiary, fontSize: 11, fontFamily: "Menlo" },
  cardSub: { color: colors.textSecondary, fontSize: 11, marginTop: 4 },
  empty: { color: colors.textTertiary, fontSize: 12, textAlign: "center", marginTop: space.s5 },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
