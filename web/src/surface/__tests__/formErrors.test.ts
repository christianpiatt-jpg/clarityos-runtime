// Card A20-R — server-side form errors tests.
//
// Five contract surfaces under test:
//
//   1. types.ts — FormErrorBag / FormResult / toFieldErrorList
//      shape contracts.
//   2. collectFormErrors — auto-orchestration over a v0.2
//      request. Valid form → empty bag. Invalid form →
//      populated bag. Missing view → empty bag (pass-through).
//      Schema-function view (A15 wizard pattern) → schema picked
//      per fields. Non-string body → empty bag.
//   3. renderFormErrors — empty bag → empty list; populated bag
//      → li per field; HTML-escape of field + message.
//   4. Determinism — same bag → byte-identical HTML across calls.
//   5. Barrel — index.ts re-exports everything callers expect.
//
// Path: web/src/surface/__tests__/formErrors.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  collectFormErrors,
  renderFormErrors,
  EMPTY_FORM_ERRORS,
  toFieldErrorList,
  FormErrorBag,
  FormResult,
  validateForm,
  type ValidationSchema,
} from "../forms";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import {
  registerView,
  _clearViewRegistryForTests,
} from "../viewRegistry";
import { clearTemplateCache } from "../templateCache";
import { clearLayoutCache } from "../layoutCache";
import { clearPartialCache } from "../partialCache";
import { clearAssetManifest } from "../assetManifest";
import { formDemoView, formDemoSchema } from "../views/formDemo";


function req(opts: Partial<WebSurfaceV0_2.Request> = {}): WebSurfaceV0_2.Request {
  return {
    path:    "/form_demo",
    method:  "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body:    "",
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
// 1. types — shape contracts
// ---------------------------------------------------------------------------
describe("FormErrorBag + helpers", () => {
  test("EMPTY_FORM_ERRORS shape is {errors: {}}", () => {
    expect(EMPTY_FORM_ERRORS).toEqual({ errors: {} });
  });

  test("toFieldErrorList preserves Object.entries insertion order", () => {
    const bag: FormErrorBag = {
      errors: {
        name:  "name-error",
        email: "email-error",
        age:   "age-error",
      },
    };
    expect(toFieldErrorList(bag)).toEqual([
      { field: "name",  message: "name-error" },
      { field: "email", message: "email-error" },
      { field: "age",   message: "age-error" },
    ]);
  });

  test("toFieldErrorList on empty bag → empty array", () => {
    expect(toFieldErrorList(EMPTY_FORM_ERRORS)).toEqual([]);
  });

  test("FormResult ok-true / ok-false union narrows correctly", () => {
    const success: FormResult<{ name: string }> = {
      ok: true, values: { name: "Alice" },
    };
    const failure: FormResult<{ name: string }> = {
      ok: false, errors: { errors: { name: "required" } },
    };
    if (success.ok) {
      expect(success.values.name).toBe("Alice");
    } else {
      throw new Error("expected ok=true");
    }
    if (!failure.ok) {
      expect(failure.errors.errors.name).toBe("required");
    } else {
      throw new Error("expected ok=false");
    }
  });
});


// ---------------------------------------------------------------------------
// 2. collectFormErrors — auto-orchestration
// ---------------------------------------------------------------------------
describe("collectFormErrors", () => {
  test("valid form → empty bag", async () => {
    const bag = await collectFormErrors(req({
      body: "name=Alice&email=a%40b.com",
    }));
    expect(bag).toEqual({ errors: {} });
  });

  test("invalid form → populated bag matching validator output", async () => {
    const bag = await collectFormErrors(req({
      body: "name=A&email=not-an-email",
    }));
    expect(bag.errors).toEqual({
      name:  "Must be at least 2 characters.",
      email: "Invalid email address.",
    });
  });

  test("missing-required field → bag carries required message", async () => {
    const bag = await collectFormErrors(req({
      body: "name=&email=",
    }));
    expect(bag.errors).toEqual({
      name:  "This field is required.",
      email: "This field is required.",
    });
  });

  test("unknown view → empty bag (pass-through, no orchestration)", async () => {
    _clearViewRegistryForTests();
    const bag = await collectFormErrors(req({
      body: "name=A",
    }));
    expect(bag).toBe(EMPTY_FORM_ERRORS);
  });

  test("view without a schema → empty bag (no validation possible)", async () => {
    _clearViewRegistryForTests();
    registerView("no_schema", {
      template: "base",
      async render() { return { title: "x", content: "" }; },
    });
    const bag = await collectFormErrors(req({
      path: "/no_schema",
      body: "name=A",
    }));
    expect(bag).toBe(EMPTY_FORM_ERRORS);
  });

  test("schema-function view (A15 wizard pattern) → schema picked per fields", async () => {
    _clearViewRegistryForTests();
    registerView("wizard_probe", {
      template: "base",
      async render() { return { title: "x", content: "" }; },
      schema(fields): ValidationSchema | undefined {
        // Step-based schema: step=1 validates ``name``; step=2
        // validates ``email``. Mirrors A15's wizard pattern.
        if (fields.step === "1") {
          return { name: { type: "string", required: true, min: 2 } };
        }
        if (fields.step === "2") {
          return { email: { type: "email", required: true } };
        }
        return undefined;
      },
    });

    const step1 = await collectFormErrors(req({
      path: "/wizard_probe",
      body: "step=1&name=A",
    }));
    expect(step1.errors).toEqual({
      name: "Must be at least 2 characters.",
    });

    const step2 = await collectFormErrors(req({
      path: "/wizard_probe",
      body: "step=2&email=bad",
    }));
    expect(step2.errors).toEqual({
      email: "Invalid email address.",
    });
  });

  test("non-string body → empty bag (defensive, doesn't throw)", async () => {
    const bag = await collectFormErrors(req({
      body: null,
    }));
    expect(bag).toBe(EMPTY_FORM_ERRORS);
  });

  test("buffer body → empty bag (multipart not supported by this helper)", async () => {
    const bag = await collectFormErrors(req({
      body: Buffer.from("name=Alice"),
    }));
    expect(bag).toBe(EMPTY_FORM_ERRORS);
  });

  test("does not mutate the request", async () => {
    const r = req({ body: "name=Alice&email=a%40b.com" });
    const frozen = JSON.stringify(r);
    await collectFormErrors(r);
    expect(JSON.stringify(r)).toBe(frozen);
  });

  test("schema iteration order preserved (deterministic key order)", async () => {
    const bag = await collectFormErrors(req({
      body: "name=&email=",
    }));
    // formDemoSchema declares name before email.
    expect(Object.keys(bag.errors)).toEqual(["name", "email"]);
  });
});


// ---------------------------------------------------------------------------
// 3. renderFormErrors — HTML output
// ---------------------------------------------------------------------------
describe("renderFormErrors", () => {
  test("empty bag → empty <ul>", () => {
    const html = renderFormErrors(EMPTY_FORM_ERRORS);
    expect(html).toContain('<ul class="form-errors">');
    expect(html).toContain("</ul>");
    expect(html).not.toContain("<li");
  });

  test("populated bag → <li data-field> per error", () => {
    const html = renderFormErrors({
      errors: {
        name:  "Must be at least 2 characters.",
        email: "Invalid email address.",
      },
    });
    expect(html).toContain('<li data-field="name">Must be at least 2 characters.</li>');
    expect(html).toContain('<li data-field="email">Invalid email address.</li>');
  });

  test("HTML-escapes the message (defence-in-depth)", () => {
    const html = renderFormErrors({
      errors: {
        x: '"><script>alert(1)</script>',
      },
    });
    expect(html).not.toContain('<script>alert(1)</script>');
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(html).toContain('&quot;');
  });

  test("HTML-escapes the field name too", () => {
    const html = renderFormErrors({
      errors: {
        '"><img>': "msg",
      },
    });
    expect(html).not.toContain('<img>');
    expect(html).toContain('&lt;img&gt;');
  });

  test("error order matches insertion order (deterministic)", () => {
    const html = renderFormErrors({
      errors: {
        c: "third",
        a: "first",
        b: "second",
      },
    });
    const cIdx = html.indexOf("third");
    const aIdx = html.indexOf("first");
    const bIdx = html.indexOf("second");
    expect(cIdx).toBeGreaterThan(-1);
    expect(aIdx).toBeGreaterThan(cIdx);  // a comes after c in the bag
    expect(bIdx).toBeGreaterThan(aIdx);
  });
});


// ---------------------------------------------------------------------------
// 4. Determinism
// ---------------------------------------------------------------------------
describe("renderFormErrors — determinism", () => {
  test("same bag → byte-identical HTML across 5 renders", () => {
    const bag: FormErrorBag = {
      errors: {
        name:  "Must be at least 2 characters.",
        email: "Invalid email address.",
      },
    };
    const outs: string[] = [];
    for (let i = 0; i < 5; i++) {
      outs.push(renderFormErrors(bag));
    }
    for (let i = 1; i < outs.length; i++) {
      expect(outs[i]).toBe(outs[0]);
    }
  });

  test("does not mutate the input bag", () => {
    const bag: FormErrorBag = { errors: { x: "y" } };
    const frozen = JSON.stringify(bag);
    renderFormErrors(bag);
    expect(JSON.stringify(bag)).toBe(frozen);
  });
});


// ---------------------------------------------------------------------------
// 5. Barrel — index.ts re-exports
// ---------------------------------------------------------------------------
describe("forms/index — barrel re-exports", () => {
  test("re-exports validateForm so callers don't need ../validator", () => {
    // Use validateForm directly to confirm it's callable
    // through the barrel.
    const result = validateForm(
      { name: "Alice" },
      { name: { type: "string", required: true, min: 2 } },
    );
    expect(result.valid).toBe(true);
    expect(result.values).toEqual({ name: "Alice" });
  });

  test("re-exports schema types so callers can author schemas", () => {
    // The fact that ``ValidationSchema`` type-imports cleanly
    // is a compile-time guarantee. Runtime check: use a
    // schema-typed value end-to-end.
    const schema: ValidationSchema = formDemoSchema;
    const result = validateForm({ name: "Alice", email: "a@b.com" }, schema);
    expect(result.valid).toBe(true);
  });
});
