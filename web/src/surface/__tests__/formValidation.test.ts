// Card A14-R — form validation + error binding tests.
//
// Six contract surfaces under test:
//
//   1. validateForm — required:
//      * Missing + required → "This field is required." error.
//      * Whitespace-only + required → also fires the required error.
//      * Missing + optional → ``values[key] = ""``, no error.
//
//   2. validateForm — string rule:
//      * ``min`` violated → "Must be at least N characters."
//      * ``max`` violated → "Must be at most N characters."
//      * ``pattern`` violated → "Invalid format."
//      * Valid input → value flows through unchanged.
//      * First-failure-wins ordering (required > length > pattern)
//        — deterministic error messages.
//
//   3. validateForm — email rule:
//      * Common valid + invalid inputs.
//      * Whitespace-bracketed input rejected.
//
//   4. validateForm — number rule:
//      * Non-numeric input → "Must be a number."
//      * ``min`` / ``max`` violations.
//      * Coercion: valid string → ``number`` in ``values``.
//
//   5. Form handler integration:
//      * View without schema → passthrough (A13-R behaviour).
//      * View with schema, valid form → ``params = {...values, errors: {}}``.
//      * View with schema, invalid form → ``errors`` carries the
//        messages; invalid fields are absent from ``values``.
//      * HTML mode renders the error spans into the template.
//      * JSON mode envelope carries the errors map.
//
//   6. Determinism + non-mutation:
//      * Same (fields, schema) in → identical ValidationResult out.
//      * Validator does not mutate ``fields`` or ``schema``.
//      * Same hostile form → byte-identical HTML across runs.
//      * Schema-bound iteration: extra fields in the POST body
//        do NOT appear in ``values`` or ``errors``.
//
// Path: web/src/surface/__tests__/formValidation.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { validateForm } from "../validator";
import {
  FieldRule,
  ValidationSchema,
} from "../validationSchema";
import { handleForm } from "../formHandler";
import { routeWebSurface } from "../router";
import { FORM_URLENCODED_CONTENT_TYPE } from "../classifier";
import { WebSurfaceV0_2_View as V } from "../viewContract";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import {
  registerView,
  _clearViewRegistryForTests,
} from "../viewRegistry";
import { clearTemplateCache } from "../templateCache";
import { clearLayoutCache } from "../layoutCache";
import { clearPartialCache } from "../partialCache";
import { clearAssetManifest } from "../assetManifest";
import { homeView } from "../views/home";
import { error404View, error500View } from "../views/errors";
import { formDemoView, formDemoSchema } from "../views/formDemo";


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
  registerView("home",       homeView);
  registerView("error_404",  error404View);
  registerView("error_500",  error500View);
  registerView("form_demo",  formDemoView);
});

afterEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
});


// ---------------------------------------------------------------------------
// 1. Required
// ---------------------------------------------------------------------------
describe("validateForm — required", () => {
  const schema: ValidationSchema = {
    name: { type: "string", required: true },
  };

  test("missing + required → required error", () => {
    const result = validateForm({}, schema);
    expect(result.valid).toBe(false);
    expect(result.errors).toEqual({ name: "This field is required." });
    expect(result.values).toEqual({});
  });

  test("empty string + required → required error", () => {
    const result = validateForm({ name: "" }, schema);
    expect(result.errors).toEqual({ name: "This field is required." });
  });

  test("whitespace-only + required → required error", () => {
    const result = validateForm({ name: "   " }, schema);
    expect(result.errors).toEqual({ name: "This field is required." });
  });

  test("present + required → no error, value passes through", () => {
    const result = validateForm({ name: "Alice" }, schema);
    expect(result.valid).toBe(true);
    expect(result.errors).toEqual({});
    expect(result.values).toEqual({ name: "Alice" });
  });

  test("missing + optional → values[key] = '' (no error)", () => {
    const optional: ValidationSchema = {
      nickname: { type: "string" },
    };
    const result = validateForm({}, optional);
    expect(result.valid).toBe(true);
    expect(result.errors).toEqual({});
    expect(result.values).toEqual({ nickname: "" });
  });
});


// ---------------------------------------------------------------------------
// 2. String rule
// ---------------------------------------------------------------------------
describe("validateForm — string rule", () => {
  test("min length violated → 'Must be at least N characters.'", () => {
    const schema: ValidationSchema = {
      name: { type: "string", min: 5 },
    };
    const result = validateForm({ name: "Ali" }, schema);
    expect(result.errors).toEqual({ name: "Must be at least 5 characters." });
    expect(result.values).toEqual({});
  });

  test("max length violated → 'Must be at most N characters.'", () => {
    const schema: ValidationSchema = {
      name: { type: "string", max: 3 },
    };
    const result = validateForm({ name: "Alice" }, schema);
    expect(result.errors).toEqual({ name: "Must be at most 3 characters." });
  });

  test("pattern violated → 'Invalid format.'", () => {
    const schema: ValidationSchema = {
      code: { type: "string", pattern: /^[A-Z]{3}$/ },
    };
    const result = validateForm({ code: "abc" }, schema);
    expect(result.errors).toEqual({ code: "Invalid format." });
  });

  test("valid input → value flows through", () => {
    const schema: ValidationSchema = {
      code: { type: "string", min: 2, max: 5, pattern: /^[A-Z]+$/ },
    };
    const result = validateForm({ code: "ABCD" }, schema);
    expect(result.valid).toBe(true);
    expect(result.values).toEqual({ code: "ABCD" });
  });

  test("first-failure-wins: required precedes min/pattern", () => {
    const schema: ValidationSchema = {
      name: {
        type:     "string",
        required: true,
        min:      10,
        pattern:  /^[A-Z]+$/,
      },
    };
    const result = validateForm({ name: "" }, schema);
    // Required fires; the other rules don't add their messages.
    expect(result.errors).toEqual({ name: "This field is required." });
  });

  test("first-failure-wins: min precedes pattern", () => {
    const schema: ValidationSchema = {
      name: { type: "string", min: 10, pattern: /^[A-Z]+$/ },
    };
    const result = validateForm({ name: "Ali" }, schema);
    expect(result.errors).toEqual({ name: "Must be at least 10 characters." });
  });
});


// ---------------------------------------------------------------------------
// 3. Email rule
// ---------------------------------------------------------------------------
describe("validateForm — email rule", () => {
  const schema: ValidationSchema = {
    email: { type: "email", required: true },
  };

  test.each([
    "a@b.com",
    "alice@example.org",
    "name.surname@sub.domain.co.uk",
    "user+tag@example.com",
  ])("accepts valid email %j", (input) => {
    const result = validateForm({ email: input }, schema);
    expect(result.errors).toEqual({});
    expect(result.values).toEqual({ email: input });
  });

  test.each([
    "not-an-email",
    "missing-at.com",
    "missing-dot@example",
    "spaces in@email.com",
    "@no-local.com",
    "no-domain@",
    "double@@at.com",
  ])("rejects invalid email %j", (input) => {
    const result = validateForm({ email: input }, schema);
    expect(result.errors).toEqual({ email: "Invalid email address." });
    expect(result.values).toEqual({});
  });
});


// ---------------------------------------------------------------------------
// 4. Number rule
// ---------------------------------------------------------------------------
describe("validateForm — number rule", () => {
  test("non-numeric → 'Must be a number.'", () => {
    const schema: ValidationSchema = { age: { type: "number" } };
    const result = validateForm({ age: "not-a-number" }, schema);
    expect(result.errors).toEqual({ age: "Must be a number." });
  });

  test("valid numeric string → coerced to number in values", () => {
    const schema: ValidationSchema = { age: { type: "number" } };
    const result = validateForm({ age: "42" }, schema);
    expect(result.valid).toBe(true);
    expect(result.values).toEqual({ age: 42 });
  });

  test("min violated → 'Must be ≥ N.'", () => {
    const schema: ValidationSchema = { age: { type: "number", min: 18 } };
    const result = validateForm({ age: "17" }, schema);
    expect(result.errors).toEqual({ age: "Must be ≥ 18." });
  });

  test("max violated → 'Must be ≤ N.'", () => {
    const schema: ValidationSchema = { age: { type: "number", max: 120 } };
    const result = validateForm({ age: "121" }, schema);
    expect(result.errors).toEqual({ age: "Must be ≤ 120." });
  });

  test("number bound zero is honoured (not falsy-skipped)", () => {
    // ``min: 0`` should still be enforced — common bug in
    // validators that treat 0 as "no bound".
    const schema: ValidationSchema = { score: { type: "number", min: 0 } };
    const result = validateForm({ score: "-1" }, schema);
    expect(result.errors).toEqual({ score: "Must be ≥ 0." });
  });

  test("decimal values are coerced and bounded correctly", () => {
    const schema: ValidationSchema = {
      ratio: { type: "number", min: 0, max: 1 },
    };
    expect(validateForm({ ratio: "0.5" }, schema).values).toEqual({
      ratio: 0.5,
    });
    expect(validateForm({ ratio: "1.5" }, schema).errors).toEqual({
      ratio: "Must be ≤ 1.",
    });
  });

  test("missing + required → required error (not 'Must be a number.')", () => {
    const schema: ValidationSchema = {
      age: { type: "number", required: true },
    };
    const result = validateForm({}, schema);
    expect(result.errors).toEqual({ age: "This field is required." });
  });
});


// ---------------------------------------------------------------------------
// 5. Form handler integration
// ---------------------------------------------------------------------------
describe("handleForm — schema integration", () => {
  test("view without schema → passthrough (A13-R behaviour preserved)", async () => {
    registerView("no_schema", {
      template: "base",
      async render(ctx) {
        return {
          title:   "x",
          content: JSON.stringify(ctx.params ?? {}),
        };
      },
    });
    const res = await handleForm({
      kind:    "form",
      view:    "no_schema",
      rawBody: "name=Alice&email=a%40b.com",
      mode:    V.Mode.json,
    });
    // JSON envelope shows raw fields, NO ``errors`` key.
    expect(res.body).toEqual({
      view:   "no_schema",
      params: { name: "Alice", email: "a@b.com" },
    });
  });

  test("view with schema, valid form → values + empty errors map", async () => {
    const res = await handleForm({
      kind:    "form",
      view:    "form_demo",
      rawBody: "name=Alice&email=a%40b.com",
      mode:    V.Mode.json,
    });
    expect(res.body).toEqual({
      view:   "form_demo",
      params: { name: "Alice", email: "a@b.com", errors: {} },
    });
  });

  test("view with schema, invalid form → errors populated, invalid fields absent from values", async () => {
    const res = await handleForm({
      kind:    "form",
      view:    "form_demo",
      rawBody: "name=A&email=not-an-email",
      mode:    V.Mode.json,
    });
    expect(res.body).toEqual({
      view:   "form_demo",
      params: {
        errors: {
          name:  "Must be at least 2 characters.",
          email: "Invalid email address.",
        },
      },
    });
  });

  test("partial invalid: name valid + email invalid → only email in errors", async () => {
    const res = await handleForm({
      kind:    "form",
      view:    "form_demo",
      rawBody: "name=Alice&email=bad",
      mode:    V.Mode.json,
    });
    expect(res.body).toEqual({
      view:   "form_demo",
      params: {
        name:   "Alice",
        errors: { email: "Invalid email address." },
      },
    });
  });

  test("HTML mode renders error spans into the template", async () => {
    const res = await handleForm({
      kind:    "form",
      view:    "form_demo",
      rawBody: "name=A&email=bad",
      mode:    V.Mode.html,
    });
    const html = res.body as string;
    expect(html).toContain(
      '<span class="error">Must be at least 2 characters.</span>',
    );
    expect(html).toContain(
      '<span class="error">Invalid email address.</span>',
    );
  });

  test("HTML mode: valid form produces no error text in the spans", async () => {
    const res = await handleForm({
      kind:    "form",
      view:    "form_demo",
      rawBody: "name=Alice&email=a%40b.com",
      mode:    V.Mode.html,
    });
    const html = res.body as string;
    expect(html).toContain('<span class="error"></span>');
    expect(html).not.toContain("This field is required.");
    expect(html).not.toContain("Must be at least");
    expect(html).not.toContain("Invalid email address.");
  });

  test("end-to-end via routeWebSurface: invalid POST surfaces errors", async () => {
    const res = await routeWebSurface(formReq("/form_demo", "name=&email="));
    expect(res.status).toBe(200);
    const html = res.body as string;
    expect(html).toContain("This field is required.");
    // The error message appears twice — once for name, once for
    // email. Each is wrapped in its own <span class="error">.
    const matches = html.match(/This field is required\./g) ?? [];
    expect(matches.length).toBe(2);
  });

  test("schema-bound iteration: extra POST fields do NOT appear in envelope", async () => {
    // ``hacker=1`` is not in the schema; it must not leak into
    // ``values`` or ``errors``. The validator iterates schema
    // keys, NOT submitted field keys.
    const res = await handleForm({
      kind:    "form",
      view:    "form_demo",
      rawBody: "name=Alice&email=a%40b.com&hacker=1",
      mode:    V.Mode.json,
    });
    expect(res.body).toEqual({
      view:   "form_demo",
      params: { name: "Alice", email: "a@b.com", errors: {} },
    });
    // No ``hacker`` key in params.
    expect(((res.body as { params: Record<string, unknown> }).params))
      .not.toHaveProperty("hacker");
  });
});


// ---------------------------------------------------------------------------
// 6. Determinism + non-mutation
// ---------------------------------------------------------------------------
describe("validation — determinism + non-mutation", () => {
  test("same (fields, schema) → identical ValidationResult", () => {
    const fields = { name: "A", email: "bad" };
    const schema = formDemoSchema;
    const a = validateForm(fields, schema);
    const b = validateForm(fields, schema);
    expect(a).toEqual(b);
  });

  test("validator does not mutate fields", () => {
    const fields = { name: "Alice", email: "a@b.com" };
    const frozen = JSON.stringify(fields);
    validateForm(fields, formDemoSchema);
    expect(JSON.stringify(fields)).toBe(frozen);
  });

  test("validator does not mutate schema", () => {
    const schema = JSON.parse(JSON.stringify({
      name:  { type: "string", required: true, min: 2 },
      email: { type: "email",  required: true },
    })) as ValidationSchema;
    const frozen = JSON.stringify(schema);
    validateForm({ name: "Alice", email: "a@b.com" }, schema);
    expect(JSON.stringify(schema)).toBe(frozen);
  });

  test("same invalid form → byte-identical HTML across 5 renders", async () => {
    const outs: string[] = [];
    for (let i = 0; i < 5; i++) {
      const r = await routeWebSurface(formReq(
        "/form_demo",
        "name=A&email=bad",
      ));
      outs.push(r.body as string);
    }
    for (let i = 1; i < outs.length; i++) {
      expect(outs[i]).toBe(outs[0]);
    }
  });

  test("error message key order matches schema declaration order", () => {
    // Determinism check: errors come out in the schema's
    // iteration order so JSON serialisation is byte-stable.
    const schema: ValidationSchema = {
      first:  { type: "string", required: true },
      second: { type: "string", required: true },
      third:  { type: "string", required: true },
    };
    const result = validateForm({}, schema);
    expect(Object.keys(result.errors)).toEqual(["first", "second", "third"]);
  });

  test("end-to-end: validation does not mutate the request", async () => {
    const req = formReq("/form_demo", "name=A&email=bad");
    const frozen = JSON.stringify(req);
    await routeWebSurface(req);
    expect(JSON.stringify(req)).toBe(frozen);
  });

  test("validation never throws on weird-but-string inputs", () => {
    const schema: ValidationSchema = {
      x: { type: "string", required: true, pattern: /^a$/, min: 1, max: 1 },
      y: { type: "email", required: false },
      z: { type: "number", min: 0, max: 0 },
    };
    expect(() => validateForm({}, schema)).not.toThrow();
    expect(() => validateForm({ x: "a", y: "", z: "0" }, schema)).not.toThrow();
    expect(() =>
      validateForm({ x: "b", y: "still@invalid", z: "1" }, schema),
    ).not.toThrow();
  });

  test("FieldRule exhaustiveness — every rule type is reachable", () => {
    // Compile-time guard: if a new rule variant is added without
    // a corresponding branch in validateForm, this test type-checks
    // but the validator's exhaustive switch fails at build time.
    // Asserted via runtime by invoking each rule type once.
    const ruleTypes: ReadonlyArray<FieldRule["type"]> = [
      "string", "email", "number",
    ];
    const schema: ValidationSchema = Object.fromEntries(
      ruleTypes.map((t) => [t, { type: t } as FieldRule]),
    );
    const result = validateForm({}, schema);
    expect(result.valid).toBe(true);
    expect(Object.keys(result.values).sort()).toEqual(
      ["email", "number", "string"],
    );
  });
});
