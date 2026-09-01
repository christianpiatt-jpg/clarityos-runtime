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
import { fetchRuntimeEnvelope, type RuntimeEnvelope } from "../services/runtime";
import { fetchContinuitySnapshot, type ContinuitySnapshot } from "../services/continuity";
// ★ lib/api declares its OWN ElinsV2Envelope / EmotionalPhysicsResponse,
// distinct from lib/elinsV2 and lib/emotionalPhysics which the thread slice
// uses. Two definitions of one payload -- reported, not merged here. The
// personal slice binds to the API's, because these are the values those
// functions actually return.
import {
  runElinsV2,
  runEmotionalPhysics,
  type ElinsV2Envelope as ApiElinsV2Envelope,
  type EmotionalPhysicsResponse as ApiEmotionalPhysicsResponse,
} from "../lib/api";
import {
  listThreads,
  createThread,
  createProject,
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

/** ★ A VIEW SWITCH, not a route and not a tab. The cockpit chrome stays;
 *  only the centre and right columns change what they render. */
export type CockpitView = "thread" | "personal";

const PERSONAL_DEFAULT_SEED =
  "Personal current state — open snapshot for analysis.";

/** ★ CT-1 ruling 2026-08-26: N = 5.
 *  Emotional Physics runs a metered vendor call, so it does not re-analyse
 *  on every turn. It refreshes automatically every 5th turn and on demand
 *  from the view's Re-run button. Batching was rejected outright -- a
 *  minutes-to-24h latency makes the panel useless as a live read -- so this
 *  is a per-turn throttle, not a queue. */
export const PHYSICS_AUTO_EVERY_N = 5;
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
  vault: { status: LoadStatus; snapshot: ContinuitySnapshot | null; error: string | null };
  runtime: { status: LoadStatus; envelope: RuntimeEnvelope | null; error: string | null };
  envelope: { status: LoadStatus; forSessionId: string | null; data: SessionEnvelope | null; error: string | null };
  /** Which surface the centre + right columns render. */
  view: CockpitView;
  /** RELATIONSHIPS. A relationship IS a thread carrying the reserved
   *  project id -- one store, one minter, one filter. The alternative
   *  was a second thread-shaped store, which is how two definitions of
   *  one payload happen. */
  relationships: {
    status: LoadStatus;
    items: ThreadMeta[];
    activeId: string | null;
    error: string | null;
  };
  /** Personal ELINS. The fetch stays a tier-2 direct call through
   *  lib/api, exactly as routes/PersonalElins.tsx does it -- only the
   *  RESULT lives here, so the centre and right panels read one state. */
  personal: {
    seed: string;
    status: LoadStatus;
    ep: ApiEmotionalPhysicsResponse | null;
    elins: ApiElinsV2Envelope | null;
    lastRunTs: number | null;
    error: string | null;
  };
  thread: {
    status: ThreadStatus;
    meta: ThreadMeta | null;
    /** Every thread the member owns. init() already fetches this list to
     *  pick the newest one; it used to discard the rest. The left rail
     *  reads it, so no second request is made. */
    items: ThreadMeta[];
    messages: CockpitChatMessage[];
    error: string | null;
    /** True while a summarize / rename / delete round-trip is in flight. */
    busy: boolean;
    tab: InsightsTab;
    /** Cached insight results so switching tabs doesn't re-fire the kernel.
     *  ELINS clears on every turn -- it is ten deterministic stages with no
     *  vendor behind them, so re-running is free. */
    elins: ElinsV2Envelope | null;
    /** Physics dispatches a real vendor call (anthropic:claude-haiku-4-5),
     *  so it is THROTTLED: auto-refreshed every PHYSICS_AUTO_EVERY_N turns,
     *  on demand at any time via the view's own Re-run control. Between
     *  those points the last result is held rather than re-fetched. */
    physics: EmotionalPhysicsResponse | null;
    turnsSincePhysics: number;
    /** ★ The text of a send that FAILED, plus why. Held so a failed request
     *  does not destroy what the member typed -- see send(). */
    failedSend: { text: string; error: string } | null;
  };
}

// ----------------------------------------------------------- store core ----

function initialState(): CockpitState {
  return {
    auth: { status: isAuthed() ? "authed" : "anon", user: getUser(), sessionId: getSession(), error: null },
    session: { status: "idle", items: [], selectedId: null, error: null },
    vault: { status: "idle", snapshot: null, error: null },
    runtime: { status: "idle", envelope: null, error: null },
    envelope: { status: "idle", forSessionId: null, data: null, error: null },
    view: "thread",   // a member lands where they land today
    relationships: { status: "idle", items: [], activeId: null, error: null },
    personal: {
      seed: PERSONAL_DEFAULT_SEED, status: "idle", ep: null, elins: null,
      lastRunTs: null, error: null,
    },
    thread: {
      status: "loading", meta: null, items: [], messages: [], error: null,
      busy: false, tab: "thread", elins: null, physics: null,
      turnsSincePhysics: 0, failedSend: null,
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

/** Keys whose value is an object. ``view`` is a bare union, and spreading a
 *  string is not a thing -- so it is excluded here rather than wrapped in a
 *  pointless ``{ current }`` box just to satisfy one generic. */
type ObjectSliceKey = {
  [K in keyof CockpitState]: CockpitState[K] extends object ? K : never
}[keyof CockpitState];

/** Replace one slice immutably (stable refs elsewhere) and notify. */
function setSlice<K extends ObjectSliceKey>(key: K, part: Partial<CockpitState[K]>): void {
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
const viewSlice = {
  state: (s: CockpitState) => s.view,
  selectors: { current: (s: CockpitState) => s.view },
  actions: {
    select(view: CockpitView): void {
      if (current.view === view) return;
      current = { ...current, view };
      listeners.forEach((l) => l());
    },
  },
};

const personalSlice = {
  state: (s: CockpitState) => s.personal,
  selectors: {
    seed: (s: CockpitState) => s.personal.seed,
    ep: (s: CockpitState) => s.personal.ep,
    elins: (s: CockpitState) => s.personal.elins,
    status: (s: CockpitState) => s.personal.status,
  },
  actions: {
    setSeed(seed: string): void { setSlice("personal", { seed }); },

    /** Run the pair. Mirrors routes/PersonalElins.tsx:52-70 exactly: the
     *  physics call is fatal to the run, the ELINS v2 call is NOT -- its
     *  failure leaves that panel empty rather than losing the read that
     *  did arrive. */
    async run(text?: string): Promise<void> {
      const seed = (text ?? current.personal.seed).trim();
      if (!seed) return;
      // The run carries its relationship. The client has held this id all
      // along and simply never sent it, which is why three runs on one
      // subject could not accumulate: the engine had no way to know run 2
      // was the same subject as run 1. Null when none is selected, and
      // then both calls send the bodies they always sent.
      const rel = current.relationships.activeId;
      setSlice("personal", { status: "loading", error: null });
      try {
        const ep = await runEmotionalPhysics(seed, rel);
        let elins: ApiElinsV2Envelope | null = null;
        try {
          elins = await runElinsV2(seed, null, rel);
        } catch {
          elins = null;   // non-fatal, same as the route
        }
        setSlice("personal", {
          status: "ready", ep, elins, lastRunTs: Date.now(),
        });
      } catch (e) {
        setSlice("personal", { status: "error", error: errMessage(e) });
      }
    },
  },
};

/** The reserved project a relationship thread belongs to. */
export const RELATIONSHIP_PROJECT = "relationships";

const isRelationship = (t: ThreadMeta) => t.project_id === RELATIONSHIP_PROJECT;

const relationshipsSlice = {
  state: (s: CockpitState) => s.relationships,
  selectors: {
    items: (s: CockpitState) => s.relationships.items,
    activeId: (s: CockpitState) => s.relationships.activeId,
  },
  actions: {
    /** Load the relationships. Reuses GET /me/threads and partitions
     *  client-side, so the list route is left exactly as it is and
     *  nothing that reads it today changes. */
    async load(): Promise<void> {
      setSlice("relationships", { status: "loading", error: null });
      try {
        const all = await listThreads();
        setSlice("relationships", {
          status: "ready", items: all.filter(isRelationship),
        });
      } catch (e) {
        setSlice("relationships", { status: "error", error: errMessage(e) });
      }
    },

    /** Mint one. The NAME IS REQUIRED -- an unnamed relationship renders
     *  as raw hex, which is exactly what makes the current thread list
     *  unreadable. Refused here rather than allowed and regretted. */
    async create(name: string): Promise<void> {
      const title = (name ?? "").trim();
      if (!title) {
        setSlice("relationships", { error: "A relationship needs a name." });
        return;
      }
      setSlice("relationships", { status: "loading", error: null });
      try {
        // The project must EXIST before a thread can join it (the backend
        // 404s otherwise). Creating it is idempotent in effect: a
        // duplicate id is a 400 we deliberately swallow.
        try {
          await createProject(RELATIONSHIP_PROJECT, "Relationships");
        } catch {
          /* already exists -- that is the state we wanted */
        }
        const meta = await createThread(title, RELATIONSHIP_PROJECT);
        setSlice("relationships", {
          status: "ready",
          items: [meta, ...current.relationships.items],
          activeId: meta.thread_id,
        });
      } catch (e) {
        setSlice("relationships", { status: "error", error: errMessage(e) });
      }
    },

    /** Select one. The next run keys on it. */
    open(threadId: string): void {
      setSlice("relationships", { activeId: threadId });
    },
  },
};

const threadSlice = {
  state: (s: CockpitState) => s.thread,
  selectors: {
    meta: (s: CockpitState) => s.thread.meta,
    items: (s: CockpitState) => s.thread.items,
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
        // Relationships are threads, so they arrive here too. Sessions
        // shows threads and the personal list shows relationships;
        // without this partition each would show both. No thread written
        // before this commit carries the reserved project id, so this
        // filters nothing that already exists.
        const threads = (await listThreads()).filter((t) => !isRelationship(t));
        const meta = threads[0] ?? (await createThread("Cockpit"));
        const detail = await getThread(meta.thread_id);
        setSlice("thread", {
          status: "ready", meta: detail.meta, messages: detail.messages,
          items: threads.length ? threads : [meta],
          elins: null, physics: null, turnsSincePhysics: 0,
        });
        sessionSlice.actions.select(detail.meta.thread_id);
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
      setSlice("thread", { status: "sending", error: null, failedSend: null });
      const nextTurns = current.thread.turnsSincePhysics + 1;
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
          // The transcript changed, so the ELINS envelope is stale. It is
          // deterministic and vendorless, so clearing it costs nothing.
          elins: null,
          // ★ Physics is throttled: only every Nth turn drops the cached
          // response, which is what lets the view auto-run again. On the
          // other turns the previous reading is held and the operator can
          // still force a fresh one with Re-run.
          ...(nextTurns >= PHYSICS_AUTO_EVERY_N
            ? { physics: null, turnsSincePhysics: 0 }
            : { turnsSincePhysics: nextTurns }),
          failedSend: null,
        });
      } catch (e) {
        // ★★ DO NOT DESTROY THE MEMBER'S WORDS.
        //
        // ChatPanel clears the composer the moment send() is called, and a
        // failed send never reaches `messages`. Before this, a failure
        // deleted what the member typed and left a detached error banner at
        // the top of a pane full of successfully-persisted history -- no
        // visual difference between "sent" and "gone", and nothing to retry
        // from. The 400 was one half of the defect; this was the other.
        setSlice("thread", {
          status: "error",
          error: errMessage(e),
          failedSend: { text: trimmed, error: errMessage(e) },
        });
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

    /** Start an empty thread and make it the active one.
     *  
     *  createThread(null) -- a null title, matching the v1 route
     *  (Threads.tsx:191). No prompt, no modal: the use is paste-then-send,
     *  so the thread has to land ACTIVE and EMPTY with the composer ready.
     *  
     *  Opens via threadSlice.actions.open rather than a second selection
     *  path -- open() also sets session.selectedId, so the Envelope panel
     *  follows the new thread for free. A parallel path is how the 5abeb18
     *  orphan happened. */
    async create(): Promise<void> {
      if (current.thread.busy) return;
      setSlice("thread", { busy: true, error: null });
      try {
        const meta = await createThread(null);
        setSlice("thread", { items: [meta, ...current.thread.items] });
        await threadSlice.actions.open(meta.thread_id);
      } catch (e) {
        setSlice("thread", { error: errMessage(e) });
      } finally {
        setSlice("thread", { busy: false });
      }
    },

    /** Switch the cockpit to an existing thread. The left rail lists the
     *  member's threads, so selecting one has to load it. */
    async open(threadId: string): Promise<void> {
      if (current.thread.meta?.thread_id === threadId) return;
      setSlice("thread", { status: "loading", error: null });
      try {
        const detail = await getThread(threadId);
        setSlice("thread", {
          status: "ready", meta: detail.meta, messages: detail.messages,
          elins: null, physics: null, turnsSincePhysics: 0,
        });
        // ONE selection concept: session.selectedId mirrors the active
        // thread. EnvelopeViewerPanel gates on it, and 5abeb18 left it
        // unset when the rail moved off sessionSlice -- the panel read
        // "Select a session." with a thread plainly selected.
        sessionSlice.actions.select(threadId);
      } catch (e) {
        setSlice("thread", { status: "error", error: errMessage(e) });
      }
    },

    /** Drop a failed attempt once the member has retried or edited it. */
    clearFailedSend(): void { setSlice("thread", { failedSend: null }); },
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
  void relationshipsSlice.actions.load();
}

/** The six slices, each with { state, selectors, actions }. */
export const cockpit = {
  auth: authSlice,
  view: viewSlice,
  personal: personalSlice,
  relationships: relationshipsSlice,
  session: sessionSlice,
  vault: vaultSlice,
  runtime: runtimeSlice,
  envelope: envelopeSlice,
  thread: threadSlice,
};
