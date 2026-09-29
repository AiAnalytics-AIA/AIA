// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { research, researchAgents, type ResearchAgentJob, type ResearchAgentResult } from "@/lib/api";
import type { JobUpdate } from "@/research/jobs";
import type { ResearchStore } from "@/research/store";
import { canonicalProject, useResearchAgents } from "./useResearchAgents";

vi.mock("@/lib/api", () => ({
  research: { submitDesign: vi.fn() },
  researchAgents: { jobs: vi.fn(), job: vi.fn(), start: vi.fn(), result: vi.fn(), accept: vi.fn(), design: vi.fn(), cancel: vi.fn() },
}));
const job: ResearchAgentJob = {
  run_id: "RUN-1", design_revision_id: "REV-1", action: "analyze_brief", status: "COMPLETED",
  is_terminal: true, needs_attention: false, context_sha256: "hash", harness_version: "v1",
  created_at: null, steps: [], actual_cost_usd: null,
};
const result: ResearchAgentResult = {
  result: { project: { goal: "Original", title: "Proposed" }, proposal: { problem_summary: "Proposed summary" }, analysis: { objectives: ["A"] } },
  provenance: { agent_id: "research", design_revision_id: "REV-1", context_sha256: "hash", status: "PROPOSED" },
};
let project: Record<string, unknown>;
let store: ResearchStore;
let flush: ReturnType<typeof vi.fn>;
let onUpdate = vi.fn<(u: JobUpdate | null) => void>();
let running: Promise<unknown> | null;
function Harness({ studyId = "STU-1" }: { studyId?: string }) {
  const [error, setError] = useState("");
  const agents = useResearchAgents(studyId, store, onUpdate);
  return <>
    <button onClick={() => { running = agents.run("analyze_brief", {}, "Brief").catch((e: Error) => setError(e.message)); }}>Run</button>
    <button onClick={() => { project = { ...project, goal: "Edited" }; }}>Edit</button>
    <button onClick={() => void agents.open(job)}>Open</button>
    <p>{error}</p><p>{agents.notice}</p>{agents.dialog}
  </>;
}
beforeEach(() => {
  vi.resetAllMocks();
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
  project = { goal: "Original" }; flush = vi.fn().mockResolvedValue(undefined); onUpdate = vi.fn(); running = null;
  store = { get: () => ({ project }), flush,
    update: (fn: (state: { project: Record<string, unknown> }) => { project: Record<string, unknown> }) => { project = fn({ project }).project; },
  } as unknown as ResearchStore;
  vi.mocked(research.submitDesign).mockResolvedValue({ revision_id: "REV-1" } as Awaited<ReturnType<typeof research.submitDesign>>);
  vi.mocked(researchAgents.jobs).mockResolvedValue([]);
  vi.mocked(researchAgents.start).mockResolvedValue(job);
  vi.mocked(researchAgents.job).mockResolvedValue(job);
  vi.mocked(researchAgents.result).mockResolvedValue(result);
  vi.mocked(researchAgents.accept).mockResolvedValue({ revision_id: "REV-2" } as Awaited<ReturnType<typeof researchAgents.accept>>);
  vi.mocked(researchAgents.design).mockResolvedValue({ content: { goal: "Original" } } as unknown as Awaited<ReturnType<typeof researchAgents.design>>);
});
afterEach(cleanup);

it("freezes a Study revision, follows the job, and writes nothing until review", async () => {
  render(<Harness />); fireEvent.click(screen.getByText("Run"));
  await screen.findByRole("dialog");
  expect(research.submitDesign).toHaveBeenCalledWith("STU-1", { goal: "Original" }, "brief");
  expect(researchAgents.start).toHaveBeenCalledWith("STU-1", "REV-1", "analyze_brief", "");
  expect(researchAgents.accept).not.toHaveBeenCalled(); expect(project).toEqual({ goal: "Original" });
  fireEvent.click(screen.getByText("Použít návrh"));
  await waitFor(() => expect(project.title).toBe("Proposed"));
  expect(researchAgents.accept).toHaveBeenCalledExactlyOnceWith("STU-1", "RUN-1", "REV-1");
});
it("keeping the current design leaves the saved proposal unapplied", async () => {
  render(<Harness />); fireEvent.click(screen.getByText("Run"));
  fireEvent.click(await screen.findByText("Ponechat současný návrh"));
  await screen.findByText(/současný návrh jste ponechali/);
  expect(researchAgents.accept).not.toHaveBeenCalled(); expect(project).toEqual({ goal: "Original" });
});
it("edits during review block acceptance instead of overwriting them", async () => {
  render(<Harness />); fireEvent.click(screen.getByText("Run"));
  await screen.findByRole("dialog"); fireEvent.click(screen.getByText("Edit")); fireEvent.click(screen.getByText("Použít návrh"));
  await screen.findByText(/Zadání se během AI kroku změnilo/);
  expect(researchAgents.accept).not.toHaveBeenCalled(); expect(project.goal).toBe("Edited");
});
it("restores a running job without creating another job or automatically applying it", async () => {
  vi.mocked(researchAgents.jobs).mockResolvedValue([{ ...job, status: "RUNNING", is_terminal: false }]);
  render(<Harness />);
  await screen.findByText(/Návrh AI je uložený/);
  expect(researchAgents.job).toHaveBeenCalledWith("STU-1", "RUN-1");
  expect(researchAgents.start).not.toHaveBeenCalled(); expect(researchAgents.accept).not.toHaveBeenCalled();
});
it("leaving a review settles its local promise and never cancels the durable job", async () => {
  const view = render(<Harness />); fireEvent.click(screen.getByText("Run"));
  await screen.findByRole("dialog"); view.unmount();
  await act(async () => { await running; });
  expect(researchAgents.accept).not.toHaveBeenCalled(); expect(researchAgents.cancel).not.toHaveBeenCalled();
});
it("does not replace the original job error with a failed inbox refresh", async () => {
  vi.mocked(researchAgents.jobs).mockResolvedValueOnce([]).mockResolvedValueOnce([]).mockRejectedValueOnce(new Error("Inbox failed"));
  vi.mocked(researchAgents.job).mockResolvedValue({ ...job, status: "RECOVERY_REQUIRED", needs_attention: true });
  render(<Harness />); fireEvent.click(screen.getByText("Run"));
  await screen.findByText(/AI krok čeká na zásah/);
  expect(researchAgents.accept).not.toHaveBeenCalled();
});
it("opens an older proposal for reading without allowing it to replace the current design", async () => {
  project = { goal: "Edited" }; render(<Harness />); fireEvent.click(screen.getByText("Open"));
  await screen.findByRole("dialog"); expect(screen.queryByText("Použít návrh")).toBeNull();
  fireEvent.click(screen.getByText("Zavřít")); await screen.findByText(/staršího zadání/);
  expect(researchAgents.accept).not.toHaveBeenCalled();
});
it("compares object keys independently of JSON ordering, retaining array order", () => {
  expect(canonicalProject({ a: [1, 2], b: { d: 4, c: 3 } })).toBe(canonicalProject({ b: { c: 3, d: 4 }, a: [1, 2] }));
  expect(canonicalProject([1, 2])).not.toBe(canonicalProject([2, 1]));
});
