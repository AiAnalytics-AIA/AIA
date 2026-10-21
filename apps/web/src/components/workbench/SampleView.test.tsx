// @vitest-environment jsdom
// Vzorek (plan artifact-sample): what is set, read only, with the way to where it is set; the
// server's forecast labelled a forecast, and what it could not forecast unknown, never good.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Readiness } from "@/lib/api";
import type { ResearchProject } from "@/research/model";
import type { ResearchStore } from "@/research/store";
import { SampleArtifact } from "./SampleView";
import { loadSampleReadiness, type SampleReadiness } from "./useSampleReadiness";

afterEach(cleanup);

const project = (over: Partial<ResearchProject>): ResearchProject => ({
  briefing: {}, research_plan: {}, study_config: {}, instrument_library: {}, audience: {}, discovery: {}, budget: {}, run_policy: {}, ui_state: {}, sections: [],
  ...over,
});

const readiness = (over: Partial<Readiness>): Readiness => ({
  design_revision_id: "r7", rules: "aia-readiness-1", ready: true, checks: [], questions: 3, batteries: 0, objects: 0, n: 200,
  fieldwork_source: "ai_runtime", cost_ceiling_usd: null, cost_ceiling_unknown: null, fieldwork_requests: 0, analysis_calls: 0,
  spend_confirm_usd: null, confirmation_required: false, ...over,
});

const ready = (over: Partial<Readiness>): SampleReadiness => ({ kind: "ready", revision: 7, readiness: readiness(over) });

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
    fireEvent.click(screen.getByRole("button", { name: "Ověřit v Kontrole a spuštění" }));
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
    expect(screen.getByText("Podle revize návrhu 7")).toBeTruthy();
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

describe("loadSampleReadiness", () => {
  const store = (save: string) => ({ get: () => ({ save: { kind: save } }) }) as unknown as ResearchStore;

  it("reads an editor's readiness on the revision their working copy submits to", async () => {
    const read = vi.fn(async () => readiness({}));
    const s = await loadSampleReadiness(store("saved"), "s1", true, { submit: async () => ({ revision_id: "r7", revision: 7 }), revisions: vi.fn(), readiness: read });
    expect(s).toMatchObject({ kind: "ready", revision: 7 });
    expect(read).toHaveBeenCalledWith("s1", "r7");
  });

  it("reads a reader's on the latest revision and submits nothing", async () => {
    const submit = vi.fn();
    const s = await loadSampleReadiness(store("saved"), "s1", false, { submit, revisions: async () => [{ revision_id: "r3", revision: 3 }], readiness: async () => readiness({}) });
    expect(s).toMatchObject({ kind: "ready", revision: 3 });
    expect(submit).not.toHaveBeenCalled();
    expect(await loadSampleReadiness(store("saved"), "s1", false, { submit, revisions: async () => [], readiness: vi.fn() })).toEqual({ kind: "none" });
  });

  it("never reads readiness on a copy whose save was refused", async () => {
    const read = vi.fn();
    const s = await loadSampleReadiness(store("conflict"), "s1", true, { submit: async () => { throw new Error("409"); }, revisions: vi.fn(), readiness: read });
    expect(s.kind).toBe("failed");
    expect(read).not.toHaveBeenCalled();
  });
});
