import { useCallback, useState } from "react";
import {
  FlatList,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { listNotes, listSessions, type VaultItem, type VaultNote, type VaultSession } from "../lib/vault";
import { colors, radius, space } from "../lib/theme";

type Combined = VaultItem;

export default function VaultScreen() {
  const [notes, setNotes] = useState<VaultNote[]>([]);
  const [sessions, setSessions] = useState<VaultSession[]>([]);
  const [active, setActive] = useState<Combined | null>(null);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      (async () => {
        const [n, s] = await Promise.all([listNotes(), listSessions()]);
        if (cancelled) return;
        setNotes(n);
        setSessions(s);
      })();
      return () => {
        cancelled = true;
      };
    }, [])
  );

  const items: Combined[] = [...notes, ...sessions].sort((a, b) =>
    b.createdAt.localeCompare(a.createdAt)
  );

  return (
    <View style={{ flex: 1, backgroundColor: colors.bgDeep }}>
      <FlatList
        data={items}
        keyExtractor={(i) => i.type + ":" + i.id}
        ListHeaderComponent={
          <View style={{ padding: space.s5, paddingBottom: 0 }}>
            <Text style={styles.h1}>Vault</Text>
            <Text style={styles.muted}>
              {items.length} item{items.length === 1 ? "" : "s"} · on-device only
            </Text>
          </View>
        }
        ListEmptyComponent={
          <View style={{ padding: space.s5 }}>
            <Text style={styles.muted}>
              Nothing saved yet. Use Paste from clipboard or Done in a session to save here.
            </Text>
          </View>
        }
        renderItem={({ item }) => (
          <Pressable onPress={() => setActive(item)} style={styles.row}>
            <Text style={styles.rowTitle} numberOfLines={1}>
              {firstLine(item.content)}
            </Text>
            <Text style={styles.rowMeta}>
              {item.type} · {new Date(item.createdAt).toLocaleString()}
              {item.tags.length ? "  ·  " + item.tags.join(", ") : ""}
            </Text>
          </Pressable>
        )}
        contentContainerStyle={{ paddingBottom: space.s7 }}
      />

      <Modal
        visible={!!active}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setActive(null)}
      >
        <View style={{ flex: 1, backgroundColor: colors.bgDeep }}>
          <View style={styles.detailHeader}>
            <Pressable onPress={() => setActive(null)} hitSlop={10}>
              <Text style={styles.close}>Close</Text>
            </Pressable>
          </View>
          <ScrollView contentContainerStyle={{ padding: space.s5 }}>
            {active && (
              <>
                <Text style={styles.detailMeta}>
                  {active.type} · {new Date(active.createdAt).toLocaleString()}
                </Text>
                {active.tags.length > 0 && (
                  <Text style={styles.detailTags}>tags: {active.tags.join(", ")}</Text>
                )}
                <Text style={styles.detailContent}>{active.content}</Text>
              </>
            )}
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

function firstLine(s: string) {
  const trimmed = s.split("\n").find((l) => l.trim()) || s;
  return trimmed.length > 80 ? trimmed.slice(0, 80) + "…" : trimmed;
}

const styles = StyleSheet.create({
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "600", marginBottom: 4 },
  muted: { color: colors.textSecondary, fontSize: 13 },
  row: {
    marginHorizontal: space.s5,
    marginTop: space.s3,
    padding: space.s4,
    backgroundColor: colors.bgSurface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
  },
  rowTitle: { color: colors.textPrimary, fontSize: 15, fontWeight: "500" },
  rowMeta: { color: colors.textTertiary, fontSize: 12, marginTop: 2 },
  detailHeader: {
    padding: space.s4,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    alignItems: "flex-end",
  },
  close: { color: colors.accent, fontSize: 14, fontWeight: "500" },
  detailMeta: { color: colors.textTertiary, fontSize: 12, marginBottom: space.s2 },
  detailTags: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s4 },
  detailContent: {
    color: colors.textPrimary,
    fontFamily: "Menlo",
    fontSize: 13,
    lineHeight: 20,
  },
});
