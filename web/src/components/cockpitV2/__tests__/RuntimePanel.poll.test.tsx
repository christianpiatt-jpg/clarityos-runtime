/**
 * The envelope poll (housekeeping 2026-09-16): /runtime/envelope is 62.5 KB
 * and one sitting pulled it 18 times at the old 10 s cadence. The OPEN
 * panel polls at RUNTIME_POLL_MS now, never below 60 s; a closed panel
 * polls nothing. The caller is named in the panel's header comment.
 *
 * ★ These pin the PANEL'S USE of the constant, not the constant alone: the
 * interval the panel installs carries RUNTIME_POLL_MS, its tick reads
 * through the same door, and closing the panel clears it.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

const load = vi.hoisted(() => vi.fn(async () => {}));
vi.mock("../../../state/cockpitStore", () => ({
  useCockpit: (sel: (s: { runtime: { status: string; envelope: null; error: null } }) => unknown) =>
    sel({ runtime: { status: "idle", envelope: null, error: null } }),
  cockpit: { runtime: { actions: { load } } },
}));
vi.mock("../../runtime/EnvelopeRenderer", () => ({ default: () => null }));

import RuntimePanel, { RUNTIME_POLL_MS } from "../RuntimePanel";

const toggle = () => screen.getByRole("button", { name: /runtime/i });

describe("the runtime envelope poll", () => {
  beforeEach(() => { load.mockClear(); });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it("★ never below 60 s", () => {
    expect(RUNTIME_POLL_MS).toBeGreaterThanOrEqual(60_000);
  });

  it("★ closed: no read, no timer; open: one read now and an interval of RUNTIME_POLL_MS; closed again: cleared", () => {
    const si = vi.spyOn(window, "setInterval");
    const ci = vi.spyOn(window, "clearInterval");
    const { unmount } = render(<RuntimePanel />);
    expect(load).toHaveBeenCalledTimes(0);
    expect(si).not.toHaveBeenCalled();

    fireEvent.click(toggle());                              // open
    expect(load).toHaveBeenCalledTimes(1);                  // first paint has data
    expect(si).toHaveBeenCalledTimes(1);
    const [tick, delay] = si.mock.calls[0] as unknown as [() => void, number];
    expect(delay).toBe(RUNTIME_POLL_MS);
    tick();                                                 // the interval reads through the same door
    expect(load).toHaveBeenCalledTimes(2);

    fireEvent.click(toggle());                              // close
    expect(ci).toHaveBeenCalledWith(si.mock.results[0].value);
    expect(si).toHaveBeenCalledTimes(1);                    // no second timer
    unmount();
    expect(load).toHaveBeenCalledTimes(2);
  });
});
