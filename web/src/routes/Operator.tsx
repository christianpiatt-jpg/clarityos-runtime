// Operator panel — admin-only invite minting + envelope info.
//
// Backend coupling: GET /me, GET /config, POST /invite/create.
// All other "operator" data (cohort, billing, Terrace-1 cap) comes
// from /me + /config. No new endpoints.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  config,
  createInvite,
  getProfile,
  type Cohort,
  type ConfigResponse,
  type InviteCreated,
} from "../lib/api";
import { syncProfile } from "../lib/auth";

const RECENT_INVITES_KEY = "clarityos.recent_invites";

interface RecentInvite extends InviteCreated {
  created_at_local: number;
}

function loadRecent(): RecentInvite[] {
  try { return JSON.parse(localStorage.getItem(RECENT_INVITES_KEY) || "[]"); }
  catch { return []; }
}
function saveRecent(list: RecentInvite[]): void {
  try { localStorage.setItem(RECENT_INVITES_KEY, JSON.stringify(list.slice(0, 50))); }
  catch { /* noop */ }
}

export default function Operator() {
  const [cfg, setCfg] = useState<ConfigResponse["data"] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [minting, setMinting] = useState<Cohort | null>(null);
  const [recent, setRecent] = useState<RecentInvite[]>(loadRecent());
  const profile = getProfile();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        if (!profile) await syncProfile();
        const c = await config();
        if (!cancelled) setCfg(c.data);
      } catch (e: any) {
        if (!cancelled) setError(e?.message || "Could not load runtime config");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [profile]);

  const isAdmin = profile?.cohort === "founder";

  async function mint(cohort: Cohort) {
    if (minting) return;
    setMinting(cohort);
    setError(null);
    try {
      const r = await createInvite(cohort as "founder_exception" | "terrace_1");
      const next = [{ ...r, created_at_local: Date.now() }, ...recent];
      setRecent(next);
      saveRecent(next);
    } catch (e: any) {
      const msg = e instanceof ApiError ? e.message : (e?.message || "Mint failed");
      setError(msg);
    } finally {
      setMinting(null);
    }
  }

  function copyToClipboard(text: string) {
    navigator.clipboard?.writeText(text).catch(() => { /* user can copy manually */ });
  }

  function clearRecent() {
    setRecent([]);
    saveRecent([]);
  }

  if (loading) return <div className="panel"><span className="spinner" /> Loading operator panel…</div>;

  return (
    <div>
      <div className="panel">
        <h1>OPERATOR</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Mint invites and inspect the operator envelope. Founder-only tools.
        </p>
      </div>

      {error ? <div className="banner err">{error}</div> : null}

      {/* Envelope */}
      <div className="panel">
        <h2>ENVELOPE</h2>
        <div className="kv">
          <div className="k">user</div>
          <div className="v">{profile?.user || "—"}</div>
          <div className="k">cohort</div>
          <div className="v">{profile?.cohort || "—"}</div>
          <div className="k">operator id</div>
          <div className="v">{profile?.operator_id || "—"}</div>
          <div className="k">tier</div>
          <div className="v">{profile?.tier || "—"}</div>
          <div className="k">billing expires</div>
          <div className="v">
            {profile?.billing_expires_at
              ? new Date(profile.billing_expires_at * 1000).toLocaleString()
              : "—"}
          </div>
        </div>
      </div>

      {/* Terrace-1 cap */}
      {cfg ? (
        <div className="panel">
          <h2>TERRACE-1</h2>
          <div className="kv">
            <div className="k">redeemed</div>
            <div className="v">
              {cfg.terrace_1_redeemed ?? 0} / {cfg.terrace_1_cap ?? 500}
            </div>
            <div className="k">invite-only mode</div>
            <div className="v">{cfg.invite_only ? "ON" : "off"}</div>
            <div className="k">stripe configured</div>
            <div className="v">{cfg.billing_configured ? "yes" : "no (free invites only)"}</div>
          </div>
        </div>
      ) : null}

      {/* Mint */}
      <div className="panel">
        <h2>MINT INVITE</h2>
        {!isAdmin ? (
          <div className="banner warn">
            You're signed in as <span className="mono">{profile?.user || "—"}</span> with cohort{" "}
            <span className="mono">{profile?.cohort || "none"}</span>. Founder-only.
            The backend will return 403 on mint attempts.
          </div>
        ) : null}
        <div className="row">
          <button
            className="btn"
            onClick={() => mint("founder_exception" as Cohort)}
            disabled={!isAdmin || minting !== null}
          >
            {minting === "founder_exception" ? <span className="spinner" /> : "FOUNDER EXCEPTION  ·  free"}
          </button>
          <button
            className="btn"
            onClick={() => mint("terrace_1" as Cohort)}
            disabled={!isAdmin || minting !== null}
          >
            {minting === "terrace_1" ? <span className="spinner" /> : "TERRACE-1  ·  $50"}
          </button>
        </div>
        <p className="muted" style={{ fontSize: "0.8rem", marginTop: 12 }}>
          Each click mints exactly one single-use invite. Copy the URL and send it to the recipient.
          Tokens expire in 7 days.
        </p>
      </div>

      {/* Recent */}
      <div className="panel">
        <div className="row row-between" style={{ marginBottom: 12 }}>
          <h2 style={{ margin: 0 }}>RECENT INVITES</h2>
          {recent.length > 0 ? (
            <button className="btn btn-sm btn-secondary" onClick={clearRecent}>
              CLEAR LOCAL HISTORY
            </button>
          ) : null}
        </div>
        {recent.length === 0 ? (
          <div className="empty">No invites minted from this browser yet.</div>
        ) : (
          recent.map((inv) => (
            <div key={inv.invite_id} className="list-item" style={{ cursor: "default" }}>
              <div className="row row-between">
                <div>
                  <span className={`tag ${inv.cohort === "terrace_1" ? "cyan" : "red"}`}>
                    {inv.cohort}
                  </span>
                  <span className="mono dim">{inv.invite_id}</span>
                </div>
                <div className="dim mono" style={{ fontSize: "0.75rem" }}>
                  {new Date(inv.created_at_local).toLocaleString()}
                </div>
              </div>
              <pre className="output" style={{ marginTop: 8, fontSize: "0.75rem" }}>{inv.url}</pre>
              <div className="row" style={{ marginTop: 8 }}>
                <button
                  className="btn btn-sm btn-secondary"
                  onClick={() => copyToClipboard(inv.url)}
                >
                  COPY URL
                </button>
                <span className="dim" style={{ fontSize: "0.75rem" }}>
                  expires {new Date(inv.expires_at * 1000).toLocaleString()}
                </span>
              </div>
            </div>
          ))
        )}
      </div>

      <p className="muted" style={{ fontSize: "0.8rem" }}>
        Don't see your envelope? <Link to="/system">Check System</Link> for backend health.
      </p>
    </div>
  );
}
