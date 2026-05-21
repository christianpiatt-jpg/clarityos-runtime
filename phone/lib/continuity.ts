// Continuity — detect interrupted state on app launch and surface resume
// options. Pure-local, AsyncStorage + filesystem reads only.

import * as FileSystem from "expo-file-system/legacy";
import { storage, KEYS } from "./storage";

export type ResumeOption =
  | { kind: "interrupted-session"; threadId: string; lastEditedAt: number }
  | { kind: "pending-vault"; count: number }
  | { kind: "last-thread"; threadId: string; title?: string };

interface InterruptedRecord {
  threadId: string;
  at: number;
}

const NOTES_DIR = (FileSystem.documentDirectory ?? "") + "vault/notes/";
const SESSIONS_DIR = (FileSystem.documentDirectory ?? "") + "vault/sessions/";

// ---------- Interrupted flag (write-side) ----------------------------------

export async function markInterrupted(threadId: string): Promise<void> {
  const rec: InterruptedRecord = { threadId, at: Date.now() };
  await storage.set(KEYS.interrupted, JSON.stringify(rec));
}

export async function clearInterrupted(): Promise<void> {
  await storage.remove(KEYS.interrupted);
}

async function readInterrupted(): Promise<InterruptedRecord | null> {
  const raw = await storage.get(KEYS.interrupted);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as InterruptedRecord;
  } catch {
    return null;
  }
}

// ---------- Read-side ------------------------------------------------------

export async function checkForInterruptedSession(): Promise<boolean> {
  return (await readInterrupted()) !== null;
}

async function dirCount(dir: string): Promise<number> {
  try {
    const info = await FileSystem.getInfoAsync(dir);
    if (!info.exists) return 0;
    const files = await FileSystem.readDirectoryAsync(dir);
    return files.filter((f) => f.endsWith(".json")).length;
  } catch {
    return 0;
  }
}

interface StoredThread {
  id: string;
  title?: string;
  created?: number;
}

async function readLastThread(): Promise<StoredThread | null> {
  const raw = await storage.get(KEYS.threads);
  if (!raw) return null;
  try {
    const list = JSON.parse(raw);
    if (!Array.isArray(list) || list.length === 0) return null;
    const sorted = (list as StoredThread[]).slice().sort(
      (a, b) => (b.created || 0) - (a.created || 0)
    );
    return sorted[0] ?? null;
  } catch {
    return null;
  }
}

export async function getResumeOptions(): Promise<ResumeOption[]> {
  const out: ResumeOption[] = [];

  const interrupted = await readInterrupted();
  if (interrupted) {
    out.push({
      kind: "interrupted-session",
      threadId: interrupted.threadId,
      lastEditedAt: interrupted.at,
    });
  }

  // TODO: refine to "unreviewed since last open" once vault items carry an
  // `unread` flag. v1 surfaces total vault count.
  const pending = (await dirCount(NOTES_DIR)) + (await dirCount(SESSIONS_DIR));
  if (pending > 0) {
    out.push({ kind: "pending-vault", count: pending });
  }

  const last = await readLastThread();
  if (last && last.id) {
    out.push({ kind: "last-thread", threadId: last.id, title: last.title });
  }

  return out;
}
