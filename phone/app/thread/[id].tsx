// ClarityOS Mobile — Thread detail screen (v49).
// Mirrors web/src/routes/Threads.tsx right-column semantics: header
// (title + meta + Rename/Delete actions), scrollable message log
// (user right-aligned, assistant left-aligned with model footer),
// composer at the bottom.
//
// Style follows memory_vault.tsx patterns + session/[id].tsx for the
// composer keyboard behaviour.

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  ActivityIndicator, Alert, KeyboardAvoidingView, Modal, Platform,
  Pressable, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import {
  router, useLocalSearchParams, useNavigation,
} from "expo-router";
import {
  deleteThread, getThread, postThreadMessage, renameThread,
  summarizeThread,
  type DirectiveMeta, type GroundingStatus,
  type ThreadMessage, type ThreadMeta,
} from "../../lib/api";
import { colors, radius, space } from "../../lib/theme";

// A19/A30 — view-model: a thread message plus the per-turn directive surface
// (cite grounding + directive_metadata). Rides on the live POST response, so
// present only for turns sent this session; absent for rehydrated history.
type ChatMessage = ThreadMessage & {
  grounding_status?: GroundingStatus | null;
  directive_metadata?: Record<string, DirectiveMeta> | null;
};

const DIRECTIVE_LABEL: Record<string, string> = {
  structure: "Structure", primitives: "Primitives", regression: "Regression",
  compare: "Compare", reduce: "Reduce", operator: "Operator",
};

export default function ThreadDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const navigation = useNavigation();

  const [meta, setMeta] = useState<ThreadMeta | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const [renameOpen, setRenameOpen] = useState(false);
  const [renameDraft, setRenameDraft] = useState("");

  const scrollRef = useRef<ScrollView | null>(null);
  function scrollToBottom() {
    setTimeout(
      () => scrollRef.current?.scrollToEnd({ animated: true }),
      0,
    );
  }

  // ------------ Load ------------
  const load = useCallback(async (thread_id: string) => {
    setBusy("load"); setLoadError(null);
    try {
      const r = await getThread(thread_id);
      setMeta(r.meta);
      setMessages(r.messages);
      scrollToBottom();
    } catch (e: unknown) {
      setLoadError(e instanceof Error ? e.message : String(e));
      setMeta(null);
      setMessages([]);
    } finally { setBusy(null); }
  }, []);

  useEffect(() => {
    if (id) void load(id);
  }, [id, load]);

  // ------------ Header (rename / delete actions) ------------
  useLayoutEffect(() => {
    navigation.setOptions({
      title: meta ? displayTitle(meta) : "Thread",
    });
  }, [navigation, meta]);

  // ------------ Mutators ------------
  const onSend = useCallback(async () => {
    if (!id || !meta) return;
    const text = draft.trim();
    if (!text || busy) return;
    setBusy("send"); setLoadError(null);
    try {
      const r = await postThreadMessage(id, text);
      setMeta(r.meta);
      setMessages((cur) => [
        ...cur,
        r.user_message,
        {
          ...r.assistant_message,
          grounding_status: r.grounding_status ?? null,
          directive_metadata: r.directive_metadata ?? null,
        },
      ]);
      setDraft("");
      scrollToBottom();
    } catch (e: unknown) {
      setLoadError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, [id, meta, draft, busy]);

  const onSummarize = useCallback(async () => {
    if (!id || !meta || busy) return;
    setBusy("summarize"); setLoadError(null);
    try {
      const updated = await summarizeThread(id);
      setMeta(updated);
    } catch (e: unknown) {
      setLoadError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, [id, meta, busy]);

  const openRename = useCallback(() => {
    if (!meta) return;
    setRenameDraft(meta.title || "");
    setRenameOpen(true);
  }, [meta]);

  const commitRename = useCallback(async () => {
    if (!id || !meta) return;
    setBusy("rename"); setLoadError(null);
    try {
      const updated = await renameThread(id, renameDraft.trim());
      setMeta(updated);
      setRenameOpen(false);
      setRenameDraft("");
    } catch (e: unknown) {
      setLoadError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, [id, meta, renameDraft]);

  const onDelete = useCallback(() => {
    if (!id || !meta) return;
    const title = displayTitle(meta);
    Alert.alert(
      "Delete thread?",
      `"${title}" will be removed. This cannot be undone.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            setBusy("delete"); setLoadError(null);
            try {
              await deleteThread(id);
              router.back();
            } catch (e: unknown) {
              setLoadError(e instanceof Error ? e.message : String(e));
            } finally { setBusy(null); }
          },
        },
      ],
    );
  }, [id, meta]);

  // ------------ Render ------------
  if (busy === "load" && !meta) {
    return (
      <View style={styles.loadingPane}>
        <ActivityIndicator color={colors.accent} />
        <Text style={styles.loadingText}>Loading thread…</Text>
      </View>
    );
  }

  if (loadError && !meta) {
    return (
      <View style={styles.loadingPane}>
        <Text style={styles.errorText}>{loadError}</Text>
        <Pressable
          onPress={() => id && void load(id)}
          style={[styles.cta, { marginTop: space.s3 }]}
        >
          <Text style={styles.ctaLabel}>Retry</Text>
        </Pressable>
      </View>
    );
  }

  if (!meta) {
    return (
      <View style={styles.loadingPane}>
        <Text style={styles.muted}>Thread not found.</Text>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.fill}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={Platform.OS === "ios" ? 80 : 0}
    >
      <View style={styles.headerCard}>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle} numberOfLines={1}>
            {displayTitle(meta)}
          </Text>
          <Text style={styles.headerMeta}>
            {meta.message_count} message{meta.message_count === 1 ? "" : "s"}
            {" · "}updated {relativeTime(meta.updated_at)}
          </Text>
        </View>
        <View style={styles.headerActions}>
          <Pressable
            onPress={onSummarize}
            disabled={busy !== null}
            style={styles.actionPill}
            accessibilityLabel="Summarize thread"
          >
            <Text style={styles.actionLabel}>
              {busy === "summarize" ? "…" : "Summarize"}
            </Text>
          </Pressable>
          <Pressable
            onPress={openRename}
            disabled={busy !== null}
            style={styles.actionPill}
          >
            <Text style={styles.actionLabel}>Rename</Text>
          </Pressable>
          <Pressable
            onPress={onDelete}
            disabled={busy !== null}
            style={[styles.actionPill, styles.actionDanger]}
          >
            <Text style={[styles.actionLabel, styles.actionLabelDanger]}>
              Delete
            </Text>
          </Pressable>
        </View>
      </View>

      {/* v50 — summary card. Sits below the header, above the
          message log. Hidden when no summary has been generated. */}
      {meta.summary ? (
        <View style={styles.summaryCard}>
          <Text style={styles.summaryLabel}>
            SUMMARY
            {meta.summary_ts_ms
              ? ` · ${relativeTime(meta.summary_ts_ms)}`
              : ""}
          </Text>
          <Text style={styles.summaryText}>{meta.summary}</Text>
        </View>
      ) : null}

      {loadError && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{loadError}</Text>
        </View>
      )}

      <ScrollView
        ref={scrollRef}
        style={styles.log}
        contentContainerStyle={styles.logContent}
        onContentSizeChange={() => scrollToBottom()}
      >
        {messages.length === 0 ? (
          <Text style={styles.muted}>
            No messages yet — say something below to start.
          </Text>
        ) : (
          messages.map((m, idx) => (
            <Bubble key={`${m.ts_ms}-${idx}`} message={m} />
          ))
        )}
      </ScrollView>

      <View style={styles.composer}>
        <TextInput
          value={draft}
          onChangeText={setDraft}
          placeholder="Type a message…"
          placeholderTextColor={colors.textTertiary}
          multiline
          editable={busy !== "send"}
          style={styles.input}
        />
        <Pressable
          onPress={onSend}
          disabled={busy !== null || draft.trim().length === 0}
          style={[
            styles.sendBtn,
            (busy !== null || draft.trim().length === 0) && styles.sendBtnDisabled,
          ]}
        >
          <Text style={styles.sendLabel}>
            {busy === "send" ? "…" : "Send"}
          </Text>
        </Pressable>
      </View>

      {/* Rename modal */}
      <Modal
        visible={renameOpen}
        animationType="fade"
        transparent
        onRequestClose={() => setRenameOpen(false)}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.h2}>Rename thread</Text>
            <TextInput
              value={renameDraft}
              onChangeText={setRenameDraft}
              placeholder="Thread title"
              placeholderTextColor={colors.textTertiary}
              autoFocus
              style={styles.input}
            />
            <View style={styles.modalActions}>
              <Pressable
                onPress={() => setRenameOpen(false)}
                disabled={busy === "rename"}
                style={[styles.modalBtn, styles.modalBtnSecondary]}
              >
                <Text style={styles.modalBtnSecondaryLabel}>Cancel</Text>
              </Pressable>
              <Pressable
                onPress={commitRename}
                disabled={busy === "rename"}
                style={styles.modalBtn}
              >
                <Text style={styles.modalBtnLabel}>
                  {busy === "rename" ? "Saving…" : "Save"}
                </Text>
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>
    </KeyboardAvoidingView>
  );
}

// ------------ Sub-components ------------
function Bubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";
  const dmeta: Record<string, DirectiveMeta> = message.directive_metadata || {};
  const otherDirectives = isAssistant
    ? Object.keys(dmeta).filter((k) => k !== "cite")
    : [];
  const showBadges = isAssistant && (!!message.grounding_status || otherDirectives.length > 0);
  return (
    <View
      style={[
        styles.bubbleWrap,
        isUser ? styles.bubbleWrapUser : styles.bubbleWrapAssistant,
      ]}
    >
      <View
        style={[
          styles.bubble,
          isUser ? styles.bubbleUser : styles.bubbleAssistant,
        ]}
      >
        <Text style={styles.bubbleText}>{message.content}</Text>
      </View>
      {isAssistant && message.model && (
        <Text style={styles.bubbleModel}>{message.model}</Text>
      )}
      {/* A19/A30 — per-turn directive badges (cite grounding + others) */}
      {showBadges ? (
        <View style={styles.badgeRow}>
          {message.grounding_status ? (
            <Text
              style={[
                styles.badge,
                message.grounding_status === "grounded" ? styles.badgeOk : styles.badgeBad,
              ]}
            >
              {message.grounding_status === "grounded"
                ? "Grounding: OK"
                : "Grounding: Incomplete"}
            </Text>
          ) : null}
          {otherDirectives.map((name) => {
            const status = dmeta[name]?.status;
            const label = DIRECTIVE_LABEL[name] ?? name;
            return (
              <Text key={name} style={[styles.badge, styles.badgeDirective]}>
                {status ? `${label}: ${String(status)}` : label}
              </Text>
            );
          })}
        </View>
      ) : null}
    </View>
  );
}

// ------------ Helpers ------------
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
  fill: { flex: 1, backgroundColor: colors.bgDeep },
  loadingPane: {
    flex: 1, backgroundColor: colors.bgDeep,
    alignItems: "center", justifyContent: "center", padding: space.s5,
  },
  loadingText: { color: colors.textSecondary, marginTop: space.s3, fontSize: 12 },

  headerCard: {
    flexDirection: "row", alignItems: "center", gap: space.s3,
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderBottomWidth: 1,
    paddingHorizontal: space.s5, paddingVertical: space.s3,
  },
  headerTitle: { color: colors.textPrimary, fontSize: 16, fontWeight: "700" },
  headerMeta: { color: colors.textTertiary, fontSize: 11, marginTop: 2 },
  headerActions: { flexDirection: "row", gap: space.s2 },
  actionPill: {
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: radius.pill,
    backgroundColor: colors.bgDeep, borderColor: colors.border, borderWidth: 1,
  },
  actionLabel: { color: colors.textPrimary, fontSize: 11, fontWeight: "600" },
  actionDanger: { borderColor: "#ff8a8a" },
  actionLabelDanger: { color: "#ff8a8a" },

  summaryCard: {
    marginHorizontal: space.s4, marginTop: space.s3,
    padding: space.s3,
    backgroundColor: colors.bgDeep,
    borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.md,
  },
  summaryLabel: {
    color: colors.textTertiary, fontSize: 10, fontWeight: "700",
    letterSpacing: 0.5, marginBottom: 4,
  },
  summaryText: { color: colors.textPrimary, fontSize: 13, lineHeight: 18 },

  log: { flex: 1 },
  logContent: { padding: space.s4, paddingBottom: space.s5 },

  bubbleWrap: { marginVertical: 4, maxWidth: "100%" },
  bubbleWrapUser: { alignItems: "flex-end" },
  bubbleWrapAssistant: { alignItems: "flex-start" },
  bubble: {
    maxWidth: "85%",
    paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: radius.md, borderWidth: 1,
  },
  bubbleUser: {
    backgroundColor: colors.bgElevated,
    borderColor: colors.border,
  },
  bubbleAssistant: {
    backgroundColor: colors.bgDeep,
    borderColor: colors.border,
  },
  bubbleText: { color: colors.textPrimary, fontSize: 14 },
  bubbleModel: {
    color: colors.textTertiary, fontSize: 10, fontFamily: "Menlo",
    marginTop: 2,
  },
  // A19/A30 — directive badge row under the assistant bubble.
  badgeRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 4 },
  badge: {
    fontSize: 10, fontFamily: "Menlo",
    paddingHorizontal: 6, paddingVertical: 1,
    borderRadius: 3, borderWidth: 1, overflow: "hidden",
  },
  badgeOk: { color: "#2ECC71", borderColor: "#2ECC71" },
  badgeBad: { color: "#E74C3C", borderColor: "#E74C3C" },
  badgeDirective: { color: colors.accent, borderColor: colors.accent },

  composer: {
    flexDirection: "row", alignItems: "flex-end", gap: space.s3,
    paddingHorizontal: space.s4, paddingVertical: space.s3,
    backgroundColor: colors.bgSurface,
    borderTopColor: colors.border, borderTopWidth: 1,
  },
  input: {
    flex: 1,
    backgroundColor: colors.bgDeep, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.md, paddingHorizontal: 10, paddingVertical: 8,
    color: colors.textPrimary, fontSize: 14,
    minHeight: 40, maxHeight: 140,
  },
  sendBtn: {
    backgroundColor: colors.accent, paddingHorizontal: 16, paddingVertical: 10,
    borderRadius: radius.pill, alignItems: "center", justifyContent: "center",
  },
  sendBtnDisabled: { opacity: 0.4 },
  sendLabel: { color: "#04121b", fontWeight: "700", fontSize: 13 },

  modalBackdrop: {
    flex: 1, backgroundColor: "rgba(0,0,0,0.6)",
    alignItems: "center", justifyContent: "center", padding: space.s5,
  },
  modalCard: {
    width: "100%", maxWidth: 420,
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.lg, padding: space.s5, gap: space.s3,
  },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  modalActions: {
    flexDirection: "row", justifyContent: "flex-end", gap: space.s2,
    marginTop: space.s2,
  },
  modalBtn: {
    backgroundColor: colors.accent, paddingHorizontal: 16, paddingVertical: 8,
    borderRadius: radius.pill,
  },
  modalBtnLabel: { color: "#04121b", fontWeight: "700", fontSize: 12 },
  modalBtnSecondary: {
    backgroundColor: colors.bgDeep, borderColor: colors.border, borderWidth: 1,
  },
  modalBtnSecondaryLabel: { color: colors.textPrimary, fontWeight: "600", fontSize: 12 },

  cta: {
    backgroundColor: colors.accent, paddingVertical: 8, paddingHorizontal: 14,
    borderRadius: radius.pill, alignItems: "center",
  },
  ctaLabel: { color: "#04121b", fontWeight: "700", fontSize: 12 },

  muted: {
    color: colors.textTertiary, fontSize: 11, textAlign: "center",
    paddingVertical: space.s4,
  },
  errorBox: {
    margin: space.s3, padding: space.s3,
    backgroundColor: "#3a1414", borderRadius: radius.md,
  },
  errorText: { color: "#ff8a8a", fontSize: 12 },
});
