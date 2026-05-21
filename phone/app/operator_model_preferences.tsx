// v64 / Unit 67 — Model preferences (phone).
//
// v66 / Unit 70 — wrapped in AuthGate so unauthed visits show an
// inline CTA. The "(not signed in)" placeholder is no longer
// reachable because the gate intercepts before render.

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  ApiError,
  getModelPreferences,
  getUser,
  setModelPreferences,
  type ModelPreferencesResponse,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";
import AuthGate from "../components/AuthGate";

const PROVIDERS: readonly string[] = [
  "anthropic", "openai", "gemini", "xai", "local",
] as const;

const DEFAULT_MODELS: Record<string, string> = {
  anthropic: "claude-3.7",
  openai:    "gpt-4.2",
  gemini:    "gemini-2.0",
  xai:       "groq-llama",
  local:     "llama3.1",
};

export default function OperatorModelPreferencesScreen() {
  return (
    <AuthGate>
      <OperatorModelPreferencesScreenInner />
    </AuthGate>
  );
}

function OperatorModelPreferencesScreenInner() {
  const operatorId = getUser() || "";
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState(DEFAULT_MODELS.anthropic);
  const [current, setCurrent] = useState<ModelPreferencesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await getModelPreferences();
      setCurrent(r);
      setProvider(r.provider);
      setModel(r.model);
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetch(); }, [fetch]);

  async function save() {
    if (!provider || !model.trim()) return;
    setSaving(true);
    setError(null);
    setSavedAt(null);
    try {
      const r = await setModelPreferences(provider, model.trim());
      setCurrent(r);
      setSavedAt(new Date().toLocaleTimeString());
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setSaving(false);
    }
  }

  function pickProvider(next: string) {
    setProvider(next);
    setModel(DEFAULT_MODELS[next] || "");
  }

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content}>
      <View style={styles.panel}>
        <Text style={styles.h1}>MODEL PREFERENCES</Text>
        <Text style={styles.muted}>
          Per-operator (provider, model) used by the runtime loop.
          Stored in the vault.
        </Text>
        <Text style={[styles.muted, { marginTop: 8 }]}>
          authed as <Text style={styles.mono}>{operatorId}</Text>
        </Text>
      </View>

      <View style={styles.panel}>
        <Text style={styles.h2}>CURRENT</Text>
        {loading ? (
          <ActivityIndicator color={colors.accent} />
        ) : current ? (
          <View>
            <Text style={styles.kvRow}>provider: <Text style={styles.bold}>{current.provider}</Text></Text>
            <Text style={styles.kvRow}>model: <Text style={[styles.bold, styles.mono]}>{current.model}</Text></Text>
            <Text style={styles.kvRow}>
              source: {current.source === "vault" ? "explicit (vault)" : "default (chain)"}
            </Text>
          </View>
        ) : (
          <Text style={styles.empty}>No preference loaded.</Text>
        )}
      </View>

      <View style={styles.panel}>
        <Text style={styles.h2}>UPDATE</Text>
        <Text style={[styles.muted, { marginTop: 4 }]}>Provider</Text>
        <View style={styles.providerRow}>
          {PROVIDERS.map((p) => (
            <Pressable
              key={p}
              onPress={() => pickProvider(p)}
              style={[
                styles.providerChip,
                provider === p && styles.providerChipActive,
              ]}
              disabled={saving}
            >
              <Text
                style={[
                  styles.providerChipText,
                  provider === p && styles.providerChipTextActive,
                ]}
              >
                {p}
              </Text>
            </Pressable>
          ))}
        </View>

        <Text style={[styles.muted, { marginTop: 12 }]}>Model</Text>
        <TextInput
          style={styles.input}
          value={model}
          onChangeText={setModel}
          autoCapitalize="none"
          editable={!saving}
        />

        <Pressable
          style={({ pressed }) => [
            styles.btnPrimary,
            (saving || !model.trim()) && styles.btnDisabled,
            pressed && styles.btnPressed,
          ]}
          onPress={save}
          disabled={saving || !model.trim()}
        >
          <Text style={styles.btnPrimaryText}>
            {saving ? "SAVING…" : "SAVE"}
          </Text>
        </Pressable>

        {savedAt ? (
          <Text style={[styles.muted, { marginTop: 8 }]}>
            saved at {savedAt}
          </Text>
        ) : null}

        {error ? (
          <View style={styles.banner}>
            <Text style={styles.bannerText}>{error}</Text>
          </View>
        ) : null}
      </View>
    </ScrollView>
  );
}

function formatError(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.body === "object" && e.body && "detail" in (e.body as Record<string, unknown>)) {
      const d = (e.body as Record<string, unknown>).detail;
      if (typeof d === "string") return d;
    }
    return `${e.code}: ${e.message}`;
  }
  if (e instanceof Error) return e.message;
  return String(e);
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bgDeep },
  content: { padding: space.s5 },
  panel: {
    backgroundColor: colors.bgSurface,
    borderRadius: radius.lg,
    padding: space.s4,
    marginBottom: space.s3,
  },
  h1: { color: colors.textPrimary, fontSize: 18, fontWeight: "700" },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600", marginBottom: space.s3 },
  muted: { color: colors.textSecondary, fontSize: 13 },
  mono: { fontFamily: "monospace" },
  bold: { color: colors.textPrimary, fontWeight: "600" },
  kvRow: { color: colors.textPrimary, fontSize: 13, marginBottom: 4 },
  empty: { color: colors.textSecondary, fontStyle: "italic" },
  providerRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 4,
  },
  providerChip: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.sm,
  },
  providerChipActive: {
    backgroundColor: colors.bgElevated,
    borderColor: colors.accent,
  },
  providerChipText: { color: colors.textSecondary, fontSize: 12 },
  providerChipTextActive: { color: colors.textPrimary, fontWeight: "600" },
  input: {
    backgroundColor: colors.bgDeep,
    color: colors.textPrimary,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.sm,
    padding: 8,
    marginTop: 4,
    fontFamily: "monospace",
  },
  btnPrimary: {
    marginTop: space.s3,
    paddingVertical: 10,
    paddingHorizontal: 16,
    backgroundColor: colors.accent,
    borderRadius: radius.sm,
    alignSelf: "flex-start",
  },
  btnPrimaryText: { color: colors.bgDeep, fontWeight: "700", fontSize: 13 },
  btnDisabled: { opacity: 0.4 },
  btnPressed: { opacity: 0.7 },
  banner: {
    marginTop: space.s3,
    padding: 8,
    backgroundColor: "rgba(239,68,68,0.12)",
    borderRadius: radius.sm,
  },
  bannerText: { color: "#ef4444", fontSize: 13 },
});
