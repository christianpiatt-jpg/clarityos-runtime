/**
 * Pocket API client — stubs for the Python clarity-engine backend.
 *
 * The backend URL is injected at build time via the
 * ``VITE_CLARITY_ENGINE_URL`` env var (wired in
 * ``pocket/Dockerfile`` + ``pocket/cloudbuild.pocket.yaml``).
 * When unset, ``getBackendUrl`` returns an empty string so callers
 * can render an explicit "not configured" state rather than firing
 * requests at an undefined target.
 *
 * Every endpoint helper below is intentionally an empty stub in the
 * v0.3.0 scaffold. They will be filled in v0.3.x as each Pocket
 * screen lands.
 */

export function getBackendUrl(): string {
  const raw =
    (import.meta.env.VITE_CLARITY_ENGINE_URL as string | undefined) ?? "";
  return raw.trim();
}

// ---------------------------------------------------------------------------
// Endpoint stubs — implemented in v0.3.x.
// ---------------------------------------------------------------------------

export async function health(): Promise<unknown> {
  throw new Error("Pocket api.health() not implemented yet");
}

export async function me(): Promise<unknown> {
  throw new Error("Pocket api.me() not implemented yet");
}

export async function clarify(_payload: unknown): Promise<unknown> {
  throw new Error("Pocket api.clarify() not implemented yet");
}

export async function runs(): Promise<unknown> {
  throw new Error("Pocket api.runs() not implemented yet");
}

export async function status(): Promise<unknown> {
  throw new Error("Pocket api.status() not implemented yet");
}

export async function stream(_payload: unknown): Promise<unknown> {
  throw new Error("Pocket api.stream() not implemented yet");
}

export async function upload(_file: unknown): Promise<unknown> {
  throw new Error("Pocket api.upload() not implemented yet");
}
