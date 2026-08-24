// Operator welcome module — the cream center + identity/continuity rail.
//
// CT-1 spec 2026-08-24. Palette is carried verbatim from the live
// pro-mediations front-page `.cos` card. It is SCOPED to `.cos-mod`
// rather than tokens.css :root — the cockpit is dark by tokens and this
// is one cream module inside it, the same way the WP theme scopes
// `.pm-enter`.
//
// `color-scheme: light` is re-declared on the module because tokens.css
// :root now sets `color-scheme: dark` globally (A4); without the scoped
// re-declaration every native control inside the cream panel renders
// dark-on-cream.
//
// No new endpoints. Every read here already backs a shipped surface:
//   getProfile()            — the same values /account renders
//   listOperatorSessions()  — /session/history
//   getSessionDetail()      — /session/history
//   getOperatorVault()      — /operator-vault

import { useEffect, useState } from "react";
import {
  getProfile,
  getOperatorVault,
  getSessionDetail,
  listOperatorSessions,
  type SessionHistoryEntry,
} from "../../lib/api";

const MODES = ["query", "action", "plan", "diagnostic"] as const;
type Mode = (typeof MODES)[number];

interface Continuity {
  sessionId: string | null;
  steps: number;
  lastIntent: string | null;
  vaultKeys: number | null;
  recent: SessionHistoryEntry[];
}

const COLD: Continuity = {
  sessionId: null, steps: 0, lastIntent: null, vaultKeys: null, recent: [],
};

function fmtRenewal(epoch: number | null | undefined): string {
  if (!epoch) return "—";
  try { return new Date(epoch * 1000).toISOString().slice(0, 10); }
  catch { return "—"; }
}

export default function OperatorWelcome() {
  const profile = getProfile();
  const [cont, setCont] = useState<Continuity>(COLD);
  const [loaded, setLoaded] = useState(false);
  const [mode, setMode] = useState<Mode>("query");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const list = await listOperatorSessions();
        const sessions = [...(list.sessions ?? [])]
          .filter((s) => s.timestamp)
          .sort((a, b) => b.timestamp.localeCompare(a.timestamp));
        const newest = sessions[0];
        if (!newest) { if (alive) setLoaded(true); return; }

        const detail = await getSessionDetail(newest.session_id);
        // B2 / board #53 — NEWEST ON TOP. The wire order is oldest-first.
        const recent = [...(detail.session_state?.history ?? [])].reverse();

        let vaultKeys: number | null = null;
        try {
          const v = await getOperatorVault();
          vaultKeys = v.vault ? Object.keys(v.vault).length : 0;
        } catch { vaultKeys = null; }

        if (!alive) return;
        setCont({
          sessionId: newest.session_id,
          steps: newest.history_len ?? recent.length,
          lastIntent: recent[0]?.intent_type ?? null,
          vaultKeys,
          recent: recent.slice(0, 4),
        });
        setLoaded(true);
      } catch {
        if (alive) setLoaded(true);
      }
    })();
    return () => { alive = false; };
  }, []);

  const cold = loaded && !cont.sessionId;

  return (
    <section className="cos-mod">
      <style>{`
        .cos-mod{
          --cos-shell:#F4F1EA; --cos-ink:#111111; --cos-mute:#5A5750;
          --cos-line:#D8D3C8; --cos-focus:#00F0FF;
          color-scheme: light;
          background:var(--cos-shell); color:var(--cos-ink);
          display:grid; grid-template-columns:minmax(0,1fr) 320px; gap:20px;
          padding:28px; border-radius:6px; margin-bottom:20px;
          font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;
        }
        .cos-mod *{box-sizing:border-box;}
        .cos-mod .cos-panel{
          background:#FFFFFF; border:1px solid rgba(17,17,17,.07);
          border-radius:6px; padding:22px 24px;
        }
        .cos-mod .cos-panel + .cos-panel{margin-top:14px;}
        .cos-mod h2{margin:0 0 12px; font-size:1.6rem; font-weight:600;
          letter-spacing:-.02em; line-height:1.15; color:var(--cos-ink);}
        .cos-mod h3{margin:0 0 14px; font-size:.72rem; font-weight:600;
          letter-spacing:.09em; text-transform:uppercase; color:var(--cos-mute);}
        .cos-mod p{margin:0 0 14px; font-size:.95rem; line-height:1.65; color:var(--cos-mute);}
        .cos-mod ol{margin:0; padding:0; list-style:none; counter-reset:s;}
        .cos-mod ol li{position:relative; counter-increment:s; padding-left:2rem;
          margin-bottom:.85rem; font-size:.95rem; line-height:1.6; color:var(--cos-mute);}
        .cos-mod ol li::before{content:counter(s); position:absolute; left:0; top:0;
          font-size:.72rem; font-weight:600; letter-spacing:.06em; color:var(--cos-ink);
          border-bottom:2px solid var(--cos-focus); padding-bottom:1px;}
        .cos-mod .cos-row{display:flex; justify-content:space-between;
          gap:12px; padding:7px 0; border-bottom:1px solid var(--cos-line);}
        .cos-mod .cos-row:last-child{border-bottom:0;}
        .cos-mod .cos-k{font-size:.66rem; letter-spacing:.07em;
          text-transform:uppercase; color:var(--cos-mute); white-space:nowrap;}
        .cos-mod .cos-v{font-size:.86rem; color:var(--cos-ink);
          text-align:right; overflow-wrap:anywhere;}
        .cos-mod .cos-modes{display:flex; flex-wrap:wrap; gap:8px;}
        .cos-mod .cos-mode{
          flex:1 1 auto; padding:.55rem .6rem; border:1px solid var(--cos-line);
          border-radius:6px; background:transparent; color:var(--cos-mute);
          font-family:inherit; font-size:.72rem; font-weight:600;
          letter-spacing:.06em; text-transform:uppercase; cursor:pointer;
        }
        .cos-mod .cos-mode[aria-pressed="true"]{
          background:var(--cos-focus); color:#000000; border-color:var(--cos-focus);
        }
        .cos-mod .cos-mode:focus-visible{outline:2px solid #000; outline-offset:2px;}
        .cos-mod .cos-step{padding:7px 0; border-bottom:1px solid var(--cos-line);}
        .cos-mod .cos-step:last-child{border-bottom:0;}
        .cos-mod .cos-step-h{font-size:.62rem; letter-spacing:.07em;
          text-transform:uppercase; color:var(--cos-mute); margin-bottom:2px;}
        .cos-mod .cos-step-t{font-size:.84rem; color:var(--cos-ink);
          overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
        @media (max-width:900px){ .cos-mod{grid-template-columns:minmax(0,1fr);} }
      `}</style>

      {/* CENTER — template language, no data */}
      <div className="cos-panel">
        <h2>Welcome to ClarityOS</h2>
        <p>
          A deterministic operating system for operators. Everything you do here
          is a <strong>step</strong>: you state an intent, the runtime evaluates it,
          and the result is written to your continuity vault so the next step
          starts where this one ended.
        </p>
        <h3>How the system works</h3>
        <ol>
          <li>Pick a <strong>mode</strong>. It tells the runtime what kind of step this is.</li>
          <li>State the step. The runtime evaluates it and records the decision.</li>
          <li>The vault carries what mattered forward, so context is not re-typed.</li>
          <li>History is yours to read at any time — every step, timestamped.</li>
        </ol>
        <p style={{ marginBottom: 0 }}>
          Nothing here is a feed. There is no algorithm deciding what you see next.
        </p>
      </div>

      {/* RIGHT — identity · continuity · environment · mode */}
      <div>
        <div className="cos-panel">
          <h3>Who you are</h3>
          <div className="cos-row"><span className="cos-k">Email</span><span className="cos-v">{profile?.user ?? "—"}</span></div>
          <div className="cos-row"><span className="cos-k">Operator</span><span className="cos-v">{profile?.operator_id ?? "—"}</span></div>
          <div className="cos-row"><span className="cos-k">Tier</span><span className="cos-v">{profile?.tier ?? "—"}</span></div>
          <div className="cos-row"><span className="cos-k">Cohort</span><span className="cos-v">{profile?.cohort ?? "—"}</span></div>
          <div className="cos-row"><span className="cos-k">Renewal</span><span className="cos-v">{fmtRenewal(profile?.billing_expires_at)}</span></div>
        </div>

        <div className="cos-panel">
          <h3>Where you left off</h3>
          {!loaded && <p style={{ margin: 0 }}>Reading your last session…</p>}
          {cold && <p style={{ margin: 0 }}>You haven&rsquo;t taken a step yet.</p>}
          {loaded && !cold && (
            <>
              <div className="cos-row"><span className="cos-k">Steps</span><span className="cos-v">{cont.steps}</span></div>
              <div className="cos-row"><span className="cos-k">Last intent</span><span className="cos-v">{cont.lastIntent ?? "—"}</span></div>
              <div className="cos-row"><span className="cos-k">Vault keys</span><span className="cos-v">{cont.vaultKeys ?? "—"}</span></div>
              {cont.recent.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  {cont.recent.map((h, i) => (
                    <div className="cos-step" key={`${h.timestamp}-${i}`}>
                      <div className="cos-step-h">{h.timestamp.slice(0, 16).replace("T", " ")} · {h.intent_type}</div>
                      <div className="cos-step-t">{h.text}</div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        <div className="cos-panel">
          <h3>Environment</h3>
          <p style={{ margin: 0 }}>
            Your steps run against the ClarityOS runtime. Model selection,
            provider health and local-model status are reported on their own
            surfaces in the rail.
          </p>
        </div>

        <div className="cos-panel">
          <h3>Mode</h3>
          <div className="cos-modes" role="group" aria-label="Step mode">
            {MODES.map((m) => (
              <button
                key={m}
                type="button"
                className="cos-mode"
                aria-pressed={mode === m}
                onClick={() => setMode(m)}
              >
                {m}
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
