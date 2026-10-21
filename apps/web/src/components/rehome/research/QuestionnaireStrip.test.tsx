// @vitest-environment jsdom
// Dotazník's strip (artifact-questionnaire QST2): items, coverage per research question.
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NATIVE_TEST_TIMEOUT_MS, nativeAgentFixture } from "./test-native-agents";
import { ResearchScreen } from "./ResearchScreen";
import { workspaceFixture } from "./test-workspace";
import { TEST_FRAME } from "./test-frame";

vi.setConfig({ testTimeout: NATIVE_TEST_TIMEOUT_MS });
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/questionnaire", useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const RQ1 = "Jak často lidé dojíždějí?";
const RQ2 = "Která varianta osloví?";
const plan = { research_plan: { research_questions: [RQ1, RQ2] } };
const sections = (links: boolean) => [
  { id: "sec_a", type: "questions", title: "Hlavní", questions: [{ id: "Q1", text: "Jak často?", typ: "vyber", kategorie: ["Denně", "Týdně"], ...(links ? { research_questions: [RQ1] } : {}) }] },
  { id: "sec_b", type: "object_battery", title: "Varianty", object_type: "varianta", objects: ["A", "B", "C", "D"] },
];

function stub(project: Record<string, unknown>) {
  const ws = workspaceFixture(project, { analysis: null });
  const native = nativeAgentFixture(() => ({ project: {}, proposal: {} }), {}, ws.write);
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const path = String(url).split("?")[0];
    const body = init?.body ? JSON.parse(String(init.body)) : null;
    const answer = native(path, init?.method ?? "GET", body) ?? ws.answer(path, init?.method ?? "GET", body);
    if (answer === undefined) return new Response(JSON.stringify({ code: "not_found", message: "No such resource." }), { status: 404 });
    return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
  }));
}

beforeEach(() => {
  Element.prototype.scrollIntoView = () => {};
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Dotazník's strip", () => {
  it("marks a research question no item measures as a gap", async () => {
    stub({ goal: "G", ...plan, sections: sections(true), ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    const strip = await screen.findByRole("region", { name: "Dotazník v číslech" });
    expect(within(strip).getByText("5 položek pro respondenty")).toBeTruthy();
    expect(within(strip).getByText("Délka zatím neodhadnuta")).toBeTruthy();
    const pills = within(within(strip).getByRole("list", { name: "Pokrytí výzkumných otázek" })).getAllByRole("listitem");
    expect(pills.map((p) => p.getAttribute("title"))).toEqual([`VO1: ${RQ1} · měří 1`, `VO2: ${RQ2} · žádná položka ji neměří`]);
  });

  it("says coverage is unknown, not a gap, while no item declares a link", async () => {
    stub({ goal: "G", ...plan, sections: sections(false), ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    const strip = await screen.findByRole("region", { name: "Dotazník v číslech" });
    expect(within(strip).queryByRole("list")).toBeNull();
    expect(within(strip).getByText(/Pokrytí neznámé/)).toBeTruthy();
  });
});
