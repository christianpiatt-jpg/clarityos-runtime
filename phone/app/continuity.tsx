import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import {
  clearInterrupted,
  getResumeOptions,
  type ResumeOption,
} from "../lib/continuity";
import { colors, geometry, spacing, typography } from "../lib/designSystem";

export default function ContinuityScreen() {
  const [options, setOptions] = useState<ResumeOption[] | null>(null);

  useEffect(() => {
    getResumeOptions().then(setOptions);
  }, []);

  async function startFresh() {
    await clearInterrupted();
    router.replace("/chat");
  }

  async function resume(opt: ResumeOption) {
    if (opt.kind === "interrupted-session") {
      await clearInterrupted();
      router.replace(`/session/${opt.threadId}`);
      return;
    }
    if (opt.kind === "last-thread") {
      router.replace(`/session/${opt.threadId}`);
      return;
    }
    if (opt.kind === "pending-vault") {
      router.replace("/vault");
      return;
    }
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.black }}
      contentContainerStyle={styles.scroll}
    >
      <Text style={[typography.label12, { color: colors.cyan, marginBottom: spacing.blockGap }]}>
        CONTINUITY REENTRY
      </Text>

      {options === null ? (
        <Text style={[typography.body16, { color: colors.darkGrey }]}>loading…</Text>
      ) : options.length === 0 ? (
        <Text style={[typography.body16, { color: colors.darkGrey, marginBottom: spacing.blockGap }]}>
          Nothing to resume.
        </Text>
      ) : (
        options.map((opt, i) => (
          <Pressable
            key={`${opt.kind}-${i}`}
            onPress={() => resume(opt)}
            style={({ pressed }) => [
              styles.optionBlock,
              { backgroundColor: pressed ? colors.neutralGrey : colors.deepGrey },
            ]}
          >
            <Text style={[typography.label12, { color: colors.cyan, marginBottom: 6 }]}>
              {labelFor(opt)}
            </Text>
            <Text style={typography.body16}>{detailFor(opt)}</Text>
          </Pressable>
        ))
      )}

      <Pressable
        onPress={startFresh}
        style={({ pressed }) => [
          styles.fresh,
          { backgroundColor: pressed ? colors.cyan : "transparent" },
        ]}
      >
        {({ pressed }) => (
          <Text
            style={[
              typography.label14,
              { color: pressed ? colors.black : colors.cyan },
            ]}
          >
            START FRESH
          </Text>
        )}
      </Pressable>
    </ScrollView>
  );
}

function labelFor(o: ResumeOption): string {
  if (o.kind === "interrupted-session") return "INTERRUPTED SESSION";
  if (o.kind === "pending-vault") return "PENDING VAULT ITEMS";
  if (o.kind === "last-thread") return "LAST THREAD";
  return "";
}

function detailFor(o: ResumeOption): string {
  if (o.kind === "interrupted-session") {
    return `Thread ${o.threadId} · interrupted ${new Date(o.lastEditedAt).toLocaleString()}`;
  }
  if (o.kind === "pending-vault") {
    return `${o.count} item${o.count === 1 ? "" : "s"} in vault`;
  }
  if (o.kind === "last-thread") {
    return o.title || `Thread ${o.threadId}`;
  }
  return "";
}

const styles = StyleSheet.create({
  scroll: { padding: spacing.frame },
  optionBlock: {
    padding: spacing.blockPadding,
    marginBottom: spacing.blockGap,
    borderWidth: 1,
    borderColor: colors.neutralGrey,
    borderRadius: geometry.radius0,
  },
  fresh: {
    paddingVertical: spacing.buttonPaddingVertical,
    borderWidth: 1,
    borderColor: colors.cyan,
    alignItems: "center",
    borderRadius: geometry.radius0,
    marginTop: spacing.blockGap,
  },
});
