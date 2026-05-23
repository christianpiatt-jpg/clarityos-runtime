// @vitest-environment jsdom
//
// Card A24-R — client-side loading-trigger tests.
//
// Eight behaviours under test:
//
//   1. Click on data-loading-trigger POSTs to /__loading with
//      a JSON body and replaces the target fragment.
//   2. data-loading-message attribute is forwarded in the JSON
//      body as {message: <attr>}.
//   3. Missing data-loading-message → empty {} body.
//   4. Empty data-loading-message → empty {} body.
//   5. Non-HTML response → silent no-op (no native fallback).
//   6. Network failure → silent no-op.
//   7. Missing target attr / element / bad selector → no fetch.
//   8. Idempotent listener binding (re-import does not double-
//      fire).
//   9. Non-interference: A19-R/A21-R/A22-R/A23-R paths still
//      work.
//
// Path: web/src/client/__tests__/loadingEnhance.test.ts
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


function setupTrigger(opts: { message?: string } = {}): {
  trigger: HTMLButtonElement;
  out: HTMLDivElement;
} {
  const attr = opts.message !== undefined
    ? ` data-loading-message="${opts.message}"`
    : "";
  document.body.innerHTML = `
    <button id="t"
            data-loading-trigger
            data-loading-target="#out"${attr}>load</button>
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
// 1. Click → POST /__loading
// ---------------------------------------------------------------------------
describe("click → POST /__loading", () => {
  test("posts to /__loading with content-type application/json", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div class="loading-surface" data-loading-surface></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { trigger } = setupTrigger();
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const call = fetchMock.mock.calls[0];
    expect(call[0]).toBe("/__loading");
    const init = call[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(
      (init.headers as Record<string, string>)["content-type"],
    ).toBe("application/json");
  });

  test("HTML response → target replaced", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div class="loading-surface" data-loading-surface>' +
      '<div class="spinner"></div>' +
      '<p data-loading-message>Working…</p></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { trigger, out } = setupTrigger({ message: "Working…" });
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toContain("data-loading-surface");
    expect(out.innerHTML).toContain('<div class="spinner"></div>');
    expect(out.innerHTML).toContain("Working…");
  });

  test("nested element inside trigger fires the handler", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-loading-surface></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <button id="t"
              data-loading-trigger
              data-loading-target="#out">
        <span id="inner">load</span>
      </button>
      <div id="out">initial</div>
    `;
    const inner = document.getElementById("inner") as HTMLSpanElement;
    const out   = document.getElementById("out")   as HTMLDivElement;
    await loadEnhance();
    inner.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toContain("data-loading-surface");
  });
});


// ---------------------------------------------------------------------------
// 2-4. data-loading-message attribute handling
// ---------------------------------------------------------------------------
describe("data-loading-message attribute", () => {
  test("present + non-empty → forwarded in JSON body", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-loading-surface></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { trigger } = setupTrigger({ message: "Working hard" });
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({ message: "Working hard" });
  });

  test("missing attribute → empty {} body", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-loading-surface></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { trigger } = setupTrigger();  // no message
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.body).toBe("{}");
  });

  test("empty attribute → empty {} body", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-loading-surface></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { trigger } = setupTrigger({ message: "" });
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.body).toBe("{}");
  });
});


// ---------------------------------------------------------------------------
// 5. Non-HTML response → silent no-op
// ---------------------------------------------------------------------------
describe("non-HTML response → silent no-op", () => {
  test("application/json → target unchanged", async () => {
    const fetchMock = makeFetchMock(
      200,
      "application/json",
      '{"foo":"bar"}',
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
    const fetchMock = makeFetchMock(200, "text/plain", "boom");
    vi.stubGlobal("fetch", fetchMock);

    const { trigger, out } = setupTrigger();
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toBe("initial");
  });

  test("missing content-type → target unchanged", async () => {
    const fetchMock = makeFetchMock(200, null, "<p>html?</p>");
    vi.stubGlobal("fetch", fetchMock);

    const { trigger, out } = setupTrigger();
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toBe("initial");
  });
});


// ---------------------------------------------------------------------------
// 6. Network failure → silent no-op
// ---------------------------------------------------------------------------
describe("network failure → silent no-op", () => {
  test("fetch throws → no innerHTML change", async () => {
    const fetchMock = vi.fn(async () => {
      throw new Error("offline");
    });
    vi.stubGlobal("fetch", fetchMock);

    const { trigger, out } = setupTrigger();
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toBe("initial");
  });
});


// ---------------------------------------------------------------------------
// 7. Defensive paths
// ---------------------------------------------------------------------------
describe("defensive paths", () => {
  test("trigger without data-loading-target → no fetch", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>x</p>");
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <button id="t" data-loading-trigger>load</button>
    `;
    const trigger = document.getElementById("t") as HTMLButtonElement;
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("trigger pointing at missing element → no fetch", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>x</p>");
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <button id="t"
              data-loading-trigger
              data-loading-target="#nope">load</button>
    `;
    const trigger = document.getElementById("t") as HTMLButtonElement;
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("bad CSS selector → silent no-op (no throw, no fetch)", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>x</p>");
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <button id="t"
              data-loading-trigger
              data-loading-target="###bad###">load</button>
    `;
    const trigger = document.getElementById("t") as HTMLButtonElement;
    await loadEnhance();
    expect(() => trigger.click()).not.toThrow();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).not.toHaveBeenCalled();
  });
});


// ---------------------------------------------------------------------------
// 8. Idempotent listener binding
// ---------------------------------------------------------------------------
describe("idempotent listener binding", () => {
  test("re-importing the module does NOT double-fire the fetch", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-loading-surface></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { trigger } = setupTrigger();
    await loadEnhance();
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});


// ---------------------------------------------------------------------------
// 9. Non-interference with A19-R/A21-R/A22-R/A23-R
// ---------------------------------------------------------------------------
describe("non-interference with prior cards", () => {
  test("A19-R toggle still works alongside loading trigger", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>x</p>");
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <button id="load-btn"
              data-loading-trigger
              data-loading-target="#load-out">load</button>
      <div id="load-out">initial</div>

      <button id="toggle-btn" data-toggle-target="#panel">t</button>
      <div id="panel">p</div>
    `;
    await loadEnhance();
    const panel = document.getElementById("panel") as HTMLDivElement;
    const toggleBtn = document.getElementById("toggle-btn") as HTMLButtonElement;
    toggleBtn.click();
    expect(panel.classList.contains("is-open")).toBe(true);
    toggleBtn.click();
    expect(panel.classList.contains("is-open")).toBe(false);
  });

  test("A21-R diagnostic toggle still posts to /__diagnostics", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-diagnostic-fragment></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <button id="d"
              data-diagnostic-toggle
              data-diagnostic-target="#out">d</button>
      <div id="out">initial</div>
    `;
    const btn = document.getElementById("d") as HTMLButtonElement;
    await loadEnhance();
    btn.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/__diagnostics");
  });

  test("loading trigger does not match diagnostic-toggle elements", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>x</p>");
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <button id="d"
              data-diagnostic-toggle
              data-diagnostic-target="#out">d</button>
      <div id="out">initial</div>
    `;
    const btn = document.getElementById("d") as HTMLButtonElement;
    await loadEnhance();
    btn.click();
    await new Promise((r) => setTimeout(r, 0));

    // Only ONE fetch (to /__diagnostics), not two.
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/__diagnostics");
  });

  test("plain clicks on non-trigger elements remain no-ops", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>x</p>");
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `<div id="plain">click</div>`;
    const plain = document.getElementById("plain") as HTMLDivElement;
    await loadEnhance();
    plain.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).not.toHaveBeenCalled();
  });
});
