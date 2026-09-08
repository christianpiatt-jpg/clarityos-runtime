// components/membership/RenewalStatusCard.tsx — billing state + renewal date.
//
// Renders the v31 billing-state machine fields (state, renewal_ts, retry
// count, grace window).
//
// #180b (1) -- ALWAYS RENDERED. This card used to return null when
// billing.state was null, and the five billing keys died with it. A
// founder-seated membership DOES carry a billing state (app.py
// _founder_seat_membership sets "active" + a renewal_ts); null is the
// reader who never went through either seating path. Now: "next charge
// $50.00 on <date>" always, the state as a badge or a dash, retry and
// grace only when non-null.

import type { MembershipStateView, V31BillingState } from "../../lib/api";

const DASH = "—";

function fmtUsd(n: number | null | undefined): string {
  if (typeof n !== "number" || !Number.isFinite(n)) return DASH;
  return `$${n.toFixed(2)}`;
}

function fmtDate(ts: number | null | undefined): string {
  if (!ts) return DASH;
  try { return new Date(Number(ts) * 1000).toISOString().slice(0, 10); }
  catch { return String(ts); }
}

function fmtRelative(ts: number | null | undefined): string {
  if (!ts) return DASH;
  const now = Date.now() / 1000;
  const days = (Number(ts) - now) / 86400;
  if (days < -1) return `${Math.round(-days)} days ago`;
  if (days < 1) return "today";
  return `in ${Math.round(days)} day${Math.round(days) === 1 ? "" : "s"}`;
}

const STATE_LABELS: Record<NonNullable<V31BillingState>, { text: string; bg: string; fg: string; explain: string }> = {
  active: {
    text: "ACTIVE",
    bg: "#e6f5ec", fg: "#147",
    explain: "Paid up. Auto-renews on the date shown.",
  },
  past_due: {
    text: "PAST DUE",
    bg: "#fff4e0", fg: "#a55",
    explain: "Last renewal failed. We'll retry up to 3 times over the next 72 hours.",
  },
  grace_period: {
    text: "GRACE PERIOD",
    bg: "#fff4e0", fg: "#a55",
    explain: "All retries failed. Update your payment method before the grace window ends or your membership will be cancelled.",
  },
  cancelled: {
    text: "CANCELLED",
    bg: "#fde2e2", fg: "#922",
    explain: "Membership ended. Reactivate from the panel above.",
  },
  failed: {
    text: "FAILED",
    bg: "#fde2e2", fg: "#922",
    explain: "Activation payment never completed. Try again or contact support.",
  },
};

interface Props {
  state: MembershipStateView;
  onUpdatePaymentMethod?: () => void;
}

export default function RenewalStatusCard({ state, onUpdatePaymentMethod }: Props) {
  const billing = (state.billing ?? {}) as Partial<MembershipStateView["billing"]>;
  const st = billing.state ?? null;
  const meta = st ? STATE_LABELS[st] : null;
  const retry = typeof billing.renewal_retry_count === "number" ? billing.renewal_retry_count : null;
  const grace = typeof billing.renewal_grace_until_ts === "number" ? billing.renewal_grace_until_ts : null;
  const renewal = typeof billing.renewal_ts === "number" ? billing.renewal_ts : null;

  return (
    <section style={{
      border: "1px solid #ddd",
      borderRadius: 6,
      padding: 16,
      background: "#fff",
      marginBottom: 16,
    }} data-testid="renewal-card">
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "baseline",
        marginBottom: 8,
      }}>
        <h2 style={{ margin: 0, fontSize: 18 }}>Renewal</h2>
        <span
          data-testid="billing-state"
          title="state.billing.state"
          style={{
            padding: "2px 8px",
            background: meta ? meta.bg : "#eee",
            color: meta ? meta.fg : "#555",
            borderRadius: 3,
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: "0.05em",
          }}
        >
          {meta ? meta.text : DASH}
        </span>
      </div>

      <p
        data-testid="next-charge"
        title="state.billing.next_amount · state.billing.renewal_ts"
        style={{ margin: "0 0 8px 0", fontSize: 13 }}
      >
        next charge <strong>{fmtUsd(billing.next_amount)}</strong> on {fmtDate(renewal)}
        {renewal ? <span style={{ color: "#888", fontSize: 12 }}> ({fmtRelative(renewal)})</span> : null}
      </p>

      <div style={{
        display: "grid",
        gridTemplateColumns: "auto 1fr",
        gap: "4px 16px",
        fontSize: 13,
      }}>
        {retry !== null && (
          <>
            <span style={{ color: "#666" }} title="state.billing.renewal_retry_count">Retry attempts</span>
            <span data-testid="billing-retry">{retry} / 3</span>
          </>
        )}

        {grace !== null && (
          <>
            <span style={{ color: "#666" }} title="state.billing.renewal_grace_until_ts">Grace ends</span>
            <span data-testid="billing-grace">{fmtDate(grace)}</span>
          </>
        )}
      </div>

      {meta ? (
        <p style={{ marginTop: 8, marginBottom: 0, color: "#555", fontSize: 12 }}>
          {meta.explain}
        </p>
      ) : (
        <p style={{ marginTop: 8, marginBottom: 0, color: "#555", fontSize: 12 }} data-testid="billing-none">
          No billing state on record. Nothing is scheduled.
        </p>
      )}

      {(st === "past_due" || st === "grace_period") && (
        <div style={{ marginTop: 8 }}>
          <button onClick={onUpdatePaymentMethod} disabled={!onUpdatePaymentMethod}>
            Update payment method
          </button>
          <span style={{ color: "#888", fontSize: 11, marginLeft: 6 }}>
            (placeholder — Stripe-backed flow ships in a later pass)
          </span>
        </div>
      )}
    </section>
  );
}
