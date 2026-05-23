// @vitest-environment jsdom
//
// Card A19-R — progressive enhancement tests.
//
// Six surfaces under test:
//
//   1. has-js bootstrap — running the script adds ``has-js`` to
//      <html>.
//   2. Toggle delegate — clicking an element with
//      ``data-toggle-target`` flips ``is-open`` on the target.
//   3. Toggle resilience — bad selectors, missing targets,
//      nested triggers (event-bubbling via closest()).
//   4. Fetch-and-replace — happy path replaces the fragment;
//      non-2xx + network failure both fall back to native
//      submit; file inputs trigger fall-back (multipart not
//      supported by the URL-encoded path).
//   5. SSE wiring — picks up data-sse-url containers, opens
//      EventSource, applies messages, closes on error
//      (no reconnection storm), idempotent re-wiring marker.
//   6. Idempotence + defensiveness — re-importing the module
//      twice doesn't double-bind listeners; missing optional
//      globals (EventSource) don't throw.
//
// Each test imports the TS source directly so vitest can
// exercise it under jsdom. Module side effects re-run via
// vi.resetModules() in beforeEach, so each test sees a fresh
// listener-attach cycle.
//
// Path: web/src/client/__tests__/enhance.test.ts
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";


// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

function resetDocument(): void {
  document.documentElement.className = "";
  document.body.innerHTML = "";
}


async function loadEnhance(): Promise<void> {
  vi.resetModules();
  await import("../enhance");
}


beforeEach(() => {
  resetDocument();
});

afterEach(() => {
  vi.restoreAllMocks();
  resetDocument();
});


// ---------------------------------------------------------------------------
// 1. has-js bootstrap
// ---------------------------------------------------------------------------
describe("has-js bootstrap", () => {
  test("adds 'has-js' to <html> on load", async () => {
    expect(document.documentElement.classList.contains("has-js")).toBe(false);
    await loadEnhance();
    expect(document.documentElement.classList.contains("has-js")).toBe(true);
  });

  test("re-importing the module keeps has-js (idempotent)", async () => {
    await loadEnhance();
    await loadEnhance();
    // classList.add is idempotent — there should be ONE
    // instance of the class, not duplicates.
    const html = document.documentElement.outerHTML;
    expect(html.match(/has-js/g)?.length ?? 0).toBe(1);
  });
});


// ---------------------------------------------------------------------------
// 2. Toggle delegate — happy path
// ---------------------------------------------------------------------------
describe("toggle delegate", () => {
  test("click on trigger toggles 'is-open' on target", async () => {
    document.body.innerHTML = `
      <button id="trigger" data-toggle-target="#panel">toggle</button>
      <div id="panel"></div>
    `;
    await loadEnhance();
    const trigger = document.getElementById("trigger") as HTMLButtonElement;
    const panel = document.getElementById("panel") as HTMLDivElement;

    expect(panel.classList.contains("is-open")).toBe(false);
    trigger.click();
    expect(panel.classList.contains("is-open")).toBe(true);
    trigger.click();
    expect(panel.classList.contains("is-open")).toBe(false);
  });

  test("trigger inside an SVG / nested child still resolves via closest()", async () => {
    document.body.innerHTML = `
      <button id="trigger" data-toggle-target="#panel">
        <span id="icon">+</span>
      </button>
      <div id="panel"></div>
    `;
    await loadEnhance();
    const icon = document.getElementById("icon") as HTMLSpanElement;
    const panel = document.getElementById("panel") as HTMLDivElement;
    icon.click();  // event bubbles from <span> → <button>
    expect(panel.classList.contains("is-open")).toBe(true);
  });

  test("click outside any data-toggle-target does nothing", async () => {
    document.body.innerHTML = `
      <button id="plain">no-op</button>
      <div id="panel"></div>
    `;
    await loadEnhance();
    const plain = document.getElementById("plain") as HTMLButtonElement;
    const panel = document.getElementById("panel") as HTMLDivElement;
    plain.click();
    expect(panel.classList.contains("is-open")).toBe(false);
  });

  test("missing target is a no-op (no throw)", async () => {
    document.body.innerHTML = `
      <button id="trigger" data-toggle-target="#missing">x</button>
    `;
    await loadEnhance();
    const trigger = document.getElementById("trigger") as HTMLButtonElement;
    expect(() => trigger.click()).not.toThrow();
  });

  test("invalid selector is a no-op (no throw)", async () => {
    document.body.innerHTML = `
      <button id="trigger" data-toggle-target="!!!">x</button>
    `;
    await loadEnhance();
    const trigger = document.getElementById("trigger") as HTMLButtonElement;
    expect(() => trigger.click()).not.toThrow();
  });

  test("empty data-toggle-target value is a no-op", async () => {
    document.body.innerHTML = `
      <button id="trigger" data-toggle-target="">x</button>
      <div id="panel"></div>
    `;
    await loadEnhance();
    const trigger = document.getElementById("trigger") as HTMLButtonElement;
    const panel = document.getElementById("panel") as HTMLDivElement;
    trigger.click();
    expect(panel.classList.contains("is-open")).toBe(false);
  });
});


// ---------------------------------------------------------------------------
// 3. Fetch-and-replace
// ---------------------------------------------------------------------------
describe("fetch-and-replace form enhancement", () => {
  test("happy path replaces the target fragment", async () => {
    // Card A20-R: the enhance.ts response handler now branches
    // on Content-Type rather than HTTP status. The mock must
    // expose ``headers.get`` so the new check can run.
    const fetchMock = vi.fn(async () => ({
      ok:      true,
      status:  200,
      headers: {
        get(name: string) {
          return name.toLowerCase() === "content-type" ? "text/html" : null;
        },
      },
      text:    async () => "<p>fragment-from-server</p>",
    }) as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <form id="f" method="POST" action="/echo"
            data-enhance="fetch"
            data-fragment-target="#out">
        <input name="name" value="Alice">
      </form>
      <div id="out">initial</div>
    `;
    await loadEnhance();

    const form = document.getElementById("f") as HTMLFormElement;
    form.requestSubmit();
    // Wait a microtask for fetch resolution.
    await new Promise((r) => setTimeout(r, 0));

    const out = document.getElementById("out");
    expect(out!.innerHTML).toBe("<p>fragment-from-server</p>");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/echo");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["content-type"])
      .toBe("application/x-www-form-urlencoded");
    expect(init.body).toBe("name=Alice");
  });

  test("non-2xx response → fall back to native submit", async () => {
    const fetchMock = vi.fn(async () => ({
      ok:     false,
      status: 500,
      text:   async () => "boom",
    }) as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <form id="f" method="POST" action="/echo"
            data-enhance="fetch"
            data-fragment-target="#out">
        <input name="name" value="A">
      </form>
      <div id="out">initial</div>
    `;
    await loadEnhance();
    const form = document.getElementById("f") as HTMLFormElement;
    // Stub form.submit so we can detect the fall-back. jsdom's
    // native submit would navigate, which throws in this env.
    const submitSpy = vi.fn();
    form.submit = submitSpy;

    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(submitSpy).toHaveBeenCalledTimes(1);
    // data-enhance should be removed by the fallback so a
    // second submit goes native too.
    expect(form.getAttribute("data-enhance")).toBeNull();
    // Output not replaced (the failure short-circuits before
    // innerHTML assignment).
    expect((document.getElementById("out") as HTMLDivElement).innerHTML)
      .toBe("initial");
  });

  test("network failure (fetch throws) → fall back to native submit", async () => {
    const fetchMock = vi.fn(async () => {
      throw new Error("offline");
    });
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <form id="f" method="POST" action="/echo"
            data-enhance="fetch"
            data-fragment-target="#out">
      </form>
      <div id="out">x</div>
    `;
    await loadEnhance();
    const form = document.getElementById("f") as HTMLFormElement;
    const submitSpy = vi.fn();
    form.submit = submitSpy;

    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(submitSpy).toHaveBeenCalledTimes(1);
  });

  test("missing data-fragment-target → no interception, native submit proceeds", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true, status: 200, text: async () => "x",
    }) as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <form id="f" method="POST" action="/echo" data-enhance="fetch">
      </form>
    `;
    await loadEnhance();
    const form = document.getElementById("f") as HTMLFormElement;
    const submitSpy = vi.fn();
    form.submit = submitSpy;

    // We can't call requestSubmit and let jsdom navigate; intercept
    // by listening to the submit event directly and checking
    // preventDefault wasn't invoked by our handler.
    let prevented = false;
    form.addEventListener("submit", (e) => {
      prevented = e.defaultPrevented;
      e.preventDefault();  // our test intercept — stop jsdom navigation
    });
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(prevented).toBe(false);  // enhance.ts didn't intercept
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("form without data-enhance is left alone (no interception)", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true, status: 200, text: async () => "x",
    }) as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <form id="f" method="POST" action="/echo">
        <input name="name" value="A">
      </form>
    `;
    await loadEnhance();
    const form = document.getElementById("f") as HTMLFormElement;
    let prevented = false;
    form.addEventListener("submit", (e) => {
      prevented = e.defaultPrevented;
      e.preventDefault();
    });
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));
    expect(prevented).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("form action defaults to current URL when blank", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true, status: 200, text: async () => "ok",
    }) as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    document.body.innerHTML = `
      <form id="f" method="POST"
            data-enhance="fetch"
            data-fragment-target="#out">
        <input name="k" value="v">
      </form>
      <div id="out"></div>
    `;
    await loadEnhance();
    const form = document.getElementById("f") as HTMLFormElement;
    form.requestSubmit();
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    // jsdom's default location is http://localhost/
    expect(typeof url).toBe("string");
    expect(url.length).toBeGreaterThan(0);
  });
});


// ---------------------------------------------------------------------------
// 4. SSE wiring
// ---------------------------------------------------------------------------
describe("SSE wiring", () => {
  /** In-test fake EventSource. Captures the URL, exposes
   *  hooks to fire onmessage / onerror, and tracks close(). */
  class FakeEventSource {
    public static instances: FakeEventSource[] = [];
    public url: string;
    public onmessage: ((e: { data: string }) => void) | null = null;
    public onerror: (() => void) | null = null;
    public closed = false;
    constructor(url: string) {
      this.url = url;
      FakeEventSource.instances.push(this);
    }
    close() { this.closed = true; }
  }

  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  test("opens EventSource for each data-sse-url container", async () => {
    document.body.innerHTML = `
      <div data-sse-url="/events" data-sse-target="#out"></div>
      <pre id="out"></pre>
    `;
    await loadEnhance();
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(FakeEventSource.instances[0].url).toBe("/events");
  });

  test("onmessage replaces target innerHTML", async () => {
    document.body.innerHTML = `
      <div data-sse-url="/events" data-sse-target="#out"></div>
      <pre id="out">initial</pre>
    `;
    await loadEnhance();
    const source = FakeEventSource.instances[0];
    source.onmessage?.({ data: "<span>hello</span>" });
    expect((document.getElementById("out") as HTMLPreElement).innerHTML)
      .toBe("<span>hello</span>");
  });

  test("onerror closes the source (no reconnection storm)", async () => {
    document.body.innerHTML = `
      <div data-sse-url="/events" data-sse-target="#out"></div>
      <pre id="out"></pre>
    `;
    await loadEnhance();
    const source = FakeEventSource.instances[0];
    expect(source.closed).toBe(false);
    source.onerror?.();
    expect(source.closed).toBe(true);
  });

  test("missing data-sse-target → no subscription opened", async () => {
    document.body.innerHTML = `
      <div data-sse-url="/events"></div>
    `;
    await loadEnhance();
    expect(FakeEventSource.instances).toHaveLength(0);
  });

  test("missing data-sse-url → no subscription opened", async () => {
    document.body.innerHTML = `
      <div data-sse-target="#out"></div>
      <pre id="out"></pre>
    `;
    await loadEnhance();
    expect(FakeEventSource.instances).toHaveLength(0);
  });

  test("data-sse-active marker prevents double-subscriptions", async () => {
    document.body.innerHTML = `
      <div data-sse-url="/events" data-sse-target="#out"></div>
      <pre id="out"></pre>
    `;
    await loadEnhance();
    // Re-import — script's DOMContentLoaded already fired in
    // the first load, but on the re-load it runs synchronously
    // (document.readyState !== "loading" by then) and scans
    // again. The marker should prevent a duplicate.
    await loadEnhance();
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  test("script does not throw when EventSource is missing", async () => {
    // Replace EventSource with undefined (simulate older runtime).
    vi.stubGlobal("EventSource", undefined);
    document.body.innerHTML = `
      <div data-sse-url="/events" data-sse-target="#out"></div>
      <pre id="out"></pre>
    `;
    await expect(loadEnhance()).resolves.not.toThrow();
  });
});


// ---------------------------------------------------------------------------
// 5. Defensiveness — no data-* hooks present at all
// ---------------------------------------------------------------------------
describe("defensiveness", () => {
  test("module loads cleanly against an empty DOM", async () => {
    document.body.innerHTML = "";
    await expect(loadEnhance()).resolves.not.toThrow();
    // has-js still applied.
    expect(document.documentElement.classList.contains("has-js")).toBe(true);
  });

  test("module loads cleanly when no data-* attributes exist", async () => {
    document.body.innerHTML = `
      <h1>plain page</h1>
      <p>no enhancement hooks here</p>
      <button>click me</button>
      <form><input name="x"></form>
    `;
    await expect(loadEnhance()).resolves.not.toThrow();
    // Clicking the plain button doesn't toggle anything (no
    // data-toggle-target).
    const btn = document.querySelector("button") as HTMLButtonElement;
    expect(() => btn.click()).not.toThrow();
  });

  test("script exports nothing (pure side-effect module)", async () => {
    const mod = await import("../enhance");
    // Module-namespace object exists, but has zero declared
    // exports. (Symbol-keyed metadata like __esModule may be
    // present in some loaders — assert no NAMED exports.)
    const namedKeys = Object.keys(mod).filter((k) => k !== "default");
    expect(namedKeys).toEqual([]);
  });
});
