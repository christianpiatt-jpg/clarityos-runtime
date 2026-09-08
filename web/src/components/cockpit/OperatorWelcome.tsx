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

import { cohortWord } from "../../lib/cohortWord";
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

// #180b (3) -- /me's kernel block on the card: a value as it came, the dash
// when the server did not send one. A boolean renders its word.
const DASH = "—";
function val(v: unknown): string {
  if (v === null || v === undefined) return DASH;
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "number") return Number.isFinite(v) ? String(v) : DASH;
  return String(v) || DASH;
}
function fmtMs(ms: unknown): string {
  if (typeof ms !== "number" || !Number.isFinite(ms) || ms <= 0) return DASH;
  try { return new Date(ms).toISOString().replace("T", " ").slice(0, 16) + "Z"; }
  catch { return DASH; }
}

export default function OperatorWelcome() {
  const profile = getProfile();
  const kernel = profile?.intelligence_kernel ?? null;
  const caps = profile?.capabilities ?? [];
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
        <div className="cos-panel" data-testid="who-you-are">
          <h3>Who you are</h3>
          <div className="cos-row" title="user"><span className="cos-k">Email</span><span className="cos-v">{profile?.user ?? "—"}</span></div>
          <div className="cos-row" title="operator_id"><span className="cos-k">Operator</span><span className="cos-v">{profile?.operator_id ?? "—"}</span></div>
          <div className="cos-row" title="tier"><span className="cos-k">Tier</span><span className="cos-v">{profile?.tier ?? "—"}</span></div>
          {/* #171 -- the one word the surface has: citizen / admin / nothing */}
          <div className="cos-row" title="cohort · member_number · paid · controller · citz_id"><span className="cos-k">Cohort</span><span className="cos-v">{cohortWord(profile)}</span></div>
          <div className="cos-row" title="billing_expires_at"><span className="cos-k">Renewal</span><span className="cos-v">{fmtRenewal(profile?.billing_expires_at)}</span></div>
          {/* #180b (3) -- vault_ready as a word; absent = the server did not say */}
          <div className="cos-row" title="vault_ready"><span className="cos-k">Vault</span><span className="cos-v" data-testid="vault-ready">{profile?.vault_ready === true ? "ready" : profile?.vault_ready === false ? "not ready" : DASH}</span></div>
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

        {/* #180b (3) -- /me's intelligence_kernel block, one row per key; the
            two top-level copies (external_signal_mode, eso_source) share a
            row with the kernel's. */}
        <div className="cos-panel" data-testid="environment">
          <h3>Environment</h3>
          {([
            ["Last model", kernel?.last_model_used, "intelligence_kernel.last_model_used"],
            ["Kernel", kernel?.version, "intelligence_kernel.version"],
            ["Threads", kernel?.thread_count, "intelligence_kernel.thread_count"],
            ["Notes", kernel?.notes_count, "intelligence_kernel.notes_count"],
            ["Embeddings", kernel?.embeddings_count, "intelligence_kernel.embeddings_count"],
            ["Vault keys", kernel?.vault_keys, "intelligence_kernel.vault_keys"],
            ["Signal mode", kernel?.external_signal_mode ?? profile?.external_signal_mode, "intelligence_kernel.external_signal_mode · external_signal_mode"],
            ["ESO source", kernel?.eso_source ?? profile?.eso_source, "intelligence_kernel.eso_source · eso_source"],
            ["Preferred model", kernel?.preferred_model, "intelligence_kernel.preferred_model"],
            ["Local model uses", kernel?.local_model_usage_count, "intelligence_kernel.local_model_usage_count"],
          ] as Array<[string, unknown, string]>).map(([k, v, path]) => (
            <div className="cos-row" key={path} title={path} data-testid={`env-${path.split(" ")[0].split(".").pop()}`}>
              <span className="cos-k">{k}</span><span className="cos-v">{val(v)}</span>
            </div>
          ))}
          <div className="cos-row" title="intelligence_kernel.last_thread_updated_at" data-testid="env-last_thread_updated_at">
            <span className="cos-k">Last thread</span><span className="cos-v">{fmtMs(kernel?.last_thread_updated_at)}</span>
          </div>
        </div>

        {/* #180b (3) -- capabilities[] as the server lists them. Every route
            listed on 2026-09-08 exists in app.py (all 19 checked by decorator);
            the route rides in the title, the label is the text. */}
        <div className="cos-panel" data-testid="capabilities">
          <h3>What you can call</h3>
          {caps.length === 0 ? (
            <p style={{ margin: 0 }}>{DASH}</p>
          ) : caps.map((c) => (
            <div className="cos-row" key={c.id} title={`capabilities[].id ${c.id} · capabilities[].route ${c.route}`} data-testid={`cap-${c.id}`}>
              <span className="cos-k" title="capabilities[].label">{c.label}</span>
              <span className="cos-v">{c.route}</span>
            </div>
          ))}
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
