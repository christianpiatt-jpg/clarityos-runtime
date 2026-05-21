// Local continuity detection. No backend route — surfaces resume options
// at app launch from local-only state:
//   - last conversation thread (from local sessions store)
//   - interrupted session (set by chat-style flows when they're cut off)
//
// Pending-vault detection was dropped when the vault moved to the server
// (Storage Layer v1). "Pending" no longer has meaning when writes are
// synchronous and authoritative.

const SESSIONS_KEY = "clarityos.threads"; // thread = local conversation
const INTERRUPTED_KEY = "clarityos.interrupted";

export type ResumeOption =
  | { kind: "interrupted-session"; threadId: string; lastEditedAt: number }
  | { kind: "last-thread"; threadId: string; title?: string };

interface InterruptedRecord { threadId: string; at: number; }

export function markInterrupted(threadId: string): void {
  try {
    localStorage.setItem(INTERRUPTED_KEY, JSON.stringify({ threadId, at: Date.now() } as InterruptedRecord));
  } catch { /* noop */ }
}

export function clearInterrupted(): void {
  try { localStorage.removeItem(INTERRUPTED_KEY); } catch { /* noop */ }
}

function readInterrupted(): InterruptedRecord | null {
  try {
    const raw = localStorage.getItem(INTERRUPTED_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as InterruptedRecord;
  } catch { return null; }
}

interface StoredThread { id: string; title?: string; created?: number; }

function readLastThread(): StoredThread | null {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY);
    if (!raw) return null;
    const list = JSON.parse(raw);
    if (!Array.isArray(list) || list.length === 0) return null;
    return (list as StoredThread[]).slice().sort((a, b) => (b.created || 0) - (a.created || 0))[0] ?? null;
  } catch { return null; }
}

export function getResumeOptions(): ResumeOption[] {
  const out: ResumeOption[] = [];

  const interrupted = readInterrupted();
  if (interrupted) {
    out.push({ kind: "interrupted-session", threadId: interrupted.threadId, lastEditedAt: interrupted.at });
  }

  const last = readLastThread();
  if (last && last.id) {
    out.push({ kind: "last-thread", threadId: last.id, title: last.title });
  }

  return out;
}

// ---------- Local thread helpers (used by Sessions screen) ----------

export interface LocalThread {
  id: string;
  title?: string;
  created: number;
  log: { ts: number; kind: string; text: string }[];
}

export function listThreads(): LocalThread[] {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY);
    if (!raw) return [];
    const list = JSON.parse(raw);
    if (!Array.isArray(list)) return [];
    return (list as LocalThread[]).slice().sort((a, b) => (b.created || 0) - (a.created || 0));
  } catch { return []; }
}

export function readThread(id: string): LocalThread | null {
  return listThreads().find((t) => t.id === id) || null;
}
