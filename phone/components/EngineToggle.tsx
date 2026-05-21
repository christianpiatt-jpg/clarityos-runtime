import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radius } from "../lib/theme";

type Option<V extends string> = { value: V; label: string };

type Props<V extends string> = {
  value: V;
  options: Option<V>[];
  onChange: (v: V) => void;
};

export default function SegmentedToggle<V extends string>({ value, options, onChange }: Props<V>) {
  return (
    <View style={styles.wrap}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <Pressable key={o.value} onPress={() => onChange(o.value)} style={[styles.btn, active && styles.btnActive]}>
            <Text style={[styles.label, active && styles.labelActive]}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    backgroundColor: colors.bgDeep,
    borderColor: colors.borderStrong,
    borderWidth: 1,
    borderRadius: radius.pill,
    padding: 3,
    alignSelf: "flex-start",
  },
  btn: {
    paddingVertical: 6,
    paddingHorizontal: 14,
    borderRadius: radius.pill,
  },
  btnActive: { backgroundColor: colors.accent },
  label: { color: colors.textSecondary, fontFamily: "Menlo", fontSize: 13 },
  labelActive: { color: "#04121b", fontWeight: "600" },
});
