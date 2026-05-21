// ClarityOS Mobile — causal-chain envelope chart (v34).
// Bar series for the chain envelope + a horizontal pill list of links.

import { StyleSheet, Text, View } from "react-native";
import { colors, radius, space } from "../lib/theme";

export interface ChainLink {
  key: string;
  intensity: number;
  lambda?: number;
  attenuation?: number;
}

export interface ChainEnvelopeProps {
  values: number[] | null;
  chain: ChainLink[] | null;
}

export default function ChainEnvelope({ values, chain }: ChainEnvelopeProps) {
  if (!values || values.length === 0 || !chain || chain.length === 0) {
    return <Text style={styles.empty}>No causal chain detected</Text>;
  }
  const ymax = Math.max(0.001, ...values.map(Math.abs));
  return (
    <View>
      <View style={styles.bars}>
        {values.map((v, i) => (
          <View key={`ce-${i}`} style={styles.slot}>
            <View
              style={[styles.bar, {
                height: Math.max(4, Math.round((Math.abs(v) / ymax) * 56)),
                backgroundColor: colors.danger,
              }]}
            />
            <Text style={styles.label}>D+{i}</Text>
            <Text style={styles.val}>{v.toFixed(3)}</Text>
          </View>
        ))}
      </View>
      <View style={styles.linkRow}>
        {chain.map((link, i) => (
          <View key={`link-${i}`} style={styles.linkPill}>
            <Text style={styles.linkKey}>{link.key}</Text>
            <Text style={styles.linkMeta}>
              i={link.intensity?.toFixed(3)}
              {typeof link.attenuation === "number"
                ? `  α=${link.attenuation.toFixed(2)}`
                : ""}
            </Text>
            {i < chain.length - 1 && <Text style={styles.linkArrow}>→</Text>}
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bars: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end", gap: 4 },
  slot: { flex: 1, alignItems: "center" },
  bar: { width: "75%", borderTopLeftRadius: radius.sm, borderTopRightRadius: radius.sm },
  label: { color: colors.textTertiary, fontSize: 10, marginTop: 4, fontFamily: "Menlo" },
  val: { color: colors.textSecondary, fontSize: 10, fontFamily: "Menlo" },
  linkRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: space.s3,
  },
  linkPill: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderColor: colors.borderStrong,
    borderWidth: 1,
    borderRadius: radius.pill,
    backgroundColor: colors.bgElevated,
  },
  linkKey: { color: colors.textPrimary, fontSize: 11, fontWeight: "600" },
  linkMeta: { color: colors.textSecondary, fontSize: 10, fontFamily: "Menlo", marginLeft: 4 },
  linkArrow: { color: colors.textTertiary, fontSize: 12, marginLeft: 4 },
  empty: { color: colors.textTertiary, fontSize: 12 },
});
