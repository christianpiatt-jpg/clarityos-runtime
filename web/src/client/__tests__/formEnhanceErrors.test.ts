// @vitest-environment jsdom
//
// Card A20-R — client-side fetch-and-replace tests for HTML
// error fragments.
//
// Re-tests the A19-R fetch-and-replace flow under the new
// content-type-based response handling:
//
//   * Previously (A19-R): non-2xx → fall back to native submit.
//   * Now (A20-R): HTML response (any status) → replace
//                  target; non-HTML → fall back.
//
// This lets a 4xx-with-HTML-error-fragment (e.g., the
// server-side ``renderFormErrors`` output) render inline instead
// of forcing a full-page reload.
//
// Five behaviours under test:
//
//   1. 422 + text/html error fragment → target replaced (the
//      load-bearing A20-R change).
//   2. 400 + text/html error fragment → target replaced.
//   3. 500 + text/html error fragment → target replaced
//      (content-type wins over status; if the server can speak
//      HTML, the client trusts the HTML).
//   4. 422 + application/json → fall back to native submit.
//   5. 500 + text/plain → fall back to native submit.
//   6. 2xx + HTML preserved (A19-R behaviour regression check).
//   7. Network failure → fall back (A19-R behaviour preserved).
//   8. content-type with charset suffix (``text/html; charset=utf-8``)
//      still detected as HTML.
//
// Path: web/src/client/__tests__/formEnhanceErrors.test.ts
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
  contentType: string,
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


function setupForm(): {
  form: HTMLFormElement;
  out: HTMLDivElement;
  submitSpy: ReturnType<typeof vi.fn>;
} {
  document.body.innerHTML = `
    <form id="f" method="POST" action="/echo"
          data-enhance="fetch"
          data-fragment-target="#out">
      <input name="name" value="Alice">
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
// 1-3. HTML response (any status) → replace target
// ---------------------------------------------------------------------------
describe("HTML response (any status) → replace target", () => {
  test("422 + text/html error fragment → target replaced", async () => {
    const fetchMock = makeFetchMock(
      422,
      "text/html",
      '<ul class="form-errors"><li data-field="name">Required.</li></ul>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { form, out, submitSpy } = setupForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toContain('class="form-errors"');
    expect(out.innerHTML).toContain('data-field="name"');
    expect(out.innerHTML).toContain('Required.');
    expect(submitSpy).not.toHaveBeenCalled();
  });

  test("400 + text/html error fragment → target replaced", async () => {
    const fetchMock = makeFetchMock(
      400,
      "text/html",
      '<p>bad input</p>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { form, out, submitSpy } = setupForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toBe('<p>bad input</p>');
    expect(submitSpy).not.toHaveBeenCalled();
  });

  test("500 + text/html still replaces (content-type wins over status)", async () => {
    // The server-can-speak-HTML signal is what the client
    // trusts. A 500 with an HTML body is presumed to be the
    // surface's structured error page, NOT a transport
    // failure — render it inline.
    const fetchMock = makeFetchMock(
      500,
      "text/html",
      '<h1>Internal Error</h1>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { form, out, submitSpy } = setupForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toBe('<h1>Internal Error</h1>');
    expect(submitSpy).not.toHaveBeenCalled();
  });
});


// ---------------------------------------------------------------------------
// 4-5. Non-HTML response → fall back to native submit
// ---------------------------------------------------------------------------
describe("non-HTML response → fall back to native submit", () => {
  test("422 + application/json → fall back", async () => {
    const fetchMock = makeFetchMock(
      422,
      "application/json",
      '{"errors":{"name":"Required"}}',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { form, out, submitSpy } = setupForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(submitSpy).toHaveBeenCalledTimes(1);
    // Output not replaced.
    expect(out.innerHTML).toBe("initial");
    // data-enhance stripped so the next submit goes native too.
    expect(form.getAttribute("data-enhance")).toBeNull();
  });

  test("500 + text/plain → fall back", async () => {
    const fetchMock = makeFetchMock(500, "text/plain", "boom");
    vi.stubGlobal("fetch", fetchMock);

    const { form, out, submitSpy } = setupForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(submitSpy).toHaveBeenCalledTimes(1);
    expect(out.innerHTML).toBe("initial");
  });

  test("200 + application/json → fall back (rare but covered)", async () => {
    const fetchMock = makeFetchMock(
      200,
      "application/json",
      '{"view":"form_demo","params":{}}',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { form, out, submitSpy } = setupForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(submitSpy).toHaveBeenCalledTimes(1);
    expect(out.innerHTML).toBe("initial");
  });

  test("response without content-type header → fall back", async () => {
    const fetchMock = vi.fn(async () => ({
      ok:      true,
      status:  200,
      headers: { get: (_n: string) => null },
      text:    async () => "<p>html-but-no-ct</p>",
    }) as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    const { form, out, submitSpy } = setupForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(submitSpy).toHaveBeenCalledTimes(1);
    expect(out.innerHTML).toBe("initial");
  });
});


// ---------------------------------------------------------------------------
// 6. A19-R 2xx happy path preserved
// ---------------------------------------------------------------------------
describe("A19-R 2xx happy path preserved", () => {
  test("200 + text/html replaces target (no regression)", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<p>fragment</p>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { form, out, submitSpy } = setupForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toBe('<p>fragment</p>');
    expect(submitSpy).not.toHaveBeenCalled();
  });
});


// ---------------------------------------------------------------------------
// 7. Network failure preserved
// ---------------------------------------------------------------------------
describe("network failure preserved", () => {
  test("fetch throws → fall back to native submit (A19-R preserved)", async () => {
    const fetchMock = vi.fn(async () => {
      throw new Error("offline");
    });
    vi.stubGlobal("fetch", fetchMock);

    const { form, submitSpy } = setupForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(submitSpy).toHaveBeenCalledTimes(1);
  });
});


// ---------------------------------------------------------------------------
// 8. Charset-suffix content-type still detected as HTML
// ---------------------------------------------------------------------------
describe("content-type charset suffix", () => {
  test("'text/html; charset=utf-8' detected as HTML → replace", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html; charset=utf-8",
      '<p>ok</p>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { form, out, submitSpy } = setupForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toBe('<p>ok</p>');
    expect(submitSpy).not.toHaveBeenCalled();
  });

  test("uppercase 'TEXT/HTML' still detected (case-insensitive)", async () => {
    const fetchMock = makeFetchMock(
      200,
      "TEXT/HTML; CHARSET=UTF-8",
      '<p>ok</p>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { form, out, submitSpy } = setupForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toBe('<p>ok</p>');
    expect(submitSpy).not.toHaveBeenCalled();
  });
});
