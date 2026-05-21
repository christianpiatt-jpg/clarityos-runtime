// components/membership/PurchaseCreditsModal.tsx — small confirm dialog.
// Surfaces the price and a single OK/Cancel before charging.

import { useEffect } from "react";

interface Props {
  open: boolean;
  pack: "single" | "pack20" | null;
  onConfirm: () => void;
  onCancel: () => void;
  busy?: boolean;
  error?: string | null;
}

export default function PurchaseCreditsModal({
  open, pack, onConfirm, onCancel, busy, error,
}: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open || pack === null) return null;

  const label = pack === "single" ? "Buy 1 credit for $1.00" : "Buy 20-pack for $20.00";
  const detail = pack === "single"
    ? "One #G run. Credits never expire."
    : "Twenty #G runs. Credits never expire.";

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
          width: 360,
          maxWidth: "90vw",
        }}
      >
        <h2 style={{ margin: "0 0 8px 0", fontSize: 16 }}>{label}</h2>
        <p style={{ color: "#555", fontSize: 13, margin: "0 0 12px 0" }}>{detail}</p>
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
            {busy ? "Charging…" : "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}
