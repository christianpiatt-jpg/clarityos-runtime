// components/membership/MeBillingBadge.tsx
// v42 — small inline badge for the Account / Settings surface that
// reflects the user's billing state + Stripe mode.

import { useCallback, useEffect, useState } from "react";
import { meBilling, type V42MeBilling } from "../../lib/api";

export default function MeBillingBadge() {
  const [data, setData] = useState<V42MeBilling | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const r = await meBilling();
      setData(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (error) {
    return <span style={mutedStyle}>billing unavailable</span>;
  }
  if (!data) {
    return <span style={mutedStyle}>checking…</span>;
  }
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <StatusPill status={data.status} />
      <ModePill mode={data.mode} />
      {data.renewal_ts ? (
        <span style={renewalStyle}>
          renews {new Date(data.renewal_ts * 1000).toISOString().slice(0, 10)}
        </span>
      ) : null}
      {!data.billing_enabled && (
        <span style={disabledNoticeStyle}>
          Billing temporarily unavailable
        </span>
      )}
    </span>
  );
}

function StatusPill({ status }: { status: V42MeBilling["status"] }) {
  const palette: Record<string, [string, string]> = {
    active:    ["#15803d", "#fff"],
    past_due:  ["#b45309", "#fff"],
    canceled:  ["#6b7280", "#fff"],
    none:      ["#374151", "#fff"],
  };
  const [bg, fg] = palette[status] || palette.none;
  return (
    <span style={{
      ...pillBaseStyle,
      background: bg, color: fg,
    }}>{status}</span>
  );
}

function ModePill({ mode }: { mode: V42MeBilling["mode"] }) {
  const palette: Record<string, [string, string]> = {
    live:     ["#dc2626", "#fff"],
    test:     ["#2563eb", "#fff"],
    disabled: ["#374151", "#fff"],
  };
  const [bg, fg] = palette[mode] || palette.disabled;
  return (
    <span style={{
      ...pillBaseStyle,
      background: bg, color: fg, fontFamily: "var(--font-mono, monospace)",
    }}>{mode.toUpperCase()}</span>
  );
}

const pillBaseStyle: React.CSSProperties = {
  fontSize: 10, fontWeight: 700, letterSpacing: 0.4,
  padding: "2px 8px", borderRadius: "var(--radius-pill, 999px)",
};
const mutedStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--os-text-tertiary, #585858)",
};
const renewalStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--os-text-secondary, #A0A0A0)",
  fontFamily: "var(--font-mono, monospace)",
};
const disabledNoticeStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--os-boundary, #E02020)",
  marginLeft: 4,
};
