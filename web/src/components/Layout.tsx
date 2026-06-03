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
        <Link to="/" className="brand">
          <span className="brand-icon">▲</span>
          <span>ClarityOS</span>
        </Link>
        <div className="topbar-right">
          {APP_CONFIG.IS_PLACEHOLDER && (
            <span style={{ color: "var(--os-warn)" }}>API URL: PLACEHOLDER</span>
          )}
          {auth.user ? (
            <>
              <span>{auth.user}</span>
              <button className="btn btn-sm btn-secondary" onClick={signOut}>SIGN OUT</button>
            </>
          ) : (
            <Link to="/login" className="btn btn-sm">SIGN IN</Link>
          )}
        </div>
      </header>

      <nav className="rail">
        <RailSection label="OPERATOR">
          <RailLink to="/operator">Operator</RailLink>
          <RailLink to="/sessions">Sessions</RailLink>
          <RailLink to="/continuity">Continuity</RailLink>
        </RailSection>
        <RailSection label="ENGINE">
          <RailLink to="/markov">Markov QC</RailLink>
          <RailLink to="/system">System</RailLink>
        </RailSection>
        <RailSection label="OPERATOR ENVELOPE">
          <RailLink to="/vault">Vault</RailLink>
          <RailLink to="/library">Library</RailLink>
          <RailLink to="/timeline">Timeline</RailLink>
          <RailLink to="/plans">Plans</RailLink>
          <RailLink to="/membership">Membership</RailLink>
          <RailLink to="/account">Account</RailLink>
        </RailSection>
        <RailSection label="CONVERSE">
          <RailLink to="/threads">Threads</RailLink>
        </RailSection>
        <RailSection label="RUNTIME">
          <RailLink to="/session">Session</RailLink>
          <RailLink to="/session/history">History</RailLink>
          <RailLink to="/operator-vault">Operator Vault</RailLink>
          <RailLink to="/model-preferences">Model</RailLink>
          <RailLink to="/provider-health">Provider Health</RailLink>
          <RailLink to="/operator/providers">Providers</RailLink>
          <RailLink to="/operator/timeline">Operator Timeline</RailLink>
          <RailLink to="/org/el_ins/timeline">Org Timeline</RailLink>
        </RailSection>
        <RailSection label="EXECUTION LAYER">
          <RailLink to="/operator/el_ins">EL/INS</RailLink>
          <RailLink to="/operator/el_ins/macro">EL/INS Macro</RailLink>
          <RailLink to="/operator/el_ins/dashboard">EL/INS Dashboard</RailLink>
          <RailLink to="/operator/el_ins/export">EL/INS Export</RailLink>
          <RailLink to="/operator/el_ins/anomalies">EL/INS Anomalies</RailLink>
          <RailLink to="/operator/el_ins/rollup">EL/INS Roll-Up</RailLink>
        </RailSection>
        <RailSection label="BRIDGES">
          <RailLink to="/iframe">Iframe</RailLink>
        </RailSection>
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

function cohortLabel(profile: Profile | null): string {
  if (!profile) return "—";
  if (!profile.cohort) return "—";
  if (profile.cohort === "founder") return "FOUNDER";
  if (profile.cohort === "founder_exception") return "FOUNDER·EXC";
  if (profile.cohort === "terrace_1") return "T-1";
  return profile.cohort;
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
