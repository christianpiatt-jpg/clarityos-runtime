// @vitest-environment jsdom
//
// Card A21-R — client-side diagnostic-toggle tests.
//
// Six behaviours under test:
//
//   1. Click on data-diagnostic-toggle → fetches /__diagnostics
//      and replaces the data-diagnostic-target's innerHTML.
//   2. Non-HTML response → silent no-op (target unchanged).
//   3. Network failure → silent no-op (no throw, no fallback).
//   4. Missing data-diagnostic-target → no-op.
//   5. Missing target element → no-op.
//   6. Idempotent listener binding: re-importing the module does
//      NOT register a second click handler (existing A19-R
//      symbol guard preserved).
//   7. Charset-suffix content-type still detected (text/html;
//      charset=utf-8 → replace).
//   8. Does not interfere with A19-R toggle / A20-R form paths
//      (other handlers continue to work after the diagnostic
//      handler runs).
//
// Path: web/src/client/__tests__/diagnosticEnhance.test.ts
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";


function resetDocument(): void {
  document.documentElement.className = "";
  document.body.innerHTML = "";
}


async function loadEnhance(): Promise<void> {
  vi.resetModules();
  await import("../enhance");
}


function makeFetchMock(
  status: number,
  contentType: string | null,
  body: string,
): ReturnType<typeof vi.fn> {
  return vi.fn(async () => ({
    ok:      status >= 200 && status < 300,
    status,
    headers: {
      get(name: string): string | null {
        return name.toLowerCase() === "content-type" ? contentType : null;
      },
    },
    text: async () => body,
  }) as unknown as Response);
}


function setupTrigger(): {
  trigger: HTMLButtonElement;
  out:     HTMLDivElement;
} {
  document.body.innerHTML = `
    <button id="t"
            data-diagnostic-toggle
            data-diagnostic-target="#out">
      diag
    </button>
    <div id="out">initial</div>
  `;
  const trigger = document.getElementById("t") as HTMLButtonElement;
  const out = document.getElementById("out") as HTMLDivElement;
  return { trigger, out };
}


beforeEach(() => {
  resetDocument();
});

afterEach(() => {
  vi.restoreAllMocks();
  resetDocument();
});


// ---------------------------------------------------------------------------
// 1. Happy path: HTML response → replace target
// ---------------------------------------------------------------------------
describe("HTML response → replace target", () => {
  test("click fetches /__diagnostics and swaps fragment in", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html; charset=utf-8",
      '<div class="diagnostic-panel" data-diagnostic-fragment>' +
      '<pre data-json>{"entries":[]}</pre></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { trigger, out } = setupTrigger();
    await loadEnhance();
    trigger.click();
    // Allow the promise chain inside the click handler to flush.
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const callArgs = fetchMock.mock.calls[0];
    expect(callArgs[0]).toBe("/__diagnostics");
    expect(out.innerHTML).toContain('data-diagnostic-fragment');
    expect(out.innerHTML).toContain('data-json');
  });

  test("nested element inside the trigger also fires the handler", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<p>ok</p>',
    );
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <button id="t"
              data-diagnostic-toggle
              data-diagnostic-target="#out">
        <span id="inner">diag</span>
      </button>
      <div id="out">initial</div>
    `;
    const inner = document.getElementById("inner") as HTMLSpanElement;
    const out   = document.getElementById("out")   as HTMLDivElement;

    await loadEnhance();
    inner.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toBe('<p>ok</p>');
  });
});


// ---------------------------------------------------------------------------
// 2. Non-HTML response → silent no-op
// ---------------------------------------------------------------------------
describe("non-HTML response → silent no-op", () => {
  test("application/json → target unchanged", async () => {
    const fetchMock = makeFetchMock(
      200,
      "application/json",
      '{"entries":[]}',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { trigger, out } = setupTrigger();
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(out.innerHTML).toBe("initial");
  });

  test("text/plain → target unchanged", async () => {
    const fetchMock = makeFetchMock(200, "text/plain", "not html");
    vi.stubGlobal("fetch", fetchMock);

    const { trigger, out } = setupTrigger();
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toBe("initial");
  });

  test("missing content-type header → target unchanged", async () => {
    const fetchMock = makeFetchMock(200, null, "<p>html-but-no-ct</p>");
    vi.stubGlobal("fetch", fetchMock);

    const { trigger, out } = setupTrigger();
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toBe("initial");
  });
});


// ---------------------------------------------------------------------------
// 3. Network failure → silent no-op
// ---------------------------------------------------------------------------
describe("network failure → silent no-op", () => {
  test("fetch throws → no submit, no innerHTML change", async () => {
    const fetchMock = vi.fn(async () => {
      throw new Error("offline");
    });
    vi.stubGlobal("fetch", fetchMock);

    const { trigger, out } = setupTrigger();
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toBe("initial");
    // No fallback submission attempted (read-only route).
    // Just confirming the trigger element is unchanged.
    expect(trigger.getAttribute("data-diagnostic-toggle")).toBe("");
  });
});


// ---------------------------------------------------------------------------
// 4-5. Missing target attribute / element → no-op
// ---------------------------------------------------------------------------
describe("missing target → no-op", () => {
  test("trigger without data-diagnostic-target → no fetch", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>ok</p>");
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <button id="t" data-diagnostic-toggle>diag</button>
    `;
    const trigger = document.getElementById("t") as HTMLButtonElement;
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("trigger pointing at a missing selector → no fetch", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>ok</p>");
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <button id="t"
              data-diagnostic-toggle
              data-diagnostic-target="#nope">diag</button>
    `;
    const trigger = document.getElementById("t") as HTMLButtonElement;
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("bad CSS selector → silent no-op (no fetch, no throw)", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>ok</p>");
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <button id="t"
              data-diagnostic-toggle
              data-diagnostic-target="###bad###">diag</button>
    `;
    const trigger = document.getElementById("t") as HTMLButtonElement;
    await loadEnhance();
    // querySelector throws for invalid selectors; the handler
    // must catch and no-op.
    expect(() => trigger.click()).not.toThrow();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).not.toHaveBeenCalled();
  });
});


// ---------------------------------------------------------------------------
// 6. Idempotent listener binding
// ---------------------------------------------------------------------------
describe("idempotent listener binding (A19-R guard preserved)", () => {
  test("re-importing the module does NOT double-fire the fetch", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>ok</p>");
    vi.stubGlobal("fetch", fetchMock);

    const { trigger } = setupTrigger();
    await loadEnhance();
    await loadEnhance();  // second import; symbol guard should
                          // skip re-binding the click listener.
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});


// ---------------------------------------------------------------------------
// 7. Charset-suffix content-type still detected
// ---------------------------------------------------------------------------
describe("content-type charset suffix", () => {
  test("'text/html; charset=utf-8' detected as HTML → replace", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html; charset=utf-8",
      '<p>ok</p>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { trigger, out } = setupTrigger();
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toBe('<p>ok</p>');
  });

  test("uppercase 'TEXT/HTML' still detected (case-insensitive)", async () => {
    const fetchMock = makeFetchMock(
      200,
      "TEXT/HTML; CHARSET=UTF-8",
      '<p>ok</p>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { trigger, out } = setupTrigger();
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toBe('<p>ok</p>');
  });
});


// ---------------------------------------------------------------------------
// 8. Non-interference with A19-R / A20-R paths
// ---------------------------------------------------------------------------
describe("non-interference with prior cards", () => {
  test("A19-R toggle path still works alongside diagnostic toggle", async () => {
    document.body.innerHTML = `
      <button id="diag-btn"
              data-diagnostic-toggle
              data-diagnostic-target="#diag-out">d</button>
      <div id="diag-out">initial</div>

      <button id="toggle-btn"
              data-toggle-target="#panel">t</button>
      <div id="panel">p</div>
    `;
    const fetchMock = makeFetchMock(200, "text/html", "<p>x</p>");
    vi.stubGlobal("fetch", fetchMock);

    await loadEnhance();
    const panel = document.getElementById("panel") as HTMLDivElement;
    const toggleBtn = document.getElementById("toggle-btn") as HTMLButtonElement;
    toggleBtn.click();
    expect(panel.classList.contains("is-open")).toBe(true);

    // Click again → toggles back. Confirms A19-R path is fully
    // intact and the diagnostic listener hasn't stolen events.
    toggleBtn.click();
    expect(panel.classList.contains("is-open")).toBe(false);
  });

  test("plain clicks on non-trigger elements are no-ops", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>x</p>");
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `<div id="plain">click me</div>`;
    const plain = document.getElementById("plain") as HTMLDivElement;
    await loadEnhance();
    plain.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).not.toHaveBeenCalled();
  });
});
