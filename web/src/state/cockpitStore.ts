/**
 * CockpitV2 state module — a minimal external store (no Redux, no Zustand,
 * no new dependencies). Backed by React's useSyncExternalStore.
 *
 * Used ONLY by routes/CockpitV2.tsx and components/cockpitV2/*. No existing
 * route or component imports this module.
 *
 * Six slices, each exposing { state, selectors, actions }:
 *   auth · session · engine · vault · runtime · envelope
 *
 * All backend access reuses the existing data layer (lib/api.ts +
 * services/*). This module introduces no new endpoints.
 */
import { useSyncExternalStore } from "react";

import { ApiError, login as apiLogin, isAuthed, getUser, getSession, markovEnvelopeLatest } from "../lib/api";
import { notifyLogin, signOut as authSignOut, syncProfile } from "../lib/auth";
import { fetchSessions, type SessionMeta } from "../services/sessions";
import type { EngineId } from "../services/engines";
import { fetchRuntimeEnvelope, type RuntimeEnvelope } from "../services/runtime";
import { fetchContinuitySnapshot, type ContinuitySnapshot } from "../services/continuity";

// ---------------------------------------------------------------- types ----

type LoadStatus = "idle" | "loading" | "ready" | "error";
type AuthStatus = "anon" | "authing" | "authed" | "error";

/** Per-session envelope returned by GET /markov/envelope/latest. */
export type SessionEnvelope = Awaited<ReturnType<typeof markovEnvelopeLatest>>;

export interface CockpitState {
  auth: { status: AuthStatus; user: string | null; sessionId: string | null; error: string | null };
  session: { status: LoadStatus; items: SessionMeta[]; selectedId: string | null; error: string | null };
  engine: { selected: EngineId };
  vault: { status: LoadStatus; snapshot: ContinuitySnapshot | null; error: string | null };
  runtime: { status: LoadStatus; envelope: RuntimeEnvelope | null; error: string | null };
  envelope: { status: LoadStatus; forSessionId: string | null; data: SessionEnvelope | null; error: string | null };
}

// ----------------------------------------------------------- store core ----

function initialState(): CockpitState {
  return {
    auth: { status: isAuthed() ? "authed" : "anon", user: getUser(), sessionId: getSession(), error: null },
    session: { status: "idle", items: [], selectedId: null, error: null },
    engine: { selected: "markov" },
    vault: { status: "idle", snapshot: null, error: null },
    runtime: { status: "idle", envelope: null, error: null },
    envelope: { status: "idle", forSessionId: null, data: null, error: null },
  };
}

let current: CockpitState = initialState();
const listeners = new Set<() => void>();

function getSnapshot(): CockpitState {
  return current;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Replace one slice immutably (stable refs elsewhere) and notify. */
function setSlice<K extends keyof CockpitState>(key: K, part: Partial<CockpitState[K]>): void {
  current = { ...current, [key]: { ...current[key], ...part } };
  listeners.forEach((l) => l());
}

function errMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message || e.code;
  if (e instanceof Error) return e.message;
  return "unexpected error";
}

// --------------------------------------------------------------- slices ----

const authSlice = {
  state: (s: CockpitState) => s.auth,
  selectors: {
    status: (s: CockpitState) => s.auth.status,
    user: (s: CockpitState) => s.auth.user,
    sessionId: (s: CockpitState) => s.auth.sessionId,
    isAuthed: (s: CockpitState) => s.auth.status === "authed",
    error: (s: CockpitState) => s.auth.error,
  },
  actions: {
    async login(username: string, password: string): Promise<void> {
      setSlice("auth", { status: "authing", error: null });
      try {
        await apiLogin(username.trim(), password);
        notifyLogin();
        await syncProfile();
        setSlice("auth", { status: "authed", user: getUser(), sessionId: getSession(), error: null });
      } catch (e) {
        setSlice("auth", { status: "error", error: errMessage(e) });
      }
    },
    logout(): void {
      authSignOut();
      current = initialState();
      listeners.forEach((l) => l());
    },
  },
};

const engineSlice = {
  state: (s: CockpitState) => s.engine,
  selectors: {
    selected: (s: CockpitState) => s.engine.selected,
  },
  actions: {
    select(engine: EngineId): void {
      setSlice("engine", { selected: engine });
    },
  },
};

const vaultSlice = {
  state: (s: CockpitState) => s.vault,
  selectors: {
    snapshot: (s: CockpitState) => s.vault.snapshot,
    status: (s: CockpitState) => s.vault.status,
  },
  actions: {
    async load(): Promise<void> {
      setSlice("vault", { status: "loading", error: null });
      try {
        const snapshot = await fetchContinuitySnapshot();
        setSlice("vault", { status: "ready", snapshot });
      } catch (e) {
        setSlice("vault", { status: "error", error: errMessage(e) });
      }
    },
  },
};

const runtimeSlice = {
  state: (s: CockpitState) => s.runtime,
  selectors: {
    envelope: (s: CockpitState) => s.runtime.envelope,
    status: (s: CockpitState) => s.runtime.status,
  },
  actions: {
    async load(): Promise<void> {
      setSlice("runtime", { status: "loading", error: null });
      try {
        const envelope = await fetchRuntimeEnvelope();
        setSlice("runtime", { status: "ready", envelope });
      } catch (e) {
        setSlice("runtime", { status: "error", error: errMessage(e) });
      }
    },
  },
};

const envelopeSlice = {
  state: (s: CockpitState) => s.envelope,
  selectors: {
    data: (s: CockpitState) => s.envelope.data,
    status: (s: CockpitState) => s.envelope.status,
  },
  actions: {
    /** Load the envelope for a session; ignores stale responses. */
    async loadFor(sessionId: string): Promise<void> {
      setSlice("envelope", { status: "loading", forSessionId: sessionId, data: null, error: null });
      try {
        const data = await markovEnvelopeLatest(sessionId);
        if (current.session.selectedId === sessionId) {
          setSlice("envelope", { status: "ready", data });
        }
      } catch (e) {
        if (current.session.selectedId === sessionId) {
          setSlice("envelope", { status: "error", error: errMessage(e) });
        }
      }
    },
    clear(): void {
      setSlice("envelope", { status: "idle", forSessionId: null, data: null, error: null });
    },
  },
};

const sessionSlice = {
  state: (s: CockpitState) => s.session,
  selectors: {
    items: (s: CockpitState) => s.session.items,
    selectedId: (s: CockpitState) => s.session.selectedId,
    status: (s: CockpitState) => s.session.status,
  },
  actions: {
    async load(): Promise<void> {
      setSlice("session", { status: "loading", error: null });
      try {
        const items = await fetchSessions(50);
        setSlice("session", { status: "ready", items });
      } catch (e) {
        setSlice("session", { status: "error", error: errMessage(e) });
      }
    },
    select(sessionId: string | null): void {
      setSlice("session", { selectedId: sessionId });
      if (sessionId) void envelopeSlice.actions.loadFor(sessionId);
      else envelopeSlice.actions.clear();
    },
  },
};

// --------------------------------------------------------- React binding ----

/** Subscribe a component to a slice/primitive. Selectors must return a
 *  stable reference (a slice object or a primitive) — never a fresh object. */
export function useCockpit<T>(selector: (s: CockpitState) => T): T {
  return useSyncExternalStore(
    subscribe,
    () => selector(getSnapshot()),
    () => selector(getSnapshot()),
  );
}

/** Fire the initial data loads. Call once, after auth.
 *  Runtime is intentionally excluded — RuntimePanel owns it (mount + 10s poll). */
export function bootstrapCockpit(): void {
  void sessionSlice.actions.load();
  void vaultSlice.actions.load();
}

/** The six slices, each with { state, selectors, actions }. */
export const cockpit = {
  auth: authSlice,
  session: sessionSlice,
  engine: engineSlice,
  vault: vaultSlice,
  runtime: runtimeSlice,
  envelope: envelopeSlice,
};
