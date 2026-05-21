// ClarityOS Mobile — Threads list screen (v49).
// Mirrors web/src/routes/Threads.tsx left-column semantics: list every
// thread for the caller, newest-first by updated_at, plus a "+ NEW"
// CTA in the header that creates a thread and pushes /thread/[id].
//
// Style follows memory_vault.tsx + memory_vault_embeddings.tsx — RN
// primitives + StyleSheet + theme tokens.

import { useCallback, useState } from "react";
import {
  ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View,
} from "react-native";
import { router, useFocusEffect } from "expo-router";
import {
  createThread, listThreads, type ThreadMeta,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";

export default function ThreadsScreen() {
  const [threads, setThreads] = useState<ThreadMeta[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy("load"); setError(null);
    try {
      const list = await listThreads();
      // Backend already returns updated_at-desc; sort defensively.
      const sorted = [...list].sort(
        (a, b) => (b.updated_at || 0) - (a.updated_at || 0),
      );
      setThreads(sorted);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  // Reload on focus so a deletion or message-send from the detail
  // screen reflects when the user pops back here.
  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const onNewThread = useCallback(async () => {
    if (busy) return;
    setBusy("new"); setError(null);
    try {
      const meta = await createThread(null);
      router.push(`/thread/${meta.thread_id}` as any);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, [busy]);

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.h1}>Threads</Text>
          <Text style={styles.subtitle}>
            v47 · {threads.length} thread{threads.length === 1 ? "" : "s"}
          </Text>
        </View>
        <Pressable
          onPress={onNewThread}
          disabled={busy !== null}
          style={[styles.cta, busy === "new" && styles.ctaDisabled]}
        >
          <Text style={styles.ctaLabel}>
            {busy === "new" ? "…" : "+ NEW"}
          </Text>
        </Pressable>
      </View>

      {error && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {busy === "load" && threads.length === 0 && (
        <ActivityIndicator color={colors.accent} style={{ marginTop: space.s4 }} />
      )}

      <View style={styles.card}>
        {threads.length === 0 && busy !== "load" && (
          <Text style={styles.muted}>
            No threads yet. Tap + NEW to start a conversation.
          </Text>
        )}
        {threads.map((t) => (
          <Pressable
            key={t.thread_id}
            onPress={() => router.push(`/thread/${t.thread_id}` as any)}
            style={styles.row}
            accessibilityLabel={`Open thread ${displayTitle(t)}`}
          >
            <View style={{ flex: 1 }}>
              <Text style={styles.title} numberOfLines={1}>
                {displayTitle(t)}
              </Text>
              {t.summary ? (
                <Text style={styles.summary} numberOfLines={2}>
                  {t.summary}
                </Text>
              ) : null}
              <Text style={styles.meta}>
                {t.message_count} message{t.message_count === 1 ? "" : "s"}
                {" · "}{relativeTime(t.updated_at)}
              </Text>
            </View>
            <Text style={styles.chevron}>›</Text>
          </Pressable>
        ))}
      </View>
    </ScrollView>
  );
}

function displayTitle(t: ThreadMeta): string {
  const raw = (t.title || "").trim();
  return raw || "Untitled Thread";
}

function relativeTime(ts_ms: number): string {
  if (!ts_ms) return "—";
  const diff = Date.now() - ts_ms;
  if (diff < 0) return new Date(ts_ms).toLocaleTimeString();
  const s = Math.floor(diff / 1000);
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d ago`;
  return new Date(ts_ms).toLocaleDateString();
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  headerRow: {
    flexDirection: "row", justifyContent: "space-between",
    alignItems: "flex-start", marginBottom: space.s4,
  },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginTop: 2 },
  cta: {
    backgroundColor: colors.accent, paddingVertical: 8, paddingHorizontal: 14,
    borderRadius: radius.pill, alignItems: "center",
  },
  ctaDisabled: { opacity: 0.6 },
  ctaLabel: { color: "#04121b", fontWeight: "700", fontSize: 12 },
  card: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.lg, paddingVertical: space.s2,
  },
  row: {
    flexDirection: "row", alignItems: "center",
    paddingVertical: space.s4, paddingHorizontal: space.s4,
    borderBottomColor: colors.border, borderBottomWidth: 1,
    gap: space.s3,
  },
  title: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  summary: {
    color: colors.textSecondary, fontSize: 12, marginTop: 4,
    lineHeight: 16,
  },
  meta: { color: colors.textTertiary, fontSize: 11, marginTop: 2 },
  chevron: { color: colors.textTertiary, fontSize: 22 },
  muted: {
    color: colors.textTertiary, fontSize: 11,
    paddingVertical: space.s4, paddingHorizontal: space.s4,
  },
  errorBox: {
    padding: space.s3, backgroundColor: "#3a1414",
    borderRadius: radius.md, marginBottom: space.s3,
  },
  errorText: { color: "#ff8a8a" },
});
