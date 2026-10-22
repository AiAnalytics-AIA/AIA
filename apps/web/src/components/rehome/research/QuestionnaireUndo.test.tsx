// @vitest-environment jsdom
// Dotazník's deletes with Vrátit (input-interactions chunk 3, audit A17, A18).
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

const cards = (container: HTMLElement) => [...container.querySelectorAll('[id^="qedit_"]')].map((el) => el.id);

beforeEach(() => {
  Element.prototype.scrollIntoView = () => {};
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Dotazník's deletes", () => {
  it("removes a question at once and puts it back in its place on Vrátit", async () => {
    stub({ goal: "G", sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    const { container } = render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findAllByDisplayValue("Jak často?");
    fireEvent.click(screen.getByRole("button", { name: "Odebrat otázku Q1" }));
    await waitFor(() => expect(cards(container)).toEqual(["qedit_Q2"]));
    const toast = await screen.findByText("Otázka „Jak často?“ odebrána");
    fireEvent.click(within(toast.closest("[role=status], div") as HTMLElement).getByRole("button", { name: "Vrátit" }));
    await waitFor(() => expect(cards(container)).toEqual(["qedit_Q1", "qedit_Q2"]));
  });

  it("deletes a block after its confirm and takes it back with its questions on Vrátit", async () => {
    stub({ goal: "G", sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    const { container } = render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findAllByDisplayValue("Jak často?");
    const block = container.querySelector("#qblock_sec_a") as HTMLElement;
    fireEvent.click(within(block).getAllByRole("button", { name: "Smazat" })[0]!);
    fireEvent.click(within(block).getAllByRole("button", { name: "Smazat" }).at(-1)!);
    await waitFor(() => expect(container.querySelector("#qblock_sec_a")).toBeNull());
    expect(await screen.findByText("Blok „Hlavní otázky“ smazán i s otázkami")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Vrátit" }));
    await waitFor(() => expect(cards(container)).toEqual(["qedit_Q1", "qedit_Q2"]));
  });

  it("keeps Vrátit across a look at the respondent preview", async () => {
    stub({ goal: "G", sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    const { container } = render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findAllByDisplayValue("Jak často?");
    fireEvent.click(screen.getByRole("button", { name: "Odebrat otázku Q1" }));
    await screen.findByText("Otázka „Jak často?“ odebrána");
    fireEvent.click(screen.getByRole("radio", { name: "Náhled respondenta" }));
    fireEvent.click(screen.getByRole("radio", { name: "Upravit" }));
    fireEvent.click(await screen.findByRole("button", { name: "Vrátit" }));
    await waitFor(() => expect(cards(container)).toEqual(["qedit_Q1", "qedit_Q2"]));
  });

  it("keeps Vrátit when the last block goes on the upload path and the editor closes", async () => {
    stub({ goal: "G", sections: [SECTIONS[0]], ui_state: { questionnaire_path: "upload" } });
    const { container } = render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findAllByDisplayValue("Jak často?");
    const block = container.querySelector("#qblock_sec_a") as HTMLElement;
    fireEvent.click(within(block).getAllByRole("button", { name: "Smazat" })[0]!);
    fireEvent.click(within(block).getAllByRole("button", { name: "Smazat" }).at(-1)!);
    await waitFor(() => expect(container.querySelector("#qblock_sec_a")).toBeNull());
    fireEvent.click(await screen.findByRole("button", { name: "Vrátit" }));
    await waitFor(() => expect(cards(container)).toEqual(["qedit_Q1", "qedit_Q2"]));
  });

  it("names a long question by its first 60 characters", async () => {
    const long = "Jak často během celého pracovního týdne dojíždíte do práce a jakým dopravním prostředkem?";
    stub({ goal: "G", sections: [{ ...SECTIONS[0], questions: [{ id: "Q1", text: long, typ: "otevrena" }] }], ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findAllByDisplayValue(long);
    fireEvent.click(screen.getByRole("button", { name: "Odebrat otázku Q1" }));
    expect(await screen.findByText(`Otázka „${long.slice(0, 59)}…“ odebrána`)).toBeTruthy();
  });
});
