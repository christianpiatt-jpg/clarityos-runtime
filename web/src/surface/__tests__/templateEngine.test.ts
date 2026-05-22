// Card A3 — tests for the v0.2.0 template engine + loader.
//
// Three test surfaces:
//
//   1. Template loader (``templateLoader.ts``) — file resolution,
//      content read, missing-template error.
//   2. Template engine (``templateEngine.ts``) — substitution,
//      unfilled-placeholder stripping, whitespace tolerance,
//      regex-metacharacter safety, determinism.
//   3. Integration — ``viewDefaultRenderer`` HTML mode produces
//      output through the template engine, with the XSS-escape
//      guard from A1 still active at the renderer boundary.
//
// Path: web/src/surface/__tests__/templateEngine.test.ts
import { describe, expect, test } from "vitest";

import { loadTemplate, TEMPLATES_DIR } from "../templateLoader";
import { renderTemplate } from "../templateEngine";
import { defaultRenderer } from "../viewDefaultRenderer";
import { WebSurfaceV0_2_View as V } from "../viewContract";


// ---------------------------------------------------------------------------
// 1. Template loader
// ---------------------------------------------------------------------------
describe("loadTemplate — file resolution + read", () => {
  test("templates directory path is anchored to web/templates/v0.2", () => {
    // Path resolution uses import.meta.url, not process.cwd(), so
    // vitest (cwd=web/) resolves the same path as the runtime.
    const normalised = TEMPLATES_DIR.replace(/\\/g, "/");
    expect(normalised).toContain("/web/templates/v0.2");
  });

  test("loads base.html", () => {
    const template = loadTemplate("base");
    expect(typeof template).toBe("string");
    expect(template.length).toBeGreaterThan(0);
  });

  test("base.html carries the expected placeholders", () => {
    const template = loadTemplate("base");
    expect(template).toContain("{{ title }}");
    expect(template).toContain("{{ content }}");
  });

  test("base.html is a well-formed HTML5 doc", () => {
    const template = loadTemplate("base");
    expect(template).toContain("<!DOCTYPE html>");
    expect(template).toContain("<html>");
    expect(template).toContain("</html>");
  });

  test("throws on a missing template name", () => {
    expect(() => loadTemplate("does-not-exist-xyz")).toThrow();
  });
});


// ---------------------------------------------------------------------------
// 2. Template engine — substitution
// ---------------------------------------------------------------------------
describe("renderTemplate — variable substitution", () => {
  test("substitutes a single placeholder", () => {
    const out = renderTemplate("<h1>{{ name }}</h1>", { name: "Christian" });
    expect(out).toBe("<h1>Christian</h1>");
  });

  test("substitutes multiple placeholders in one pass", () => {
    const out = renderTemplate(
      "<p>{{ greeting }}, {{ name }}!</p>",
      { greeting: "Hello", name: "world" },
    );
    expect(out).toBe("<p>Hello, world!</p>");
  });

  test("substitutes the same placeholder repeated in the template", () => {
    const out = renderTemplate(
      "{{ x }} and {{ x }} and {{ x }}",
      { x: "yes" },
    );
    expect(out).toBe("yes and yes and yes");
  });

  test("tolerates optional whitespace inside the braces", () => {
    const out = renderTemplate("{{foo}} {{ bar }} {{  baz  }}", {
      foo: "F", bar: "B", baz: "Z",
    });
    expect(out).toBe("F B Z");
  });

  test("coerces non-string values via String(value)", () => {
    const out = renderTemplate(
      "n={{ n }} flag={{ flag }} obj={{ obj }}",
      { n: 42, flag: true, obj: { a: 1 } },
    );
    // ``String(42)`` = "42"; ``String(true)`` = "true";
    // ``String({a:1})`` = "[object Object]". The engine treats vars
    // as opaque — coercion is JS-standard.
    expect(out).toBe("n=42 flag=true obj=[object Object]");
  });

  test("handles regex-metacharacter keys safely", () => {
    // Defence-in-depth: a key like "a.b" should be matched as a
    // literal, not as the regex ``a.b`` (where ``.`` means "any").
    // We don't typically pass dotted keys, but the safety property
    // is locked here.
    const out = renderTemplate("{{ a.b }}", { "a.b": "literal" });
    expect(out).toBe("literal");
  });
});


// ---------------------------------------------------------------------------
// 3. Template engine — unfilled placeholder stripping
// ---------------------------------------------------------------------------
describe("renderTemplate — unfilled placeholder handling", () => {
  test("removes unfilled placeholders entirely", () => {
    const out = renderTemplate("<p>{{ name }} {{ missing }}</p>", {
      name: "Christian",
    });
    expect(out).toBe("<p>Christian </p>");
  });

  test("removes ALL unfilled placeholders (no leaks)", () => {
    const out = renderTemplate(
      "[{{ a }}][{{ b }}][{{ c }}][{{ d }}]",
      { b: "B" },
    );
    expect(out).toBe("[][B][][]");
  });

  test("removes dotted-path placeholders (no nested resolution)", () => {
    // ``{{ user.name }}`` doesn't resolve because the engine doesn't
    // walk dotted paths — it falls through the substitution loop
    // and gets stripped by the unfilled-placeholder pass.
    const out = renderTemplate(
      "Hi {{ user.name }}!",
      { user: { name: "Christian" } },
    );
    expect(out).toBe("Hi !");
  });

  test("never leaks raw {{ var }} text into the output", () => {
    const out = renderTemplate(
      "{{ admin_password }}",
      {},
    );
    expect(out).not.toContain("{{");
    expect(out).not.toContain("admin_password");
    expect(out).toBe("");
  });
});


// ---------------------------------------------------------------------------
// 4. Template engine — determinism + purity
// ---------------------------------------------------------------------------
describe("renderTemplate — purity", () => {
  test("same input → same output (referential determinism)", () => {
    const t = "{{ x }} / {{ y }}";
    const v = { x: "a", y: "b" };
    expect(renderTemplate(t, v)).toBe(renderTemplate(t, v));
  });

  test("does not mutate the vars object", () => {
    const v = { a: 1, b: 2 };
    const frozen = JSON.stringify(v);
    renderTemplate("{{ a }}-{{ b }}", v);
    expect(JSON.stringify(v)).toBe(frozen);
  });

  test("trims leading/trailing whitespace from the output", () => {
    const out = renderTemplate("  \n  hello  \n  ", {});
    expect(out).toBe("hello");
  });

  test("module re-import is idempotent (no side effects at load)", async () => {
    const first = await import("../templateEngine");
    const second = await import("../templateEngine");
    expect(first).toBe(second);
  });
});


// ---------------------------------------------------------------------------
// 5. Integration — defaultRenderer + template engine
// ---------------------------------------------------------------------------
describe("defaultRenderer + template engine integration", () => {
  test("HTML mode body is produced via the template", async () => {
    const out = await defaultRenderer({
      view: "dashboard",
      mode: V.Mode.html,
    });
    expect(out.status).toBe(200);
    expect(out.headers["content-type"]).toBe("text/html; charset=utf-8");
    const html = out.body as string;
    // Template-shaped output.
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain("<title>dashboard</title>");
    expect(html).toContain("<h1>dashboard</h1>");
    expect(html).toContain('<div id="content">');
  });

  test("HTML mode body interpolates params under the content slot", async () => {
    const out = await defaultRenderer({
      view:   "with-params",
      params: { id: "abc", count: 3 },
      mode:   V.Mode.html,
    });
    const html = out.body as string;
    // Escaped JSON appears inside the content div.
    expect(html).toMatch(/&quot;id&quot;/);
    expect(html).toMatch(/&quot;abc&quot;/);
    expect(html).toMatch(/&quot;count&quot;/);
  });

  test("HTML output still HTML-escapes the view name (XSS regression)", async () => {
    const out = await defaultRenderer({
      view: '<script>alert("x")</script>',
      mode: V.Mode.html,
    });
    const html = out.body as string;
    expect(html).not.toContain('<script>alert("x")</script>');
    expect(html).toContain("&lt;script&gt;");
    expect(html).toContain("alert(&quot;x&quot;)");
  });

  test("HTML output still HTML-escapes params (XSS regression)", async () => {
    const out = await defaultRenderer({
      view:   "safe-view",
      params: { evil: '<img src=x onerror="alert(1)">' },
      mode:   V.Mode.html,
    });
    const html = out.body as string;
    expect(html).not.toContain('<img src=x onerror="alert(1)">');
    expect(html).toContain("&lt;img");
  });

  test("HTML output has no unfilled placeholders", async () => {
    const out = await defaultRenderer({
      view: "x",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    // The template engine strips unfilled placeholders; no raw
    // ``{{ ... }}`` text may appear in the final HTML.
    expect(html).not.toMatch(/{{\s*\w+\s*}}/);
  });

  test("JSON mode is unaffected by the template engine", async () => {
    const out = await defaultRenderer({
      view:   "json-only",
      params: { id: "abc" },
      mode:   V.Mode.json,
    });
    expect(out.status).toBe(200);
    expect(out.headers["content-type"]).toBe("application/json");
    expect(out.body).toEqual({ view: "json-only", params: { id: "abc" } });
  });
});
