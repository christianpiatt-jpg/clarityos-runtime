// Card A23-R — server-side status surface tests.
//
// Four contract surfaces under test:
//
//   1. types — StatusKind closed union; STATUS_TEMPLATE_NAMES
//      mapping correctness.
//   2. escapeHtml — five HTML-sensitive characters; & first.
//   3. renderStatusSurface — picks the right template per
//      kind; injects the (escaped) message; output carries
//      the static chrome (h2 label, data-status-surface
//      attribute); determinism + non-mutation.
//   4. handleStatus (route handler) — POST-only; JSON parse
//      gate; payload validation; 200 on success, 400 on bad
//      input but body is still the failure-surface HTML; no
//      JSON responses ever.
//
// Path: web/src/surface/__tests__/statusRender.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  renderStatusSurface,
  STATUS_TEMPLATE_NAMES,
  escapeHtml,
  type StatusKind,
  type StatusPayload,
} from "../status";
import {
  STATUS_PATH,
  handleStatus,
  _coercePayload,
} from "../../server/routes/status";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import { clearTemplateCache } from "../templateCache";
import { clearLayoutCache } from "../layoutCache";
import { clearPartialCache } from "../partialCache";
import { clearAssetManifest } from "../assetManifest";


function req(opts: Partial<WebSurfaceV0_2.Request> = {}): WebSurfaceV0_2.Request {
  return {
    path:    "/__status",
    method:  "POST",
    headers: { "content-type": "application/json" },
    body:    "",
    ...opts,
  };
}


beforeEach(() => {
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
});

afterEach(() => {
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
});


// ---------------------------------------------------------------------------
// 1. Constants + mapping
// ---------------------------------------------------------------------------
describe("constants + mapping", () => {
  test("STATUS_PATH is the literal /__status", () => {
    expect(STATUS_PATH).toBe("/__status");
  });

  test("STATUS_TEMPLATE_NAMES covers all three kinds", () => {
    expect(STATUS_TEMPLATE_NAMES.success).toBe("statusSuccess");
    expect(STATUS_TEMPLATE_NAMES.warning).toBe("statusWarning");
    expect(STATUS_TEMPLATE_NAMES.failure).toBe("statusFailure");
  });

  test("STATUS_TEMPLATE_NAMES has exactly three entries", () => {
    expect(Object.keys(STATUS_TEMPLATE_NAMES).sort()).toEqual([
      "failure",
      "success",
      "warning",
    ]);
  });
});


// ---------------------------------------------------------------------------
// 2. escapeHtml — boundary escape
// ---------------------------------------------------------------------------
describe("escapeHtml", () => {
  test("escapes the five HTML-sensitive characters", () => {
    expect(escapeHtml("<")).toBe("&lt;");
    expect(escapeHtml(">")).toBe("&gt;");
    expect(escapeHtml("&")).toBe("&amp;");
    expect(escapeHtml('"')).toBe("&quot;");
    expect(escapeHtml("'")).toBe("&#39;");
  });

  test("escapes & first so existing entities don't double-encode", () => {
    expect(escapeHtml("a & b < c")).toBe("a &amp; b &lt; c");
  });

  test("empty string passes through unchanged", () => {
    expect(escapeHtml("")).toBe("");
  });
});


// ---------------------------------------------------------------------------
// 3. renderStatusSurface — template selection + injection
// ---------------------------------------------------------------------------
describe("renderStatusSurface — per-kind output", () => {
  test("success → success template chrome + label", async () => {
    const html = await renderStatusSurface({
      kind: "success",
      message: "Saved.",
    });
    expect(html).toContain('data-status-surface="success"');
    expect(html).toContain("status-surface--success");
    expect(html).toContain("<h2>Success</h2>");
    expect(html).toContain('<p data-status-message>Saved.</p>');
  });

  test("warning → warning template chrome + label", async () => {
    const html = await renderStatusSurface({
      kind: "warning",
      message: "Be careful.",
    });
    expect(html).toContain('data-status-surface="warning"');
    expect(html).toContain("status-surface--warning");
    expect(html).toContain("<h2>Warning</h2>");
    expect(html).toContain('<p data-status-message>Be careful.</p>');
  });

  test("failure → failure template chrome + label", async () => {
    const html = await renderStatusSurface({
      kind: "failure",
      message: "Broken.",
    });
    expect(html).toContain('data-status-surface="failure"');
    expect(html).toContain("status-surface--failure");
    expect(html).toContain("<h2>Failure</h2>");
    expect(html).toContain('<p data-status-message>Broken.</p>');
  });

  test("HTML-escapes the message (defence-in-depth)", async () => {
    const html = await renderStatusSurface({
      kind: "warning",
      message: '"><script>alert(1)</script>',
    });
    expect(html).not.toContain("<script>alert(1)</script>");
    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(html).toContain("&quot;");
  });

  test("empty message → empty <p> but valid fragment", async () => {
    const html = await renderStatusSurface({
      kind: "success",
      message: "",
    });
    expect(html).toContain('<p data-status-message></p>');
    expect(html).toContain('<h2>Success</h2>');
  });
});


describe("renderStatusSurface — determinism + non-mutation", () => {
  test("same payload → byte-identical HTML across 5 renders", async () => {
    const payload: StatusPayload = {
      kind: "success", message: "ok",
    };
    const outs: string[] = [];
    for (let i = 0; i < 5; i++) {
      outs.push(await renderStatusSurface(payload));
    }
    for (let i = 1; i < outs.length; i++) {
      expect(outs[i]).toBe(outs[0]);
    }
  });

  test("does not mutate the input payload", async () => {
    const payload: StatusPayload = {
      kind: "warning", message: "watch out",
    };
    const frozen = JSON.stringify(payload);
    await renderStatusSurface(payload);
    expect(JSON.stringify(payload)).toBe(frozen);
  });
});


// ---------------------------------------------------------------------------
// 4. _coercePayload — input validation
// ---------------------------------------------------------------------------
describe("_coercePayload — validation table", () => {
  test("well-formed payload → returned as-is", () => {
    const out = _coercePayload({ kind: "success", message: "ok" });
    expect(out).toEqual({ kind: "success", message: "ok" });
  });

  test("each valid kind accepted", () => {
    for (const kind of ["success", "warning", "failure"] as StatusKind[]) {
      expect(_coercePayload({ kind, message: "x" })).toEqual({
        kind, message: "x",
      });
    }
  });

  test("missing kind → null", () => {
    expect(_coercePayload({ message: "x" })).toBeNull();
  });

  test("missing message → null", () => {
    expect(_coercePayload({ kind: "success" })).toBeNull();
  });

  test("unknown kind → null", () => {
    expect(_coercePayload({ kind: "info", message: "x" })).toBeNull();
  });

  test("non-string kind → null", () => {
    expect(_coercePayload({ kind: 1, message: "x" })).toBeNull();
  });

  test("non-string message → null", () => {
    expect(_coercePayload({ kind: "success", message: 1 })).toBeNull();
  });

  test("null → null", () => {
    expect(_coercePayload(null)).toBeNull();
  });

  test("non-object (string/number/array) → null", () => {
    expect(_coercePayload("x")).toBeNull();
    expect(_coercePayload(42)).toBeNull();
    expect(_coercePayload(["x"])).toBeNull();
  });

  test("empty-string message accepted (valid shape)", () => {
    expect(_coercePayload({ kind: "success", message: "" })).toEqual({
      kind: "success", message: "",
    });
  });
});


// ---------------------------------------------------------------------------
// 5. handleStatus — route behaviour
// ---------------------------------------------------------------------------
describe("handleStatus — happy path", () => {
  test("POST + valid body → 200 + text/html + matching fragment", async () => {
    const response = await handleStatus(req({
      body: JSON.stringify({ kind: "success", message: "Saved." }),
    }));
    expect(response.status).toBe(200);
    expect(response.headers["content-type"]).toBe(
      "text/html; charset=utf-8",
    );
    const body = response.body as string;
    expect(body).toContain('data-status-surface="success"');
    expect(body).toContain('<p data-status-message>Saved.</p>');
  });

  test("warning kind → warning fragment", async () => {
    const response = await handleStatus(req({
      body: JSON.stringify({ kind: "warning", message: "Be careful." }),
    }));
    expect(response.status).toBe(200);
    expect(response.body as string).toContain(
      'data-status-surface="warning"',
    );
  });

  test("failure kind → failure fragment", async () => {
    const response = await handleStatus(req({
      body: JSON.stringify({ kind: "failure", message: "Broken." }),
    }));
    expect(response.status).toBe(200);
    expect(response.body as string).toContain(
      'data-status-surface="failure"',
    );
  });
});


describe("handleStatus — error paths (always HTML, never JSON)", () => {
  test("non-POST method → 400 + failure surface", async () => {
    const response = await handleStatus(req({ method: "GET" }));
    expect(response.status).toBe(400);
    expect(response.headers["content-type"]).toBe(
      "text/html; charset=utf-8",
    );
    const body = response.body as string;
    expect(body).toContain('data-status-surface="failure"');
    expect(body).toContain("method_not_allowed");
  });

  test("non-string body → 400 + failure surface", async () => {
    const response = await handleStatus(req({ body: null }));
    expect(response.status).toBe(400);
    expect(response.body as string).toContain(
      "missing JSON body",
    );
  });

  test("body that's not JSON → 400 + failure surface", async () => {
    const response = await handleStatus(req({ body: "not-json{" }));
    expect(response.status).toBe(400);
    expect(response.body as string).toContain(
      "not valid JSON",
    );
  });

  test("payload missing kind → 400 + failure surface", async () => {
    const response = await handleStatus(req({
      body: JSON.stringify({ message: "x" }),
    }));
    expect(response.status).toBe(400);
    expect(response.body as string).toContain(
      'data-status-surface="failure"',
    );
  });

  test("unknown kind → 400 + failure surface", async () => {
    const response = await handleStatus(req({
      body: JSON.stringify({ kind: "info", message: "x" }),
    }));
    expect(response.status).toBe(400);
    expect(response.body as string).toContain(
      'data-status-surface="failure"',
    );
  });

  test("error responses still carry text/html content-type (never JSON)", async () => {
    const cases = [
      req({ method: "GET" }),
      req({ body: null }),
      req({ body: "not-json" }),
      req({ body: JSON.stringify({}) }),
      req({ body: JSON.stringify({ kind: "x", message: "y" }) }),
    ];
    for (const r of cases) {
      const response = await handleStatus(r);
      expect(response.headers["content-type"]).toBe(
        "text/html; charset=utf-8",
      );
      expect(typeof response.body).toBe("string");
      // Never an object that would JSON-encode at the adapter.
      expect((response.body as string).startsWith("{")).toBe(false);
    }
  });
});


describe("handleStatus — determinism + non-mutation", () => {
  test("same request → byte-identical body across calls", async () => {
    const r = req({
      body: JSON.stringify({ kind: "success", message: "ok" }),
    });
    const a = await handleStatus(r);
    const b = await handleStatus(r);
    expect(b.body).toBe(a.body);
  });

  test("does not mutate the request", async () => {
    const r = req({
      body: JSON.stringify({ kind: "success", message: "ok" }),
    });
    const frozen = JSON.stringify(r);
    await handleStatus(r);
    expect(JSON.stringify(r)).toBe(frozen);
  });
});
