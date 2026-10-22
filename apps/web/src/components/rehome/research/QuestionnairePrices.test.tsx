// @vitest-environment jsdom
// A concept-test set's prices as chips, refused at the field (input-interactions chunk 3, audit A16).
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
  { id: "sec_b", type: "object_battery", title: "Média", object_type: "média", objects: ["TV", "Rádio", "Web", "Tisk"], output_type: "test_konceptu", metadata: { price_bands: ["199 Kč"] } },
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

describe("a concept test's prices", () => {
  it("keeps a refused price in the field with its reason, and adds a price as a chip", async () => {
    const ws = stub({ goal: "G", sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    const { container } = render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findAllByDisplayValue("Jak často?");
    const set = container.querySelector("#qset_sec_b") as HTMLElement;
    const field = within(set).getByRole("textbox", { name: "Přidat cenu" });
    fireEvent.change(field, { target: { value: "zdarma" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(within(set).getByRole("alert").textContent).toBe("Cena musí být kladná částka, např. 199 Kč nebo 1 299,90 Kč.");
    expect((field as HTMLInputElement).value).toBe("zdarma");
    expect(field.getAttribute("aria-invalid")).toBe("true");
    fireEvent.change(field, { target: { value: "249 Kč" } });
    expect(within(set).queryByRole("alert")).toBeNull();
    fireEvent.keyDown(field, { key: "Enter" });
    expect(await within(set).findByRole("button", { name: "Odebrat 249 Kč" })).toBeTruthy();
    await waitFor(() => expect(ws.saves.length).toBeGreaterThan(0), { timeout: 5000 });
    const last = ws.saves.at(-1) as unknown as { content: { sections: { metadata?: { price_bands?: string[] } }[] } };
    expect(last.content.sections[1].metadata?.price_bands).toEqual(["199 Kč", "249 Kč"]);
  });
});
