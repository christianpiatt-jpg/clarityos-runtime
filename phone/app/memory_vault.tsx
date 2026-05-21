// ClarityOS Mobile — Memory Vault notes screen (v46).
// List/add/edit/delete notes against /me/vault/notes. Status header
// shows the global vault config + per-user counts. Tap a note to load
// it into the editor; trash icon deletes it after confirm.

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, Pressable, ScrollView, StyleSheet, Text,
  TextInput, View,
} from "react-native";
import { router } from "expo-router";
import {
  meVaultNotes, meVaultNotesDelete, meVaultNotesPut, meVaultStatus,
  type V46VaultNote, type V46VaultStatusResponse,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";

export default function MemoryVaultScreen() {
  const [status, setStatus] = useState<V46VaultStatusResponse | null>(null);
  const [notes, setNotes] = useState<V46VaultNote[]>([]);
  const [draftKey, setDraftKey] = useState<string>("");
  const [draftText, setDraftText] = useState<string>("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy("load"); setError(null);
    try {
      const [st, nn] = await Promise.all([meVaultStatus(), meVaultNotes()]);
      setStatus(st);
      setNotes(nn.notes);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const save = useCallback(async () => {
    const k = draftKey.trim();
    if (!k) { setError("Note key is required"); return; }
    setBusy("save"); setError(null);
    try {
      await meVaultNotesPut(k, draftText);
      setDraftKey("");
      setDraftText("");
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, [draftKey, draftText, load]);

  const remove = useCallback(async (key: string) => {
    setBusy("del"); setError(null);
    try {
      await meVaultNotesDelete(key);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, [load]);

  const editNote = useCallback((n: V46VaultNote) => {
    setDraftKey(n.key);
    setDraftText(n.text);
  }, []);

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>Memory Vault</Text>
      {status && (
        <Text style={styles.subtitle}>
          v46 · {status.global.backend} · {status.global.encrypted ? "encrypted" : "plain"}
          {" · "}{status.user.vault_keys} keys
        </Text>
      )}

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
      )}

      {busy === "load" && !status && (
        <ActivityIndicator color={colors.accent} style={{ marginTop: space.s4 }} />
      )}

      {status && (
        <View style={styles.card}>
          <Text style={styles.h2}>Counts</Text>
          <Row k="Notes" v={String(status.user.notes_count)} />
          <Row k="Embeddings" v={String(status.user.embeddings_count)} />
          <Row k="ELINS history" v={String(status.user.elins_count)} />
          <Row k="#G history" v={String(status.user.g_runs_count)} />
          <Row k="Operator state" v={String(status.user.operator_state_count)} />
        </View>
      )}

      <View style={styles.card}>
        <Text style={styles.h2}>Compose</Text>
        <TextInput
          value={draftKey}
          onChangeText={setDraftKey}
          placeholder="key (e.g. team_brief)"
          placeholderTextColor={colors.textTertiary}
          autoCapitalize="none"
          autoCorrect={false}
          style={styles.input}
        />
        <TextInput
          value={draftText}
          onChangeText={setDraftText}
          placeholder="note text"
          placeholderTextColor={colors.textTertiary}
          multiline
          style={[styles.input, styles.multiline]}
        />
        <Pressable onPress={save} disabled={busy !== null} style={styles.cta}>
          <Text style={styles.ctaLabel}>{busy === "save" ? "Saving…" : "Save note"}</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.h2}>Notes ({notes.length})</Text>
          <Pressable onPress={() => router.push("/memory_vault_embeddings" as any)}>
            <Text style={styles.link}>Embeddings →</Text>
          </Pressable>
        </View>
        {notes.length === 0 && (
          <Text style={styles.muted}>No notes yet.</Text>
        )}
        {notes.map((n) => (
          <View key={n.key} style={styles.noteRow}>
            <Pressable style={{ flex: 1 }} onPress={() => editNote(n)}>
              <Text style={styles.noteKey}>{n.key}</Text>
              <Text style={styles.noteText} numberOfLines={3}>{n.text}</Text>
            </Pressable>
            <Pressable onPress={() => void remove(n.key)} disabled={busy !== null}>
              <Text style={styles.delete}>Delete</Text>
            </Pressable>
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <View style={styles.kvRow}>
      <Text style={styles.kvKey}>{k}</Text>
      <Text style={styles.kvVal}>{v}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s4 },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600", marginBottom: space.s3 },
  card: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.lg, padding: space.s4, marginBottom: space.s3,
  },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: space.s3 },
  link: { color: colors.accent, fontSize: 12, fontWeight: "600" },
  muted: { color: colors.textTertiary, fontSize: 11, marginTop: space.s2 },
  input: {
    backgroundColor: colors.bgDeep, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.md, paddingHorizontal: 10, paddingVertical: 8,
    color: colors.textPrimary, fontSize: 13, marginBottom: space.s3,
  },
  multiline: { minHeight: 80, textAlignVertical: "top" },
  cta: {
    backgroundColor: colors.accent, paddingVertical: 10, borderRadius: radius.pill,
    alignItems: "center",
  },
  ctaLabel: { color: "#04121b", fontWeight: "700", fontSize: 13 },
  kvRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 2 },
  kvKey: { color: colors.textSecondary, fontSize: 12 },
  kvVal: { color: colors.textPrimary, fontSize: 12, fontFamily: "Menlo" },
  noteRow: {
    flexDirection: "row", paddingVertical: 6,
    borderBottomColor: colors.border, borderBottomWidth: 1, gap: space.s3,
    alignItems: "flex-start",
  },
  noteKey: { color: colors.accent, fontSize: 12, fontFamily: "Menlo" },
  noteText: { color: colors.textPrimary, fontSize: 12, marginTop: 2 },
  delete: { color: "#ff8a8a", fontSize: 11 },
  errorBox: {
    padding: space.s3, backgroundColor: "#3a1414",
    borderRadius: radius.md, marginBottom: space.s3,
  },
  errorText: { color: "#ff8a8a" },
});
