import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, getProfile, me, type MeResponse } from "../lib/api";
import { signOut } from "../lib/auth";
import MeBillingBadge from "../components/membership/MeBillingBadge";
import ModelPreferences from "../components/settings/ModelPreferences";
import LocalModelPanel from "../components/settings/LocalModelPanel";
import MemoryVaultPanel from "../components/settings/MemoryVaultPanel";

// A-WEB-CLARITY-3 §2 — presentation-only friendly names (UI mapping; no fetch,
// no backend). Maps the app's REAL categoricals: cohort (the meaningful one —
// Founding 500) and tier (currently only "free"). operator_id is a unique
// identifier, not a categorical, so it is shown raw — no table applies.
const COHORT_NAMES: Record<string, string> = {
  founder: "Founding 500",
  founder_exception: "Founding 500 (exception)",
};
const TIER_NAMES: Record<string, string> = {
  free: "Free Plan",
};
function friendly(map: Record<string, string>, raw: string | null | undefined): string {
  if (!raw) return "—";
  return map[raw] ?? `${raw} (raw)`;
}

export default function Account() {
  const [data, setData] = useState<MeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const cached = getProfile();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await me();
        if (!cancelled) setData(r);
      } catch (e: any) {
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : (e?.message || "Could not load /me"));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div>
      <div className="panel">
        <h1>ACCOUNT</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Your operator envelope as the backend sees it. Sign-out is below.
        </p>
      </div>

      {error ? <div className="banner err">{error}</div> : null}

      <div className="panel">
        <h2>ENVELOPE</h2>
        {loading && !cached ? (
          <div><span className="spinner" /> Loading /me…</div>
        ) : (
          <div className="kv">
            <div className="k">user</div>
            <div className="v">{data?.user || cached?.user || "—"}</div>
            <div className="k">cohort</div>
            <div className="v">{friendly(COHORT_NAMES, data?.cohort || cached?.cohort)}</div>
            <div className="k">operator id</div>
            <div className="v">{data?.operator_id || cached?.operator_id || "—"}</div>
            <div className="k">tier</div>
            <div className="v">{friendly(TIER_NAMES, data?.tier || cached?.tier)}</div>
            <div className="k">billing expires</div>
            <div className="v">
              {data?.billing_expires_at
                ? new Date(data.billing_expires_at * 1000).toLocaleString()
                : "—"}
            </div>
          </div>
        )}
      </div>

      <div className="panel">
        <h2>BILLING</h2>
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          Plan + renewal date come from the Stripe webhook log; never from
          a stored card or customer object.
        </p>
        <div style={{ marginTop: 8 }}>
          <MeBillingBadge />
        </div>
        <div style={{ marginTop: 12 }}>
          <Link className="btn btn-sm" to="/membership">View Membership</Link>
        </div>
      </div>

      <ModelPreferences />

      <LocalModelPanel />

      <MemoryVaultPanel />

      <div className="panel">
        <h2>SIGN OUT</h2>
        <p className="muted" style={{ marginBottom: 12, fontSize: "0.85rem" }}>
          Clears the session token from this browser. Local Vault items are preserved.
        </p>
        <button className="btn btn-danger" onClick={signOut}>SIGN OUT</button>
      </div>

      <p className="muted" style={{ fontSize: "0.8rem" }}>
        Need to swap the backend URL? <Link to="/system">System → API base override</Link>.
      </p>
    </div>
  );
}
