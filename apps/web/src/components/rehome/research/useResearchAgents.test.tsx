// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useLayoutEffect, useState } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ApiError, research, researchAgents, type ResearchAgentJob, type ResearchAgentResult } from "@/lib/api";
import type { JobUpdate } from "@/research/jobs";
import type { ResearchStore } from "@/research/store";
import { useResearchAgents } from "./useResearchAgents";

vi.mock("@/lib/api", async () => ({
  ApiError: (await vi.importActual<typeof import("@/lib/api")>("@/lib/api")).ApiError,
  research: { submitDesign: vi.fn() },
  researchAgents: { jobs: vi.fn(), job: vi.fn(), start: vi.fn(), result: vi.fn(), accept: vi.fn(), design: vi.fn(), cancel: vi.fn(), resume: vi.fn(), dismiss: vi.fn(), rebuild: vi.fn() },
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
let analysis: Record<string, unknown> | null;
let store: ResearchStore;
let flush: ReturnType<typeof vi.fn>;
let reload: ReturnType<typeof vi.fn>;
let conflict: ReturnType<typeof vi.fn>;
/** The working revision the copy is at, as AIA saved it. */
let revision: number;
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
  project = { goal: "Original" }; analysis = null; flush = vi.fn().mockResolvedValue(undefined); onUpdate = vi.fn(); running = null;
  revision = 3;
  // The server wrote the working copy (ADR 0026 decision 6): a reload reads what it wrote.
  reload = vi.fn().mockImplementation(async () => {
    project = { ...project, title: "Proposed" }; analysis = { objectives: ["A"] }; revision = 4;
  });
  conflict = vi.fn();
  store = { get: () => ({ project, analysis, revision, save: { kind: "saved" } }), flush, reload, conflict,
    update: (fn: (state: { project: Record<string, unknown>; analysis: Record<string, unknown> | null }) => { project: Record<string, unknown>; analysis?: Record<string, unknown> }) => {
      const next = fn({ project, analysis }); project = next.project; analysis = next.analysis ?? analysis;
    },
  } as unknown as ResearchStore;
  vi.mocked(research.submitDesign).mockResolvedValue({ revision_id: "REV-1" } as Awaited<ReturnType<typeof research.submitDesign>>);
  vi.mocked(researchAgents.jobs).mockResolvedValue([]);
  vi.mocked(researchAgents.start).mockResolvedValue(job);
  vi.mocked(researchAgents.job).mockResolvedValue(job);
  vi.mocked(researchAgents.resume).mockResolvedValue({ ...job, status: "RUNNING", is_terminal: false });
  vi.mocked(researchAgents.result).mockResolvedValue(result);
  vi.mocked(researchAgents.accept).mockResolvedValue({ design_revision_id: "REV-2", workspace_revision: 4 } as Awaited<ReturnType<typeof researchAgents.accept>>);
  vi.mocked(researchAgents.design).mockResolvedValue({ content: { goal: "Original" } } as unknown as Awaited<ReturnType<typeof researchAgents.design>>);
});
afterEach(cleanup);

function AdviceContinuation({ waiting = true }: { waiting?: boolean }) {
  const agents = useResearchAgents("STU-1", store, onUpdate, true);
  return <><button onClick={() => { running = agents.continueAdvice({ ...job, action: "answer_memory", status: waiting ? "WAITING_PROVIDER" : "RUNNING", is_terminal: false,
    steps: waiting ? [{ waiting_reason: "ai_runtime_unavailable" }] as ResearchAgentJob["steps"] : [],
  }); }}>Continue stored advice</button>{agents.adviceReview ? <><p>{String(agents.adviceReview.result.result.proposal.problem_summary)}</p><button onClick={() => agents.adviceReview?.decide(false)}>Close advice</button></> : null}{agents.dialog}</>;
}

it("explicitly resumes the existing advice id without creating a revision, paid job or design acceptance", async () => {
  vi.mocked(researchAgents.job).mockResolvedValue({ ...job, action: "answer_memory" });
  render(<AdviceContinuation />); fireEvent.click(screen.getByText("Continue stored advice"));
  await screen.findByText("Proposed summary");
  expect(researchAgents.resume).toHaveBeenCalledExactlyOnceWith("STU-1", "RUN-1");
  expect(researchAgents.start).not.toHaveBeenCalled(); expect(research.submitDesign).not.toHaveBeenCalled();
  expect(screen.queryByRole("dialog")).toBeNull(); fireEvent.click(screen.getByText("Close advice"));
  await act(async () => { await running; });
  expect(researchAgents.accept).not.toHaveBeenCalled(); expect(project).toEqual({ goal: "Original" });
});

it("refreshes following of an uncertain running advice job without a resume mutation or resubmission", async () => {
  vi.mocked(researchAgents.job).mockResolvedValue({ ...job, action: "answer_memory" });
  render(<AdviceContinuation waiting={false} />); fireEvent.click(screen.getByText("Continue stored advice"));
  await screen.findByText("Proposed summary");
  expect(researchAgents.resume).not.toHaveBeenCalled(); expect(researchAgents.start).not.toHaveBeenCalled();
  expect(research.submitDesign).not.toHaveBeenCalled(); fireEvent.click(screen.getByText("Close advice"));
  await act(async () => { await running; }); expect(researchAgents.accept).not.toHaveBeenCalled();
});

function Confirming({ answer }: { answer: boolean }) {
  const [error, setError] = useState("");
  const agents = useResearchAgents("STU-1", store, onUpdate, false, false, async (m) => { asked.push(m); return answer; });
  return <><button onClick={() => { running = agents.run("analyze_brief", {}, "Brief").catch((e: Error) => setError(e.message)); }}>Run</button><p>{error}</p>{agents.dialog}</>;
}
let asked: string[] = [];
const thresholdAsks = () => new ApiError(409, "cost_confirmation_required", "confirm", null, { ceiling_usd: 2, limit_usd: 1 });

it("a job reaching the confirmation threshold starts only on the person's yes, confirming the server's ceiling", async () => {
  asked = [];
  vi.mocked(researchAgents.start).mockRejectedValueOnce(thresholdAsks()).mockResolvedValueOnce(job);
  render(<Confirming answer />); fireEvent.click(screen.getByText("Run"));
  await screen.findByRole("dialog");
  expect(asked).toHaveLength(1); expect(asked[0]).toContain("Práh potvrzení");
  expect(vi.mocked(researchAgents.start).mock.calls.map((c) => c[5])).toEqual([undefined, 2]);
});

it("a no to the threshold starts nothing and says why", async () => {
  asked = [];
  vi.mocked(researchAgents.start).mockRejectedValueOnce(thresholdAsks());
  render(<Confirming answer={false} />); fireEvent.click(screen.getByText("Run"));
  await act(async () => { await running; });
  expect(asked).toHaveLength(1);
  expect(researchAgents.start).toHaveBeenCalledOnce(); expect(researchAgents.job).not.toHaveBeenCalled();
  expect(screen.getByText(/AI krok se nespustil/)).toBeTruthy();
});

it("freezes a Study revision naming its working revision, follows the job, and writes nothing until review", async () => {
  render(<Harness />); fireEvent.click(screen.getByText("Run"));
  await screen.findByRole("dialog");
  expect(research.submitDesign).toHaveBeenCalledWith("STU-1", { goal: "Original" }, "brief", 3);
  // No confirmation is sent unless the server asks for one (LO15).
  expect(researchAgents.start).toHaveBeenCalledWith("STU-1", "REV-1", "analyze_brief", "", undefined, undefined);
  expect(researchAgents.accept).not.toHaveBeenCalled(); expect(project).toEqual({ goal: "Original" });
  fireEvent.click(screen.getByText("Použít návrh"));
  await waitFor(() => expect(reload).toHaveBeenCalledOnce());
  // One server transaction with the working revision the person has; the browser then reloads
  // what the server wrote and writes nothing back itself.
  expect(researchAgents.accept).toHaveBeenCalledExactlyOnceWith("STU-1", "RUN-1", "REV-1", 3);
  expect(project.title).toBe("Proposed"); expect(analysis).toEqual({ objectives: ["A"] });
});
it("keeps a run that started before the hook's mount effect ran", async () => {
  // A click can land between React's commit and its passive effects (QuestionnaireStep's
  // flake): a layout effect runs in that gap, so the run starts before the mount effect.
  let release = () => {};
  vi.mocked(research.submitDesign).mockReturnValue(new Promise((resolve) => {
    release = () => resolve({ revision_id: "REV-1" } as Awaited<ReturnType<typeof research.submitDesign>>);
  }));
  function Early() {
    const agents = useResearchAgents("STU-1", store, onUpdate);
    const { run } = agents;
    useLayoutEffect(() => { running = run("analyze_brief", {}, "Brief"); }, [run]);
    return <><p>{agents.busy ? "busy" : "idle"}</p>{agents.dialog}</>;
  }
  render(<Early />);
  expect(screen.getByText("busy")).toBeTruthy();
  await act(async () => { release(); });
  fireEvent.click(await screen.findByText("Použít návrh"));
  await act(async () => { await running; });
  expect(researchAgents.accept).toHaveBeenCalledExactlyOnceWith("STU-1", "RUN-1", "REV-1", 3);
  expect(screen.getByText("idle")).toBeTruthy();
});
it("a second click resumes the same unbilled runtime park without editing the brief", async () => {
  vi.mocked(researchAgents.start).mockResolvedValue({
    ...job, status: "WAITING_PROVIDER", is_terminal: false,
    steps: [{ waiting_reason: "ai_runtime_unavailable" }] as ResearchAgentJob["steps"],
  });
  render(<Harness />); fireEvent.click(screen.getByText("Run"));
  await screen.findByRole("dialog");
  expect(researchAgents.resume).toHaveBeenCalledExactlyOnceWith("STU-1", "RUN-1");
  expect(researchAgents.job).toHaveBeenCalledWith("STU-1", "RUN-1");
  fireEvent.click(screen.getByText("Ponechat současný návrh"));
  await act(async () => { await running; });
});
it("keeping the current design leaves the saved proposal unapplied", async () => {
  render(<Harness />); fireEvent.click(screen.getByText("Run"));
  fireEvent.click(await screen.findByText("Ponechat současný návrh"));
  await screen.findByText(/současný návrh jste ponechali/);
  expect(researchAgents.accept).not.toHaveBeenCalled(); expect(project).toEqual({ goal: "Original" });
});
it("a stale refusal names the items in Czech and never overwrites the person's edit", async () => {
  vi.mocked(researchAgents.accept).mockRejectedValue(new ApiError(409, "stale_proposal", "stale", null, {
    reason: "items_changed", conflicting_items: ["content:brief:goal", "content:objective:najít práh ceny", "analysis:objective:najít práh ceny"],
  }));
  render(<Harness />); fireEvent.click(screen.getByText("Run"));
  await screen.findByRole("dialog"); fireEvent.click(screen.getByText("Edit")); fireEvent.click(screen.getByText("Použít návrh"));
  await screen.findByText(/Cíl studie, Cíl „najít práh ceny“\./);
  expect(flush).toHaveBeenCalled();
  expect(researchAgents.accept).toHaveBeenCalledExactlyOnceWith("STU-1", "RUN-1", "REV-1", 3);
  // The proposal stays open to read; it is not offered again, and nothing was reloaded.
  fireEvent.click(await screen.findByText("Ponechat současný návrh"));
  await screen.findByText(/současný návrh jste ponechali/);
  expect(reload).not.toHaveBeenCalled(); expect(project.goal).toBe("Edited");
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
  expect(researchAgents.resume).not.toHaveBeenCalled();
});
it("opens a stored proposal and leaves whether it still applies to the server", async () => {
  project = { goal: "Edited" }; render(<Harness />); fireEvent.click(screen.getByText("Open"));
  fireEvent.click(await screen.findByText("Použít návrh"));
  await waitFor(() => expect(reload).toHaveBeenCalledOnce());
  expect(researchAgents.design).not.toHaveBeenCalled();
  expect(researchAgents.accept).toHaveBeenCalledExactlyOnceWith("STU-1", "RUN-1", "REV-1", 3);
});

/** The inline review (ProposalReview's decisions), driven by name. */
function Inline() {
  const [error, setError] = useState("");
  const agents = useResearchAgents("STU-1", store, onUpdate, false, true);
  const review = agents.proposalReview;
  return <>
    <button onClick={() => { running = agents.run("analyze_brief", {}, "Brief").catch((e: Error) => setError(e.message)); }}>Run</button>
    {review ? <><p>{review.stale?.message ?? "fresh"}</p><p>{review.result.result.project.title as string}</p>
      <button onClick={() => review.decide("apply")}>Apply</button><button onClick={() => review.decide("dismiss")}>Dismiss</button>
      <button onClick={() => review.decide("rebuild")}>Rebuild</button></> : null}
    <p>{error}</p>
  </>;
}
const stale = new ApiError(409, "stale_proposal", "stale", null, { reason: "items_changed", conflicting_items: ["content:brief:goal"] });

it("dismisses a proposal in the ledger and writes nothing to the design", async () => {
  vi.mocked(researchAgents.dismiss).mockResolvedValue({ ...job, proposal_state: "dismissed" });
  render(<Inline />); fireEvent.click(screen.getByText("Run"));
  fireEvent.click(await screen.findByText("Dismiss"));
  await screen.findByText(/Návrh jste zahodili/);
  expect(researchAgents.dismiss).toHaveBeenCalledExactlyOnceWith("STU-1", "RUN-1");
  expect(researchAgents.accept).not.toHaveBeenCalled(); expect(reload).not.toHaveBeenCalled();
});

it("rebuilds a stale proposal on the current design and reviews the new one", async () => {
  const rebuilt: ResearchAgentJob = { ...job, run_id: "RUN-2", rebuild_of: "RUN-1" };
  vi.mocked(researchAgents.accept).mockRejectedValueOnce(stale).mockResolvedValue({ design_revision_id: "REV-3", workspace_revision: 5 } as Awaited<ReturnType<typeof researchAgents.accept>>);
  vi.mocked(researchAgents.rebuild).mockResolvedValue(rebuilt);
  vi.mocked(researchAgents.job).mockImplementation(async (_s, id) => (id === "RUN-2" ? rebuilt : job));
  vi.mocked(researchAgents.result).mockImplementation(async (_s, id) => (id === "RUN-2"
    ? { ...result, result: { ...result.result, project: { goal: "Original", title: "Rebuilt" } } } : result));
  render(<Inline />); fireEvent.click(screen.getByText("Run"));
  fireEvent.click(await screen.findByText("Apply"));
  // Refused by name: the review stays, saying why, and offers the rebuild.
  await screen.findByText(/mezitím se změnilo, co návrh mění – Cíl studie/);
  project = { ...project, goal: "Edited" };
  fireEvent.click(screen.getByText("Rebuild"));
  await screen.findByText("Rebuilt");
  expect(screen.getByText("fresh")).toBeTruthy();
  expect(research.submitDesign).toHaveBeenLastCalledWith("STU-1", { goal: "Edited" }, "brief", 3);
  expect(researchAgents.rebuild).toHaveBeenCalledExactlyOnceWith("STU-1", "RUN-1", "REV-1", undefined);
  fireEvent.click(screen.getByText("Apply"));
  await waitFor(() => expect(reload).toHaveBeenCalledOnce());
  expect(researchAgents.accept).toHaveBeenLastCalledWith("STU-1", "RUN-2", "REV-1", 3);
});

it("never drops an edit typed while the accept was on its way: the copy stops saving and says so", async () => {
  let commit = () => {};
  vi.mocked(researchAgents.accept).mockReturnValue(new Promise((resolve) => {
    commit = () => resolve({ design_revision_id: "REV-2", workspace_revision: 4 } as Awaited<ReturnType<typeof researchAgents.accept>>);
  }));
  render(<Harness />); fireEvent.click(screen.getByText("Run"));
  fireEvent.click(await screen.findByText("Použít návrh"));
  await waitFor(() => expect(researchAgents.accept).toHaveBeenCalledOnce());
  // The stage is still editable while the accept is in flight.
  act(() => { store.update(({ project: p }) => ({ project: { ...p, goal: "Typed during the accept" } })); });
  await act(async () => { commit(); await running; });
  // Not reloaded over: the edit stays on screen, the copy is held in conflict at the accepted
  // revision (nothing saves over it), and the person is told what to do.
  expect(reload).not.toHaveBeenCalled();
  expect(project.goal).toBe("Typed during the accept");
  expect(conflict).toHaveBeenCalledExactlyOnceWith(4);
  expect(screen.getByText(/Úpravu, kterou jste mezitím napsali, jsme nepřepsali/)).toBeTruthy();
});
