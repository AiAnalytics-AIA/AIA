// @vitest-environment jsdom
// Dotazník's Deep Research panel shows a run a Lead card started while it is open, without a
// reload: it read its runs when it mounted and polls only a run it already knows (review of #1006).
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { deepResearch, type DeepResearchRun } from "@/lib/api";
import { announceDeepResearchStarted } from "@/lib/deep-research-started";

import { DeepResearchPanel } from "./DeepResearchPanel";

vi.mock("@/lib/api", async () => ({
  ApiError: (await vi.importActual<typeof import("@/lib/api")>("@/lib/api")).ApiError,
  deepResearch: { runs: vi.fn(), events: vi.fn(), bundle: vi.fn() },
}));
vi.mock("./context", () => ({
  useResearch: () => ({ frame: { studyId: "S-1", canEdit: false }, store: {}, confirm: vi.fn(), state: {} }),
}));
vi.mock("./frame", () => ({ canReview: () => false }));
vi.mock("./useStepActivity", () => ({ useStepActivity: () => [] }));
vi.mock("./StepActivityPanel", () => ({ StepActivityPanel: () => null }));
vi.mock("./DeepResearchWaits", () => ({ DeepResearchWaits: () => null }));

const run = (run_id: string, purpose = "DESIGN_RESEARCH"): DeepResearchRun =>
  ({ run_id, purpose, phase: "QUEUED", is_terminal: true, retryable: false, steps: [], created_at: null }) as unknown as DeepResearchRun;

beforeEach(() => vi.resetAllMocks());
afterEach(cleanup);

describe("DeepResearchPanel", () => {
  it("reads and selects a design run a Lead card started while it is open", async () => {
    vi.mocked(deepResearch.runs).mockResolvedValueOnce([]);
    render(<DeepResearchPanel />);
    expect(await screen.findByText("Zatím bez běhů.")).toBeTruthy();
    vi.mocked(deepResearch.runs).mockResolvedValue([run("RUN-new")]);
    act(() => announceDeepResearchStarted({ runId: "RUN-new", purpose: "DESIGN_RESEARCH" }));
    await waitFor(() => expect(screen.getByRole("status")).toBeTruthy());
    expect(screen.queryByText("Zatím bez běhů.")).toBeNull();
  });

  it("does not read again for an Interpretation run, which belongs to the results", async () => {
    vi.mocked(deepResearch.runs).mockResolvedValue([]);
    render(<DeepResearchPanel />);
    await screen.findByText("Zatím bez běhů.");
    act(() => announceDeepResearchStarted({ runId: "RUN-i", purpose: "INTERPRETATION_RESEARCH" }));
    expect(deepResearch.runs).toHaveBeenCalledTimes(1);
  });
});
