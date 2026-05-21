import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { router, useFocusEffect, useLocalSearchParams, useNavigation } from "expo-router";
import * as Clipboard from "expo-clipboard";
import * as api from "../../lib/api";
import { storage, KEYS, getAIProvider } from "../../lib/storage";
import { getProviderById } from "../../lib/providers";
import type { ProviderId } from "../../lib/providers/types";
import { saveNote, saveSession } from "../../lib/vault";
import SegmentedToggle from "../../components/EngineToggle";
import ConsoleLine, { Line } from "../../components/ConsoleLine";
import TagSaveModal from "../../components/TagSaveModal";
import Toast from "../../components/Toast";
import { colors, radius, space } from "../../lib/theme";

type Engine = "markov" | "galileo" | "tizzy";
type Mode = "c" | "G";
type Thread = { id: string; title: string; created: number; log: Line[] };

type SaveFlow =
  | { kind: "paste"; text: string }
  | { kind: "session-end"; text: string; pendingAction: any };

export default function SessionScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const navigation = useNavigation();

  const [thread, setThread] = useState<Thread | null>(null);
  const [engine, setEngine] = useState<Engine>("markov");
  const [mode, setMode] = useState<Mode>("G");
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [providerId, setProviderId] = useState<ProviderId | null>(null);
  const [flow, setFlow] = useState<SaveFlow | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const scrollRef = useRef<ScrollView>(null);

  const allowLeaveRef = useRef(false);
  const hasContentRef = useRef(false);
  const sessionTextRef = useRef("");

  useEffect(() => {
    (async () => {
      const raw = await storage.get(KEYS.threads);
      const list: Thread[] = raw ? safeParse(raw) : [];
      const t = list.find((x) => x.id === id);
      if (t) setThread(t);
      const e = (await storage.get(KEYS.engine)) as Engine | null;
      const m = (await storage.get(KEYS.mode)) as Mode | null;
      if (e) setEngine(e);
      if (m) setMode(m);
    })();
  }, [id]);

  // Refresh provider whenever the session screen comes back into focus —
  // covers the "user opened Settings, picked a provider, came back" path.
  useFocusEffect(
    useCallback(() => {
      let cancel = false;
      getAIProvider().then((p) => { if (!cancel) setProviderId(p); });
      return () => { cancel = true; };
    }, [])
  );

  useEffect(() => {
    sessionTextRef.current = thread?.log.map((l) => l.text).join("\n") || "";
    hasContentRef.current = (thread?.log.length || 0) > 0;
  }, [thread]);

  // Back-button intercept: when leaving with content, prompt to save.
  // allowLeaveRef bypasses the prompt when we re-dispatch the pending
  // action after the user makes a choice.
  useEffect(() => {
    const sub = navigation.addListener("beforeRemove" as any, (e: any) => {
      if (allowLeaveRef.current) return;
      if (!hasContentRef.current) return;
      e.preventDefault();
      setFlow({
        kind: "session-end",
        text: sessionTextRef.current,
        pendingAction: e.data.action,
      });
    });
    return sub;
  }, [navigation]);

  async function persist(updated: Thread) {
    setThread(updated);
    const raw = await storage.get(KEYS.threads);
    const list: Thread[] = raw ? safeParse(raw) : [];
    const next = list.map((x) => (x.id === updated.id ? updated : x));
    await storage.set(KEYS.threads, JSON.stringify(next));
  }

  async function setEnginePersist(e: Engine) {
    setEngine(e);
    await storage.set(KEYS.engine, e);
  }
  async function setModePersist(m: Mode) {
    setMode(m);
    await storage.set(KEYS.mode, m);
  }

  async function send() {
    if (!thread || !input.trim() || busy) return;
    const text = input.trim();
    setInput("");
    setBusy(true);

    const userLine: Line = { kind: "user", text: `[#${mode} ${engine}] ${text}`, ts: Date.now() };
    let working: Thread = {
      ...thread,
      title: thread.log.length === 0 ? text.slice(0, 40) : thread.title,
      log: [...thread.log, userLine],
    };
    await persist(working);

    try {
      const resp = mode === "c" ? api.localCompute(engine, text) : await api[engine](text);
      const summary = summarize(engine, (resp as any).data);
      const engineLine: Line = { kind: "engine", text: summary, ts: Date.now() };
      working = { ...working, log: [...working.log, engineLine] };
    } catch (e: any) {
      const errLine: Line = { kind: "error", text: `error: ${e?.message || e}`, ts: Date.now() };
      working = { ...working, log: [...working.log, errLine] };
    }
    await persist(working);
    setBusy(false);
    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 50);
  }

  async function sendToProvider() {
    const text = input.trim();
    if (!text) {
      setToast("Type a message first");
      return;
    }
    const id = await getAIProvider();
    if (!id) {
      Alert.alert(
        "No AI provider selected",
        "Pick one in Settings first.",
        [
          { text: "Cancel", style: "cancel" },
          { text: "Open Settings", onPress: () => router.push("/settings") },
        ]
      );
      return;
    }
    const provider = getProviderById(id);
    if (!provider) {
      setToast("Provider not found");
      return;
    }
    const result = await provider.sendMessage(text);
    setToast(result.message || (result.success ? "Sent to " + provider.name : "Could not open " + provider.name));
  }

  async function pasteFromClipboard() {
    const t = await Clipboard.getStringAsync();
    if (!t || !t.trim()) {
      setToast("Clipboard is empty");
      return;
    }
    setFlow({ kind: "paste", text: t });
  }

  function done() {
    // Always go through router.back(); if there's content, beforeRemove
    // will prevent default and surface the save modal.
    router.back();
  }

  async function handleModalSave({ text, tags }: { text: string; tags: string[] }) {
    if (!flow) return;
    const current = flow;
    setFlow(null);
    if (current.kind === "paste") {
      await saveNote({
        type: "note",
        content: text,
        tags,
        source: "ai",
        providerId: providerId ?? undefined,
      });
      setToast("Saved to your vault");
      return;
    }
    // session-end
    await saveSession({ type: "session", content: text, tags });
    allowLeaveRef.current = true;
    navigation.dispatch(current.pendingAction);
  }

  function handleModalCancel() {
    if (!flow) return;
    const current = flow;
    setFlow(null);
    if (current.kind === "session-end") {
      // Spec: cancelling the end-of-session prompt discards and leaves.
      allowLeaveRef.current = true;
      navigation.dispatch(current.pendingAction);
    }
    // Paste flow: just close the modal — stay on screen.
  }

  if (!thread) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bgDeep, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  const providerLabel = providerId ? getProviderById(providerId)?.name ?? "AI" : "AI";

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: colors.bgDeep }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View style={styles.toolbar}>
        <SegmentedToggle
          value={mode}
          options={[{ value: "c", label: "#c" }, { value: "G", label: "#G" }]}
          onChange={(v) => setModePersist(v as Mode)}
        />
        <SegmentedToggle
          value={engine}
          options={[
            { value: "markov", label: "markov" },
            { value: "galileo", label: "galileo" },
            { value: "tizzy", label: "tizzy" },
          ]}
          onChange={(v) => setEnginePersist(v as Engine)}
        />
      </View>

      <ScrollView
        ref={scrollRef}
        style={styles.log}
        contentContainerStyle={{ padding: space.s4 }}
        onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: false })}
      >
        {thread.log.length === 0 ? (
          <Text style={{ color: colors.textTertiary, fontFamily: "Menlo" }}>
            // thread is empty. send a prompt to begin.
          </Text>
        ) : (
          thread.log.map((l, i) => <ConsoleLine key={i} line={l} />)
        )}
      </ScrollView>

      <View style={styles.actionRow}>
        <Pressable onPress={pasteFromClipboard} style={styles.actionBtn}>
          <Text style={styles.actionLabel}>Paste</Text>
        </Pressable>
        <Pressable onPress={sendToProvider} style={styles.actionBtn}>
          <Text style={styles.actionLabel} numberOfLines={1}>
            Send to {providerLabel}
          </Text>
        </Pressable>
        <Pressable onPress={done} style={styles.actionBtn}>
          <Text style={styles.actionLabel}>Done</Text>
        </Pressable>
      </View>

      <View style={styles.inputRow}>
        <TextInput
          value={input}
          onChangeText={setInput}
          placeholder="Send a prompt"
          placeholderTextColor={colors.textTertiary}
          style={styles.input}
          multiline
        />
        <Pressable
          onPress={send}
          style={[styles.send, (busy || !input.trim()) && { opacity: 0.5 }]}
          disabled={busy || !input.trim()}
        >
          <Text style={styles.sendLabel}>{busy ? "…" : "Send"}</Text>
        </Pressable>
      </View>

      <TagSaveModal
        visible={!!flow}
        initialText={flow?.text ?? ""}
        onSave={handleModalSave}
        onCancel={handleModalCancel}
      />

      <Toast visible={!!toast} message={toast || ""} onHide={() => setToast(null)} />
    </KeyboardAvoidingView>
  );
}

function safeParse<T>(s: string): T {
  try { return JSON.parse(s); } catch { return [] as unknown as T; }
}

function summarize(engine: Engine, data: any) {
  if (!data) return "(no data)";
  if (engine === "markov") return `score=${(data.score || 0).toFixed(2)} tags=[${(data.tags || []).join(",")}] ${data.interpretation || ""}`;
  if (engine === "galileo") return `clarity=${data.clarity_level} ${data.summary || ""}`;
  if (engine === "tizzy") return data.result || JSON.stringify(data);
  return JSON.stringify(data);
}

const styles = StyleSheet.create({
  toolbar: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: space.s3,
    padding: space.s3,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.bgSurface,
  },
  log: { flex: 1, backgroundColor: colors.bgDeep },
  actionRow: {
    flexDirection: "row",
    gap: space.s2,
    paddingHorizontal: space.s3,
    paddingTop: space.s3,
    backgroundColor: colors.bgSurface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  actionBtn: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    backgroundColor: colors.bgDeep,
    alignItems: "center",
  },
  actionLabel: { color: colors.textPrimary, fontSize: 12 },
  inputRow: {
    flexDirection: "row",
    padding: space.s3,
    gap: space.s2,
    backgroundColor: colors.bgSurface,
  },
  input: {
    flex: 1,
    minHeight: 44,
    maxHeight: 120,
    backgroundColor: colors.bgDeep,
    borderColor: colors.borderStrong,
    borderWidth: 1,
    borderRadius: radius.sm,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: colors.textPrimary,
    fontFamily: "Menlo",
    fontSize: 14,
  },
  send: {
    backgroundColor: colors.accent,
    paddingHorizontal: 18,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  sendLabel: { color: "#04121b", fontWeight: "700", fontSize: 14 },
});
