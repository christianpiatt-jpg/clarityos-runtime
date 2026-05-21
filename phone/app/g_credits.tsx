// ClarityOS Mobile — #G credits screen (v30).
// Balance + buy buttons + purchase confirm modal + recent activity.

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFlags } from "../lib/hooks/useFlags";
import { useMembership } from "../lib/hooks/useMembership";
import { gHistory, type MembershipTransaction } from "../lib/api";
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

interface PurchaseModalProps {
  open: boolean;
  pack: "single" | "pack20" | null;
  busy: boolean;
  error: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}

function PurchaseModal({ open, pack, busy, error, onConfirm, onCancel }: PurchaseModalProps) {
  if (!pack) return null;
  const label = pack === "single" ? "Buy 1 credit for $1.00" : "Buy 20-pack for $20.00";
  const detail = pack === "single"
    ? "One #G run. Credits never expire."
    : "Twenty #G runs. Credits never expire.";
  return (
    <Modal visible={open} transparent animationType="fade" onRequestClose={onCancel}>
      <View style={styles.modalScrim}>
        <View style={styles.modalCard}>
          <Text style={styles.h2}>{label}</Text>
          <Text style={styles.muted}>{detail}</Text>
          {error ? (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}
          <View style={styles.row}>
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
              <Text style={styles.ctaLabel}>{busy ? "Charging…" : "Confirm"}</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

export default function GCreditsScreen() {
  const { flags, loading: flagsLoading } = useFlags();
  const { state, loading, error, refresh, buySingle, buyPack20 } = useMembership();
  const [modal, setModal] = useState<"single" | "pack20" | null>(null);
  const [busy, setBusy] = useState(false);
  const [purchaseError, setPurchaseError] = useState<string | null>(null);
  const [history, setHistory] = useState<MembershipTransaction[]>([]);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    setHistoryError(null);
    try {
      const r = await gHistory(50);
      setHistory(r.transactions);
    } catch (e: unknown) {
      setHistoryError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => { void fetchHistory(); }, [fetchHistory]);

  const confirmPurchase = useCallback(async () => {
    setBusy(true);
    setPurchaseError(null);
    const r = modal === "single" ? await buySingle() : await buyPack20();
    setBusy(false);
    if (r === null) {
      setPurchaseError("Purchase failed — try again.");
      return;
    }
    setModal(null);
    void fetchHistory();
  }, [modal, buySingle, buyPack20, fetchHistory]);

  if (flagsLoading || loading) {
    return <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>;
  }
  if (flags.g_credits_enabled !== true) {
    return (
      <View style={styles.container}>
        <Text style={styles.h1}>#G credits</Text>
        <Text style={styles.muted}>#G credits are not enabled for your account yet.</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.h1}>#G credits</Text>

      <View style={styles.card}>
        <Text style={styles.balance}>{state?.g_credits.balance ?? 0}</Text>
        <Text style={styles.muted}>One credit = one #G run. Credits never expire.</Text>
        <View style={styles.row}>
          <Pressable
            onPress={() => { setPurchaseError(null); setModal("single"); }}
            style={styles.btn}
          >
            <Text style={styles.btnLabel}>Buy 1 ({fmtUsd(1.0)})</Text>
          </Pressable>
          <Pressable
            onPress={() => { setPurchaseError(null); setModal("pack20"); }}
            style={styles.btn}
          >
            <Text style={styles.btnLabel}>20-pack ({fmtUsd(20.0)})</Text>
          </Pressable>
        </View>
        {error ? (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
            <Pressable onPress={() => void refresh()}>
              <Text style={styles.linkText}>Retry</Text>
            </Pressable>
          </View>
        ) : null}
      </View>

      <View style={styles.card}>
        <View style={styles.rowBetween}>
          <Text style={styles.h2}>Recent activity</Text>
          <Pressable onPress={() => void fetchHistory()}>
            <Text style={styles.linkText}>Refresh</Text>
          </Pressable>
        </View>
        {historyError ? (
          <Text style={styles.errorText}>{historyError}</Text>
        ) : null}
        {history.length === 0 ? (
          <Text style={styles.muted}>No activity yet.</Text>
        ) : (
          history.slice(0, 20).map((t, i) => (
            <View key={i} style={styles.txRow}>
              <Text style={styles.txWhen}>{fmtTs(t.ts)}</Text>
              <Text style={styles.txType}>{t.type}</Text>
              <Text style={[
                styles.txDelta,
                { color: t.credits_delta < 0 ? "#ff8a8a" : "#7CD992" },
              ]}>
                {t.credits_delta > 0 ? "+" : ""}{t.credits_delta}
              </Text>
              <Text style={styles.txAmount}>{fmtUsd(t.amount)}</Text>
            </View>
          ))
        )}
      </View>

      <PurchaseModal
        open={modal !== null}
        pack={modal}
        busy={busy}
        error={purchaseError}
        onConfirm={() => void confirmPurchase()}
        onCancel={() => setModal(null)}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bgDeep },
  container: { padding: space.s5 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bgDeep },
  h1: { color: colors.textPrimary, fontSize: 22, fontWeight: "700", marginBottom: space.s4 },
  h2: { color: colors.textPrimary, fontSize: 16, fontWeight: "600", marginBottom: space.s3 },
  muted: { color: colors.textSecondary, fontSize: 13, marginBottom: space.s3 },
  balance: { color: colors.textPrimary, fontSize: 48, fontWeight: "700", marginBottom: space.s3 },
  card: {
    backgroundColor: colors.bgSurface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: space.s5,
    marginBottom: space.s4,
  },
  row: { flexDirection: "row", gap: space.s3, marginTop: space.s3 },
  rowBetween: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: space.s3,
  },
  btn: {
    flex: 1,
    backgroundColor: colors.bgElevated,
    paddingVertical: 10,
    borderRadius: radius.pill,
    alignItems: "center",
  },
  btnLabel: { color: colors.textPrimary, fontWeight: "600" },
  cta: {
    backgroundColor: colors.accent,
    paddingVertical: 10,
    paddingHorizontal: 18,
    borderRadius: radius.pill,
    alignItems: "center",
  },
  ctaLabel: { color: "#04121b", fontWeight: "700" },
  btnGhost: {
    backgroundColor: "transparent",
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: 10,
    paddingHorizontal: 18,
    borderRadius: radius.pill,
  },
  btnGhostLabel: { color: colors.textPrimary, fontWeight: "600" },
  disabled: { opacity: 0.4 },
  txRow: { flexDirection: "row", paddingVertical: 4, gap: space.s2 },
  txWhen: { color: colors.textSecondary, fontSize: 11, flex: 2 },
  txType: { color: colors.textPrimary, fontSize: 11, flex: 2 },
  txDelta: { fontSize: 11, fontWeight: "600", flex: 1, textAlign: "right" },
  txAmount: { color: colors.textPrimary, fontSize: 11, flex: 1, textAlign: "right" },
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
  errorBox: {
    marginTop: space.s3,
    padding: space.s3,
    backgroundColor: "#3a1414",
    borderRadius: radius.md,
    flexDirection: "row",
    justifyContent: "space-between",
  },
  errorText: { color: "#ff8a8a", flex: 1 },
  linkText: { color: colors.accent, fontWeight: "600" },
});
