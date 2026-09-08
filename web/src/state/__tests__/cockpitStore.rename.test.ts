/**
 * #188 -- rename patches the LIST copy of the title (thread.items, and the
 * relationships list when the thread is one), not only the working meta.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    listThreads: vi.fn(), createThread: vi.fn(), getThread: vi.fn(),
    renameThread: vi.fn(), getRelationshipTurns: vi.fn(),
  };
});

import * as api from "../../lib/api";
import { cockpit, useCockpit } from "../cockpitStore";

const T = (id: string, title: string, project_id: string | null = null) => ({
  thread_id: id, title, created_at: 1, updated_at: 2, message_count: 0,
  archived: false, summary: null, summary_ts_ms: null, project_id,
});

afterEach(() => vi.clearAllMocks());

describe("thread.actions.rename (#188)", () => {
  it("★ the list row reads the new title after a rename", async () => {
    vi.mocked(api.listThreads).mockResolvedValue([T("t1", "Old title"), T("t2", "Other")] as never);
    vi.mocked(api.getThread).mockResolvedValue({ meta: T("t1", "Old title"), messages: [] } as never);
    vi.mocked(api.renameThread).mockResolvedValue(T("t1", "New title") as never);
    const { result } = renderHook(() => useCockpit((s) => s.thread));
    await act(async () => { await cockpit.thread.actions.init(); });
    await act(async () => { await cockpit.thread.actions.open("t1"); });
    expect(result.current.meta?.thread_id).toBe("t1");
    await act(async () => { await cockpit.thread.actions.rename("New title"); });
    expect(api.renameThread).toHaveBeenCalledWith("t1", "New title");
    expect(result.current.meta?.title).toBe("New title");
    const titles = Object.fromEntries(result.current.items.map((t) => [t.thread_id, t.title]));
    expect(titles.t1).toBe("New title");
    expect(titles.t2).toBe("Other");   // the other row is untouched
  });
});
