// ClarityOS Mobile — Membership screen (v30).
// Activate / cancel Founding Cohort, see #G balance link, view cohort fill.

import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { router } from "expo-router";
import { useFlags } from "../lib/hooks/useFlags";
import { useMembership } from "../lib/hooks/useMembership";
import { colors, radius, space } from "../lib/theme";
import type { PaymentIntentView } from "../lib/api";

function fmtUsd(n: number | null | undefined): string {
  if (typeof n !== "number") return "—";
  return `$${n.toFixed(2)}`;
}

function fmtTs(ts: number | null | undefined): string {
  if (!ts) return "—";
  try { return new Date(Number(ts) * 1000).toISOString().slice(0, 10); }
  catch { return String(ts); }
}

export default function MembershipScreen() {
  const { flags, loading: flagsLoading } = useFlags();
  const { state, loading, error, refresh, activate, cancel, confirmIntent } = useMembership();
  const [accept, setAccept] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [pendingIntent, setPendingIntent] = useState<PaymentIntentView | null>(null);
  const [paymentBusy, setPaymentBusy] = useState(false);
  const [paymentError, setPaymentError] = useState<string | null>(null);

  const onActivate = useCallback(async () => {
    setBusy("activate");
    setPaymentError(null);
    const r = await activate(accept);
    setBusy(null);
    if (r === null) return;
    if (r.pending && r.intent) {
      setPendingIntent(r.intent);
    }
  }, [accept, activate]);

  const onCancel = useCallback(async () => {
    setBusy("cancel");
    await cancel();
    setBusy(null);
  }, [cancel]);

  const onConfirmPayment = useCallback(async () => {
    if (!pendingIntent) return;
    setPaymentBusy(true);
    setPaymentError(null);
    try {
      await confirmIntent(pendingIntent.intent_id);
      setPendingIntent(null);
    } catch (e: unknown) {
      setPaymentError(e instanceof Error ? e.message : String(e));
    } finally {
      setPaymentBusy(false);
    }
  }, [pendingIntent, confirmIntent]);

  if (flagsLoading || loading) {
    return (
      <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>
    );
  }
  if (flags.membership_ui_enabled !== true) {
    return (
      <View style={styles.container}>
        <Text style={styles.h1}>Membership</Text>
        <Text style={styles.muted}>
          Membership is not enabled for your account yet.
        </Text>
      </View>
    );
  }
  if (!state) {
    return (
      <View style={styles.container}>
        <Text style={styles.h1}>Membership</Text>
        {error ? (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
            <Pressable onPress={() => void refresh()} style={styles.linkBtn}>
              <Text style={styles.linkText}>Retry</Text>
            </Pressable>
          </View>
        ) : null}
      </View>
    );
  }

  const m = state.membership;
  const c = state.cohort;
  const isActive = m.status === "active";
  const isCancelled = m.status === "cancelled";
  const founderTier = flags.founder_tier_enabled === true;

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>Membership</Text>

      {/* Status card */}
      <View style={styles.card}>
        <View style={styles.rowBetween}>
          <Text style={styles.h2}>
            {m.tier === "founding_500" ? "Founding 500" : "Membership"}
          </Text>
          <View style={[
            styles.badge,
            isActive ? styles.badgeActive
              : isCancelled ? styles.badgeCancelled
              : styles.badgePending,
          ]}>
            <Text style={styles.badgeText}>
              {isActive ? "ACTIVE" : isCancelled ? "CANCELLED" : "NOT JOINED"}
            </Text>
          </View>
        </View>

        <Row k="Locked price" v={fmtUsd(m.price_locked)} />
        <Row k="Next price" v={fmtUsd(m.next_price)} />
        <Row k="Started" v={fmtTs(m.started_ts)} />
        {isCancelled && <Row k="Cancelled" v={fmtTs(m.cancelled_ts)} />}
        <Row k="Cohort fill" v={`${c.active_count} / ${c.cap ?? "—"}`} />
        {state.waitlist_position !== null && state.waitlist_position !== undefined && (
          <Row k="Waitlist position" v={`#${state.waitlist_position}`} />
        )}

        {isCancelled && (
          <View style={styles.warnBox}>
            <Text style={styles.warnText}>
              Reactivation will pay the full price ({fmtUsd(m.next_price)}).
            </Text>
          </View>
        )}
      </View>

      {/* v31 — Billing + renewal summary, links to the full billing screen. */}
      <Pressable
        onPress={() => router.push("/billing" as any)}
        style={styles.card}
      >
        <View style={styles.rowBetween}>
          <Text style={styles.h2}>Billing</Text>
          <RenewalBadge state={state.billing.state} />
        </View>
        {state.billing.renewal_ts ? (
          <Row k="Next renewal" v={fmtTs(state.billing.renewal_ts)} />
        ) : (
          <Text style={styles.muted}>Not yet active.</Text>
        )}
        {state.billing.next_amount > 0 && (
          <Row k="Next amount" v={fmtUsd(state.billing.next_amount)} />
        )}
        {state.billing.renewal_retry_count > 0 && (
          <Row k="Retry attempts" v={`${state.billing.renewal_retry_count} / 3`} />
        )}
        <Text style={[styles.linkText, { marginTop: 8 }]}>View transactions →</Text>
      </Pressable>

      {/* #G credits link */}
      <Pressable
        // expo-router typegen refreshes on prebuild — cast keeps the build
        // green for screens added in this pass.
        onPress={() => router.push("/g_credits" as any)}
        style={styles.card}
      >
        <View style={styles.rowBetween}>
          <View>
            <Text style={styles.h2}>#G credits</Text>
            <Text style={styles.muted}>
              {state.g_credits.balance} credits — tap to manage
            </Text>
          </View>
          <Text style={styles.linkText}>→</Text>
        </View>
      </Pressable>

      {/* Activate / Cancel */}
      {founderTier && !isActive && (
        <View style={styles.card}>
          <Text style={styles.h2}>
            {isCancelled ? "Reactivate" : "Activate Founding membership"}
          </Text>
          <Text style={styles.muted}>
            {isCancelled
              ? `Reactivation pays ${fmtUsd(m.next_price)}. Founding price lock is forfeited.`
              : `Locked at ${fmtUsd(m.next_price)} for the life of your membership. Cancellation forfeits the lock permanently.`}
          </Text>
          <View style={styles.row}>
            <Switch
              value={accept}
              onValueChange={setAccept}
              trackColor={{ false: colors.border, true: colors.accent }}
            />
            <Text style={styles.acceptLabel}>I understand the price-lock terms.</Text>
          </View>
          <Pressable
            onPress={() => void onActivate()}
            disabled={!accept || busy === "activate"}
            style={[
              styles.cta,
              (!accept || busy === "activate") && styles.disabled,
            ]}
          >
            <Text style={styles.ctaLabel}>
              {busy === "activate" ? "Activating…" : "Activate"}
            </Text>
          </Pressable>
        </View>
      )}

      {isActive && (
        <View style={styles.card}>
          <Text style={styles.h2}>Cancel</Text>
          <Text style={styles.muted}>
            Cancellation forfeits the {fmtUsd(m.price_locked)} price lock
            permanently. Reactivation will cost {fmtUsd(150.0)}.
          </Text>
          <Pressable
            onPress={() => void onCancel()}
            disabled={busy === "cancel"}
            style={[styles.dangerCta, busy === "cancel" && styles.disabled]}
          >
            <Text style={styles.dangerLabel}>
              {busy === "cancel" ? "Cancelling…" : "Cancel membership"}
            </Text>
          </Pressable>
        </View>
      )}

      <PaymentConfirmModal
        intent={pendingIntent}
        busy={paymentBusy}
        error={paymentError}
        onConfirm={onConfirmPayment}
        onCancel={() => { setPendingIntent(null); setPaymentError(null); }}
      />
    </ScrollView>
  );
}

interface PaymentConfirmModalProps {
  intent: PaymentIntentView | null;
  busy: boolean;
  error: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}

function PaymentConfirmModal({ intent, busy, error, onConfirm, onCancel }: PaymentConfirmModalProps) {
  if (!intent) return null;
  const isStripe = intent.mode === "stripe";
  return (
    <Modal visible={true} transparent animationType="fade" onRequestClose={onCancel}>
      <View style={styles.modalScrim}>
        <View style={styles.modalCard}>
          <Text style={styles.h2}>Confirm payment</Text>
          <Row k="Amount" v={fmtUsd(intent.amount)} />
          <Row k="Kind" v={intent.kind} />
          <Row k="Mode" v={intent.mode} />
          {isStripe ? (
            <Text style={styles.muted}>
              Stripe Elements would render here. The real client uses the
              client_secret to confirm.
            </Text>
          ) : (
            <Text style={styles.muted}>
              Mock mode — confirm fires a synthetic payment_intent.succeeded
              webhook.
            </Text>
          )}
          {error ? (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}
          <View style={[styles.row, { marginTop: space.s4 }]}>
            <Pressable
              onPress={onCancel}
              disabled={busy}
              style={[styles.btnGhost, busy && styles.disabled]}
            >
              <Text style={styles.btnGhostLabel}>Cancel</Text>
            </Pressable>
            <Pressable
              onPress={onConfirm}
              disabled={busy}
              style={[styles.cta, busy && styles.disabled]}
            >
              <Text style={styles.ctaLabel}>{busy ? "Confirming…" : "Confirm"}</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <View style={styles.row2}>
      <Text style={styles.muted}>{k}</Text>
      <Text style={styles.value}>{v}</Text>
    </View>
  );
}

const BADGE_FOR_STATE: Record<string, { label: string; bg: string; fg: string }> = {
  active:        { label: "ACTIVE",   bg: "#15301f", fg: "#7CD992" },
  past_due:      { label: "PAST DUE", bg: "#3a2c14", fg: "#ffb86b" },
  grace_period:  { label: "GRACE",    bg: "#3a2c14", fg: "#ffb86b" },
  cancelled:     { label: "CANCEL",   bg: "#3a1414", fg: "#ff8a8a" },
  failed:        { label: "FAILED",   bg: "#3a1414", fg: "#ff8a8a" },
};

function RenewalBadge({ state }: { state: string | null | undefined }) {
  if (!state) {
    return (
      <View style={[styles.badge, { backgroundColor: colors.bgElevated }]}>
        <Text style={styles.badgeText}>NONE</Text>
      </View>
    );
  }
  const meta = BADGE_FOR_STATE[state] ?? { label: state.toUpperCase(), bg: colors.bgElevated, fg: colors.textPrimary };
  return (
    <View style={[styles.badge, { backgroundColor: meta.bg }]}>
      <Text style={[styles.badgeText, { color: meta.fg }]}>{meta.label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bgDeep },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700", marginBottom: space.s4 },
  h2: { color: colors.textPrimary, fontSize: 16, fontWeight: "600", marginBottom: space.s3 },
  muted: { color: colors.textSecondary, fontSize: 13, marginBottom: space.s3 },
  value: { color: colors.textPrimary, fontSize: 13 },
  card: {
    backgroundColor: colors.bgSurface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: space.s5,
    marginBottom: space.s4,
  },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.pill },
  badgeActive: { backgroundColor: "#15301f" },
  badgeCancelled: { backgroundColor: "#3a1414" },
  badgePending: { backgroundColor: colors.bgElevated },
  badgeText: { color: colors.textPrimary, fontSize: 11, fontWeight: "700", letterSpacing: 0.5 },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  row: { flexDirection: "row", alignItems: "center", gap: space.s3, marginVertical: space.s3 },
  row2: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 4, gap: space.s3 },
  acceptLabel: { color: colors.textPrimary, fontSize: 13, flex: 1 },
  cta: {
    backgroundColor: colors.accent,
    paddingVertical: 12,
    borderRadius: radius.pill,
    alignItems: "center",
    marginTop: space.s3,
  },
  ctaLabel: { color: "#04121b", fontWeight: "700", fontSize: 14 },
  dangerCta: {
    backgroundColor: "#3a1414",
    borderWidth: 1,
    borderColor: "#ff8a8a",
    paddingVertical: 12,
    borderRadius: radius.pill,
    alignItems: "center",
    marginTop: space.s3,
  },
  dangerLabel: { color: "#ff8a8a", fontWeight: "700", fontSize: 14 },
  disabled: { opacity: 0.4 },
  warnBox: {
    marginTop: space.s3,
    padding: space.s3,
    backgroundColor: "#3a2c14",
    borderRadius: radius.md,
  },
  warnText: { color: "#ffd28a", fontSize: 12 },
  errorBox: {
    padding: space.s3,
    backgroundColor: "#3a1414",
    borderRadius: radius.md,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  errorText: { color: "#ff8a8a", flex: 1 },
  linkBtn: { padding: space.s2 },
  linkText: { color: colors.accent, fontWeight: "600" },
  modalScrim: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.6)",
    alignItems: "center",
    justifyContent: "center",
  },
  modalCard: {
    backgroundColor: colors.bgSurface,
    borderRadius: radius.lg,
    padding: space.s5,
    width: "85%",
    maxWidth: 360,
  },
  btnGhost: {
    backgroundColor: "transparent",
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: 10,
    paddingHorizontal: 18,
    borderRadius: radius.pill,
  },
  btnGhostLabel: { color: colors.textPrimary, fontWeight: "600" },
});
