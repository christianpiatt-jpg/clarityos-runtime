import * as FileSystem from "expo-file-system/legacy";
import type { ProviderId } from "./providers/types";
import type { ClarityObject, ContradictionKind, PressureSignature } from "./langbridg";

// Vault clarity payload — structured runtime data attached to a saved item.
// Lets the operator inspect why something was saved (which decisions/
// contradictions/pressure profile drove the moment) without re-running
// the pipeline. Kept separate from `content` so the human-readable
// distilled text and the structured signals don't get tangled.
export interface VaultClarityPayload {
  decisions: string[];                // decision vectors
  warnings: string[];
  contradictions: Array<{             // contradiction vectors
    a: string;
    b: string;
    lineA: number;
    lineB: number;
    kind: ContradictionKind;
  }>;
  pressure: PressureSignature;        // pressure signature
  interpreters: string[];             // which interpreters contributed
}

export interface VaultNote {
  id: string;
  type: "note";
  content: string;
  tags: string[];
  createdAt: string;
  source?: "ai" | "session";
  providerId?: ProviderId;
  clarity?: VaultClarityPayload;
}

export interface VaultSession {
  id: string;
  type: "session";
  content: string;
  tags: string[];
  createdAt: string;
  clarity?: VaultClarityPayload;
}

export function clarityPayloadFrom(c: ClarityObject): VaultClarityPayload {
  return {
    decisions: c.decisions,
    warnings: c.warnings,
    contradictions: c.contradictions,
    pressure: c.pressure,
    interpreters: c.interpreterTrace,
  };
}

export type VaultItem = VaultNote | VaultSession;

const ROOT = (FileSystem.documentDirectory ?? "") + "vault/";
const NOTES_DIR = ROOT + "notes/";
const SESSIONS_DIR = ROOT + "sessions/";

async function ensureDir(dir: string) {
  const info = await FileSystem.getInfoAsync(dir);
  if (!info.exists) {
    await FileSystem.makeDirectoryAsync(dir, { intermediates: true });
  }
}

function newId(prefix: string) {
  return `${prefix}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

export async function saveNote(
  note: Omit<VaultNote, "id" | "createdAt">
): Promise<VaultNote> {
  await ensureDir(NOTES_DIR);
  const full: VaultNote = {
    ...note,
    id: newId("n"),
    createdAt: new Date().toISOString(),
  };
  await FileSystem.writeAsStringAsync(NOTES_DIR + full.id + ".json", JSON.stringify(full));
  return full;
}

export async function saveSession(
  session: Omit<VaultSession, "id" | "createdAt">
): Promise<VaultSession> {
  await ensureDir(SESSIONS_DIR);
  const full: VaultSession = {
    ...session,
    id: newId("s"),
    createdAt: new Date().toISOString(),
  };
  await FileSystem.writeAsStringAsync(SESSIONS_DIR + full.id + ".json", JSON.stringify(full));
  return full;
}

async function readAll<T extends VaultItem>(dir: string): Promise<T[]> {
  await ensureDir(dir);
  const files = await FileSystem.readDirectoryAsync(dir);
  const out: T[] = [];
  for (const f of files) {
    if (!f.endsWith(".json")) continue;
    try {
      const raw = await FileSystem.readAsStringAsync(dir + f);
      out.push(JSON.parse(raw) as T);
    } catch {
      // skip unreadable files rather than fail the whole list
    }
  }
  return out.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export const listNotes = () => readAll<VaultNote>(NOTES_DIR);
export const listSessions = () => readAll<VaultSession>(SESSIONS_DIR);

export async function readItem(
  type: "note" | "session",
  id: string
): Promise<VaultItem | null> {
  const dir = type === "note" ? NOTES_DIR : SESSIONS_DIR;
  const path = dir + id + ".json";
  const info = await FileSystem.getInfoAsync(path);
  if (!info.exists) return null;
  const raw = await FileSystem.readAsStringAsync(path);
  return JSON.parse(raw) as VaultItem;
}
