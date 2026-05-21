// ClarityOS desktop — top-level App. Decides whether to show the
// login screen or the chat shell based on session state.

import { useCallback, useEffect, useState } from "react";
import { ApiError, getSession, isAuthed, login, me } from "./lib/api";
import ChatWindow from "./ChatWindow";
import PersonalElinsShell from "./PersonalElinsShell";
import LibraryShell from "./LibraryShell";
import SessionShell from "./SessionShell";
import SessionHistoryShell from "./SessionHistoryShell";
import OperatorVaultShell from "./OperatorVaultShell";
import ModelPreferencesShell from "./ModelPreferencesShell";
import ProviderHealthShell from "./ProviderHealthShell";
import ProviderDashboardShell from "./ProviderDashboardShell";
import OperatorElinsShell from "./OperatorElinsShell";
import OperatorElinsMacroShell from "./OperatorElinsMacroShell";
import OperatorElinsDashboardShell from "./OperatorElinsDashboardShell";
import OperatorElinsExportShell from "./OperatorElinsExportShell";
import OperatorElinsAnomaliesShell from "./OperatorElinsAnomaliesShell";
import OperatorElinsRollupShell from "./OperatorElinsRollupShell";
import OperatorTimelineShell from "./OperatorTimelineShell";
import OrgTimelineShell from "./OrgTimelineShell";
import RegressionFirstShell from "./RegressionFirstShell";

type AuthState =
  | { kind: "probing" }
  | { kind: "signed_out"; error?: string }
  | { kind: "authed" };

// Desktop is single-window — no react-router. The view-switcher below
// is the lightest possible "routing" surface (single useState). Matches
// the brief's "Do NOT introduce new routing systems" constraint.
// v62 / Unit 45 — added "session" for the operator runtime UI.
// v63 / Units 47 + 48 — added "session-history" + "operator-vault".
// v64 / Unit 67 — added "model-preferences".
// v65 / Unit 69 — added "provider-health".
// v68 / Unit 73 — added "provider-dashboard" (unified health+models+config).
// v69 / Unit 74 — added "el-ins" + "el-ins-macro" surfaces.
// v70 / Unit 77 — added "el-ins-dashboard" unified surface.
// v71 / Unit 78 — added "el-ins-export" surface.
// v72 / Units 80+81 — added "el-ins-anomalies" + "el-ins-rollup" surfaces.
// v73 / Units 82+83 — added "timeline" + "org-timeline" surfaces.
type View =
  | "threads"
  | "personal-elins"
  | "library"
  | "session"
  | "session-history"
  | "operator-vault"
  | "model-preferences"
  | "provider-health"
  | "provider-dashboard"
  | "el-ins"
  | "el-ins-macro"
  | "el-ins-dashboard"
  | "el-ins-export"
  | "el-ins-anomalies"
  | "el-ins-rollup"
  | "timeline"
  | "org-timeline"
  | "regression-first";

export default function App() {
  const [auth, setAuth] = useState<AuthState>(
    isAuthed() ? { kind: "probing" } : { kind: "signed_out" },
  );
  const [view, setView] = useState<View>("threads");

  // On launch with a cached session, ping /me to validate. On 401/403
  // drop the cache; on network errors stay signed-in (transient).
  useEffect(() => {
    if (!getSession()) return;
    let cancelled = false;
    (async () => {
      try {
        await me();
        if (!cancelled) setAuth({ kind: "authed" });
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
          setAuth({ kind: "signed_out", error: "Session expired — sign in again." });
        } else {
          // Backend unreachable but we have a session token — stay
          // signed in optimistically; the chat surface will surface
          // the error itself when it fails to list threads.
          setAuth({ kind: "authed" });
        }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (auth.kind === "probing") {
    return (
      <div className="placeholder">
        <span>connecting…</span>
      </div>
    );
  }

  if (auth.kind === "signed_out") {
    return (
      <SignIn
        initialError={auth.error}
        onSignedIn={() => setAuth({ kind: "authed" })}
      />
    );
  }

  const handleNavigate = (label: string) => {
    if (label === "Threads") setView("threads");
    else if (label === "Personal ELINS") setView("personal-elins");
    else if (label === "Library") setView("library");
    else if (label === "Session") setView("session");
    else if (label === "History") setView("session-history");
    else if (label === "Operator Vault") setView("operator-vault");
    else if (label === "Model") setView("model-preferences");
    else if (label === "Provider Health") setView("provider-health");
    else if (label === "Providers") setView("provider-dashboard");
    else if (label === "EL/INS") setView("el-ins");
    else if (label === "EL/INS Macro") setView("el-ins-macro");
    else if (label === "EL/INS Dashboard") setView("el-ins-dashboard");
    else if (label === "EL/INS Export") setView("el-ins-export");
    else if (label === "EL/INS Anomalies") setView("el-ins-anomalies");
    else if (label === "EL/INS Roll-Up") setView("el-ins-rollup");
    else if (label === "Timeline") setView("timeline");
    else if (label === "Org Timeline") setView("org-timeline");
    else if (label === "Regression First") setView("regression-first");
    // Other NavItem labels are static for now (B1 spec).
  };
  const signOut = () => setAuth({ kind: "signed_out" });

  if (view === "personal-elins") {
    return (
      <PersonalElinsShell
        onSignOut={signOut}
        onNavigate={handleNavigate}
      />
    );
  }

  if (view === "library") {
    return (
      <LibraryShell
        onSignOut={signOut}
        onNavigate={handleNavigate}
      />
    );
  }

  if (view === "session") {
    return (
      <SessionShell
        onSignOut={signOut}
        onNavigate={handleNavigate}
      />
    );
  }

  if (view === "session-history") {
    return (
      <SessionHistoryShell
        onSignOut={signOut}
        onNavigate={handleNavigate}
      />
    );
  }

  if (view === "operator-vault") {
    return (
      <OperatorVaultShell
        onSignOut={signOut}
        onNavigate={handleNavigate}
      />
    );
  }

  if (view === "model-preferences") {
    return (
      <ModelPreferencesShell
        onSignOut={signOut}
        onNavigate={handleNavigate}
      />
    );
  }

  if (view === "provider-health") {
    return (
      <ProviderHealthShell
        onSignOut={signOut}
        onNavigate={handleNavigate}
      />
    );
  }

  if (view === "provider-dashboard") {
    return (
      <ProviderDashboardShell
        onSignOut={signOut}
        onNavigate={handleNavigate}
      />
    );
  }

  if (view === "el-ins") {
    return (
      <OperatorElinsShell
        onSignOut={signOut}
        onNavigate={handleNavigate}
      />
    );
  }

  if (view === "el-ins-macro") {
    return (
      <OperatorElinsMacroShell
        onSignOut={signOut}
        onNavigate={handleNavigate}
      />
    );
  }

  if (view === "el-ins-dashboard") {
    return (
      <OperatorElinsDashboardShell
        onSignOut={signOut}
        onNavigate={handleNavigate}
      />
    );
  }

  if (view === "el-ins-export") {
    return (
      <OperatorElinsExportShell
        onSignOut={signOut}
        onNavigate={handleNavigate}
      />
    );
  }

  if (view === "el-ins-anomalies") {
    return (
      <OperatorElinsAnomaliesShell
        onSignOut={signOut}
        onNavigate={handleNavigate}
      />
    );
  }

  if (view === "el-ins-rollup") {
    return (
      <OperatorElinsRollupShell
        onSignOut={signOut}
        onNavigate={handleNavigate}
      />
    );
  }

  if (view === "timeline") {
    return (
      <OperatorTimelineShell
        onSignOut={signOut}
        onNavigate={handleNavigate}
      />
    );
  }

  if (view === "org-timeline") {
    return (
      <OrgTimelineShell
        onSignOut={signOut}
        onNavigate={handleNavigate}
      />
    );
  }

  if (view === "regression-first") {
    return (
      <RegressionFirstShell
        onSignOut={signOut}
        onNavigate={handleNavigate}
      />
    );
  }

  return (
    <ChatWindow
      onSignOut={signOut}
      onNavigate={handleNavigate}
    />
  );
}

// ---------------------------------------------------------------------------
// SignIn — minimal login form. The web client has a richer flow
// (registration, plans, etc.); the desktop client is auth-only.
// Users register via the web client first, then sign in here.
// ---------------------------------------------------------------------------
function SignIn({
  initialError, onSignedIn,
}: { initialError?: string; onSignedIn: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(initialError ?? null);

  const submit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) return;
    setBusy(true); setError(null);
    try {
      await login(username.trim(), password);
      onSignedIn();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [username, password, onSignedIn]);

  return (
    <div className="auth-shell selectable">
      <form className="auth-card" onSubmit={submit}>
        <h1>ClarityOS</h1>
        {error ? <div className="banner err">{error}</div> : null}
        <label htmlFor="u">Username</label>
        <input
          id="u" type="text"
          autoCapitalize="off" autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          disabled={busy}
          autoFocus
        />
        <label htmlFor="p">Password</label>
        <input
          id="p" type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={busy}
        />
        <button
          type="submit"
          disabled={busy || !username.trim() || !password}
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

// Surface any preload-bridged platform metadata so the renderer can
// behave platform-aware in future passes (Cmd vs Ctrl labels, etc.).
// We don't pull in @types/node (would shadow DOM types in the
// renderer); the platform string is just a small literal union the
// preload script returns from process.platform.
type DesktopPlatform =
  | "aix" | "android" | "darwin" | "freebsd" | "haiku"
  | "linux" | "openbsd" | "sunos" | "win32" | "cygwin" | "netbsd";

declare global {
  interface Window {
    clarityos?: {
      onNewThread?: (handler: () => void) => () => void;
      getPlatform?: () => Promise<DesktopPlatform>;
      getVersion?: () => Promise<string>;
    };
  }
}
