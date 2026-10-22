// @vitest-environment jsdom
// Dotazník's block and set fields edited in place (input-interactions chunk 3e, audit A4, A13).
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NATIVE_TEST_TIMEOUT_MS, nativeAgentFixture } from "./test-native-agents";
import { ResearchScreen } from "./ResearchScreen";
import { type SavedBody, workspaceFixture } from "./test-workspace";
import { TEST_FRAME } from "./test-frame";

vi.setConfig({ testTimeout: NATIVE_TEST_TIMEOUT_MS });
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/questionnaire", useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const SECTIONS = [
  { id: "sec_a", type: "questions", title: "Hlavní otázky", purpose: "Zájem", questions: [{ id: "Q1", text: "Jak často?", typ: "vyber", kategorie: ["Denně", "Týdně"] }] },
  { id: "sec_b", type: "object_battery", title: "Média", object_type: "média", objects: ["TV", "Rádio", "Web", "Tisk"] },
];

let saves: SavedBody[] = [];
function stub(sections: unknown[] = SECTIONS) {
  const ws = workspaceFixture({ goal: "G", sections, ui_state: { questionnaire_path: "manual" } }, { analysis: null });
  saves = ws.saves;
  const native = nativeAgentFixture(() => ({ project: {}, proposal: {} }), {}, ws.write);
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const path = String(url).split("?")[0];
    const body = init?.body ? JSON.parse(String(init.body)) : null;
    const answer = native(path, init?.method ?? "GET", body) ?? ws.answer(path, init?.method ?? "GET", body);
    if (answer === undefined) return new Response(JSON.stringify({ code: "not_found", message: "No such resource." }), { status: 404 });
    return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
  }));
}
const sectionsSaved = () => (saves.at(-1) as unknown as { content: { sections: { title?: string; purpose?: string; object_type?: string; object_family?: string; object_question?: string; objects?: string[] }[] } } | undefined)?.content.sections;
const open = async (name: string) => {
  fireEvent.click(await screen.findByRole("button", { name }));
};

beforeEach(() => {
  Element.prototype.scrollIntoView = () => {};
  stub();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Dotazník's block and set fields", () => {
  it("renames a block in place: Enter saves at once and the field says it", async () => {
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await open("Upravit: Název bloku Hlavní otázky");
    const field = screen.getByRole("textbox", { name: "Název bloku" });
    fireEvent.change(field, { target: { value: "Úvodní otázky" } });
    fireEvent.keyDown(field, { key: "Enter" });
    await waitFor(() => expect(sectionsSaved()?.[0].title).toBe("Úvodní otázky"));
    expect(await screen.findByRole("button", { name: "Upravit: Název bloku Úvodní otázky" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Úvodní otázky" })).toBeTruthy();
  });

  it("puts the name back on Esc and saves nothing", async () => {
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await open("Upravit: Název sady Média");
    const before = saves.length;
    const field = screen.getByRole("textbox", { name: "Název sady" });
    fireEvent.change(field, { target: { value: "Kanály" } });
    fireEvent.keyDown(field, { key: "Escape" });
    expect(await screen.findByRole("button", { name: "Upravit: Název sady Média" })).toBeTruthy();
    expect(saves.length).toBe(before);
  });

  it("refuses an empty name at the field, and lets a purpose be cleared", async () => {
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await open("Upravit: Název bloku Hlavní otázky");
    const name = screen.getByRole("textbox", { name: "Název bloku" });
    fireEvent.change(name, { target: { value: "  " } });
    fireEvent.keyDown(name, { key: "Enter" });
    expect(name.getAttribute("aria-invalid")).toBe("true");
    fireEvent.keyDown(name, { key: "Escape" });
    const block = document.getElementById("qblock_sec_a") as HTMLElement;
    fireEvent.click(await within(block).findByRole("button", { name: /^Upravit: Proč se na tento blok ptáme\?/ }));
    const purpose = screen.getByRole("textbox", { name: "Proč se na tento blok ptáme?" });
    fireEvent.change(purpose, { target: { value: "" } });
    fireEvent.keyDown(purpose, { key: "Enter" });
    await waitFor(() => expect(sectionsSaved()?.[0].purpose).toBe(""));
    expect(sectionsSaved()?.[0].title).toBe("Hlavní otázky");
  });

  it("offers no edit on a design the person may not change", async () => {
    render(<ResearchScreen step="questionnaire" frame={{ ...TEST_FRAME, canEdit: false }} />);
    expect(((await screen.findByRole("button", { name: "Upravit: Název bloku Hlavní otázky" })) as HTMLButtonElement).disabled).toBe(true);
  });

  it("edits a set's object type and common question in place, refusing a question without {object}", async () => {
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await open("Upravit: Typ sledovaných objektů média");
    const type = screen.getByRole("textbox", { name: "Typ sledovaných objektů" });
    fireEvent.change(type, { target: { value: "kanály" } });
    fireEvent.keyDown(type, { key: "Enter" });
    await waitFor(() => expect(sectionsSaved()?.[1]).toMatchObject({ object_type: "kanály", object_family: "kanály" }));
    await open("Upravit: Společná otázka Jak hodnotíte {object}?");
    const question = screen.getByRole("textbox", { name: "Společná otázka" });
    fireEvent.change(question, { target: { value: "Jak často je používáte?" } });
    fireEvent.keyDown(question, { key: "Enter" });
    // Said at the field and kept there; nothing saved.
    expect(question.getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByText("Otázka musí obsahovat {object}, jinak se položky do otázky nepromítnou.")).toBeTruthy();
    fireEvent.change(question, { target: { value: "Jak často používáte {object}?" } });
    fireEvent.keyDown(question, { key: "Enter" });
    await waitFor(() => expect(sectionsSaved()?.[1].object_question).toBe("Jak často používáte {object}?"));
  });

  it("offers + {object} only for a stored question that lacks it, and adds it once", async () => {
    stub([SECTIONS[0], { ...SECTIONS[1], object_question: "Jak často je používáte?" }]);
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "+ {object}" }));
    await waitFor(() => expect(sectionsSaved()?.[1].object_question).toBe("Jak často je používáte? {object}"));
    await waitFor(() => expect(screen.queryByRole("button", { name: "+ {object}" })).toBeNull());
  });

  it("edits a set's goal in place and lets it be cleared", async () => {
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    const set = document.getElementById("qset_sec_b") ?? (await screen.findByText("SADA 1")).closest("article")!;
    fireEvent.click(await within(set as HTMLElement).findByRole("button", { name: /^Upravit: Co chceme z porovnání zjistit\?/ }));
    const goal = screen.getByRole("textbox", { name: "Co chceme z porovnání zjistit?" });
    fireEvent.change(goal, { target: { value: "Který kanál oslovuje nejvíc" } });
    fireEvent.keyDown(goal, { key: "Enter" });
    await waitFor(() => expect(sectionsSaved()?.[1].purpose).toBe("Který kanál oslovuje nejvíc"));
  });

  it("counts a set's objects beside the list and refuses a sixteenth in words (A14)", async () => {
    stub([SECTIONS[0], { ...SECTIONS[1], objects: Array.from({ length: 14 }, (_, i) => `Objekt ${i + 1}`) }]);
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    const add = await screen.findByRole("textbox", { name: "Přidat objekt a Enter" });
    // The card's one count sits in the list's own label row.
    const count = () => screen.getByText(/^\d+ \/ 4–15$/).textContent;
    expect(count()).toBe("14 / 4–15");
    fireEvent.change(add, { target: { value: "Objekt 15" } });
    fireEvent.keyDown(add, { key: "Enter" });
    await waitFor(() => expect(count()).toBe("15 / 4–15"));
    fireEvent.change(add, { target: { value: "Objekt 16" } });
    fireEvent.keyDown(add, { key: "Enter" });
    expect(await screen.findByText("AIA doporučuje sadu nejvýše s 15 objekty. Další přidáte, až jeden odeberete.")).toBeTruthy();
    expect((add as HTMLInputElement).value).toBe("Objekt 16");
    // One removed: the reason no longer holds and goes; Enter then adds the kept name.
    fireEvent.click(screen.getByRole("button", { name: /Objekt 1$/ }));
    await waitFor(() => expect(count()).toBe("14 / 4–15"));
    expect(screen.queryByText("AIA doporučuje sadu nejvýše s 15 objekty. Další přidáte, až jeden odeberete.")).toBeNull();
    fireEvent.keyDown(add, { key: "Enter" });
    await waitFor(() => expect(count()).toBe("15 / 4–15"));
  });

  it("keeps a set stored above fifteen whole when one object is removed", async () => {
    // The server takes up to 40 (an import, an older copy); the screen shows them all and cuts none.
    stub([SECTIONS[0], { ...SECTIONS[1], objects: Array.from({ length: 17 }, (_, i) => `Objekt ${i + 1}`) }]);
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    expect(await screen.findByText("17 / 4–15")).toBeTruthy();
    expect(screen.getByText("Sledovaná sada potřebuje 4–15 položek.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Objekt 1$/ }));
    await waitFor(() => expect(sectionsSaved()?.[1].objects).toEqual(Array.from({ length: 16 }, (_, i) => `Objekt ${i + 2}`)));
    expect(screen.getByText("16 / 4–15")).toBeTruthy();
  });
});
