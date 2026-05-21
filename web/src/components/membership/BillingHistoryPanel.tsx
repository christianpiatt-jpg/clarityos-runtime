// components/membership/BillingHistoryPanel.tsx — combined transaction
// + intent history. Reads /billing/history.

import { useCallback, useEffect, useState } from "react";
import { billingHistory, type BillingHistoryIntent, type MembershipTransaction } from "../../lib/api";

function fmtUsd(n: number | null | undefined): string {
  if (typeof n !== "number") return "—";
  return `$${n.toFixed(2)}`;
}

function fmtTs(ts: number | null | undefined): string {
  if (!ts) return "—";
  try { return new Date(Number(ts) * 1000).toISOString().slice(0, 16).replace("T", " "); }
  catch { return String(ts); }
}

const TX_LABELS: Record<string, string> = {
  membership_activation: "Membership activation",
  membership_renewal: "Membership renewal",
  membership_cancel: "Membership cancelled",
  g_credit_single: "Credit (single)",
  g_credit_pack: "Credit (20-pack)",
  g_consume: "Credit consumed",
  failed_payment: "Failed payment",
  refund: "Refund",
};

const STATUS_COLORS: Record<string, { bg: string; fg: string }> = {
  succeeded: { bg: "#e6f5ec", fg: "#147" },
  failed: { bg: "#fde2e2", fg: "#922" },
  canceled: { bg: "#eee", fg: "#888" },
  processing: { bg: "#eef", fg: "#447" },
  requires_payment_method: { bg: "#fff8e1", fg: "#a55" },
  requires_action: { bg: "#fff8e1", fg: "#a55" },
};

export default function BillingHistoryPanel() {
  const [transactions, setTransactions] = useState<MembershipTransaction[]>([]);
  const [intents, setIntents] = useState<BillingHistoryIntent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await billingHistory(100);
      setTransactions(r.transactions);
      setIntents(r.intents);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  return (
    <section style={{
      border: "1px solid #ddd",
      borderRadius: 6,
      padding: 16,
      background: "#fff",
      marginBottom: 16,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <h2 style={{ margin: 0, fontSize: 18 }}>Billing history</h2>
        <button onClick={() => void refresh()} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {error && (
        <div style={{
          padding: 8,
          background: "#fee",
          border: "1px solid #f99",
          fontSize: 12,
          borderRadius: 4,
          marginBottom: 8,
        }}>
          {error}
        </div>
      )}

      <h3 style={{ fontSize: 14, marginTop: 8, marginBottom: 4 }}>Transactions</h3>
      {transactions.length === 0 ? (
        <div style={{ color: "#888", fontSize: 12 }}>No transactions yet.</div>
      ) : (
        <table style={{ width: "100%", fontSize: 12 }}>
          <thead style={{ color: "#888" }}>
            <tr>
              <th style={{ textAlign: "left" }}>When</th>
              <th style={{ textAlign: "left" }}>Type</th>
              <th style={{ textAlign: "right" }}>Δ credits</th>
              <th style={{ textAlign: "right" }}>$</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((t, i) => (
              <tr key={i}>
                <td>{fmtTs(t.ts)}</td>
                <td>{TX_LABELS[t.type] ?? t.type}</td>
                <td style={{
                  textAlign: "right",
                  color: t.credits_delta < 0 ? "#922" : t.credits_delta > 0 ? "#147" : "#888",
                }}>
                  {t.credits_delta > 0 ? "+" : ""}{t.credits_delta || "—"}
                </td>
                <td style={{ textAlign: "right" }}>{fmtUsd(t.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3 style={{ fontSize: 14, marginTop: 16, marginBottom: 4 }}>Payment intents</h3>
      {intents.length === 0 ? (
        <div style={{ color: "#888", fontSize: 12 }}>No payment intents yet.</div>
      ) : (
        <table style={{ width: "100%", fontSize: 12 }}>
          <thead style={{ color: "#888" }}>
            <tr>
              <th style={{ textAlign: "left" }}>Created</th>
              <th style={{ textAlign: "left" }}>Kind</th>
              <th style={{ textAlign: "left" }}>Status</th>
              <th style={{ textAlign: "right" }}>$</th>
            </tr>
          </thead>
          <tbody>
            {intents.map((i) => {
              const sc = STATUS_COLORS[i.status] ?? { bg: "#eee", fg: "#444" };
              return (
                <tr key={i.intent_id}>
                  <td>{fmtTs(i.created_ts)}</td>
                  <td>{i.kind}</td>
                  <td>
                    <span style={{
                      padding: "1px 6px",
                      background: sc.bg,
                      color: sc.fg,
                      borderRadius: 3,
                      fontSize: 11,
                    }}>
                      {i.status}
                    </span>
                  </td>
                  <td style={{ textAlign: "right" }}>{fmtUsd(i.amount)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}
