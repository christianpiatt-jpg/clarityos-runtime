/**
 * Web Surface v0.2.0 — Node HTTP request handler factory
 * (Track C).
 *
 * Single entrypoint for the Node ``http`` server. Composes the
 * pure pieces in this directory:
 *
 *   1. ``handleHealth`` — intercept ``/health`` + ``/ready``
 *      BEFORE the surface router (per Track C spec).
 *   2. ``readRequestBody`` + ``buildSurfaceRequest`` — translate
 *      the IncomingMessage into ``WebSurfaceV0_2.Request``.
 *   3. ``routeWebSurface`` — the TS surface (authoritative
 *      runtime for v0.2 per Track C).
 *   4. ``writeSurfaceResponse`` — translate the surface's
 *      ``WebSurfaceV0_2.Response`` back onto the wire.
 *
 * Factored out of the server bootstrap (``main.ts``) so tests
 * can exercise the handler without invoking ``listen()``.
 *
 * Error isolation (A11-style):
 *   * Any unexpected throw inside the handler is caught and
 *     translated into a 500 + minimal JSON envelope. The
 *     surface itself has its own A11 fallback inside
 *     ``executeRenderPipeline``, so this catch is the
 *     belt-and-braces layer for adapter / I/O failures.
 *   * No stack-trace leakage. No exception text in the body.
 *
 * Stream / SSE compatibility:
 *   * The handler awaits ``routeWebSurface`` and writes the full
 *     Response at once — exactly the same shape the rest of the
 *     surface expects. A17 (stream) and A18 (SSE) already
 *     pre-assemble their bodies; they ride through this handler
 *     unchanged. Future wire-level streaming would replace the
 *     ``writeSurfaceResponse`` step with a streaming variant
 *     WITHOUT touching anything inside the surface.
 */
import { IncomingMessage, ServerResponse } from "node:http";

import { WebSurfaceV0_2 } from "../contracts/webSurfaceV0_2";
import { routeWebSurface } from "../surface/router";

import {
  buildSurfaceRequest,
  readRequestBody,
  writeSurfaceResponse,
} from "./httpAdapter";
import {
  HEALTH_PATHS,
  handleHealth,
} from "./healthRouter";
import {
  DIAGNOSTICS_PATH,
  handleDiagnostics,
} from "./routes/diagnostics";
import {
  STREAM_PATH,
  handleStream,
} from "./routes/stream";


/** Compile-time guard so we can reuse the constant in narrow
 *  checks. Mirrors ``HEALTH_PATHS`` but as a Set for O(1)
 *  membership. */
const _HEALTH_PATH_SET = new Set<string>(HEALTH_PATHS);


/** The fallback 500 envelope used when the adapter itself throws
 *  (i.e., something outside the surface's own A11 try/catch).
 *  Exported so tests can assert against the exact shape. */
export const ADAPTER_INTERNAL_ERROR_ENVELOPE: WebSurfaceV0_2.Response = {
  status:  500,
  headers: { "content-type": "application/json" },
  body:    { error: "internal_server_error" },
};


/**
 * Extract the path component of a Node request URL, dropping
 * any querystring. The classifier reads the querystring back
 * via ``new URL(path, ...)`` so we keep the original
 * ``req.url`` for the surface; this helper is only for the
 * health-bypass match.
 */
function _pathOnly(url: string | undefined): string {
  const u = url ?? "/";
  const q = u.indexOf("?");
  return q === -1 ? u : u.slice(0, q);
}


/**
 * Build a Node-http compatible request handler that drives the
 * v0.2 surface.
 *
 * Exported as a factory (rather than a single shared handler)
 * so tests can instantiate fresh handlers per test, and so
 * future Track C++ work can inject alternate dependencies
 * (e.g., a metrics-wrapped routeWebSurface) without monkey-
 * patching the module.
 */
export function createRequestHandler(): (
  req: IncomingMessage,
  res: ServerResponse,
) => Promise<void> {
  return async function handle(req, res) {
    try {
      // Health / ready bypass — must not touch the surface, the
      // view registry, or the Python 503 gate.
      const path = _pathOnly(req.url);
      if (_HEALTH_PATH_SET.has(path)) {
        writeSurfaceResponse(res, handleHealth());
        return;
      }

      // Card A21-R: diagnostics interceptor. Same shape as the
      // health bypass — matched BEFORE the surface router so a
      // broken view registry can't take operator diagnostics
      // down with it. We still build a normalised surface
      // request (the collector reads method / path / headers
      // off it) but ``routeWebSurface`` is never called.
      if (path === DIAGNOSTICS_PATH) {
        const diagBody = await readRequestBody(req);
        const diagReq = buildSurfaceRequest(req, diagBody);
        const diagRes = await handleDiagnostics(diagReq);
        writeSurfaceResponse(res, diagRes);
        return;
      }

      // Card A22-R: streaming interceptor. Same interception
      // shape as the diagnostics route — matched BEFORE the
      // surface router so a broken view registry can't disable
      // operator-facing long-running-task feedback. The route
      // returns an SSE-shaped Response (a single buffered body
      // with ``text/event-stream`` content-type) that the
      // browser's ``EventSource`` can consume directly.
      if (path === STREAM_PATH) {
        const streamBody = await readRequestBody(req);
        const streamReq = buildSurfaceRequest(req, streamBody);
        const streamRes = await handleStream(streamReq);
        writeSurfaceResponse(res, streamRes);
        return;
      }

      // Surface dispatch.
      const body = await readRequestBody(req);
      const surfaceReq = buildSurfaceRequest(req, body);
      const surfaceRes = await routeWebSurface(surfaceReq);
      writeSurfaceResponse(res, surfaceRes);
    } catch {
      // Adapter-level fault. The surface's own try/catch (Card
      // A11) handles render-pipeline faults; this is the
      // outermost defence-in-depth for body-read failures,
      // response-write failures, etc.
      try {
        writeSurfaceResponse(res, ADAPTER_INTERNAL_ERROR_ENVELOPE);
      } catch {
        // Triple-fault — give up. Node will close the socket.
      }
    }
  };
}
