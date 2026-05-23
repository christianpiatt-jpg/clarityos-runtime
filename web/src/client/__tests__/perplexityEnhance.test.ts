// @vitest-environment jsdom
//
// Card A30-R — client-side Perplexity relay tests.
//
// Seven behaviours under test:
//
//   1. Click on data-perplexity-query element POSTs to
//      /__perplexity with the data-query value.
//   2. Form submit on a form carrying data-perplexity-query
//      pulls the query from the name="query" field.
//   3. Click handler skips form elements (the submit handler
//      owns them — no double-fire).
//   4. HTML response → target replaced.
//   5. Non-HTML response / network failure:
//      * Click branch → silent no-op.
//      * Form branch → strip marker + native submit.
//   6. Defensive paths: missing target attr / element / bad
//      selector / missing data-query (click) / missing query
//      field (submit) → no fetch.
//   7. Idempotent listener binding (re-import does not
//      double-fire).
//   8. Non-interference: A23-R data-enhance="status" still
//      works alongside data-perplexity-query.
//
// Path: web/src/client/__tests__/perplexityEnhance.test.ts
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


function setupClickTrigger(opts: { query?: string } = {}): {
  trigger: HTMLButtonElement;
  out:     HTMLDivElement;
} {
  const queryAttr = opts.query !== undefined
    ? ` data-query="${opts.query}"`
    : "";
  document.body.innerHTML = `
    <button id="t"
            data-perplexity-query
            data-perplexity-target="#out"${queryAttr}>ask</button>
    <div id="out">initial</div>
  `;
  return {
    trigger: document.getElementById("t") as HTMLButtonElement,
    out:     document.getElementById("out") as HTMLDivElement,
  };
}


function setupSubmitForm(opts: { query?: string } = {}): {
  form: HTMLFormElement;
  out:  HTMLDivElement;
  submitSpy: ReturnType<typeof vi.fn>;
} {
  document.body.innerHTML = `
    <form id="f" method="POST" action="/somewhere"
          data-perplexity-query
          data-perplexity-target="#out">
      <input name="query" value="${opts.query ?? ""}">
    </form>
    <div id="out">initial</div>
  `;
  const form = document.getElementById("f") as HTMLFormElement;
  const out = document.getElementById("out") as HTMLDivElement;
  const submitSpy = vi.fn();
  form.submit = submitSpy;
  return { form, out, submitSpy };
}


beforeEach(() => {
  resetDocument();
});

afterEach(() => {
  vi.restoreAllMocks();
  resetDocument();
});


// ---------------------------------------------------------------------------
// 1. Click branch — POST /__perplexity
// ---------------------------------------------------------------------------
describe("click branch → POST /__perplexity", () => {
  test("click POSTs to /__perplexity with the data-query value", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-perplexity-answer><pre data-answer>ok</pre></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { trigger } = setupClickTrigger({ query: "weather" });
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const call = fetchMock.mock.calls[0];
    expect(call[0]).toBe("/__perplexity");
    const init = call[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(
      (init.headers as Record<string, string>)["content-type"],
    ).toBe("application/json");
    expect(JSON.parse(init.body as string)).toEqual({ query: "weather" });
  });

  test("HTML response → target replaced", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-perplexity-answer><pre data-answer>It is sunny.</pre></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { trigger, out } = setupClickTrigger({ query: "weather" });
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toContain("data-perplexity-answer");
    expect(out.innerHTML).toContain("It is sunny.");
  });

  test("missing data-query → no fetch (no sensible default)", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>x</p>");
    vi.stubGlobal("fetch", fetchMock);

    const { trigger } = setupClickTrigger();  // no query
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("empty data-query → no fetch", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>x</p>");
    vi.stubGlobal("fetch", fetchMock);

    const { trigger } = setupClickTrigger({ query: "" });
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).not.toHaveBeenCalled();
  });
});


// ---------------------------------------------------------------------------
// 2. Form submit branch
// ---------------------------------------------------------------------------
describe("submit branch → POST /__perplexity from form", () => {
  test("submit POSTs with name=\"query\" field value", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-perplexity-answer><pre data-answer>ok</pre></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { form } = setupSubmitForm({ query: "from form" });
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(init.body as string)).toEqual({
      query: "from form",
    });
  });

  test("HTML response → target replaced", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-perplexity-answer><pre data-answer>answer</pre></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { form, out } = setupSubmitForm({ query: "x" });
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toContain("answer");
  });

  test("missing name=\"query\" field → fall through to native (no preventDefault)", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>x</p>");
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <form id="f" method="POST" action="/somewhere"
            data-perplexity-query
            data-perplexity-target="#out">
        <input name="other" value="x">
      </form>
      <div id="out">initial</div>
    `;
    const form = document.getElementById("f") as HTMLFormElement;
    const submitSpy = vi.fn();
    form.submit = submitSpy;
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    // No fetch (no query field) AND no preventDefault'd
    // intercept, so the native submit fires.
    expect(fetchMock).not.toHaveBeenCalled();
  });
});


// ---------------------------------------------------------------------------
// 3. Click handler skips forms
// ---------------------------------------------------------------------------
describe("click handler skips form elements (no double-fire)", () => {
  test("clicking a form-typed trigger does NOT fire a duplicate click POST", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-perplexity-answer></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { form } = setupSubmitForm({ query: "x" });
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    // ONE fetch (from the submit handler), not two.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});


// ---------------------------------------------------------------------------
// 4. Non-HTML response → branch-appropriate fallback
// ---------------------------------------------------------------------------
describe("non-HTML response → branch-appropriate fallback", () => {
  test("click branch + JSON response → target unchanged (silent no-op)", async () => {
    const fetchMock = makeFetchMock(200, "application/json", '{"ok":1}');
    vi.stubGlobal("fetch", fetchMock);

    const { trigger, out } = setupClickTrigger({ query: "x" });
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toBe("initial");
  });

  test("form branch + JSON response → native submit + marker stripped", async () => {
    const fetchMock = makeFetchMock(200, "application/json", '{"ok":1}');
    vi.stubGlobal("fetch", fetchMock);

    const { form, out, submitSpy } = setupSubmitForm({ query: "x" });
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(submitSpy).toHaveBeenCalledTimes(1);
    expect(out.innerHTML).toBe("initial");
    expect(form.hasAttribute("data-perplexity-query")).toBe(false);
  });

  test("click branch + network failure → silent no-op", async () => {
    const fetchMock = vi.fn(async () => {
      throw new Error("offline");
    });
    vi.stubGlobal("fetch", fetchMock);

    const { trigger, out } = setupClickTrigger({ query: "x" });
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toBe("initial");
  });

  test("form branch + network failure → native submit", async () => {
    const fetchMock = vi.fn(async () => {
      throw new Error("offline");
    });
    vi.stubGlobal("fetch", fetchMock);

    const { form, submitSpy } = setupSubmitForm({ query: "x" });
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(submitSpy).toHaveBeenCalledTimes(1);
  });
});


// ---------------------------------------------------------------------------
// 5. Defensive paths
// ---------------------------------------------------------------------------
describe("defensive paths", () => {
  test("click trigger without data-perplexity-target → no fetch", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>x</p>");
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <button id="t" data-perplexity-query data-query="x">ask</button>
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
              data-perplexity-query
              data-perplexity-target="#nope"
              data-query="x">ask</button>
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
              data-perplexity-query
              data-perplexity-target="###bad###"
              data-query="x">ask</button>
    `;
    const trigger = document.getElementById("t") as HTMLButtonElement;
    await loadEnhance();
    expect(() => trigger.click()).not.toThrow();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("nested click inside the trigger still fires", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-perplexity-answer></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <button id="t"
              data-perplexity-query
              data-perplexity-target="#out"
              data-query="weather">
        <span id="inner">ask</span>
      </button>
      <div id="out">initial</div>
    `;
    const inner = document.getElementById("inner") as HTMLSpanElement;
    await loadEnhance();
    inner.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});


// ---------------------------------------------------------------------------
// 6. Idempotent listener binding
// ---------------------------------------------------------------------------
describe("idempotent listener binding", () => {
  test("re-importing the module does NOT double-fire the click POST", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-perplexity-answer></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { trigger } = setupClickTrigger({ query: "x" });
    await loadEnhance();
    await loadEnhance();
    trigger.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});


// ---------------------------------------------------------------------------
// 7. Non-interference with prior cards
// ---------------------------------------------------------------------------
describe("non-interference with prior cards", () => {
  test("A23-R data-enhance='status' still POSTs to /__status", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-status-surface="success"></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <form id="f" data-enhance="status" data-status-target="#out">
        <input name="kind" value="success">
        <input name="message" value="OK">
      </form>
      <div id="out">initial</div>
    `;
    const form = document.getElementById("f") as HTMLFormElement;
    form.submit = vi.fn();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/__status");
  });

  test("A24-R data-loading-trigger still POSTs to /__loading", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-loading-surface></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <button id="b"
              data-loading-trigger
              data-loading-target="#out">load</button>
      <div id="out">initial</div>
    `;
    const btn = document.getElementById("b") as HTMLButtonElement;
    await loadEnhance();
    btn.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/__loading");
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
