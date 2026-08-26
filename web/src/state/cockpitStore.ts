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
import {
  listThreads,
  createThread,
  getThread,
  postThreadMessage,
  summarizeThread,
  renameThread,
  deleteThread,
  type ThreadMeta,
  type ThreadMessage,
} from "../lib/api";
import type { DirectiveSurface } from "../components/shared/DirectiveBadges";
import type { ElinsV2Envelope } from "../lib/elinsV2";
import type { EmotionalPhysicsResponse } from "../lib/emotionalPhysics";

// ---------------------------------------------------------------- types ----

type LoadStatus = "idle" | "loading" | "ready" | "error";
type ThreadStatus = "loading" | "ready" | "sending" | "error";
/** Which pane the cockpit InsightsPanel is showing. Mirrors Threads.tsx. */
export type InsightsTab = "thread" | "elins" | "physics";

/** A19/A30 — same view-model Threads.tsx uses: the stored message plus the
 *  per-turn directive surface, which rides on the live POST response only. */
export type CockpitChatMessage = ThreadMessage & DirectiveSurface;
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
  thread: {
    status: ThreadStatus;
    meta: ThreadMeta | null;
    messages: CockpitChatMessage[];
    error: string | null;
    /** True while a summarize / rename / delete round-trip is in flight. */
    busy: boolean;
    tab: InsightsTab;
    /** Cached insight results so switching tabs doesn't re-fire the kernel.
     *  Cleared whenever the transcript changes. */
    elins: ElinsV2Envelope | null;
    physics: EmotionalPhysicsResponse | null;
  };
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
    thread: {
      status: "loading", meta: null, messages: [], error: null,
      busy: false, tab: "thread", elins: null, physics: null,
    },
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

// v55 — thread slice. Holds the cockpit's single working thread so that
// ChatPanel (composer + transcript) and ThreadInsightsPanel (meta / summary /
// ELINS / Physics) read the same state instead of each owning a copy.
// Reuses lib/api's existing thread endpoints — no new endpoint, no backend
// change.
const threadSlice = {
  state: (s: CockpitState) => s.thread,
  selectors: {
    meta: (s: CockpitState) => s.thread.meta,
    messages: (s: CockpitState) => s.thread.messages,
    status: (s: CockpitState) => s.thread.status,
    tab: (s: CockpitState) => s.thread.tab,
  },
  actions: {
    /** Adopt the newest existing thread, or create the cockpit's own.
     *  Idempotent: a second call while one is in flight is a no-op, which is
     *  what keeps StrictMode's double-invoked mount effect from creating two
     *  "Cockpit" threads (the guard ChatPanel used to hold in a ref). */
    async init(): Promise<void> {
      if (initInFlight) return;
      initInFlight = true;
      setSlice("thread", { status: "loading", error: null });
      try {
        const threads = await listThreads();
        const meta = threads[0] ?? (await createThread("Cockpit"));
        const detail = await getThread(meta.thread_id);
        setSlice("thread", {
          status: "ready", meta: detail.meta, messages: detail.messages,
          elins: null, physics: null,
        });
      } catch (e) {
        setSlice("thread", { status: "error", error: errMessage(e) });
      } finally {
        initInFlight = false;
      }
    },

    /** Send one turn. Attaches the A19/A30 directive surface from the live
     *  POST response onto the assistant message — Threads.tsx:189-194. */
    async send(text: string): Promise<void> {
      const { meta, status } = current.thread;
      const trimmed = text.trim();
      if (!trimmed || !meta || status === "sending") return;
      setSlice("thread", { status: "sending", error: null });
      try {
        const r = await postThreadMessage(meta.thread_id, trimmed);
        setSlice("thread", {
          status: "ready",
          meta: r.meta,
          messages: [
            ...current.thread.messages,
            r.user_message,
            {
              ...r.assistant_message,
              grounding_status: r.grounding_status ?? null,
              directive_metadata: r.directive_metadata ?? null,
            },
          ],
          // The transcript changed, so cached insight results are stale.
          elins: null,
          physics: null,
        });
      } catch (e) {
        setSlice("thread", { status: "error", error: errMessage(e) });
      }
    },

    async summarize(): Promise<void> {
      const meta = current.thread.meta;
      if (!meta || current.thread.busy) return;
      setSlice("thread", { busy: true, error: null });
      try {
        setSlice("thread", { meta: await summarizeThread(meta.thread_id) });
      } catch (e) {
        setSlice("thread", { error: errMessage(e) });
      } finally {
        setSlice("thread", { busy: false });
      }
    },

    async rename(title: string): Promise<void> {
      const meta = current.thread.meta;
      if (!meta || current.thread.busy) return;
      setSlice("thread", { busy: true, error: null });
      try {
        setSlice("thread", { meta: await renameThread(meta.thread_id, title) });
      } catch (e) {
        setSlice("thread", { error: errMessage(e) });
      } finally {
        setSlice("thread", { busy: false });
      }
    },

    /** Delete the working thread, then re-init so the cockpit always has one. */
    async remove(): Promise<void> {
      const meta = current.thread.meta;
      if (!meta || current.thread.busy) return;
      setSlice("thread", { busy: true, error: null });
      try {
        await deleteThread(meta.thread_id);
        setSlice("thread", { meta: null, messages: [], elins: null, physics: null });
        await threadSlice.actions.init();
      } catch (e) {
        setSlice("thread", { error: errMessage(e) });
      } finally {
        setSlice("thread", { busy: false });
      }
    },

    setTab(tab: InsightsTab): void { setSlice("thread", { tab }); },
    setElins(elins: ElinsV2Envelope | null): void { setSlice("thread", { elins }); },
    setPhysics(physics: EmotionalPhysicsResponse | null): void { setSlice("thread", { physics }); },
  },
};

/** Guards threadSlice.actions.init against concurrent invocation. */
let initInFlight = false;

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
  void threadSlice.actions.init();
}

/** The six slices, each with { state, selectors, actions }. */
export const cockpit = {
  auth: authSlice,
  session: sessionSlice,
  engine: engineSlice,
  vault: vaultSlice,
  runtime: runtimeSlice,
  envelope: envelopeSlice,
  thread: threadSlice,
};
