// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from "vitest";

import { AGENTS_PATH, NATIVE_JOB_WAIT, NATIVE_TEST_TIMEOUT_MS, PARK_MESSAGE, approveProposal, nativeAgentFixture } from "./test-native-agents";
import { briefFingerprint, defaultsMerge } from "@/research/model";
import { FrameNavigation } from "../step";
import { ResearchScreen } from "./ResearchScreen";
import { type SavedBody, workspaceFixture } from "./test-workspace";
import { TEST_FRAME, stagePath } from "./test-frame";

// Native jobs need more than vitest's 5 s under CI load (test-native-agents.ts).
vi.setConfig({ testTimeout: NATIVE_TEST_TIMEOUT_MS });

const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/questionnaire", useRouter: () => ({ push, replace }) }));

const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/research/fixtures/empty-project.json"), "utf8"));
const TEMPLATE = { empty_project: EMPTY };
const SECTIONS = [
  { id: "sec_a", type: "questions", title: "Hlavní otázky", purpose: "", questions: [
    { id: "Q1", text: "Jak často?", typ: "vyber", kategorie: ["Denně", "Týdně"] },
    { id: "Q2", text: "Jak moc?", typ: "skala", skala: [1, 10], popisky_skaly: ["vůbec", "zcela"] },
  ] },
  { id: "sec_b", type: "object_battery", title: "Sledovaná sada — média", object_type: "média", objects: ["TV", "Rádio", "Web", "Tisk"], object_question: "Jak často používáte {object}?", scale_labels: ["nikdy", "denně"] },
];
const BRIEF = { goal: "Zjistit zájem o nový nápoj" };

type Call = { url: string; body: Record<string, unknown> | null };
let calls: Call[] = [];
let saves: SavedBody[] = [];
function unitStub(project: Record<string, unknown>, analysis: unknown = null, over: Record<string, (b: unknown) => unknown> = {}) {
  calls = [];
  const ws = workspaceFixture(project, { analysis: analysis });
  saves = ws.saves;
  const native = nativeAgentFixture((action, baseline) => action === "analyze_brief" ? { project: baseline, proposal: { objectives: ["O"] }, analysis: { objectives: ["O"] } } : { project: { ...baseline, sections: SECTIONS }, proposal: { sections: SECTIONS } }, over, ws.write);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ url: u, body });
      const answer = native(u.split("?")[0], init?.method ?? "GET", body) ?? ws.answer(u.split("?")[0], init?.method ?? "GET", body) ?? over[u.split("?")[0]]?.(body);
      if (answer === undefined) return new Response(JSON.stringify({ code: "not_found", message: "No such resource." }), { status: 404 });
      return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
    }),
  );
}
const posted = (path: string) => calls.filter((c) => c.url.split("?")[0] === path && (!path.startsWith("/api/v1/") || c.body !== null));

/** Every test here also proves the screen reached nothing of the 18.6.6 unit (ADR 0018). */
const unitCalls = () => calls.filter((c) => !c.url.startsWith("/api/v1/") && c.url !== "/config").map((c) => c.url);
const lastSave = () => saves.at(-1) as unknown as { content: { sections: { questions?: { typ: string; kategorie?: string[] }[]; objects?: string[] }[]; ui_state: Record<string, unknown> }; reason: string };

async function saved() {
  // The store saves 1.8 s after the last change; the test waits for that body.
  await waitFor(() => expect(saves.length).toBeGreaterThan(0));
}

if (!Blob.prototype.arrayBuffer) {
  Blob.prototype.arrayBuffer = function (this: Blob) {
    return new Promise<ArrayBuffer>((resolve) => {
      const r = new FileReader();
      r.onload = () => resolve(r.result as ArrayBuffer);
      r.readAsArrayBuffer(this);
    });
  };
}
beforeEach(() => {
  push.mockReset();
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
  Element.prototype.scrollIntoView = () => {};
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  expect(unitCalls()).toEqual([]);
});

describe("Dotazník", () => {
  it("offers the three paths with the design availability, and waits for questions before going on", async () => {
    unitStub(BRIEF);
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    expect(await screen.findByRole("heading", { name: "Jak chcete dotazník vytvořit?" })).toBeTruthy();
    expect(screen.getByText("Návrh AI se uloží jako návrh ke kontrole. Změny použijete až po potvrzení.")).toBeTruthy();
    expect((screen.getByRole("button", { name: /Další · cílová skupina/ }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Nejdřív vytvořte nebo nahrajte dotazník.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Sestavit ručně/ }));
    expect(await screen.findByText("Dotazník je prázdný")).toBeTruthy();
    // Studio v3: a method switcher replaces "změnit způsob vytvoření".
    fireEvent.click(within(screen.getByRole("radiogroup", { name: "Způsob" })).getByRole("radio", { name: "Nahrát Excel" }));
    expect(await screen.findByRole("heading", { name: "Nahrát dotazník" })).toBeTruthy();
  });

  it("says tracked sets alone are no questionnaire yet, and the dock is not ready (OI-52 (b))", async () => {
    unitStub({ ...BRIEF, sections: [SECTIONS[1]], ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    const note = await screen.findByText("Samotné sledované sady dotazník netvoří: přidejte alespoň jednu běžnou otázku.");
    expect(note.className).toContain("text-status-you-ink");
    expect(screen.queryByText("Dotazník je připravený")).toBeNull();
  });

  it("draws the preview and the editor, and has no dead 'AI: zlepšit blok' (OI-49)", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    expect(await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" })).toBeTruthy();
    // The outline lists blocks, questions and sets; the preview is the editor's other tab.
    expect(screen.getAllByRole("button", { name: /^(B1|Q1|Q2|S1)/ }).map((b) => b.textContent)).toEqual(["B1Hlavní otázky", "Q1Jak často?", "Q2Jak moc?", "S1Sledovaná sada — média"]);
    fireEvent.click(screen.getByRole("radio", { name: "Náhled respondenta" }));
    const preview = screen.getByRole("region", { name: "Jak bude dotazník přibližně vypadat" });
    expect(within(preview).getByText("Otázka 1")).toBeTruthy();
    expect(within(preview).getByText("Sledovaná sada 1 · Sledovaná sada — média")).toBeTruthy();
    expect(within(preview).getAllByText("Jak často používáte TV?").length).toBe(1);
    expect(screen.queryByText(/zlepšit blok/)).toBeNull();
    expect((screen.getByRole("button", { name: /Další · cílová skupina/ }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("marks a question without wording where it is, and lists it beside the questionnaire", async () => {
    const sections = structuredClone(SECTIONS) as { questions?: { text?: string }[] }[];
    sections[0]!.questions![1]!.text = "";
    unitStub({ ...BRIEF, sections, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" });
    const unworded = screen.getAllByRole("textbox", { name: "Znění otázky" }).find((x) => x.getAttribute("aria-invalid") === "true")!;
    expect(document.getElementById(unworded.getAttribute("aria-describedby")!)?.textContent).toBe("Doplňte znění. Bez něj návrh nejde spustit.");
    const ready = screen.getByRole("region", { name: "Dotazník" });
    expect(within(ready).getByRole("button", { name: /Otázky bez znění: 1/ })).toBeTruthy();
  });

  it("shows a question's display condition from 18.6.6 and removes it, so the run can start (PC15)", async () => {
    const sections = structuredClone(SECTIONS) as { questions?: Record<string, unknown>[] }[];
    sections[0]!.questions![1]!.filtr = "Q1 != 'Denně'";
    unitStub({ ...BRIEF, sections, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" });
    const card = document.getElementById("qedit_Q2") as HTMLElement;
    // Shown as written, with no claim that AIA cannot read it: Kontrola says what it makes of it.
    expect(within(card).getByText(/„Q1 != 'Denně'“\)\. Ukazujeme ji, jak je zapsaná; zda ji běh přijme, řekne Kontrola\./)).toBeTruthy();
    expect(card.textContent).not.toMatch(/nerozumí/);
    expect(document.getElementById("qedit_Q1")!.querySelector("[data-question-condition]")).toBeNull();
    fireEvent.click(within(card).getByRole("button", { name: "Odebrat podmínku" }));
    expect(card.querySelector("[data-question-condition]")).toBeNull();
    await saved();
    const question = (lastSave().content.sections[0]!.questions as Record<string, unknown>[] | undefined)![1]!;
    expect("filtr" in question).toBe(false);
    expect(question.text).toBe("Jak moc?");
  });

  it("sets a question's display condition on an earlier choice question's answers, edits it and removes it (WCE13)", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } }, null, { "/config": () => ({ routing: true }) });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" });
    // Q1 has no earlier choice question, so nothing to stand on: no condition is offered.
    expect(within(document.getElementById("qedit_Q1")!).queryByRole("button", { name: "Podmínka zobrazení" })).toBeNull();
    const card = document.getElementById("qedit_Q2") as HTMLElement;
    // The switch is read from /config once the card is there.
    fireEvent.click(await within(card).findByRole("button", { name: "Podmínka zobrazení" }));
    fireEvent.click(within(within(card).getByRole("radiogroup", { name: "Zobrazit podle odpovědi na otázku" })).getByRole("radio", { name: /^Q1 · Jak často\?/ }));
    const save = within(card).getByRole("button", { name: "Uložit podmínku" }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.click(within(within(card).getByRole("group", { name: "Zobrazit těm, kdo odpověděli" })).getByRole("button", { name: "Týdně" }));
    fireEvent.click(save);
    expect(within(card).getByText(/Zobrazí se jen těm, kdo u Q1 \(„Jak často\?“\) odpověděli „Týdně“\./)).toBeTruthy();
    await saved();
    const question = () => (lastSave().content.sections[0]!.questions as Record<string, unknown>[] | undefined)![1]!;
    expect(question().filtr).toEqual({ question_id: "Q1", options: ["Týdně"] });
    // Edited: the form opens on what is stored, and Escape leaves it unchanged.
    fireEvent.click(within(card).getByRole("button", { name: "Upravit podmínku" }));
    const answers = within(card).getByRole("group", { name: "Zobrazit těm, kdo odpověděli" });
    expect(within(answers).getByRole("button", { name: "Týdně" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.keyDown(within(answers).getByRole("button", { name: "Denně" }), { key: "Escape" });
    expect(within(card).queryByRole("button", { name: "Uložit podmínku" })).toBeNull();
    fireEvent.click(within(card).getByRole("button", { name: "Upravit podmínku" }));
    fireEvent.click(within(within(card).getByRole("group", { name: "Zobrazit těm, kdo odpověděli" })).getByRole("button", { name: "Denně" }));
    fireEvent.click(within(card).getByRole("button", { name: "Uložit podmínku" }));
    await waitFor(() => expect(question().filtr).toEqual({ question_id: "Q1", options: ["Denně", "Týdně"] }));
    fireEvent.click(within(card).getByRole("button", { name: "Odebrat podmínku" }));
    await waitFor(() => expect("filtr" in question()).toBe(false));
  });

  it("moves focus into the condition form and back to its button when it closes, for the keyboard", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } }, null, { "/config": () => ({ routing: true }) });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" });
    const card = document.getElementById("qedit_Q2") as HTMLElement;
    fireEvent.click(await within(card).findByRole("button", { name: "Podmínka zobrazení" }));
    const form = card.querySelector("[data-condition-form]") as HTMLElement;
    // Opened: focus is in the form, on its first choice, never left on the page.
    expect(form.contains(document.activeElement)).toBe(true);
    // Escape: back on the button that opened it.
    fireEvent.keyDown(document.activeElement!, { key: "Escape" });
    expect(document.activeElement).toBe(within(card).getByRole("button", { name: "Podmínka zobrazení" }));
    // Saved: on the stored condition's own button.
    fireEvent.click(within(card).getByRole("button", { name: "Podmínka zobrazení" }));
    fireEvent.click(within(card).getByRole("radio", { name: /^Q1 · / }));
    fireEvent.click(within(within(card).getByRole("group", { name: "Zobrazit těm, kdo odpověděli" })).getByRole("button", { name: "Týdně" }));
    fireEvent.click(within(card).getByRole("button", { name: "Uložit podmínku" }));
    expect(document.activeElement).toBe(within(card).getByRole("button", { name: "Upravit podmínku" }));
    // Zrušit: back on the same button.
    fireEvent.click(within(card).getByRole("button", { name: "Upravit podmínku" }));
    fireEvent.click(within(card).getByRole("button", { name: "Zrušit" }));
    expect(document.activeElement).toBe(within(card).getByRole("button", { name: "Upravit podmínku" }));
    // Odebrat podmínku: on the button that sets one again.
    fireEvent.click(within(card).getByRole("button", { name: "Odebrat podmínku" }));
    await waitFor(() => expect(document.activeElement).toBe(within(card).getByRole("button", { name: "Podmínka zobrazení" })));
  });

  it("keeps the form open and says why when the questionnaire moved under it", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } }, null, { "/config": () => ({ routing: true }) });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" });
    const card = document.getElementById("qedit_Q2") as HTMLElement;
    fireEvent.click(await within(card).findByRole("button", { name: "Podmínka zobrazení" }));
    fireEvent.click(within(card).getByRole("radio", { name: /^Q1 · / }));
    fireEvent.click(within(within(card).getByRole("group", { name: "Zobrazit těm, kdo odpověděli" })).getByRole("button", { name: "Týdně" }));
    // The answer chosen is removed from Q1 while the form is open.
    fireEvent.click(within(document.getElementById("qedit_Q1")!).getByRole("button", { name: "Odebrat možnost 2" }));
    fireEvent.click(within(card).getByRole("button", { name: "Uložit podmínku" }));
    expect(within(card).getByRole("alert").textContent).toBe("Otázka, na které podmínka stojí, takovou odpověď nemá.");
    expect(within(card).getByRole("button", { name: "Uložit podmínku" })).toBeTruthy();
    expect(card.querySelector("[data-question-condition]")).toBeNull();
  });

  it("says why a stored condition does not stand, and sets it again", async () => {
    const sections = structuredClone(SECTIONS) as { questions?: Record<string, unknown>[] }[];
    sections[0]!.questions![1]!.filtr = { question_id: "Q1", options: ["Někdy"] };
    unitStub({ ...BRIEF, sections, ui_state: { questionnaire_path: "manual" } }, null, { "/config": () => ({ routing: true }) });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" });
    const card = document.getElementById("qedit_Q2") as HTMLElement;
    expect(within(card).getByText(/Podmínka neplatí: Otázka, na které podmínka stojí, takovou odpověď nemá\./)).toBeTruthy();
    fireEvent.click(await within(card).findByRole("button", { name: "Nastavit znovu" }));
    // Nothing refused is carried into the form: it starts from no question and no answer.
    const sources = within(card).getByRole("radiogroup", { name: "Zobrazit podle odpovědi na otázku" });
    expect(within(sources).getAllByRole("radio").every((r) => r.getAttribute("aria-checked") === "false")).toBe(true);
    fireEvent.click(within(sources).getByRole("radio", { name: /^Q1 · / }));
    const answers = within(card).getByRole("group", { name: "Zobrazit těm, kdo odpověděli" });
    expect(within(answers).getAllByRole("button").every((b) => b.getAttribute("aria-pressed") === "false")).toBe(true);
    fireEvent.click(within(answers).getByRole("button", { name: "Denně" }));
    fireEvent.click(within(card).getByRole("button", { name: "Uložit podmínku" }));
    await within(card).findByText(/Zobrazí se jen těm, kdo u Q1 \(„Jak často\?“\) odpověděli „Denně“\./);
  });

  it("reads an 18.6.6 expression as Kontrola does: a valid one as a sentence, a refused one with why", async () => {
    const sections = structuredClone(SECTIONS) as { questions?: Record<string, unknown>[] }[];
    sections[0]!.questions![0]!.filtr = "Q2 == '5'";
    sections[0]!.questions![1]!.filtr = "Q1 in ['Týdně']";
    unitStub({ ...BRIEF, sections, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" });
    const first = document.getElementById("qedit_Q1") as HTMLElement;
    expect(within(first).getByText(/^Podmínka neplatí: Podmínka smí stavět jen na otázce, která je v dotazníku dřív\.$/)).toBeTruthy();
    const second = document.getElementById("qedit_Q2") as HTMLElement;
    expect(within(second).getByText(/Zobrazí se jen těm, kdo u Q1 \(„Jak často\?“\) odpověděli „Týdně“\./)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/nerozumí/);
  });

  it("offers no condition to set without the routing switch; a stored one is shown and can be removed", async () => {
    const sections = structuredClone(SECTIONS) as { questions?: Record<string, unknown>[] }[];
    unitStub({ ...BRIEF, sections, ui_state: { questionnaire_path: "manual" } }, null, { "/config": () => ({ routing: false }) });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" });
    await waitFor(() => expect(calls.some((c) => c.url === "/config")).toBe(true));
    const card = document.getElementById("qedit_Q2") as HTMLElement;
    await waitFor(() => expect(within(card).queryByRole("button", { name: "Podmínka zobrazení" })).toBeNull());
    cleanup();
    sections[0]!.questions![1]!.filtr = { question_id: "Q1", options: ["Týdně"] };
    unitStub({ ...BRIEF, sections, ui_state: { questionnaire_path: "manual" } }, null, { "/config": () => ({ routing: false }) });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" });
    const stored = document.getElementById("qedit_Q2") as HTMLElement;
    expect(within(stored).getByText(/Zobrazí se jen těm, kdo u Q1/)).toBeTruthy();
    await waitFor(() => expect(within(stored).queryByRole("button", { name: "Upravit podmínku" })).toBeNull());
    expect(within(stored).getByRole("button", { name: "Odebrat podmínku" })).toBeTruthy();
    // Removed with nothing left in its box: focus goes to the question's wording, never to a type
    // chip, where one key would change the question's type (QF-18, the stand-in review).
    fireEvent.click(within(stored).getByRole("button", { name: "Odebrat podmínku" }));
    await waitFor(() => expect(document.activeElement).toBe(within(stored).getByRole("textbox", { name: "Znění otázky" })));
  });

  it("introduces the topic and market research in Czech, promising nothing the panel lacks", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    const section = await screen.findByRole("region", { name: "Před uzavřením dotazníku" });
    // What Design Research looks into: the study's research questions and tracked objects, in approved
    // client knowledge and on the web (deep_research/contracts.py SubjectKind, Channel).
    expect(within(section).getByText("Volitelně si nechte udělat rešerši výzkumných otázek a sledovaných objektů studie ve schválených znalostech klienta a na webu. Čísla o výsledcích, která rešerše najde, AIA respondentům sama nikdy neukáže.")).toBeTruthy();
    // The browser audit: half English, a model choice and an update the panel does not offer, and
    // 18.6.6's topic list, which no track researches.
    expect(section.textContent).not.toMatch(/research tématu|price\/value|Outcome|Existing|zvolený model|aktualizovat|motivace|konkurence/);
  });

  it("numbers the respondent's preview as the editor does, questions and sets each on their own", async () => {
    // A set before the questions: 18.6.6's running count would read Sledovaná sada 1, Otázka 2, Otázka 3.
    unitStub({ ...BRIEF, sections: [SECTIONS[1], SECTIONS[0]], ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("radio", { name: "Náhled respondenta" }));
    const preview = await screen.findByRole("region", { name: "Jak bude dotazník přibližně vypadat" });
    for (const label of ["Sledovaná sada 1 · Sledovaná sada — média", "Otázka 1", "Otázka 2"]) expect(within(preview).getByText(label)).toBeTruthy();
    expect(within(preview).queryByText("Otázka 3")).toBeNull();
  });

  it("edits a question as the classic editor does: type, options and a scale", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" });
    const card = document.getElementById("qedit_Q1") as HTMLElement;
    // Options are rows: Enter adds one below, and the list is applied when it is left.
    const options = within(card).getByRole("group", { name: "Možnosti — jedna na řádek" });
    fireEvent.change(within(options).getByLabelText("Možnost 1"), { target: { value: " Denně " } });
    fireEvent.keyDown(within(options).getByLabelText("Možnost 2"), { key: "Enter" });
    fireEvent.change(within(options).getByLabelText("Možnost 3"), { target: { value: "Nikdy " } });
    fireEvent.blur(within(options).getByLabelText("Možnost 3"), { relatedTarget: null });
    fireEvent.click(within(card).getByRole("button", { name: "Jedna odpověď, typ otázky" }));
    fireEvent.click(within(card).getByRole("menuitem", { name: "Škála" }));
    expect(await within(card).findByRole("radiogroup", { name: "Rozsah škály Q1" })).toBeTruthy();
    await saved();
    const q1 = lastSave().content.sections[0].questions![0];
    expect(q1).toMatchObject({ typ: "skala", kategorie: ["Denně", "Týdně", "Nikdy"] });
  });

  it("saves a scale's preset and a label on every point through the working copy (input-interactions 3b2)", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" });
    const card = document.getElementById("qedit_Q2") as HTMLElement;
    fireEvent.click(within(within(card).getByRole("radiogroup", { name: "Rozsah škály Q2" })).getByRole("radio", { name: "1–5" }));
    fireEvent.click(within(within(card).getByRole("radiogroup", { name: "Popisky škály Q2" })).getByRole("radio", { name: "Každý bod" }));
    for (const [n, label] of [[2, "spíše ne"], [3, "nevím"], [4, "spíše ano"]] as const) {
      fireEvent.click(within(card).getByRole("button", { name: new RegExp(`^Upravit: Popisek bodu ${n}`) }));
      const field = within(card).getByRole("textbox", { name: `Popisek bodu ${n}` });
      fireEvent.change(field, { target: { value: label } });
      fireEvent.keyDown(field, { key: "Enter" });
    }
    await saved();
    await waitFor(() => {
      const q2 = (lastSave().content.sections[0].questions as unknown as { skala: number[]; popisky_skaly: string[] }[])[1];
      expect(q2.skala).toEqual([1, 5]);
      expect(q2.popisky_skaly).toEqual(["vůbec", "spíše ne", "nevím", "spíše ano", "zcela"]);
    }, { timeout: 10_000 });
    // A set's scale shows its range and offers its two ends only.
    const set = document.getElementById("qset_sec_b") as HTMLElement;
    expect(within(set).getByText("Škála 1–10")).toBeTruthy();
    expect(within(set).queryByRole("radiogroup", { name: "Popisky škály sada 1" })).toBeNull();
  });

  it("shows a question's links as VO chips named by the research question's text, and says when it measures none (Q3)", async () => {
    const plan = { research_questions: ["Jak často lidé pijí kávu?", "Která média lidé používají?"] };
    unitStub({ ...BRIEF, research_plan: plan, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" });
    const linksOfItem = (id: string) => within(document.getElementById(id) as HTMLElement).getByRole("group", { name: "Odpovídá na výzkumné otázky" });
    const q1 = linksOfItem("qedit_Q1");
    // The chip reads "VO1" and is named by it and the question; the question is its tooltip too.
    const chip = within(q1).getByRole("button", { name: "VO1: Jak často lidé pijí kávu?" });
    expect(chip.querySelector("[title]")?.getAttribute("title")).toBe("Jak často lidé pijí kávu?");
    // The page keys "VO n" to its question without hover: the comparisons card numbers its rows the same way.
    expect(screen.getByText("VO2 · Která média lidé používají?")).toBeTruthy();
    // Nothing linked anywhere yet: coverage is unknown, so no card says it measures nothing.
    expect(screen.queryByText(/^Neměří žádnou výzkumnou otázku/)).toBeNull();
    fireEvent.click(chip);
    // Q1's link is written out for touch, and Q2, now beside a linked item, says it measures none.
    expect(within(q1).getByText("VO1 · Jak často lidé pijí kávu?")).toBeTruthy();
    expect(within(linksOfItem("qedit_Q2")).getByText(/^Neměří žádnou výzkumnou otázku/)).toBeTruthy();
  });

  it("says which research question a question and a set measure, and drops a link the plan no longer states", async () => {
    const plan = { research_questions: ["Jak často lidé pijí kávu?", "Která média lidé používají?"] };
    const sections = [{ ...SECTIONS[0], questions: [{ ...SECTIONS[0].questions![0], research_questions: ["Stará otázka?"] }, SECTIONS[0].questions![1]] }, SECTIONS[1]];
    unitStub({ ...BRIEF, research_plan: plan, sections, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" });
    const card = document.getElementById("qedit_Q1") as HTMLElement;
    const links = within(card).getByRole("group", { name: "Odpovídá na výzkumné otázky" });
    fireEvent.click(within(links).getByRole("button", { name: "Odebrat odkaz na „Stará otázka?“" }));
    fireEvent.click(within(links).getByRole("button", { name: "VO1: Jak často lidé pijí kávu?" }));
    expect(within(links).getByRole("button", { name: "VO1: Jak často lidé pijí kávu?" }).getAttribute("aria-pressed")).toBe("true");
    const set = document.getElementById("qset_sec_b") as HTMLElement;
    fireEvent.click(within(within(set).getByRole("group", { name: "Odpovídá na výzkumné otázky" })).getByRole("button", { name: "VO2: Která média lidé používají?" }));
    await saved();
    await waitFor(() => expect(lastSave().reason).toBe("questionnaire_links"));
    const content = lastSave().content as unknown as { sections: { research_questions?: string[]; questions?: { research_questions?: string[] }[] }[] };
    expect(content.sections[0].questions![0].research_questions).toEqual(["Jak často lidé pijí kávu?"]);
    expect(content.sections[0].questions![1]).not.toHaveProperty("research_questions");
    expect(content.sections[1].research_questions).toEqual(["Která média lidé používají?"]);
  });

  it("declares how each research question is answered and saves it in the plan", async () => {
    const plan = { research_questions: ["Jak často lidé pijí kávu?", "Která média lidé používají?"] };
    unitStub({ ...BRIEF, research_plan: plan, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    const panel = await screen.findByRole("region", { name: "Jak výzkumné otázky zodpovíme" });
    // One of five, chosen as chips (input-interactions chunk 3, audit A11): "Neurčeno" until chosen.
    const media = within(panel).getByRole("radiogroup", { name: "Způsob odpovědi na „Která média lidé používají?“" });
    expect(within(media).getByRole("radio", { checked: true }).textContent).toBe("Neurčeno");
    fireEvent.click(within(media).getByRole("radio", { name: "Pořadí položek sady" }));
    await saved();
    await waitFor(() => expect(lastSave().reason).toBe("research_question_comparison"));
    const content = lastSave().content as unknown as { research_plan: { research_question_comparisons?: Record<string, string>; research_questions: string[] } };
    expect(content.research_plan.research_question_comparisons).toEqual({ "Která média lidé používají?": "rank_objects" });
    expect(content.research_plan.research_questions).toEqual(plan.research_questions);
  });

  it("opens on the place a link from the Run stage names, and on the editor for a place it no longer has", async () => {
    // research-integrity-report 14: each gap links to where it is fixed (lib/answerability.ts gapFixes),
    // by the server's id: the question the web calls "Q2" is "q2" there (review, 2026-10-18).
    const seen: string[] = [];
    Element.prototype.scrollIntoView = function (this: Element) {
      seen.push(this.id);
    };
    window.history.replaceState(null, "", "#qedit_q2");
    onTestFinished(() => window.history.replaceState(null, "", "/"));
    const plan = { research_questions: ["Jak často lidé pijí kávu?"] };
    unitStub({ ...BRIEF, research_plan: plan, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    // Once the editor is drawn, never before.
    await waitFor(() => expect(seen).toEqual(["qedit_Q2"]));
    // Keyboard focus moves there too, so Tab goes on from the question, not the page's start
    // (review web#7); the card is focusable from script only, never in the Tab order.
    await waitFor(() => expect(document.activeElement?.id).toBe("qedit_Q2"));
    expect(document.activeElement?.getAttribute("tabindex")).toBe("-1");
    const go = async (hash: string, id: string) => {
      window.location.hash = hash;
      fireEvent(window, new HashChangeEvent("hashchange"));
      await waitFor(() => expect(seen.at(-1)).toBe(id));
      await waitFor(() => expect(document.activeElement?.id).toBe(id));
    };
    await go("q-comparisons", "q-comparisons");
    expect(document.getElementById("q-comparisons")?.getAttribute("aria-label")).toBe("Jak výzkumné otázky zodpovíme");
    // The web's own id names no item a link can name.
    await go("qedit_Q2", "q-editor");
    await go("qset_sec_b", "qset_sec_b");
    await go("qedit_gone", "q-editor");
  });

  it("turns a tracked set into a concept test an A/B comparison needs, and back (review, Codex on #426)", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" });
    const set = document.getElementById("qset_sec_b") as HTMLElement;
    const toggle = within(set).getByRole("switch", { name: "Porovnat položky jako koncepty (A/B test)" });
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    expect(within(set).queryByText("Cenová pásma pro test konceptu")).toBeNull();
    fireEvent.click(toggle);
    await saved();
    await waitFor(() => expect(lastSave().reason).toBe("concept_test"));
    expect((lastSave().content as unknown as { sections: { output_type?: string }[] }).sections[1].output_type).toBe("test_konceptu");
    expect(within(set).getByText("Cenová pásma pro test konceptu")).toBeTruthy();
    fireEvent.click(within(set).getByRole("switch", { name: "Porovnat položky jako koncepty (A/B test)" }));
    await waitFor(() => expect((lastSave().content as unknown as { sections: { output_type?: string }[] }).sections[1].output_type).toBe("pozicni_mapa"));
  });

  it("adds a question, a block and a set in their own rows, without a prompt (input-interactions I5)", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" });
    // Quick add: the kind as chips, the wording in the row; Enter adds it and opens the next row.
    fireEvent.click(within(screen.getByRole("radiogroup", { name: "Typ nové otázky" })).getByRole("radio", { name: "Škála 1–10" }));
    fireEvent.click(screen.getByRole("button", { name: "Nová otázka" }));
    const row = screen.getByRole("textbox", { name: "Nová otázka" });
    fireEvent.change(row, { target: { value: "Jak moc vám chutná?" } });
    fireEvent.keyDown(row, { key: "Enter" });
    await screen.findByRole("heading", { name: "3 otázky · 1 sledovaná sada" });
    expect(screen.getByRole("textbox", { name: "Nová otázka" })).toBeTruthy();
    await saved();
    await waitFor(() => expect(lastSave().content.sections[0].questions!.at(-1)).toMatchObject({ typ: "skala" }));
    // A set named in its row opens with its objects still to add, the count beside them.
    fireEvent.click(screen.getByRole("button", { name: "Sledovaná sada" }));
    const set = screen.getByRole("textbox", { name: "Sledovaná sada" });
    fireEvent.change(set, { target: { value: "značky" } });
    fireEvent.keyDown(set, { key: "Enter" });
    await screen.findByRole("heading", { name: "3 otázky · 2 sledované sady" });
    expect(screen.getByText("0 / doporučeno 4–15")).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  it("names a new block in its row, and adds a question into a block from the block's own row", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" });
    fireEvent.click(screen.getByRole("button", { name: "Nový blok" }));
    const name = screen.getByRole("textbox", { name: "Nový blok" });
    fireEvent.change(name, { target: { value: "Úvod" } });
    fireEvent.keyDown(name, { key: "Enter" });
    await waitFor(() => expect(screen.getByRole("button", { name: "Upravit: Název bloku Úvod" })).toBeTruthy());
    const block = document.getElementById("qblock_sec_a") as HTMLElement;
    fireEvent.click(within(block).getByRole("button", { name: "Otázka do tohoto bloku" }));
    const wording = within(block).getByRole("textbox", { name: "Otázka do tohoto bloku" });
    fireEvent.change(wording, { target: { value: "Kolik šálků denně?" } });
    fireEvent.keyDown(wording, { key: "Enter" });
    await saved();
    await waitFor(() => expect(lastSave().content.sections[0].questions!.map((q) => (q as { text?: string }).text)).toEqual(["Jak často?", "Jak moc?", "Kolik šálků denně?"]));
    expect((lastSave().content.sections as { title?: string }[]).at(-1)?.title).toBe("Úvod");
  });

  it("says an empty new question as its wording to write, never a name", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" });
    const block = document.getElementById("qblock_sec_a") as HTMLElement;
    fireEvent.click(within(block).getByRole("button", { name: "Otázka do tohoto bloku" }));
    // Each row's own message: the one its field is described by.
    const said = (row: HTMLElement) => document.getElementById(row.getAttribute("aria-describedby") ?? "")?.textContent;
    const inBlock = within(block).getByRole("textbox", { name: "Otázka do tohoto bloku" });
    fireEvent.keyDown(inBlock, { key: "Enter" });
    expect(said(inBlock)).toBe("Napište znění.");
    fireEvent.click(screen.getByRole("button", { name: "Nová otázka" }));
    const outline = screen.getByRole("textbox", { name: "Nová otázka" });
    fireEvent.keyDown(outline, { key: "Enter" });
    expect(said(outline)).toBe("Napište znění.");
  });

  it("notes a set under four objects, and removes a block only when confirmed", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    // Objects are chips; updateObjects notes a set under four.
    fireEvent.click(await screen.findByRole("button", { name: "Odebrat Tisk" }));
    expect(await screen.findByText("Nejmenší počet objektů v sadě: 4.")).toBeTruthy();
    expect(screen.getByText("3 / doporučeno 4–15")).toBeTruthy();
    // Removal is confirmed on the card.
    fireEvent.click(screen.getAllByRole("button", { name: "Smazat" })[1]);
    expect(screen.getByRole("alertdialog").textContent).toContain("Odstranit tuto sadu?");
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Smazat" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "2 otázky · 0 sledovaných sad" })).toBeTruthy());
  });

  it("starts durable public Deep Research from the saved design, without the legacy endpoint", async () => {
    const path = "/api/v1/studies/STU-1/deep-research/runs";
    // A step that waits on the study's budget, and one waiting for a reason this client has no words for.
    const waiting = [
      { step_id: "S-1", node_key: "investigate/web-1", status: "AWAITING_BUDGET", waiting_reason: "budget_exceeded", error_message: null },
      { step_id: "S-2", node_key: "verify", status: "RUNNABLE", waiting_reason: "gate:novel", error_message: null },
    ];
    const job = { run_id: "RUN-a1", design_revision_id: "REV-A", preset: "QUICK", channels: ["WEB"], status: "RUNNING", phase: "RUNNING", is_terminal: false, needs_attention: false, retryable: false, created_at: null, steps: waiting, actual_cost_usd: null };
    let started = false;
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } }, null, {
      [path]: (body) => {
        if (body) { started = true; return job; }
        return started ? [job] : [];
      },
    });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Spustit veřejný výzkum" }));
    await waitFor(() => expect(posted(path)).toHaveLength(1));
    expect(posted(path)[0].body).toEqual({ design_revision_id: "REV-A", preset_name: "QUICK", channels: ["WEB"] });
    expect(posted("/api/v1/studies/STU-1/design/revisions")[0].body).toMatchObject({ source_stage: "questionnaire" });
    expect(calls.some((call) => call.url === "/api/research/deep")).toBe(false);
    expect(await screen.findByText("Stav: Běží")).toBeTruthy();
    // Each step by its name and its reason in words (6b); an unknown reason keeps its code aside.
    expect(screen.getByText(/Hledání zdrojů \(web-1\):/).textContent).toContain("Krok čeká, protože by překročil rozpočet studie.");
    expect(screen.getByText(/Ověření podkladů:/).textContent).toContain("AIA k tomuto záznamu zatím nemá popis.");
    expect(screen.getByText("gate:novel").closest("details")).toBeTruthy();
    expect(screen.queryByText(/budget_exceeded|investigate\/web-1/)).toBeNull();
  });

  it("asks before a Deep Research start the study's limit holds, with what remains of its budget, and sends the yes (6d)", async () => {
    const path = "/api/v1/studies/STU-1/deep-research/runs";
    const job = { run_id: "RUN-a1", design_revision_id: "REV-A", preset: "QUICK", channels: ["WEB"], status: "QUEUED", phase: "QUEUED", is_terminal: false, needs_attention: false, retryable: false, created_at: null, steps: [], actual_cost_usd: null };
    let started = false;
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } }, null, {
      [path]: (body) => {
        if (!body) return started ? [job] : [];
        if (!(body as { confirm_cost_usd?: number }).confirm_cost_usd) {
          return new Response(JSON.stringify({ code: "cost_confirmation_required", message: "confirm", details: { ceiling_usd: 4, limit_usd: 2 } }), { status: 409 });
        }
        started = true;
        return job;
      },
      "/api/v1/studies/STU-1": () => ({ study_id: "STU-1", budget_usd: 10, spent_usd: 7, remaining_usd: 3 }),
    });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Spustit veřejný výzkum" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Výzkum může stát nejvýše 4.00 USD. Čerpá rozpočet této studie. Spustit? Z rozpočtu studie zbývá 3.00 USD. To je víc, než nyní zbývá: přesáhne-li skutečná cena zbytek, krok se zastaví, dokud rozpočet nezvýšíte.")).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "OK" }));
    await waitFor(() => expect(posted(path).map((c) => (c.body as { confirm_cost_usd?: number }).confirm_cost_usd)).toEqual([undefined, 4]));
  });

  const IMPORT_PATH = "/api/v1/studies/STU-1/workspace/questionnaire-import";
  const TEMPLATE_PATH = "/api/v1/studies/STU-1/workspace/questionnaire-template";

  it("imports a file in AIA, puts its sections on the questionnaire and saves", async () => {
    unitStub(
      { ...BRIEF, title: "Moje studie", ui_state: { questionnaire_path: "upload" } },
      null,
      { [IMPORT_PATH]: () => ({ sections: SECTIONS, summary: { question_count: 2, tracked_sets: 1, sections: 2 }, filename: "dotaznik.xlsx" }) },
    );
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.change(await screen.findByLabelText("Vyplněný XLSX / CSV"), { target: { files: [new File(["x"], "dotaznik.xlsx")] } });
    expect(await screen.findByText("Načteno: 2 otázky · 1 sledovaná sada")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "2 otázky · 1 sledovaná sada" })).toBeTruthy();
    // AIA is sent the file alone, never the project, and nothing reaches the unit.
    expect(posted(IMPORT_PATH).map((c) => c.body)).toEqual([{ filename: "dotaznik.xlsx", data_b64: btoa("x") }]);
    expect(calls.filter((c) => c.url.startsWith("/api/questionnaire"))).toEqual([]);
    await saved();
    const body = saves.at(-1) as unknown as { reason: string; content: Record<string, unknown> & { research_plan: { status: string }; ui_state: Record<string, unknown> } };
    expect(body.reason).toBe("questionnaire_import");
    expect(body.content.sections).toEqual(SECTIONS);
    expect(body.content.research_plan.status).toBe("questionnaire_ready");
    expect(body.content.ui_state.questionnaire_path).toBe("manual");
    // The rest of the project is the person's own.
    expect(body.content.title).toBe("Moje studie");
  });

  it("says a file replaces the questionnaire there is, and takes the import back with Vrátit (QF-15)", async () => {
    const mine = [{ id: "sec_m", type: "questions", title: "Moje", purpose: "", questions: [{ id: "Q9", text: "Moje otázka?", typ: "otevrena" }] }];
    const loaded = [{ id: "sec_l", type: "questions", title: "Ze souboru", purpose: "", questions: [{ id: "Q1", text: "Ze souboru?", typ: "otevrena" }, { id: "Q2", text: "Také?", typ: "otevrena" }] }];
    unitStub(
      { ...BRIEF, sections: mine, research_plan: { status: "draft", objectives: ["Cíl"] }, ui_state: { questionnaire_path: "upload" } },
      null,
      { [IMPORT_PATH]: () => ({ sections: loaded, summary: { question_count: 2, tracked_sets: 0, sections: 1 }, filename: "dotaznik.xlsx" }) },
    );
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    expect(await screen.findByText("Načtený soubor nahradí současný dotazník. Hned potom ho půjde vrátit.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Vyplněný XLSX / CSV"), { target: { files: [new File(["x"], "dotaznik.xlsx")] } });
    const toast = (await screen.findByText("Načteno: 2 otázky · 0 sledovaných sad")).closest("[role=status]") as HTMLElement;
    expect(screen.getByRole("heading", { name: "2 otázky · 0 sledovaných sad" })).toBeTruthy();
    fireEvent.click(within(toast).getByRole("button", { name: "Vrátit" }));
    expect(await screen.findByRole("heading", { name: "1 otázka · 0 sledovaných sad" })).toBeTruthy();
    await waitFor(() => expect((saves.at(-1) as unknown as { reason: string }).reason).toBe("questionnaire_import_undone"));
    const body = saves.at(-1) as unknown as { content: { sections: unknown; research_plan: Record<string, unknown>; ui_state: Record<string, unknown> } };
    expect(body.content.sections).toEqual(mine);
    // Only the status the import set goes back: the rest of the plan is as it now is.
    expect(body.content.research_plan.status).toBe("draft");
    expect(body.content.research_plan.objectives).toEqual(["Cíl"]);
    expect(body.content.ui_state.questionnaire_path).toBe("upload");
  });

  it("never takes an import back over a change made since, and says so", async () => {
    const mine = [{ id: "sec_m", type: "questions", title: "Moje", purpose: "", questions: [] }];
    unitStub(
      { ...BRIEF, sections: mine, ui_state: { questionnaire_path: "upload" } },
      null,
      { [IMPORT_PATH]: () => ({ sections: SECTIONS, summary: {}, filename: "dotaznik.xlsx" }) },
    );
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    // A block with no questions yet is a questionnaire a file would replace.
    expect(await screen.findByText("Načtený soubor nahradí současný dotazník. Hned potom ho půjde vrátit.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Vyplněný XLSX / CSV"), { target: { files: [new File(["x"], "dotaznik.xlsx")] } });
    const toast = (await screen.findByText("Načteno: 2 otázky · 1 sledovaná sada")).closest("[role=status]") as HTMLElement;
    // A question's wording changed after the import, then Vrátit.
    fireEvent.change(screen.getAllByRole("textbox", { name: "Znění otázky" })[0]!, { target: { value: "Upraveno po načtení?" } });
    fireEvent.click(within(toast).getByRole("button", { name: "Vrátit" }));
    expect(await screen.findByText("Dotazník se od načtení změnil, import už se nevrátí.")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "2 otázky · 1 sledovaná sada" })).toBeTruthy();
  });

  it("shows why a file did not import, in the words AIA gave", async () => {
    unitStub({ ...BRIEF, ui_state: { questionnaire_path: "upload" } }, null, {
      [IMPORT_PATH]: () => new Response(JSON.stringify({ code: "missing_columns", message: "Chybí povinné sloupce: typ" }), { status: 422 }),
    });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.change(await screen.findByLabelText("Vyplněný XLSX / CSV"), { target: { files: [new File(["x"], "dotaznik.csv")] } });
    expect((await screen.findByRole("alert")).textContent).toBe("Chybí povinné sloupce: typ");
    expect(saves).toEqual([]);
  });

  it("says an empty file, a refusal without words of its own and a lost connection in Czech, never the API's English", async () => {
    let answer: () => Response = () => new Response(JSON.stringify({ code: "validation_error", message: "The request body or parameters are invalid." }), { status: 422 });
    unitStub({ ...BRIEF, ui_state: { questionnaire_path: "upload" } }, null, { [IMPORT_PATH]: () => answer() });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    const pick = async (f: File) => fireEvent.change(await screen.findByLabelText("Vyplněný XLSX / CSV"), { target: { files: [f] } });
    // An empty file is refused before it is sent (the API's 422 for it is English).
    await pick(new File([], "prazdny.csv"));
    expect((await screen.findByRole("alert")).textContent).toBe("prazdny.csv: soubor je prázdný");
    expect(posted(IMPORT_PATH)).toEqual([]);
    await pick(new File(["x"], "dotaznik.csv"));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("dotaznik.csv: AIA soubor nepřijala (kód validation_error)"));
    answer = () => {
      throw new TypeError("Failed to fetch");
    };
    await pick(new File(["x"], "dotaznik.csv"));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("dotaznik.csv: Spojení s AIA se nepodařilo; zkuste to znovu"));
    // A file the browser cannot read was never sent, so no connection is blamed.
    const sent = posted(IMPORT_PATH).length;
    const gone = new File(["x"], "smazany.csv");
    gone.arrayBuffer = () => Promise.reject(new DOMException("gone", "NotReadableError"));
    await pick(gone);
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("smazany.csv: soubor se nepodařilo přečíst; vyberte ho znovu"));
    expect(posted(IMPORT_PATH)).toHaveLength(sent);
    expect(saves).toEqual([]);
  });

  it("says a template the API would not give in Czech, by its code", async () => {
    unitStub({ ...BRIEF, ui_state: { questionnaire_path: "upload" } }, null, {
      [TEMPLATE_PATH]: () => new Response(JSON.stringify({ code: "study_not_open", message: "Your role on this study does not permit that." }), { status: 403 }),
    });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Stáhnout XLSX šablonu" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Šablonu se nepodařilo stáhnout (kód study_not_open)");
  });

  it("downloads AIA's template through the study, and links to nothing of the unit's", async () => {
    const created: Blob[] = [];
    const clicked = vi.fn();
    const real = { create: URL.createObjectURL, revoke: URL.revokeObjectURL, click: HTMLAnchorElement.prototype.click };
    URL.createObjectURL = (b: Blob) => (created.push(b), "blob:t");
    URL.revokeObjectURL = () => {};
    HTMLAnchorElement.prototype.click = clicked;
    onTestFinished(() => {
      URL.createObjectURL = real.create;
      URL.revokeObjectURL = real.revoke;
      HTMLAnchorElement.prototype.click = real.click;
    });
    unitStub({ ...BRIEF, ui_state: { questionnaire_path: "upload" } }, null, {
      [TEMPLATE_PATH]: () => new Response("PK-template", { status: 200 }),
    });
    const { container } = render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Stáhnout XLSX šablonu" }));
    await waitFor(() => expect(clicked).toHaveBeenCalledTimes(1));
    expect(new TextDecoder().decode(await created[0].arrayBuffer())).toBe("PK-template");
    // No link into the unit's paths: the template and the guide are AIA's.
    const hrefs = [...container.querySelectorAll("a")].map((a) => a.getAttribute("href") || "");
    expect(hrefs.filter((h) => h.startsWith("/api/questionnaire") || h.startsWith("/files/"))).toEqual([]);
    expect(screen.queryByText("Metodika pro externí AI")).toBeNull();
  });

  it("reviews the native brief analysis and questionnaire before opening the editor", async () => {
    const sig = briefFingerprint(defaultsMerge(BRIEF, TEMPLATE));
    unitStub({ ...BRIEF, ui_state: { questionnaire_path: "ai" } }, { objectives: ["O"], _brief_signature: sig });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Sestavit první verzi dotazníku" }));
    await approveProposal();
    expect(await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" })).toBeTruthy();
    expect(posted("/api/research/analyze")).toEqual([]);
    expect(posted(AGENTS_PATH).map((c) => (c.body as { action: string }).action)).toEqual(["build_questionnaire"]);
    expect(posted("/api/research/build_questionnaire")).toEqual([]);
  });

  it("builds the questionnaire once its analysis, waiting for budget, is lifted and accepted: the analysis is not asked again (CR-2)", async () => {
    let lifted = false;
    const waiting = { run_id: "RUN-A", design_revision_id: "REV-A", action: "analyze_brief", status: "AWAITING_BUDGET", is_terminal: false, needs_attention: true,
      steps: [{ step_id: "STEP-A", node_key: "agent", status: "AWAITING_BUDGET", waiting_reason: "budget_exceeded", error_message: null }],
      created_at: null, context_sha256: "sha", harness_version: "v1", actual_cost_usd: null };
    unitStub({ ...BRIEF, ui_state: { questionnaire_path: "ai" } }, null, {
      "native/job": () => (lifted ? undefined : waiting),
      [`${AGENTS_PATH}/RUN-A/budget`]: () => { lifted = true; return { ...waiting, status: "RUNNING", steps: [{ ...waiting.steps[0], status: "RUNNABLE" }] }; },
      "/api/v1/studies/STU-1": () => ({ study_id: "STU-1", name: "Alfa", budget_usd: 5, spent_usd: 5, remaining_usd: 0 }),
    });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Sestavit první verzi dotazníku" }, NATIVE_JOB_WAIT));
    const form = await screen.findByRole("form", { name: "Zvýšit rozpočet studie" }, NATIVE_JOB_WAIT);
    expect(screen.queryByRole("button", { name: "Zkusit znovu" })).toBeNull();
    await within(form).findByText(/5\.00/);
    fireEvent.change(within(form).getByLabelText("Nový rozpočet studie (USD)"), { target: { value: "9" } });
    fireEvent.click(within(form).getByRole("button", { name: "Zvýšit rozpočet a pokračovat" }));
    await approveProposal(); // the analysis
    await waitFor(() => expect(posted(AGENTS_PATH)).toHaveLength(2), NATIVE_JOB_WAIT);
    await approveProposal(); // the build that waited behind it
    expect(await screen.findByRole("heading", { name: "2 otázky · 1 sledovaná sada" }, NATIVE_JOB_WAIT)).toBeTruthy();
    expect(posted(AGENTS_PATH).map((c) => (c.body as { action: string }).action)).toEqual(["analyze_brief", "build_questionnaire"]);
  });

  it("parks the build at the native runtime boundary", async () => {
    unitStub({ ...BRIEF, ui_state: { questionnaire_path: "ai" } }, null, { "native/job": () => ({ status: "WAITING_PROVIDER", is_terminal: false, needs_attention: true, steps: [{ error_message: PARK_MESSAGE }], run_id: "RUN-A" }) });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Sestavit první verzi dotazníku" }));
    expect(await screen.findByText(PARK_MESSAGE, {}, NATIVE_JOB_WAIT)).toBeTruthy();
    expect(posted("/api/research/build_questionnaire")).toEqual([]);
  });

  it("reviews native optimization without asking for a legacy provider connection", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } }, null);
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click((await screen.findAllByRole("button", { name: "Optimalizovat dotazník s AI" }))[0]);
    await approveProposal();
    await waitFor(() => expect(posted(`${AGENTS_PATH}/RUN-A/accept`)).toHaveLength(1));
    expect(posted("/api/providers/claude-code/status")).toEqual([]);
    expect(posted(AGENTS_PATH)[0].body).toMatchObject({ action: "optimize_questionnaire" });
    expect(posted("/api/questionnaire/optimize")).toEqual([]);
  });

  it("inside the workbench goes on to the audience through the frame's next stage", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    const go = vi.fn();
    render(<FrameNavigation.Provider value={{ next: { label: "Cílová skupina", go } }}><ResearchScreen step="questionnaire" frame={TEST_FRAME} /></FrameNavigation.Provider>);
    fireEvent.click(await screen.findByRole("button", { name: /Další · cílová skupina/ }));
    expect(go).toHaveBeenCalledTimes(1);
    expect(push).not.toHaveBeenCalled();
    await saved();
    expect(lastSave()).toMatchObject({ reason: "questionnaire_done" });
  });

  it("goes on to the audience at its first choice", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /Další · cílová skupina/ }));
    expect(push).toHaveBeenCalledWith(stagePath("audience"));
    await saved();
    expect(lastSave()).toMatchObject({ reason: "questionnaire_done", content: { ui_state: { audience_entry: "choose" } } });
  });

  it("opens the outline's place and moves focus there, from the preview too (QF-6)", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /^Q2/ }));
    await waitFor(() => expect(document.activeElement?.id).toBe("qedit_Q2"));
    // The preview draws no editor: the outline opens Upravit, then the place.
    fireEvent.click(screen.getByRole("radio", { name: "Náhled respondenta" }));
    expect(document.getElementById("qedit_Q1")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /^S1/ }));
    await waitFor(() => expect(document.activeElement?.id).toBe("qset_sec_b"));
    expect((screen.getByRole("radio", { name: "Upravit" }) as HTMLElement).getAttribute("aria-checked")).toBe("true");
  });

  it("says what Sestavit s AI does once the questionnaire has items, and claims no provider choice (QF-4, QF-5)", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("radio", { name: "Sestavit s AI" }));
    expect(await screen.findByText("Dotazník už má otázky, takže ho AI znovu nesestaví: úpravy navrhne „Optimalizovat dotazník s AI“.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Optimalizovat dotazník s AI" })).toBeTruthy();
    fireEvent.click(screen.getByRole("radio", { name: "Náhled respondenta" }));
    expect(screen.queryByText(/technický editor je pod ní/)).toBeNull();
    expect(screen.getByText(/Upravíte je v režimu Upravit/)).toBeTruthy();
    cleanup();
    unitStub({ ...BRIEF, ui_state: { questionnaire_path: "ai" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    expect(await screen.findByRole("heading", { name: "Dotazník s AI" })).toBeTruthy();
    expect(screen.queryByText(/Provider\/model/)).toBeNull();
  });
});
