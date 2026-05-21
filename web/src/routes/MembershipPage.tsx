// routes/MembershipPage.tsx — Founding cohort + #G credits page (v31).
//
// Composes the membership components:
//   * MembershipStatusCard   — tier / locked price / cohort fill / waitlist
//   * RenewalStatusCard      — billing state + renewal date (v31)
//   * GCreditsPanel          — balance, buy buttons, recent activity
//   * PurchaseCreditsModal   — confirm dialog for credit purchases
//   * PaymentModal           — PaymentIntent confirmation (v31)
//   * BillingHistoryPanel    — full transaction + intent history (v31)
//
// Plus the activate / cancel actions, gated on the membership_ui_enabled
// flag. The activate flow now creates a PaymentIntent and surfaces the
// confirmation modal; in mock auto-confirm mode the side-effect lands
// inline so the modal closes immediately.

import { useState } from "react";
import { useFlags } from "../hooks/useFlags";
import { useMembership } from "../hooks/useMembership";
import MembershipStatusCard from "../components/membership/MembershipStatusCard";
import RenewalStatusCard from "../components/membership/RenewalStatusCard";
import GCreditsPanel from "../components/membership/GCreditsPanel";
import PurchaseCreditsModal from "../components/membership/PurchaseCreditsModal";
import PaymentModal from "../components/membership/PaymentModal";
import BillingHistoryPanel from "../components/membership/BillingHistoryPanel";
import type { PaymentIntentView } from "../lib/api";

export default function MembershipPage() {
  const { flags, loading: flagsLoading } = useFlags();
  const {
    state, loading, error, refresh,
    activate, cancel, buySingle, buyPack20, confirmIntent,
  } = useMembership();

  const [accept, setAccept] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState<"single" | "pack20" | null>(null);
  const [purchaseError, setPurchaseError] = useState<string | null>(null);
  const [pendingIntent, setPendingIntent] = useState<PaymentIntentView | null>(null);
  const [paymentBusy, setPaymentBusy] = useState(false);
  const [paymentError, setPaymentError] = useState<string | null>(null);

  const uiEnabled = flags.membership_ui_enabled === true;

  if (flagsLoading || loading) {
    return (
      <div className="membership">
        <h1>Membership</h1>
        <p style={{ color: "#666" }}>Loading…</p>
      </div>
    );
  }

  if (!uiEnabled) {
    return (
      <div className="membership">
        <h1>Membership</h1>
        <p style={{ color: "#666" }}>
          Membership is not enabled for your account yet. Contact an admin to
          opt in.
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="membership">
        <h1>Membership</h1>
        <div style={{
          padding: 12,
          background: "#fee",
          border: "1px solid #f99",
          marginBottom: 12,
        }}>
          {error}
          <button onClick={() => void refresh()} style={{ marginLeft: 8 }}>Retry</button>
        </div>
      </div>
    );
  }

  if (!state) {
    return (
      <div className="membership">
        <h1>Membership</h1>
        <p style={{ color: "#666" }}>No membership state available.</p>
      </div>
    );
  }

  const founderTierEnabled = flags.founder_tier_enabled === true;
  const gCreditsEnabled = flags.g_credits_enabled === true;
  const m = state.membership;
  const isActive = m.status === "active";

  const onActivate = async () => {
    setBusyAction("activate");
    setPaymentError(null);
    const result = await activate(accept);
    setBusyAction(null);
    if (result === null) return;
    // If the call returned a pending PaymentIntent, surface the confirmation
    // modal. In auto-confirm mock mode the result is already settled and
    // the intent block is omitted.
    if (result.pending && result.intent) {
      setPendingIntent(result.intent);
    }
  };

  const onCancel = async () => {
    if (!confirm(
      "Cancel your Founding membership? You'll lose your $50 price lock; reactivation will cost $150."
    )) return;
    setBusyAction("cancel");
    await cancel();
    setBusyAction(null);
  };

  const confirmPurchase = async () => {
    setPurchaseError(null);
    setBusyAction(modalOpen);
    const r = modalOpen === "single" ? await buySingle() : await buyPack20();
    setBusyAction(null);
    if (r === null) {
      setPurchaseError("Purchase failed — try again.");
      return;
    }
    setModalOpen(null);
    if (r.pending && r.intent) {
      // Async path — surface the payment modal so the user confirms.
      setPendingIntent(r.intent);
    }
  };

  const onPaymentConfirm = async () => {
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
  };

  return (
    <div className="membership" style={{ maxWidth: 720 }}>
      <h1>Membership</h1>

      <MembershipStatusCard state={state} />

      <RenewalStatusCard
        state={state}
        onUpdatePaymentMethod={undefined /* placeholder until v32 */}
      />

      {gCreditsEnabled && (
        <GCreditsPanel
          state={state}
          onBuySingle={() => { setPurchaseError(null); setModalOpen("single"); }}
          onBuyPack20={() => { setPurchaseError(null); setModalOpen("pack20"); }}
          busy={busyAction === "single" ? "single" : busyAction === "pack20" ? "pack20" : null}
        />
      )}

      {founderTierEnabled && !isActive && (
        <section style={{
          border: "1px solid #ddd",
          borderRadius: 6,
          padding: 16,
          background: "#fff",
          marginBottom: 16,
        }}>
          <h2 style={{ margin: "0 0 8px 0", fontSize: 16 }}>
            {m.status === "cancelled" ? "Reactivate membership" : "Activate Founding membership"}
          </h2>
          <p style={{ color: "#555", fontSize: 13, marginTop: 0 }}>
            {m.status === "cancelled"
              ? `Reactivation pays the full price ($${m.next_price.toFixed(2)}). Founding price lock is forfeited.`
              : `Locked at $${m.next_price.toFixed(2)} for the life of your membership. Cancellation forfeits the lock permanently.`}
          </p>
          <label style={{ display: "block", fontSize: 13, marginBottom: 8 }}>
            <input
              type="checkbox"
              checked={accept}
              onChange={(e) => setAccept(e.target.checked)}
              style={{ marginRight: 6 }}
            />
            I understand the price-lock terms.
          </label>
          <button
            onClick={() => void onActivate()}
            disabled={!accept || busyAction === "activate"}
          >
            {busyAction === "activate" ? "Activating…" : "Activate"}
          </button>
        </section>
      )}

      {isActive && (
        <section style={{
          border: "1px solid #ddd",
          borderRadius: 6,
          padding: 16,
          background: "#fff",
          marginBottom: 16,
        }}>
          <h2 style={{ margin: "0 0 8px 0", fontSize: 16 }}>Cancel</h2>
          <p style={{ color: "#555", fontSize: 13, marginTop: 0 }}>
            Cancellation forfeits the $50 price lock permanently. You can come
            back later but reactivation costs $150.
          </p>
          <button
            onClick={() => void onCancel()}
            disabled={busyAction === "cancel"}
            style={{ background: "#fee", color: "#922", borderColor: "#f99" }}
          >
            {busyAction === "cancel" ? "Cancelling…" : "Cancel membership"}
          </button>
        </section>
      )}

      <BillingHistoryPanel />

      <PurchaseCreditsModal
        open={modalOpen !== null}
        pack={modalOpen}
        onConfirm={() => void confirmPurchase()}
        onCancel={() => setModalOpen(null)}
        busy={busyAction === "single" || busyAction === "pack20"}
        error={purchaseError}
      />

      <PaymentModal
        open={pendingIntent !== null}
        intent={pendingIntent}
        onConfirm={() => void onPaymentConfirm()}
        onCancel={() => { setPendingIntent(null); setPaymentError(null); }}
        busy={paymentBusy}
        error={paymentError}
      />
    </div>
  );
}
