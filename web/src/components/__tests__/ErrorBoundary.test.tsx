// Phase 6 — shared ErrorBoundary tests.
import { afterEach, describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { type ReactElement } from "react";

import ErrorBoundary from "../ErrorBoundary";

// Always throws; the ReactElement annotation makes it a valid JSX component
// type (it never actually returns).
function Boom(): ReactElement {
  throw new Error("kaboom");
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ErrorBoundary", () => {
  test("renders children when there is no error", () => {
    render(
      <ErrorBoundary>
        <div>safe content</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText("safe content")).toBeInTheDocument();
    expect(screen.queryByTestId("error-boundary")).toBeNull();
  });

  test("renders the fallback with the error message when a child throws", () => {
    // React logs the caught error to console.error — silence the expected noise.
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary label="Boom happened">
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByTestId("error-boundary")).toBeInTheDocument();
    expect(screen.getByText("Boom happened")).toBeInTheDocument();
    expect(screen.getByTestId("error-boundary-message")).toHaveTextContent("kaboom");
  });

  test("Try again clears the error and re-renders recovered children", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    let shouldThrow = true;
    function Flaky() {
      if (shouldThrow) throw new Error("first-fail");
      return <div>recovered</div>;
    }
    render(
      <ErrorBoundary>
        <Flaky />
      </ErrorBoundary>,
    );
    expect(screen.getByTestId("error-boundary")).toBeInTheDocument();
    shouldThrow = false;
    fireEvent.click(screen.getByTestId("error-boundary-retry"));
    expect(screen.getByText("recovered")).toBeInTheDocument();
    expect(screen.queryByTestId("error-boundary")).toBeNull();
  });
});
