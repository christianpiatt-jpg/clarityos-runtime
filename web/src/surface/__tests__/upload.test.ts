// Card A16 — file uploads (multipart/form-data) tests.
//
// Six contract surfaces under test:
//
//   1. _splitBuffer (low-level Buffer scan):
//      * Splits on every occurrence of the delimiter.
//      * Returns N+1 chunks for N delimiters (preamble + parts
//        + epilogue).
//      * Handles delimiter at start / end / consecutive
//        delimiters (empty chunks).
//      * Empty body / no delimiter → single-chunk result.
//
//   2. parseMultipart:
//      * Single text field → fields populated, files empty.
//      * Single file upload → files populated, filename +
//        contentType + data preserved.
//      * Mixed text + file → both maps populated.
//      * Multiple files (different field names) → all surface.
//      * Default contentType (no Content-Type header) →
//        ``application/octet-stream``.
//      * Trailing CRLF stripped from file content (load-bearing
//        byte-integrity property).
//      * Binary bytes preserved exactly across a parse round-
//        trip.
//      * Malformed part (no Content-Disposition) → silently
//        skipped.
//      * Empty body / unknown boundary → empty maps.
//
//   3. Classifier — upload detection:
//      * POST + ``multipart/form-data; boundary=...`` + Buffer
//        body → upload action with extracted boundary.
//      * content-type ``multipart/form-data;\s*charset=utf-8;
//        boundary=...`` → still detected, boundary extracted
//        correctly.
//      * Quoted boundary (``boundary="abc"``) → extracted.
//      * Non-Buffer body → render(error_500).
//      * Missing boundary → render(error_500).
//      * Mode preserved (HTML default + Accept: application/json).
//      * GET never produces an upload action.
//      * Precedence: /redirect with multipart body classifies
//        as redirect (URL primitive wins).
//
//   4. Upload handler:
//      * Parses rawBody + boundary, dispatches via render
//        pipeline with ``params = {...fields, files}``.
//      * View reads ``ctx.params.files`` via the standard
//        params channel.
//      * Multiple files survive the handler.
//      * Does not mutate the action.
//
//   5. End-to-end (upload_demo round-trip):
//      * GET /upload_demo → empty form, empty metadata.
//      * POST single-file upload → metadata surfaces in HTML.
//      * Filename HTML-escaped at the view boundary.
//      * Standard layout wraps the response.
//      * JSON mode envelope carries the files map.
//
//   6. Determinism + non-mutation:
//      * Same multipart body → byte-identical HTML across
//        renders.
//      * Router / handler do not mutate the request or the
//        registry.
//      * File bytes round-trip through ctx.params unchanged.
//
// Path: web/src/surface/__tests__/upload.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  parseMultipart,
  _splitBuffer,
  UploadedFile,
} from "../multipartParser";
import { handleUpload } from "../uploadHandler";
import { routeWebSurface } from "../router";
import { renderWebSurface } from "../renderer";
import {
  classifyWebSurfaceRequest,
  _extractMultipartBoundary,
  ERROR_500_VIEW,
  MULTIPART_FORM_DATA_CONTENT_TYPE,
} from "../classifier";
import { WebSurfaceV0_2_View as V } from "../viewContract";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import {
  registerView,
  _clearViewRegistryForTests,
  _listRegisteredViewsForTests,
} from "../viewRegistry";
import { clearTemplateCache } from "../templateCache";
import { clearLayoutCache } from "../layoutCache";
import { clearPartialCache } from "../partialCache";
import { clearAssetManifest } from "../assetManifest";
import { homeView } from "../views/home";
import { error404View, error500View } from "../views/errors";
import { uploadDemoView } from "../views/uploadDemo";


// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

interface TextPart {
  kind: "text";
  name: string;
  value: string;
}
interface FilePart {
  kind: "file";
  name: string;
  filename: string;
  contentType?: string;
  data: Buffer;
}

type PartSpec = TextPart | FilePart;


/**
 * Build a multipart/form-data body from a list of parts.
 * Returns the body Buffer + the boundary string so tests don't
 * have to maintain them in lock-step.
 */
function buildMultipart(
  parts: PartSpec[],
  boundary = "----TestBoundary_a1B2c3",
): { body: Buffer; boundary: string } {
  const chunks: Buffer[] = [];
  for (const part of parts) {
    chunks.push(Buffer.from(`--${boundary}\r\n`));
    if (part.kind === "text") {
      chunks.push(Buffer.from(
        `Content-Disposition: form-data; name="${part.name}"\r\n\r\n` +
        `${part.value}\r\n`,
      ));
    } else {
      const ct = part.contentType ?? "application/octet-stream";
      chunks.push(Buffer.from(
        `Content-Disposition: form-data; name="${part.name}"; ` +
        `filename="${part.filename}"\r\n` +
        `Content-Type: ${ct}\r\n\r\n`,
      ));
      chunks.push(part.data);
      chunks.push(Buffer.from("\r\n"));
    }
  }
  chunks.push(Buffer.from(`--${boundary}--\r\n`));
  return { body: Buffer.concat(chunks), boundary };
}


function reqOf(
  overrides: Partial<WebSurfaceV0_2.Request> = {},
): WebSurfaceV0_2.Request {
  return {
    path:    "/",
    method:  "GET",
    headers: {},
    body:    null,
    ...overrides,
  };
}


function uploadReq(
  path: string,
  parts: PartSpec[],
  extra: Partial<WebSurfaceV0_2.Request> = {},
  boundary = "----TestBoundary_a1B2c3",
): WebSurfaceV0_2.Request {
  const { body, boundary: actualBoundary } = buildMultipart(parts, boundary);
  const { headers: extraHeaders, ...rest } = extra;
  return {
    path,
    method: "POST",
    body,
    ...rest,
    headers: {
      "content-type":
        `${MULTIPART_FORM_DATA_CONTENT_TYPE}; boundary=${actualBoundary}`,
      ...(extraHeaders ?? {}),
    },
  };
}


beforeEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
  registerView("home",         homeView);
  registerView("error_404",    error404View);
  registerView("error_500",    error500View);
  registerView("upload_demo",  uploadDemoView);
});

afterEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
});


// ---------------------------------------------------------------------------
// 1. _splitBuffer
// ---------------------------------------------------------------------------
describe("_splitBuffer", () => {
  test("single delimiter → two chunks (pre + post)", () => {
    const parts = _splitBuffer(
      Buffer.from("AAA|BBB"),
      Buffer.from("|"),
    );
    expect(parts).toHaveLength(2);
    expect(parts[0].toString()).toBe("AAA");
    expect(parts[1].toString()).toBe("BBB");
  });

  test("multiple delimiters → N+1 chunks", () => {
    const parts = _splitBuffer(
      Buffer.from("A|B|C|D"),
      Buffer.from("|"),
    );
    expect(parts).toHaveLength(4);
    expect(parts.map((p) => p.toString())).toEqual(["A", "B", "C", "D"]);
  });

  test("delimiter at start → empty leading chunk", () => {
    const parts = _splitBuffer(
      Buffer.from("|A|B"),
      Buffer.from("|"),
    );
    expect(parts).toHaveLength(3);
    expect(parts[0].length).toBe(0);
    expect(parts[1].toString()).toBe("A");
    expect(parts[2].toString()).toBe("B");
  });

  test("delimiter at end → empty trailing chunk", () => {
    const parts = _splitBuffer(
      Buffer.from("A|B|"),
      Buffer.from("|"),
    );
    expect(parts).toHaveLength(3);
    expect(parts[2].length).toBe(0);
  });

  test("no delimiter → single-chunk result", () => {
    const parts = _splitBuffer(
      Buffer.from("hello"),
      Buffer.from("|"),
    );
    expect(parts).toHaveLength(1);
    expect(parts[0].toString()).toBe("hello");
  });

  test("empty body → single empty chunk", () => {
    const parts = _splitBuffer(Buffer.alloc(0), Buffer.from("|"));
    expect(parts).toHaveLength(1);
    expect(parts[0].length).toBe(0);
  });

  test("multi-byte delimiter scans correctly", () => {
    const parts = _splitBuffer(
      Buffer.from("AAA--BBB--CCC"),
      Buffer.from("--"),
    );
    expect(parts.map((p) => p.toString())).toEqual(["AAA", "BBB", "CCC"]);
  });
});


// ---------------------------------------------------------------------------
// 2. parseMultipart
// ---------------------------------------------------------------------------
describe("parseMultipart", () => {
  test("single text field", () => {
    const { body, boundary } = buildMultipart([
      { kind: "text", name: "name", value: "Alice" },
    ]);
    const result = parseMultipart(body, boundary);
    expect(result.fields).toEqual({ name: "Alice" });
    expect(result.files).toEqual({});
  });

  test("single file upload", () => {
    const fileBytes = Buffer.from("hello world", "utf8");
    const { body, boundary } = buildMultipart([
      {
        kind:        "file",
        name:        "file",
        filename:    "hello.txt",
        contentType: "text/plain",
        data:        fileBytes,
      },
    ]);
    const result = parseMultipart(body, boundary);
    expect(result.fields).toEqual({});
    expect(Object.keys(result.files)).toEqual(["file"]);
    const f = result.files["file"];
    expect(f.filename).toBe("hello.txt");
    expect(f.contentType).toBe("text/plain");
    expect(Buffer.from(f.data).toString("utf8")).toBe("hello world");
  });

  test("mixed text + file", () => {
    const { body, boundary } = buildMultipart([
      { kind: "text", name: "name", value: "Alice" },
      {
        kind:        "file",
        name:        "avatar",
        filename:    "av.png",
        contentType: "image/png",
        data:        Buffer.from("PNGDATA"),
      },
    ]);
    const result = parseMultipart(body, boundary);
    expect(result.fields).toEqual({ name: "Alice" });
    expect(Object.keys(result.files)).toEqual(["avatar"]);
    expect(result.files["avatar"].contentType).toBe("image/png");
  });

  test("multiple files (different field names)", () => {
    const { body, boundary } = buildMultipart([
      {
        kind:     "file",
        name:     "a",
        filename: "a.bin",
        data:     Buffer.from([1, 2, 3]),
      },
      {
        kind:     "file",
        name:     "b",
        filename: "b.bin",
        data:     Buffer.from([4, 5, 6, 7]),
      },
    ]);
    const result = parseMultipart(body, boundary);
    expect(Object.keys(result.files).sort()).toEqual(["a", "b"]);
    expect(result.files["a"].data.length).toBe(3);
    expect(result.files["b"].data.length).toBe(4);
  });

  test("default contentType when header missing", () => {
    // Manually build a part without Content-Type to bypass the
    // helper's default — we want to exercise the parser's
    // ``application/octet-stream`` fallback.
    const boundary = "BOUNDARY";
    const body = Buffer.concat([
      Buffer.from(`--${boundary}\r\n`),
      Buffer.from(
        `Content-Disposition: form-data; name="x"; filename="x.bin"\r\n\r\n`,
      ),
      Buffer.from([0xAA, 0xBB]),
      Buffer.from(`\r\n--${boundary}--\r\n`),
    ]);
    const result = parseMultipart(body, boundary);
    expect(result.files["x"].contentType).toBe("application/octet-stream");
  });

  test("trailing CRLF is stripped from file content (byte-integrity)", () => {
    // Load-bearing: the framing ``\r\n`` between content and the
    // next boundary must NOT end up appended to the file's data.
    const fileBytes = Buffer.from("exactly-11b", "utf8");
    expect(fileBytes.length).toBe(11);
    const { body, boundary } = buildMultipart([
      {
        kind:     "file",
        name:     "file",
        filename: "f.txt",
        data:     fileBytes,
      },
    ]);
    const result = parseMultipart(body, boundary);
    expect(result.files["file"].data.length).toBe(11);
    expect(Buffer.from(result.files["file"].data).equals(fileBytes)).toBe(true);
  });

  test("binary bytes preserved exactly across parse round-trip", () => {
    // Bytes including 0x00, 0x0d (CR), 0x0a (LF), and high values.
    const fileBytes = Buffer.from([
      0x00, 0x01, 0x0d, 0x0a, 0xfe, 0xff, 0x42, 0x00, 0x80,
    ]);
    const { body, boundary } = buildMultipart([
      {
        kind:     "file",
        name:     "blob",
        filename: "blob.bin",
        data:     fileBytes,
      },
    ]);
    const result = parseMultipart(body, boundary);
    const got = Buffer.from(result.files["blob"].data);
    expect(got.equals(fileBytes)).toBe(true);
  });

  test("malformed part (no Content-Disposition) is skipped", () => {
    const boundary = "B";
    const body = Buffer.concat([
      Buffer.from(`--${boundary}\r\n`),
      Buffer.from("X-Garbage: yes\r\n\r\n"),
      Buffer.from("ignored"),
      Buffer.from(`\r\n--${boundary}\r\n`),
      Buffer.from(`Content-Disposition: form-data; name="ok"\r\n\r\n`),
      Buffer.from("kept\r\n"),
      Buffer.from(`--${boundary}--\r\n`),
    ]);
    const result = parseMultipart(body, boundary);
    expect(result.fields).toEqual({ ok: "kept" });
    expect(result.files).toEqual({});
  });

  test("empty body → empty maps", () => {
    expect(parseMultipart(Buffer.alloc(0), "anything")).toEqual({
      fields: {},
      files:  {},
    });
  });

  test("body that doesn't contain the boundary → empty maps", () => {
    expect(parseMultipart(Buffer.from("no-boundary-here"), "B")).toEqual({
      fields: {},
      files:  {},
    });
  });

  test("returns fresh maps per call (no shared mutation surface)", () => {
    const { body, boundary } = buildMultipart([
      { kind: "text", name: "k", value: "v" },
    ]);
    const a = parseMultipart(body, boundary);
    const b = parseMultipart(body, boundary);
    expect(a).toEqual(b);
    expect(a).not.toBe(b);
    expect(a.fields).not.toBe(b.fields);
    expect(a.files).not.toBe(b.files);
  });
});


// ---------------------------------------------------------------------------
// 3. Classifier — upload detection
// ---------------------------------------------------------------------------
describe("classifier — upload detection", () => {
  test("POST + multipart/form-data + Buffer body → upload action", () => {
    const req = uploadReq("/upload_demo", [
      { kind: "text", name: "k", value: "v" },
    ]);
    const action = classifyWebSurfaceRequest(req);
    expect(action.kind).toBe("upload");
    if (action.kind === "upload") {
      expect(action.view).toBe("upload_demo");
      expect(action.boundary).toBe("----TestBoundary_a1B2c3");
      expect(action.mode).toBe(V.Mode.html);
      expect(Buffer.isBuffer(action.rawBody)).toBe(true);
    }
  });

  test("mode preserved through Accept: application/json", () => {
    const req = uploadReq("/upload_demo", [
      { kind: "text", name: "k", value: "v" },
    ], { headers: { accept: "application/json" } });
    const action = classifyWebSurfaceRequest(req);
    expect(action.kind).toBe("upload");
    if (action.kind === "upload") {
      expect(action.mode).toBe(V.Mode.json);
    }
  });

  test("content-type with charset BEFORE boundary still detected", () => {
    const { body, boundary } = buildMultipart([
      { kind: "text", name: "k", value: "v" },
    ]);
    const req = reqOf({
      path:   "/upload_demo",
      method: "POST",
      body,
      headers: {
        "content-type":
          `multipart/form-data; charset=utf-8; boundary=${boundary}`,
      },
    });
    const action = classifyWebSurfaceRequest(req);
    expect(action.kind).toBe("upload");
    if (action.kind === "upload") {
      expect(action.boundary).toBe(boundary);
    }
  });

  test("quoted boundary value is extracted", () => {
    const { body, boundary } = buildMultipart([
      { kind: "text", name: "k", value: "v" },
    ], "qb-1");
    const req = reqOf({
      path:   "/upload_demo",
      method: "POST",
      body,
      headers: {
        "content-type": `multipart/form-data; boundary="${boundary}"`,
      },
    });
    const action = classifyWebSurfaceRequest(req);
    if (action.kind !== "upload") throw new Error("expected upload");
    expect(action.boundary).toBe(boundary);
  });

  test("non-Buffer body → render(error_500)", () => {
    const req = reqOf({
      path:    "/upload_demo",
      method:  "POST",
      body:    "looks-like-form-but-isnt-a-buffer",
      headers: { "content-type": "multipart/form-data; boundary=abc" },
    });
    const action = classifyWebSurfaceRequest(req);
    expect(action.kind).toBe("render");
    if (action.kind === "render") {
      expect(action.view).toBe(ERROR_500_VIEW);
      expect((action.params as { message: string }).message)
        .toContain("must be a Buffer");
    }
  });

  test("missing boundary in content-type → render(error_500)", () => {
    const req = reqOf({
      path:    "/upload_demo",
      method:  "POST",
      body:    Buffer.from("ignored"),
      headers: { "content-type": "multipart/form-data" },
    });
    const action = classifyWebSurfaceRequest(req);
    expect(action.kind).toBe("render");
    if (action.kind === "render") {
      expect(action.view).toBe(ERROR_500_VIEW);
      expect((action.params as { message: string }).message)
        .toContain("missing a boundary");
    }
  });

  test("empty boundary value → render(error_500)", () => {
    const req = reqOf({
      path:    "/upload_demo",
      method:  "POST",
      body:    Buffer.from("ignored"),
      headers: { "content-type": "multipart/form-data; boundary=" },
    });
    const action = classifyWebSurfaceRequest(req);
    expect(action.kind).toBe("render");
    if (action.kind === "render") {
      expect(action.view).toBe(ERROR_500_VIEW);
    }
  });

  test("GET with multipart content-type never produces upload", () => {
    const req = reqOf({
      path:    "/upload_demo",
      method:  "GET",
      headers: { "content-type": "multipart/form-data; boundary=abc" },
      body:    null,
    });
    const action = classifyWebSurfaceRequest(req);
    expect(action.kind).not.toBe("upload");
  });

  test("precedence: /redirect with multipart body still classifies as redirect", () => {
    const { body, boundary } = buildMultipart([
      { kind: "text", name: "k", value: "v" },
    ]);
    const req = reqOf({
      path:    "/redirect?to=/foo",
      method:  "POST",
      body,
      headers: {
        "content-type": `multipart/form-data; boundary=${boundary}`,
      },
    });
    const action = classifyWebSurfaceRequest(req);
    expect(action.kind).toBe("redirect");
  });

  test("_extractMultipartBoundary helper", () => {
    expect(_extractMultipartBoundary("multipart/form-data; boundary=abc"))
      .toBe("abc");
    expect(_extractMultipartBoundary("multipart/form-data; boundary=\"abc\""))
      .toBe("abc");
    expect(_extractMultipartBoundary("multipart/form-data; charset=utf-8; boundary=xyz"))
      .toBe("xyz");
    expect(_extractMultipartBoundary("multipart/form-data; BOUNDARY=upper"))
      .toBe("upper");
    expect(_extractMultipartBoundary("multipart/form-data"))
      .toBeNull();
    expect(_extractMultipartBoundary("multipart/form-data; boundary="))
      .toBeNull();
  });
});


// ---------------------------------------------------------------------------
// 4. Upload handler
// ---------------------------------------------------------------------------
describe("handleUpload", () => {
  test("dispatches via render pipeline with files map", async () => {
    const { body, boundary } = buildMultipart([
      { kind: "text", name: "name", value: "Alice" },
      {
        kind:     "file",
        name:     "file",
        filename: "hello.txt",
        contentType: "text/plain",
        data:     Buffer.from("hello world"),
      },
    ]);
    const res = await handleUpload({
      kind:     "upload",
      view:     "upload_demo",
      rawBody:  body,
      boundary,
      mode:     V.Mode.html,
    });
    expect(res.status).toBe(200);
    const html = res.body as string;
    expect(html).toContain("Filename: hello.txt");
    expect(html).toContain("Type: text/plain");
    expect(html).toContain("Size: 11 bytes");
  });

  test("custom view sees files via ctx.params.files", async () => {
    let seen: Record<string, UploadedFile> | undefined;
    registerView("upload_probe", {
      template: "base",
      async render(ctx) {
        seen = (ctx.params as { files?: Record<string, UploadedFile> })?.files;
        return { title: "x", content: "" };
      },
    });
    const { body, boundary } = buildMultipart([
      {
        kind:     "file",
        name:     "doc",
        filename: "doc.txt",
        data:     Buffer.from("abc"),
      },
    ]);
    await handleUpload({
      kind:    "upload",
      view:    "upload_probe",
      rawBody: body,
      boundary,
      mode:    V.Mode.html,
    });
    expect(seen).toBeDefined();
    expect(Object.keys(seen!)).toEqual(["doc"]);
    expect(seen!["doc"].filename).toBe("doc.txt");
    expect(Buffer.from(seen!["doc"].data).toString("utf8")).toBe("abc");
  });

  test("does not mutate the input action", async () => {
    const { body, boundary } = buildMultipart([
      { kind: "text", name: "k", value: "v" },
    ]);
    const action = {
      kind:    "upload" as const,
      view:    "upload_demo",
      rawBody: body,
      boundary,
      mode:    V.Mode.html,
    };
    // Capture pre-state. Buffer equality is checked separately.
    const preBytes = Buffer.from(action.rawBody);
    const preMeta = JSON.stringify({
      kind: action.kind, view: action.view,
      boundary: action.boundary, mode: action.mode,
    });
    await handleUpload(action);
    expect(action.rawBody.equals(preBytes)).toBe(true);
    expect(JSON.stringify({
      kind: action.kind, view: action.view,
      boundary: action.boundary, mode: action.mode,
    })).toBe(preMeta);
  });

  test("JSON mode returns the canonical envelope with files key", async () => {
    const { body, boundary } = buildMultipart([
      {
        kind:     "file",
        name:     "file",
        filename: "x.txt",
        data:     Buffer.from("abc"),
      },
    ]);
    const res = await handleUpload({
      kind:    "upload",
      view:    "upload_demo",
      rawBody: body,
      boundary,
      mode:    V.Mode.json,
    });
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("application/json");
    const envBody = res.body as {
      view: string;
      params: { files: Record<string, UploadedFile> };
    };
    expect(envBody.view).toBe("upload_demo");
    expect(Object.keys(envBody.params.files)).toEqual(["file"]);
    expect(envBody.params.files["file"].filename).toBe("x.txt");
  });
});


// ---------------------------------------------------------------------------
// 5. End-to-end (upload_demo round-trip)
// ---------------------------------------------------------------------------
describe("routeWebSurface — upload_demo round-trip", () => {
  test("GET /upload_demo → empty form, empty metadata block", async () => {
    const res = await routeWebSurface(reqOf({ path: "/upload_demo" }));
    expect(res.status).toBe(200);
    const html = res.body as string;
    expect(html).toContain("<h1>Upload Demo</h1>");
    expect(html).toContain('enctype="multipart/form-data"');
    expect(html).toContain("Filename: </p>");
    expect(html).toContain("Type: </p>");
    expect(html).toContain("Size: 0 bytes");
  });

  test("POST single-file upload surfaces metadata in HTML", async () => {
    const res = await routeWebSurface(uploadReq("/upload_demo", [
      {
        kind:        "file",
        name:        "file",
        filename:    "report.txt",
        contentType: "text/plain",
        data:        Buffer.from("hello world"),
      },
    ]));
    expect(res.status).toBe(200);
    const html = res.body as string;
    expect(html).toContain("Filename: report.txt");
    expect(html).toContain("Type: text/plain");
    expect(html).toContain("Size: 11 bytes");
  });

  test("hostile filename is HTML-escaped in the metadata block", async () => {
    // No embedded ``"`` — that would break out of the multipart
    // ``filename="..."`` field at parse time (real browsers
    // escape these per RFC 7578). What we DO test is that a
    // filename containing HTML-significant characters survives
    // the parse and is then HTML-escaped at the view boundary
    // before substitution into the template.
    const hostile = "<script>alert(1)</script>";
    const res = await routeWebSurface(uploadReq("/upload_demo", [
      {
        kind:        "file",
        name:        "file",
        filename:    hostile,
        contentType: "text/plain",
        data:        Buffer.from("x"),
      },
    ]));
    const html = res.body as string;
    expect(html).not.toContain('<script>alert(1)</script>');
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
  });

  test("POST is wrapped in the standard layout", async () => {
    const res = await routeWebSurface(uploadReq("/upload_demo", [
      { kind: "text", name: "k", value: "v" },
    ]));
    const html = res.body as string;
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain('<div id="layout">');
    expect(html).toContain("<header>");
    expect(html).toContain("<footer>");
  });

  test("non-Buffer body routes through error_500 end-to-end", async () => {
    const res = await routeWebSurface(reqOf({
      path:    "/upload_demo",
      method:  "POST",
      headers: { "content-type": "multipart/form-data; boundary=abc" },
      body:    "looks-like-form-but-isnt-a-buffer",
    }));
    expect(res.status).toBe(500);
    const html = res.body as string;
    expect(html).toContain("Internal Error");
    expect(html).toContain("must be a Buffer");
  });

  test("JSON mode end-to-end carries the files envelope", async () => {
    const res = await routeWebSurface(uploadReq("/upload_demo", [
      {
        kind:     "file",
        name:     "file",
        filename: "x.txt",
        contentType: "text/plain",
        data:     Buffer.from("abc"),
      },
    ], { headers: { accept: "application/json" } }));
    expect(res.headers["content-type"]).toBe("application/json");
    const envBody = res.body as {
      view: string;
      params: { files: Record<string, UploadedFile> };
    };
    expect(envBody.view).toBe("upload_demo");
    expect(envBody.params.files["file"].filename).toBe("x.txt");
  });
});


// ---------------------------------------------------------------------------
// 6. Determinism + non-mutation
// ---------------------------------------------------------------------------
describe("upload — determinism + non-mutation", () => {
  test("same multipart body → byte-identical HTML across 5 renders", async () => {
    const reqFactory = () => uploadReq("/upload_demo", [
      {
        kind:     "file",
        name:     "file",
        filename: "x.txt",
        data:     Buffer.from("hello"),
      },
    ]);
    const outs: string[] = [];
    for (let i = 0; i < 5; i++) {
      const r = await routeWebSurface(reqFactory());
      outs.push(r.body as string);
    }
    for (let i = 1; i < outs.length; i++) {
      expect(outs[i]).toBe(outs[0]);
    }
  });

  test("router does not mutate the input request", async () => {
    const req = uploadReq("/upload_demo", [
      { kind: "text", name: "k", value: "v" },
    ]);
    const preBody = Buffer.from(req.body as Buffer);
    const preMeta = JSON.stringify({
      path: req.path, method: req.method, headers: req.headers,
    });
    await routeWebSurface(req);
    expect((req.body as Buffer).equals(preBody)).toBe(true);
    expect(JSON.stringify({
      path: req.path, method: req.method, headers: req.headers,
    })).toBe(preMeta);
  });

  test("upload pathway does not register or unregister views", async () => {
    const before = _listRegisteredViewsForTests().slice().sort();
    await routeWebSurface(uploadReq("/upload_demo", [
      { kind: "text", name: "k", value: "v" },
    ]));
    await routeWebSurface(uploadReq("/upload_demo", [
      {
        kind:     "file",
        name:     "file",
        filename: "x.txt",
        data:     Buffer.from("bytes"),
      },
    ]));
    const after = _listRegisteredViewsForTests().slice().sort();
    expect(after).toEqual(before);
  });

  test("file bytes round-trip through ctx.params unchanged", async () => {
    const bytes = Buffer.from([0x00, 0x01, 0xfe, 0xff, 0x0d, 0x0a]);
    let seen: UploadedFile | undefined;
    registerView("upload_byte_probe", {
      template: "base",
      async render(ctx) {
        const files =
          (ctx.params as { files?: Record<string, UploadedFile> })?.files;
        seen = files?.["file"];
        return { title: "x", content: "" };
      },
    });
    await routeWebSurface(uploadReq("/upload_byte_probe", [
      {
        kind:     "file",
        name:     "file",
        filename: "raw.bin",
        data:     bytes,
      },
    ]));
    expect(seen).toBeDefined();
    expect(Buffer.from(seen!.data).equals(bytes)).toBe(true);
  });

  test("renderer does not mutate ctx", async () => {
    const ctx = {
      view: "upload_demo",
      params: {
        files: {
          file: {
            filename:    "x.txt",
            contentType: "text/plain",
            data:        new Uint8Array([97, 98, 99]),
          },
        },
      },
      mode: V.Mode.html,
    };
    // The Uint8Array is a binary buffer that JSON.stringify
    // doesn't serialise meaningfully; compare meta + raw bytes
    // separately.
    const fileBefore = new Uint8Array(ctx.params.files.file.data);
    const metaBefore = JSON.stringify({
      view:     ctx.view,
      mode:     ctx.mode,
      filename: ctx.params.files.file.filename,
      ct:       ctx.params.files.file.contentType,
    });
    await renderWebSurface(ctx);
    expect(JSON.stringify({
      view:     ctx.view,
      mode:     ctx.mode,
      filename: ctx.params.files.file.filename,
      ct:       ctx.params.files.file.contentType,
    })).toBe(metaBefore);
    expect(Array.from(ctx.params.files.file.data))
      .toEqual(Array.from(fileBefore));
  });

  test("upload handler is deterministic — same body → same parsed result", async () => {
    const { body, boundary } = buildMultipart([
      { kind: "text", name: "k", value: "v" },
      {
        kind:     "file",
        name:     "file",
        filename: "x.txt",
        data:     Buffer.from("abc"),
      },
    ]);
    const a = await handleUpload({
      kind: "upload", view: "upload_demo",
      rawBody: body, boundary, mode: V.Mode.json,
    });
    const b = await handleUpload({
      kind: "upload", view: "upload_demo",
      rawBody: body, boundary, mode: V.Mode.json,
    });
    expect(a.status).toBe(b.status);
    expect(a.headers).toEqual(b.headers);
    // JSON bodies are objects — deep equal them.
    expect(a.body).toEqual(b.body);
  });
});
