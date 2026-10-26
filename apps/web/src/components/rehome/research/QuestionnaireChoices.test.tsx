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
  it("reads a question with no type as a single choice, as the compiler does", async () => {
    const untyped = [{ ...SECTIONS[0], questions: [{ ...(SECTIONS[0] as { questions: Record<string, unknown>[] }).questions[0], typ: " " }] }, ...SECTIONS.slice(1)];
    stub({ goal: "G", sections: untyped, ui_state: { questionnaire_path: "manual" } });
    const { container } = render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findAllByDisplayValue("Jak často?");
    expect(within(container.querySelector("#qedit_Q1") as HTMLElement).getByRole("button", { name: "Jedna odpověď, typ otázky" })).toBeTruthy();
  });

  it("chooses a question's type from its tag's menu, the current type not offered again (spec navrh/Q2)", async () => {
    const ws = stub({ goal: "G", sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    const { container } = render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findAllByDisplayValue("Jak často?");
    const card = container.querySelector("#qedit_Q1") as HTMLElement;
    expect(within(card).queryByRole("radiogroup", { name: "Typ" })).toBeNull();
    fireEvent.click(within(card).getByRole("button", { name: "Jedna odpověď, typ otázky" }));
    const menu = within(card).getByRole("menu", { name: "Jedna odpověď, typ otázky" });
    expect((within(menu).getByRole("menuitem", { name: "Jedna odpověď" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(within(menu).getByRole("menuitem", { name: "Více odpovědí" }));
    expect(await within(card).findByRole("button", { name: "Více odpovědí, typ otázky" })).toBeTruthy();
    await waitFor(() => expect(ws.saves.length).toBeGreaterThan(0), { timeout: 5000 });
  });
});
