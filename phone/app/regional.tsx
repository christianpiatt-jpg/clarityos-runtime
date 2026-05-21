// ClarityOS Mobile — Regional ELINS list (v35).
// Pulls /elins/regional/list and lets the user drill into a region.

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { elinsRegionalList, type V35RegionalListItem } from "../lib/api";
import { colors, radius, space } from "../lib/theme";

export default function RegionalScreen() {
  const [items, setItems] = useState<V35RegionalListItem[]>([]);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const r = await elinsRegionalList();
      setItems(r.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={styles.container}
      refreshControl={
        <RefreshControl refreshing={busy} onRefresh={load} tintColor={colors.accent} />
      }
    >
      <Text style={styles.h1}>Regional ELINS</Text>
      <Text style={styles.subtitle}>v35 · {items.length} regions</Text>

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
      )}

      {busy && items.length === 0 && (
        <ActivityIndicator color={colors.accent} style={{ marginTop: space.s4 }} />
      )}

      <View style={styles.grid}>
        {items.map((item) => (
          <Pressable
            key={item.region_code}
            style={styles.card}
            onPress={() =>
              router.push({ pathname: "/regional_detail", params: { region: item.region_code } })
            }
          >
            <View style={styles.cardHead}>
              <Text style={styles.cardTitle}>{item.region_code}</Text>
              {item.latest?.external_present && (
                <View style={styles.esoBadge}>
                  <Text style={styles.esoBadgeText}>ESO</Text>
                </View>
              )}
            </View>
            {item.latest ? (
              <View>
                <Text style={styles.cardLine}>
                  top: <Text style={styles.cardEm}>
                    {(item.latest.summary as { top_primitive?: string })?.top_primitive || "—"}
                  </Text>
                </Text>
                <Text style={styles.cardLine}>
                  signal: <Text style={styles.cardEm}>
                    {(item.latest.summary as { signal?: string })?.signal || "—"}
                  </Text>
                </Text>
                <Text style={styles.cardDay}>{item.latest.day}</Text>
              </View>
            ) : (
              <Text style={styles.cardEmpty}>No runs yet</Text>
            )}
          </Pressable>
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s4 },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: space.s3 },
  card: {
    flexBasis: "47%", flexGrow: 1,
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.md, padding: space.s4,
  },
  cardHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: space.s2 },
  cardTitle: { color: colors.textPrimary, fontSize: 15, fontWeight: "700" },
  cardLine: { color: colors.textSecondary, fontSize: 12, marginBottom: 2 },
  cardEm: { color: colors.textPrimary, fontWeight: "600" },
  cardDay: { color: colors.textTertiary, fontSize: 10, fontFamily: "Menlo", marginTop: 4 },
  cardEmpty: { color: colors.textTertiary, fontSize: 11, fontStyle: "italic" },
  esoBadge: {
    paddingHorizontal: 6, paddingVertical: 1,
    borderRadius: radius.pill, borderColor: colors.accent, borderWidth: 1,
  },
  esoBadgeText: { color: colors.accent, fontSize: 9, fontWeight: "600" },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
