// ClarityOS Mobile — domain envelope chart (v34).
// One row per spec-named domain. Each row is a sparkline rendered as a
// thin View list (no SVG dep).

import { StyleSheet, Text, View } from "react-native";
import { colors, radius, space } from "../lib/theme";

const DOMAIN_COLORS: Record<string, string> = {
  Economic_Markets:   "#fbbf24",
  Geopolitical:       "#ff7b72",
  Social_Cultural:    "#22d3ee",
  Security_Military:  "#ef4444",
  Legal_Justice:      "#a78bfa",
  Science_Technology: "#4ade80",
  Environmental:      "#34d399",
};

export interface DomainEnvelopeProps {
  domains: Record<string, number[]>;
}

export default function DomainEnvelope({ domains }: DomainEnvelopeProps) {
  const entries = Object.entries(domains).filter(
    ([, vs]) => Array.isArray(vs) && vs.length > 0,
  );
  if (entries.length === 0) {
    return <Text style={styles.empty}>No domain envelopes</Text>;
  }
  return (
    <View>
      {entries.map(([name, values]) => {
        const ymax = Math.max(0.001, ...values.map(Math.abs));
        const color = DOMAIN_COLORS[name] || colors.accent;
        return (
          <View key={name} style={styles.row}>
            <View style={styles.head}>
              <Text style={styles.name}>{name.replace("_", " ")}</Text>
              <Text style={styles.range}>
                {values[0]?.toFixed(3)} → {values[values.length - 1]?.toFixed(3)}
              </Text>
            </View>
            <View style={styles.spark}>
              {values.map((v, i) => (
                <View
                  key={`${name}-${i}`}
                  style={[styles.bar, {
                    height: Math.max(2, Math.round((Math.abs(v) / ymax) * 24)),
                    backgroundColor: color,
                  }]}
                />
              ))}
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    paddingVertical: space.s2,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
  },
  head: { flexDirection: "row", justifyContent: "space-between", marginBottom: 4 },
  name: { color: colors.textPrimary, fontSize: 11, fontWeight: "600" },
  range: { color: colors.textTertiary, fontSize: 10, fontFamily: "Menlo" },
  spark: { flexDirection: "row", alignItems: "flex-end", gap: 3, height: 26 },
  bar: { flex: 1, borderRadius: radius.sm },
  empty: { color: colors.textTertiary, fontSize: 12 },
});
