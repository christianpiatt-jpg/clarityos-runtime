// ClarityOS Mobile — Founder console hub (v33).
// Lists shortcuts to the founder sub-screens. The API gates each
// endpoint server-side; this surface is just navigation.

import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { colors, radius, space } from "../lib/theme";

const SHORTCUTS: Array<{ path: string; title: string; subtitle: string }> = [
  { path: "/dashboard", title: "ELINS dashboard",
    subtitle: "v38 single intelligence surface (global + regional + macro + entity)" },
  { path: "/founder_analytics", title: "Analytics",
    subtitle: "v43 users + billing + intelligence summary" },
  { path: "/member_detail", title: "Member ops",
    subtitle: "Activate / cancel / adjust credits" },
  { path: "/elins_inspector", title: "ELINS inspector",
    subtitle: "Run the 10-layer pipeline + S_ELINS QC" },
  { path: "/dm_notes", title: "DM inbox",
    subtitle: "Manual DM tracker + founder notes" },
  { path: "/comment_generator", title: "#cmt — Comment generator",
    subtitle: "Most Relevant Comment Generator (MRCG v1.0)" },
  { path: "/regional", title: "Regional ELINS",
    subtitle: "v35 basin views (US/EU/MEA/APAC/Markets/Tech)" },
  { path: "/macro_runs", title: "Macro-ELINS",
    subtitle: "v36 scheduled global + regional runs" },
  { path: "/entities", title: "Entity graph",
    subtitle: "v37 cross-cluster entity network" },
];

export default function FounderHub() {
  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>Founder console</Text>
      <Text style={styles.muted}>
        All endpoints below are gated server-side; this surface is just navigation.
      </Text>
      {SHORTCUTS.map((s) => (
        <Pressable
          key={s.path}
          onPress={() => router.push(s.path as any)}
          style={styles.card}
        >
          <Text style={styles.cardTitle}>{s.title}</Text>
          <Text style={styles.cardSub}>{s.subtitle}</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700", marginBottom: space.s3 },
  muted: { color: colors.textSecondary, fontSize: 13, marginBottom: space.s4 },
  card: {
    backgroundColor: colors.bgSurface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: space.s5,
    marginBottom: space.s4,
  },
  cardTitle: { color: colors.textPrimary, fontSize: 16, fontWeight: "600" },
  cardSub: { color: colors.textSecondary, fontSize: 13, marginTop: 4 },
});
