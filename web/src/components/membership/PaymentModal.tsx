// components/membership/PaymentModal.tsx — PaymentIntent confirmation dialog.
//
// In Stripe mode this would mount Stripe.js Elements; in mock mode the
// modal shows the intent metadata and a "Confirm" button that calls
// /billing/intent/confirm to fire the synthetic webhook. Either way the
// caller passes an intent + onConfirmed callback.

import { useEffect } from "react";
import type { PaymentIntentView } from "../../lib/api";

function fmtUsd(n: number | null | undefined): string {
  if (typeof n !== "number") return "—";
  return `$${n.toFixed(2)}`;
}

interface Props {
  open: boolean;
  intent: PaymentIntentView | null;
  onConfirm: () => void;
  onCancel: () => void;
  busy?: boolean;
  error?: string | null;
}

export default function PaymentModal({ open, intent, onConfirm, onCancel, busy, error }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open || !intent) return null;

  const isStripe = intent.mode === "stripe";

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.4)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div
        style={{
          background: "#fff",
          borderRadius: 6,
          padding: 16,
          width: 440,
          maxWidth: "90vw",
        }}
      >
        <h2 style={{ margin: "0 0 8px 0", fontSize: 16 }}>
          Confirm payment
        </h2>
        <div style={{
          display: "grid",
          gridTemplateColumns: "auto 1fr",
          gap: "4px 12px",
          fontSize: 13,
          marginBottom: 12,
        }}>
          <span style={{ color: "#666" }}>Amount</span>
          <strong>{fmtUsd(intent.amount)}</strong>
          <span style={{ color: "#666" }}>Kind</span>
          <code>{intent.kind}</code>
          <span style={{ color: "#666" }}>Mode</span>
          <span>{intent.mode}</span>
          <span style={{ color: "#666" }}>Intent</span>
          <code style={{ fontSize: 11 }}>{intent.intent_id}</code>
        </div>

        {isStripe ? (
          <div style={{
            padding: 8,
            background: "#fff8e1",
            border: "1px solid #f3d57a",
            fontSize: 12,
            borderRadius: 4,
            marginBottom: 8,
          }}>
            Stripe Elements would render here. The real client uses
            <code style={{ marginLeft: 4 }}>{intent.client_secret?.slice(0, 24) ?? "—"}…</code>
          </div>
        ) : (
          <div style={{
            padding: 8,
            background: "#eef",
            fontSize: 12,
            borderRadius: 4,
            marginBottom: 8,
          }}>
            Mock mode — confirming will fire a synthetic{" "}
            <code>payment_intent.succeeded</code> webhook.
          </div>
        )}

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

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button onClick={onCancel} disabled={busy}>Cancel</button>
          <button onClick={onConfirm} disabled={busy} style={{ fontWeight: 600 }}>
            {busy ? "Confirming…" : "Confirm payment"}
          </button>
        </div>
      </div>
    </div>
  );
}
