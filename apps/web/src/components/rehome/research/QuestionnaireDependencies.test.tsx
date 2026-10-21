// @vitest-environment jsdom
// Závislosti on Dotazník (artifact-questionnaire QST8): what reads each set and question.
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NATIVE_TEST_TIMEOUT_MS, nativeAgentFixture } from "./test-native-agents";
import { ResearchScreen } from "./ResearchScreen";
import { workspaceFixture } from "./test-workspace";
import { TEST_FRAME, stagePath } from "./test-frame";

vi.setConfig({ testTimeout: NATIVE_TEST_TIMEOUT_MS });
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/questionnaire", useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const SECTIONS = [
  { id: "sec_a", type: "questions", title: "Hlavní otázky", questions: [
    { id: "Q1", text: "Jak často?", typ: "vyber", kategorie: ["Denně", "Týdně"] },
    { id: "Q2", text: "Jak se dnes cítíte?", typ: "skala", skala: [1, 10], sociomap_rating: true },
    { id: "Q3", text: "Proč?", typ: "otevrena" },
    { id: "Q4", text: "Komu?", typ: "vyber", kategorie: ["A", "B"], filtr: "Q1 = Denně" },
  ] },
  { id: "sec_b", type: "object_battery", title: "Média", object_type: "média", objects: ["TV", "Rádio", "Web", "Tisk"], context_objects: ["Tisk"] },
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

describe("Dotazník's Závislosti", () => {
  it("lists Sociomapa for a set and a declared rating item, and nothing for a held question", async () => {
    stub({ goal: "Zjistit zájem", sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    const deps = await screen.findByRole("region", { name: "Závislosti" });
    const row = (name: RegExp) => within(deps).getByRole("link", { name }).closest("li") as HTMLElement;

    const set = row(/^Sada 1 Média$/);
    expect(within(set).getByRole("link", { name: "Sociomapa" }).getAttribute("href")).toBe(`${stagePath("results")}#maps`);
    expect(within(set).getByText("Kontextové položky (Tisk): v mapě, ale mimo hlavní skóre.")).toBeTruthy();
    expect(within(deps).getByRole("link", { name: /^Sada 1/ }).getAttribute("href")).toBe("#qset_sec_b");

    expect(within(row(/^Q2 /)).getByRole("link", { name: "Sociomapa" })).toBeTruthy();
    const open = row(/^Q3 /);
    expect(within(open).queryByRole("link", { name: "Analýza" })).toBeNull();
    expect(within(open).getByText(/data, ne připuštěná evidence/)).toBeTruthy();
    const held = row(/^Q4 /);
    expect(within(held).queryAllByRole("link")).toHaveLength(1);
    expect(within(held).getByText(/běh ji odmítne/)).toBeTruthy();

    const closed = within(deps).getByText("1 uzavřená otázka (Q1)").closest("li") as HTMLElement;
    expect(within(closed).getAllByRole("link").map((a) => a.textContent)).toEqual(["Sběr dat", "Výsledky", "Analýza", "Zpráva"]);
  });
});
