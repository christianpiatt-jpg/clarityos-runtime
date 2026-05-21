import { useEffect, useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { colors, radius, space } from "../lib/theme";

// TODO: replace with a curated local Dewey subset once the taxonomy ships.
const SUGGESTED_TAGS = ["work", "personal", "insight", "question"];

type Props = {
  visible: boolean;
  initialText: string;
  onSave: (payload: { text: string; tags: string[] }) => void;
  onCancel: () => void;
};

export default function TagSaveModal({ visible, initialText, onSave, onCancel }: Props) {
  const [tagsText, setTagsText] = useState("");
  const [chosen, setChosen] = useState<string[]>([]);

  useEffect(() => {
    if (visible) {
      setTagsText("");
      setChosen([]);
    }
  }, [visible]);

  function toggleSuggestion(t: string) {
    setChosen((prev) => (prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]));
  }

  function handleSave() {
    const typed = tagsText.split(",").map((t) => t.trim()).filter(Boolean);
    const tags = Array.from(new Set([...chosen, ...typed]));
    onSave({ text: initialText, tags });
  }

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <Text style={styles.h3}>Save to your vault</Text>
          <Text style={styles.muted}>Local-only. Nothing is sent to the cloud.</Text>

          <Text style={styles.label}>Preview</Text>
          <ScrollView style={styles.preview} nestedScrollEnabled>
            <Text style={styles.previewText}>{initialText}</Text>
          </ScrollView>

          <Text style={styles.label}>Suggested tags</Text>
          <View style={styles.suggested}>
            {SUGGESTED_TAGS.map((t) => {
              const on = chosen.includes(t);
              return (
                <Pressable
                  key={t}
                  onPress={() => toggleSuggestion(t)}
                  style={[styles.chip, on && styles.chipOn]}
                >
                  <Text style={[styles.chipLabel, on && styles.chipLabelOn]}>{t}</Text>
                </Pressable>
              );
            })}
          </View>

          <Text style={styles.label}>Other tags (comma-separated)</Text>
          <TextInput
            value={tagsText}
            onChangeText={setTagsText}
            placeholder="e.g. mediation, draft"
            placeholderTextColor={colors.textTertiary}
            autoCapitalize="none"
            style={styles.input}
          />

          <View style={styles.actions}>
            <Pressable onPress={onCancel} style={[styles.btn, styles.btnGhost]}>
              <Text style={styles.btnGhostLabel}>Cancel</Text>
            </Pressable>
            <Pressable onPress={handleSave} style={[styles.btn, styles.btnPrimary]}>
              <Text style={styles.btnPrimaryLabel}>Save</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.6)",
    justifyContent: "center",
    padding: space.s4,
  },
  card: {
    backgroundColor: colors.bgSurface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: space.s5,
    maxHeight: "85%",
  },
  h3: { color: colors.textPrimary, fontSize: 18, fontWeight: "600", marginBottom: 4 },
  muted: { color: colors.textSecondary, fontSize: 13, marginBottom: space.s4 },
  label: {
    color: colors.textSecondary,
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginTop: space.s4,
    marginBottom: space.s2,
  },
  preview: {
    maxHeight: 180,
    backgroundColor: colors.bgDeep,
    borderColor: colors.borderStrong,
    borderWidth: 1,
    borderRadius: radius.sm,
    padding: space.s3,
  },
  previewText: { color: colors.textPrimary, fontFamily: "Menlo", fontSize: 13 },
  suggested: { flexDirection: "row", flexWrap: "wrap", gap: space.s2 },
  chip: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    backgroundColor: colors.bgDeep,
  },
  chipOn: { backgroundColor: colors.accent, borderColor: colors.accent },
  chipLabel: { color: colors.textSecondary, fontSize: 13 },
  chipLabelOn: { color: "#04121b", fontWeight: "600" },
  input: {
    backgroundColor: colors.bgDeep,
    borderColor: colors.borderStrong,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: 14,
    paddingVertical: 10,
    color: colors.textPrimary,
    fontSize: 14,
  },
  actions: { flexDirection: "row", gap: space.s3, marginTop: space.s5 },
  btn: { flex: 1, paddingVertical: 12, borderRadius: radius.pill, alignItems: "center" },
  btnPrimary: { backgroundColor: colors.accent },
  btnPrimaryLabel: { color: "#04121b", fontWeight: "700" },
  btnGhost: {
    backgroundColor: colors.bgElevated,
    borderColor: colors.borderStrong,
    borderWidth: 1,
  },
  btnGhostLabel: { color: colors.textPrimary, fontWeight: "500" },
});
