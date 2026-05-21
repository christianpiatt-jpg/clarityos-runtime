// /invite/[token] — invite onboarding flow.
//
// Three branches based on the invite metadata returned by GET /invite/{token}:
//   1. founder_exception (free): collect username/password → /redeem
//   2. terrace_1 (paid):
//      a. collect username/password + plan → /checkout → open Stripe URL
//      b. on Stripe success-redirect, finalize via /finalize
//
// The "success" path back from Stripe lands at /invite/{token}?stripe_session_id=...
// (configured server-side via SUCCESS_URL). This screen detects the param
// and switches to the finalize step.

import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router, useLocalSearchParams } from "expo-router";
import { colors, geometry, spacing, typography } from "../../lib/designSystem";
import { refreshProfile, setSessionToken } from "../../lib/api";
import {
  getInvite,
  redeemFree,
  startCheckout,
  finalizeCheckout,
  type InviteMeta,
  type Plan,
} from "../../lib/invite";

type Phase =
  | { kind: "loading" }
  | { kind: "invalid"; message: string }
  | { kind: "form"; meta: InviteMeta }
  | { kind: "finalizing"; stripeSessionId: string; meta: InviteMeta }
  | { kind: "submitting" }
  | { kind: "done" };

export default function InviteScreen() {
  const params = useLocalSearchParams<{
    token: string;
    stripe_session_id?: string;
    plan?: Plan;
  }>();
  const token = params.token || "";
  const stripeSessionId = params.stripe_session_id || "";

  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [plan, setPlan] = useState<Plan>("recurring");
  const [error, setError] = useState<string | null>(null);

  // Load invite metadata on mount; if Stripe redirected back with a
  // session_id, jump straight into the finalize step.
  useEffect(() => {
    if (!token) {
      setPhase({ kind: "invalid", message: "No token in URL" });
      return;
    }
    let cancel = false;
    (async () => {
      try {
        const meta = await getInvite(token);
        if (cancel) return;
        if (stripeSessionId) {
          setPhase({ kind: "finalizing", stripeSessionId, meta });
        } else {
          setPhase({ kind: "form", meta });
        }
      } catch (e: any) {
        if (cancel) return;
        setPhase({ kind: "invalid", message: e?.message || "Invalid invite" });
      }
    })();
    return () => {
      cancel = true;
    };
  }, [token, stripeSessionId]);

  async function submitFree(meta: InviteMeta) {
    setError(null);
    setPhase({ kind: "submitting" });
    try {
      const r = await redeemFree(token, username.trim(), password);
      await setSessionToken(r.session_id, r.user);
      // Populate the in-memory profile (cohort + operator_id) so the next
      // screen sees the right state without an extra round-trip.
      await refreshProfile();
      setPhase({ kind: "done" });
      router.replace("/chat");
    } catch (e: any) {
      setError(e?.message || "Could not redeem invite");
      setPhase({ kind: "form", meta });
    }
  }

  async function submitPaid(meta: InviteMeta) {
    setError(null);
    setPhase({ kind: "submitting" });
    try {
      const r = await startCheckout(token, username.trim(), password, plan);
      // Hand off to Stripe Checkout. The success_url Stripe redirects back
      // to is /invite/{token}?stripe_session_id=... (configured server-side).
      await Linking.openURL(r.checkout_url);
      // Stay in the form; when the user returns, deep-link will rehydrate.
      setPhase({ kind: "form", meta });
    } catch (e: any) {
      setError(e?.message || "Could not start checkout");
      setPhase({ kind: "form", meta });
    }
  }

  async function submitFinalize(meta: InviteMeta) {
    setError(null);
    setPhase({ kind: "submitting" });
    try {
      const r = await finalizeCheckout(token, stripeSessionId, username.trim(), password);
      await setSessionToken(r.session_id, r.user);
      await refreshProfile();
      setPhase({ kind: "done" });
      router.replace("/chat");
    } catch (e: any) {
      setError(e?.message || "Could not finalize");
      setPhase({ kind: "finalizing", stripeSessionId, meta });
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <ScrollView
        style={styles.body}
        contentContainerStyle={styles.bodyContent}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={[typography.label12, { color: colors.cyan, marginBottom: spacing.blockGap }]}>
          INVITE
        </Text>

        {phase.kind === "loading" ? (
          <View style={styles.center}>
            <ActivityIndicator color={colors.cyan} />
            <Text style={[typography.body16, { color: colors.darkGrey, marginTop: spacing.blockPadding }]}>
              Validating invite…
            </Text>
          </View>
        ) : null}

        {phase.kind === "invalid" ? (
          <View style={styles.errorBlock}>
            <Text style={[typography.label12, { color: colors.red, marginBottom: 4 }]}>
              INVITE INVALID
            </Text>
            <Text style={typography.body16}>{phase.message}</Text>
          </View>
        ) : null}

        {(phase.kind === "form" || phase.kind === "submitting") &&
        "meta" in phase ? (
          <CredentialsForm
            meta={phase.meta}
            username={username}
            password={password}
            plan={plan}
            error={error}
            busy={phase.kind === "submitting"}
            onUsernameChange={setUsername}
            onPasswordChange={setPassword}
            onPlanChange={setPlan}
            onSubmit={() =>
              phase.meta.billing_required
                ? submitPaid(phase.meta)
                : submitFree(phase.meta)
            }
          />
        ) : null}

        {phase.kind === "form" && !phase.meta.billing_required ? null : null}

        {phase.kind === "finalizing" ? (
          <FinalizeForm
            meta={phase.meta}
            username={username}
            password={password}
            error={error}
            onUsernameChange={setUsername}
            onPasswordChange={setPassword}
            onSubmit={() => submitFinalize(phase.meta)}
          />
        ) : null}
      </ScrollView>

      <SafeAreaView edges={["bottom"]} style={styles.footer}>
        <Text style={[typography.label12, { color: colors.darkGrey }]}>
          Terrace-1 · ClarityOS
        </Text>
      </SafeAreaView>
    </KeyboardAvoidingView>
  );
}

// ---------- subcomponents -------------------------------------------------

function CohortBlock({ meta }: { meta: InviteMeta }) {
  const isFounder = meta.cohort === "founder_exception";
  return (
    <View style={styles.cohortBlock}>
      <Text style={[typography.label12, { color: colors.cyan, marginBottom: 4 }]}>
        {isFounder ? "FOUNDER EXCEPTION" : "TERRACE-1"}
      </Text>
      <Text style={typography.body18}>
        {isFounder
          ? "Free for life. Full operator envelope."
          : `$50  ·  monthly recurring or one-time (30 days)`}
      </Text>
    </View>
  );
}

function PlanPicker({ value, onChange }: { value: Plan; onChange: (p: Plan) => void }) {
  return (
    <View style={styles.planRow}>
      <PlanCard
        label="$50 / month"
        sub="Recurring · cancel any time"
        active={value === "recurring"}
        onPress={() => onChange("recurring")}
      />
      <PlanCard
        label="$50 once"
        sub="30 days · expires"
        active={value === "onetime"}
        onPress={() => onChange("onetime")}
      />
    </View>
  );
}

function PlanCard({
  label,
  sub,
  active,
  onPress,
}: {
  label: string;
  sub: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.planCard,
        {
          borderColor: active ? colors.cyan : colors.neutralGrey,
          backgroundColor: pressed ? colors.deepGrey : "transparent",
        },
      ]}
    >
      <Text
        style={[
          typography.label14,
          { color: active ? colors.cyan : colors.white, marginBottom: 4 },
        ]}
      >
        {label}
      </Text>
      <Text style={[typography.label12, { color: colors.darkGrey }]}>{sub}</Text>
    </Pressable>
  );
}

function CredentialsForm({
  meta,
  username,
  password,
  plan,
  error,
  busy,
  onUsernameChange,
  onPasswordChange,
  onPlanChange,
  onSubmit,
}: {
  meta: InviteMeta;
  username: string;
  password: string;
  plan: Plan;
  error: string | null;
  busy: boolean;
  onUsernameChange: (s: string) => void;
  onPasswordChange: (s: string) => void;
  onPlanChange: (p: Plan) => void;
  onSubmit: () => void;
}) {
  const canSubmit = !!username.trim() && password.length >= 8 && !busy;
  const ctaLabel = meta.billing_required
    ? `CONTINUE TO PAYMENT  ·  $${meta.price}`
    : "CREATE OPERATOR";
  return (
    <>
      <CohortBlock meta={meta} />
      <Text style={[typography.label12, styles.fieldLabel]}>USERNAME</Text>
      <TextInput
        value={username}
        onChangeText={onUsernameChange}
        autoCapitalize="none"
        autoCorrect={false}
        placeholder="3-64 chars, no spaces"
        placeholderTextColor={colors.darkGrey}
        style={styles.input}
        editable={!busy}
      />
      <Text style={[typography.label12, styles.fieldLabel]}>PASSWORD</Text>
      <TextInput
        value={password}
        onChangeText={onPasswordChange}
        secureTextEntry
        placeholder="8+ characters"
        placeholderTextColor={colors.darkGrey}
        style={styles.input}
        editable={!busy}
      />

      {meta.billing_required ? (
        <>
          <Text style={[typography.label12, styles.fieldLabel]}>PLAN</Text>
          <PlanPicker value={plan} onChange={onPlanChange} />
        </>
      ) : null}

      {error ? (
        <View style={styles.errorLine}>
          <Text style={[typography.label14, { color: colors.red }]}>{error}</Text>
        </View>
      ) : null}

      <Pressable
        onPress={onSubmit}
        disabled={!canSubmit}
        style={({ pressed }) => [
          styles.cta,
          {
            backgroundColor: pressed && canSubmit ? colors.cyan : "transparent",
            opacity: canSubmit ? 1 : 0.5,
          },
        ]}
      >
        {({ pressed }) => (
          <Text
            style={[
              typography.label14,
              { color: pressed && canSubmit ? colors.black : colors.cyan },
            ]}
          >
            {busy ? "…" : ctaLabel}
          </Text>
        )}
      </Pressable>

      {meta.billing_required ? (
        <Text style={[typography.label12, { color: colors.darkGrey, marginTop: spacing.blockPadding }]}>
          You'll be redirected to Stripe to complete payment, then sent back here to finalize your operator envelope.
        </Text>
      ) : null}
    </>
  );
}

function FinalizeForm({
  meta,
  username,
  password,
  error,
  onUsernameChange,
  onPasswordChange,
  onSubmit,
}: {
  meta: InviteMeta;
  username: string;
  password: string;
  error: string | null;
  onUsernameChange: (s: string) => void;
  onPasswordChange: (s: string) => void;
  onSubmit: () => void;
}) {
  const canSubmit = !!username.trim() && password.length >= 8;
  return (
    <>
      <CohortBlock meta={meta} />
      <View style={styles.successBlock}>
        <Text style={[typography.label12, { color: colors.cyan, marginBottom: 4 }]}>
          PAYMENT RECEIVED
        </Text>
        <Text style={typography.body16}>
          Confirm credentials to finalize your operator envelope.
        </Text>
      </View>

      <Text style={[typography.label12, styles.fieldLabel]}>USERNAME</Text>
      <TextInput
        value={username}
        onChangeText={onUsernameChange}
        autoCapitalize="none"
        autoCorrect={false}
        placeholderTextColor={colors.darkGrey}
        style={styles.input}
      />
      <Text style={[typography.label12, styles.fieldLabel]}>PASSWORD</Text>
      <TextInput
        value={password}
        onChangeText={onPasswordChange}
        secureTextEntry
        placeholderTextColor={colors.darkGrey}
        style={styles.input}
      />

      {error ? (
        <View style={styles.errorLine}>
          <Text style={[typography.label14, { color: colors.red }]}>{error}</Text>
        </View>
      ) : null}

      <Pressable
        onPress={onSubmit}
        disabled={!canSubmit}
        style={({ pressed }) => [
          styles.cta,
          {
            backgroundColor: pressed && canSubmit ? colors.cyan : "transparent",
            opacity: canSubmit ? 1 : 0.5,
          },
        ]}
      >
        {({ pressed }) => (
          <Text
            style={[
              typography.label14,
              { color: pressed && canSubmit ? colors.black : colors.cyan },
            ]}
          >
            FINALIZE OPERATOR
          </Text>
        )}
      </Pressable>
    </>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.black },
  body: { flex: 1 },
  bodyContent: { padding: spacing.frame, paddingBottom: spacing.frame * 2 },
  center: { alignItems: "center", justifyContent: "center", paddingVertical: spacing.frame * 2 },
  cohortBlock: {
    backgroundColor: colors.deepGrey,
    padding: spacing.blockPadding,
    borderWidth: 1,
    borderColor: colors.neutralGrey,
    borderRadius: geometry.radius0,
    marginBottom: spacing.blockGap,
  },
  successBlock: {
    backgroundColor: colors.deepGrey,
    padding: spacing.blockPadding,
    borderWidth: 1,
    borderColor: colors.cyan,
    borderRadius: geometry.radius0,
    marginBottom: spacing.blockGap,
  },
  fieldLabel: {
    color: colors.cyan,
    marginTop: spacing.blockPadding,
    marginBottom: 4,
  },
  input: {
    backgroundColor: colors.deepGrey,
    borderColor: colors.neutralGrey,
    borderWidth: 1,
    borderRadius: geometry.radius0,
    paddingHorizontal: spacing.blockPadding,
    paddingVertical: spacing.blockPadding,
    color: colors.white,
    fontSize: 16,
  },
  planRow: {
    flexDirection: "row",
    gap: spacing.gridGap,
  },
  planCard: {
    flex: 1,
    backgroundColor: colors.deepGrey,
    borderWidth: 1,
    borderRadius: geometry.radius0,
    padding: spacing.blockPadding,
  },
  errorBlock: {
    backgroundColor: colors.deepGrey,
    padding: spacing.blockPadding,
    borderWidth: 1,
    borderColor: colors.red,
    borderRadius: geometry.radius0,
    marginBottom: spacing.blockGap,
  },
  errorLine: {
    marginTop: spacing.blockPadding,
    paddingVertical: 6,
  },
  cta: {
    marginTop: spacing.blockGap,
    paddingVertical: spacing.buttonPaddingVertical,
    borderWidth: 1,
    borderColor: colors.cyan,
    borderRadius: geometry.radius0,
    alignItems: "center",
    justifyContent: "center",
  },
  footer: {
    paddingHorizontal: spacing.frame,
    paddingVertical: spacing.blockPadding,
    borderTopWidth: 1,
    borderTopColor: colors.neutralGrey,
    backgroundColor: colors.black,
  },
});
