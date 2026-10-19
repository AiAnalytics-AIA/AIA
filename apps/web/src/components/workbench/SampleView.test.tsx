// @vitest-environment jsdom
// Vzorek (research-lead-workbench D2): what is set, read only, with the way to where it is set.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ResearchProject } from "@/research/model";
import { SampleView } from "./SampleView";

afterEach(cleanup);

const project = (over: Partial<ResearchProject>): ResearchProject => ({
  briefing: {}, research_plan: {}, study_config: {}, instrument_library: {}, audience: {}, discovery: {}, budget: {}, run_policy: {}, ui_state: {}, sections: [],
  ...over,
});

describe("SampleView", () => {
  it("shows the size, the audience and the dimensions as set, and edits none of them", () => {
    const onOpen = vi.fn();
    render(<SampleView project={project({ n: 450, persona_dimensions: { approved: ["media", "cena"] }, audience: { description: "Dojíždějící", filters: { kraj: ["A"], vek: { min: 25 } } } })} onOpen={onOpen} />);
    expect(screen.getByText("N = 450")).toBeTruthy();
    expect(screen.getByText("Dojíždějící · 2 filtry")).toBeTruthy();
    expect(screen.getByText("Média a informační chování")).toBeTruthy();
    expect(screen.queryByRole("textbox")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Upravit v Dimenzích" }));
    fireEvent.click(screen.getByRole("button", { name: "Ověřit v Kontrole a spuštění" }));
    expect(onOpen.mock.calls).toEqual([["dimensions"], ["fieldwork"]]);
  });

  it("says what is not set, rather than a default", () => {
    render(<SampleView project={project({})} onOpen={vi.fn()} />);
    expect(screen.getByText("Nenastaveno")).toBeTruthy();
    expect(screen.getByText("Bez popisu")).toBeTruthy();
  });
});
