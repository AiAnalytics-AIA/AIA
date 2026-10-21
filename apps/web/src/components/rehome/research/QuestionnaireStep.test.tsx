// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from "vitest";

import { AGENTS_PATH, NATIVE_JOB_WAIT, NATIVE_TEST_TIMEOUT_MS, PARK_MESSAGE, approveProposal, nativeAgentFixture } from "./test-native-agents";
import { briefFingerprint, defaultsMerge } from "@/research/model";
import { GUIDED_PROMPT, PROMPT_SET_ITEMS, PROMPT_SET_TYPE, SET_SIZE, SET_TOO_SMALL } from "@/research/questionnaire";
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

async function answerDialog(question: string, value: string | null) {
  const form = (await screen.findByText(question)).closest("form") as HTMLFormElement;
  if (value === null) return fireEvent.click(within(form).getByRole("button", { name: "Zrušit" }));
  const input = within(form).queryByRole("textbox");
  if (input) fireEvent.change(input, { target: { value } });
  fireEvent.submit(form);
}
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

  it("draws the preview and the editor, and has no dead 'AI: zlepšit blok' (OI-49)", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    expect(await screen.findByRole("heading", { name: "2 otázek · 1 sledovaných sad" })).toBeTruthy();
    // The outline lists blocks, questions and sets; the preview is the editor's other tab.
    expect(screen.getAllByRole("button", { name: /^(B1|Q1|Q2|S1)/ }).map((b) => b.textContent)).toEqual(["B1Hlavní otázky", "Q1Jak často?", "Q2Jak moc?", "S1Sledovaná sada — média"]);
    fireEvent.click(screen.getByRole("radio", { name: "Náhled respondenta" }));
    const preview = screen.getByRole("region", { name: "Jak bude dotazník přibližně vypadat" });
    expect(within(preview).getByText("Otázka 1")).toBeTruthy();
    expect(within(preview).getByText("Sledovaná sada 3 · Sledovaná sada — média")).toBeTruthy();
    expect(within(preview).getAllByText("Jak často používáte TV?").length).toBe(1);
    expect(screen.queryByText(/zlepšit blok/)).toBeNull();
    expect((screen.getByRole("button", { name: /Další · cílová skupina/ }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("marks a question without wording where it is, and lists it beside the questionnaire", async () => {
    const sections = structuredClone(SECTIONS) as { questions?: { text?: string }[] }[];
    sections[0]!.questions![1]!.text = "";
    unitStub({ ...BRIEF, sections, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázek · 1 sledovaných sad" });
    const unworded = screen.getAllByRole("textbox", { name: "Znění otázky" }).find((x) => x.getAttribute("aria-invalid") === "true")!;
    expect(document.getElementById(unworded.getAttribute("aria-describedby")!)?.textContent).toBe("Doplňte znění. Bez něj návrh nejde spustit.");
    const ready = screen.getByRole("region", { name: "Dotazník" });
    expect(within(ready).getByRole("button", { name: /Otázky bez znění: 1/ })).toBeTruthy();
  });

  it("shows a question's display condition from 18.6.6 and removes it, so the run can start (PC15)", async () => {
    const sections = structuredClone(SECTIONS) as { questions?: Record<string, unknown>[] }[];
    sections[0]!.questions![1]!.filtr = "Q1 == 'Denně'";
    unitStub({ ...BRIEF, sections, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázek · 1 sledovaných sad" });
    const card = document.getElementById("qedit_Q2") as HTMLElement;
    expect(within(card).getByText(/„Q1 == 'Denně'“/)).toBeTruthy();
    expect(document.getElementById("qedit_Q1")!.querySelector("[data-question-condition]")).toBeNull();
    fireEvent.click(within(card).getByRole("button", { name: "Odebrat podmínku" }));
    expect(card.querySelector("[data-question-condition]")).toBeNull();
    await saved();
    const question = (lastSave().content.sections[0]!.questions as Record<string, unknown>[] | undefined)![1]!;
    expect("filtr" in question).toBe(false);
    expect(question.text).toBe("Jak moc?");
  });

  it("edits a question as the classic editor does: type, options and a scale", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázek · 1 sledovaných sad" });
    const card = document.getElementById("qedit_Q1") as HTMLElement;
    // Options are rows: Enter adds one below, and the list is applied when it is left.
    const options = within(card).getByRole("group", { name: "Možnosti — jedna na řádek" });
    fireEvent.change(within(options).getByLabelText("Možnost 1"), { target: { value: " Denně " } });
    fireEvent.keyDown(within(options).getByLabelText("Možnost 2"), { key: "Enter" });
    fireEvent.change(within(options).getByLabelText("Možnost 3"), { target: { value: "Nikdy " } });
    fireEvent.blur(within(options).getByLabelText("Možnost 3"), { relatedTarget: null });
    fireEvent.click(within(within(card).getByRole("radiogroup", { name: "Typ" })).getByRole("radio", { name: "Škála" }));
    expect(await within(card).findByLabelText("Minimum")).toBeTruthy();
    await saved();
    const q1 = lastSave().content.sections[0].questions![0];
    expect(q1).toMatchObject({ typ: "skala", kategorie: ["Denně", "Týdně", "Nikdy"] });
  });

  it("says which research question a question and a set measure, and drops a link the plan no longer states", async () => {
    const plan = { research_questions: ["Jak často lidé pijí kávu?", "Která média lidé používají?"] };
    const sections = [{ ...SECTIONS[0], questions: [{ ...SECTIONS[0].questions![0], research_questions: ["Stará otázka?"] }, SECTIONS[0].questions![1]] }, SECTIONS[1]];
    unitStub({ ...BRIEF, research_plan: plan, sections, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "2 otázek · 1 sledovaných sad" });
    const card = document.getElementById("qedit_Q1") as HTMLElement;
    const links = within(card).getByRole("group", { name: "Odpovídá na výzkumné otázky" });
    fireEvent.click(within(links).getByRole("button", { name: "Odebrat odkaz na „Stará otázka?“" }));
    fireEvent.click(within(links).getByRole("button", { name: "Jak často lidé pijí kávu?" }));
    expect(within(links).getByRole("button", { name: "Jak často lidé pijí kávu?" }).getAttribute("aria-pressed")).toBe("true");
    const set = document.getElementById("qset_sec_b") as HTMLElement;
    fireEvent.click(within(within(set).getByRole("group", { name: "Odpovídá na výzkumné otázky" })).getByRole("button", { name: "Která média lidé používají?" }));
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
    const media = within(panel).getByLabelText("Způsob odpovědi na „Která média lidé používají?“") as HTMLSelectElement;
    expect(media.value).toBe("");
    fireEvent.change(media, { target: { value: "rank_objects" } });
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
    await screen.findByRole("heading", { name: "2 otázek · 1 sledovaných sad" });
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

  it("adds a guided question through the classic prompt, and refuses a set of three", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Škála 1–10" }));
    await answerDialog(GUIDED_PROMPT.scale, "Jak moc vám chutná?");
    expect((await screen.findAllByText("Jak moc vám chutná?")).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "3 otázek · 1 sledovaných sad" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Sledovaná sada" }));
    await answerDialog(PROMPT_SET_TYPE, "značky");
    await answerDialog(PROMPT_SET_ITEMS, "A, B, C");
    expect(await screen.findByText(SET_SIZE)).toBeTruthy();
  });

  it("notes a set under four objects, and removes a block only when confirmed", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    // Objects are chips; updateObjects notes a set under four.
    fireEvent.click(await screen.findByRole("button", { name: "Odebrat Tisk" }));
    expect(await screen.findByText(SET_TOO_SMALL)).toBeTruthy();
    expect(screen.getByText("3 / 4–15")).toBeTruthy();
    // Removal is confirmed on the card.
    fireEvent.click(screen.getAllByRole("button", { name: "Smazat" })[1]);
    expect(screen.getByRole("alertdialog").textContent).toContain("Odstranit tuto sadu?");
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Smazat" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "2 otázek · 0 sledovaných sad" })).toBeTruthy());
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
    expect(await screen.findByText("Načteno: 2 otázek · 1 sledovaných sad")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "2 otázek · 1 sledovaných sad" })).toBeTruthy();
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

  it("shows why a file did not import, in the words AIA gave", async () => {
    unitStub({ ...BRIEF, ui_state: { questionnaire_path: "upload" } }, null, {
      [IMPORT_PATH]: () => new Response(JSON.stringify({ code: "missing_columns", message: "Chybí povinné sloupce: typ" }), { status: 422 }),
    });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.change(await screen.findByLabelText("Vyplněný XLSX / CSV"), { target: { files: [new File(["x"], "dotaznik.csv")] } });
    expect((await screen.findByRole("alert")).textContent).toBe("Chybí povinné sloupce: typ");
    expect(saves).toEqual([]);
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
    expect(await screen.findByRole("heading", { name: "2 otázek · 1 sledovaných sad" })).toBeTruthy();
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
    expect(await screen.findByRole("heading", { name: "2 otázek · 1 sledovaných sad" }, NATIVE_JOB_WAIT)).toBeTruthy();
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

  it("goes on to the audience at its first choice", async () => {
    unitStub({ ...BRIEF, sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /Další · cílová skupina/ }));
    expect(push).toHaveBeenCalledWith(stagePath("audience"));
    await saved();
    expect(lastSave()).toMatchObject({ reason: "questionnaire_done", content: { ui_state: { audience_entry: "choose" } } });
  });
});
