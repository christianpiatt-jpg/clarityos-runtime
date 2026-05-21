import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { router } from "expo-router";
import * as api from "../lib/api";
import { storage, KEYS, getAIProvider, setAIProvider } from "../lib/storage";
import { getProviders } from "../lib/providers";
import type { ProviderId } from "../lib/providers/types";
import { colors, radius, space } from "../lib/theme";
import { API_BASE } from "../lib/config";
import { useFlags } from "../lib/hooks/useFlags";
import { useMembership } from "../lib/hooks/useMembership";

export default function SettingsScreen() {
  const [base, setBase] = useState("");
  const [user, setUser] = useState<string | null>(null);
  const [config, setConfig] = useState<Record<string, any> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [providerId, setProviderId] = useState<ProviderId | null>(null);

  useEffect(() => {
    (async () => {
      const stored = await storage.get(KEYS.apiBaseOverride);
      setBase(stored || API_BASE);
      setUser(api.getUser());
      setProviderId(await getAIProvider());
      try {
        const r = await api.config();
        setConfig(r.data);
      } catch (e: any) {
        setError(e?.message || "Could not load runtime config");
      }
    })();
  }, []);

  async function chooseProvider(id: ProviderId) {
    await setAIProvider(id);
    setProviderId(id);
  }

  async function saveBase() {
    setError(null);
    const trimmed = base.trim();
    if (!trimmed) {
      await api.setApiBaseOverride(null);
    } else {
      await api.setApiBaseOverride(trimmed);
    }
  }

  async function logout() {
    await api.logout();
    await storage.multiRemove([KEYS.threads, KEYS.activeThread]);
    router.replace("/login");
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.bgDeep }} contentContainerStyle={{ padding: space.s5 }}>
      <View style={styles.card}>
        <Text style={styles.h3}>Backend</Text>
        <Text style={styles.muted}>Cloud Run URL the app talks to. Default comes from app.json. Set blank to revert.</Text>
        <TextInput
          value={base}
          onChangeText={setBase}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="https://...run.app"
          placeholderTextColor={colors.textTertiary}
          style={styles.input}
        />
        <Pressable onPress={saveBase} style={styles.cta}>
          <Text style={styles.ctaLabel}>Save</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.h3}>Account</Text>
        <Row k="user" v={user || "-"} />
        <MembershipBadge />
        <FounderBadge />
        <Pressable onPress={logout} style={[styles.cta, { backgroundColor: colors.bgElevated, marginTop: space.s4 }]}>
          <Text style={[styles.ctaLabel, { color: colors.textPrimary, fontWeight: "500" }]}>Sign out</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.h3}>AI Provider</Text>
        <Text style={styles.muted}>Picks which AI handles "Send to AI" from a session. The text is copied to your clipboard and the provider opens — paste once you're there.</Text>
        {getProviders().map((p) => {
          const on = p.id === providerId;
          return (
            <Pressable key={p.id} onPress={() => chooseProvider(p.id)} style={styles.providerRow}>
              <Text style={[styles.providerName, on && { color: colors.accent }]}>{p.name}</Text>
              {on && <Text style={styles.providerCheck}>✓</Text>}
            </Pressable>
          );
        })}
      </View>

      <View style={styles.card}>
        <Text style={styles.h3}>My intelligence profile</Text>
        <Text style={styles.muted}>v39 operator state — last topics, preferred regions, ESO mode. Metadata only.</Text>
        <Pressable onPress={() => router.push("/operator_profile")} style={[styles.cta, { backgroundColor: colors.bgElevated }]}>
          <Text style={[styles.ctaLabel, { color: colors.textPrimary, fontWeight: "500" }]}>Open profile</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.h3}>Model preferences</Text>
        <Text style={styles.muted}>v44 router — pick which model the kernel uses for #c, #G, ELINS and macro runs.</Text>
        <Pressable onPress={() => router.push("/model_preferences")} style={[styles.cta, { backgroundColor: colors.bgElevated }]}>
          <Text style={[styles.ctaLabel, { color: colors.textPrimary, fontWeight: "500" }]}>Open model picker</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.h3}>Local model</Text>
        <Text style={styles.muted}>v45 — on-device inference. Configured via CLARITYOS_LOCAL_MODEL_PATH on the backend; falls back to a deterministic mock when unset.</Text>
        <Pressable onPress={() => router.push("/local_model" as any)} style={[styles.cta, { backgroundColor: colors.bgElevated }]}>
          <Text style={[styles.ctaLabel, { color: colors.textPrimary, fontWeight: "500" }]}>Open local model</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.h3}>Memory Vault</Text>
        <Text style={styles.muted}>v46 — encrypted local KV store. Operator state, ELINS history, notes + embeddings live here.</Text>
        <Pressable onPress={() => router.push("/memory_vault" as any)} style={[styles.cta, { backgroundColor: colors.bgElevated }]}>
          <Text style={[styles.ctaLabel, { color: colors.textPrimary, fontWeight: "500" }]}>Open Memory Vault</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.h3}>Threads</Text>
        <Text style={styles.muted}>v47/v48 — persistent threaded conversations routed through the kernel's model picker. Stored encrypted in your Memory Vault.</Text>
        <Pressable onPress={() => router.push("/threads" as any)} style={[styles.cta, { backgroundColor: colors.bgElevated }]}>
          <Text style={[styles.ctaLabel, { color: colors.textPrimary, fontWeight: "500" }]}>Open Threads</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.h3}>Regression First</Text>
        <Text style={styles.muted}>v80 — drop a unified cognitive packet (EL/INS + regression skeleton) and persist it as a chain with one seeded layer. Timeline events emitted.</Text>
        <Pressable onPress={() => router.push("/regression_first" as any)} style={[styles.cta, { backgroundColor: colors.bgElevated }]}>
          <Text style={[styles.ctaLabel, { color: colors.textPrimary, fontWeight: "500" }]}>Open Regression First</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.h3}>Operator session</Text>
        <Text style={styles.muted}>v62 — runtime loop. Server holds vault + history; reload resumes the most recent session.</Text>
        <Pressable onPress={() => router.push("/operator_session" as any)} style={[styles.cta, { backgroundColor: colors.bgElevated }]}>
          <Text style={[styles.ctaLabel, { color: colors.textPrimary, fontWeight: "500" }]}>Open Operator Session</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.h3}>Session history</Text>
        <Text style={styles.muted}>v63 — read-only inspector over past operator sessions for this user.</Text>
        <Pressable onPress={() => router.push("/operator_session_history" as any)} style={[styles.cta, { backgroundColor: colors.bgElevated }]}>
          <Text style={[styles.ctaLabel, { color: colors.textPrimary, fontWeight: "500" }]}>Open Session History</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.h3}>Operator vault</Text>
        <Text style={styles.muted}>v63 — read-only snapshot of the runtime ELINS vault. Distinct from the legacy Vault below.</Text>
        <Pressable onPress={() => router.push("/operator_vault" as any)} style={[styles.cta, { backgroundColor: colors.bgElevated }]}>
          <Text style={[styles.ctaLabel, { color: colors.textPrimary, fontWeight: "500" }]}>Open Operator Vault</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.h3}>Model preferences</Text>
        <Text style={styles.muted}>v64 — choose which provider + model the runtime calls for your sessions.</Text>
        <Pressable onPress={() => router.push("/operator_model_preferences" as any)} style={[styles.cta, { backgroundColor: colors.bgElevated }]}>
          <Text style={[styles.ctaLabel, { color: colors.textPrimary, fontWeight: "500" }]}>Open Model Preferences</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.h3}>Vault</Text>
        <Text style={styles.muted}>Private, on-device storage for notes and session transcripts. Nothing is synced.</Text>
        <Pressable onPress={() => router.push("/vault")} style={[styles.cta, { backgroundColor: colors.bgElevated }]}>
          <Text style={[styles.ctaLabel, { color: colors.textPrimary, fontWeight: "500" }]}>Open Vault</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.h3}>Runtime configuration</Text>
        {error ? <Text style={{ color: colors.danger }}>{error}</Text> : null}
        {config ? (
          <>
            <Row k="backend" v={String(config.backend)} />
            <Row k="version" v={String(config.version)} />
            <Row k="library bucket" v={String(config.library_bucket)} />
            <Row k="session ttl" v={`${config.session_ttl}s`} />
            <Row k="gcs ready" v={String(config.gcs_available)} />
          </>
        ) : !error ? <Text style={styles.muted}>loading…</Text> : null}
      </View>

      <View style={styles.card}>
        <Text style={styles.h3}>Mode model</Text>
        <Text style={styles.muted}>
          <Text style={[styles.mono, { color: colors.accent }]}>#c</Text> runs an on-device adapter — fast, free, no network.{"\n"}
          <Text style={[styles.mono, { color: colors.accentViolet }]}>#G</Text> calls the Cloud Run engines (markov / galileo / tizzy / library).{"\n\n"}
          Threads are local-first. The cloud only sees what you forward. Switching mode mid-thread is fine — context is yours, the engines are stateless.
        </Text>
      </View>
    </ScrollView>
  );
}

/**
 * Membership badge — small inline summary inside the Account card.
 * Hidden when the membership UI flag is off. Tapping the badge opens
 * the full /membership screen.
 */
function MembershipBadge() {
  const { flags } = useFlags();
  const { state } = useMembership();
  if (flags.membership_ui_enabled !== true) return null;

  let label = "Not joined";
  let color: string = colors.textSecondary;
  if (state?.membership.status === "active") {
    label = `Founding 500 — $${(state.membership.price_locked ?? 50).toFixed(0)} locked`;
    color = colors.accent;
  } else if (state?.membership.status === "cancelled") {
    label = "Membership cancelled";
    color = "#ffb86b";
  }

  return (
    <Pressable
      // expo-router infers path types from the app/ tree; cast keeps the
      // build green when typegen hasn't run yet (CI runs `expo prebuild`).
      onPress={() => router.push("/membership" as any)}
      style={badgeStyles.row}
    >
      <Text style={badgeStyles.label}>Membership</Text>
      <Text style={[badgeStyles.value, { color }]}>{label} →</Text>
    </Pressable>
  );
}

const badgeStyles = StyleSheet.create({
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 6,
    marginTop: 4,
  },
  label: { color: colors.textSecondary, fontSize: 13 },
  value: { fontSize: 13, fontWeight: "600" },
});


/**
 * Founder badge — only visible to founder/founder_exception cohorts.
 * Tapping opens the /founder console hub.
 */
function FounderBadge() {
  const [isFounder, setIsFounder] = useState<boolean>(false);

  useEffect(() => {
    let active = true;
    api.me()
      .then((m: any) => {
        if (!active) return;
        const cohort = m?.cohort;
        if (cohort === "founder" || cohort === "founder_exception") {
          setIsFounder(true);
        }
      })
      .catch(() => { /* not authed or transient — stay hidden */ });
    return () => { active = false; };
  }, []);

  if (!isFounder) return null;

  return (
    <Pressable
      onPress={() => router.push("/founder" as any)}
      style={badgeStyles.row}
    >
      <Text style={badgeStyles.label}>Founder console</Text>
      <Text style={[badgeStyles.value, { color: colors.accent }]}>Open →</Text>
    </Pressable>
  );
}


function Row({ k, v }: { k: string; v: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.muted}>{k}</Text>
      <Text style={[styles.mono, { color: colors.textPrimary }]} numberOfLines={1}>{v}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgSurface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: space.s5,
    marginBottom: space.s4,
  },
  h3: { color: colors.textPrimary, fontSize: 16, fontWeight: "600", marginBottom: space.s3 },
  muted: { color: colors.textSecondary, fontSize: 13, marginBottom: space.s3 },
  input: {
    backgroundColor: colors.bgDeep,
    borderColor: colors.borderStrong,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: colors.textPrimary,
    fontFamily: "Menlo",
    fontSize: 13,
  },
  cta: {
    backgroundColor: colors.accent,
    paddingVertical: 12,
    borderRadius: radius.pill,
    alignItems: "center",
    marginTop: space.s4,
  },
  ctaLabel: { color: "#04121b", fontWeight: "700", fontSize: 14 },
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 4, gap: space.s3 },
  mono: { fontFamily: "Menlo", fontSize: 13 },
  providerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  providerName: { color: colors.textPrimary, fontSize: 14 },
  providerCheck: { color: colors.accent, fontSize: 16, fontWeight: "700" },
});
