// ClarityOS Mobile — operator self-profile (v39).
//
// v66 / Unit 70 — wrapped in AuthGate so unauthed visits show an
// inline CTA. The backend /me/operator_state endpoint is already
// auth-only; the gate just provides explicit UX instead of a 401
// banner.

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, Pressable, RefreshControl,
  ScrollView, StyleSheet, Text, View,
} from "react-native";
import { router } from "expo-router";
import {
  meOperatorState, meOperatorStateUpdate,
  type V39OperatorState, type V39SignalMode,
} from "../lib/api";
import { colors, radius, space } from "../lib/theme";
import AuthGate from "../components/AuthGate";

const SIGNAL_MODES: V39SignalMode[] = ["cloud_only", "cloud_perplexity"];

export default function OperatorProfileScreen() {
  return (
    <AuthGate>
      <OperatorProfileScreenInner />
    </AuthGate>
  );
}

function OperatorProfileScreenInner() {
  const [state, setState] = useState<V39OperatorState | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy("load"); setError(null);
    try {
      const r = await meOperatorState();
      setState(r.state);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const setMode = useCallback(async (mode: V39SignalMode) => {
    setBusy("save"); setError(null);
    try {
      const r = await meOperatorStateUpdate({ external_signal_mode: mode });
      setState(r.state);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  if (busy === "load" && !state) {
    return <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>;
  }

  const domains = state ? Object.entries(state.preferred_domains).sort((a, b) => b[1] - a[1]).slice(0, 8) : [];
  const regions = state ? Object.entries(state.preferred_regions).sort((a, b) => b[1] - a[1]).slice(0, 8) : [];
  const dmax = Math.max(0.001, ...domains.map(([, v]) => v));
  const rmax = Math.max(0.001, ...regions.map(([, v]) => v));

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={styles.container}
      refreshControl={<RefreshControl refreshing={busy === "load"} onRefresh={load} tintColor={colors.accent} />}
    >
      <Text style={styles.h1}>My intelligence profile</Text>
      <Text style={styles.subtitle}>v39 operator state · metadata-only</Text>

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
      )}

      {state && (
        <View>
          <View style={styles.card}>
            <Text style={styles.h2}>Account</Text>
            <Row k="user_id" v={state.user_id} mono />
            <Row k="created" v={fmtTs(state.created_ts)} mono />
            <Row k="active" v={fmtTs(state.last_active_ts)} mono />
            <Row k="ELINS runs" v={String(state.elins_history.length)} mono />
            <Row k="#G runs" v={String(state.g_history.length)} mono />
          </View>

          <View style={styles.card}>
            <Text style={styles.h2}>External signal mode</Text>
            <Text style={styles.muted}>
              cloud_perplexity blends Perplexity-derived ESO into your regional ELINS runs.
            </Text>
            <View style={styles.row}>
              {SIGNAL_MODES.map((m) => (
                <Pressable
                  key={m}
                  onPress={() => void setMode(m)}
                  disabled={busy !== null}
                  style={[styles.pill, state.external_signal_mode === m && styles.pillOn]}
                >
                  <Text style={[
                    styles.pillLabel,
                    state.external_signal_mode === m && styles.pillLabelOn,
                  ]}>{m}</Text>
                </Pressable>
              ))}
            </View>
          </View>

          {regions.length > 0 && (
            <View style={styles.card}>
              <Text style={styles.h2}>Preferred regions</Text>
              {regions.map(([k, v]) => (
                <PrefRow key={k} name={k} weight={v} max={rmax} accent="#fbbf24" />
              ))}
            </View>
          )}

          {domains.length > 0 && (
            <View style={styles.card}>
              <Text style={styles.h2}>Preferred domains</Text>
              {domains.map(([k, v]) => (
                <PrefRow key={k} name={k} weight={v} max={dmax} accent={colors.accent} />
              ))}
            </View>
          )}

          <Pressable style={styles.linkRow} onPress={() => router.push("/operator_timeline")}>
            <Text style={styles.linkText}>Open full timeline →</Text>
          </Pressable>
        </View>
      )}
    </ScrollView>
  );
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <View style={styles.kvRow}>
      <Text style={styles.kvKey}>{k}</Text>
      <Text style={[styles.kvVal, mono && { fontFamily: "Menlo" }]}>{v}</Text>
    </View>
  );
}

function PrefRow({ name, weight, max, accent }: {
  name: string; weight: number; max: number; accent: string;
}) {
  return (
    <View style={{ marginBottom: 4 }}>
      <View style={styles.kvRow}>
        <Text style={styles.kvKey}>{name}</Text>
        <Text style={[styles.kvVal, { fontFamily: "Menlo" }]}>{weight.toFixed(2)}</Text>
      </View>
      <View style={styles.barTrack}>
        <View style={[styles.barFill, {
          width: `${Math.min(100, (weight / max) * 100)}%`,
          backgroundColor: accent,
        }]} />
      </View>
    </View>
  );
}

function fmtTs(ts: number): string {
  if (!ts || ts <= 0) return "—";
  return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 19);
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bgDeep },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginBottom: space.s4 },
  h2: { color: colors.textPrimary, fontSize: 14, fontWeight: "600", marginBottom: space.s3 },
  card: {
    backgroundColor: colors.bgSurface, borderColor: colors.border, borderWidth: 1,
    borderRadius: radius.lg, padding: space.s4, marginBottom: space.s3,
  },
  row: { flexDirection: "row", flexWrap: "wrap", gap: space.s2, marginTop: space.s2 },
  pill: {
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill,
    backgroundColor: colors.bgDeep, borderColor: colors.border, borderWidth: 1,
  },
  pillOn: { borderColor: colors.accent, backgroundColor: colors.bgElevated },
  pillLabel: { color: colors.textSecondary, fontSize: 12 },
  pillLabelOn: { color: colors.accent, fontWeight: "600" },
  kvRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 2 },
  kvKey: { color: colors.textSecondary, fontSize: 12 },
  kvVal: { color: colors.textPrimary, fontSize: 12 },
  barTrack: { height: 5, backgroundColor: colors.bgDeep, borderRadius: 3, marginTop: 2 },
  barFill: { height: "100%", borderRadius: 3 },
  muted: { color: colors.textTertiary, fontSize: 11, marginBottom: 4 },
  linkRow: { paddingVertical: space.s3, alignItems: "center" },
  linkText: { color: colors.accent, fontSize: 13, fontWeight: "600" },
  errorBox: { padding: space.s3, backgroundColor: "#3a1414", borderRadius: radius.md, marginBottom: space.s3 },
  errorText: { color: "#ff8a8a" },
});
