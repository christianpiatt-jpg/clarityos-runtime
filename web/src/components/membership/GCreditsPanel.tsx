// components/membership/GCreditsPanel.tsx — balance + buy buttons +
// recent activity tail (last few decrements/purchases).

import type { MembershipStateView } from "../../lib/api";
import { fmtDelta, microToDollars } from "../../lib/money";

function fmtUsd(n: number | null | undefined): string {
  if (typeof n !== "number") return "—";
  return `$${n.toFixed(2)}`;
}

function fmtTs(ts: number | null | undefined): string {
  if (!ts) return "—";
  try { return new Date(Number(ts) * 1000).toISOString().slice(0, 16).replace("T", " "); }
  catch { return String(ts); }
}

interface Props {
  state: MembershipStateView;
  /** Kept for the page's call site; the $1 single SKU is RETIRED
   *  (billing_intents.RETIRED_KINDS) and no button fires it. */
  onBuySingle?: () => void;
  onBuyPack20: () => void;
  busy?: string | null;
}

export default function GCreditsPanel({ state, onBuyPack20, busy }: Props) {
  // #142 -- the big number is DOLLARS: balance_display from the API
  // ("unlimited" for the controller), the client formatter as the fallback
  // for a state that predates the field. Never the raw micro figure.
  const g = state.g_credits;
  const shown = g?.unlimited
    ? "unlimited"
    : (g?.balance_display ?? microToDollars(g?.balance_micro ?? g?.balance ?? 0));
  const tail = (g?.history_tail ?? []).slice(-5).reverse();

  return (
    <section style={{
      border: "1px solid #ddd",
      borderRadius: 6,
      padding: 16,
      background: "#fff",
      marginBottom: 16,
    }}>
      <h2 style={{ margin: "0 0 8px 0", fontSize: 18 }}>#G balance</h2>

      <div style={{ fontSize: 36, fontWeight: 600, marginBottom: 8 }} data-testid="g-balance">
        {shown}
      </div>
      <div style={{ color: "#666", fontSize: 12, marginBottom: 12 }}>
        $1.00 buys one #G run. Metered from this balance. Never expires.
      </div>

      {/* #142 -- one SKU. The $1 single is RETIRED on the backend (402
          bad_kind), so no button offers it. */}
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button
          onClick={onBuyPack20}
          disabled={busy === "pack20"}
          style={{ flex: 1, padding: "8px 12px" }}
        >
          {busy === "pack20" ? "Charging…" : "Buy 20-pack (" + fmtUsd(20.0) + ")"}
        </button>
      </div>

      {tail.length > 0 && (
        <details>
          <summary style={{ cursor: "pointer", fontSize: 12, color: "#555" }}>
            Recent activity ({tail.length})
          </summary>
          <table style={{ width: "100%", marginTop: 8, fontSize: 12 }}>
            <thead style={{ color: "#888" }}>
              <tr>
                <th style={{ textAlign: "left" }}>When</th>
                <th style={{ textAlign: "left" }}>Type</th>
                <th style={{ textAlign: "right" }}>Δ balance</th>
                <th style={{ textAlign: "right" }}>paid</th>
              </tr>
            </thead>
            <tbody>
              {tail.map((t, i) => {
                // #142/#155 -- the delta is MICRO on every producer's row:
                // credits_delta, or the meter's amount_micro. Shown in
                // dollars at $0.01. "paid" is the money that changed hands
                // (a purchase); a grant or a debit paid nothing.
                const micro = typeof t.credits_delta === "number" ? t.credits_delta
                  : typeof t.amount_micro === "number" ? t.amount_micro : null;
                const kind = t.type ?? t.kind ?? "\u2014";
                return (
                  <tr key={i} data-testid="g-history-row">
                    <td>{fmtTs(t.ts)}</td>
                    <td>{kind}</td>
                    <td
                      data-testid="g-history-delta"
                      style={{
                        textAlign: "right",
                        color: (micro ?? 0) < 0 ? "#922" : "#147",
                      }}
                    >
                      {fmtDelta(micro)}
                    </td>
                    <td style={{ textAlign: "right" }}>
                      {typeof t.amount === "number" && t.amount > 0 ? fmtUsd(t.amount) : "\u2014"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </details>
      )}
    </section>
  );
}
