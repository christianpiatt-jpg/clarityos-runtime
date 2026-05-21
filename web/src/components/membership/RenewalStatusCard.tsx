// components/membership/RenewalStatusCard.tsx — billing state + renewal date.
//
// Renders the v31 billing-state machine fields (state, renewal_ts, retry
// count, grace window). Hidden when no membership state to render.

import type { MembershipStateView, V31BillingState } from "../../lib/api";

function fmtUsd(n: number | null | undefined): string {
  if (typeof n !== "number") return "—";
  return `$${n.toFixed(2)}`;
}

function fmtDate(ts: number | null | undefined): string {
  if (!ts) return "—";
  try { return new Date(Number(ts) * 1000).toISOString().slice(0, 10); }
  catch { return String(ts); }
}

function fmtRelative(ts: number | null | undefined): string {
  if (!ts) return "—";
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
  const billing = state.billing;
  if (!billing.state) return null;

  const meta = STATE_LABELS[billing.state];

  return (
    <section style={{
      border: "1px solid #ddd",
      borderRadius: 6,
      padding: 16,
      background: "#fff",
      marginBottom: 16,
    }}>
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "baseline",
        marginBottom: 8,
      }}>
        <h2 style={{ margin: 0, fontSize: 18 }}>Renewal</h2>
        <span style={{
          padding: "2px 8px",
          background: meta.bg,
          color: meta.fg,
          borderRadius: 3,
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: "0.05em",
        }}>
          {meta.text}
        </span>
      </div>

      <div style={{
        display: "grid",
        gridTemplateColumns: "auto 1fr",
        gap: "4px 16px",
        fontSize: 13,
      }}>
        <span style={{ color: "#666" }}>Next renewal</span>
        <span>
          {fmtDate(billing.renewal_ts)}{" "}
          <span style={{ color: "#888", fontSize: 12 }}>({fmtRelative(billing.renewal_ts)})</span>
        </span>

        <span style={{ color: "#666" }}>Next amount</span>
        <strong>{fmtUsd(billing.next_amount)}</strong>

        {billing.renewal_retry_count > 0 && (
          <>
            <span style={{ color: "#666" }}>Retry attempts</span>
            <span>{billing.renewal_retry_count} / 3</span>
          </>
        )}

        {billing.state === "grace_period" && (
          <>
            <span style={{ color: "#666" }}>Grace ends</span>
            <span>{fmtDate(billing.renewal_grace_until_ts)}</span>
          </>
        )}
      </div>

      <p style={{ marginTop: 8, marginBottom: 0, color: "#555", fontSize: 12 }}>
        {meta.explain}
      </p>

      {(billing.state === "past_due" || billing.state === "grace_period") && (
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
