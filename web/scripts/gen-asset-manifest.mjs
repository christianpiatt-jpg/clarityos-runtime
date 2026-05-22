#!/usr/bin/env node
// Card A10 — Track A — v0.2.0 Web Surface asset manifest generator.
//
// Produces a deterministic JSON snapshot of every tracked static
// asset's fingerprinted filename:
//
//     web/assets/v0.2/manifest.json
//
// The snapshot is the runtime source of truth for cache-safe URLs.
// The render pipeline imports manifest.json directly; the asset
// manifest module (TS) bootstraps from the same file at module
// load. CI runs this generator and asserts the on-disk JSON is
// byte-identical to a fresh generation — that is the drift gate
// (scripts/check_asset_manifest.sh).
//
// Algorithm parity:
//   The hash logic here MUST agree with
//   ``web/src/surface/assetFingerprint.ts`` (fingerprintAsset).
//   Both:
//     * read the raw asset bytes via fs.readFileSync,
//     * compute sha256, slice the first 12 hex chars,
//     * format ``base.<hash>.<ext>`` where ``ext`` is the substring
//       after the LAST dot in the pathname.
//   The vitest test suite locks this equivalence — if either
//   side drifts, A10's snapshot tests fail.
//
// Determinism contract:
//   * Sorted keys (lexicographic) at the top level.
//   * 2-space indent.
//   * Single trailing newline.
//   * No timestamps, no host data, no environment-derived values.
//   * Two identical input directories produce byte-identical output.
//
// Usage:
//
//     npm run assets:gen          # regenerate manifest.json
//     npm run assets:check        # regenerate + git-diff guard
//
// Pure Node (createHash + readFileSync + writeFileSync). No
// dependency on the TS source — running this script does not
// require a build step, which keeps it usable in CI without
// transpilation.

import { writeFileSync, readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const WEB_ROOT = resolve(__dirname, "..");
const ASSETS_DIR = resolve(WEB_ROOT, "assets", "v0.2");
const MANIFEST_PATH = join(ASSETS_DIR, "manifest.json");

/** Width of the hex prefix sliced from the SHA-256 digest. MUST
 *  match ``FINGERPRINT_HEX_LENGTH`` in
 *  web/src/surface/assetFingerprint.ts. */
const FINGERPRINT_HEX_LENGTH = 12;

/** Tracked assets — every entry below ships in v0.2.0. Adding a
 *  new asset means appending its pathname here AND regenerating
 *  manifest.json. The drift gate enforces both. */
const TRACKED_ASSETS = [
  "app.js",
  "style.css",
];

/**
 * Compute ``base.<12-hex>.ext`` for a pathname relative to
 * ASSETS_DIR. Mirror of fingerprintAsset() in TS — must produce
 * identical results.
 */
function fingerprintAsset(pathname) {
  const buf = readFileSync(join(ASSETS_DIR, pathname));
  const hash = createHash("sha256")
    .update(buf)
    .digest("hex")
    .slice(0, FINGERPRINT_HEX_LENGTH);

  const dotIdx = pathname.lastIndexOf(".");
  if (dotIdx <= 0 || dotIdx === pathname.length - 1) {
    return `${pathname}.${hash}`;
  }
  const base = pathname.slice(0, dotIdx);
  const ext = pathname.slice(dotIdx + 1);
  return `${base}.${hash}.${ext}`;
}

function main() {
  const manifest = {};
  for (const pathname of [...TRACKED_ASSETS].sort()) {
    manifest[pathname] = fingerprintAsset(pathname);
  }

  const out = JSON.stringify(manifest, null, 2) + "\n";

  try {
    writeFileSync(MANIFEST_PATH, out);
  } catch (err) {
    console.error(`✗ failed to write manifest: ${MANIFEST_PATH}\n  ${err.message}`);
    process.exit(1);
  }

  const relPath = MANIFEST_PATH.replace(WEB_ROOT + "/", "").replace(WEB_ROOT + "\\", "");
  console.log(`✓ wrote ${relPath} (${Object.keys(manifest).length} assets)`);
}

main();
