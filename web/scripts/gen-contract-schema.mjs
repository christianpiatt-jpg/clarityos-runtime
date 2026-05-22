#!/usr/bin/env node
// PASS — v0.2.0 Web Surface contract — JSON Schema generator.
//
// Generates a deterministic, version-pinned JSON Schema from the
// canonical TypeScript contract at:
//
//     web/src/contracts/webSurfaceV0_2.ts
//
// Output:
//
//     web/src/contracts/webSurfaceV0_2.schema.json
//
// The schema is the bridge between the Vite/React SPA (TS, this
// side) and the FastAPI handler (Python, web_surface.py). Both
// sides validate against this file — when the TS contract changes,
// re-running this script regenerates the schema, which is then
// reviewable in a single commit diff.
//
// Determinism contract:
//   * keys sorted lexicographically at every depth
//   * 2-space indent
//   * single trailing newline
//   * version string is extracted from the TS source (not hardcoded)
//     so a forgotten VERSION bump surfaces in the diff
//
// Usage:
//
//     npm run contracts:gen
//     # or, to verify the committed schema is up to date with the TS:
//     npm run contracts:check
//
import { createGenerator } from "ts-json-schema-generator";
import { writeFileSync, readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const WEB_ROOT = resolve(__dirname, "..");

const CONTRACT_PATH = resolve(WEB_ROOT, "src/contracts/webSurfaceV0_2.ts");
const TSCONFIG_PATH = resolve(WEB_ROOT, "tsconfig.json");
const OUTPUT_PATH = resolve(WEB_ROOT, "src/contracts/webSurfaceV0_2.schema.json");

/**
 * Sort every object's keys deterministically. Arrays preserve order
 * (they're semantically ordered in JSON Schema — anyOf, oneOf,
 * required[]); only object keys get reshuffled.
 */
function sortKeysDeep(value) {
  if (Array.isArray(value)) {
    return value.map(sortKeysDeep);
  }
  if (value && typeof value === "object" && value.constructor === Object) {
    const sorted = {};
    for (const key of Object.keys(value).sort()) {
      sorted[key] = sortKeysDeep(value[key]);
    }
    return sorted;
  }
  return value;
}

/**
 * Extract the contract VERSION constant from the TS source. This
 * keeps the schema's version field in lock-step with the contract's
 * own pin — if a developer bumps WebSurfaceV0_2.VERSION without
 * re-running the generator, the contracts:check CI guard catches
 * the stale schema.
 */
function extractContractVersion(tsSource) {
  const match = tsSource.match(/VERSION\s*=\s*"([^"]+)"/);
  if (!match) {
    throw new Error(
      "could not extract VERSION constant from contract source — " +
        "expected a line like `VERSION = \"v0.2.0\"`",
    );
  }
  return match[1];
}

function main() {
  let tsSource;
  try {
    tsSource = readFileSync(CONTRACT_PATH, "utf-8");
  } catch (err) {
    console.error(`✗ failed to read contract: ${CONTRACT_PATH}\n  ${err.message}`);
    process.exit(1);
  }

  const contractVersion = extractContractVersion(tsSource);

  // ts-json-schema-generator config. ``type: "*"`` emits a single
  // schema with every exported type from the contract module under
  // ``$defs`` / ``definitions``, which gives the Python side every
  // shape it needs (Request, Response, ErrorEnvelope, SurfaceAction)
  // in one artifact.
  const config = {
    path: CONTRACT_PATH,
    tsconfig: TSCONFIG_PATH,
    type: "*",
    expose: "all",
    topRef: true,
    jsDoc: "extended",
    sortProps: true,
    strictTuples: true,
    skipTypeCheck: false,
    additionalProperties: false,
  };

  let baseSchema;
  try {
    const generator = createGenerator(config);
    baseSchema = generator.createSchema(config.type);
  } catch (err) {
    console.error(`✗ schema generation failed:\n  ${err.message}`);
    process.exit(1);
  }

  // Augment with metadata: title + contract version + an inline
  // provenance pointer. We keep ``$schema`` if the generator set
  // it; otherwise emit the draft-07 marker (what ts-json-schema-
  // generator currently uses).
  const augmented = {
    $schema: baseSchema.$schema ?? "http://json-schema.org/draft-07/schema#",
    $comment:
      "Auto-generated from web/src/contracts/webSurfaceV0_2.ts. " +
      "Do not hand-edit — run `npm run contracts:gen` in web/ instead. " +
      "The version field below is extracted from the contract's VERSION constant.",
    title: "WebSurfaceV0_2",
    version: contractVersion,
    ...baseSchema,
  };

  // Force the augmented metadata to win over any generator output of
  // the same keys, then sort everything for determinism.
  augmented.$schema = baseSchema.$schema ?? "http://json-schema.org/draft-07/schema#";
  augmented.title = "WebSurfaceV0_2";
  augmented.version = contractVersion;

  const out = JSON.stringify(sortKeysDeep(augmented), null, 2) + "\n";

  try {
    writeFileSync(OUTPUT_PATH, out);
  } catch (err) {
    console.error(`✗ failed to write schema: ${OUTPUT_PATH}\n  ${err.message}`);
    process.exit(1);
  }

  console.log(
    `✓ wrote ${OUTPUT_PATH.replace(WEB_ROOT + "/", "")} ` +
      `(WebSurfaceV0_2 ${contractVersion})`,
  );
}

main();
