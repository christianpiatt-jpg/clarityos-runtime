// @vitest-environment node
//
// Track C — HTTP adapter tests.
//
// Five surfaces under test:
//
//   1. normalizeHeaders — case folding, array joining, undefined drop.
//
//   2. coerceBodyForSurface — multipart → Buffer; empty → null;
//      other → UTF-8 string. Matches the v0.2 classifier's
//      type-check expectations.
//
//   3. readRequestBody — stream → single Buffer. Works on a
//      Readable that yields Buffer chunks AND on one that
//      yields strings (Node coerces inbound text encoding for
//      the latter).
//
//   4. buildSurfaceRequest — combines the helpers into a
//      WebSurfaceV0_2.Request that the classifier accepts.
//
//   5. writeSurfaceResponse / _responseBodyToBytes — body shape
//      dispatch (string passthrough, Buffer passthrough,
//      Uint8Array wrap, object JSON-encode, null → empty).
//
// Path: web/src/server/__tests__/httpAdapter.test.ts
import { Readable } from "node:stream";

import { describe, expect, test } from "vitest";

import {
  normalizeHeaders,
  coerceBodyForSurface,
  readRequestBody,
  buildSurfaceRequest,
  writeSurfaceResponse,
  _responseBodyToBytes,
  MULTIPART_PREFIX,
} from "../httpAdapter";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";


// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

/** Build a fake IncomingMessage shape sufficient for the
 *  adapter functions that don't actually read the body stream
 *  (normalizeHeaders, buildSurfaceRequest). */
function fakeIncomingMessage(opts: {
  method?: string;
  url?: string;
  headers?: Record<string, string | string[] | undefined>;
}): import("node:http").IncomingMessage {
  return {
    method:  opts.method,
    url:     opts.url,
    headers: opts.headers ?? {},
  } as unknown as import("node:http").IncomingMessage;
}


/** Capture-style fake ServerResponse. ``writeHead`` records the
 *  status + headers; ``end`` records the body. */
function fakeServerResponse(): {
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


// ---------------------------------------------------------------------------
// 1. normalizeHeaders
// ---------------------------------------------------------------------------
describe("normalizeHeaders", () => {
  test("lowercases header names", () => {
    expect(normalizeHeaders({ "Content-Type": "text/html" })).toEqual({
      "content-type": "text/html",
    });
  });

  test("preserves lowercase keys unchanged", () => {
    expect(normalizeHeaders({ accept: "application/json" })).toEqual({
      accept: "application/json",
    });
  });

  test("joins array values with ','", () => {
    expect(normalizeHeaders({
      "set-cookie": ["a=1", "b=2", "c=3"],
    })).toEqual({
      "set-cookie": "a=1,b=2,c=3",
    });
  });

  test("drops undefined values", () => {
    expect(normalizeHeaders({
      "content-type": "text/plain",
      "x-undefined": undefined,
    })).toEqual({
      "content-type": "text/plain",
    });
  });

  test("returns an empty object for empty input", () => {
    expect(normalizeHeaders({})).toEqual({});
  });

  test("coerces non-string single values to strings", () => {
    // Node's typings allow only string | string[], but defence
    // in depth — a stray number shouldn't crash the adapter.
    const out = normalizeHeaders({
      "x-num": 42 as unknown as string,
    });
    expect(out["x-num"]).toBe("42");
  });
});


// ---------------------------------------------------------------------------
// 2. coerceBodyForSurface
// ---------------------------------------------------------------------------
describe("coerceBodyForSurface", () => {
  test("empty + non-multipart → null (matches default GET shape)", () => {
    expect(coerceBodyForSurface(Buffer.alloc(0), "text/plain")).toBeNull();
  });

  test("empty + multipart → empty Buffer (NOT null)", () => {
    const out = coerceBodyForSurface(Buffer.alloc(0), MULTIPART_PREFIX);
    expect(Buffer.isBuffer(out)).toBe(true);
    expect((out as Buffer).length).toBe(0);
  });

  test("multipart/form-data; boundary=... → Buffer", () => {
    const bytes = Buffer.from("--boundary\r\n");
    const out = coerceBodyForSurface(
      bytes,
      "multipart/form-data; boundary=abc",
    );
    expect(Buffer.isBuffer(out)).toBe(true);
    expect((out as Buffer).equals(bytes)).toBe(true);
  });

  test("form-urlencoded → UTF-8 string", () => {
    const out = coerceBodyForSurface(
      Buffer.from("name=Alice", "utf8"),
      "application/x-www-form-urlencoded",
    );
    expect(typeof out).toBe("string");
    expect(out).toBe("name=Alice");
  });

  test("UTF-8 multibyte bytes round-trip through string coercion", () => {
    const text = "café";
    const out = coerceBodyForSurface(
      Buffer.from(text, "utf8"),
      "text/plain",
    );
    expect(out).toBe(text);
  });

  test("JSON content-type still coerces to string (caller parses)", () => {
    const out = coerceBodyForSurface(
      Buffer.from('{"a":1}', "utf8"),
      "application/json",
    );
    expect(out).toBe('{"a":1}');
  });

  test("multipart match is case-insensitive (Content-Type capitalisation)", () => {
    const bytes = Buffer.from("body");
    const out = coerceBodyForSurface(
      bytes,
      "MULTIPART/FORM-DATA; boundary=abc",
    );
    expect(Buffer.isBuffer(out)).toBe(true);
  });
});


// ---------------------------------------------------------------------------
// 3. readRequestBody
// ---------------------------------------------------------------------------
describe("readRequestBody", () => {
  test("concatenates Buffer chunks in order", async () => {
    const stream = Readable.from([
      Buffer.from("hel"),
      Buffer.from("lo "),
      Buffer.from("world"),
    ]);
    const body = await readRequestBody(
      stream as unknown as import("node:http").IncomingMessage,
    );
    expect(body.toString("utf8")).toBe("hello world");
  });

  test("coerces string chunks into Buffer", async () => {
    const stream = Readable.from(["alpha", "beta"]);
    const body = await readRequestBody(
      stream as unknown as import("node:http").IncomingMessage,
    );
    expect(Buffer.isBuffer(body)).toBe(true);
    expect(body.toString("utf8")).toBe("alphabeta");
  });

  test("empty stream → empty Buffer", async () => {
    const stream = Readable.from([] as Buffer[]);
    const body = await readRequestBody(
      stream as unknown as import("node:http").IncomingMessage,
    );
    expect(Buffer.isBuffer(body)).toBe(true);
    expect(body.length).toBe(0);
  });

  test("binary bytes preserved verbatim", async () => {
    const bytes = Buffer.from([0x00, 0x01, 0xff, 0xfe]);
    const stream = Readable.from([bytes]);
    const body = await readRequestBody(
      stream as unknown as import("node:http").IncomingMessage,
    );
    expect(body.equals(bytes)).toBe(true);
  });
});


// ---------------------------------------------------------------------------
// 4. buildSurfaceRequest
// ---------------------------------------------------------------------------
describe("buildSurfaceRequest", () => {
  test("populates path, method, headers, body for a plain GET", () => {
    const req = fakeIncomingMessage({
      method:  "GET",
      url:     "/web-surface/v0.2/home",
      headers: { accept: "text/html" },
    });
    const surface = buildSurfaceRequest(req, Buffer.alloc(0));
    expect(surface).toEqual({
      path:    "/web-surface/v0.2/home",
      method:  "GET",
      headers: { accept: "text/html" },
      body:    null,
    });
  });

  test("force-uppercases the method (defensive)", () => {
    const req = fakeIncomingMessage({ method: "post" });
    const out = buildSurfaceRequest(req, Buffer.alloc(0));
    expect(out.method).toBe("POST");
  });

  test("defaults missing url to '/'", () => {
    const req = fakeIncomingMessage({ method: "GET" });
    expect(buildSurfaceRequest(req, Buffer.alloc(0)).path).toBe("/");
  });

  test("defaults missing method to 'GET'", () => {
    const req = fakeIncomingMessage({});
    expect(buildSurfaceRequest(req, Buffer.alloc(0)).method).toBe("GET");
  });

  test("form POST routes body to string (matches classifier expectation)", () => {
    const req = fakeIncomingMessage({
      method:  "POST",
      url:     "/form_demo",
      headers: { "content-type": "application/x-www-form-urlencoded" },
    });
    const out = buildSurfaceRequest(req, Buffer.from("name=Alice"));
    expect(out.body).toBe("name=Alice");
  });

  test("multipart POST routes body to Buffer (matches classifier expectation)", () => {
    const req = fakeIncomingMessage({
      method:  "POST",
      url:     "/upload_demo",
      headers: { "content-type": "multipart/form-data; boundary=abc" },
    });
    const bytes = Buffer.from("--abc\r\n");
    const out = buildSurfaceRequest(req, bytes);
    expect(Buffer.isBuffer(out.body)).toBe(true);
    expect((out.body as Buffer).equals(bytes)).toBe(true);
  });

  test("lowercased headers are accessible via the surface's lookup pattern", () => {
    const req = fakeIncomingMessage({
      method:  "GET",
      headers: { "Accept": "application/json", "X-Stream": "1" },
    });
    const out = buildSurfaceRequest(req, Buffer.alloc(0));
    expect(out.headers["accept"]).toBe("application/json");
    expect(out.headers["x-stream"]).toBe("1");
  });
});


// ---------------------------------------------------------------------------
// 5. writeSurfaceResponse / _responseBodyToBytes
// ---------------------------------------------------------------------------
describe("_responseBodyToBytes", () => {
  test("null → empty string", () => {
    expect(_responseBodyToBytes(null)).toBe("");
  });

  test("undefined → empty string", () => {
    expect(_responseBodyToBytes(undefined)).toBe("");
  });

  test("string passes through verbatim", () => {
    expect(_responseBodyToBytes("hello")).toBe("hello");
  });

  test("Buffer passes through verbatim", () => {
    const buf = Buffer.from([0x00, 0x01, 0xff]);
    const out = _responseBodyToBytes(buf);
    expect(Buffer.isBuffer(out)).toBe(true);
    expect((out as Buffer).equals(buf)).toBe(true);
  });

  test("Uint8Array (non-Buffer) gets wrapped", () => {
    const u8 = new Uint8Array([1, 2, 3]);
    const out = _responseBodyToBytes(u8);
    expect(Buffer.isBuffer(out)).toBe(true);
    expect(Array.from(out as Buffer)).toEqual([1, 2, 3]);
  });

  test("plain object → JSON.stringify", () => {
    expect(_responseBodyToBytes({ a: 1, b: "x" })).toBe('{"a":1,"b":"x"}');
  });

  test("array → JSON.stringify", () => {
    expect(_responseBodyToBytes([1, 2, 3])).toBe("[1,2,3]");
  });

  test("number → JSON.stringify", () => {
    expect(_responseBodyToBytes(42)).toBe("42");
  });
});


describe("writeSurfaceResponse", () => {
  test("writes status + headers + string body", () => {
    const { res, captured } = fakeServerResponse();
    const surfaceRes: WebSurfaceV0_2.Response = {
      status:  200,
      headers: { "content-type": "text/html; charset=utf-8" },
      body:    "<h1>ok</h1>",
    };
    writeSurfaceResponse(res, surfaceRes);
    expect(captured.status).toBe(200);
    expect(captured.headers).toEqual({
      "content-type": "text/html; charset=utf-8",
    });
    expect(captured.body).toBe("<h1>ok</h1>");
    expect(captured.endCalled).toBe(true);
  });

  test("JSON-encodes object bodies via _responseBodyToBytes", () => {
    const { res, captured } = fakeServerResponse();
    writeSurfaceResponse(res, {
      status:  200,
      headers: { "content-type": "application/json" },
      body:    { redirect: "/home" },
    });
    expect(captured.body).toBe('{"redirect":"/home"}');
  });

  test("writes Buffer bodies verbatim (asset path)", () => {
    const { res, captured } = fakeServerResponse();
    const buf = Buffer.from("body { font-family: sans-serif; }", "utf8");
    writeSurfaceResponse(res, {
      status:  200,
      headers: { "content-type": "text/css" },
      body:    buf,
    });
    expect(Buffer.isBuffer(captured.body)).toBe(true);
    expect((captured.body as Buffer).equals(buf)).toBe(true);
  });

  test("404 envelope shape passes through faithfully", () => {
    const { res, captured } = fakeServerResponse();
    writeSurfaceResponse(res, {
      status:  404,
      headers: { "content-type": "application/json" },
      body:    { error: "asset_not_found", detail: { pathname: "x.css" } },
    });
    expect(captured.status).toBe(404);
    expect(captured.body).toBe(
      '{"error":"asset_not_found","detail":{"pathname":"x.css"}}',
    );
  });

  test("does not mutate the surface Response object", () => {
    const { res } = fakeServerResponse();
    const surfaceRes: WebSurfaceV0_2.Response = {
      status:  200,
      headers: { "content-type": "text/html" },
      body:    "hi",
    };
    const frozen = JSON.stringify({
      status:  surfaceRes.status,
      headers: surfaceRes.headers,
      body:    surfaceRes.body,
    });
    writeSurfaceResponse(res, surfaceRes);
    expect(JSON.stringify({
      status:  surfaceRes.status,
      headers: surfaceRes.headers,
      body:    surfaceRes.body,
    })).toBe(frozen);
  });
});
