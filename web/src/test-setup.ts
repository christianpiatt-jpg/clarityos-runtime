// v48 — Vitest setup. Pulls in @testing-library/jest-dom matchers
// (toBeInTheDocument, toHaveTextContent, etc.) so route tests can
// assert against the rendered DOM ergonomically.

import "@testing-library/jest-dom/vitest";

// jsdom doesn't ship scrollIntoView; the Threads route calls it after
// every send. Stub once globally so tests don't need to monkey-patch
// per-render.
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  // eslint-disable-next-line @typescript-eslint/no-empty-function
  Element.prototype.scrollIntoView = function noop() {};
}
