// Card A22-R — server-side streaming tests.
//
// Three contract surfaces under test:
//
//   1. types — StreamEvent shape (closed type enum, string
//      message).
//   2. runStreamTask — generator yields a deterministic
//      sequence; ``?simulate=error`` switches to the early-
//      abort branch; same request → byte-identical sequence
//      across calls; non-mutation.
//   3. handleStream — frames each event via _formatSseFrame
//      (SSE event: <type>, data: <json>); body uses SSE_CONTENT_TYPE;
//      catch block appends STREAM_FATAL_ERROR_EVENT when the
//      generator throws past its own error event.
//
// Path: web/src/surface/__tests__/streaming.test.ts
import { describe, expect, test } from "vitest";

import {
  runStreamTask,
  SIMULATE_ERROR_QUERY,
  type StreamEvent,
} from "../streaming";
import {
  STREAM_PATH,
  STREAM_FATAL_ERROR_EVENT,
  handleStream,
} from "../../server/routes/stream";
import { SSE_CONTENT_TYPE } from "../sseHandler";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";


function req(opts: Partial<WebSurfaceV0_2.Request> = {}): WebSurfaceV0_2.Request {
  return {
    path:    "/__stream",
    method:  "GET",
    headers: {},
    body:    null,
    ...opts,
  };
}


async function collect(
  request: WebSurfaceV0_2.Request,
): Promise<StreamEvent[]> {
  const out: StreamEvent[] = [];
  for await (const ev of runStreamTask(request)) {
    out.push(ev);
  }
  return out;
}


// ---------------------------------------------------------------------------
// 1. Constants
// ---------------------------------------------------------------------------
describe("constants", () => {
  test("STREAM_PATH is the literal /__stream", () => {
    expect(STREAM_PATH).toBe("/__stream");
  });

  test("SIMULATE_ERROR_QUERY is the literal simulate=error", () => {
    expect(SIMULATE_ERROR_QUERY).toBe("simulate=error");
  });

  test("STREAM_FATAL_ERROR_EVENT is type=error", () => {
    expect(STREAM_FATAL_ERROR_EVENT.type).toBe("error");
    expect(typeof STREAM_FATAL_ERROR_EVENT.message).toBe("string");
  });
});


// ---------------------------------------------------------------------------
// 2. runStreamTask — generator behaviour
// ---------------------------------------------------------------------------
describe("runStreamTask — generator", () => {
  test("default sequence: status → log → status → log → log → status → done", async () => {
    const events = await collect(req());
    const types = events.map((e) => e.type);
    expect(types).toEqual([
      "status",
      "log",
      "status",
      "log",
      "log",
      "status",
      "done",
    ]);
  });

  test("each yielded event has type + message", async () => {
    const events = await collect(req());
    for (const ev of events) {
      expect(["log", "status", "done", "error"]).toContain(ev.type);
      expect(typeof ev.message).toBe("string");
      expect(ev.message.length).toBeGreaterThan(0);
    }
  });

  test("default sequence ends on done with message 'task complete'", async () => {
    const events = await collect(req());
    const last = events[events.length - 1];
    expect(last.type).toBe("done");
    expect(last.message).toBe("task complete");
  });

  test("simulate=error query switches to early-abort branch", async () => {
    const events = await collect(req({
      path: "/__stream?simulate=error",
    }));
    const types = events.map((e) => e.type);
    expect(types).toEqual(["status", "log", "error"]);
    expect(events[events.length - 1]).toEqual({
      type:    "error",
      message: "simulated failure",
    });
  });

  test("simulate=error short-circuits — no events after the error", async () => {
    const events = await collect(req({
      path: "/__stream?simulate=error",
    }));
    expect(events).toHaveLength(3);
  });

  test("byte-identical sequence across repeated calls (deterministic)", async () => {
    const r = req();
    const a = await collect(r);
    const b = await collect(r);
    expect(b).toEqual(a);
  });

  test("does not mutate the request", async () => {
    const r = req({ path: "/__stream?simulate=error" });
    const frozen = JSON.stringify(r);
    await collect(r);
    expect(JSON.stringify(r)).toBe(frozen);
  });
});


// ---------------------------------------------------------------------------
// 3. handleStream — SSE response
// ---------------------------------------------------------------------------
describe("handleStream — SSE response", () => {
  test("returns 200 + text/event-stream content-type", async () => {
    const response = await handleStream(req());
    expect(response.status).toBe(200);
    expect(response.headers["content-type"]).toBe(SSE_CONTENT_TYPE);
  });

  test("body frames each event with event: + data: lines", async () => {
    const response = await handleStream(req());
    const body = response.body as string;
    // Spec-shaped SSE: each frame is
    //   event: <type>\ndata: <json>\n\n
    expect(body).toContain("event: status\n");
    expect(body).toContain("event: log\n");
    expect(body).toContain("event: done\n");
    // data: is JSON-encoded — look for the encoded shape.
    expect(body).toContain('data: {"type":"status","message":"starting"}');
    expect(body).toContain('data: {"type":"log","message":"task initialized"}');
    expect(body).toContain('data: {"type":"done","message":"task complete"}');
  });

  test("each frame ends with the canonical \\n\\n terminator", async () => {
    const response = await handleStream(req());
    const body = response.body as string;
    // Default sequence yields 7 events → 7 \n\n terminators.
    const terminators = body.match(/\n\n/g);
    expect(terminators).not.toBeNull();
    expect(terminators!.length).toBe(7);
  });

  test("frames appear in generator emission order", async () => {
    const response = await handleStream(req());
    const body = response.body as string;
    // Use substrings that occur exactly once in the body so
    // indexOf is unambiguous. "complete" is no good — it shows
    // up inside "step 1 complete" and "step 2 complete" too.
    const startingIdx   = body.indexOf("starting");
    const processingIdx = body.indexOf("processing");
    const finalizingIdx = body.indexOf("finalizing");
    const taskCompleteIdx = body.indexOf("task complete");
    expect(startingIdx).toBeGreaterThanOrEqual(0);
    expect(processingIdx).toBeGreaterThan(startingIdx);
    expect(finalizingIdx).toBeGreaterThan(processingIdx);
    expect(taskCompleteIdx).toBeGreaterThan(finalizingIdx);
  });

  test("simulate=error path produces a terminal error frame", async () => {
    const response = await handleStream(req({
      path: "/__stream?simulate=error",
    }));
    const body = response.body as string;
    expect(body).toContain("event: error\n");
    expect(body).toContain('"simulated failure"');
    // No "done" frame on the error branch.
    expect(body).not.toContain("event: done\n");
  });

  test("byte-identical body across repeated calls (deterministic)", async () => {
    const r = req();
    const a = await handleStream(r);
    const b = await handleStream(r);
    expect(b.body).toBe(a.body);
  });

  test("does not mutate the request", async () => {
    const r = req();
    const frozen = JSON.stringify(r);
    await handleStream(r);
    expect(JSON.stringify(r)).toBe(frozen);
  });

  test("error body does NOT leak stack trace text", async () => {
    const response = await handleStream(req({
      path: "/__stream?simulate=error",
    }));
    const body = response.body as string;
    expect(body).not.toContain("at runStreamTask");
    expect(body).not.toContain("Error:");
  });
});
