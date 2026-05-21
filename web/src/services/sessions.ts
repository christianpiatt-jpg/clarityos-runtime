// services/sessions.ts — list the user's Markov sessions (metadata only).

import { getApiBase } from "../lib/config";

export interface SessionMeta {
  session_id: string;
  state_count: number;
  latest_state_index: number;
  latest_ts: number;
}

export async function fetchSessions(limit = 50): Promise<SessionMeta[]> {
  const session = localStorage.getItem("clarityos_session");
  if (!session) throw new Error("missing_session");
  const r = await fetch(`${getApiBase()}/sessions?limit=${limit}`, {
    headers: { "X-Session-ID": session },
  });
  const data = await r.json();
  if (!r.ok || data?.ok === false) {
    throw new Error(data?.message || `sessions HTTP ${r.status}`);
  }
  return (data?.sessions ?? []) as SessionMeta[];
}
