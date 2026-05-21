// Auth helpers + a tiny store with subscribe so React components can
// re-render on session changes without a heavyweight state library.
//
// Critical: getAuthSnapshot() MUST return a stable reference. React's
// useSyncExternalStore treats reference identity as "did the data change?"
// — if we return a fresh object every call, React loops forever.
// We cache a frozen snapshot and rebuild it only when something
// explicitly invalidates (login / sign-out / profile refresh).

import { clearSession, getProfile, getSession, getUser, refreshProfile, type Profile } from "./api";

type Listener = () => void;
const listeners = new Set<Listener>();

export interface AuthSnapshot {
  session: string | null;
  user: string | null;
  profile: Profile | null;
}

function buildSnapshot(): AuthSnapshot {
  return {
    session: getSession(),
    user: getUser(),
    profile: getProfile(),
  };
}

let cachedSnapshot: AuthSnapshot = buildSnapshot();

function invalidateAndNotify(): void {
  cachedSnapshot = buildSnapshot();
  for (const l of listeners) l();
}

export function subscribeAuth(fn: Listener): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

/** Stable reference. React calls this on every render; same object until
 *  invalidateAndNotify() runs. */
export function getAuthSnapshot(): AuthSnapshot {
  return cachedSnapshot;
}

/** Refresh /me + invalidate so subscribers re-render with the new profile. */
export async function syncProfile(): Promise<Profile | null> {
  const p = await refreshProfile();
  invalidateAndNotify();
  return p;
}

export function signOut(): void {
  clearSession();
  invalidateAndNotify();
}

/** Call after a successful login()/redeem so the rest of the app sees
 *  the new session immediately. */
export function notifyLogin(): void {
  invalidateAndNotify();
}
