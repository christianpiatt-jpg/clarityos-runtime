/**
 * Web Surface v0.2.0 — streaming task controller (Card A22-R).
 *
 * Single helper: ``runStreamTask(request)`` is an async
 * generator that yields a deterministic sequence of
 * ``StreamEvent`` records describing a long-running operation.
 * The ``/__stream`` route adapts each yield into an SSE frame
 * via the existing ``_formatSseFrame`` helper from
 * ``../sseHandler``.
 *
 * Why a generator (and not a callback / promise array):
 *   * Symmetric with the A17 + A18 view ``stream()`` / ``events()``
 *     contracts — same forward-compat shape (when real wire
 *     streaming lands, the route swaps "collect into array"
 *     for "pipe to wire" without touching this file).
 *   * Tests can iterate the generator directly without going
 *     through HTTP or SSE framing.
 *
 * Determinism:
 *   * The default sequence is fixed: status → log → status →
 *     log → log → status → done. Same request in → same event
 *     sequence out.
 *   * Test mode (``?simulate=error`` on the request path)
 *     forces the early-abort path so the route's
 *     error-propagation can be exercised end-to-end.
 *   * No async timing (no ``await sleep``), no I/O, no random
 *     IDs.
 *
 * Error policy:
 *   * The generator may throw in test mode; the route's outer
 *     ``try/catch`` converts a thrown generator into a single
 *     ``error`` SSE frame (defence-in-depth — the generator
 *     also yields a clean ``error`` event before throwing so
 *     normal consumers see structured data).
 */
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";

import { StreamEvent } from "./types";


/** Query-param key that switches the demo task into its
 *  error-simulating branch. Held as a constant so tests +
 *  callers agree on the exact spelling. */
export const SIMULATE_ERROR_QUERY = "simulate=error";


/**
 * Run the demo streaming task and yield ``StreamEvent``
 * records describing each phase.
 *
 * Default sequence:
 *   1. status "starting"
 *   2. log    "task initialized"
 *   3. status "processing"
 *   4. log    "step 1 complete"
 *   5. log    "step 2 complete"
 *   6. status "finalizing"
 *   7. done   "task complete"
 *
 * Error sequence (when the request path includes
 * ``?simulate=error``):
 *   1. status "starting"
 *   2. log    "task initialized"
 *   3. error  "simulated failure"
 *   (generator returns; no further events)
 */
export async function* runStreamTask(
  request: WebSurfaceV0_2.Request,
): AsyncGenerator<StreamEvent> {
  const simulateError = (request.path ?? "").includes(SIMULATE_ERROR_QUERY);

  yield { type: "status", message: "starting" };
  yield { type: "log",    message: "task initialized" };

  if (simulateError) {
    yield { type: "error", message: "simulated failure" };
    return;
  }

  yield { type: "status", message: "processing" };
  yield { type: "log",    message: "step 1 complete" };
  yield { type: "log",    message: "step 2 complete" };
  yield { type: "status", message: "finalizing" };
  yield { type: "done",   message: "task complete" };
}
