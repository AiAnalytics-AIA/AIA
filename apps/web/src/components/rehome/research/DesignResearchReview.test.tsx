// @vitest-environment jsdom
// A Design Research proposal reviewed in the artifact (research-lead-workbench 7b, F-DRL-1): a person
// ticks findings and accepts; the server writes; the working copy is read again; a stale proposal is said.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, deepResearch, type DesignProposal } from "@/lib/api";
import type { ResearchStore } from "@/research/store";

import { ACCEPT_LABEL, DesignResearchReview, REVIEW_LABEL } from "./DesignResearchReview";

vi.mock("@/lib/api", async () => ({
  ApiError: (await vi.importActual<typeof import("@/lib/api")>("@/lib/api")).ApiError,
  deepResearch: { designProposal: vi.fn(), acceptDesignProposal: vi.fn() },
}));

const A = "DRP-aaaaaaaaaaaaaaaaaaaaaaaa";
const B = "DRP-bbbbbbbbbbbbbbbbbbbbbbbb";
const G = "DRP-cccccccccccccccccccccccc";
const finding = (id: string, claim: string) => ({ evidence_id: id, claim, quote: `citace ${id}`, source_title: `Zdroj ${id}`, source: `https://example.org/${id}`, source_class: "B", confidence: 0.7 });
const PROPOSAL: DesignProposal = {
  run_id: "DR-1", design_revision_id: "REV-7", design_revision: 7, admissible: true, refusal: null,
  items: [
    { item_id: A, kind: "EVIDENCE", subject_key: "q-a", subject_kind: "QUESTION", subject_text: "Jak často lidé pijí kávu?", subject_origin: "rq[0]", findings: [finding("EV-1", "Většina pije denně")] },
    { item_id: B, kind: "EVIDENCE", subject_key: "o-b", subject_kind: "OBJECT", subject_text: "Značka B", subject_origin: "set[0]", findings: [finding("EV-2", "Značka B roste")] },
    { item_id: G, kind: "GAP", subject_key: "q-g", subject_kind: "QUESTION", subject_text: "Proč nepijí čaj?", subject_origin: "rq[1]", findings: [] },
  ],
};

let project: Record<string, unknown>;
let revision: number;
let store: Pick<ResearchStore, "flush" | "get" | "reload">;
let flush: ReturnType<typeof vi.fn>;
let reload: ReturnType<typeof vi.fn>;
/** The copy's save state, as ResearchStore keeps it: a change waits ("pending") until a flush saves it. */
let saveKind: "saved" | "pending";

beforeEach(() => {
  vi.resetAllMocks();
  project = { title: "Studie" };
  revision = 11;
  saveKind = "pending";
  // One save of what the copy held: it is now stored at the next revision.
  flush = vi.fn().mockImplementation(async () => { revision += 1; saveKind = "saved"; });
  // The server wrote the working copy from what was saved: a reload reads it, unless the copy moved
  // since (store.reload's `since`), when it keeps the copy as it is.
  reload = vi.fn().mockImplementation(async (_read: unknown, { since }: { since: { project: unknown } }) => {
    if (since.project !== project) return false;
    project = { ...project, design_research: { contract_version: "aia-design-research-proposal-1", items: { [A]: { provenance: { run_id: "DR-1" } } } } };
    revision += 1;
    return true;
  });
  store = { flush, reload, get: () => ({ project, analysis: null, revision, save: { kind: saveKind } }) } as unknown as typeof store;
  vi.mocked(deepResearch.designProposal).mockResolvedValue(PROPOSAL);
  vi.mocked(deepResearch.acceptDesignProposal).mockResolvedValue({ revision_id: "REV-8", workspace_revision: 13 } as Awaited<ReturnType<typeof deepResearch.acceptDesignProposal>>);
});
afterEach(() => cleanup());

const show = async (canApply = true) => {
  const view = render(<DesignResearchReview studyId="STU-1" runId="DR-1" store={store} project={project} canApply={canApply} />);
  fireEvent.click(await screen.findByRole("button", { name: REVIEW_LABEL }));
  return view;
};
const box = (subject: string) => screen.getByRole("checkbox", { name: new RegExp(subject) });

describe("a Design Research proposal, reviewed in the artifact", () => {
  it("writes nothing until the person accepts, and a GAP item has no checkbox", async () => {
    await show();
    expect(screen.getAllByRole("checkbox")).toHaveLength(2);
    expect(screen.getByText("Proč nepijí čaj?")).toBeTruthy();
    expect(screen.getByText(/Výzkum k tomu nic nenašel/)).toBeTruthy();
    // The findings are shown with their quotes and sources.
    expect(screen.getByText("citace EV-1")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Zdroj EV-1" }).getAttribute("href")).toBe("https://example.org/EV-1");
    expect((screen.getByRole("button", { name: ACCEPT_LABEL }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Ponechat současný návrh" }));
    expect(deepResearch.acceptDesignProposal).not.toHaveBeenCalled();
    expect(flush).not.toHaveBeenCalled();
  });

  it("posts exactly the ticked items on both revisions, then reloads the working copy from what it held", async () => {
    await show();
    fireEvent.click(box("Jak často"));
    fireEvent.click(box("Značka B"));
    fireEvent.click(box("Značka B")); // untick: dismissed, never sent
    fireEvent.click(screen.getByRole("button", { name: `${ACCEPT_LABEL} (1)` }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("Přijato do návrhu: 1 položka"));
    expect(flush).toHaveBeenCalledOnce();
    expect(deepResearch.acceptDesignProposal).toHaveBeenCalledWith("STU-1", "DR-1", [A], "REV-7", 12);
    // The browser writes nothing back: it reads what the server wrote, keeping a change typed meanwhile.
    expect(reload).toHaveBeenCalledWith(undefined, { since: expect.objectContaining({ project: expect.anything() }) });
  });

  it("says a stale proposal by name and never applies it", async () => {
    vi.mocked(deepResearch.acceptDesignProposal).mockRejectedValue(
      new ApiError(409, "stale_proposal", "stale", null, { reason: "items_changed", conflicting_items: ["content:field:design_research"] }),
    );
    await show();
    fireEvent.click(box("Jak často"));
    fireEvent.click(screen.getByRole("button", { name: `${ACCEPT_LABEL} (1)` }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe("Návrh nejde použít: mezitím se změnilo, co návrh mění – Podklady z hloubkového výzkumu. Vaše úpravy zůstávají; návrh připravte znovu nad současným zadáním.");
    expect(reload).not.toHaveBeenCalled();
    expect((screen.getByRole("button", { name: /Přijmout vybrané/ }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("keeps the person's typed change when it moved under the accept, and says so", async () => {
    reload.mockResolvedValue(false);
    await show();
    fireEvent.click(box("Jak často"));
    fireEvent.click(screen.getByRole("button", { name: `${ACCEPT_LABEL} (1)` }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("jsme nepřepsali ani neuložili"));
  });

  it("offers no further accept from a run whose items the working copy already took", async () => {
    project = { design_research: { contract_version: "aia-design-research-proposal-1", items: { [A]: { provenance: { run_id: "DR-1" } } } } };
    await show();
    expect(screen.getByText("V návrhu")).toBeTruthy();
    expect((box("Jak často") as HTMLInputElement).checked).toBe(true);
    expect((box("Značka B") as HTMLInputElement).disabled).toBe(true);
    expect(screen.getByText(/Z tohoto běhu už jsou podklady v návrhu/)).toBeTruthy();
  });

  it("saves an edit typed during the save before it accepts, so the accept keeps it", async () => {
    // The first save is of the copy before the edit; the edit, typed while it was in flight, stays pending.
    flush.mockImplementationOnce(async () => {
      project = { ...project, goal: "Typed while saving" };
      revision += 1; // 12: the copy without the edit
      saveKind = "pending";
    });
    await show();
    fireEvent.click(box("Jak často"));
    fireEvent.click(screen.getByRole("button", { name: `${ACCEPT_LABEL} (1)` }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("Přijato do návrhu: 1 položka"));
    // Flushed again until saved: the accept names the revision that holds the edit, never the one before.
    expect(flush).toHaveBeenCalledTimes(2);
    expect(deepResearch.acceptDesignProposal).toHaveBeenCalledWith("STU-1", "DR-1", [A], "REV-7", 13);
    // The working copy read back from the server still has it.
    expect(project.goal).toBe("Typed while saving");
    expect(project.design_research).toBeTruthy();
  });

  it("never posts while the copy still has an unsaved edit", async () => {
    flush.mockImplementation(async () => { revision += 1; saveKind = "pending"; });
    await show();
    fireEvent.click(box("Jak často"));
    fireEvent.click(screen.getByRole("button", { name: `${ACCEPT_LABEL} (1)` }));
    expect((await screen.findByRole("alert")).textContent).toContain("se ještě ukládá");
    expect(deepResearch.acceptDesignProposal).not.toHaveBeenCalled();
    expect(reload).not.toHaveBeenCalled();
  });

  it("never shows, ticks or sends one run's items for another after the run changes", async () => {
    const D = "DRP-dddddddddddddddddddddddd";
    const second: DesignProposal = { ...PROPOSAL, run_id: "DR-2", design_revision_id: "REV-9", items: [{ ...PROPOSAL.items[0], item_id: D, subject_text: "Druhý běh: kdo kupuje?" }] };
    let answer: (p: DesignProposal) => void = () => {};
    const view = await show();
    fireEvent.click(box("Jak často"));
    vi.mocked(deepResearch.designProposal).mockImplementationOnce(() => new Promise((r) => { answer = r; }));
    view.rerender(<DesignResearchReview studyId="STU-1" runId="DR-2" store={store} project={project} canApply />);
    // DR-2's proposal has not come yet: nothing of DR-1 is offered under DR-2's name.
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
    expect(screen.queryByRole("button", { name: /Přijmout vybrané/ })).toBeNull();
    answer(second);
    const button = await screen.findByRole("button", { name: /Zkontrolovat návrh|Zavřít/ });
    if (button.textContent === REVIEW_LABEL) fireEvent.click(button);
    // The tick on DR-1 did not travel: DR-2 starts with nothing chosen.
    expect((box("Druhý běh") as HTMLInputElement).checked).toBe(false);
    fireEvent.click(box("Druhý běh"));
    fireEvent.click(screen.getByRole("button", { name: `${ACCEPT_LABEL} (1)` }));
    await waitFor(() => expect(deepResearch.acceptDesignProposal).toHaveBeenCalledOnce());
    expect(deepResearch.acceptDesignProposal).toHaveBeenCalledWith("STU-1", "DR-2", [D], "REV-9", 12);
  });

  it("offers a loaded proposal only under the run it belongs to", async () => {
    // The state the one render after a switch holds: a proposal of DR-1 while the component is DR-2's.
    vi.mocked(deepResearch.designProposal).mockResolvedValue(PROPOSAL);
    render(<DesignResearchReview studyId="STU-1" runId="DR-2" store={store} project={project} canApply />);
    await waitFor(() => expect(deepResearch.designProposal).toHaveBeenCalledWith("STU-1", "DR-2"));
    await Promise.resolve();
    expect(screen.queryByRole("button", { name: REVIEW_LABEL })).toBeNull();
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
    expect(document.querySelector("[data-design-research-review]")).toBeNull();
  });

  it("is read only where the person may not accept", async () => {
    await show(false);
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
    expect(screen.queryByRole("button", { name: /Přijmout vybrané/ })).toBeNull();
    expect(screen.getByText("Většina pije denně")).toBeTruthy();
  });
});
