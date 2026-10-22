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
    expect(screen.getAllByRole("alert").every((a) => a.textContent?.includes("500"))).toBe(true);
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
    const { container } = render(<SampleArtifact project={project({ n: 200 })} onOpen={onOpen} readiness={ready({ ready: false, checks })} />);
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

  it("shows a check the server names outside the id grammar, nameable by no one, without failing the render", () => {
    // A question with no text yet: domain/research_design.py names it `compile:<code>:<section>#<n>`.
    const { container } = render(<SampleArtifact project={project({ n: 200 })} onOpen={vi.fn()} readiness={ready({
      ready: false, checks: [{ id: "compile:question_without_text:S1#1", status: "FAIL", message: "Otázka nemá text." }],
    })} />);
    const row = screen.getByText("Otázka nemá text.").closest("li")!;
    expect(row.hasAttribute("data-aia")).toBe(false);
    fireEvent.click(row.querySelector("button")!);
    expect(container.querySelector('[data-aia^="sample:ready:compile"]')).toBeNull();
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

  it("takes the server's verdict: not ready with no FAIL still stops the run, and an unknown status allows no 'continue'", () => {
    render(<SampleArtifact project={project({ n: 200 })} onOpen={vi.fn()} readiness={ready({ ready: false, checks: [checks[0]] })} />);
    expect(screen.getByRole("region", { name: "Připravenost ke spuštění" }).textContent).toContain("server spuštění nepovolí");
    cleanup();
    render(<SampleArtifact project={project({ n: 200 })} onOpen={vi.fn()} readiness={ready({ checks: [checks[2], { id: "x", status: "SKIPPED" as never, message: "?" }] })} />);
    const section = screen.getByRole("region", { name: "Připravenost ke spuštění" });
    expect(section.textContent).toContain("stav některých kontrol neznámý");
    expect(section.textContent).not.toContain("Lze pokračovat");
  });

  it("names a panel run's unknown forecast as unknown here too, never as a warning", () => {
    render(<SampleArtifact project={project({ n: 200 })} onOpen={vi.fn()} readiness={ready({ persona_source: "panel", checks: [{ id: "support_forecast", status: "WARN", message: "Ukáže se až při výběru." }] })} />);
    const section = screen.getByRole("region", { name: "Připravenost ke spuštění" });
    expect(section.textContent).toContain("Opora výsledků je předem neznámá: viz oddíl 2.");
    expect(section.textContent).not.toContain("varuje");
  });

  it("says why the checks could not be read, as an alert", () => {
    render(<SampleArtifact project={project({})} onOpen={vi.fn()} readiness={{ kind: "failed", message: "Někdo uložil novější verzi." }} />);
    const alerts = screen.getAllByRole("alert").map((a) => a.textContent);
    expect(alerts).toContain("Kontroly se nepodařilo načíst: Někdo uložil novější verzi.");
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

  it("reads an editor's readiness on the working revision, saving a waiting change first and submitting nothing", async () => {
    const read = vi.fn(async () => readiness({}));
    const s7 = store("pending", 7);
    expect(await loadSampleReadiness(s7, "s1", true, { readiness: read })).toMatchObject({ kind: "ready", revision: 7 });
    expect(s7.flush).toHaveBeenCalledTimes(1);
    expect(read).toHaveBeenCalledWith("s1", 7);
    const saved = store("saved", 7);
    await loadSampleReadiness(saved, "s1", true, { readiness: read });
    expect(saved.flush).not.toHaveBeenCalled();
  });

  it("writes nothing for a new study nobody has touched: no revision, nothing read", async () => {
    const read = vi.fn();
    const fresh = store("new", null);
    expect(await loadSampleReadiness(fresh, "s1", true, { readiness: read })).toEqual({ kind: "none" });
    expect(fresh.flush).not.toHaveBeenCalled();
    expect(read).not.toHaveBeenCalled();
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

describe("Složení podle kvót", () => {
  const cells = Array.from({ length: 12 }, (_, i) => ({ key: `zena/k${i}`, values: ["žena", `kraj ${i}`], n: 12 - i }));
  const composition = { refused: null, version_id: "DSV-1", seed: 7, quota_fields: ["pohlavi", "kraj"], cells, sample_donors: 40 };

  it("lists a panel run's quota cells, largest first, each a target, the rest folded away", () => {
    const { container } = render(<SampleArtifact project={project({ n: 78 })} onOpen={vi.fn()} readiness={ready({ persona_source: "panel", sample_composition: composition })} />);
    const section = screen.getByRole("region", { name: "Velikost a složení" });
    expect(section.textContent).toContain("Podle: Pohlaví × Kraj. 12 buněk s respondenty, 40 různých dárců.");
    const rows = [...container.querySelectorAll('[data-aia^="sample:quota:"]')].map((r) => r.getAttribute("data-aia"));
    expect(rows).toHaveLength(12);
    expect(rows[0]).toBe("sample:quota:zena/k0");
    expect(container.querySelector('[data-aia="sample:quota:zena/k0"]')!.textContent).toContain("15,4 %");
    // Ten shown, two under "Dalších", nothing on the page to press but navigation.
    expect(section.querySelector("details")!.textContent).toContain("Dalších 2 buňky");
    expect(section.querySelectorAll("details tr[data-aia]")).toHaveLength(2);
  });

  it("says the sampler's refusal in words, unknown when nothing was drawn, and no quotas for the roster", () => {
    render(<SampleArtifact project={project({ n: 78 })} onOpen={vi.fn()} readiness={ready({ persona_source: "panel", sample_composition: { ...composition, refused: "sampling_empty", cells: [] } })} />);
    expect(screen.getByText(/Vzorek z populace teď nelze vybrat: Filtry nevyberou žádného člověka z populace\./)).toBeTruthy();
    cleanup();
    render(<SampleArtifact project={project({ n: 78 })} onOpen={vi.fn()} readiness={ready({ persona_source: "panel", sample_composition: null })} />);
    expect(screen.getByText(/Složení vzorku z populace: neznámé/)).toBeTruthy();
    cleanup();
    render(<SampleArtifact project={project({ n: 78 })} onOpen={vi.fn()} readiness={ready({ persona_source: "fictional_roster" })} />);
    expect(screen.getByText("Fiktivní respondenti se nevybírají podle kvót.")).toBeTruthy();
  });
});
