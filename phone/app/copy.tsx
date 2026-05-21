import { useRef } from "react";
import { Pressable, ScrollView, Share, StyleSheet, Text, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import * as Clipboard from "expo-clipboard";
import { colors, geometry, spacing, typography } from "../lib/designSystem";
import { clarityPayloadFrom, saveNote, type VaultClarityPayload } from "../lib/vault";
import { takePendingClarity } from "../lib/runtimeBuffer";

export default function CopyScreen() {
  const params = useLocalSearchParams<{
    distilled?: string;
    engine?: string;
    interpreter?: string;
  }>();
  const distilled = params.distilled || "";
  const engine = params.engine || "";
  const interpreter = params.interpreter || "";

  // Drain the runtime buffer once, on first render. Subsequent re-renders
  // (state updates from button presses, etc.) reuse the cached value.
  const clarityRef = useRef<ReturnType<typeof takePendingClarity> | undefined>(undefined);
  if (clarityRef.current === undefined) {
    clarityRef.current = takePendingClarity();
  }
  const clarity = clarityRef.current;
  const payload: VaultClarityPayload | undefined = clarity
    ? clarityPayloadFrom(clarity)
    : undefined;

  async function copy() {
    if (!distilled) return;
    await Clipboard.setStringAsync(distilled);
  }

  async function share() {
    if (!distilled) return;
    try {
      await Share.share({ message: distilled });
    } catch {
      // user dismissed
    }
  }

  async function save() {
    if (!distilled) return;
    await saveNote({
      type: "note",
      content: distilled,
      tags: [engine, interpreter].filter(Boolean),
      source: "ai",
      clarity: payload,
    });
  }

  function discard() {
    router.replace("/chat");
  }

  // Optional: small pressure-signature footer so the operator can see why
  // this distillation looks the way it does at a glance.
  const pressureLine = payload
    ? `pressure: sentences=${payload.pressure.sentenceCount}  imperatives=${payload.pressure.imperatives}  urgency=${payload.pressure.urgencyWords}  hedge=${payload.pressure.hedgeRatio}  contradictions=${payload.pressure.contradictions}`
    : null;
  const interpreters = payload?.interpreters?.length
    ? payload.interpreters.map((i) => i.toUpperCase()).join(" · ")
    : null;

  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.outputBlock}>
          <Text
            style={[
              typography.label12,
              { color: colors.cyan, marginBottom: spacing.blockPadding },
            ]}
          >
            DISTILLED OUTPUT
            {interpreters ? `  ·  ${interpreters}` : ""}
          </Text>
          <Text style={typography.body18}>{distilled || "(no output)"}</Text>
          {pressureLine ? (
            <Text
              style={[
                typography.label12,
                { color: colors.darkGrey, marginTop: spacing.blockPadding },
              ]}
            >
              {pressureLine}
            </Text>
          ) : null}
        </View>
      </ScrollView>

      <View style={styles.grid}>
        <View style={styles.gridRow}>
          <Action label="COPY" onPress={copy} pressColor={colors.darkGrey} />
          <Action label="SHARE" onPress={share} pressColor={colors.darkGrey} />
        </View>
        <View style={styles.gridRow}>
          <Action label="SAVE TO VAULT" onPress={save} pressColor={colors.cyan} />
          <Action label="DISCARD" onPress={discard} pressColor={colors.red} />
        </View>
      </View>
    </View>
  );
}

function Action({
  label,
  onPress,
  pressColor,
}: {
  label: string;
  onPress: () => void;
  pressColor: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.actionBtn,
        { backgroundColor: pressed ? pressColor : "transparent" },
      ]}
    >
      {({ pressed }) => (
        <Text
          style={[
            typography.label14,
            { color: pressed ? colors.black : colors.white },
          ]}
        >
          {label}
        </Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.black },
  scroll: { padding: spacing.frame },
  outputBlock: {
    borderWidth: 1,
    borderColor: colors.neutralGrey,
    backgroundColor: colors.deepGrey,
    padding: spacing.blockPadding,
    borderRadius: geometry.radius0,
    minHeight: 200,
    width: "100%",
  },
  grid: {
    padding: spacing.frame,
    paddingTop: 0,
    gap: spacing.gridGap,
  },
  gridRow: {
    flexDirection: "row",
    gap: spacing.gridGap,
  },
  actionBtn: {
    flex: 1,
    paddingVertical: spacing.buttonPaddingVertical,
    borderWidth: 1,
    borderColor: colors.neutralGrey,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: geometry.radius0,
  },
});
