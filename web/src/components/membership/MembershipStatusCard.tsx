// components/membership/MembershipStatusCard.tsx — header strip showing
// the user's tier, locked price, status, started/cancelled timestamps.
//
// A-WEB-CLARITY-2: dark-theme aligned (operator palette via existing tokens;
// no layout/copy change) + explicit lifetime-lock badge. Status-badge colors
// match MeBillingBadge (active green / cancelled red / not-joined gray).

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

  // A-WEB-CLARITY-2 §2 — lifetime-lock indicator. price_locked is the locked
  // PRICE (number), not a boolean; the lock is live while the membership is
  // active, carries a locked price, and hasn't been forfeited.
  const showLock = isActive && typeof m.price_locked === "number" && !m.price_lock_forfeit;

  let badge: { text: string; bg: string; fg: string };
  if (isActive) badge = { text: "ACTIVE", bg: "#15803d", fg: "#fff" };
  else if (isCancelled) badge = { text: "CANCELLED", bg: "#dc2626", fg: "#fff" };
  else badge = { text: "NOT JOINED", bg: "#374151", fg: "#fff" };

  return (
    <section style={{
      border: "1px solid rgba(255,255,255,0.15)",
      borderRadius: 6,
      padding: 16,
      background: "var(--color-bg-surface, #0A0A0A)",
      color: "var(--color-text-primary, #fff)",
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
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {showLock && (
            <span style={{
              padding: "2px 8px",
              background: "rgba(0, 240, 255, 0.12)",
              color: "var(--color-accent-cyan, #00F0FF)",
              border: "1px solid var(--color-accent-cyan, #00F0FF)",
              borderRadius: 3,
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.05em",
            }}>
              LOCKED PRICE
            </span>
          )}
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
      </div>

      <div style={{
        display: "grid",
        gridTemplateColumns: "auto 1fr",
        gap: "4px 16px",
        fontSize: 13,
      }}>
        <span style={{ color: "var(--color-text-secondary, #888)" }}>Locked price</span>
        <strong>{fmtUsd(m.price_locked)}</strong>

        <span style={{ color: "var(--color-text-secondary, #888)" }}>Next price</span>
        <strong>{fmtUsd(m.next_price)}</strong>

        <span style={{ color: "var(--color-text-secondary, #888)" }}>Started</span>
        <span>{fmtTs(m.started_ts)}</span>

        {isCancelled && (
          <>
            <span style={{ color: "var(--color-text-secondary, #888)" }}>Cancelled</span>
            <span>{fmtTs(m.cancelled_ts)}</span>
          </>
        )}

        <span style={{ color: "var(--color-text-secondary, #888)" }}>Cohort fill</span>
        <span>
          {c.active_count} / {c.cap ?? "—"}
          {c.is_full && (
            <span style={{ color: "var(--color-accent-red, #E02020)", marginLeft: 6, fontSize: 11 }}>
              (full — waitlist)
            </span>
          )}
        </span>

        {state.waitlist_position !== null && state.waitlist_position !== undefined && (
          <>
            <span style={{ color: "var(--color-text-secondary, #888)" }}>Waitlist position</span>
            <strong>#{state.waitlist_position}</strong>
          </>
        )}
      </div>

      {isCancelled && (
        <div style={{
          marginTop: 12,
          padding: 8,
          background: "var(--color-bg-surface-alt, #111)",
          border: "1px solid #b45309",
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
          background: "var(--color-bg-surface-alt, #111)",
          border: "1px solid var(--color-accent-cyan, #00F0FF)",
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
          background: "var(--color-bg-surface-alt, #111)",
          border: "1px solid var(--color-accent-red, #E02020)",
          fontSize: 12,
          borderRadius: 4,
        }}>
          The Founding 500 cohort is full. You'll be added to the waitlist.
        </div>
      )}
    </section>
  );
}
