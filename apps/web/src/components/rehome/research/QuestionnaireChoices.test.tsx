// @vitest-environment jsdom
// Dotazník's choices as chips (input-interactions chunk 3, audit A2, A11): one Tab stop, arrows choose.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NATIVE_TEST_TIMEOUT_MS, nativeAgentFixture } from "./test-native-agents";
import { ResearchScreen } from "./ResearchScreen";
import { workspaceFixture } from "./test-workspace";
import { TEST_FRAME } from "./test-frame";

vi.setConfig({ testTimeout: NATIVE_TEST_TIMEOUT_MS });
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/questionnaire", useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const SECTIONS = [
  { id: "sec_a", type: "questions", title: "Hlavní otázky", questions: [
    { id: "Q1", text: "Jak často?", typ: "vyber", kategorie: ["Denně", "Týdně"] },
    { id: "Q2", text: "Kde nakupujete?", typ: "vyber", kategorie: ["Obchod", "Web"] },
  ] },
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
  return ws;
}


beforeEach(() => {
  Element.prototype.scrollIntoView = () => {};
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Dotazník's choices", () => {
  it("chooses a question's type with the arrows, one Tab stop for the group", async () => {
    const ws = stub({ goal: "G", sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    const { container } = render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findAllByDisplayValue("Jak často?");
    const group = within(container.querySelector("#qedit_Q1") as HTMLElement).getByRole("radiogroup", { name: "Typ" });
    const radios = within(group).getAllByRole("radio");
    expect(radios.map((r) => r.tabIndex)).toEqual([0, -1, -1, -1]);
    fireEvent.keyDown(radios[0]!, { key: "ArrowRight" });
    await waitFor(() => expect(within(group).getByRole("radio", { checked: true }).textContent).toBe("Více odpovědí"));
    await waitFor(() => expect(ws.saves.length).toBeGreaterThan(0), { timeout: 5000 });
  });
});
