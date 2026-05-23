// @vitest-environment jsdom
//
// Card A23-R — client-side status-submit tests.
//
// Six behaviours under test:
//
//   1. Form with data-enhance="status" submits → POST to
//      /__status with JSON body containing the form fields.
//   2. HTML response → replace data-status-target's innerHTML.
//   3. Non-HTML response → fall back to native submit.
//   4. Network failure → fall back to native submit.
//   5. Missing data-status-target → no fetch.
//   6. Bad CSS selector → silent no-op.
//   7. Idempotent listener binding (re-import does not double-
//      fire).
//   8. Non-interference: A19-R data-enhance="fetch" still
//      works alongside data-enhance="status".
//
// Path: web/src/client/__tests__/statusEnhance.test.ts
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


function setupStatusForm(): {
  form: HTMLFormElement;
  out: HTMLDivElement;
  submitSpy: ReturnType<typeof vi.fn>;
} {
  document.body.innerHTML = `
    <form id="f" method="POST" action="/some-action"
          data-enhance="status"
          data-status-target="#out">
      <input name="kind" value="success">
      <input name="message" value="It worked.">
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
// 1. POST /__status with JSON body
// ---------------------------------------------------------------------------
describe("submit → POST /__status with JSON body", () => {
  test("posts to /__status, not to form.action", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-status-surface="success"><h2>Success</h2></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { form } = setupStatusForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const call = fetchMock.mock.calls[0];
    expect(call[0]).toBe("/__status");
    const init = call[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(
      (init.headers as Record<string, string>)["content-type"],
    ).toBe("application/json");
  });

  test("serialises form fields as JSON {kind, message}", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-status-surface="success"></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { form } = setupStatusForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({
      kind: "success",
      message: "It worked.",
    });
  });
});


// ---------------------------------------------------------------------------
// 2. HTML response → replace target
// ---------------------------------------------------------------------------
describe("HTML response → replace target", () => {
  test("200 + text/html → target replaced", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-status-surface="success"><h2>Success</h2><p>OK</p></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { form, out, submitSpy } = setupStatusForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toContain('data-status-surface="success"');
    expect(out.innerHTML).toContain("<h2>Success</h2>");
    expect(submitSpy).not.toHaveBeenCalled();
  });

  test("400 + text/html (failure surface) → target replaced", async () => {
    // Content-type-based branching matches A20-R behaviour:
    // a 4xx with HTML body still swaps in, because the failure
    // surface IS the operator-facing payload.
    const fetchMock = makeFetchMock(
      400,
      "text/html",
      '<div data-status-surface="failure"><h2>Failure</h2></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { form, out, submitSpy } = setupStatusForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toContain('data-status-surface="failure"');
    expect(submitSpy).not.toHaveBeenCalled();
  });

  test("text/html; charset=utf-8 detected (charset suffix)", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html; charset=utf-8",
      '<div data-status-surface="success"></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { form, out } = setupStatusForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(out.innerHTML).toContain('data-status-surface="success"');
  });
});


// ---------------------------------------------------------------------------
// 3. Non-HTML response → fall back to native submit
// ---------------------------------------------------------------------------
describe("non-HTML response → fall back to native submit", () => {
  test("application/json → fallback", async () => {
    const fetchMock = makeFetchMock(
      200,
      "application/json",
      '{"kind":"success"}',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { form, out, submitSpy } = setupStatusForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(submitSpy).toHaveBeenCalledTimes(1);
    expect(out.innerHTML).toBe("initial");
    expect(form.getAttribute("data-enhance")).toBeNull();
  });

  test("text/plain → fallback", async () => {
    const fetchMock = makeFetchMock(500, "text/plain", "boom");
    vi.stubGlobal("fetch", fetchMock);

    const { form, out, submitSpy } = setupStatusForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(submitSpy).toHaveBeenCalledTimes(1);
    expect(out.innerHTML).toBe("initial");
  });

  test("missing content-type → fallback", async () => {
    const fetchMock = makeFetchMock(200, null, "<p>html?</p>");
    vi.stubGlobal("fetch", fetchMock);

    const { form, out, submitSpy } = setupStatusForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(submitSpy).toHaveBeenCalledTimes(1);
    expect(out.innerHTML).toBe("initial");
  });
});


// ---------------------------------------------------------------------------
// 4. Network failure → fallback
// ---------------------------------------------------------------------------
describe("network failure → fallback", () => {
  test("fetch throws → fall back to native submit", async () => {
    const fetchMock = vi.fn(async () => {
      throw new Error("offline");
    });
    vi.stubGlobal("fetch", fetchMock);

    const { form, submitSpy } = setupStatusForm();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(submitSpy).toHaveBeenCalledTimes(1);
  });
});


// ---------------------------------------------------------------------------
// 5-6. Defensive paths
// ---------------------------------------------------------------------------
describe("defensive paths", () => {
  test("form without data-status-target → no fetch", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>x</p>");
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <form id="f" data-enhance="status">
        <input name="kind" value="success">
        <input name="message" value="x">
      </form>
    `;
    const form = document.getElementById("f") as HTMLFormElement;
    const submitSpy = vi.fn();
    form.submit = submitSpy;
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).not.toHaveBeenCalled();
    // Without a target, A23-R hands control back — but there's
    // no explicit fallback path here (mirrors the A19-R
    // missing-target behaviour).
  });

  test("data-status-target pointing at missing element → no fetch", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>x</p>");
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <form id="f" data-enhance="status" data-status-target="#nope">
        <input name="kind" value="success">
        <input name="message" value="x">
      </form>
    `;
    const form = document.getElementById("f") as HTMLFormElement;
    form.submit = vi.fn();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("bad CSS selector → silent no-op (no throw)", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>x</p>");
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <form id="f" data-enhance="status" data-status-target="###bad###">
        <input name="kind" value="success">
        <input name="message" value="x">
      </form>
    `;
    const form = document.getElementById("f") as HTMLFormElement;
    form.submit = vi.fn();
    await loadEnhance();
    expect(() => form.requestSubmit()).not.toThrow();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("non-string FormData entry → fall back to native submit", async () => {
    // jsdom doesn't ship ``DataTransfer``, so we can't
    // synthesize a real File-bearing FormData. Instead, stub
    // ``FormData`` with a class whose ``entries()`` iterator
    // yields a Blob (non-string) value — this exercises the
    // same ``typeof value !== "string"`` guard the file-input
    // path would hit in a real browser.
    const fetchMock = makeFetchMock(200, "text/html", "<p>x</p>");
    vi.stubGlobal("fetch", fetchMock);

    const originalFormData = (globalThis as Record<string, unknown>).FormData;
    try {
      class StubFormData {
        *entries(): IterableIterator<[string, string | Blob]> {
          yield ["kind",   "success"];
          yield ["upload", new Blob(["x"])];
        }
      }
      (globalThis as Record<string, unknown>).FormData = StubFormData;

      document.body.innerHTML = `
        <form id="f" data-enhance="status" data-status-target="#out">
          <input name="kind" value="success">
        </form>
        <div id="out">initial</div>
      `;
      const form = document.getElementById("f") as HTMLFormElement;
      const submitSpy = vi.fn();
      form.submit = submitSpy;
      await loadEnhance();
      form.requestSubmit();
      await new Promise((r) => setTimeout(r, 0));

      expect(submitSpy).toHaveBeenCalledTimes(1);
      expect(fetchMock).not.toHaveBeenCalled();
    } finally {
      (globalThis as Record<string, unknown>).FormData = originalFormData;
    }
  });
});


// ---------------------------------------------------------------------------
// 7. Idempotent listener binding
// ---------------------------------------------------------------------------
describe("idempotent listener binding", () => {
  test("re-importing the module does NOT double-fire the fetch", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-status-surface="success"></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    const { form } = setupStatusForm();
    await loadEnhance();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});


// ---------------------------------------------------------------------------
// 8. Non-interference with A19-R/A20-R/A21-R/A22-R
// ---------------------------------------------------------------------------
describe("non-interference with prior cards", () => {
  test("data-enhance='fetch' (A19-R) still uses form-urlencoded POST", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<p>fetch-replied</p>',
    );
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <form id="f" method="POST" action="/echo"
            data-enhance="fetch"
            data-fragment-target="#out">
        <input name="x" value="y">
      </form>
      <div id="out">initial</div>
    `;
    const form = document.getElementById("f") as HTMLFormElement;
    const out = document.getElementById("out") as HTMLDivElement;
    form.submit = vi.fn();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(
      (init.headers as Record<string, string>)["content-type"],
    ).toBe("application/x-www-form-urlencoded");
    expect(init.body).toContain("x=y");
    expect(out.innerHTML).toBe("<p>fetch-replied</p>");
  });

  test("forms without any data-enhance are not intercepted", async () => {
    const fetchMock = makeFetchMock(200, "text/html", "<p>x</p>");
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <form id="f" method="POST" action="/echo">
        <input name="x" value="y">
      </form>
    `;
    const form = document.getElementById("f") as HTMLFormElement;
    form.submit = vi.fn();
    await loadEnhance();
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("A21-R data-diagnostic-toggle path unaffected by status branch", async () => {
    const fetchMock = makeFetchMock(
      200,
      "text/html",
      '<div data-diagnostic-fragment></div>',
    );
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <button id="b"
              data-diagnostic-toggle
              data-diagnostic-target="#out">d</button>
      <div id="out">initial</div>
    `;
    const btn = document.getElementById("b") as HTMLButtonElement;
    const out = document.getElementById("out") as HTMLDivElement;
    await loadEnhance();
    btn.click();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const call = fetchMock.mock.calls[0];
    expect(call[0]).toBe("/__diagnostics");
    expect(out.innerHTML).toContain('data-diagnostic-fragment');
  });
});
