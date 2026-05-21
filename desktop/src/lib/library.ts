// desktop/src/lib/library.ts
//
// Typed client for the per-user authored library (GET /library/list).
//
// Item shape mirrors library_store.py exactly:
//   {id, user, title, content, tags[], metadata, size_bytes,
//    created_at, updated_at}
//
// Distinct from the engine-owned GCS-backed POST /library route which
// reads a global content bucket; that endpoint is not consumed here.
//
// Read-only in this client — Slice 4 is browse-only. /library/write,
// /library/update, and /library/delete are deliberately not wrapped
// yet to keep the surface tight.

import { getApiBase, getSession, ApiError } from "./api";

export interface LibraryItem {
  id:          string;
  user:        string;
  title:       string;
  content:     string;
  tags:        string[];
  metadata:    Record<string, unknown>;
  size_bytes:  number;
  created_at:  number;  // float seconds since epoch (server convention)
  updated_at:  number;
}

export interface LibraryListResponse {
  ok:    true;
  items: LibraryItem[];
  count: number;
}

/**
 * GET /library/list. Returns the caller's library entries newest-first.
 * Server clamps ``limit`` to [1, 500].
 */
export async function listLibrary(limit?: number): Promise<LibraryListResponse> {
  const session = getSession();
  if (!session) {
    throw new ApiError("no_session", "not authenticated", 401);
  }
  const q = typeof limit === "number" ? `?limit=${Math.floor(limit)}` : "";
  const url = `${getApiBase()}/library/list${q}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": session,
      },
    });
  } catch (e) {
    throw new ApiError(
      "network",
      e instanceof Error ? e.message : "network failure",
      0,
    );
  }

  let body: unknown = null;
  try { body = await res.json(); } catch { /* leave null */ }

  if (!res.ok) {
    const code =
      isObj(body) && isObj(body.detail) && typeof body.detail.code === "string"
        ? body.detail.code
        : "library_list_failed";
    const message =
      isObj(body) && isObj(body.detail) && typeof body.detail.message === "string"
        ? body.detail.message
        : res.statusText;
    throw new ApiError(code, message, res.status, body);
  }

  if (!isLibraryListResponse(body)) {
    throw new ApiError(
      "shape_mismatch",
      "response is not a library list envelope",
      res.status,
      body,
    );
  }
  return body;
}

// -----------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------

function isObj(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === "object";
}

function isLibraryListResponse(v: unknown): v is LibraryListResponse {
  if (!isObj(v)) return false;
  if (v.ok !== true) return false;
  if (!Array.isArray(v.items)) return false;
  if (typeof v.count !== "number") return false;
  return true;
}
