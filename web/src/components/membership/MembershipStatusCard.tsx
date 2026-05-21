// components/membership/MembershipStatusCard.tsx — header strip showing
// the user's tier, locked price, status, started/cancelled timestamps.

import type { MembershipStateView } from "../../lib/api";

function fmtUsd(n: number | null | undefined): string {
  if (typeof n !== "number") return "—";
  return `$${n.toFixed(2)}`;
}

function fmtTs(ts: number | null | undefined): string {
  if (!ts) return "—";
  try { return new Date(Number(ts) * 1000).toISOString().slice(0, 10); }
  catch { return String(ts); }
}

interface Props {
  state: MembershipStateView;
}

export default function MembershipStatusCard({ state }: Props) {
  const m = state.membership;
  const c = state.cohort;
  const isActive = m.status === "active";
  const isCancelled = m.status === "cancelled";
  const isNonMember = !m.status;

  let badge: { text: string; bg: string; fg: string };
  if (isActive) badge = { text: "ACTIVE", bg: "#e6f5ec", fg: "#147" };
  else if (isCancelled) badge = { text: "CANCELLED", bg: "#fde2e2", fg: "#922" };
  else badge = { text: "NOT JOINED", bg: "#eef", fg: "#447" };

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
        <h2 style={{ margin: 0, fontSize: 18 }}>
          {m.tier === "founding_500" ? "Founding 500" : "Membership"}
        </h2>
        <span style={{
          padding: "2px 8px",
          background: badge.bg,
          color: badge.fg,
          borderRadius: 3,
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: "0.05em",
        }}>
          {badge.text}
        </span>
      </div>

      <div style={{
        display: "grid",
        gridTemplateColumns: "auto 1fr",
        gap: "4px 16px",
        fontSize: 13,
      }}>
        <span style={{ color: "#666" }}>Locked price</span>
        <strong>{fmtUsd(m.price_locked)}</strong>

        <span style={{ color: "#666" }}>Next price</span>
        <strong>{fmtUsd(m.next_price)}</strong>

        <span style={{ color: "#666" }}>Started</span>
        <span>{fmtTs(m.started_ts)}</span>

        {isCancelled && (
          <>
            <span style={{ color: "#666" }}>Cancelled</span>
            <span>{fmtTs(m.cancelled_ts)}</span>
          </>
        )}

        <span style={{ color: "#666" }}>Cohort fill</span>
        <span>
          {c.active_count} / {c.cap ?? "—"}
          {c.is_full && (
            <span style={{ color: "#922", marginLeft: 6, fontSize: 11 }}>
              (full — waitlist)
            </span>
          )}
        </span>

        {state.waitlist_position !== null && state.waitlist_position !== undefined && (
          <>
            <span style={{ color: "#666" }}>Waitlist position</span>
            <strong>#{state.waitlist_position}</strong>
          </>
        )}
      </div>

      {isCancelled && (
        <div style={{
          marginTop: 12,
          padding: 8,
          background: "#fff8e1",
          border: "1px solid #f3d57a",
          fontSize: 12,
          borderRadius: 4,
        }}>
          Reactivation will pay the full price ({fmtUsd(m.next_price)}).
          Founding-cohort price lock is forfeited on cancellation.
        </div>
      )}

      {isNonMember && !c.is_full && (
        <div style={{
          marginTop: 12,
          padding: 8,
          background: "#eef",
          fontSize: 12,
          borderRadius: 4,
        }}>
          Join the Founding 500 cohort for {fmtUsd(m.next_price)} (locked for life of membership).
        </div>
      )}

      {isNonMember && c.is_full && (
        <div style={{
          marginTop: 12,
          padding: 8,
          background: "#fee",
          fontSize: 12,
          borderRadius: 4,
        }}>
          The Founding 500 cohort is full. You'll be added to the waitlist.
        </div>
      )}
    </section>
  );
}
