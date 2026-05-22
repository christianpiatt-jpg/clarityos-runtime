// Structural tests for the generated v0.2.0 Web Surface JSON Schema.
//
// The schema is produced by `npm run contracts:gen` from the
// canonical TypeScript contract. These tests lock the SHAPE of the
// generated artifact so that:
//
//   * regenerating the schema without re-running tests can't
//     silently change the wire contract,
//   * the contract VERSION pin stays in lock-step with the
//     generated schema (catches "bumped TS, forgot to regenerate"),
//   * the FastAPI handler can rely on a stable set of definition
//     names and required-field lists.
//
// If a structural assertion below fails after a contract edit, the
// fix is usually one of:
//   1. you intended the shape change → update the assertion here
//      AND bump WebSurfaceV0_2.VERSION (breaking change), or
//   2. you didn't intend it → revert the contract edit.
//
// Path: web/src/contracts/__tests__/webSurfaceV0_2.schema.test.ts
import { describe, expect, test } from "vitest";

import schemaJson from "../webSurfaceV0_2.schema.json";
import { WebSurfaceV0_2 } from "../webSurfaceV0_2";


// Re-type for assertion ergonomics. The schema is generated, so its
// shape is well-known at runtime even if TypeScript only sees it as
// the JSON literal type.
const schema = schemaJson as Record<string, any>;


describe("WebSurfaceV0_2 schema — top-level metadata", () => {
  test("loads as a parsed JSON object", () => {
    expect(schema).toBeTruthy();
    expect(typeof schema).toBe("object");
  });

  test("carries title, $schema, $comment, version, definitions", () => {
    expect(Object.keys(schema).sort()).toEqual(
      ["$comment", "$schema", "definitions", "title", "version"],
    );
  });

  test("title is the namespace name", () => {
    expect(schema.title).toBe("WebSurfaceV0_2");
  });

  test("$schema is JSON Schema draft-07", () => {
    expect(schema.$schema).toBe("http://json-schema.org/draft-07/schema#");
  });

  test("$comment marks the file as auto-generated", () => {
    expect(schema.$comment).toMatch(/Auto-generated/i);
    expect(schema.$comment).toMatch(/contracts:gen/);
  });

  test("version matches the contract's VERSION constant", () => {
    expect(schema.version).toBe(WebSurfaceV0_2.VERSION);
    expect(schema.version).toBe("v0.2.0");
  });
});


describe("WebSurfaceV0_2 schema — definitions inventory", () => {
  // The four contract-defined shapes MUST appear under
  // `definitions`. ts-json-schema-generator may emit additional
  // helper defs (Record<string,string>, etc.) — we don't gate on
  // those, only on the contract-public ones.
  const REQUIRED_DEFS = [
    "WebSurfaceV0_2.Request",
    "WebSurfaceV0_2.Response",
    "WebSurfaceV0_2.ErrorEnvelope",
    "WebSurfaceV0_2.SurfaceAction",
  ];

  test.each(REQUIRED_DEFS)("definitions contains %s", (name) => {
    expect(schema.definitions).toBeDefined();
    expect(schema.definitions[name]).toBeDefined();
  });
});


describe("WebSurfaceV0_2 schema — ErrorEnvelope shape", () => {
  const env = (schema.definitions as Record<string, any>)[
    "WebSurfaceV0_2.ErrorEnvelope"
  ];

  test("is an object type", () => {
    expect(env.type).toBe("object");
  });

  test("requires the `error` field only", () => {
    expect(env.required).toEqual(["error"]);
  });

  test("`error` is a string", () => {
    expect(env.properties.error.type).toBe("string");
  });

  test("`detail` is present and unconstrained (matches `unknown`)", () => {
    expect(env.properties).toHaveProperty("detail");
    // ``unknown`` in TS → ``{}`` in JSON Schema (no constraints).
    expect(env.properties.detail).toEqual({});
  });

  test("forbids additional properties", () => {
    expect(env.additionalProperties).toBe(false);
  });
});


describe("WebSurfaceV0_2 schema — Request envelope", () => {
  const req = (schema.definitions as Record<string, any>)[
    "WebSurfaceV0_2.Request"
  ];

  test("is an object type", () => {
    expect(req.type).toBe("object");
  });

  test("requires path + method + headers + body", () => {
    expect(req.required.sort()).toEqual(
      ["body", "headers", "method", "path"],
    );
  });

  test("`path` and `method` are strings", () => {
    expect(req.properties.path.type).toBe("string");
    expect(req.properties.method.type).toBe("string");
  });

  test("`headers` references the Record<string,string> helper def", () => {
    expect(req.properties.headers.$ref).toContain("Record");
  });

  test("forbids additional properties", () => {
    expect(req.additionalProperties).toBe(false);
  });
});


describe("WebSurfaceV0_2 schema — Response envelope", () => {
  const res = (schema.definitions as Record<string, any>)[
    "WebSurfaceV0_2.Response"
  ];

  test("is an object type", () => {
    expect(res.type).toBe("object");
  });

  test("requires status + headers + body", () => {
    expect(res.required.sort()).toEqual(["body", "headers", "status"]);
  });

  test("`status` is a number", () => {
    expect(res.properties.status.type).toBe("number");
  });

  test("`headers` references the Record<string,string> helper def", () => {
    expect(res.properties.headers.$ref).toContain("Record");
  });

  test("forbids additional properties", () => {
    expect(res.additionalProperties).toBe(false);
  });
});


describe("WebSurfaceV0_2 schema — SurfaceAction discriminated union", () => {
  const action = (schema.definitions as Record<string, any>)[
    "WebSurfaceV0_2.SurfaceAction"
  ];

  test("is an anyOf union", () => {
    expect(Array.isArray(action.anyOf)).toBe(true);
  });

  test("has exactly three variants", () => {
    expect(action.anyOf).toHaveLength(3);
  });

  // Pull every variant's `type` const out so we can assert the
  // discriminator inventory regardless of variant ordering.
  const discriminators = action.anyOf.map(
    (v: any) => v.properties.type.const,
  );

  test("variants cover noop + render + navigate", () => {
    expect(discriminators.sort()).toEqual(
      ["navigate", "noop", "render"],
    );
  });

  test("every variant forbids additional properties", () => {
    for (const v of action.anyOf) {
      expect(v.additionalProperties).toBe(false);
    }
  });

  test("noop variant only requires `type`", () => {
    const noop = action.anyOf.find(
      (v: any) => v.properties.type.const === "noop",
    );
    expect(noop.required).toEqual(["type"]);
    expect(Object.keys(noop.properties)).toEqual(["type"]);
  });

  test("render variant requires `type` + `view`, params optional", () => {
    const render = action.anyOf.find(
      (v: any) => v.properties.type.const === "render",
    );
    expect(render.required.sort()).toEqual(["type", "view"]);
    expect(render.properties.view.type).toBe("string");
    expect(render.properties).toHaveProperty("params");
  });

  test("navigate variant requires `type` + `path`", () => {
    const nav = action.anyOf.find(
      (v: any) => v.properties.type.const === "navigate",
    );
    expect(nav.required.sort()).toEqual(["path", "type"]);
    expect(nav.properties.path.type).toBe("string");
  });

  test("discriminator inventory matches SurfaceActionType constants", () => {
    expect(discriminators.sort()).toEqual(
      [
        WebSurfaceV0_2.SurfaceActionType.navigate,
        WebSurfaceV0_2.SurfaceActionType.noop,
        WebSurfaceV0_2.SurfaceActionType.render,
      ].sort(),
    );
  });
});


describe("WebSurfaceV0_2 schema — additionalProperties policy", () => {
  test("every contract-public object forbids additional properties", () => {
    const defs = schema.definitions as Record<string, any>;
    const offenders: string[] = [];
    for (const name of [
      "WebSurfaceV0_2.Request",
      "WebSurfaceV0_2.Response",
      "WebSurfaceV0_2.ErrorEnvelope",
    ]) {
      if (defs[name].additionalProperties !== false) {
        offenders.push(name);
      }
    }
    expect(offenders).toEqual([]);
  });
});
