// ClarityOS Mobile — Operator session runtime (v62 / Unit 45).
//
// Phone mirror of web/src/routes/Session.tsx. Same 5-panel layout
// reflowed for a tall single-column scrolling view. Wraps the
// /operator/session/{start,step} surface (built in v60–v61).
//
// Named ``operator_session`` (not ``session``) to avoid colliding
// with the legacy ``session/[id]`` parametric route already in the
// app router — that one is a different concept (chat-engine console).
//
// v66 / Unit 70 — auth-required surface. Unauthed visits render an
// inline AuthGate CTA instead of falling through to "op_anon" (which
// is rejected by the auth-gated /operator/session/* backend since
// Unit 68). The legacy ``operator_id`` KV row is removed; the operator
// identity is implicit in the authed session and surfaced as an
// "Authed as ..." badge.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  ApiError,
  getUser,
  startSession,
  stepSession,
  type SessionIntentType,
  type SessionState,
  type SessionStepResult,
} from "../lib/api";
import { KEYS, storage } from "../lib/storage";
import { colors, radius, space } from "../lib/theme";
import AuthGate from "../components/AuthGate";

const INTENT_OPTIONS: SessionIntentType[] = [
  "query",
  "action",
  "plan",
  "diagnostic",
];

export default function OperatorSessionScreen() {
  return (
    <AuthGate>
      <OperatorSessionScreenInner />
    </AuthGate>
  );
}

function OperatorSessionScreenInner() {
  const authedUser = getUser() || "";
  const [state, setState] = useState<SessionState | null>(null);
  const [lastStep, setLastStep] = useState<SessionStepResult | null>(null);
  const [text, setText] = useState("");
  const [intent, setIntent] = useState<SessionIntentType>("query");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const operatorIdRef = useRef<string>(authedUser);

  const bootstrap = useCallback(async () => {
    setLoading(true);
    setError(null);
    const opId = authedUser;
    operatorIdRef.current = opId;
    try {
      const storedId = await storage.get(KEYS.operatorSessionResumeId);
      const r = storedId
        ? await startSession(opId, { resume: true, sessionId: storedId })
        : await startSession(opId);
      setState(r.session_state);
      await storage.set(
        KEYS.operatorSessionResumeId, r.session_state.session_id,
      );
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void bootstrap(); }, [bootstrap]);

  const handleSend = useCallback(async () => {
    if (!state) return;
    if (!text.trim()) return;
    setSending(true);
    setError(null);
    try {
      const r = await stepSession(state, text, intent);
      setState(r.session_state);
      setLastStep(r.step_result);
      setText("");
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setSending(false);
    }
  }, [state, text, intent]);

  const handleNewSession = useCallback(async () => {
    await storage.remove(KEYS.operatorSessionResumeId);
    setState(null);
    setLastStep(null);
    setText("");
    setError(null);
    setLoading(true);
    try {
      const r = await startSession(operatorIdRef.current);
      setState(r.session_state);
      await storage.set(
        KEYS.operatorSessionResumeId, r.session_state.session_id,
      );
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, []);
  // bootstrap uses authedUser captured at mount; eslint exhaustive-deps
  // is acceptable as the gate ensures it never changes during render.

  const ui = lastStep?.runtime?.ui_response;
  const modelText = lastStep?.model?.response?.text;
  const severityTone = ui ? severityToColor(ui.severity) : colors.textSecondary;

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: colors.bgDeep }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
        <Text style={styles.h1}>Operator session</Text>
        <Text style={styles.subtitle}>
          Runtime — server holds vault + history; this screen renders
          the response. Reload resumes the most recent session.
        </Text>
        <Text style={styles.authedBadge}>
          Authed as <Text style={styles.authedBadgeName}>{authedUser}</Text>
        </Text>

        {/* STATE */}
        <View style={styles.section}>
          <View style={styles.rowBetween}>
            <Text style={styles.h2}>STATE</Text>
            <Pressable
              onPress={() => void handleNewSession()}
              disabled={loading || sending}
              style={[styles.btnSecondary, (loading || sending) && styles.disabled]}
            >
              <Text style={styles.btnSecondaryLabel}>NEW SESSION</Text>
            </Pressable>
          </View>
          {loading && !state ? (
            <View style={{ paddingVertical: space.s3 }}>
              <ActivityIndicator color={colors.accent} />
            </View>
          ) : state ? (
            <View style={{ marginTop: space.s2 }}>
              <KV k="session_id" v={state.session_id} mono />
              <KV k="history" v={`${state.history.length} step(s)`} />
            </View>
          ) : null}
          {error ? (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}
        </View>

        {/* COMPOSE */}
        <View style={styles.section}>
          <Text style={styles.h2}>COMPOSE</Text>
          <TextInput
            value={text}
            onChangeText={setText}
            placeholder="e.g. what should the operator do next?"
            placeholderTextColor={colors.textSecondary}
            multiline
            editable={!!state && !sending}
            style={styles.textarea}
          />
          <View style={styles.intentRow}>
            {INTENT_OPTIONS.map((opt) => {
              const active = opt === intent;
              return (
                <Pressable
                  key={opt}
                  onPress={() => setIntent(opt)}
                  disabled={!state || sending}
                  style={[
                    styles.intentChip,
                    active && styles.intentChipActive,
                  ]}
                >
                  <Text style={[
                    styles.intentChipLabel,
                    active && styles.intentChipLabelActive,
                  ]}>{opt}</Text>
                </Pressable>
              );
            })}
          </View>
          <Pressable
            onPress={() => void handleSend()}
            disabled={!state || sending || !text.trim()}
            style={[
              styles.cta,
              (!state || sending || !text.trim()) && styles.disabled,
            ]}
          >
            <Text style={styles.ctaLabel}>{sending ? "SENDING…" : "SEND"}</Text>
          </Pressable>
        </View>

        {/* RUNTIME RESPONSE */}
        <View style={styles.section}>
          <Text style={styles.h2}>RUNTIME RESPONSE</Text>
          {!lastStep ? (
            <Text style={styles.empty}>No step taken yet.</Text>
          ) : ui ? (
            <View style={[styles.responseCard, { borderLeftColor: severityTone }]}>
              <Text style={[styles.responseSeverity, { color: severityTone }]}>
                {ui.severity.toUpperCase()}
              </Text>
              <Text style={styles.responseHeadline}>{ui.headline}</Text>
              <Text style={styles.responseBody}>{ui.body}</Text>
              {ui.tags.length > 0 ? (
                <View style={styles.tagRow}>
                  {ui.tags.map((tag) => (
                    <View key={tag} style={styles.tag}>
                      <Text style={styles.tagLabel}>{tag}</Text>
                    </View>
                  ))}
                </View>
              ) : null}
            </View>
          ) : null}
        </View>

        {/* MODEL RESPONSE */}
        <View style={styles.section}>
          <Text style={styles.h2}>MODEL RESPONSE</Text>
          {!lastStep ? (
            <Text style={styles.empty}>No step taken yet.</Text>
          ) : (
            <View>
              <KV k="model" v={lastStep.model.request.model_id} mono />
              <KV k="provider" v={lastStep.model.metadata.provider} />
              <KV k="mock" v={String(lastStep.model.metadata.mock)} />
              <Text style={styles.modelText}>{modelText || "(empty)"}</Text>
            </View>
          )}
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function KV({ k, v, mono = false }: { k: string; v: string; mono?: boolean }) {
  return (
    <View style={styles.kvRow}>
      <Text style={styles.kvK}>{k}</Text>
      <Text
        style={[styles.kvV, mono && styles.kvVMono]}
        numberOfLines={1}
        ellipsizeMode="middle"
      >
        {v}
      </Text>
    </View>
  );
}

function severityToColor(severity: string): string {
  if (severity === "critical") return "#ef4444";
  if (severity === "warning")  return "#f59e0b";
  return "#10b981";
}

function formatError(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.body === "object" && e.body && "detail" in e.body) {
      const detail = (e.body as Record<string, unknown>).detail;
      if (typeof detail === "string") return detail;
    }
    return `${e.code}: ${e.message}`;
  }
  if (e instanceof Error) return e.message;
  return String(e);
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5, paddingBottom: space.s5 * 2 },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s2 },
  authedBadge: {
    color: colors.textSecondary,
    fontSize: 11,
    marginBottom: space.s4,
  },
  authedBadgeName: {
    color: colors.textPrimary,
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
  },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  section: {
    backgroundColor: colors.bgSurface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: space.s4,
    marginBottom: space.s4,
  },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  empty: { color: colors.textSecondary, fontStyle: "italic", marginTop: space.s2 },
  kvRow: { flexDirection: "row", paddingVertical: 4 },
  kvK: { color: colors.textSecondary, width: 90, fontSize: 12 },
  kvV: { color: colors.textPrimary, flex: 1, fontSize: 12 },
  kvVMono: { fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace" },
  textarea: {
    color: colors.textPrimary,
    backgroundColor: colors.bgDeep,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: space.s3,
    minHeight: 80,
    marginTop: space.s2,
    textAlignVertical: "top",
  },
  intentRow: { flexDirection: "row", flexWrap: "wrap", gap: space.s2, marginTop: space.s3 },
  intentChip: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radius.pill,
    borderColor: colors.border,
    borderWidth: 1,
    backgroundColor: colors.bgDeep,
  },
  intentChipActive: { borderColor: colors.accent, backgroundColor: colors.bgSurface },
  intentChipLabel: { color: colors.textSecondary, fontSize: 12 },
  intentChipLabelActive: { color: colors.textPrimary, fontWeight: "600" },
  cta: {
    backgroundColor: colors.accent,
    paddingVertical: 10,
    borderRadius: radius.pill,
    alignItems: "center",
    marginTop: space.s3,
  },
  ctaLabel: { color: "#04121b", fontWeight: "700" },
  btnSecondary: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: radius.pill,
    borderColor: colors.border,
    borderWidth: 1,
  },
  btnSecondaryLabel: { color: colors.textSecondary, fontSize: 11, fontWeight: "600" },
  disabled: { opacity: 0.4 },
  responseCard: {
    borderLeftWidth: 3,
    paddingLeft: space.s3,
    paddingVertical: space.s2,
    marginTop: space.s2,
  },
  responseSeverity: { fontSize: 11, fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace", marginBottom: 4 },
  responseHeadline: { color: colors.textPrimary, fontWeight: "600", marginBottom: 4 },
  responseBody: { color: colors.textSecondary, fontSize: 12 },
  tagRow: { flexDirection: "row", flexWrap: "wrap", gap: 4, marginTop: space.s2 },
  tag: { backgroundColor: "rgba(255,255,255,0.06)", paddingHorizontal: 6, paddingVertical: 2, borderRadius: 2 },
  tagLabel: { color: colors.textSecondary, fontSize: 10, fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace" },
  modelText: {
    color: colors.textPrimary,
    fontSize: 12,
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
    backgroundColor: colors.bgDeep,
    padding: space.s3,
    borderRadius: radius.md,
    marginTop: space.s3,
  },
  errorBox: {
    padding: space.s3,
    backgroundColor: "#3a1414",
    borderRadius: radius.md,
    marginTop: space.s3,
  },
  errorText: { color: "#ff8a8a", fontSize: 12 },
});
