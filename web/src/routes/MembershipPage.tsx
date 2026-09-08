// routes/MembershipPage.tsx — Founding cohort + #G credits page (v31) and,
// since #145 / #141, the member's ACCOUNT: the terms, a password, the model
// preference and sign-out live here. /plans and /account redirect to this
// page; the two routes are gone.
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
// flag. The activate flow creates a PaymentIntent and surfaces the
// confirmation modal; in mock auto-confirm mode the side-effect lands
// inline so the modal closes immediately.
//
// ★ The ACCOUNT block below the membership body is NOT behind the flag: a
// member whose membership UI is off still has a password to set and a way
// out. /account never gated on it either.

import { useState, useSyncExternalStore, type CSSProperties } from "react";
import { useFlags } from "../hooks/useFlags";
import { useMembership } from "../hooks/useMembership";
import { signOut, getAuthSnapshot, subscribeAuth } from "../lib/auth";
import { cohortWord } from "../lib/cohortWord";
import MembershipStatusCard from "../components/membership/MembershipStatusCard";
import RenewalStatusCard from "../components/membership/RenewalStatusCard";
import GCreditsPanel from "../components/membership/GCreditsPanel";
import PurchaseCreditsModal from "../components/membership/PurchaseCreditsModal";
import PaymentModal from "../components/membership/PaymentModal";
import BillingHistoryPanel from "../components/membership/BillingHistoryPanel";
import SetPasswordPanel from "../components/settings/SetPasswordPanel";
import ModelPreferences from "../components/settings/ModelPreferences";
import LocalModelPanel from "../components/settings/LocalModelPanel";
import KernelFacts from "../components/settings/KernelFacts";
import MemoryVaultPanel from "../components/settings/MemoryVaultPanel";
import type { MembershipStateView, PaymentIntentView } from "../lib/api";

export default function MembershipPage() {
  return (
    <div className="membership" style={{ maxWidth: 720 }}>
      <h1>Membership</h1>
      <MembershipBody />
      <AccountBlock />
    </div>
  );
}

function MembershipBody() {
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
    return <p style={{ color: "#666" }}>Loading…</p>;
  }

  if (!uiEnabled) {
    return (
      <p style={{ color: "#666" }} data-testid="membership-disabled">
        Membership is not enabled for your account yet. Contact an admin to
        opt in.
      </p>
    );
  }

  if (error) {
    return (
      <div style={{
        padding: 12,
        background: "#fee",
        border: "1px solid #f99",
        marginBottom: 12,
      }}>
        {error}
        <button onClick={() => void refresh()} style={{ marginLeft: 8 }}>Retry</button>
      </div>
    );
  }

  if (!state) {
    return <p style={{ color: "#666" }}>No membership state available.</p>;
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
    <>
      <MembershipStatusCard state={state} />

      <RenewalStatusCard
        state={state}
        onUpdatePaymentMethod={undefined /* placeholder until v32 */}
      />

      {/* #187 -- the words render for every member; the flag disables the
          buy action only. */}
      <GCreditsPanel
        state={state}
        onBuySingle={() => { setPurchaseError(null); setModalOpen("single"); }}
        onBuyPack20={() => { setPurchaseError(null); setModalOpen("pack20"); }}
        busy={busyAction === "single" ? "single" : busyAction === "pack20" ? "pack20" : null}
        buyEnabled={gCreditsEnabled}
      />

      {/* #183 -- the homeless panels, housed: the envelope kv, the one tier
          card, the billing + cap panel. Words and numbers the page already
          holds (state, the profile); no new component. */}
      <HomelessPanels state={state} />

      {founderTierEnabled && !isActive && (
        <section style={sectionStyle}>
          <h2 style={h2Style}>
            {m.status === "cancelled" ? "Reactivate membership" : "Activate Founding membership"}
          </h2>
          <p style={pStyle}>
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
        <section style={sectionStyle}>
          <h2 style={h2Style}>Cancel</h2>
          <p style={pStyle}>
            Cancellation forfeits the $50 price lock permanently. You can come
            back later but reactivation costs $150.
          </p>
          <button
            onClick={() => void onCancel()}
            disabled={busyAction === "cancel"}
            style={dangerButtonStyle}
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
    </>
  );
}

// #183 -- the three panels /account and /plans left homeless at #141, now
// housed on /membership. Envelope kv (who: the address, the word, the
// operator id, billing expiry), the ONE tier card (one membership exists,
// CT-1 09-04), the billing + cap panel (state · renewal · retries · the
// cohort's fill). A missing value reads "—"; a false reads its word.
function fmtDay(ts: number | null | undefined): string {
  if (typeof ts !== "number" || !Number.isFinite(ts) || ts <= 0) return "—";
  const ms = ts > 1e11 ? ts : ts * 1000;
  try {
    return new Date(ms).toISOString().slice(0, 10);
  } catch {
    return "—";   // a stamp outside Date's range (a nanosecond value, say) is absent, not a crash
  }
}

function HomelessPanels({ state }: { state: MembershipStateView }) {
  const auth = useSyncExternalStore(subscribeAuth, getAuthSnapshot, getAuthSnapshot);
  const p = auth.profile;
  const m = state.membership;
  const b = state.billing;
  const c = state.cohort;
  const kvStyle: CSSProperties = { display: "grid", gridTemplateColumns: "max-content 1fr", gap: "4px 12px", fontSize: 13 };
  const k: CSSProperties = { color: "#666" };
  return (
    <>
      <section style={sectionStyle} data-testid="membership-envelope">
        <h2 style={h2Style}>Envelope</h2>
        <div style={kvStyle} title="profile.user · profile.member_number · profile.controller · profile.operator_id · profile.billing_expires_at">
          <span style={k}>user</span><span>{p?.user ?? "—"}</span>
          <span style={k}>word</span><span>{cohortWord(p)}</span>
          <span style={k}>operator</span><span style={{ fontFamily: "var(--font-mono, monospace)" }}>{p?.operator_id ?? "—"}</span>
          <span style={k}>billing expires</span><span>{fmtDay(p?.billing_expires_at)}</span>
        </div>
      </section>
      <section style={sectionStyle} data-testid="membership-tier">
        <h2 style={h2Style}>Tier</h2>
        <div style={kvStyle} title="membership.tier · membership.status · membership.price_locked · membership.next_price · membership.price_lock_forfeit">
          <span style={k}>tier</span><span>{m.tier ?? "—"}</span>
          <span style={k}>status</span><span>{m.status ?? "—"}</span>
          <span style={k}>price locked</span><span>{typeof m.price_locked === "number" ? `$${m.price_locked.toFixed(2)}` : "—"}</span>
          <span style={k}>next price</span><span>{typeof m.next_price === "number" ? `$${m.next_price.toFixed(2)}` : "—"}</span>
          <span style={k}>lock forfeit</span><span>{m.price_lock_forfeit === true ? "true" : m.price_lock_forfeit === false ? "false" : "—"}</span>
        </div>
      </section>
      <section style={sectionStyle} data-testid="membership-billing-cap">
        <h2 style={h2Style}>Billing and cap</h2>
        <div style={kvStyle} title="billing.state · billing.renewal_ts · billing.renewal_retry_count · billing.next_amount · cohort.active_count · cohort.cap · cohort.remaining · cohort.waitlist_count · cohort.is_full">
          <span style={k}>billing</span><span>{b.state ?? "—"}</span>
          <span style={k}>renewal</span><span>{fmtDay(b.renewal_ts)}</span>
          <span style={k}>retries</span><span>{typeof b.renewal_retry_count === "number" ? b.renewal_retry_count : "—"}</span>
          <span style={k}>next amount</span><span>{typeof b.next_amount === "number" ? `$${b.next_amount.toFixed(2)}` : "—"}</span>
          <span style={k}>cap</span><span>{typeof c.active_count === "number" ? c.active_count : "—"} of {c.cap ?? "—"} seated · {c.remaining ?? "—"} remaining · {typeof c.waitlist_count === "number" ? c.waitlist_count : "—"} waiting · {c.is_full === true ? "full" : c.is_full === false ? "open" : "—"}</span>
        </div>
      </section>
    </>
  );
}

// #145 / #141 -- THE ACCOUNT, folded from /account and /plans: the terms
// (#162's copy, the one paragraph /plans still had a reason for), a
// password (pen ruling 2026-08-12), the model preference, the member's own
// memory-vault notes and local-model panels (their only surface; a member
// keeps them), and sign-out. NOT carried: Account's envelope kv (user /
// cohort / operator id / billing expires -- the topbar and the status card
// carry the member's identity), its billing badge (RenewalStatusCard above
// is the renewal), the System link (the admin's page now); Plans' tier
// cards and the /config state panel (one membership exists, CT-1 09-04,
// and the status card shows the cohort fill).
function AccountBlock() {
  return (
    <>
      <section style={sectionStyle} data-testid="membership-terms">
        <h2 style={h2Style}>What you pay for</h2>
        {/* #162 (f) -- CT-1 ruled 09-04: one membership, $50 recurring until
            cancelled; the price lock stays until CT-1 removes it. No one-time
            path exists and none is sold here. */}
        <p style={pStyle} data-testid="plans-terms">
          One membership: $50 a month, recurring until you cancel. Your price
          stays locked for as long as your membership stands.
        </p>
      </section>

      <SetPasswordPanel />

      <ModelPreferences />

      {/* #180b (3) -- /me's kernel facts on the member's own page: the
          welcome card the order named is the admin's since #145. */}
      <KernelFacts />

      <LocalModelPanel />

      <MemoryVaultPanel />

      <section style={sectionStyle}>
        <h2 style={h2Style}>Sign out</h2>
        <p style={pStyle}>
          Clears the session token from this browser. Local Vault items are preserved.
        </p>
        <button
          type="button"
          onClick={signOut}
          style={dangerButtonStyle}
          data-testid="membership-signout"
        >
          Sign out
        </button>
      </section>
    </>
  );
}

const sectionStyle: React.CSSProperties = {
  border: "1px solid #ddd",
  borderRadius: 6,
  padding: 16,
  background: "#fff",
  marginBottom: 16,
};
const h2Style: React.CSSProperties = { margin: "0 0 8px 0", fontSize: 16 };
const pStyle: React.CSSProperties = { color: "#555", fontSize: 13, marginTop: 0 };
const dangerButtonStyle: React.CSSProperties = { background: "#fee", color: "#922", borderColor: "#f99" };
