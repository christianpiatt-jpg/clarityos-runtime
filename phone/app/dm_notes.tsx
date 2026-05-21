// ClarityOS Mobile — Founder DM inbox (v33).

import { useCallback, useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import {
  founderDMAdd, founderDMList, founderDMNote,
  type V33DM, type V33DMChannel, type V33DMNote,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";

const CHANNELS: ReadonlyArray<V33DMChannel> = ["manual", "linkedin", "facebook", "email"];

export default function DMNotesScreen() {
  const [dms, setDms] = useState<V33DM[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [newChannel, setNewChannel] = useState<V33DMChannel>("manual");
  const [newSubject, setNewSubject] = useState("");
  const [newSnippet, setNewSnippet] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [notesByDm, setNotesByDm] = useState<Record<string, V33DMNote[]>>({});
  const [noteBody, setNoteBody] = useState("");

  const refresh = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const r = await founderDMList({ limit: 200 });
      setDms(r.dms);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const addDm = useCallback(async () => {
    setError(null);
    try {
      await founderDMAdd({
        channel: newChannel,
        subject: newSubject.trim() || undefined,
        snippet: newSnippet.trim() || undefined,
      });
      setNewSubject(""); setNewSnippet("");
      await refresh();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
  }, [newChannel, newSubject, newSnippet, refresh]);

  const addNote = useCallback(async () => {
    if (!selected || !noteBody.trim()) return;
    try {
      const r = await founderDMNote(selected, noteBody.trim());
      setNotesByDm((m) => ({ ...m, [selected]: r.notes }));
      setNoteBody("");
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
  }, [selected, noteBody]);

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>DM inbox</Text>

      <View style={styles.card}>
        <Text style={styles.h2}>Add DM</Text>
        <View style={styles.chipRow}>
          {CHANNELS.map((c) => (
            <Pressable key={c} onPress={() => setNewChannel(c)}
              style={[styles.chip, newChannel === c && styles.chipActive]}>
              <Text style={[styles.chipText, newChannel === c && styles.chipTextActive]}>{c}</Text>
            </Pressable>
          ))}
        </View>
        <TextInput
          value={newSubject}
          onChangeText={setNewSubject}
          placeholder="subject"
          placeholderTextColor={colors.textTertiary}
          style={styles.input}
        />
        <TextInput
          value={newSnippet}
          onChangeText={setNewSnippet}
          placeholder="snippet (≤ 500 chars)"
          placeholderTextColor={colors.textTertiary}
          multiline
          style={[styles.input, { minHeight: 60 }]}
          maxLength={500}
        />
        <Pressable onPress={() => void addDm()} style={styles.cta} disabled={busy}>
          <Text style={styles.ctaLabel}>Add</Text>
        </Pressable>
      </View>

      {error && <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>}

      <View style={styles.card}>
        <View style={styles.headerRow}>
          <Text style={styles.h2}>{dms.length} DMs</Text>
          <Pressable onPress={() => void refresh()}>
            <Text style={styles.linkText}>Refresh</Text>
          </Pressable>
        </View>
        {dms.map((dm) => (
          <Pressable
            key={dm.id}
            onPress={() => setSelected(selected === dm.id ? null : dm.id)}
            style={[styles.dmRow, selected === dm.id && styles.dmRowSelected]}
          >
            <Text style={styles.dmTitle}>
              <Text style={{ fontFamily: "Menlo", fontSize: 11 }}>{dm.channel}</Text>
              {" · "}
              {dm.subject || "(no subject)"}
            </Text>
            {dm.snippet ? <Text style={styles.dmSnippet}>{dm.snippet}</Text> : null}
            {selected === dm.id && (
              <View style={{ marginTop: space.s3 }}>
                {(notesByDm[dm.id] || []).map((n) => (
                  <Text key={n.id} style={styles.note}>• {n.body}</Text>
                ))}
                <TextInput
                  value={noteBody}
                  onChangeText={setNoteBody}
                  placeholder="Append note"
                  placeholderTextColor={colors.textTertiary}
                  multiline
                  style={[styles.input, { marginTop: space.s2, minHeight: 50 }]}
                  maxLength={4000}
                />
                <Pressable
                  onPress={() => void addNote()}
                  disabled={!noteBody.trim()}
                  style={[styles.cta, !noteBody.trim() && styles.disabled, { marginTop: 4 }]}
                >
                  <Text style={styles.ctaLabel}>Add note</Text>
                </Pressable>
              </View>
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
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700", marginBottom: space.s4 },
  h2: { color: colors.textPrimary, fontSize: 16, fontWeight: "600" },
  card: {
    backgroundColor: colors.bgSurface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: space.s5,
    marginBottom: space.s4,
  },
  input: {
    backgroundColor: colors.bgDeep,
    borderColor: colors.borderStrong,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 10,
    color: colors.textPrimary,
    fontSize: 13,
    marginBottom: space.s3,
    textAlignVertical: "top",
  },
  cta: {
    backgroundColor: colors.accent,
    paddingVertical: 10,
    borderRadius: radius.pill,
    alignItems: "center",
  },
  ctaLabel: { color: "#04121b", fontWeight: "700" },
  disabled: { opacity: 0.4 },
  chipRow: { flexDirection: "row", gap: space.s2, marginBottom: space.s3, flexWrap: "wrap" },
  chip: {
    paddingHorizontal: 10, paddingVertical: 6,
    backgroundColor: colors.bgElevated, borderRadius: radius.pill,
    borderWidth: 1, borderColor: colors.border,
  },
  chipActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  chipText: { color: colors.textPrimary, fontSize: 12 },
  chipTextActive: { color: "#04121b", fontWeight: "700" },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: space.s3 },
  dmRow: {
    paddingVertical: 8, paddingHorizontal: 6,
    borderRadius: radius.md, marginBottom: 4,
    backgroundColor: colors.bgDeep,
  },
  dmRowSelected: { backgroundColor: colors.bgElevated },
  dmTitle: { color: colors.textPrimary, fontSize: 13, fontWeight: "600" },
  dmSnippet: { color: colors.textSecondary, fontSize: 12, marginTop: 2 },
  note: { color: colors.textSecondary, fontSize: 12, marginBottom: 2 },
  linkText: { color: colors.accent, fontWeight: "600" },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
