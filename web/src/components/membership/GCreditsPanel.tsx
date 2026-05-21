// components/membership/GCreditsPanel.tsx — balance + buy buttons +
// recent activity tail (last few decrements/purchases).

import type { MembershipStateView } from "../../lib/api";

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
  onBuySingle: () => void;
  onBuyPack20: () => void;
  busy?: string | null;
}

export default function GCreditsPanel({ state, onBuySingle, onBuyPack20, busy }: Props) {
  const balance = state.g_credits?.balance ?? 0;
  const tail = (state.g_credits?.history_tail ?? []).slice(-5).reverse();

  return (
    <section style={{
      border: "1px solid #ddd",
      borderRadius: 6,
      padding: 16,
      background: "#fff",
      marginBottom: 16,
    }}>
      <h2 style={{ margin: "0 0 8px 0", fontSize: 18 }}>#G credits</h2>

      <div style={{ fontSize: 36, fontWeight: 600, marginBottom: 8 }}>
        {balance}
      </div>
      <div style={{ color: "#666", fontSize: 12, marginBottom: 12 }}>
        One credit = one #G run. Credits never expire.
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button
          onClick={onBuySingle}
          disabled={busy === "single"}
          style={{ flex: 1, padding: "8px 12px" }}
        >
          {busy === "single" ? "Charging…" : "Buy 1 credit (" + fmtUsd(1.0) + ")"}
        </button>
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
                <th style={{ textAlign: "right" }}>Δ</th>
                <th style={{ textAlign: "right" }}>$</th>
              </tr>
            </thead>
            <tbody>
              {tail.map((t, i) => (
                <tr key={i}>
                  <td>{fmtTs(t.ts)}</td>
                  <td>{t.type}</td>
                  <td style={{
                    textAlign: "right",
                    color: t.credits_delta < 0 ? "#922" : "#147",
                  }}>
                    {t.credits_delta > 0 ? "+" : ""}{t.credits_delta}
                  </td>
                  <td style={{ textAlign: "right" }}>{fmtUsd(t.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </section>
  );
}
