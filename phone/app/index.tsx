import { useEffect, useState, useCallback } from "react";
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";
import { router, useFocusEffect } from "expo-router";
import Orb from "../components/Orb";
import NodeStatusBlock from "../components/NodeStatus";
import SegmentedToggle from "../components/EngineToggle";
import ElInsIndicator from "../components/ElInsIndicator";
import * as api from "../lib/api";
import { storage, KEYS } from "../lib/storage";
import { colors, radius, space } from "../lib/theme";

type Thread = { id: string; title: string; created: number; log: { kind: string; text: string; ts: number }[] };
type Mode = "c" | "G";

function newThread(): Thread {
  return { id: "t_" + Math.random().toString(36).slice(2, 10), title: "New thread", created: Date.now(), log: [] };
}

export default function HomeScreen() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [mode, setMode] = useState<Mode>("G");
  const [cloud, setCloud] = useState<{ status: "ok" | "err" | "idle"; meta: string }>({ status: "idle", meta: "checking…" });
  const [me, setMe] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const loadThreads = useCallback(async () => {
    const raw = await storage.get(KEYS.threads);
    let list: Thread[] = [];
    if (raw) { try { list = JSON.parse(raw); } catch { list = []; } }
    setThreads(list);
  }, []);

  const probeCloud = useCallback(async () => {
    try {
      const t0 = Date.now();
      const r = await api.health();
      setCloud({ status: "ok", meta: `${r.version} · ${Date.now() - t0}ms` });
    } catch (e: any) {
      setCloud({ status: "err", meta: e?.message || "unreachable" });
    }
  }, []);

  useFocusEffect(useCallback(() => {
    if (!api.getSession()) {
      router.replace("/login");
      return;
    }
    setMe(api.getUser());
    loadThreads();
    probeCloud();
    storage.get(KEYS.mode).then((v) => v && setMode(v as Mode));
  }, [loadThreads, probeCloud]));

  async function setModePersist(m: Mode) {
    setMode(m);
    await storage.set(KEYS.mode, m);
  }

  async function createThread() {
    const t = newThread();
    const next = [t, ...threads];
    setThreads(next);
    await storage.set(KEYS.threads, JSON.stringify(next));
    await storage.set(KEYS.activeThread, t.id);
    router.push(`/session/${t.id}`);
  }

  async function onRefresh() {
    setRefreshing(true);
    await Promise.all([loadThreads(), probeCloud()]);
    setRefreshing(false);
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bgDeep }}>
      <FlatList
        data={threads.slice().sort((a, b) => b.created - a.created)}
        keyExtractor={(t) => t.id}
        ListHeaderComponent={
          <View style={{ padding: space.s5 }}>
            <View style={{ alignItems: "center", marginBottom: space.s5 }}>
              <Orb size={140} />
              <Text style={styles.greeting}>{me ? `Hi, ${me}` : "ClarityOS"}</Text>
            </View>

            <NodeStatusBlock
              local={{ name: "#c local", meta: "on-device stub adapter", status: "ok" }}
              cloud={{ name: "#G cloud", meta: cloud.meta, status: cloud.status }}
            />

            <View style={styles.row}>
              <Text style={styles.section}>Mode</Text>
              <SegmentedToggle
                value={mode}
                options={[{ value: "c", label: "#c" }, { value: "G", label: "#G" }]}
                onChange={(v) => setModePersist(v)}
              />
            </View>

            <Pressable
              onPress={() => router.push("/dashboard")}
              style={styles.dashboardCta}
            >
              <Text style={styles.dashboardCtaLabel}>ELINS dashboard →</Text>
              <Text style={styles.dashboardCtaSub}>Global · Regional · Macro · Entity</Text>
            </Pressable>

            <ElInsIndicator />

            <View style={[styles.row, { justifyContent: "space-between", marginTop: space.s5 }]}>
              <Text style={styles.section}>Sessions</Text>
              <Pressable onPress={createThread} style={styles.addBtn}>
                <Text style={styles.addBtnLabel}>+ New</Text>
              </Pressable>
            </View>
          </View>
        }
        renderItem={({ item }) => (
          <Pressable onPress={() => router.push(`/session/${item.id}`)} style={styles.threadRow}>
            <Text style={styles.threadTitle} numberOfLines={1}>{item.title || "Untitled"}</Text>
            <Text style={styles.threadMeta}>{new Date(item.created).toLocaleString()} · {item.log.length} msgs</Text>
          </Pressable>
        )}
        ListEmptyComponent={
          <View style={{ padding: space.s5 }}>
            <Text style={{ color: colors.textTertiary, textAlign: "center" }}>No threads yet. Tap + New to start.</Text>
          </View>
        }
        ListFooterComponent={
          <Pressable onPress={() => router.push("/settings")} style={styles.settingsBtn}>
            <Text style={{ color: colors.textSecondary }}>Settings</Text>
          </Pressable>
        }
        contentContainerStyle={{ paddingBottom: space.s7 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  greeting: { color: colors.textPrimary, fontSize: 20, fontWeight: "600", marginTop: space.s4 },
  row: { flexDirection: "row", alignItems: "center", gap: space.s4, marginTop: space.s5 },
  section: { color: colors.textSecondary, fontSize: 13, textTransform: "uppercase", letterSpacing: 0.6 },
  addBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.borderStrong, backgroundColor: colors.bgSurface },
  addBtnLabel: { color: colors.textPrimary, fontSize: 13 },
  threadRow: {
    marginHorizontal: space.s5,
    marginBottom: space.s2,
    padding: space.s4,
    backgroundColor: colors.bgSurface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
  },
  threadTitle: { color: colors.textPrimary, fontSize: 15, fontWeight: "500" },
  threadMeta: { color: colors.textTertiary, fontSize: 12, marginTop: 2 },
  settingsBtn: { alignItems: "center", padding: space.s5 },
  dashboardCta: {
    marginTop: space.s5,
    paddingVertical: space.s4,
    paddingHorizontal: space.s4,
    borderRadius: radius.md,
    backgroundColor: colors.bgSurface,
    borderColor: colors.accent,
    borderWidth: 1,
  },
  dashboardCtaLabel: { color: colors.accent, fontSize: 14, fontWeight: "700" },
  dashboardCtaSub: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
});
