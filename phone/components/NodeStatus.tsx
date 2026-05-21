import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { colors, radius, space } from "../lib/theme";

type Status = "ok" | "warn" | "err" | "idle";

type NodeProps = {
  name: string;
  meta: string;
  status: Status;
};

const dotColor: Record<Status, string> = {
  ok: colors.success,
  warn: colors.warning,
  err: colors.danger,
  idle: colors.textTertiary,
};

function Pill({ status, label }: { status: Status; label: string }) {
  return (
    <View style={styles.pill}>
      <View style={[styles.dot, { backgroundColor: dotColor[status], shadowColor: dotColor[status] }]} />
      <Text style={styles.pillText}>{label}</Text>
    </View>
  );
}

function NodeCard({ name, meta, status }: NodeProps) {
  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={styles.name}>{name}</Text>
        <Pill status={status} label={status === "ok" ? "ready" : status === "err" ? "down" : status} />
      </View>
      <Text style={styles.meta}>{meta}</Text>
    </View>
  );
}

type BlockProps = {
  local: NodeProps;
  cloud: NodeProps;
};

export default function NodeStatusBlock({ local, cloud }: BlockProps) {
  return (
    <View style={styles.row}>
      <View style={styles.col}><NodeCard {...local} /></View>
      <View style={styles.col}><NodeCard {...cloud} /></View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", gap: space.s3 },
  col: { flex: 1 },
  card: {
    backgroundColor: colors.bgSurface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: space.s4,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: space.s2,
  },
  name: { color: colors.textPrimary, fontWeight: "600", fontSize: 14 },
  meta: { color: colors.textTertiary, fontSize: 12 },
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingVertical: 2,
    paddingHorizontal: 8,
    borderRadius: radius.pill,
    backgroundColor: colors.bgElevated,
  },
  pillText: { color: colors.textSecondary, fontSize: 11, fontFamily: "Menlo" },
  dot: {
    width: 6, height: 6, borderRadius: 3,
    shadowOpacity: 0.6, shadowRadius: 6, shadowOffset: { width: 0, height: 0 },
  },
});
