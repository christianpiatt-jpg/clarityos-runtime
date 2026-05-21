// ClarityOS Mobile — local model runtime screen (v45).
// Mirrors web/Account LocalModelPanel — shows whether the on-device
// runtime is configured/loaded, the path it would use, the per-user
// usage counter, and the fallback behaviour when nothing is wired up.
//
// Pulls /me/local_model and renders read-only. The runtime warms up
// on the first kernel call that selects local:llama3.1; this screen
// never tries to drive a load itself.

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View,
} from "react-native";
import { meLocalModel, type V45LocalModelMe } from "../lib/api";
import { colors, radius, space } from "../lib/theme";

export default function LocalModelScreen() {
  const [data, setData] = useState<V45LocalModelMe | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy("load"); setError(null);
    try {
      const r = await meLocalModel();
      setData(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>Local model</Text>
      <Text style={styles.subtitle}>
        v45 runtime · {data?.runtime.backend || "—"}
      </Text>

      {error && (
        <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View>
      )}

      {busy === "load" && !data && (
        <ActivityIndicator color={colors.accent} style={{ marginTop: space.s4 }} />
      )}

      {data && (
        <>
          <View style={styles.card}>
            <Text style={styles.h2}>Runtime</Text>
            <Row k="Configured" v={data.runtime.configured ? "yes" : "no"} on={data.runtime.configured} />
            <Row k="Loaded" v={data.runtime.loaded ? "yes" : "cold"} on={data.runtime.loaded} />
            <Row k="Real / mock" v={data.runtime.mock ? "mock" : "real"} on={!data.runtime.mock} />
            <Row k="Backend" v={data.runtime.backend || "—"} />
            <Row k="Memory" v={`${data.runtime.memory_footprint_mb.toFixed(1)} MB`} />
            <Row k="Inferences (process)" v={String(data.runtime.inference_count)} />
          </View>

          <View style={styles.card}>
            <Text style={styles.h2}>Path</Text>
            <Text style={styles.path}>{data.runtime.path || "(unset)"}</Text>
            <Text style={styles.muted}>
              {data.runtime.path
                ? "Loaded once per process. Restart the backend to pick up a new path."
                : "Set CLARITYOS_LOCAL_MODEL_PATH on the backend to enable on-device inference."}
            </Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.h2}>Your usage</Text>
            <Row k="Local model picks" v={String(data.usage.local_model_usage_count)} />
            <Row k="Last model used" v={data.usage.last_model_used || "—"} />
            <Row k="Preferred?" v={data.usage.is_local_preferred ? "yes" : "no"} on={data.usage.is_local_preferred} />
            <Text style={styles.muted}>
              Counter increments each time the kernel routes one of your runs through
              the on-device model.
            </Text>
          </View>

          {data.runtime.fallback && (
            <View style={styles.card}>
              <Text style={styles.h2}>Fallback</Text>
              <Text style={styles.path}>{data.runtime.fallback}</Text>
              <Text style={styles.muted}>
                Without a configured path the runtime returns a deterministic mock so the
                routing chain still works end-to-end.
              </Text>
            </View>
          )}

          {data.runtime.last_error && (
            <View style={styles.card}>
              <Text style={[styles.h2, { color: "#ff8a8a" }]}>Last error</Text>
              <Text style={styles.path}>{data.runtime.last_error}</Text>
            </View>
          )}

          <Pressable onPress={() => void load()} disabled={busy !== null} style={styles.cta}>
            <Text style={styles.ctaLabel}>{busy === "load" ? "…" : "Refresh"}</Text>
          </Pressable>
        </>
      )}
    </ScrollView>
  );
}

function Row({ k, v, on }: { k: string; v: string; on?: boolean }) {
  return (
    <View style={styles.kvRow}>
      <Text style={styles.kvKey}>{k}</Text>
      <Text style={[
        styles.kvVal,
        on === true && { color: colors.success },
        on === false && { color: colors.textTertiary },
      ]}>{v}</Text>
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
  muted: { color: colors.textTertiary, fontSize: 11, marginTop: space.s2 },
  path: {
    color: colors.textPrimary, fontFamily: "Menlo", fontSize: 12,
    marginBottom: space.s2,
  },
  kvRow: {
    flexDirection: "row", justifyContent: "space-between",
    paddingVertical: 3, gap: space.s3,
  },
  kvKey: { color: colors.textSecondary, fontSize: 12 },
  kvVal: { color: colors.textPrimary, fontSize: 12, fontFamily: "Menlo" },
  cta: {
    backgroundColor: colors.bgElevated, borderColor: colors.border, borderWidth: 1,
    paddingVertical: 12, borderRadius: radius.pill, alignItems: "center",
    marginTop: space.s2,
  },
  ctaLabel: { color: colors.textPrimary, fontWeight: "600", fontSize: 13 },
  errorBox: {
    padding: space.s3, backgroundColor: "#3a1414",
    borderRadius: radius.md, marginBottom: space.s3,
  },
  errorText: { color: "#ff8a8a" },
});
