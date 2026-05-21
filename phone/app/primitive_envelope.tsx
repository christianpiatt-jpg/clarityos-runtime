// ClarityOS Mobile — primitive envelope chart (v34).
// Stacked horizontal mini-bars: one row per primitive, one bar per
// day (D+0..D+N). Pure RN view — no SVG dep, no animation.

import { StyleSheet, Text, View } from "react-native";
import { colors, radius, space } from "../lib/theme";

const PRIMITIVE_COLORS: Record<string, string> = {
  pressure:      "#ff7b72",
  tension:       "#f59e0b",
  trust:         "#4ade80",
  drift:         "#a78bfa",
  contradiction: "#fb7185",
  alignment:     "#22d3ee",
};

export interface PrimitiveEnvelopeProps {
  envelopes: Record<string, number[]>;
}

export default function PrimitiveEnvelope({ envelopes }: PrimitiveEnvelopeProps) {
  const entries = Object.entries(envelopes).filter(
    ([, vs]) => Array.isArray(vs) && vs.length > 0,
  );
  if (entries.length === 0) {
    return <Text style={styles.empty}>No primitives</Text>;
  }
  const allVals = entries.flatMap(([, vs]) => vs.map(Math.abs));
  const ymax = Math.max(0.001, ...allVals);

  return (
    <View>
      {entries.map(([key, values]) => {
        const color = PRIMITIVE_COLORS[key] || colors.accent;
        return (
          <View key={key} style={styles.row}>
            <Text style={styles.label}>{key}</Text>
            <View style={styles.bars}>
              {values.map((v, i) => (
                <View key={`${key}-${i}`} style={styles.barSlot}>
                  <View
                    style={[styles.bar, {
                      height: Math.max(2, Math.round((Math.abs(v) / ymax) * 36)),
                      backgroundColor: color,
                    }]}
                  />
                  <Text style={styles.barLabel}>D+{i}</Text>
                  <Text style={styles.barVal}>{v.toFixed(3)}</Text>
                </View>
              ))}
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { marginBottom: space.s3 },
  label: { color: colors.textSecondary, fontSize: 11, marginBottom: 2 },
  bars: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end", gap: 4 },
  barSlot: { flex: 1, alignItems: "center" },
  bar: { width: "75%", borderTopLeftRadius: radius.sm, borderTopRightRadius: radius.sm },
  barLabel: { color: colors.textTertiary, fontSize: 9, marginTop: 2, fontFamily: "Menlo" },
  barVal: { color: colors.textSecondary, fontSize: 9, fontFamily: "Menlo" },
  empty: { color: colors.textTertiary, fontSize: 12 },
});
