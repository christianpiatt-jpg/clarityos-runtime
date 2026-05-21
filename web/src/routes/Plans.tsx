import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { config, getProfile, type ConfigResponse, type Profile } from "../lib/api";
import { syncProfile } from "../lib/auth";

const TIERS = [
  {
    cohort: "founder_exception",
    label: "FOUNDER EXCEPTION",
    price: "Free for life",
    bullets: [
      "Full operator envelope",
      "All engines, all interpreters",
      "Vault + continuity",
      "By invite, capped",
    ],
  },
  {
    cohort: "terrace_1",
    label: "TERRACE-1",
    price: "$50",
    sub: "monthly recurring or one-time (30 days)",
    bullets: [
      "All engines, all interpreters",
      "Vault + continuity",
      "Operator envelope",
      "500-seat cap; one-time-paid expires permanently",
    ],
    featured: true,
  },
] as const;

export default function Plans() {
  const [cfg, setCfg] = useState<ConfigResponse["data"] | null>(null);
  const [profile, setProfile] = useState<Profile | null>(getProfile());

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await config();
        if (!cancelled) setCfg(r.data);
      } catch { /* page works without /config */ }
      try {
        const p = await syncProfile();
        if (!cancelled) setProfile(p);
      } catch { /* unauth users skip */ }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div>
      <div className="panel">
        <h1>PLANS</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          ClarityOS access tiers. Founder cohort is invite-only.
        </p>
        {profile?.cohort ? (
          <p className="mono" style={{ marginTop: 8, color: "var(--os-focus)" }}>
            current: {profile.cohort}
          </p>
        ) : null}
      </div>

      {cfg ? (
        <div className="panel">
          <h2>TERRACE-1 STATE</h2>
          <div className="kv">
            <div className="k">cap</div>
            <div className="v">{cfg.terrace_1_cap ?? 500}</div>
            <div className="k">redeemed</div>
            <div className="v">{cfg.terrace_1_redeemed ?? 0}</div>
            <div className="k">remaining</div>
            <div className="v">{(cfg.terrace_1_cap ?? 500) - (cfg.terrace_1_redeemed ?? 0)}</div>
            <div className="k">billing system</div>
            <div className="v">{cfg.billing_configured ? "online" : "offline (free invites only)"}</div>
          </div>
        </div>
      ) : null}

      <div className="panel-grid">
        {TIERS.map((t) => (
          <div
            key={t.cohort}
            className="panel"
            style={{
              marginBottom: 0,
              borderColor:
                profile?.cohort === t.cohort
                  ? "var(--os-focus)"
                  : (t as any).featured
                  ? "var(--os-line-strong)"
                  : "var(--os-line)",
            }}
          >
            <h2>{t.label}</h2>
            <div className="mono" style={{ fontSize: "1.6rem", margin: "12px 0" }}>{t.price}</div>
            {(t as any).sub ? (
              <div className="dim" style={{ fontSize: "0.85rem", marginBottom: 12 }}>{(t as any).sub}</div>
            ) : null}
            <ul style={{ listStyle: "none", padding: 0, margin: "0 0 16px" }}>
              {t.bullets.map((b, i) => (
                <li key={i} style={{ padding: "4px 0", color: "var(--os-text-secondary)", fontSize: "0.9rem" }}>
                  → {b}
                </li>
              ))}
            </ul>
            {profile?.cohort === t.cohort ? (
              <div className="banner ok">CURRENT TIER</div>
            ) : (
              <Link to="/login" className="btn btn-block">
                {t.cohort === "founder_exception" ? "Founder access by invite" : "Upgrade by invite"}
              </Link>
            )}
          </div>
        ))}
      </div>

      <div className="panel">
        <h2>WHAT YOU PAY FOR</h2>
        <p className="muted">
          Compute meters by calls to the engine routes (markov / galileo / tizzy / library).
          Vault is local; nothing is billed for storage today.
        </p>
      </div>
    </div>
  );
}
