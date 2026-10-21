// @vitest-environment jsdom
// Dotazník's Lead targets (the contract, lib/workbench-artifacts.ts): every block, tracked set and
// question carries data-aia "<kind>:<id>" by its stored id, and an item without a valid id none.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { targetOfElement } from "@/lib/lead";
import { parseAiaId } from "@/lib/workbench-artifacts";
import { NATIVE_TEST_TIMEOUT_MS, nativeAgentFixture } from "./test-native-agents";
import { ResearchScreen } from "./ResearchScreen";
import { workspaceFixture } from "./test-workspace";
import { TEST_FRAME } from "./test-frame";

vi.setConfig({ testTimeout: NATIVE_TEST_TIMEOUT_MS });
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/questionnaire", useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const SECTIONS = [
  { id: "sec_a", type: "questions", title: "Hlavní otázky", questions: [
    { id: "Q1", text: "Jak často?", typ: "vyber", kategorie: ["Denně", "Týdně"] },
    { id: "Q 2", text: "Mezera v id?", typ: "otevrena" },
  ] },
  { type: "questions", title: "Bez id", questions: [{ text: "Bez id?", typ: "otevrena" }] },
  { id: "sec_b", type: "object_battery", title: "Média", object_type: "média", objects: ["TV", "Rádio", "Web", "Tisk"] },
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

describe("Dotazník's Lead targets", () => {
  it("marks each block, set and question by its stored id, and nothing without a valid one", async () => {
    stub({ goal: "G", sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    const { container } = render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findAllByDisplayValue("Jak často?");
    const marked = [...container.querySelectorAll("[data-aia]")].map((el) => el.getAttribute("data-aia")!).filter((v) => /^(section|question):/.test(v));
    expect(marked).toEqual(["section:sec_a", "question:Q1", "section:sec_b"]);
    for (const m of marked) expect(parseAiaId(m)?.stage).toBe("questionnaire");
    // The Lead's pointing reads the mark from anywhere inside the card.
    const field = container.querySelector('[data-aia="question:Q1"] textarea');
    expect(targetOfElement(field)?.id).toBe("question:Q1");
    // Named by what the person reads: a question's wording, a block's or set's title, never a legend.
    expect(targetOfElement(field)?.label).toBe("Otázka Q1: Jak často?");
    expect(targetOfElement(container.querySelector('[data-aia="section:sec_a"] input'))?.label).toBe("Oddíl: Hlavní otázky");
    expect(targetOfElement(container.querySelector('[data-aia="section:sec_b"] input'))?.label).toBe("Oddíl: Média");
    expect(targetOfElement(container.querySelector('[data-aia="section:sec_b"] input'))?.id).toBe("section:sec_b");
  });
});
