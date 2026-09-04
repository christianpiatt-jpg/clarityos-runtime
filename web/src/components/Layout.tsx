import { cohortWord } from "../lib/cohortWord";
import { useEffect, useState, useSyncExternalStore } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import {
  getAuthSnapshot,
  signOut,
  subscribeAuth,
  syncProfile,
} from "../lib/auth";
import { probeBackend, type BackendStatus, type Profile } from "../lib/api";
import { getResumeOptions } from "../lib/continuity";
import { APP_CONFIG } from "../lib/config";
import { isController } from "./RequireAdmin";

/**
 * Cockpit shell — top bar / left rail / main pane / status bar.
 *
 * The status bar surfaces three live cells:
 *   • SID  — first 8 chars of the active session token
 *   • MQC  — Markov QC indicator (last result, set by /markov route)
 *   • CONT — count of pending resume options (continuity)
 *   • API  — backend reachability (from probeBackend)
 *
 * All state lives outside this component (auth store, localStorage, in-memory
 * Markov last-call). The bar just reads it.
 */

// MQC last-call slot. Set by Markov route on each successful call.
//
// Critical (same gotcha as the auth store): getMqcSnapshot must return a
// STABLE reference between updates. We hold a single object and only
// reassign it when pushMarkovScore fires, so React's useSyncExternalStore
// doesn't see a "change" on every render and infinite-loop.
type MqcSnapshot = { score: number | null; at: number | null };
let mqcSnapshot: MqcSnapshot = { score: null, at: null };
const mqcListeners = new Set<() => void>();

export function pushMarkovScore(score: number): void {
  mqcSnapshot = { score, at: Date.now() };
  for (const l of mqcListeners) l();
}

function subscribeMqc(fn: () => void): () => void {
  mqcListeners.add(fn);
  return () => { mqcListeners.delete(fn); };
}

function getMqcSnapshot(): MqcSnapshot {
  return mqcSnapshot;
}

// ---------- Auth subscription via useSyncExternalStore ----------
function useAuth() {
  return useSyncExternalStore(subscribeAuth, getAuthSnapshot, getAuthSnapshot);
}

function useMqc() {
  return useSyncExternalStore(subscribeMqc, getMqcSnapshot, getMqcSnapshot);
}

// ---------- Layout ----------
export default function Layout() {
  const auth = useAuth();
  const mqc = useMqc();
  const [backend, setBackend] = useState<BackendStatus | null>(null);
  const [resumeCount, setResumeCount] = useState(0);
  const location = useLocation();
  // #145 -- the one flag. /me.controller (RequireAdmin.isController, the
  // same predicate the route gate reads). A null profile -- the load
  // window, a signed-out visitor, a member -- fails closed to the member
  // rail. The route table is what keeps a typed URL out; the backend is
  // the boundary.
  const admin = isController(auth.profile);

  // Probe backend at mount.
  useEffect(() => {
    let cancelled = false;
    probeBackend().then((s) => { if (!cancelled) setBackend(s); });
    return () => { cancelled = true; };
  }, []);

  // Pull /me if we have a session and the backend is reachable. Fire once
  // per backend-status change so logging in elsewhere refreshes the cell.
  useEffect(() => {
    if (auth.session && backend?.reachable && !auth.profile) {
      syncProfile().catch(() => { /* handled inside */ });
    }
  }, [auth.session, auth.profile, backend?.reachable]);

  // Continuity count — re-read on every navigation so saving from /vault
  // updates the bar.
  useEffect(() => {
    setResumeCount(getResumeOptions().length);
  }, [location.pathname]);

  return (
    <div className="cockpit">
      <header className="topbar">
        <Link to={auth.session ? "/cockpit" : "/"} className="brand">
          <span className="brand-icon">▲</span>
          <span>ClarityOS</span>
        </Link>
        <div className="topbar-right">
          {APP_CONFIG.IS_PLACEHOLDER && (
            <span style={{ color: "var(--os-warn)" }}>API URL: PLACEHOLDER</span>
          )}
          {auth.session ? (
            <>
              <span>{auth.user ?? auth.profile?.user ?? "OPERATOR"}</span>
              <button className="btn btn-sm btn-secondary" onClick={signOut}>SIGN OUT</button>
            </>
          ) : (
            <Link to="/login" className="btn btn-sm">SIGN IN</Link>
          )}
        </div>
      </header>

      <nav className="rail">
        {/* #145 -- TWO RAILS, ONE FLAG. CT-1 RULED 09-04: the MEMBER rail
            is the member's own stores and the door out -- Cockpit · Library
            · Vault · Timeline · Membership · Sign out -- and nothing else.
            Everything else is the OPERATOR rail, one group, rendered only
            for the controller. /plans and /account fold into /membership
            (#141); /threads is /cockpit (#144); neither is a link any more.
            Sign out is the same call the topbar makes. */}
        <RailSection label="MEMBER">
          <RailLink to="/cockpit">Cockpit</RailLink>
          <RailLink to="/library">Library</RailLink>
          <RailLink to="/vault">Vault</RailLink>
          <RailLink to="/timeline">Timeline</RailLink>
          <RailLink to="/membership">Membership</RailLink>
          {auth.session ? (
            <Link to="/" onClick={signOut} data-testid="rail-signout">Sign out</Link>
          ) : null}
        </RailSection>
        {admin ? (
          <RailSection label="OPERATOR">
            <RailLink to="/founder">Founder console</RailLink>
            <RailLink to="/dashboard">Dashboard</RailLink>
            <RailLink to="/elins">EL/INS Overview</RailLink>
            <RailLink to="/operator">Operator</RailLink>
            <RailLink to="/sessions">Sessions</RailLink>
            <RailLink to="/continuity">Continuity</RailLink>
            <RailLink to="/markov">Markov QC</RailLink>
            <RailLink to="/system">System</RailLink>
            <RailLink to="/session">Session</RailLink>
            <RailLink to="/session/history">History</RailLink>
            {/* #34 -- one thing is called Vault (the member's store above);
                the runtime inspector is the Runtime Vault. Path unchanged. */}
            <RailLink to="/operator-vault">Runtime Vault</RailLink>
            <RailLink to="/model-preferences">Model</RailLink>
            <RailLink to="/provider-health">Provider Health</RailLink>
            <RailLink to="/operator/providers">Providers</RailLink>
            <RailLink to="/operator/timeline">Operator Timeline</RailLink>
            <RailLink to="/org/el_ins/timeline">Org Timeline</RailLink>
            <RailLink to="/operator/el_ins">EL/INS</RailLink>
            <RailLink to="/operator/el_ins/macro">EL/INS Macro</RailLink>
            <RailLink to="/operator/el_ins/dashboard">EL/INS Dashboard</RailLink>
            <RailLink to="/operator/el_ins/export">EL/INS Export</RailLink>
            <RailLink to="/operator/el_ins/anomalies">EL/INS Anomalies</RailLink>
            <RailLink to="/operator/el_ins/rollup">EL/INS Roll-Up</RailLink>
            <RailLink to="/iframe">Iframe</RailLink>
          </RailSection>
        ) : null}
      </nav>

      <main className="main">
        <Outlet />
      </main>

      <footer className="status">
        <StatusCell
          label="SID"
          value={auth.session ? auth.session.slice(0, 8) + "…" : "—"}
          tone={auth.session ? "ok" : "idle"}
        />
        <StatusCell
          label="COHORT"
          value={cohortLabel(auth.profile)}
          tone={auth.profile?.cohort ? "ok" : "idle"}
        />
        <StatusCell
          label="MQC"
          value={mqc.score !== null ? mqc.score.toFixed(2) : "—"}
          tone={mqc.score !== null ? "ok" : "idle"}
        />
        <StatusCell
          label="CONT"
          value={resumeCount > 0 ? `${resumeCount} pending` : "clear"}
          tone={resumeCount > 0 ? "warn" : "ok"}
        />
        <StatusCell
          label="API"
          value={backend?.reachable ? `OK · ${backend.version || "?"}` : backend === null ? "probing…" : "DOWN"}
          tone={backend?.reachable ? "ok" : backend === null ? "idle" : "err"}
        />
      </footer>
    </div>
  );
}

// #171 -- the footer says the one word the surface has for a member
// (citizen · admin · nothing) and, when numbered, the citizen id. The
// derived label and the legacy strings no longer reach the surface. The
// derived label "controller" and the legacy strings founder /
// founder_exception / admin all read as admin (the strings for one
// deploy, #157).
function cohortLabel(profile: Profile | null): string {
  if (!profile) return "—";
  const id = profile.citz_id ? ` ${profile.citz_id}` : "";
  const legacyAdmin = profile.cohort === "controller" || profile.cohort === "founder"
    || profile.cohort === "founder_exception" || profile.cohort === "admin";
  const word = cohortWord({ member_number: profile.member_number, controller: !!profile.controller || legacyAdmin });
  return word === "—" ? (id ? id.trim() : "—") : word + id;
}

// ---------- Rail bits ----------
function RailSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="rail-section">
        <div className="rail-section-label">{label}</div>
      </div>
      <div>{children}</div>
      <div style={{ height: "var(--gap-lg)" }} />
    </div>
  );
}

function RailLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink to={to} className={({ isActive }) => (isActive ? "active" : "")}>
      {children}
    </NavLink>
  );
}

// ---------- Status cell ----------
function StatusCell({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "ok" | "warn" | "err" | "idle";
}) {
  return (
    <div className="status-cell">
      <span className={`status-dot ${tone}`} />
      <span className="dim">{label}</span>
      <span>{value}</span>
    </div>
  );
}
