/**
 * Web Surface v0.2.0 — HTTP adapter (Track C).
 *
 * Pure normalisation layer between Node's ``http.IncomingMessage`` /
 * ``http.ServerResponse`` shapes and the v0.2 surface's internal
 * ``WebSurfaceV0_2.Request`` / ``WebSurfaceV0_2.Response`` shapes.
 * No business logic — every function here is a translation, not a
 * decision.
 *
 * Authority note (Track C):
 *   * The TypeScript surface at ``web/src/surface/`` is the
 *     authoritative v0.2 runtime. This adapter exists so a Node
 *     HTTP server can drive it.
 *   * The Python ``web_surface.py`` stub stays untouched, still
 *     503-gated. This adapter does NOT call into Python.
 *
 * Determinism / non-mutation:
 *   * All helpers are pure functions of their inputs (plus
 *     reading the body bytes off a stream — that's the only I/O).
 *   * No global state. No caches. No side effects beyond the
 *     stream read and the response write.
 *
 * Body coercion policy (matches the v0.2 classifier expectations):
 *   * ``multipart/form-data`` → ``Buffer`` (the upload classifier
 *     branch type-checks via ``Buffer.isBuffer``).
 *   * Empty body                → ``null`` (matches the default
 *     ``req.body`` shape used by GETs throughout the test suite).
 *   * Everything else           → UTF-8 string (the form classifier
 *     branch type-checks via ``typeof === "string"``).
 *
 * Header policy:
 *   * Names are lowercased. Node already lowercases inbound
 *     header names, but ``normalizeHeaders`` enforces it
 *     defensively so the surface's lowercase-only lookups always
 *     succeed.
 *   * Array values (duplicate headers) are joined with ``,``
 *     deterministically. The v0.2 surface's lookups treat each
 *     header as a single string — joining preserves the values
 *     without forcing the surface to handle the array shape.
 */
import { IncomingMessage, ServerResponse } from "node:http";

import { WebSurfaceV0_2 } from "../contracts/webSurfaceV0_2";


/** Content-type prefix that triggers Buffer-body coercion. Held
 *  as a constant so the test suite + the adapter agree on the
 *  exact match. */
export const MULTIPART_PREFIX = "multipart/form-data";


/**
 * Normalise Node's ``req.headers`` map into the
 * ``Record<string, string>`` shape the v0.2 surface expects.
 *
 * Node's IncomingMessage.headers is already keyed on lowercase
 * names, but values may be ``string | string[] | undefined``.
 * This helper:
 *   * Drops undefined values entirely.
 *   * Joins string-array values with ``,`` (RFC 7230's
 *     general-purpose folded-header representation).
 *   * Force-lowercases keys for defence-in-depth.
 */
export function normalizeHeaders(
  raw: IncomingMessage["headers"],
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [name, value] of Object.entries(raw)) {
    if (value === undefined) continue;
    const key = name.toLowerCase();
    out[key] = Array.isArray(value) ? value.join(",") : String(value);
  }
  return out;
}


/**
 * Translate raw body bytes into the shape the v0.2 surface
 * classifier expects (see module docstring for the policy).
 *
 * Exported separately from ``buildSurfaceRequest`` so tests can
 * lock the per-content-type behaviour without rebuilding a
 * full ``IncomingMessage``.
 */
export function coerceBodyForSurface(
  bytes: Buffer,
  contentType: string,
): unknown {
  if (contentType.toLowerCase().startsWith(MULTIPART_PREFIX)) {
    // Multipart upload — surface expects a Buffer even when empty.
    return bytes;
  }
  if (bytes.length === 0) {
    return null;
  }
  return bytes.toString("utf8");
}


/**
 * Read the entire request body into a single Buffer. The v0.2
 * surface is request/response shaped (not streaming), so the
 * adapter materialises the body before calling ``routeWebSurface``.
 *
 * No size cap here. A future card or upstream proxy can enforce
 * one when wire activation moves past v0.2.
 */
export async function readRequestBody(
  req: IncomingMessage,
): Promise<Buffer> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    chunks.push(
      typeof chunk === "string" ? Buffer.from(chunk, "utf8") : chunk,
    );
  }
  return Buffer.concat(chunks);
}


/**
 * Build a ``WebSurfaceV0_2.Request`` from a Node IncomingMessage
 * plus the already-read body bytes.
 *
 * Body reading is split out (``readRequestBody``) so tests can
 * supply a Buffer directly without faking a Readable stream.
 */
export function buildSurfaceRequest(
  req: IncomingMessage,
  body: Buffer,
): WebSurfaceV0_2.Request {
  const headers = normalizeHeaders(req.headers);
  const contentType = headers["content-type"] ?? "";
  return {
    path:    req.url ?? "/",
    method:  (req.method ?? "GET").toUpperCase(),
    headers,
    body:    coerceBodyForSurface(body, contentType),
  };
}


/**
 * Write a ``WebSurfaceV0_2.Response`` out through a Node
 * ServerResponse.
 *
 * Body shape dispatch:
 *   * string                 → written as UTF-8.
 *   * Buffer                 → written verbatim.
 *   * Uint8Array (non-Buffer) → wrapped in a Buffer.
 *   * null / undefined       → empty body.
 *   * anything else (object) → JSON-stringified.
 *
 * The JSON path is what carries the surface's JSON-mode
 * envelopes (``{view, params}``, ``{redirect: ...}``, etc.) onto
 * the wire. The surface itself never JSON-stringifies — that's
 * the adapter's job, at the HTTP boundary, so internal tests
 * can keep asserting on the object shape.
 */
export function writeSurfaceResponse(
  res: ServerResponse,
  response: WebSurfaceV0_2.Response,
): void {
  res.writeHead(response.status, response.headers);
  res.end(_responseBodyToBytes(response.body));
}


/** Exported for tests so the body coercion can be exercised
 *  without faking a ServerResponse. */
export function _responseBodyToBytes(body: unknown): string | Buffer {
  if (body === null || body === undefined) {
    return "";
  }
  if (typeof body === "string") {
    return body;
  }
  if (Buffer.isBuffer(body)) {
    return body;
  }
  if (body instanceof Uint8Array) {
    return Buffer.from(body);
  }
  // Object / array / number / boolean — JSON-encode.
  return JSON.stringify(body);
}
