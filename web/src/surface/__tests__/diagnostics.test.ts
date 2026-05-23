// Card A21-R — server-side diagnostics tests.
//
// Three contract surfaces under test:
//
//   1. types — DiagnosticEntry / DiagnosticPayload shape.
//   2. collectDiagnostics — walks request → entries; route
//      metadata via resolveView; form-error count via A20-R
//      collectFormErrors; timestamp is ISO-8601.
//   3. handleDiagnostics (route handler) — loads
//      diagnosticFragment template, JSON-stringifies payload,
//      HTML-escapes it, returns 200 + text/html response with
//      <pre data-json> body.
//
// Path: web/src/surface/__tests__/diagnostics.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  collectDiagnostics,
  type DiagnosticEntry,
  type DiagnosticPayload,
} from "../diagnostics";
import {
  DIAGNOSTICS_PATH,
  escapeHtml,
  handleDiagnostics,
} from "../../server/routes/diagnostics";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import {
  registerView,
  _clearViewRegistryForTests,
} from "../viewRegistry";
import { clearTemplateCache } from "../templateCache";
import { clearLayoutCache } from "../layoutCache";
import { clearPartialCache } from "../partialCache";
import { clearAssetManifest } from "../assetManifest";
import { formDemoView } from "../views/formDemo";


function req(opts: Partial<WebSurfaceV0_2.Request> = {}): WebSurfaceV0_2.Request {
  return {
    path:    "/__diagnostics",
    method:  "GET",
    headers: { "accept": "text/html" },
    body:    null,
    ...opts,
  };
}


beforeEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
  registerView("form_demo", formDemoView);
});

afterEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
});


// ---------------------------------------------------------------------------
// 1. Constants
// ---------------------------------------------------------------------------
describe("DIAGNOSTICS_PATH constant", () => {
  test("is the literal /__diagnostics", () => {
    expect(DIAGNOSTICS_PATH).toBe("/__diagnostics");
  });
});


// ---------------------------------------------------------------------------
// 2. collectDiagnostics — payload shape
// ---------------------------------------------------------------------------
describe("collectDiagnostics — payload shape", () => {
  test("returns a DiagnosticPayload with entries + timestamp", async () => {
    const payload: DiagnosticPayload = await collectDiagnostics(req());
    expect(Array.isArray(payload.entries)).toBe(true);
    expect(typeof payload.timestamp).toBe("string");
  });

  test("timestamp is ISO-8601 (parseable + ends with Z)", async () => {
    const payload = await collectDiagnostics(req());
    expect(payload.timestamp).toMatch(
      /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/,
    );
    expect(Number.isNaN(Date.parse(payload.timestamp))).toBe(false);
  });

  test("records request.method / request.path / request.headers", async () => {
    const payload = await collectDiagnostics(req({
      method:  "POST",
      path:    "/form_demo",
      headers: { "content-type": "application/x-www-form-urlencoded" },
    }));
    const byKey = Object.fromEntries(
      payload.entries.map((e) => [e.key, e]),
    );
    expect(byKey["request.method"]?.value).toBe("POST");
    expect(byKey["request.path"]?.value).toBe("/form_demo");
    expect(byKey["request.headers"]?.value).toEqual({
      "content-type": "application/x-www-form-urlencoded",
    });
  });

  test("records route.view + route.mode via resolveView", async () => {
    const payload = await collectDiagnostics(req({
      path: "/form_demo",
    }));
    const byKey = Object.fromEntries(
      payload.entries.map((e) => [e.key, e]),
    );
    expect(byKey["route.view"]?.value).toBe("form_demo");
    expect(byKey["route.mode"]?.value).toBe("html");
  });

  test("route.mode reflects json mode when ?mode=json", async () => {
    const payload = await collectDiagnostics(req({
      path: "/form_demo?mode=json",
    }));
    const route = payload.entries.find((e) => e.key === "route.mode");
    expect(route?.value).toBe("json");
  });

  test("form.error_count is 0 (info severity) for non-form requests", async () => {
    const payload = await collectDiagnostics(req());
    const formCount = payload.entries.find(
      (e) => e.key === "form.error_count",
    );
    expect(formCount?.value).toBe(0);
    expect(formCount?.severity).toBe("info");
  });

  test("form.error_count > 0 (warn severity) when a form fails validation", async () => {
    const payload = await collectDiagnostics(req({
      path:    "/form_demo",
      method:  "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body:    "name=&email=",
    }));
    const formCount = payload.entries.find(
      (e) => e.key === "form.error_count",
    );
    expect(formCount?.value).toBe(2);
    expect(formCount?.severity).toBe("warn");
  });

  test("timing placeholders carry null (no infra yet)", async () => {
    const payload = await collectDiagnostics(req());
    const byKey = Object.fromEntries(
      payload.entries.map((e) => [e.key, e]),
    );
    expect(byKey["server.timing_ms"]?.value).toBeNull();
    expect(byKey["surface.render_ms"]?.value).toBeNull();
  });

  test("entries each carry a closed-enum severity", async () => {
    const payload = await collectDiagnostics(req());
    for (const entry of payload.entries) {
      expect(["info", "warn", "error"]).toContain(entry.severity);
    }
  });

  test("does not mutate the request", async () => {
    const r = req({ path: "/form_demo" });
    const frozen = JSON.stringify(r);
    await collectDiagnostics(r);
    expect(JSON.stringify(r)).toBe(frozen);
  });

  test("entry order is deterministic across calls", async () => {
    const r = req({ path: "/form_demo" });
    const keys1 = (await collectDiagnostics(r)).entries.map((e) => e.key);
    const keys2 = (await collectDiagnostics(r)).entries.map((e) => e.key);
    expect(keys2).toEqual(keys1);
  });
});


// ---------------------------------------------------------------------------
// 3. escapeHtml — boundary escape
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

  test("returns empty string unchanged", () => {
    expect(escapeHtml("")).toBe("");
  });
});


// ---------------------------------------------------------------------------
// 4. handleDiagnostics — fragment rendering
// ---------------------------------------------------------------------------
describe("handleDiagnostics — fragment rendering", () => {
  test("returns 200 + text/html response", async () => {
    const response = await handleDiagnostics(req());
    expect(response.status).toBe(200);
    expect(response.headers["content-type"]).toBe(
      "text/html; charset=utf-8",
    );
  });

  test("body wraps a <div class=\"diagnostic-panel\"> with <pre data-json>", async () => {
    const response = await handleDiagnostics(req());
    const html = response.body as string;
    expect(html).toContain('<div class="diagnostic-panel"');
    expect(html).toContain("data-diagnostic-fragment");
    expect(html).toContain('<pre data-json>');
    expect(html).toContain("</pre>");
    expect(html).toContain("</div>");
  });

  test("body carries the JSON payload (entries + timestamp)", async () => {
    const response = await handleDiagnostics(req());
    const html = response.body as string;
    expect(html).toContain("&quot;entries&quot;");
    expect(html).toContain("&quot;timestamp&quot;");
    expect(html).toContain("&quot;request.method&quot;");
    expect(html).toContain("&quot;route.view&quot;");
  });

  test("JSON content is HTML-escaped (no raw < or >)", async () => {
    // Craft a request whose headers contain a value that would
    // be HTML-dangerous if not escaped (the headers value is
    // serialised verbatim into the payload).
    const response = await handleDiagnostics(req({
      headers: { "x-probe": '<script>alert(1)</script>' },
    }));
    const html = response.body as string;
    expect(html).not.toContain("<script>alert(1)</script>");
    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
  });

  test("body parses back into the same payload shape", async () => {
    const response = await handleDiagnostics(req());
    const html = response.body as string;
    // Extract the JSON between <pre data-json> and </pre>.
    const match = html.match(/<pre data-json>([\s\S]*?)<\/pre>/);
    expect(match).not.toBeNull();
    // Unescape the five entities we apply at the boundary.
    const escaped = match![1];
    const unescaped = escaped
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'")
      .replace(/&amp;/g, "&");
    const parsed = JSON.parse(unescaped) as DiagnosticPayload;
    expect(Array.isArray(parsed.entries)).toBe(true);
    expect(typeof parsed.timestamp).toBe("string");
    const byKey = Object.fromEntries(
      parsed.entries.map((e: DiagnosticEntry) => [e.key, e]),
    );
    expect(byKey["request.method"]?.value).toBe("GET");
  });

  test("body includes a freshly-formatted timestamp on each call", async () => {
    const r1 = await handleDiagnostics(req());
    // Sleep one millisecond to guarantee a distinct ISO string.
    await new Promise((resolve) => setTimeout(resolve, 2));
    const r2 = await handleDiagnostics(req());
    // Timestamps appear inside the JSON; just check the bodies
    // are not byte-identical (would prove the timestamp slot
    // is being filled per call).
    expect(r2.body).not.toBe(r1.body);
  });
});
