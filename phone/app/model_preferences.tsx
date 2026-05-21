// ClarityOS Mobile — model preferences (v44).
// Pick the model the kernel routes runs through. Mirrors web/Account
// ModelPreferences shape but stacked vertically for the phone form
// factor. Founder-controlled provider status comes from
// /founder/models/status when available; non-founder sessions get a
// 403 there and we fall back to the static list.

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View,
} from "react-native";
import {
  getProfile, founderModelsStatus, meOperatorStateModel, refreshProfile,
  V44_MODEL_IDS, type V44ModelId, type V44RouterStatus,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";

interface KernelBlock {
  preferred_model?: V44ModelId | null;
  last_model_used?: V44ModelId | null;
  models?: V44RouterStatus;
}

export default function ModelPreferencesScreen() {
  const [pref, setPref] = useState<V44ModelId | null>(null);
  const [last, setLast] = useState<V44ModelId | null>(null);
  const [router, setRouter] = useState<V44RouterStatus | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy("load"); setError(null);
    try {
      const profile = await refreshProfile();
      const ik = (profile as unknown as { intelligence_kernel?: KernelBlock })?.intelligence_kernel;
      setPref(ik?.preferred_model || null);
      setLast(ik?.last_model_used || null);
      // Provider status — try the founder-only endpoint, fall back if 403.
      try {
        const r = await founderModelsStatus();
        setRouter(r.router);
      } catch {
        setRouter(null);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const apply = useCallback(async (next: V44ModelId | null) => {
    setBusy("save"); setError(null);
    try {
      const value = next === "auto" ? null : next;
      await meOperatorStateModel(value);
      setPref(value);
      // Profile cache stays fresh on next /me — but for the
      // immediate UI feedback we already set local state.
      void getProfile;
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>Model preferences</Text>
      <Text style={styles.subtitle}>
        v44 router · {router ? `${Object.keys(router.providers).length} providers` : "user view"}
      </Text>

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
      )}

      {busy === "load" && !pref && (
        <ActivityIndicator color={colors.accent} style={{ marginTop: space.s4 }} />
      )}

      <View style={styles.card}>
        <Text style={styles.h2}>Your model</Text>
        <Text style={styles.muted}>
          The kernel routes #c, #G, ELINS and macro runs through whichever model
          you pick here. Tap "(auto)" to defer to the system default.
        </Text>
        <View style={styles.row}>
          {V44_MODEL_IDS.map((m) => {
            const selected = (pref || "auto") === m;
            return (
              <Pressable
                key={m}
                onPress={() => void apply(m)}
                disabled={busy !== null}
                style={[styles.pill, selected && styles.pillOn]}
              >
                <Text style={[styles.pillLabel, selected && styles.pillLabelOn]}>
                  {m === "auto" ? "auto" : m}
                </Text>
              </Pressable>
            );
          })}
        </View>
      </View>

      <View style={styles.card}>
        <Text style={styles.h2}>Status</Text>
        <Row k="Current preference" v={pref || "system default"} />
        <Row k="Last model used" v={last || "—"} />
        {router?.founder_default_model && (
          <Row k="Founder default" v={router.founder_default_model} warn />
        )}
      </View>

      {router && (
        <View style={styles.card}>
          <Text style={styles.h2}>Providers</Text>
          {Object.entries(router.providers).map(([provider, info]) => (
            <View key={provider} style={styles.providerRow}>
              <Text style={styles.providerName}>{provider}</Text>
              <Text style={[
                styles.providerState,
                info.configured ? styles.ready : styles.notReady,
              ]}>{info.configured ? "READY" : "NO KEY"}</Text>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

function Row({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <View style={styles.kvRow}>
      <Text style={styles.kvKey}>{k}</Text>
      <Text style={[styles.kvVal, warn && { color: colors.accent }]}>{v}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s4 },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600", marginBottom: space.s3 },
  card: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.lg, padding: space.s4, marginBottom: space.s3,
  },
  muted: { color: colors.textTertiary, fontSize: 11, marginBottom: space.s3 },
  row: { flexDirection: "row", flexWrap: "wrap", gap: space.s2 },
  pill: {
    paddingHorizontal: 10, paddingVertical: 5, borderRadius: radius.pill,
    backgroundColor: colors.bgDeep, borderColor: colors.border, borderWidth: 1,
  },
  pillOn: { borderColor: colors.accent, backgroundColor: colors.bgElevated },
  pillLabel: { color: colors.textSecondary, fontSize: 11, fontFamily: "Menlo" },
  pillLabelOn: { color: colors.accent, fontWeight: "600" },
  kvRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 2 },
  kvKey: { color: colors.textSecondary, fontSize: 12 },
  kvVal: { color: colors.textPrimary, fontSize: 12, fontFamily: "Menlo" },
  providerRow: {
    flexDirection: "row", justifyContent: "space-between",
    paddingVertical: 4, borderBottomColor: colors.border, borderBottomWidth: 1,
  },
  providerName: { color: colors.textPrimary, fontSize: 12, fontWeight: "600" },
  providerState: { fontSize: 10, fontWeight: "700", letterSpacing: 0.5 },
  ready: { color: colors.success },
  notReady: { color: colors.textTertiary },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
