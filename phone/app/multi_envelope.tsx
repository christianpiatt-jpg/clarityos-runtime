// ClarityOS Mobile — multi-primitive envelope chart (v34).
// Single horizontal bar series (D+0..D+N).

import { StyleSheet, Text, View } from "react-native";
import { colors, radius, space } from "../lib/theme";

export interface MultiEnvelopeProps {
  values: number[];
}

export default function MultiEnvelope({ values }: MultiEnvelopeProps) {
  if (!Array.isArray(values) || values.length === 0) {
    return <Text style={styles.empty}>No multi envelope</Text>;
  }
  const ymax = Math.max(0.001, ...values.map(Math.abs));
  return (
    <View style={styles.row}>
      {values.map((v, i) => (
        <View key={`mp-${i}`} style={styles.slot}>
          <View
            style={[styles.bar, {
              height: Math.max(4, Math.round((Math.abs(v) / ymax) * 60)),
              backgroundColor: v < 0 ? colors.danger : colors.accent,
            }]}
          />
          <Text style={styles.label}>D+{i}</Text>
          <Text style={styles.val}>{v.toFixed(3)}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end", gap: 4 },
  slot: { flex: 1, alignItems: "center" },
  bar: { width: "75%", borderTopLeftRadius: radius.sm, borderTopRightRadius: radius.sm },
  label: { color: colors.textTertiary, fontSize: 10, marginTop: 4, fontFamily: "Menlo" },
  val: { color: colors.textSecondary, fontSize: 10, fontFamily: "Menlo" },
  empty: { color: colors.textTertiary, fontSize: 12 },
});
