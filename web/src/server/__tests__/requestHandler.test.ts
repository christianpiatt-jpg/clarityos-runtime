// @vitest-environment node
//
// Track C — request handler tests.
//
// Six surfaces under test:
//
//   1. /health bypass — bypasses the surface, returns deterministic
//      JSON, never calls routeWebSurface.
//   2. /ready bypass  — same as /health.
//   3. Surface dispatch — non-health paths flow through
//      routeWebSurface and the response makes it back to the wire.
//   4. Multiple registered views work end-to-end (home, assets).
//   5. Error isolation — adapter-level fault yields the
//      ADAPTER_INTERNAL_ERROR_ENVELOPE.
//   6. Determinism — same request → same wire bytes across calls.
//
// Path: web/src/server/__tests__/requestHandler.test.ts
import { Readable } from "node:stream";

import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  createRequestHandler,
  ADAPTER_INTERNAL_ERROR_ENVELOPE,
} from "../requestHandler";
import {
  registerView,
  _clearViewRegistryForTests,
} from "../../surface/viewRegistry";
import { clearTemplateCache } from "../../surface/templateCache";
import { clearLayoutCache } from "../../surface/layoutCache";
import { clearPartialCache } from "../../surface/partialCache";
import { clearAssetManifest } from "../../surface/assetManifest";
import { clearAssetCache } from "../../surface/assetCache";
import { homeView } from "../../surface/views/home";
import { error404View, error500View } from "../../surface/views/errors";


// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

function makeReq(opts: {
  method?: string;
  url?: string;
  headers?: Record<string, string | string[] | undefined>;
  body?: Buffer | string | null;
}): import("node:http").IncomingMessage {
  const bodyBuf =
    opts.body === null || opts.body === undefined
      ? Buffer.alloc(0)
      : typeof opts.body === "string"
        ? Buffer.from(opts.body, "utf8")
        : opts.body;
  const stream = Readable.from([bodyBuf]) as unknown as
    import("node:http").IncomingMessage;
  (stream as unknown as { method?: string }).method = opts.method ?? "GET";
  (stream as unknown as { url?: string }).url = opts.url ?? "/";
  (stream as unknown as { headers: Record<string, string | string[] | undefined> })
    .headers = opts.headers ?? {};
  return stream;
}


function makeRes(): {
  res: import("node:http").ServerResponse;
  captured: {
    status?: number;
    headers?: Record<string, string>;
    body?: string | Buffer;
    endCalled: boolean;
  };
} {
  const captured: {
    status?: number;
    headers?: Record<string, string>;
    body?: string | Buffer;
    endCalled: boolean;
  } = { endCalled: false };
  const res = {
    writeHead(status: number, headers: Record<string, string>) {
      captured.status = status;
      captured.headers = headers;
      return this;
    },
    end(body?: string | Buffer) {
      if (body !== undefined) captured.body = body;
      captured.endCalled = true;
    },
  } as unknown as import("node:http").ServerResponse;
  return { res, captured };
}


beforeEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
  clearAssetCache();
  registerView("home",      homeView);
  registerView("error_404", error404View);
  registerView("error_500", error500View);
});

afterEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
  clearAssetCache();
});


// ---------------------------------------------------------------------------
// 1. /health bypass
// ---------------------------------------------------------------------------
describe("createRequestHandler — /health bypass", () => {
  test("GET /health → 200 + JSON payload, no surface involvement", async () => {
    const handler = createRequestHandler();
    const req = makeReq({ method: "GET", url: "/health" });
    const { res, captured } = makeRes();
    await handler(req, res);
    expect(captured.status).toBe(200);
    expect(captured.headers).toEqual({ "content-type": "application/json" });
    expect(captured.body).toBe('{"status":"ok","surface":"v0.2.0"}');
  });

  test("/health works even when the view registry is empty", async () => {
    // Wipe the registry to simulate a startup where no views
    // are loaded yet. /health must still answer.
    _clearViewRegistryForTests();
    const handler = createRequestHandler();
    const req = makeReq({ method: "GET", url: "/health" });
    const { res, captured } = makeRes();
    await handler(req, res);
    expect(captured.status).toBe(200);
    expect(captured.body).toBe('{"status":"ok","surface":"v0.2.0"}');
  });

  test("/health works for POST too (method-agnostic bypass)", async () => {
    const handler = createRequestHandler();
    const req = makeReq({ method: "POST", url: "/health" });
    const { res, captured } = makeRes();
    await handler(req, res);
    expect(captured.status).toBe(200);
  });

  test("/health?probe=1 (querystring) still hits the bypass", async () => {
    const handler = createRequestHandler();
    const req = makeReq({ method: "GET", url: "/health?probe=1" });
    const { res, captured } = makeRes();
    await handler(req, res);
    expect(captured.status).toBe(200);
    expect(captured.body).toBe('{"status":"ok","surface":"v0.2.0"}');
  });
});


// ---------------------------------------------------------------------------
// 2. /ready bypass
// ---------------------------------------------------------------------------
describe("createRequestHandler — /ready bypass", () => {
  test("GET /ready → same payload as /health (Track C spec)", async () => {
    const handler = createRequestHandler();
    const req = makeReq({ method: "GET", url: "/ready" });
    const { res, captured } = makeRes();
    await handler(req, res);
    expect(captured.status).toBe(200);
    expect(captured.body).toBe('{"status":"ok","surface":"v0.2.0"}');
  });
});


// ---------------------------------------------------------------------------
// 3. Surface dispatch (non-health paths)
// ---------------------------------------------------------------------------
describe("createRequestHandler — surface dispatch", () => {
  test("GET /home → 200 HTML via routeWebSurface", async () => {
    const handler = createRequestHandler();
    const req = makeReq({ method: "GET", url: "/home" });
    const { res, captured } = makeRes();
    await handler(req, res);
    expect(captured.status).toBe(200);
    expect(captured.headers?.["content-type"])
      .toBe("text/html; charset=utf-8");
    expect(typeof captured.body).toBe("string");
    expect(String(captured.body)).toContain("<!DOCTYPE html>");
  });

  test("unknown path → 404 error page (classifier rewrite to error_404)", async () => {
    const handler = createRequestHandler();
    const req = makeReq({ method: "GET", url: "/no-such-view" });
    const { res, captured } = makeRes();
    await handler(req, res);
    expect(captured.status).toBe(404);
    expect(String(captured.body)).toContain("Not Found");
  });

  test("JSON Accept → JSON envelope on the wire (object body JSON-stringified)", async () => {
    const handler = createRequestHandler();
    const req = makeReq({
      method:  "GET",
      url:     "/no-such-view",
      headers: { accept: "application/json" },
    });
    const { res, captured } = makeRes();
    await handler(req, res);
    expect(captured.headers?.["content-type"]).toBe("application/json");
    // JSON-encoded object body — the surface returns an object;
    // the adapter stringifies it for the wire.
    expect(typeof captured.body).toBe("string");
    const parsed = JSON.parse(String(captured.body));
    expect(parsed).toEqual({
      view:   "error_404",
      params: { message: "View 'no-such-view' not found." },
    });
  });

  test("asset request returns Buffer body verbatim on the wire", async () => {
    const handler = createRequestHandler();
    const req = makeReq({
      method: "GET",
      url:    "/web-surface/v0.2/assets/style.css",
    });
    const { res, captured } = makeRes();
    await handler(req, res);
    expect(captured.status).toBe(200);
    expect(captured.headers?.["content-type"]).toBe("text/css");
    expect(Buffer.isBuffer(captured.body)).toBe(true);
    expect((captured.body as Buffer).toString("utf8"))
      .toContain("font-family");
  });

  test("form POST body flows through as string", async () => {
    const handler = createRequestHandler();
    // Probe view doesn't HTML-escape — we're testing the
    // adapter's body-flow, not the view layer's escape policy.
    // Raw JSON ends up in <pre> with literal quotes.
    registerView("echo_form", {
      template: "base",
      async render(ctx) {
        return {
          title:   "echo",
          content: JSON.stringify(ctx.params ?? {}),
        };
      },
    });
    const req = makeReq({
      method:  "POST",
      url:     "/echo_form",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body:    "name=Alice&id=42",
    });
    const { res, captured } = makeRes();
    await handler(req, res);
    expect(captured.status).toBe(200);
    expect(String(captured.body))
      .toContain('{"name":"Alice","id":"42"}');
  });

  test("multipart POST body flows through as Buffer", async () => {
    const handler = createRequestHandler();
    const boundary = "----TestB_track_c";
    const body = Buffer.concat([
      Buffer.from(`--${boundary}\r\n`),
      Buffer.from(
        `Content-Disposition: form-data; name="file"; filename="x.txt"\r\n` +
        `Content-Type: text/plain\r\n\r\n`,
      ),
      Buffer.from("hello"),
      Buffer.from(`\r\n--${boundary}--\r\n`),
    ]);
    // Register a probe view to assert the upload made it through.
    registerView("upload_probe_track_c", {
      template: "base",
      async render(ctx) {
        const files =
          (ctx.params as { files?: Record<string, { filename: string }> })
            ?.files ?? {};
        return {
          title:   "p",
          content: files["file"]?.filename ?? "(none)",
        };
      },
    });
    const req = makeReq({
      method:  "POST",
      url:     "/upload_probe_track_c",
      headers: { "content-type": `multipart/form-data; boundary=${boundary}` },
      body,
    });
    const { res, captured } = makeRes();
    await handler(req, res);
    expect(captured.status).toBe(200);
    expect(String(captured.body)).toContain("x.txt");
  });
});


// ---------------------------------------------------------------------------
// 4. Error isolation
// ---------------------------------------------------------------------------
describe("createRequestHandler — error isolation", () => {
  test("body stream that throws → ADAPTER_INTERNAL_ERROR_ENVELOPE", async () => {
    const handler = createRequestHandler();
    // A Readable that throws on first read — simulates an
    // upstream proxy / Cloud Run socket failure mid-request.
    const failingStream = new Readable({
      read() {
        this.destroy(new Error("upstream-fail"));
      },
    }) as unknown as import("node:http").IncomingMessage;
    (failingStream as unknown as { method?: string }).method = "POST";
    (failingStream as unknown as { url?: string }).url = "/home";
    (failingStream as unknown as {
      headers: Record<string, string>;
    }).headers = { "content-type": "text/plain" };

    const { res, captured } = makeRes();
    await handler(failingStream, res);

    expect(captured.status).toBe(ADAPTER_INTERNAL_ERROR_ENVELOPE.status);
    expect(captured.body).toBe(
      JSON.stringify(ADAPTER_INTERNAL_ERROR_ENVELOPE.body),
    );
  });

  test("error envelope does NOT leak the upstream exception text", async () => {
    const handler = createRequestHandler();
    const secret = "track-c-secret-do-not-leak";
    const failingStream = new Readable({
      read() {
        this.destroy(new Error(secret));
      },
    }) as unknown as import("node:http").IncomingMessage;
    (failingStream as unknown as { method?: string }).method = "POST";
    (failingStream as unknown as { url?: string }).url = "/home";
    (failingStream as unknown as { headers: Record<string, string> }).headers =
      { "content-type": "text/plain" };

    const { res, captured } = makeRes();
    await handler(failingStream, res);

    expect(String(captured.body)).not.toContain(secret);
  });

  test("error envelope shape matches the A11 posture", () => {
    expect(ADAPTER_INTERNAL_ERROR_ENVELOPE).toEqual({
      status:  500,
      headers: { "content-type": "application/json" },
      body:    { error: "internal_server_error" },
    });
  });
});


// ---------------------------------------------------------------------------
// 5. Determinism
// ---------------------------------------------------------------------------
describe("createRequestHandler — determinism", () => {
  test("same GET → same wire bytes across 3 calls", async () => {
    const handler = createRequestHandler();
    const bodies: Array<string | Buffer | undefined> = [];
    for (let i = 0; i < 3; i++) {
      const req = makeReq({ method: "GET", url: "/health" });
      const { res, captured } = makeRes();
      await handler(req, res);
      bodies.push(captured.body);
    }
    for (let i = 1; i < bodies.length; i++) {
      expect(bodies[i]).toBe(bodies[0]);
    }
  });

  test("handler is reentrant — two parallel calls don't cross-contaminate", async () => {
    const handler = createRequestHandler();
    const reqA = makeReq({ method: "GET", url: "/home" });
    const reqB = makeReq({ method: "GET", url: "/health" });
    const { res: resA, captured: capA } = makeRes();
    const { res: resB, captured: capB } = makeRes();
    await Promise.all([handler(reqA, resA), handler(reqB, resB)]);
    // Home → HTML; health → JSON. Bytes must not have crossed.
    expect(capA.headers?.["content-type"])
      .toBe("text/html; charset=utf-8");
    expect(capB.headers?.["content-type"])
      .toBe("application/json");
  });
});
