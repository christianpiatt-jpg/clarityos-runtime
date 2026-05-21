// ClarityOS Mobile — Billing screen (v31).
// Shows the billing-state machine + transaction + intent history.

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { billingHistory, meBilling, type BillingHistoryIntent, type MembershipTransaction, type V42MeBilling } from "../lib/api";
import { useMembership } from "../lib/hooks/useMembership";
import { useFlags } from "../lib/hooks/useFlags";
import { colors, radius, space } from "../lib/theme";

function fmtUsd(n: number | null | undefined): string {
  if (typeof n !== "number") return "—";
  return `$${n.toFixed(2)}`;
}

function fmtTs(ts: number | null | undefined): string {
  if (!ts) return "—";
  try { return new Date(Number(ts) * 1000).toISOString().slice(0, 16).replace("T", " "); }
  catch { return String(ts); }
}

function fmtDate(ts: number | null | undefined): string {
  if (!ts) return "—";
  try { return new Date(Number(ts) * 1000).toISOString().slice(0, 10); }
  catch { return String(ts); }
}

const BILLING_LABEL: Record<string, { label: string; color: string; explain: string }> = {
  active: { label: "Active", color: "#7CD992", explain: "Paid up. Auto-renews on the date below." },
  past_due: { label: "Past due", color: "#ffb86b", explain: "Last renewal failed. Retrying up to 3 times over 72 hours." },
  grace_period: { label: "Grace period", color: "#ffb86b", explain: "Update payment before grace ends or membership cancels." },
  cancelled: { label: "Cancelled", color: "#ff8a8a", explain: "Membership ended. Reactivate from the membership screen." },
  failed: { label: "Failed", color: "#ff8a8a", explain: "Activation never completed." },
};

export default function BillingScreen() {
  const { flags, loading: flagsLoading } = useFlags();
  const { state, loading: memLoading } = useMembership();
  const [transactions, setTransactions] = useState<MembershipTransaction[]>([]);
  const [intents, setIntents] = useState<BillingHistoryIntent[]>([]);
  const [meBill, setMeBill] = useState<V42MeBilling | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [history, billing] = await Promise.all([
        billingHistory(100),
        meBilling().catch(() => null),
      ]);
      setTransactions(history.transactions);
      setIntents(history.intents);
      setMeBill(billing);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  if (flagsLoading || memLoading) {
    return <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>;
  }

  if (flags.membership_ui_enabled !== true) {
    return (
      <View style={styles.container}>
        <Text style={styles.h1}>Billing</Text>
        <Text style={styles.muted}>Billing is not enabled for your account yet.</Text>
      </View>
    );
  }

  const billing = state?.billing;
  const labelMeta = billing?.state ? BILLING_LABEL[billing.state] : null;

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <View style={styles.headerRow}>
        <Text style={styles.h1}>Billing</Text>
        {meBill && <ModePill mode={meBill.mode} />}
      </View>
      {meBill && !meBill.billing_enabled && (
        <View style={styles.disabledNotice}>
          <Text style={styles.disabledNoticeText}>
            Billing temporarily unavailable. Upgrades + renewals are paused.
          </Text>
        </View>
      )}

      {labelMeta && (
        <View style={styles.card}>
          <View style={styles.rowBetween}>
            <Text style={styles.h2}>Renewal</Text>
            <View style={[styles.badge, { backgroundColor: "#15301f" }]}>
              <Text style={[styles.badgeText, { color: labelMeta.color }]}>
                {labelMeta.label.toUpperCase()}
              </Text>
            </View>
          </View>
          <Row k="Next renewal" v={fmtDate(billing?.renewal_ts)} />
          <Row k="Next amount" v={fmtUsd(billing?.next_amount)} />
          {billing && billing.renewal_retry_count > 0 && (
            <Row k="Retry attempts" v={`${billing.renewal_retry_count} / 3`} />
          )}
          {billing?.state === "grace_period" && (
            <Row k="Grace ends" v={fmtDate(billing?.renewal_grace_until_ts)} />
          )}
          <Text style={styles.explain}>{labelMeta.explain}</Text>
          {(billing?.state === "past_due" || billing?.state === "grace_period") && (
            <Pressable style={[styles.btn, styles.disabled]}>
              <Text style={styles.btnLabel}>Update payment method</Text>
            </Pressable>
          )}
        </View>
      )}

      {error && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
          <Pressable onPress={() => void refresh()}>
            <Text style={styles.linkText}>Retry</Text>
          </Pressable>
        </View>
      )}

      <View style={styles.card}>
        <View style={styles.rowBetween}>
          <Text style={styles.h2}>Transactions</Text>
          <Pressable onPress={() => void refresh()}>
            <Text style={styles.linkText}>{loading ? "…" : "Refresh"}</Text>
          </Pressable>
        </View>
        {transactions.length === 0 ? (
          <Text style={styles.muted}>No transactions yet.</Text>
        ) : transactions.slice(0, 30).map((t, i) => (
          <View key={i} style={styles.txRow}>
            <Text style={styles.txWhen}>{fmtTs(t.ts)}</Text>
            <Text style={styles.txType}>{t.type}</Text>
            <Text style={[
              styles.txDelta,
              { color: t.credits_delta < 0 ? "#ff8a8a" : t.credits_delta > 0 ? "#7CD992" : colors.textSecondary },
            ]}>
              {t.credits_delta > 0 ? "+" : ""}{t.credits_delta || ""}
            </Text>
            <Text style={styles.txAmount}>{fmtUsd(t.amount)}</Text>
          </View>
        ))}
      </View>

      <View style={styles.card}>
        <Text style={styles.h2}>Payment intents</Text>
        {intents.length === 0 ? (
          <Text style={styles.muted}>No payment intents yet.</Text>
        ) : intents.slice(0, 30).map((i) => (
          <View key={i.intent_id} style={styles.txRow}>
            <Text style={styles.txWhen}>{fmtTs(i.created_ts)}</Text>
            <Text style={styles.txType}>{i.kind}</Text>
            <Text style={styles.txStatus}>{i.status}</Text>
            <Text style={styles.txAmount}>{fmtUsd(i.amount)}</Text>
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.muted}>{k}</Text>
      <Text style={styles.value}>{v}</Text>
    </View>
  );
}

function ModePill({ mode }: { mode: V42MeBilling["mode"] }) {
  const palette: Record<string, [string, string]> = {
    live:     ["#dc2626", "#fff"],
    test:     ["#2563eb", "#fff"],
    disabled: ["#6b7280", "#fff"],
  };
  const [bg, fg] = palette[mode] || palette.disabled;
  return (
    <View style={{
      backgroundColor: bg, paddingHorizontal: 10, paddingVertical: 3,
      borderRadius: radius.pill,
    }}>
      <Text style={{ color: fg, fontSize: 11, fontWeight: "700", letterSpacing: 0.6 }}>
        {mode.toUpperCase()}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bgDeep },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700" },
  headerRow: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    marginBottom: space.s4,
  },
  disabledNotice: {
    padding: space.s3, backgroundColor: "#3a1414",
    borderRadius: radius.md, marginBottom: space.s4,
  },
  disabledNoticeText: { color: "#ff8a8a", fontSize: 12 },
  h2: { color: colors.textPrimary, fontSize: 16, fontWeight: "600" },
  muted: { color: colors.textSecondary, fontSize: 13 },
  value: { color: colors.textPrimary, fontSize: 13 },
  explain: { color: colors.textSecondary, fontSize: 12, marginTop: space.s3 },
  card: {
    backgroundColor: colors.bgSurface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: space.s5,
    marginBottom: space.s4,
  },
  rowBetween: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: space.s3,
  },
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 4, gap: space.s3 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.pill },
  badgeText: { fontSize: 11, fontWeight: "700", letterSpacing: 0.5 },
  txRow: {
    flexDirection: "row",
    paddingVertical: 4,
    gap: space.s2,
    alignItems: "center",
  },
  txWhen: { color: colors.textSecondary, fontSize: 11, flex: 2 },
  txType: { color: colors.textPrimary, fontSize: 11, flex: 2 },
  txStatus: { color: colors.textSecondary, fontSize: 11, flex: 1 },
  txDelta: { fontSize: 11, fontWeight: "600", flex: 1, textAlign: "right" },
  txAmount: { color: colors.textPrimary, fontSize: 11, flex: 1, textAlign: "right" },
  btn: {
    backgroundColor: colors.bgElevated,
    paddingVertical: 10,
    borderRadius: radius.pill,
    alignItems: "center",
    marginTop: space.s3,
  },
  btnLabel: { color: colors.textPrimary, fontWeight: "600" },
  disabled: { opacity: 0.4 },
  errorBox: {
    padding: space.s3,
    backgroundColor: "#3a1414",
    borderRadius: radius.md,
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: space.s4,
  },
  errorText: { color: "#ff8a8a", flex: 1 },
  linkText: { color: colors.accent, fontWeight: "600" },
});
