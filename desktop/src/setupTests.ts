// Card 8.5a — Vitest setup for the desktop renderer tests. Pulls in
// @testing-library/jest-dom matchers (toBeInTheDocument, toHaveTextContent,
// etc.) so component tests can assert against the rendered DOM ergonomically.
// Mirrors web/src/test-setup.ts.

import "@testing-library/jest-dom/vitest";

// jsdom doesn't ship scrollIntoView; stub once globally so any component
// that calls it during a test doesn't need a per-render monkey-patch.
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  // eslint-disable-next-line @typescript-eslint/no-empty-function
  Element.prototype.scrollIntoView = function noop() {};
}
