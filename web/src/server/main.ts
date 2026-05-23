/**
 * Web Surface v0.2.0 — Node HTTP server bootstrap (Track C).
 *
 * This is the file the container CMD runs:
 *
 *     npx tsx src/server/main.ts
 *
 * It does one thing: create an http.Server around the request
 * handler from ``requestHandler.ts`` and listen on
 * ``0.0.0.0:$PORT``. No logic lives here — every decision
 * (routing, normalisation, error handling) is in the modules
 * this file imports.
 *
 * Why bootstrap is split out from requestHandler.ts:
 *   * Tests import ``createRequestHandler`` directly and drive
 *     it against mock req/res. They MUST NOT trigger
 *     ``server.listen()`` as a side effect of import. Splitting
 *     bootstrap into its own module makes that guarantee
 *     structural (tests just don't import main.ts).
 *
 * Environment:
 *   * ``PORT``         — bind port. Defaults to 8080 (Cloud Run
 *                        default).
 *   * ``ENVIRONMENT``  — ``local`` | ``staging`` | ``prod``.
 *                        Only used for log labelling. NO
 *                        environment-specific behaviour beyond
 *                        logging (Track C invariant).
 *
 * The container always binds to ``0.0.0.0`` — Cloud Run
 * requirement.
 */
import { createServer } from "node:http";

import { createRequestHandler } from "./requestHandler";


const DEFAULT_PORT = 8080;
const HOST = "0.0.0.0";


function _resolvePort(): number {
  const raw = process.env.PORT;
  if (!raw) return DEFAULT_PORT;
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0 || n > 65535) {
    // Bad PORT — log and fall back rather than crashing.
    // eslint-disable-next-line no-console
    console.warn(
      `[clarityos-web-v0-2] invalid PORT=${raw}, ` +
      `falling back to ${DEFAULT_PORT}`,
    );
    return DEFAULT_PORT;
  }
  return n;
}


function _resolveEnvironment(): string {
  const env = (process.env.ENVIRONMENT ?? "local").toLowerCase();
  if (env === "local" || env === "staging" || env === "prod") {
    return env;
  }
  return "local";
}


function main(): void {
  const port = _resolvePort();
  const environment = _resolveEnvironment();
  const handler = createRequestHandler();
  const server = createServer((req, res) => {
    // ``handle`` is async; the http.Server contract is
    // synchronous, so we fire-and-forget here. Any throw
    // inside ``handle`` is already swallowed by its own
    // try/catch (see requestHandler.ts).
    void handler(req, res);
  });
  server.listen(port, HOST, () => {
    // eslint-disable-next-line no-console
    console.log(
      `[clarityos-web-v0-2] env=${environment} listening on ` +
      `${HOST}:${port}`,
    );
  });
}


main();
