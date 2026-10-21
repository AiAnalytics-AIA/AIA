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

beforeEach(() => {
  vi.resetAllMocks();
  project = { title: "Studie" };
  revision = 12;
  flush = vi.fn().mockResolvedValue(undefined);
  // The server wrote the working copy: a reload reads what it wrote.
  reload = vi.fn().mockImplementation(async () => {
    project = { ...project, design_research: { contract_version: "aia-design-research-proposal-1", items: { [A]: { provenance: { run_id: "DR-1" } } } } };
    revision = 13;
    return true;
  });
  store = { flush, reload, get: () => ({ project, analysis: null, revision, save: { kind: "saved" } }) } as unknown as typeof store;
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

  it("is read only where the person may not accept", async () => {
    await show(false);
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
    expect(screen.queryByRole("button", { name: /Přijmout vybrané/ })).toBeNull();
    expect(screen.getByText("Většina pije denně")).toBeTruthy();
  });
});
