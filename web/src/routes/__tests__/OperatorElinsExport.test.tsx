// v71 / Unit 78 — OperatorElinsExport route tests.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type {
  ConfigResponse,
  ElInsExportJsonResponse,
  ElInsOperatorSummaryResponse,
} from "../../lib/api";
import OperatorElinsExport from "../OperatorElinsExport";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>(
    "../../lib/api",
  );
  return {
    ...actual,
    getElInsOperatorSummary: vi.fn(),
    getElInsExportJson:      vi.fn(),
    fetchElInsExportPdfBlob: vi.fn(),
    config:                  vi.fn(),
  };
});

import {
  config,
  fetchElInsExportPdfBlob,
  getElInsExportJson,
  getElInsOperatorSummary,
} from "../../lib/api";

const mockSummary = vi.mocked(getElInsOperatorSummary);
const mockJson    = vi.mocked(getElInsExportJson);
const mockPdf     = vi.mocked(fetchElInsExportPdfBlob);
const mockConfig  = vi.mocked(config);

function makeSummary(): ElInsOperatorSummaryResponse {
  return {
    recent_classification_distribution: {
      high_el: 4, high_ins: 2, balanced: 14,
    },
    avg_tsi:     82,
    trend:       "improving",
    sample_size: 20,
  };
}

function makeJsonResponse(): ElInsExportJsonResponse {
  return {
    operator_id:  "op_alice",
    generated_at: "2026-05-13T19:00:00Z",
    records: [
      {
        timestamp: "2026-05-13T18:59:00Z",
        thread_id: "t1",
        el: 5.5, ins: 3.0,
        classification: "high_el",
        tsi: 78,
        source: "on_demand",
      },
    ],
  };
}

function makeConfig(): ConfigResponse {
  return {
    ok: true,
    data: {
      backend: "memory",
      version: "4.14",
    },
  };
}

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/operator/el_ins/export"]}>
      <OperatorElinsExport />
    </MemoryRouter>,
  );
}

// Stub URL.createObjectURL/revokeObjectURL — jsdom doesn't ship them.
beforeEach(() => {
  mockSummary.mockReset();
  mockJson.mockReset();
  mockPdf.mockReset();
  mockConfig.mockReset();
  if (typeof URL.createObjectURL !== "function") {
    (URL.createObjectURL as unknown) = vi.fn(() => "blob:fake");
  } else {
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:fake");
  }
  if (typeof URL.revokeObjectURL !== "function") {
    (URL.revokeObjectURL as unknown) = vi.fn();
  } else {
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  }
});

afterEach(() => {
  vi.restoreAllMocks();
  try { localStorage.clear(); } catch { /* noop */ }
});

describe("OperatorElinsExport route", () => {
  test("fires summary + config on mount", async () => {
    mockSummary.mockResolvedValueOnce(makeSummary());
    mockConfig.mockResolvedValueOnce(makeConfig());
    renderRoute();
    await waitFor(() => {
      expect(mockSummary).toHaveBeenCalledTimes(1);
      expect(mockConfig).toHaveBeenCalledTimes(1);
    });
  });

  test("renders the preview block after fetch", async () => {
    mockSummary.mockResolvedValueOnce(makeSummary());
    mockConfig.mockResolvedValueOnce(makeConfig());
    renderRoute();
    const preview = await screen.findByTestId("el-ins-export-summary");
    expect(preview).toHaveTextContent(/sample size/i);
    expect(preview).toHaveTextContent("20");
    expect(preview).toHaveTextContent("82/100");
    expect(preview).toHaveTextContent("improving");
  });

  test("renders version in footer", async () => {
    mockSummary.mockResolvedValueOnce(makeSummary());
    mockConfig.mockResolvedValueOnce(makeConfig());
    renderRoute();
    const version = await screen.findByTestId("el-ins-export-version");
    expect(version).toHaveTextContent("4.14");
  });

  test("DOWNLOAD JSON button fires the JSON helper", async () => {
    const user = userEvent.setup();
    mockSummary.mockResolvedValueOnce(makeSummary());
    mockConfig.mockResolvedValueOnce(makeConfig());
    mockJson.mockResolvedValueOnce(makeJsonResponse());
    renderRoute();
    await screen.findByTestId("el-ins-export-summary");
    await user.click(screen.getByTestId("el-ins-export-json-btn"));
    await waitFor(() => expect(mockJson).toHaveBeenCalledTimes(1));
  });

  test("DOWNLOAD PDF button fires the PDF helper", async () => {
    const user = userEvent.setup();
    mockSummary.mockResolvedValueOnce(makeSummary());
    mockConfig.mockResolvedValueOnce(makeConfig());
    mockPdf.mockResolvedValueOnce(new Blob([new Uint8Array([0x25, 0x50, 0x44, 0x46])], {
      type: "application/pdf",
    }));
    renderRoute();
    await screen.findByTestId("el-ins-export-summary");
    await user.click(screen.getByTestId("el-ins-export-pdf-btn"));
    await waitFor(() => expect(mockPdf).toHaveBeenCalledTimes(1));
  });

  test("buttons disable while a download is in flight", async () => {
    const user = userEvent.setup();
    mockSummary.mockResolvedValueOnce(makeSummary());
    mockConfig.mockResolvedValueOnce(makeConfig());
    // Resolve PDF helper after assertion so the loading state is observable.
    let resolveBlob: ((b: Blob) => void) | null = null;
    mockPdf.mockReturnValueOnce(new Promise<Blob>((res) => { resolveBlob = res; }));
    renderRoute();
    await screen.findByTestId("el-ins-export-summary");
    const pdfBtn = screen.getByTestId("el-ins-export-pdf-btn");
    const jsonBtn = screen.getByTestId("el-ins-export-json-btn");
    await user.click(pdfBtn);
    expect(pdfBtn).toBeDisabled();
    expect(jsonBtn).toBeDisabled();
    // Resolve the pending promise; cast restores resolveBlob's type past CFA narrowing.
    (resolveBlob as ((b: Blob) => void) | null)?.(new Blob([new Uint8Array([0x25, 0x50, 0x44, 0x46])]));
    await waitFor(() => expect(pdfBtn).not.toBeDisabled());
  });

  test("JSON download failure surfaces in error banner", async () => {
    const user = userEvent.setup();
    mockSummary.mockResolvedValueOnce(makeSummary());
    mockConfig.mockResolvedValueOnce(makeConfig());
    mockJson.mockRejectedValueOnce(new Error("json boom"));
    renderRoute();
    await screen.findByTestId("el-ins-export-summary");
    await user.click(screen.getByTestId("el-ins-export-json-btn"));
    await screen.findByTestId("el-ins-export-error");
  });

  test("PDF download failure surfaces in error banner", async () => {
    const user = userEvent.setup();
    mockSummary.mockResolvedValueOnce(makeSummary());
    mockConfig.mockResolvedValueOnce(makeConfig());
    mockPdf.mockRejectedValueOnce(new Error("pdf boom"));
    renderRoute();
    await screen.findByTestId("el-ins-export-summary");
    await user.click(screen.getByTestId("el-ins-export-pdf-btn"));
    await screen.findByTestId("el-ins-export-error");
  });

  test("empty operator state renders empty preview", async () => {
    mockSummary.mockResolvedValueOnce({
      recent_classification_distribution: { high_el: 0, high_ins: 0, balanced: 0 },
      avg_tsi: 0,
      trend: "stable",
      sample_size: 0,
    });
    mockConfig.mockResolvedValueOnce(makeConfig());
    renderRoute();
    const preview = await screen.findByTestId("el-ins-export-summary");
    // sample_size 0 still renders the kv panel; the empty class only
    // appears when summary itself is missing.
    expect(preview).toHaveTextContent("0");
  });

  test("no operator_id label appears in the export surface", async () => {
    mockSummary.mockResolvedValueOnce(makeSummary());
    mockConfig.mockResolvedValueOnce(makeConfig());
    renderRoute();
    await screen.findByTestId("el-ins-export-summary");
    // Identity invariant from v67/v68 still holds.
    expect(screen.queryByText(/operator_id/i)).not.toBeInTheDocument();
  });
});
