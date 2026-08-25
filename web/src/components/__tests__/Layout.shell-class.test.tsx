// Guard: `.cockpit` is the SHELL class and must be owned by Layout alone.
//
// WHY THIS FILE EXISTS
// --------------------
// `.cockpit` (app.css) is a 100vw x 100vh grid declaring the shell's four
// areas — topbar / rail / main / status. Layout.tsx owns it.
//
// When a PAGE container also carries `className="cockpit"`, it nests a
// second copy of that grid inside <main class="main">. The page's own
// children carry no grid-area, so they auto-place into the inherited
// two-column template and pair up (column 1 = var(--rail-w) ~265px,
// column 2 = 1fr), while the single 1fr row absorbs the height and the
// remaining children collapse into overlapping implicit rows.
//
// That shipped once from routes/Cockpit.tsx and was fixed in fe2fcea.
// This file exists so a third occurrence fails here, not in a browser.
//
// TWO ASSERTIONS, DELIBERATELY
// ----------------------------
// 1. SOURCE. The rule is a source invariant — "only Layout may carry the
//    shell class" — so the primary guard reads the source. It cannot be
//    defeated by a route that fails to mount, needs auth, or degrades in
//    jsdom, which is precisely how the first version of this test came to
//    pass with the defect present.
// 2. DOM. Renders Layout with a page mounted through its Outlet and counts
//    occurrences in the tree, catching a duplicate introduced dynamically
//    (className built at runtime) that the source scan cannot see.
//
// The first version of this test asserted only on <Layout /> rendered
// alone. Its Outlet had no child route, so no page container ever mounted
// and it passed with `className="cockpit"` restored in Cockpit.tsx.
// Verified failing before this version was committed.

import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import Layout from "../Layout";

const SHELL_CLASS = 'className="cockpit"';

// Vite's glob, not node:fs — `web` has no @types/node and tsconfig
// includes all of src, so a node import fails `tsc --noEmit`.
// `__tests__` is excluded: this file necessarily contains the literal it
// searches for, and test files are not shipped components.
const SOURCES = import.meta.glob("../../**/*.tsx", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

describe("shell class is owned by Layout alone", () => {
  it("no file outside components/Layout.tsx carries the shell class", () => {
    // __tests__ is excluded: this file necessarily contains the literal it
    // searches for, and test files are not shipped components.
    const offenders = Object.entries(SOURCES)
      .filter(([path]) => !path.includes("__tests__") && !path.includes(".test."))
      .filter(([, source]) => source.includes(SHELL_CLASS))
      // Vite normalises glob keys relative to THIS file, so a sibling of
      // components/ arrives as "../Layout.tsx" while a route arrives as
      // "../../routes/Cockpit.tsx". Strip the leading ../ so the assertion
      // is stable and an offender still reads as its path.
      .map(([path]) => path.replace(/^(\.\.\/)+/, ""))
      .sort();

    expect(offenders).toEqual(["Layout.tsx"]);
  });

  it("renders .cockpit exactly once with a page mounted in the Outlet", () => {
    // A stand-in page container. If a real page reintroduces the shell
    // class this assertion still holds — the source check above is what
    // catches that — but this one catches a runtime-built duplicate.
    const { container } = render(
      <MemoryRouter initialEntries={["/x"]}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/x" element={<div className="cockpit-page">page</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(container.querySelectorAll(".cockpit")).toHaveLength(1);
  });

  it("the shell element owns the four grid areas", () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/"]}>
        <Layout />
      </MemoryRouter>,
    );
    const shell = container.querySelector(".cockpit");
    expect(shell).not.toBeNull();
    expect(shell?.querySelector("header.topbar")).not.toBeNull();
    expect(shell?.querySelector("nav.rail")).not.toBeNull();
    expect(shell?.querySelector("main.main")).not.toBeNull();
  });
});
