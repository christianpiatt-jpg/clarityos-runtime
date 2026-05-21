// ClarityOS Mobile — Founder member ops (v33).
// Activate / cancel / adjust credits for a target user.

import { useCallback, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import {
  founderMembershipActivate,
  founderMembershipCancel,
  founderMembershipCredits,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";

export default function MemberDetailScreen() {
  const [user, setUser] = useState("");
  const [delta, setDelta] = useState("1");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wrap = useCallback(async (label: string, fn: () => Promise<unknown>) => {
    if (!user.trim()) {
      setError("Enter a username first.");
      return;
    }
    setBusy(label); setInfo(null); setError(null);
    try {
      await fn();
      setInfo(`${label} succeeded`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }, [user]);

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>Member ops</Text>
      <View style={styles.card}>
        <Text style={styles.label}>Username</Text>
        <TextInput
          value={user}
          onChangeText={setUser}
          placeholder="exact ClarityOS username"
          placeholderTextColor={colors.textTertiary}
          style={styles.input}
          autoCapitalize="none"
          autoCorrect={false}
        />
        <View style={styles.row}>
          <Pressable
            onPress={() => void wrap("activate",
              () => founderMembershipActivate(user.trim(), { note: "manual" }))}
            disabled={busy !== null}
            style={[styles.cta, busy === "activate" && styles.disabled]}
          >
            <Text style={styles.ctaLabel}>{busy === "activate" ? "…" : "Activate"}</Text>
          </Pressable>
          <Pressable
            onPress={() => void wrap("cancel",
              () => founderMembershipCancel(user.trim(), "manual"))}
            disabled={busy !== null}
            style={[styles.dangerCta, busy === "cancel" && styles.disabled]}
          >
            <Text style={styles.dangerLabel}>{busy === "cancel" ? "…" : "Cancel"}</Text>
          </Pressable>
        </View>
      </View>

      <View style={styles.card}>
        <Text style={styles.h2}>#G credits</Text>
        <Text style={styles.label}>Delta (positive grants, negative revokes)</Text>
        <TextInput
          value={delta}
          onChangeText={setDelta}
          keyboardType="numeric"
          style={styles.input}
        />
        <Text style={styles.label}>Reason (optional)</Text>
        <TextInput
          value={reason}
          onChangeText={setReason}
          placeholder="e.g. welcome bonus"
          placeholderTextColor={colors.textTertiary}
          style={styles.input}
        />
        <Pressable
          onPress={() => void wrap("credits",
            () => founderMembershipCredits(
              user.trim(), parseInt(delta, 10) || 0, reason.trim() || undefined,
            ),
          )}
          disabled={busy !== null}
          style={[styles.cta, busy === "credits" && styles.disabled]}
        >
          <Text style={styles.ctaLabel}>
            {busy === "credits" ? <ActivityIndicator color="#04121b" /> : "Adjust credits"}
          </Text>
        </Pressable>
      </View>

      {info && <View style={styles.infoBox}><Text style={styles.infoText}>{info}</Text></View>}
      {error && <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700", marginBottom: space.s3 },
  h2: { color: colors.textPrimary, fontSize: 16, fontWeight: "600", marginBottom: space.s3 },
  label: { color: colors.textSecondary, fontSize: 12, marginBottom: 4 },
  card: {
    backgroundColor: colors.bgSurface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: space.s5,
    marginBottom: space.s4,
  },
  input: {
    backgroundColor: colors.bgDeep,
    borderColor: colors.borderStrong,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: 14,
    paddingVertical: 10,
    color: colors.textPrimary,
    fontSize: 13,
    marginBottom: space.s3,
  },
  row: { flexDirection: "row", gap: space.s3 },
  cta: {
    flex: 1,
    backgroundColor: colors.accent,
    paddingVertical: 12,
    borderRadius: radius.pill,
    alignItems: "center",
  },
  ctaLabel: { color: "#04121b", fontWeight: "700" },
  dangerCta: {
    flex: 1,
    backgroundColor: "#3a1414",
    borderWidth: 1,
    borderColor: "#ff8a8a",
    paddingVertical: 12,
    borderRadius: radius.pill,
    alignItems: "center",
  },
  dangerLabel: { color: "#ff8a8a", fontWeight: "700" },
  disabled: { opacity: 0.4 },
  infoBox: { padding: space.s3, backgroundColor: "#15301f", borderRadius: radius.md, marginBottom: space.s3 },
  infoText: { color: "#7CD992" },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
