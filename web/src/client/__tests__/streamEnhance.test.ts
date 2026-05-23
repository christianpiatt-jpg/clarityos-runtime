// @vitest-environment jsdom
//
// Card A22-R — client-side streaming-task tests.
//
// Eight behaviours under test:
//
//   1. Click on data-stream-start opens an EventSource for
//      /__stream and registers log/status/done/error listeners.
//   2. "log" events append to <pre data-stream-log>.
//   3. "status" events replace <div data-stream-status>.
//   4. "done" closes the source + clears the active marker.
//   5. "error" closes the source + clears the active marker.
//   6. Per-trigger guard (data-stream-active) prevents a second
//      session from starting while one is running.
//   7. Idempotent listener binding: re-importing the module
//      does NOT register a second click handler.
//   8. Defensive paths: missing target attr / element / bad
//      selector → no EventSource opened.
//   9. Malformed JSON in event data → silent drop (no throw,
//      no DOM mutation).
//   10. Missing EventSource global → silent no-op (jsdom-style
//       environments).
//
// Path: web/src/client/__tests__/streamEnhance.test.ts
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";


// ---------------------------------------------------------------------------
// MockEventSource — captures opens, exposes per-event dispatch.
// ---------------------------------------------------------------------------

interface MockListener {
  (event: { data: string }): void;
}

class MockEventSource {
  url:        string;
  closed:     boolean = false;
  listeners:  Map<string, MockListener[]> = new Map();
  static last: MockEventSource | null = null;
  static instances: MockEventSource[] = [];

  constructor(url: string) {
    this.url = url;
    MockEventSource.last = this;
    MockEventSource.instances.push(this);
  }

  addEventListener(name: string, fn: MockListener): void {
    const arr = this.listeners.get(name) ?? [];
    arr.push(fn);
    this.listeners.set(name, arr);
  }

  removeEventListener(name: string, fn: MockListener): void {
    const arr = this.listeners.get(name) ?? [];
    this.listeners.set(name, arr.filter((f) => f !== fn));
  }

  close(): void {
    this.closed = true;
  }

  /** Test helper — dispatch a named event with stringified data. */
  emit(name: string, payload: unknown): void {
    const arr = this.listeners.get(name) ?? [];
    const data = typeof payload === "string" ? payload : JSON.stringify(payload);
    for (const fn of arr) fn({ data });
  }
}


function resetDocument(): void {
  document.documentElement.className = "";
  document.body.innerHTML = "";
}


async function loadEnhance(): Promise<void> {
  vi.resetModules();
  await import("../enhance");
}


function setupTrigger(): {
  trigger: HTMLButtonElement;
  panel:   HTMLDivElement;
  logEl:   HTMLPreElement;
  statusEl: HTMLDivElement;
} {
  document.body.innerHTML = `
    <button id="t"
            data-stream-start
            data-stream-target="#panel">START</button>
    <div id="panel" class="stream-fragment" data-stream-fragment>
      <pre data-stream-log></pre>
      <div data-stream-status></div>
    </div>
  `;
  const trigger  = document.getElementById("t") as HTMLButtonElement;
  const panel    = document.getElementById("panel") as HTMLDivElement;
  const logEl    = panel.querySelector("[data-stream-log]") as HTMLPreElement;
  const statusEl = panel.querySelector("[data-stream-status]") as HTMLDivElement;
  return { trigger, panel, logEl, statusEl };
}


beforeEach(() => {
  resetDocument();
  MockEventSource.last = null;
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
});

afterEach(() => {
  vi.restoreAllMocks();
  resetDocument();
  MockEventSource.last = null;
  MockEventSource.instances = [];
});


// ---------------------------------------------------------------------------
// 1. Click opens EventSource at /__stream
// ---------------------------------------------------------------------------
describe("click → open EventSource", () => {
  test("opens EventSource pointing at /__stream", async () => {
    const { trigger } = setupTrigger();
    await loadEnhance();
    trigger.click();
    expect(MockEventSource.last).not.toBeNull();
    expect(MockEventSource.last!.url).toBe("/__stream");
  });

  test("sets data-stream-active marker on the trigger", async () => {
    const { trigger } = setupTrigger();
    await loadEnhance();
    trigger.click();
    expect(trigger.getAttribute("data-stream-active")).toBe("1");
  });

  test("registers log/status/done/error listeners on the source", async () => {
    const { trigger } = setupTrigger();
    await loadEnhance();
    trigger.click();
    const src = MockEventSource.last!;
    expect(src.listeners.has("log")).toBe(true);
    expect(src.listeners.has("status")).toBe(true);
    expect(src.listeners.has("done")).toBe(true);
    expect(src.listeners.has("error")).toBe(true);
  });

  test("nested element inside the trigger still fires the handler", async () => {
    document.body.innerHTML = `
      <button id="t"
              data-stream-start
              data-stream-target="#panel">
        <span id="inner">START</span>
      </button>
      <div id="panel">
        <pre data-stream-log></pre>
        <div data-stream-status></div>
      </div>
    `;
    const inner = document.getElementById("inner") as HTMLSpanElement;
    await loadEnhance();
    inner.click();
    expect(MockEventSource.last).not.toBeNull();
  });
});


// ---------------------------------------------------------------------------
// 2. log events append to <pre data-stream-log>
// ---------------------------------------------------------------------------
describe("log events → append to <pre>", () => {
  test("one log event appends one line with trailing newline", async () => {
    const { trigger, logEl } = setupTrigger();
    await loadEnhance();
    trigger.click();
    MockEventSource.last!.emit("log", { type: "log", message: "hello" });
    expect(logEl.textContent).toBe("hello\n");
  });

  test("multiple log events are appended in arrival order", async () => {
    const { trigger, logEl } = setupTrigger();
    await loadEnhance();
    trigger.click();
    const src = MockEventSource.last!;
    src.emit("log", { type: "log", message: "first" });
    src.emit("log", { type: "log", message: "second" });
    src.emit("log", { type: "log", message: "third" });
    expect(logEl.textContent).toBe("first\nsecond\nthird\n");
  });
});


// ---------------------------------------------------------------------------
// 3. status events replace <div data-stream-status>
// ---------------------------------------------------------------------------
describe("status events → replace <div>", () => {
  test("status event sets the div textContent", async () => {
    const { trigger, statusEl } = setupTrigger();
    await loadEnhance();
    trigger.click();
    MockEventSource.last!.emit("status", {
      type: "status",
      message: "processing",
    });
    expect(statusEl.textContent).toBe("processing");
  });

  test("subsequent status events overwrite (not append)", async () => {
    const { trigger, statusEl } = setupTrigger();
    await loadEnhance();
    trigger.click();
    const src = MockEventSource.last!;
    src.emit("status", { type: "status", message: "starting" });
    src.emit("status", { type: "status", message: "finalizing" });
    expect(statusEl.textContent).toBe("finalizing");
  });
});


// ---------------------------------------------------------------------------
// 4-5. done / error close the source + clear the active marker
// ---------------------------------------------------------------------------
describe("done / error → close + clear marker", () => {
  test("done event closes the source", async () => {
    const { trigger } = setupTrigger();
    await loadEnhance();
    trigger.click();
    const src = MockEventSource.last!;
    src.emit("done", { type: "done", message: "complete" });
    expect(src.closed).toBe(true);
  });

  test("done event clears data-stream-active", async () => {
    const { trigger } = setupTrigger();
    await loadEnhance();
    trigger.click();
    MockEventSource.last!.emit("done", { type: "done", message: "complete" });
    expect(trigger.hasAttribute("data-stream-active")).toBe(false);
  });

  test("error event closes the source", async () => {
    const { trigger } = setupTrigger();
    await loadEnhance();
    trigger.click();
    const src = MockEventSource.last!;
    src.emit("error", { type: "error", message: "boom" });
    expect(src.closed).toBe(true);
  });

  test("error event clears data-stream-active", async () => {
    const { trigger } = setupTrigger();
    await loadEnhance();
    trigger.click();
    MockEventSource.last!.emit("error", { type: "error", message: "boom" });
    expect(trigger.hasAttribute("data-stream-active")).toBe(false);
  });
});


// ---------------------------------------------------------------------------
// 6. Per-trigger guard (data-stream-active)
// ---------------------------------------------------------------------------
describe("per-trigger active guard", () => {
  test("re-clicking while active does NOT open a second source", async () => {
    const { trigger } = setupTrigger();
    await loadEnhance();
    trigger.click();
    trigger.click();
    trigger.click();
    expect(MockEventSource.instances).toHaveLength(1);
  });

  test("after done, clicking again opens a fresh source", async () => {
    const { trigger } = setupTrigger();
    await loadEnhance();
    trigger.click();
    expect(MockEventSource.instances).toHaveLength(1);
    MockEventSource.last!.emit("done", { type: "done", message: "x" });
    trigger.click();
    expect(MockEventSource.instances).toHaveLength(2);
  });
});


// ---------------------------------------------------------------------------
// 7. Idempotent listener binding (A19-R symbol guard preserved)
// ---------------------------------------------------------------------------
describe("idempotent listener binding", () => {
  test("re-importing the module does NOT double-fire on a click", async () => {
    const { trigger } = setupTrigger();
    await loadEnhance();
    await loadEnhance();
    await loadEnhance();
    trigger.click();
    // Only ONE source opened, not three.
    expect(MockEventSource.instances).toHaveLength(1);
  });
});


// ---------------------------------------------------------------------------
// 8. Defensive paths → no EventSource opened
// ---------------------------------------------------------------------------
describe("defensive paths", () => {
  test("trigger without data-stream-target → no source", async () => {
    document.body.innerHTML = `<button id="t" data-stream-start>x</button>`;
    const trigger = document.getElementById("t") as HTMLButtonElement;
    await loadEnhance();
    trigger.click();
    expect(MockEventSource.last).toBeNull();
  });

  test("trigger pointing at missing element → no source", async () => {
    document.body.innerHTML = `
      <button id="t" data-stream-start data-stream-target="#nope">x</button>
    `;
    const trigger = document.getElementById("t") as HTMLButtonElement;
    await loadEnhance();
    trigger.click();
    expect(MockEventSource.last).toBeNull();
  });

  test("invalid CSS selector → silent no-op (no throw, no source)", async () => {
    document.body.innerHTML = `
      <button id="t"
              data-stream-start
              data-stream-target="###bad###">x</button>
    `;
    const trigger = document.getElementById("t") as HTMLButtonElement;
    await loadEnhance();
    expect(() => trigger.click()).not.toThrow();
    expect(MockEventSource.last).toBeNull();
  });
});


// ---------------------------------------------------------------------------
// 9. Malformed JSON in event data
// ---------------------------------------------------------------------------
describe("malformed event data", () => {
  test("non-JSON string in log event → silent drop, log unchanged", async () => {
    const { trigger, logEl } = setupTrigger();
    await loadEnhance();
    trigger.click();
    MockEventSource.last!.emit("log", "not-json{");
    expect(logEl.textContent).toBe("");
  });

  test("JSON without message field → silent drop", async () => {
    const { trigger, logEl } = setupTrigger();
    await loadEnhance();
    trigger.click();
    MockEventSource.last!.emit("log", { type: "log" });
    expect(logEl.textContent).toBe("");
  });

  test("message field that's not a string → silent drop", async () => {
    const { trigger, logEl } = setupTrigger();
    await loadEnhance();
    trigger.click();
    MockEventSource.last!.emit("log", { type: "log", message: 123 });
    expect(logEl.textContent).toBe("");
  });
});


// ---------------------------------------------------------------------------
// 10. Missing EventSource global → silent no-op
// ---------------------------------------------------------------------------
describe("missing EventSource", () => {
  test("no EventSource → click is a silent no-op (no throw)", async () => {
    // Tear down the mock so EventSource is undefined.
    vi.unstubAllGlobals();
    // Defensive: blow away any leftover binding from earlier
    // imports in this run.
    (globalThis as { EventSource?: unknown }).EventSource = undefined;

    const { trigger } = setupTrigger();
    await loadEnhance();
    expect(() => trigger.click()).not.toThrow();
    // No marker set because the function bails before opening.
    expect(trigger.hasAttribute("data-stream-active")).toBe(false);
  });
});


// ---------------------------------------------------------------------------
// Non-interference with A19/A20/A21 paths
// ---------------------------------------------------------------------------
describe("non-interference with prior cards", () => {
  test("A19-R toggle still works alongside stream trigger", async () => {
    document.body.innerHTML = `
      <button id="stream-btn"
              data-stream-start
              data-stream-target="#panel">START</button>
      <div id="panel">
        <pre data-stream-log></pre>
        <div data-stream-status></div>
      </div>
      <button id="toggle-btn" data-toggle-target="#expander">T</button>
      <div id="expander">x</div>
    `;
    await loadEnhance();
    const expander = document.getElementById("expander") as HTMLDivElement;
    const toggleBtn = document.getElementById("toggle-btn") as HTMLButtonElement;
    toggleBtn.click();
    expect(expander.classList.contains("is-open")).toBe(true);
    toggleBtn.click();
    expect(expander.classList.contains("is-open")).toBe(false);
  });

  test("plain clicks on non-trigger elements do not open a source", async () => {
    document.body.innerHTML = `<div id="plain">click</div>`;
    const plain = document.getElementById("plain") as HTMLDivElement;
    await loadEnhance();
    plain.click();
    expect(MockEventSource.last).toBeNull();
  });
});
