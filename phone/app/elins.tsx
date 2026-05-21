// ClarityOS Mobile — ELINS surface (v29-hardened).
// Adds:
//   * /v29/flags gating (v28 surfaces hidden when off)
//   * Loading + error states with explicit retry
//   * Offline fallback — last known feed loaded from AsyncStorage on mount
//   * Pull-to-refresh on the daily feed
//   * Defensive analysis rendering (never throws on missing fields)

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  fetchDailyFeed,
  isSuccessfulAnalysis,
  queueDailyReport,
  runPersonalElins,
  type ElinsDeliveredReport,
  type GElinsAnalysis,
} from "../lib/services/elins";
import { useFlags } from "../lib/hooks/useFlags";
import { storage } from "../lib/storage";
import { colors, geometry, spacing, typography } from "../lib/designSystem";

const SCENARIO_MAX_LEN = 8000;
const FEED_CACHE_KEY = "clarityos.elins_feed_cache";

function fmtTs(ts: number | null | undefined): string {
  if (!ts) return "—";
  try { return new Date(Number(ts) * 1000).toISOString().replace("T", " ").slice(0, 19); }
  catch { return String(ts); }
}

async function readCachedFeed(): Promise<ElinsDeliveredReport[]> {
  try {
    const raw = await storage.get(FEED_CACHE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch { return []; }
}

async function persistFeed(feed: ElinsDeliveredReport[]): Promise<void> {
  try { await storage.set(FEED_CACHE_KEY, JSON.stringify(feed)); } catch { /* noop */ }
}

export default function ElinsScreen() {
  const { flags, loading: flagsLoading } = useFlags();
  const [scenario, setScenario] = useState("");
  const [analysis, setAnalysis] = useState<GElinsAnalysis | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feed, setFeed] = useState<ElinsDeliveredReport[]>([]);
  const [feedError, setFeedError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [feedFromCache, setFeedFromCache] = useState(false);
  const [queueResult, setQueueResult] = useState<{ report_id: string; scheduled_for_ts: number } | null>(null);

  const v28Enabled = flags.v28_surfaces === true;

  const refreshFeed = useCallback(async () => {
    setRefreshing(true);
    setFeedError(null);
    try {
      const f = await fetchDailyFeed(50);
      setFeed(f);
      setFeedFromCache(false);
      await persistFeed(f);
    } catch (e: unknown) {
      setFeedError(e instanceof Error ? e.message : String(e));
      // On failure, keep whatever we have cached (already shown).
    } finally {
      setRefreshing(false);
    }
  }, []);

  // First mount: hydrate from cache before hitting network.
  useEffect(() => {
    let active = true;
    (async () => {
      const cached = await readCachedFeed();
      if (active && cached.length > 0) {
        setFeed(cached);
        setFeedFromCache(true);
      }
      if (v28Enabled) {
        await refreshFeed();
      }
    })();
    return () => { active = false; };
    // refreshFeed is stable (useCallback []); v28Enabled flips when flags load.
  }, [v28Enabled, refreshFeed]);

  const runG = useCallback(async () => {
    const text = scenario.trim();
    if (!text) { setError("Scenario must be non-empty."); return; }
    if (text.length > SCENARIO_MAX_LEN) {
      setError(`Scenario must be at most ${SCENARIO_MAX_LEN} characters.`);
      return;
    }
    setRunning(true); setError(null); setAnalysis(null);
    try { setAnalysis(await runPersonalElins(text)); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setRunning(false); }
  }, [scenario]);

  const queueDaily = useCallback(async () => {
    const text = scenario.trim();
    if (!text) { setError("Scenario must be non-empty."); return; }
    if (text.length > SCENARIO_MAX_LEN) {
      setError(`Scenario must be at most ${SCENARIO_MAX_LEN} characters.`);
      return;
    }
    setError(null);
    try {
      setQueueResult(await queueDailyReport({
        scenario_text: text,
        deliver_email: false,
        deliver_feed: true,
      }));
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
  }, [scenario]);

  const counter = useMemo(
    () => `${scenario.length}/${SCENARIO_MAX_LEN}`,
    [scenario.length],
  );

  if (flagsLoading) {
    return (
      <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
        <Text style={styles.h1}>ELINS</Text>
        <Text style={styles.subtle}>Checking access…</Text>
      </ScrollView>
    );
  }

  if (!v28Enabled) {
    return (
      <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
        <Text style={styles.h1}>ELINS</Text>
        <Text style={styles.subtle}>
          v28 surfaces (#G + daily feed) are not enabled for your account yet.
          Contact an admin to opt in.
        </Text>
      </ScrollView>
    );
  }

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={styles.container}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={refreshFeed}
          tintColor={colors.white}
        />
      }
    >
      <Text style={styles.h1}>ELINS</Text>
      <Text style={styles.subtle}>
        #G runs use existing primitives only. Scenario text is never persisted —
        only Dewey membership metadata. Daily reports deliver at 05:00 local.
      </Text>

      <View style={styles.section}>
        <Text style={styles.h2}>Scenario</Text>
        <TextInput
          value={scenario}
          onChangeText={setScenario}
          placeholder="us-china trade tensions and energy supply"
          placeholderTextColor={colors.darkGrey}
          multiline
          numberOfLines={4}
          maxLength={SCENARIO_MAX_LEN}
          style={styles.input}
          accessibilityLabel="Scenario text"
        />
        <Text style={[styles.subtle, { textAlign: "right", fontSize: 11, marginBottom: 0 }]}>
          {counter}
        </Text>
        <View style={styles.row}>
          <Pressable
            onPress={runG}
            disabled={running || !scenario.trim()}
            style={({ pressed }) => [
              styles.button,
              (running || !scenario.trim()) && styles.buttonDisabled,
              pressed && styles.buttonPressed,
            ]}
          >
            <Text style={styles.buttonText}>{running ? "Running…" : "Run #G now"}</Text>
          </Pressable>
          <Pressable
            onPress={queueDaily}
            disabled={!scenario.trim()}
            style={({ pressed }) => [
              styles.buttonSecondary,
              !scenario.trim() && styles.buttonDisabled,
              pressed && styles.buttonPressed,
            ]}
          >
            <Text style={styles.buttonSecondaryText}>Queue 05:00</Text>
          </Pressable>
        </View>
        {queueResult && (
          <View style={styles.notice}>
            <Text style={styles.noticeText}>
              Queued {queueResult.report_id} for {fmtTs(queueResult.scheduled_for_ts)}.
            </Text>
          </View>
        )}
        {error && (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
            <Pressable onPress={() => setError(null)} style={styles.linkButton}>
              <Text style={styles.linkText}>Dismiss</Text>
            </Pressable>
          </View>
        )}
      </View>

      {analysis && (
        <View style={styles.section}>
          <Text style={styles.h2}>Latest #G analysis</Text>
          <AnalysisRender a={analysis} />
        </View>
      )}

      <View style={styles.section}>
        <View style={styles.rowBetween}>
          <Text style={styles.h2}>Daily feed ({feed.length})</Text>
          <Pressable onPress={refreshFeed} style={styles.linkButton}>
            {refreshing
              ? <ActivityIndicator size="small" color={colors.white} />
              : <Text style={styles.linkText}>Refresh</Text>}
          </Pressable>
        </View>
        {feedFromCache && !refreshing && !feedError && (
          <Text style={styles.subtle}>
            Showing last-known feed (offline cache).
          </Text>
        )}
        {feedError && (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{feedError}</Text>
            <Pressable onPress={refreshFeed} style={styles.linkButton}>
              <Text style={styles.linkText}>Retry</Text>
            </Pressable>
          </View>
        )}
        {feed.length === 0 && !feedError && !refreshing && (
          <Text style={styles.subtle}>No delivered reports yet.</Text>
        )}
        {feed.map((r) => (
          <View key={r.report_id} style={styles.feedItem}>
            <Text style={styles.feedHeader}>
              {fmtTs(r.delivered_at)} · {r.scenario_id ?? "—"}
            </Text>
            {isSuccessfulAnalysis(r.analysis) ? (
              <AnalysisRender a={r.analysis} compact />
            ) : (
              <Text style={styles.errorText}>
                {r.analysis?.error ?? "error"}: {r.analysis?.message ?? ""}
              </Text>
            )}
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

function AnalysisRender({ a, compact = false }: { a: GElinsAnalysis; compact?: boolean }) {
  // v29 — every accessor is defensive: backend may return partial blocks
  // when an upstream layer is empty (new account, no Dewey neighborhoods).
  const neighborhoods = Array.isArray(a?.neighborhoods) ? a.neighborhoods : [];
  const pressure = a?.qc_summary?.pressure;
  const universal = a?.universal_physics;
  return (
    <View>
      <Text style={styles.body}>
        QC pressure: {typeof pressure === "number" ? pressure.toFixed(4) : "—"} ·{" "}
        Membership: {a?.persisted_membership_id || "(none)"}
      </Text>
      <Text style={[styles.body, { marginTop: spacing.gridGap }]}>
        Neighborhoods ({neighborhoods.length}):
      </Text>
      {neighborhoods.slice(0, compact ? 3 : 5).map((nb) => (
        <Text key={String(nb.neighborhood_id)} style={styles.bodyDim}>
          • {nb.name || nb.neighborhood_id || "(unnamed)"} —{" "}
          sim={typeof nb.similarity === "number" ? nb.similarity.toFixed(3) : "—"}
        </Text>
      ))}
      {!compact && universal && (
        <Text style={[styles.body, { marginTop: spacing.gridGap }]}>
          Universal constraints: {(universal.constraints || []).length} ·
          phases: {(universal.phases || []).length} ·
          operators: {(universal.operators || []).length}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.black },
  container: { padding: spacing.frame, paddingBottom: spacing.frame * 3 },
  h1: { ...typography.body18, color: colors.white, fontWeight: "700", marginBottom: spacing.gridGap, fontSize: 22 },
  h2: { ...typography.label16, color: colors.white, marginBottom: spacing.gridGap },
  body: { ...typography.body16, color: colors.white },
  bodyDim: { ...typography.body16, color: colors.lightGrey, marginLeft: spacing.gridGap },
  subtle: { ...typography.body16, color: colors.lightGrey, marginBottom: spacing.blockGap, fontSize: 13 },
  section: {
    marginTop: spacing.blockGap,
    padding: spacing.blockPadding,
    backgroundColor: colors.deepGrey,
    borderRadius: geometry.radius4,
  },
  input: {
    minHeight: 80,
    padding: spacing.blockPadding,
    color: colors.white,
    backgroundColor: colors.black,
    borderRadius: geometry.radius4,
    textAlignVertical: "top",
    fontSize: 14,
  },
  row: { flexDirection: "row", gap: spacing.gridGap, marginTop: spacing.gridGap },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  button: {
    paddingHorizontal: spacing.blockPadding,
    paddingVertical: spacing.gridGap,
    backgroundColor: colors.white,
    borderRadius: geometry.radius4,
  },
  buttonText: { ...typography.body16, color: colors.black, fontWeight: "600" },
  buttonSecondary: {
    paddingHorizontal: spacing.blockPadding,
    paddingVertical: spacing.gridGap,
    backgroundColor: colors.deepGrey,
    borderRadius: geometry.radius4,
    borderWidth: 1,
    borderColor: colors.white,
  },
  buttonSecondaryText: { ...typography.body16, color: colors.white, fontWeight: "600" },
  buttonDisabled: { opacity: 0.4 },
  buttonPressed: { opacity: 0.7 },
  linkButton: { padding: spacing.gridGap },
  linkText: { ...typography.body16, color: colors.white, fontWeight: "600" },
  notice: {
    marginTop: spacing.gridGap,
    padding: spacing.gridGap,
    backgroundColor: colors.black,
    borderRadius: geometry.radius4,
  },
  noticeText: { ...typography.body16, color: colors.white, fontSize: 12 },
  errorBox: {
    marginTop: spacing.gridGap,
    padding: spacing.gridGap,
    backgroundColor: "#3a1414",
    borderRadius: geometry.radius4,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  errorText: { ...typography.body16, color: "#ff8a8a", flex: 1 },
  feedItem: {
    marginTop: spacing.gridGap,
    padding: spacing.gridGap,
    backgroundColor: colors.black,
    borderRadius: geometry.radius4,
  },
  feedHeader: { ...typography.body16, color: colors.white, fontWeight: "600", marginBottom: spacing.gridGap, fontSize: 12 },
});
