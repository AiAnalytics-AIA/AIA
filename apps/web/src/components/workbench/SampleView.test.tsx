// @vitest-environment jsdom
// Vzorek (plan artifact-sample): what is set, read only, with the way to where it is set; the
// server's forecast labelled a forecast, and what it could not forecast unknown, never good.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { WorkingReadiness } from "@/lib/api";
import type { ResearchProject } from "@/research/model";
import type { ResearchStore } from "@/research/store";
import { SampleArtifact } from "./SampleView";
import { loadSampleReadiness, type SampleReadiness } from "./useSampleReadiness";

afterEach(cleanup);

const project = (over: Partial<ResearchProject>): ResearchProject => ({
  briefing: {}, research_plan: {}, study_config: {}, instrument_library: {}, audience: {}, discovery: {}, budget: {}, run_policy: {}, ui_state: {}, sections: [],
  ...over,
});

const readiness = (over: Partial<WorkingReadiness>): WorkingReadiness => ({
  working_revision: 7, rules: "aia-readiness-1", ready: true, checks: [], questions: 3, batteries: 0, objects: 0, n: 200,
  fieldwork_source: "ai_runtime", cost_ceiling_usd: null, cost_ceiling_unknown: null, fieldwork_requests: 0, analysis_calls: 0,
  spend_confirm_usd: null, confirmation_required: false, ...over,
});

const ready = (over: Partial<WorkingReadiness>): SampleReadiness => ({ kind: "ready", revision: 7, readiness: readiness(over) });

describe("SampleArtifact", () => {
  it("shows the size, the audience and the dimensions as set, and edits none of them", () => {
    const onOpen = vi.fn();
    render(<SampleArtifact project={project({ n: 450, persona_dimensions: { approved: ["media", "cena"] }, audience: { description: "Dojíždějící", filters: { kraj: ["A"], vek: { min: 25 } } } })} readiness={{ kind: "loading" }} onOpen={onOpen} />);
    expect(screen.getByText("N = 450")).toBeTruthy();
    expect(screen.getByText("Dojíždějící · 2 filtry")).toBeTruthy();
    expect(screen.getByText("Média a informační chování")).toBeTruthy();
    expect(screen.queryByRole("textbox")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Upravit v Dimenzích" }));
    fireEvent.click(screen.getByRole("button", { name: "Sociomapa" }));
    fireEvent.click(screen.getByRole("button", { name: "Pokračovat na Sběr dat" }));
    expect(onOpen.mock.calls).toEqual([["dimensions"], ["sociomap"], ["fieldwork"]]);
  });

  it("says what is not set, rather than a default", () => {
    render(<SampleArtifact project={project({})} readiness={{ kind: "loading" }} onOpen={vi.fn()} />);
    expect(screen.getByText("Nenastaveno")).toBeTruthy();
    expect(screen.getByText("Bez popisu")).toBeTruthy();
  });

  it("labels the server's forecast a forecast, with the revision it was read on", () => {
    render(<SampleArtifact project={project({ n: 200 })} onOpen={vi.fn()} readiness={ready({
      persona_source: "fictional_roster",
      checks: [{ id: "support_forecast", status: "PASS", message: "Běh bude mít 67 různých dárců na 200 respondentů: opora stačí." }],
      question_outlook: [{ question_id: "q1", text: "", section_id: "s", battery_id: null, verdict: "AT_RISK", reasons: [] }],
    })} />);
    expect(screen.getByText("odhad, ne výsledek")).toBeTruthy();
    expect(screen.getByText("Podle pracovní kopie, revize 7")).toBeTruthy();
    expect(screen.getByText("Opora výsledků")).toBeTruthy();
    expect(screen.getByText("Běh bude mít 67 různých dárců na 200 respondentů: opora stačí.")).toBeTruthy();
    expect(screen.getByRole("region", { name: "Odhad podpory před během" }).querySelector('[data-aia="sample:forecast:outlook"]')?.textContent).toContain("1 S rizikem");
  });

  it("reads a panel run's unknown forecast as neznámé, never good", () => {
    const { container } = render(<SampleArtifact project={project({ n: 200 })} onOpen={vi.fn()} readiness={ready({
      persona_source: "panel",
      checks: [{ id: "support_forecast", status: "WARN", message: "Kolik různých dárců běh bude mít, se ukáže až při výběru respondentů z populace." }],
    })} />);
    expect(screen.getByText("Opora výsledků: neznámé")).toBeTruthy();
    expect(screen.getByText("Na co běh odpoví: neznámé")).toBeTruthy();
    expect(container.querySelector('[data-aia="sample:forecast:support"] [aria-label="neznámé"]')).toBeTruthy();
  });

  it("says when there is no revision to forecast on, and when the read failed", () => {
    render(<SampleArtifact project={project({})} onOpen={vi.fn()} readiness={{ kind: "none" }} />);
    expect(screen.getByText(/Odhad je neznámý/)).toBeTruthy();
    cleanup();
    render(<SampleArtifact project={project({})} onOpen={vi.fn()} readiness={{ kind: "failed", message: "500" }} />);
    expect(screen.getByRole("alert").textContent).toContain("500");
  });
});

describe("Připravenost ke spuštění", () => {
  const checks = [
    { id: "sample_size", status: "PASS" as const, message: "n = 200." },
    { id: "conditional_questions", status: "FAIL" as const, message: "Podmíněnou otázku AIA neumí položit." },
    { id: "sociomap_support", status: "WARN" as const, message: "n je pod 30 na pár." },
    { id: "new_server_check", status: "WARN" as const, message: "Něco nového." },
  ];

  it("lists every check worst first; a FAIL names its stage and opens it", () => {
    const onOpen = vi.fn();
    const { container } = render(<SampleArtifact project={project({ n: 200 })} onOpen={onOpen} readiness={ready({ checks })} />);
    const section = screen.getByRole("region", { name: "Připravenost ke spuštění" });
    expect(section.textContent).toContain("1 kontrola brání spuštění");
    const items = [...section.querySelectorAll("li")].map((li) => li.getAttribute("data-aia"));
    expect(items).toEqual(["sample:ready:conditional_questions", "sample:ready:sociomap_support", "sample:ready:new_server_check", "sample:ready:sample_size"]);
    const fail = container.querySelector('[data-aia="sample:ready:conditional_questions"]')!;
    fireEvent.click(fail.querySelector("button")!);
    expect(onOpen).toHaveBeenCalledWith("questionnaire");
    // n's support is fixed where n is set; a check this client does not know names no stage.
    expect(container.querySelector('[data-aia="sample:ready:sociomap_support"] button')?.textContent).toBe("Dimenze");
    expect(container.querySelector('[data-aia="sample:ready:new_server_check"] button')).toBeNull();
    expect(section.textContent).not.toContain("Lze pokračovat s omezeními");
  });

  it("shows the support forecast in section 2 only, counted and named here when it warns", () => {
    render(<SampleArtifact project={project({ n: 50 })} onOpen={vi.fn()} readiness={ready({ checks: [{ id: "support_forecast", status: "WARN", message: "Čísla budou potlačená." }] })} />);
    const section = screen.getByRole("region", { name: "Připravenost ke spuštění" });
    expect(section.querySelector('[data-aia="sample:ready:support_forecast"]')).toBeNull();
    expect(section.textContent).toContain("1 varování, nic nebrání");
    expect(section.textContent).toContain("viz oddíl 2");
    expect(screen.getAllByText("Čísla budou potlačená.")).toHaveLength(1);
  });

  it("says a run with only warnings may continue with limits", () => {
    render(<SampleArtifact project={project({ n: 200 })} onOpen={vi.fn()} readiness={ready({ checks: checks.filter((c) => c.status !== "FAIL") })} />);
    const section = screen.getByRole("region", { name: "Připravenost ke spuštění" });
    expect(section.textContent).toContain("2 varování, nic nebrání");
    expect(section.textContent).toContain("Lze pokračovat s omezeními.");
  });

  it("says when nothing was checked, never that nothing stops the run", () => {
    render(<SampleArtifact project={project({})} onOpen={vi.fn()} readiness={{ kind: "none" }} />);
    const section = screen.getByRole("region", { name: "Připravenost ke spuštění" });
    expect(section.textContent).toContain("kontroly neproběhly");
    expect(section.textContent).not.toContain("nic nebrání");
  });
});

describe("Kdo bude odpovídat", () => {
  const sources = [
    { source: "fictional_roster", offered: true, reason: null, default: true },
    { source: "panel", offered: false, reason: "panel_personas_disabled", default: false },
  ];

  it("shows the offered sources and the default, sets none of them, and opens Spuštění to change it", () => {
    const onOpen = vi.fn();
    render(<SampleArtifact project={project({ n: 200 })} onOpen={onOpen} readiness={ready({ persona_sources: sources })} />);
    const section = screen.getByRole("region", { name: "Kdo bude odpovídat" });
    expect(section.textContent).toContain("Fiktivní respondenti · výchozí");
    expect(section.querySelectorAll("input, select").length).toBe(0);
    expect(screen.queryByRole("radio")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Změnit ve Spuštění" }));
    expect(onOpen).toHaveBeenCalledWith("fieldwork");
  });

  it("names an unoffered source with the server's reason", () => {
    const { container } = render(<SampleArtifact project={project({ n: 200 })} onOpen={vi.fn()} readiness={ready({ persona_sources: sources })} />);
    const panel = container.querySelector('[data-aia="sample:respondents:panel"]');
    expect(panel?.textContent).toContain("AI respondenti z populace · nenabízeno");
    expect(panel?.textContent).toContain("Toto nasazení odpovědi z populace zatím nenabízí.");
  });

  it("sends no one to Spuštění for a choice it does not offer: a run not answered by AI respondents", () => {
    render(<SampleArtifact project={project({ n: 200 })} onOpen={vi.fn()} readiness={ready({ fieldwork_source: "synthetic_fixture", persona_sources: sources })} />);
    const section = screen.getByRole("region", { name: "Kdo bude odpovídat" });
    expect(section.textContent).toContain("nesbírá data přes AI respondenty");
    expect(screen.queryByRole("button", { name: "Změnit ve Spuštění" })).toBeNull();
  });

  it("says unknown when the server sent no sources, never a default", () => {
    render(<SampleArtifact project={project({ n: 200 })} onOpen={vi.fn()} readiness={ready({})} />);
    expect(screen.getByText(/zdroje respondentů nevrátil: neznámé/)).toBeTruthy();
    expect(screen.getByRole("region", { name: "Kdo bude odpovídat" }).textContent).not.toContain("výchozí");
  });
});

describe("loadSampleReadiness", () => {
  // A store at a working revision; flush resolves, or rejects as a refused save does.
  const store = (save: string, revision: number | null, flush: () => Promise<void> = async () => {}) =>
    ({ get: () => ({ save: { kind: save }, revision }), flush: vi.fn(flush) }) as unknown as ResearchStore & { flush: ReturnType<typeof vi.fn> };

  it("reads an editor's readiness on the working revision, saving what waits first and submitting nothing", async () => {
    const read = vi.fn(async () => readiness({}));
    const s7 = store("saved", 7);
    expect(await loadSampleReadiness(s7, "s1", true, { readiness: read })).toMatchObject({ kind: "ready", revision: 7 });
    expect(s7.flush).toHaveBeenCalledTimes(1);
    expect(read).toHaveBeenCalledWith("s1", 7);
  });

  it("reads a reader's on the revision loaded, saving nothing", async () => {
    const s3 = store("readonly", 3);
    expect(await loadSampleReadiness(s3, "s1", false, { readiness: async () => readiness({}) })).toMatchObject({ kind: "ready", revision: 3 });
    expect(s3.flush).not.toHaveBeenCalled();
    expect(await loadSampleReadiness(store("readonly", null), "s1", false, { readiness: vi.fn() })).toEqual({ kind: "none" });
  });

  it("never reads readiness on a copy whose save was refused", async () => {
    const read = vi.fn();
    const s = await loadSampleReadiness(store("conflict", 4, async () => { throw new Error("409"); }), "s1", true, { readiness: read });
    expect(s.kind).toBe("failed");
    expect(read).not.toHaveBeenCalled();
  });
});
