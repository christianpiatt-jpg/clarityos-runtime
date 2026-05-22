// Card A15 — multi-step form wizard tests.
//
// Seven contract surfaces under test:
//
//   1. _computeDisplayStep (pure helper):
//      * GET (no errors map) → submitted step, default "1".
//      * POST + empty errors → advance to next step.
//      * POST + non-empty errors → stay on submitted step.
//      * Unknown / malformed step values → fall back to "1".
//      * "done" is terminal (advances to itself).
//
//   2. _wizardSchemaFor (pure schema picker):
//      * Each step returns the expected permissive carry-forward
//        rules plus a required rule for the field for THAT step.
//      * Unknown / "done" steps return undefined (skip
//        validation).
//
//   3. ViewDefinition function-typed template + schema:
//      * resolveViewTemplate calls a function template.
//      * resolveViewSchema calls a function schema.
//      * Static-value views still work unchanged.
//
//   4. GET behaviour (no validation runs):
//      * GET /form_wizard → renders step 1.
//      * GET /form_wizard?step=2 → renders step 2 (deep link).
//      * GET /form_wizard?step=done → renders summary (empty
//        fields).
//
//   5. POST step transitions (full flow):
//      * step=1 with valid name → renders step 2 with hidden
//        name carry-forward.
//      * step=2 with valid name+email → renders step 3 with
//        hidden name + email carry-forward.
//      * step=3 with valid name+email+age → renders done with
//        all three values.
//
//   6. POST validation failures (stay on step + show error):
//      * step=1 + invalid name → renders step 1 with name error.
//      * step=2 + invalid email → renders step 2 with email
//        error and preserved name.
//      * step=3 + invalid age → renders step 3 with age error
//        and preserved name+email.
//      * step=3 + age=0 (below min=1) → stays on step 3.
//
//   7. Determinism + non-mutation:
//      * Same wizard POST → byte-identical HTML across runs.
//      * Renderer does not mutate ctx.
//      * Form pathway does not register or unregister views.
//      * Tampered carry-forward fields don't crash; their
//        permissive validation lets them flow through unchanged.
//
// Path: web/src/surface/__tests__/formWizard.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { routeWebSurface } from "../router";
import { renderWebSurface } from "../renderer";
import {
  resolveViewTemplate,
  resolveViewSchema,
  registerView,
  _clearViewRegistryForTests,
  _listRegisteredViewsForTests,
} from "../viewRegistry";
import { WebSurfaceV0_2_View as V } from "../viewContract";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import { FORM_URLENCODED_CONTENT_TYPE } from "../classifier";
import { clearTemplateCache } from "../templateCache";
import { clearLayoutCache } from "../layoutCache";
import { clearPartialCache } from "../partialCache";
import { clearAssetManifest } from "../assetManifest";
import { homeView } from "../views/home";
import { error404View, error500View } from "../views/errors";
import {
  formWizardView,
  _computeDisplayStep,
  _wizardSchemaFor,
} from "../views/formWizard";


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


function formReq(
  path: string,
  body: string,
  extra: Partial<WebSurfaceV0_2.Request> = {},
): WebSurfaceV0_2.Request {
  const { headers: extraHeaders, ...rest } = extra;
  return {
    path,
    method: "POST",
    body,
    ...rest,
    headers: {
      "content-type": FORM_URLENCODED_CONTENT_TYPE,
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
  registerView("form_wizard",  formWizardView);
});

afterEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
});


// ---------------------------------------------------------------------------
// 1. _computeDisplayStep
// ---------------------------------------------------------------------------
describe("_computeDisplayStep", () => {
  test("GET with no params → '1' (default)", () => {
    expect(_computeDisplayStep({ view: "form_wizard", mode: V.Mode.html }))
      .toBe("1");
  });

  test("GET with ?step=2 → '2' (deep-link, no validation ran)", () => {
    expect(_computeDisplayStep({
      view: "form_wizard", mode: V.Mode.html, params: { step: "2" },
    })).toBe("2");
  });

  test("GET with ?step=done → 'done'", () => {
    expect(_computeDisplayStep({
      view: "form_wizard", mode: V.Mode.html, params: { step: "done" },
    })).toBe("done");
  });

  test("POST with empty errors → advance ('1' → '2')", () => {
    expect(_computeDisplayStep({
      view: "form_wizard", mode: V.Mode.html,
      params: { step: "1", errors: {} },
    })).toBe("2");
  });

  test("POST with non-empty errors → stay on submitted step", () => {
    expect(_computeDisplayStep({
      view: "form_wizard", mode: V.Mode.html,
      params: { step: "1", errors: { name: "..." } },
    })).toBe("1");
  });

  test("advance chain: 1 → 2 → 3 → done → done", () => {
    const advance = (step: string) =>
      _computeDisplayStep({
        view: "form_wizard", mode: V.Mode.html,
        params: { step, errors: {} },
      });
    expect(advance("1")).toBe("2");
    expect(advance("2")).toBe("3");
    expect(advance("3")).toBe("done");
    expect(advance("done")).toBe("done");
  });

  test("unknown step value falls back to '1' (defence-in-depth)", () => {
    expect(_computeDisplayStep({
      view: "form_wizard", mode: V.Mode.html,
      params: { step: "99" },
    })).toBe("1");
  });

  test("non-string step value falls back to '1'", () => {
    expect(_computeDisplayStep({
      view: "form_wizard", mode: V.Mode.html,
      params: { step: 42 as unknown as string },
    })).toBe("1");
  });

  test("errors must be an object (null does not count as valid)", () => {
    // ``errors: null`` shouldn't be treated as "validation
    // passed". The helper treats it as "no validation ran"
    // (errors === undefined branch via the !=== check).
    expect(_computeDisplayStep({
      view: "form_wizard", mode: V.Mode.html,
      params: { step: "1", errors: null as unknown as Record<string, string> },
    })).toBe("1");
  });
});


// ---------------------------------------------------------------------------
// 2. _wizardSchemaFor
// ---------------------------------------------------------------------------
describe("_wizardSchemaFor", () => {
  test("step=1 → schema requires name (min 2) + permissive step", () => {
    const schema = _wizardSchemaFor({ step: "1" });
    expect(schema).toEqual({
      step: { type: "string" },
      name: { type: "string", required: true, min: 2 },
    });
  });

  test("step=2 → schema requires email + carry-forward name", () => {
    const schema = _wizardSchemaFor({ step: "2" });
    expect(schema).toEqual({
      step:  { type: "string" },
      name:  { type: "string" },
      email: { type: "email", required: true },
    });
  });

  test("step=3 → schema requires age (number, min 1) + carry-forward name/email", () => {
    const schema = _wizardSchemaFor({ step: "3" });
    expect(schema).toEqual({
      step:  { type: "string" },
      name:  { type: "string" },
      email: { type: "string" },
      age:   { type: "number", required: true, min: 1 },
    });
  });

  test("step=done → undefined (skip validation)", () => {
    expect(_wizardSchemaFor({ step: "done" })).toBeUndefined();
  });

  test("missing step → defaults to '1' schema", () => {
    expect(_wizardSchemaFor({})).toEqual(_wizardSchemaFor({ step: "1" }));
  });

  test("unknown step → undefined (passthrough)", () => {
    expect(_wizardSchemaFor({ step: "99" })).toBeUndefined();
  });
});


// ---------------------------------------------------------------------------
// 3. ViewDefinition function-typed template + schema
// ---------------------------------------------------------------------------
describe("ViewDefinition function-typed template + schema", () => {
  test("resolveViewTemplate passes through static strings", () => {
    expect(resolveViewTemplate("home", {
      view: "x", mode: V.Mode.html,
    })).toBe("home");
  });

  test("resolveViewTemplate calls function templates with ctx", () => {
    let seen: V.RenderContext | undefined;
    const fn = (ctx: V.RenderContext) => {
      seen = ctx;
      return "computed_template";
    };
    const ctx: V.RenderContext = {
      view: "x", mode: V.Mode.html, params: { step: "2" },
    };
    expect(resolveViewTemplate(fn, ctx)).toBe("computed_template");
    expect(seen).toBe(ctx);
  });

  test("resolveViewSchema passes through static schemas", () => {
    const schema = { name: { type: "string" as const } };
    expect(resolveViewSchema(schema, {})).toBe(schema);
  });

  test("resolveViewSchema calls function schemas with fields", () => {
    let seen: Record<string, string> | undefined;
    const fn = (fields: Record<string, string>) => {
      seen = fields;
      return { name: { type: "string" as const } };
    };
    const fields = { step: "1", name: "Alice" };
    const result = resolveViewSchema(fn, fields);
    expect(result).toEqual({ name: { type: "string" } });
    expect(seen).toBe(fields);
  });

  test("resolveViewSchema returns undefined when schema is undefined", () => {
    expect(resolveViewSchema(undefined, {})).toBeUndefined();
  });

  test("resolveViewSchema returns undefined when function returns undefined", () => {
    expect(resolveViewSchema(() => undefined, {})).toBeUndefined();
  });
});


// ---------------------------------------------------------------------------
// 4. GET behaviour
// ---------------------------------------------------------------------------
describe("routeWebSurface — GET /form_wizard", () => {
  test("GET / (no step) → renders step 1 template", async () => {
    const res = await routeWebSurface(reqOf({ path: "/form_wizard" }));
    expect(res.status).toBe(200);
    const html = res.body as string;
    expect(html).toContain("Step 1 of 3 — Name");
    expect(html).toContain('<input type="hidden" name="step" value="1">');
    expect(html).toContain('<input type="text" name="name" value="">');
  });

  test("GET ?step=2 → renders step 2 (deep link, empty carry-forward)", async () => {
    const res = await routeWebSurface(reqOf({
      path: "/form_wizard?step=2",
    }));
    const html = res.body as string;
    expect(html).toContain("Step 2 of 3 — Email");
    expect(html).toContain('<input type="hidden" name="step" value="2">');
    expect(html).toContain('<input type="hidden" name="name" value="">');
  });

  test("GET ?step=3 → renders step 3", async () => {
    const res = await routeWebSurface(reqOf({
      path: "/form_wizard?step=3",
    }));
    const html = res.body as string;
    expect(html).toContain("Step 3 of 3 — Age");
    expect(html).toContain('<input type="hidden" name="step" value="3">');
  });

  test("GET ?step=done → renders summary", async () => {
    const res = await routeWebSurface(reqOf({
      path: "/form_wizard?step=done",
    }));
    const html = res.body as string;
    expect(html).toContain("<h2>Summary</h2>");
  });

  test("GET goes through the standard layout", async () => {
    const res = await routeWebSurface(reqOf({ path: "/form_wizard" }));
    const html = res.body as string;
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain('<div id="layout">');
  });

  test("GET errors map is undefined → no validation triggered", async () => {
    // Sanity: a GET with ?step=1 doesn't fire validation, so
    // no "This field is required." appears.
    const res = await routeWebSurface(reqOf({ path: "/form_wizard?step=1" }));
    const html = res.body as string;
    expect(html).not.toContain("This field is required.");
  });
});


// ---------------------------------------------------------------------------
// 5. POST step transitions (full flow)
// ---------------------------------------------------------------------------
describe("routeWebSurface — wizard POST transitions", () => {
  test("step=1 + valid name → renders step 2 with name carry-forward", async () => {
    const res = await routeWebSurface(formReq(
      "/form_wizard",
      "step=1&name=Alice",
    ));
    expect(res.status).toBe(200);
    const html = res.body as string;
    expect(html).toContain("Step 2 of 3 — Email");
    expect(html).toContain('<input type="hidden" name="step" value="2">');
    expect(html).toContain('<input type="hidden" name="name" value="Alice">');
    // No error spans populated.
    expect(html).not.toContain("Must be at least");
  });

  test("step=2 + valid email → renders step 3 with name + email carry-forward", async () => {
    const res = await routeWebSurface(formReq(
      "/form_wizard",
      "step=2&name=Alice&email=a%40b.com",
    ));
    const html = res.body as string;
    expect(html).toContain("Step 3 of 3 — Age");
    expect(html).toContain('<input type="hidden" name="step" value="3">');
    expect(html).toContain('<input type="hidden" name="name" value="Alice">');
    expect(html).toContain('<input type="hidden" name="email" value="a@b.com">');
  });

  test("step=3 + valid age → renders done with all three values", async () => {
    const res = await routeWebSurface(formReq(
      "/form_wizard",
      "step=3&name=Alice&email=a%40b.com&age=30",
    ));
    const html = res.body as string;
    expect(html).toContain("<h2>Summary</h2>");
    expect(html).toContain("Name: Alice");
    expect(html).toContain("Email: a@b.com");
    expect(html).toContain("Age: 30");
  });

  test("full happy-path: step 1 → 2 → 3 → done preserves values across renders", async () => {
    // Simulate the user clicking through the wizard. Each POST's
    // body mirrors what the previous render's form would have
    // sent (hidden inputs carry forward).
    const step1 = await routeWebSurface(formReq(
      "/form_wizard", "step=1&name=Bob",
    ));
    expect((step1.body as string)).toContain("Step 2 of 3");

    const step2 = await routeWebSurface(formReq(
      "/form_wizard", "step=2&name=Bob&email=b%40c.com",
    ));
    const step2html = step2.body as string;
    expect(step2html).toContain("Step 3 of 3");
    expect(step2html).toContain('name="name" value="Bob"');
    expect(step2html).toContain('name="email" value="b@c.com"');

    const done = await routeWebSurface(formReq(
      "/form_wizard", "step=3&name=Bob&email=b%40c.com&age=42",
    ));
    const doneHtml = done.body as string;
    expect(doneHtml).toContain("<h2>Summary</h2>");
    expect(doneHtml).toContain("Name: Bob");
    expect(doneHtml).toContain("Email: b@c.com");
    expect(doneHtml).toContain("Age: 42");
  });
});


// ---------------------------------------------------------------------------
// 6. POST validation failures
// ---------------------------------------------------------------------------
describe("routeWebSurface — wizard validation errors", () => {
  test("step=1 + name too short → stays on step 1 with error", async () => {
    const res = await routeWebSurface(formReq(
      "/form_wizard",
      "step=1&name=A",
    ));
    const html = res.body as string;
    expect(html).toContain("Step 1 of 3 — Name");
    expect(html).toContain('<span class="error">Must be at least 2 characters.</span>');
  });

  test("step=1 + missing name → required error, stays on step 1", async () => {
    const res = await routeWebSurface(formReq(
      "/form_wizard",
      "step=1&name=",
    ));
    const html = res.body as string;
    expect(html).toContain("Step 1 of 3 — Name");
    expect(html).toContain("This field is required.");
  });

  test("step=2 + invalid email → stays on step 2, name carries forward", async () => {
    const res = await routeWebSurface(formReq(
      "/form_wizard",
      "step=2&name=Alice&email=not-an-email",
    ));
    const html = res.body as string;
    expect(html).toContain("Step 2 of 3 — Email");
    expect(html).toContain("Invalid email address.");
    // Name was permissively carried forward — it's in values
    // and surfaces in the hidden input.
    expect(html).toContain('<input type="hidden" name="name" value="Alice">');
  });

  test("step=3 + age=0 (below min=1) → stays on step 3 with error", async () => {
    const res = await routeWebSurface(formReq(
      "/form_wizard",
      "step=3&name=Alice&email=a%40b.com&age=0",
    ));
    const html = res.body as string;
    expect(html).toContain("Step 3 of 3 — Age");
    expect(html).toContain("Must be ≥ 1.");
    // Both carry-forwards preserved.
    expect(html).toContain('name="name" value="Alice"');
    expect(html).toContain('name="email" value="a@b.com"');
  });

  test("step=3 + non-numeric age → stays on step 3 with error", async () => {
    const res = await routeWebSurface(formReq(
      "/form_wizard",
      "step=3&name=Alice&email=a%40b.com&age=not-a-number",
    ));
    const html = res.body as string;
    expect(html).toContain("Step 3 of 3 — Age");
    expect(html).toContain("Must be a number.");
  });

  test("step=3 + missing age → required error, stays on step 3", async () => {
    const res = await routeWebSurface(formReq(
      "/form_wizard",
      "step=3&name=Alice&email=a%40b.com",
    ));
    const html = res.body as string;
    expect(html).toContain("Step 3 of 3 — Age");
    expect(html).toContain("This field is required.");
  });
});


// ---------------------------------------------------------------------------
// 7. Determinism + non-mutation
// ---------------------------------------------------------------------------
describe("wizard — determinism + non-mutation", () => {
  test("same POST → byte-identical HTML across 5 renders", async () => {
    const outs: string[] = [];
    for (let i = 0; i < 5; i++) {
      const r = await routeWebSurface(formReq(
        "/form_wizard",
        "step=1&name=Alice",
      ));
      outs.push(r.body as string);
    }
    for (let i = 1; i < outs.length; i++) {
      expect(outs[i]).toBe(outs[0]);
    }
  });

  test("renderer does not mutate ctx", async () => {
    const ctx = {
      view:   "form_wizard",
      params: { step: "2", name: "Alice", errors: {} },
      mode:   V.Mode.html,
    };
    const frozen = JSON.stringify(ctx);
    await renderWebSurface(ctx);
    expect(JSON.stringify(ctx)).toBe(frozen);
  });

  test("wizard pathway does not register or unregister views", async () => {
    const before = _listRegisteredViewsForTests().slice().sort();
    await routeWebSurface(formReq("/form_wizard", "step=1&name=Alice"));
    await routeWebSurface(formReq("/form_wizard", "step=2&name=Alice&email=a%40b.com"));
    const after = _listRegisteredViewsForTests().slice().sort();
    expect(after).toEqual(before);
  });

  test("tampered carry-forward field renders without crash (permissive)", async () => {
    // Hostile name on step 2 — the permissive schema treats it
    // as a plain string. The value flows through, gets HTML-
    // escaped at the view boundary, and never breaks out of the
    // hidden input's value attribute.
    const hostile = '"><script>alert(1)</script>';
    const body = `step=2&name=${encodeURIComponent(hostile)}&email=a%40b.com`;
    const res = await routeWebSurface(formReq("/form_wizard", body));
    expect(res.status).toBe(200);
    const html = res.body as string;
    expect(html).not.toContain('<script>alert(1)</script>');
    expect(html).toContain("&lt;script&gt;");
  });

  test("script-tag count stays at the layout baseline (no injection)", async () => {
    // Only the standard layout's <script src="app.js"> tag is
    // expected. Hostile carry-forward values must not inflate
    // this count.
    const safe = await routeWebSurface(formReq(
      "/form_wizard", "step=2&name=Alice&email=a%40b.com",
    ));
    const safeCount =
      (safe.body as string).match(/<script\b/g)?.length ?? 0;
    expect(safeCount).toBe(1);

    const hostile = await routeWebSurface(formReq(
      "/form_wizard",
      `step=2&name=${encodeURIComponent('"><script>alert(1)</script>')}&email=x%40y.com`,
    ));
    const hostileCount =
      (hostile.body as string).match(/<script\b/g)?.length ?? 0;
    expect(hostileCount).toBe(safeCount);
  });

  test("template fn is pure — same ctx → same template name", () => {
    const ctx: V.RenderContext = {
      view:   "form_wizard",
      params: { step: "2", errors: {} },
      mode:   V.Mode.html,
    };
    expect(resolveViewTemplate(formWizardView.template, ctx))
      .toBe(resolveViewTemplate(formWizardView.template, ctx));
  });

  test("schema fn is pure — same fields → same schema shape", () => {
    const a = _wizardSchemaFor({ step: "2", name: "A" });
    const b = _wizardSchemaFor({ step: "2", name: "B" });
    // Same step → same schema shape regardless of field values.
    expect(a).toEqual(b);
  });

  test("router does not mutate request on wizard POST", async () => {
    const req = formReq("/form_wizard", "step=1&name=Alice");
    const frozen = JSON.stringify(req);
    await routeWebSurface(req);
    expect(JSON.stringify(req)).toBe(frozen);
  });
});
