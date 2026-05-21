import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { colors } from "../lib/theme";

export type LineKind = "user" | "engine" | "error";
export type Line = { kind: LineKind; text: string; ts: number };

const colorFor: Record<LineKind, string> = {
  user: colors.accent,
  engine: colors.textPrimary,
  error: colors.danger,
};

export default function ConsoleLine({ line }: { line: Line }) {
  const ts = new Date(line.ts).toLocaleTimeString();
  return (
    <View style={styles.row}>
      <Text style={styles.ts}>{ts}</Text>
      <Text style={[styles.body, { color: colorFor[line.kind] }]}>{line.text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", paddingVertical: 4, gap: 8, flexWrap: "wrap" },
  ts: { color: colors.textTertiary, fontFamily: "Menlo", fontSize: 12 },
  body: { fontFamily: "Menlo", fontSize: 13, flex: 1, flexWrap: "wrap" },
});
