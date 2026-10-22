// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from "vitest";

import { AGENTS_PATH, DESIGN_PATH, NATIVE_JOB_WAIT, NATIVE_TEST_TIMEOUT_MS, approveProposal, nativeAgentFixture } from "./test-native-agents";
import { briefFingerprint, defaultsMerge } from "@/research/model";
import { ResearchScreen } from "./ResearchScreen";
import { workspaceFixture } from "./test-workspace";
import { TEST_FRAME, stagePath } from "./test-frame";

// Native jobs need more than vitest's 5 s under CI load (test-native-agents.ts).
vi.setConfig({ testTimeout: NATIVE_TEST_TIMEOUT_MS });

const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/plan", useRouter: () => ({ push, replace }) }));

const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/research/fixtures/empty-project.json"), "utf8"));
const TEMPLATE = { empty_project: EMPTY };
const PROJECT = { goal: "Zjistit zájem o nový nápoj", briefing: { what_is_known: "Víme A." } };
const ANALYSIS = {
  problem_summary: "Jde o test nového konceptu.",
  objectives: ["Změřit zájem"],
  hypotheses: ["Mírnější varianta vyhraje"],
  tracked_sets: [{ title: "Varianty nápoje", object_type: "varianta", objects: ["Jemná", "Silná"], object_question: "Jak vás oslovuje {object}?" }],
  questions_for_user: ["Jen MHD?"],
  project_variants: [
    { id: "focused", title: "Jen varianty", summary: "Úzce", n: 300, complexity: "light", objectives: ["Porovnat varianty"] },
    { id: "recommended", title: "Varianty a cena", summary: "Doporučeno", n: 600 },
  ],
  _brief_signature: briefFingerprint(defaultsMerge(PROJECT, TEMPLATE)),
};

/** The readiness limits in force (RQC9): what a variant's n is held to. */
const LIMITS_PATH = "/api/v1/studies/STU-1/research/limits";
const LIMITS = { methodology_version: "aia-readiness-1", version: null, sample_size: { min: 20, max: 10000 } };

type Call = { url: string; body: Record<string, unknown> | null };
let calls: Call[] = [];
function unitStub(analysis: unknown = ANALYSIS, over: Record<string, (b: unknown) => unknown> = {}, project: Record<string, unknown> = PROJECT) {
  calls = [];
  const ws = workspaceFixture(project, { analysis: analysis });
  const native = nativeAgentFixture((_action, baseline) => ({ project: { ...baseline, research_plan: { ...ANALYSIS, problem_summary: "Nové shrnutí." } }, proposal: { ...ANALYSIS, problem_summary: "Nové shrnutí." }, analysis: { ...ANALYSIS, problem_summary: "Nové shrnutí." } }), over, ws.write);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ url: u, body });
      const answers: Record<string, (b: unknown) => unknown> = { [LIMITS_PATH]: () => LIMITS, ...over };
      const answer = native(u.split("?")[0], init?.method ?? "GET", body) ?? ws.answer(u.split("?")[0], init?.method ?? "GET", body) ?? answers[u.split("?")[0]]?.(body);
      if (answer === undefined) return new Response(JSON.stringify({ code: "not_found", message: "No such resource." }), { status: 404 });
      return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
    }),
  );
  return ws;
}
const posted = (path: string) => calls.filter((c) => c.url.split("?")[0] === path && (!path.startsWith("/api/v1/") || c.body !== null));

/** Every test here also proves the screen reached nothing of the 18.6.6 unit (ADR 0018). */
const unitCalls = () => calls.filter((c) => !c.url.startsWith("/api/v1/") && c.url !== "/config").map((c) => c.url);

beforeEach(() => {
  push.mockReset();
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  expect(unitCalls()).toEqual([]);
});

describe("Návrh", () => {
  it("without an analysis says so, and offers the brief and the questionnaire", async () => {
    unitStub(null);
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    expect(await screen.findByText("Zatím není návrh")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Otevřít zadání" }));
    expect(push).toHaveBeenCalledWith(stagePath("brief"));
    expect(screen.queryByRole("region", { name: /Označte text a přidejte komentář/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Přeskočit na dotazník" }));
    expect(push).toHaveBeenCalledWith(stagePath("questionnaire"));
  });

  it("draws the analysis, its sets with the question preview, the follow-ups and the comments", async () => {
    unitStub();
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    expect(await screen.findByRole("heading", { name: "Zkontrolujte, jak AI pochopila zadání" })).toBeTruthy();
    expect(screen.getByText("Jde o test nového konceptu.")).toBeTruthy();
    expect(screen.getByText("Mírnější varianta vyhraje")).toBeTruthy();
    expect(screen.getByText("Jak vás oslovuje Jemná?")).toBeTruthy();
    // Two items: under the 4–15 a set is measured with, and the dock says so.
    expect(screen.getByText("2 / 4–15")).toBeTruthy();
    expect(screen.getByText(/má 2 položek, potřebuje 4–15/)).toBeTruthy();
    expect(screen.getByText("Jen MHD?")).toBeTruthy();
    const process = screen.getByRole("button", { name: "Zpracovat komentáře" }) as HTMLButtonElement;
    expect(process.disabled).toBe(true);
    expect(process.getAttribute("data-ai-action")).toBe("true");
    // The recommended variant is the chosen one until another is applied.
    expect(screen.getByRole("radio", { name: /Varianty a cena/ }).getAttribute("aria-checked")).toBe("true");
    // Jump chips over the sections.
    const jump = screen.getByRole("navigation", { name: "Oddíly návrhu" });
    expect(within(jump).getAllByRole("button").map((b) => b.textContent)).toEqual(["Rozsah", "Porozumění", "Sady · 1", "Otázky AI · 0/1", "Komentáře · 0"]);
  });

  it("opens on the research questions a link from the Run stage names", async () => {
    // research-integrity-report 14: a design with no research question is fixed here.
    const seen: string[] = [];
    const original = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = function (this: Element) {
      seen.push(this.id);
    };
    window.history.replaceState(null, "", "#plan-understanding");
    onTestFinished(() => {
      Element.prototype.scrollIntoView = original;
      window.history.replaceState(null, "", "/");
    });
    unitStub();
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    await waitFor(() => expect(seen).toEqual(["plan-understanding"]));
    // Keyboard focus moves there too (review web#7).
    await waitFor(() => expect(document.activeElement?.id).toBe("plan-understanding"));
  });

  it("applies a design variant to the project", async () => {
    unitStub();
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    const radio = await screen.findByRole("radio", { name: /Jen varianty/ });
    await waitFor(() => {
      fireEvent.click(radio); // applied once the valid range is read (RQC9)
      expect(screen.getByText("Použit návrh: Jen varianty")).toBeTruthy();
    });
    expect(screen.getByRole("radio", { name: /Jen varianty/ }).getAttribute("aria-checked")).toBe("true");
    expect(screen.getByText("Použit návrh: Jen varianty")).toBeTruthy();
    expect(screen.getByText("Porovnat varianty")).toBeTruthy();
  });

  it("applies a variant whose n the valid range refuses without its n, and says so", async () => {
    unitStub(ANALYSIS, { [LIMITS_PATH]: () => ({ ...LIMITS, version: 3, sample_size: { min: 400, max: 500 } }) }, { ...PROJECT, n: 450 });
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    // Until the range is read, nothing is applied; the click is repeated until it is.
    const radio = await screen.findByRole("radio", { name: /Jen varianty/ });
    await waitFor(() => {
      fireEvent.click(radio);
      expect(screen.getByText(/Použit návrh: Jen varianty\. Velikost vzorku z návrhu nebyla uložena: Počet respondentů musí být od 400 do 500/)).toBeTruthy();
    });
    expect(screen.getByText("Porovnat varianty")).toBeTruthy();
  });

  it("adds, renames and fills a set in place, removes an object, and removes a set only when confirmed", async () => {
    unitStub();
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    // Each set's title is edited in place (I1): its button shows it.
    const names = () => screen.queryAllByRole("button", { name: /^Upravit: Název sady/ }).map((b) => b.querySelector("span")!.textContent);
    fireEvent.click(await screen.findByRole("button", { name: "Přidat sadu" }));
    const title = screen.getByPlaceholderText("Např. Značky, Regiony, Argumenty…");
    fireEvent.change(title, { target: { value: "Kraje" } });
    fireEvent.click(screen.getByRole("button", { name: "Založit sadu" }));
    await waitFor(() => expect(names()).toContain("Kraje"));
    expect(screen.getByText("Geografické kategorie")).toBeTruthy();
    // Items are typed into the set's chip input, through addPlanObject.
    const items = screen.getAllByLabelText("Přidat položku a Enter")[1];
    for (const v of ["Praha", "Brno"]) {
      fireEvent.change(items, { target: { value: v } });
      fireEvent.keyDown(items, { key: "Enter" });
    }
    expect(await screen.findByRole("button", { name: "Odebrat Brno" })).toBeTruthy();
    // A repeated item is refused at the chip and stays typed there (I9).
    fireEvent.change(items, { target: { value: "praha" } });
    fireEvent.keyDown(items, { key: "Enter" });
    expect(await screen.findByText("Tato položka už v sadě je.")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /^Odebrat Praha/ })).toHaveLength(1);
    // Renamed in place, through renamePlanSet, when the field is left.
    fireEvent.click(screen.getByRole("button", { name: "Upravit: Název sady Kraje" }));
    const kraje = screen.getByRole("textbox", { name: "Název sady" });
    fireEvent.change(kraje, { target: { value: "Regiony" } });
    fireEvent.blur(kraje);
    await waitFor(() => expect(names()).toContain("Regiony"));
    fireEvent.click(screen.getByRole("button", { name: "Odebrat Jemná" }));
    expect(screen.queryByText("Jak vás oslovuje Jemná?")).toBeNull();
    // Removal is confirmed on the card: "Ponechat" keeps it.
    fireEvent.click(screen.getAllByRole("button", { name: "Odstranit sadu" })[1]);
    fireEvent.click(screen.getByRole("button", { name: "Ponechat" }));
    expect(names()).toContain("Regiony");
    fireEvent.click(screen.getAllByRole("button", { name: "Odstranit sadu" })[1]);
    fireEvent.click(screen.getByRole("button", { name: "Odstranit" }));
    await waitFor(() => expect(names()).not.toContain("Regiony"));
  });

  it("answers the follow-up questions into the brief and analyses it again", async () => {
    unitStub();
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Doplnit a aktualizovat návrh" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Napište odpovědi.");
    fireEvent.change(screen.getByLabelText("Odpověď na otázku 1"), { target: { value: "Ano, jen MHD." } });
    expect(screen.getByText("1 z 1 zodpovězeno")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Doplnit a aktualizovat návrh" }));
    await approveProposal();
    expect(await screen.findByText("Nové shrnutí.")).toBeTruthy();
    const [analyze] = posted(DESIGN_PATH);
    expect(((analyze.body?.content as { briefing: { what_is_known: string } }).briefing).what_is_known).toBe("Víme A.\n\nDoplnění k analýze:\nJen MHD?\nAno, jen MHD.");
    expect(push).not.toHaveBeenCalled();
  });

  describe("an analysis that waited for the study's budget (CR-2, Codex on #533)", () => {
    const waitingFor = () => {
      let lifted = false;
      const waiting = { run_id: "RUN-A", design_revision_id: "REV-A", action: "analyze_brief", status: "AWAITING_BUDGET", is_terminal: false, needs_attention: true,
        steps: [{ step_id: "STEP-A", node_key: "agent", status: "AWAITING_BUDGET", waiting_reason: "budget_exceeded", error_message: null }],
        created_at: null, context_sha256: "sha", harness_version: "v1", actual_cost_usd: null };
      return {
        "native/job": () => (lifted ? undefined : waiting),
        [`${AGENTS_PATH}/RUN-A/budget`]: () => { lifted = true; return { ...waiting, status: "RUNNING", steps: [{ ...waiting.steps[0], status: "RUNNABLE" }] }; },
        "/api/v1/studies/STU-1": () => ({ study_id: "STU-1", name: "Alfa", budget_usd: 5, spent_usd: 5, remaining_usd: 0 }),
      };
    };
    const liftAndAccept = async () => {
      const form = await screen.findByRole("form", { name: "Zvýšit rozpočet studie" }, NATIVE_JOB_WAIT);
      await within(form).findByText(/5\.00/);
      fireEvent.change(within(form).getByLabelText("Nový rozpočet studie (USD)"), { target: { value: "7" } });
      fireEvent.click(within(form).getByRole("button", { name: "Zvýšit rozpočet a pokračovat" }));
      await approveProposal();
    };

    it("keeps the comments' mode with the wait: the plan is marked as changed by them, and says so", async () => {
      unitStub(ANALYSIS, waitingFor());
      render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
      fireEvent.click(await screen.findByRole("button", { name: "Komentovat: Jde o test nového konceptu." }, NATIVE_JOB_WAIT));
      const draft = await screen.findByLabelText("Co změnit? Enter uloží komentář");
      fireEvent.change(draft, { target: { value: "Není to test." } });
      fireEvent.keyDown(draft, { key: "Enter" });
      fireEvent.click(screen.getByRole("button", { name: "Zpracovat komentáře" }));
      await liftAndAccept();
      expect(await screen.findByText("Upraveno podle vašich komentářů", {}, NATIVE_JOB_WAIT)).toBeTruthy();
      expect(await screen.findByText("Komentáře zapracovány", {}, NATIVE_JOB_WAIT)).toBeTruthy();
      expect(posted(AGENTS_PATH)).toHaveLength(1);
    });

    it("clears an earlier comments mark when a follow-up's analysis waited, as the follow-up itself does", async () => {
      unitStub(ANALYSIS, waitingFor(), { ...PROJECT, ui_state: { plan_changed26: true } });
      render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
      expect(await screen.findByText("Upraveno podle vašich komentářů", {}, NATIVE_JOB_WAIT)).toBeTruthy();
      fireEvent.change(screen.getByLabelText("Odpověď na otázku 1"), { target: { value: "Ano, jen MHD." } });
      fireEvent.click(screen.getByRole("button", { name: "Doplnit a aktualizovat návrh" }));
      await liftAndAccept();
      expect(await screen.findByText("Nové shrnutí.", {}, NATIVE_JOB_WAIT)).toBeTruthy();
      await waitFor(() => expect(screen.queryByText("Upraveno podle vašich komentářů")).toBeNull(), NATIVE_JOB_WAIT);
      expect(screen.queryByText("Komentáře zapracovány")).toBeNull();
      expect(posted(AGENTS_PATH)).toHaveLength(1);
    });
  });

  it("comments on selected text, then works the comments in with a forced analysis", async () => {
    unitStub();
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    // An item edited in place is a button, which a browser selects no text in: the narrative's
    // items are commented on by their own action, quoting the item whole (DSN3).
    fireEvent.click(await screen.findByRole("button", { name: "Komentovat: Jde o test nového konceptu." }));
    // The comment is typed on its row, not in a prompt; Enter keeps it.
    const draft = await screen.findByLabelText("Co změnit? Enter uloží komentář");
    fireEvent.change(draft, { target: { value: "Není to test." } });
    fireEvent.keyDown(draft, { key: "Enter" });
    expect(await screen.findByText("Není to test.")).toBeTruthy();
    expect(screen.getByText("„Jde o test nového konceptu.“")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Zpracovat komentáře" }));
    await approveProposal();
    expect(await screen.findByText("Upraveno podle vašich komentářů")).toBeTruthy();
    const [analyze] = posted(DESIGN_PATH);
    // The revised briefing is frozen in the native Design Revision.
    expect(((analyze.body?.content as { briefing: { review_comments: string } }).briefing).review_comments).toBe("1. K textu „Jde o test nového konceptu.“: Není to test.");
    expect(screen.queryByText("Není to test.")).toBeNull();
    // Set when the analysis resolves, after the plan above is drawn: waited for, never read at once.
    expect(await screen.findByText("Komentáře zapracovány", {}, NATIVE_JOB_WAIT)).toBeTruthy();
  });

  it("keeps objectives typed without an analysis when a set is added (#609's addSet finding, traced through Návrh)", async () => {
    // The Brief's goal edit drops the analysis; the plan keeps the objectives a person typed.
    const ws = unitStub(null, {}, { ...PROJECT, research_plan: { problem_summary: "Uložený problém", objectives: ["Zjistit bariéry"], research_questions: ["Proč nekupují?"] } });
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Přidat sadu" }));
    fireEvent.change(screen.getByPlaceholderText("Např. Značky, Regiony, Argumenty…"), { target: { value: "Kraje" } });
    fireEvent.click(screen.getByRole("button", { name: "Založit sadu" }));
    await waitFor(() => expect(ws.saves.length).toBeGreaterThan(0));
    // addSet starts an analysis from the goal only where it is called with none; Návrh passes the plan.
    expect(ws.saves.at(-1)?.content.research_plan).toMatchObject({ objectives: ["Zjistit bariéry"] });
    expect(ws.saves.at(-1)?.analysis).toMatchObject({ objectives: ["Zjistit bariéry"] });
    expect(screen.queryByText(PROJECT.goal)).toBeNull();
  });

  it("marks each narrative item for the Lead by its stable id: an objective as the Brief's own target", async () => {
    unitStub(null, {}, { ...PROJECT, research_plan: { problem_summary: "P", objectives: ["Cíl A"], research_questions: ["Kdo?"], hypotheses: ["H1"] } });
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    const item = (text: string) => screen.getByText(text).closest("li")!;
    await screen.findByText("Cíl A");
    expect(item("Cíl A").getAttribute("data-aia")).toMatch(/^objective:obj_/);
    expect(item("Kdo?").getAttribute("data-aia")).toMatch(/^rq:rq_/);
    expect(item("H1").getAttribute("data-aia")).toMatch(/^hypothesis:hyp_/);
  });

  it("still comments on text selected outside the narrative's items, such as a set's question", async () => {
    unitStub();
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    const text = (await screen.findByText("Jak vás oslovuje Jemná?")).firstChild as Text;
    // jsdom lays nothing out: a selection has no box of its own.
    Range.prototype.getBoundingClientRect = () => ({ left: 100, top: 200, width: 80, height: 16, right: 180, bottom: 216, x: 100, y: 200, toJSON: () => ({}) });
    const range = document.createRange();
    range.setStart(text, 0);
    range.setEnd(text, 15);
    window.getSelection()!.removeAllRanges();
    window.getSelection()!.addRange(range);
    fireEvent.mouseUp(text.parentElement!);
    fireEvent.click(await screen.findByRole("button", { name: "Přidat komentář" }));
    const draft = await screen.findByLabelText("Co změnit? Enter uloží komentář");
    fireEvent.change(draft, { target: { value: "Zkrátit." } });
    fireEvent.keyDown(draft, { key: "Enter" });
    expect(await screen.findByText("„Jak vás oslovuj“")).toBeTruthy();
  });

  it("goes on to the questionnaire at its three paths", async () => {
    unitStub();
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /Další · dotazník/ }));
    expect(push).toHaveBeenCalledWith(stagePath("questionnaire"));
  });
});


describe("direct proposal editing", () => {
  it("retains native saved sets when adding another set without a legacy analysis", async () => {
    const existing = { ...ANALYSIS.tracked_sets[0], objects: ["A", "B", "C", "D"] };
    const ws = unitStub(null, {}, { ...PROJECT, research_plan: { objectives: ["Saved objective"], tracked_sets: [existing] } });
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "Přidat sadu" }));
    const input = screen.getAllByLabelText("Název sady").find((e) => e.getAttribute("placeholder") !== "Název sady")!;
    fireEvent.change(input, { target: { value: "Nová sada" } });
    fireEvent.submit(input.closest("form")!);
    await waitFor(() => expect(ws.saves.length).toBeGreaterThan(0));
    const sets = (ws.saves.at(-1)!.content.research_plan as { tracked_sets: unknown[] }).tracked_sets;
    expect(sets).toHaveLength(2);
    expect(sets[0]).toEqual(existing);
  });

  it("shows a native saved plan without a legacy analysis and saves each narrative item edited in place to both representations", async () => {
    const ws = unitStub(null, {}, { ...PROJECT, research_plan: { problem_summary: "Uložený problém", objectives: ["Uložený cíl"], research_questions: ["Uložená otázka?"], status: "approved" } });
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    expect(await screen.findByText("Uložený cíl")).toBeTruthy();
    expect(screen.queryByText("Zatím není návrh")).toBeNull();
    // artifact-design DSN3: no separate editor; every item is edited where it is shown.
    expect(screen.queryByRole("button", { name: "Upravit text návrhu" })).toBeNull();
    const edit = (label: RegExp, name: string, value: string) => {
      fireEvent.click(screen.getByRole("button", { name: label }));
      const field = screen.getByRole("textbox", { name });
      fireEvent.change(field, { target: { value } });
      fireEvent.keyDown(field, { key: "Enter", ctrlKey: true });
    };
    edit(/^Upravit: Shrnutí výzkumného problému/, "Shrnutí výzkumného problému", "Upravený problém");
    edit(/^Upravit: Výzkumná otázka 1/, "Výzkumná otázka 1", "Nová otázka?");
    fireEvent.click(screen.getByRole("button", { name: "Přidat cíl" }));
    const row = screen.getByRole("textbox", { name: "Přidat cíl" });
    fireEvent.change(row, { target: { value: "Druhý cíl" } });
    fireEvent.keyDown(row, { key: "Enter" });
    await waitFor(() => expect(ws.saves.at(-1)?.content.research_plan).toMatchObject({ objectives: ["Uložený cíl", "Druhý cíl"] }));
    expect(ws.saves.at(-1)?.content.research_plan).toMatchObject({ problem_summary: "Upravený problém", research_questions: ["Nová otázka?"], status: "approved" });
    expect(ws.saves.at(-1)?.analysis).toMatchObject({ problem_summary: "Upravený problém", objectives: ["Uložený cíl", "Druhý cíl"] });
    expect(posted(DESIGN_PATH)).toEqual([]); // manual editing never pays for an AI task
  });

  it("refuses a repeat at the field, keeps the last objective, and takes a removal back with Vrátit", async () => {
    const ws = unitStub();
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    await screen.findByText("Mírnější varianta vyhraje");
    // The last objective stays: removing it is refused and nothing is saved.
    fireEvent.click(screen.getByRole("button", { name: "Odebrat: Změřit zájem" }));
    expect(await screen.findByText("Doplňte alespoň jeden cíl výzkumu.")).toBeTruthy();
    expect(screen.getByText("Změřit zájem")).toBeTruthy();
    // A hypothesis added twice is refused at the row.
    fireEvent.click(screen.getByRole("button", { name: "Přidat hypotézu" }));
    const row = screen.getByRole("textbox", { name: "Přidat hypotézu" });
    fireEvent.change(row, { target: { value: "mírnější  varianta vyhraje" } });
    fireEvent.keyDown(row, { key: "Enter" });
    expect(ws.saves).toEqual([]);
    fireEvent.keyDown(row, { key: "Escape" });
    // A removal happens at once and Vrátit puts it back where it was.
    fireEvent.click(screen.getByRole("button", { name: "Odebrat: Mírnější varianta vyhraje" }));
    expect(screen.queryByText("Mírnější varianta vyhraje")).toBeNull();
    fireEvent.click(await screen.findByRole("button", { name: "Vrátit" }));
    expect(await screen.findByText("Mírnější varianta vyhraje")).toBeTruthy();
    // No unfinished editor to guard: leaving is not held.
    const unload = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(unload);
    expect(unload.defaultPrevented).toBe(false);
  });

  it("edits a set's measurement field by field on its card, preserving its extra fields and the existing questionnaire, and confirms scope replacement", async () => {
    const analysis = { ...ANALYSIS, tracked_sets: [{ ...ANALYSIS.tracked_sets[0], purpose: "Porovnat varianty", objects: ["A", "B", "C", "D"], custom_method: "keep" }] };
    const ws = unitStub(analysis, {}, { ...PROJECT, sections: [{ title: "Existující dotazník" }] });
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    // audit A33: no separate editor and no form to apply; each field is the card's own.
    await screen.findByText("Porovnat varianty");
    expect(screen.queryByRole("form")).toBeNull();
    const edit = (name: string, value: string, multiline = true) => {
      fireEvent.click(screen.getByRole("button", { name: new RegExp(`^Upravit: ${name} · Varianty nápoje`) }));
      const field = screen.getByRole("textbox", { name: `${name} · Varianty nápoje` });
      fireEvent.change(field, { target: { value } });
      fireEvent.keyDown(field, { key: "Enter", ctrlKey: multiline });
      return field;
    };
    // A field stored empty (no scale ends: the default shows as its placeholder), opened and left
    // as it was, closes and sends nothing.
    fireEvent.click(screen.getByRole("button", { name: /^Upravit: 1 na škále · Varianty nápoje/ }));
    fireEvent.blur(screen.getByRole("textbox", { name: "1 na škále · Varianty nápoje" }));
    expect(screen.queryByRole("textbox", { name: "1 na škále · Varianty nápoje" })).toBeNull();
    // A question without {object} is refused at the field and stays typed there; nothing is saved.
    const question = edit("Otázka sady · položí se ke každé položce", "Chybná otázka");
    expect(await screen.findByText("Otázka musí obsahovat {object}: tam se vloží název položky.")).toBeTruthy();
    expect((question as HTMLTextAreaElement).value).toBe("Chybná otázka");
    expect(ws.saves).toEqual([]);
    // Going on would drop it: the person is asked first, and "Zrušit" stays.
    fireEvent.click(screen.getByRole("button", { name: /Další · dotazník/ }));
    expect(await screen.findByText("Některé úpravy návrhu nejdou uložit a zůstaly v poli. Zahodit je a pokračovat?")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Zrušit" }));
    await waitFor(() => expect(screen.queryByText(/nejdou uložit a zůstaly v poli/)).toBeNull());
    expect(push).not.toHaveBeenCalled();
    // Removing an item remounts the chips after it, so a chip's refused rewording is asked about
    // first; the refused question, which no removal remounts, is not.
    fireEvent.click(screen.getByRole("button", { name: "Upravit: Položka · 3 C" }));
    const third = screen.getByRole("textbox", { name: "Položka · 3" });
    fireEvent.change(third, { target: { value: "a" } });
    fireEvent.keyDown(third, { key: "Enter" });
    expect(await screen.findByText("Tato položka už v sadě je.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Odebrat A" }));
    expect(await screen.findByText(/nejdou uložit a zůstaly v poli/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Zrušit" }));
    await waitFor(() => expect(screen.queryByText(/nejdou uložit a zůstaly v poli/)).toBeNull());
    expect(screen.getByRole("button", { name: "Odebrat A" })).toBeTruthy();
    fireEvent.keyDown(screen.getByRole("textbox", { name: "Položka · 3" }), { key: "Escape" });
    expect(ws.saves).toEqual([]);
    fireEvent.change(question, { target: { value: "Zvolili byste {object}?" } });
    fireEvent.keyDown(question, { key: "Enter", ctrlKey: true });
    // The preview follows each field as it is saved.
    expect(await screen.findByText("Zvolili byste A?")).toBeTruthy();
    edit("1 na škále", "určitě ne", false);
    // An item is reworded in its place: the order the preview and the questionnaire take is kept.
    fireEvent.click(screen.getByRole("button", { name: "Upravit: Položka · 2 B" }));
    const item = screen.getByRole("textbox", { name: "Položka · 2" });
    fireEvent.change(item, { target: { value: "Bé" } });
    fireEvent.keyDown(item, { key: "Enter" });
    await waitFor(() => expect((ws.saves.at(-1)?.content.research_plan as { tracked_sets?: unknown[] } | undefined)?.tracked_sets?.[0]).toMatchObject({ scale_labels: ["určitě ne", "velmi"], objects: ["A", "Bé", "C", "D"] }));
    const body = ws.saves.at(-1)!;
    expect(body.content.sections).toEqual([{ title: "Existující dotazník" }]);
    expect((body.content.research_plan as { tracked_sets: unknown[] }).tracked_sets[0]).toMatchObject({ object_question: "Zvolili byste {object}?", objects: ["A", "Bé", "C", "D"], custom_method: "keep" });
    expect((body.analysis as { tracked_sets: unknown[] }).tracked_sets).toEqual((body.content.research_plan as { tracked_sets: unknown[] }).tracked_sets);
    expect(posted(DESIGN_PATH)).toEqual([]);
    fireEvent.click(screen.getByRole("radio", { name: /Jen varianty/ }));
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Ponechat" }));
    expect(screen.getByText("Zvolili byste A?")).toBeTruthy();
  });
});

// artifact-design DSN2: each research question with its coverage, read from the newest Design
// Revision's readiness (a GET; nothing is submitted, started or paid).
describe("Návrh: Výzkumné otázky a jejich pokrytí", () => {
  const REVISIONS = "/api/v1/studies/STU-1/design/revisions";
  const READINESS = "/api/v1/studies/STU-1/research/readiness";
  const RQS = ["Kolik lidí nápoj zkusí?", "Proč by ho nekoupili?", "Nová otázka?"];
  const WITH_RQS = { ...PROJECT, research_plan: { ...ANALYSIS, research_questions: RQS } };
  const rev = (n: number, workspace: number) => ({ revision_id: `DR-${n}`, study_id: "STU-1", revision: n, content_sha256: "x", parent_revision: null, source_stage: "run", created_by: "u", created_at: "2026-10-21T10:00:00Z", workspace_revision: workspace });
  const readiness = {
    design_revision_id: "DR-2",
    question_outlook: [{ question_id: "q_try", text: "Zkusil byste nápoj?", section_id: "s1", battery_id: null, verdict: "ANSWERABLE", reasons: [] }],
    research_trace: {
      linked: true, dangling: [],
      questions: [
        { text: RQS[0], measures: ["q_try"], verdict: "ANSWERABLE", reasons: [], comparison: "describe" },
        { text: RQS[1], measures: [], verdict: "UNANSWERABLE", reasons: ["unmeasured"] },
      ],
    },
  };
  const section = async () => screen.findByRole("region", { name: "Výzkumné otázky a jejich pokrytí" });
  // The native fixture answers these GETs with nothing; these tests' answers go in front of it.
  const stub = (routes: Record<string, () => unknown>) => {
    unitStub(ANALYSIS, {}, WITH_RQS);
    const inner = globalThis.fetch;
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const answer = (init?.method ?? "GET") === "GET" ? routes[String(url).split("?")[0]] : undefined;
      if (!answer) return inner(url, init);
      calls.push({ url: String(url), body: null });
      return new Response(JSON.stringify(answer()), { status: 200 });
    }));
  };

  it("shows each research question with the trace's status, its items linked to Dotazník and its gaps", async () => {
    stub({ [REVISIONS]: () => ({ items: [rev(1, 1), rev(2, 3)] }), [READINESS]: () => readiness });
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    const s = await section();
    await within(s).findByText(/Podle revize návrhu 2, která odpovídá této pracovní verzi/);
    // The newest revision's readiness is read, never another's.
    expect(calls.some((c) => c.url.startsWith(READINESS) && c.url.includes("design_revision_id=DR-2"))).toBe(true);
    const items = within(s).getAllByRole("listitem").filter((li) => li.parentElement?.tagName === "OL");
    expect(items.map((li) => li.querySelector("p")?.textContent)).toEqual(RQS);
    expect(within(items[0]).getAllByText("pokryto").length).toBeGreaterThan(0);
    const link = within(items[0]).getByRole("link", { name: "Zkusil byste nápoj?" });
    expect(link.getAttribute("href")).toMatch(/\/questionnaire#qedit_q_try$/);
    expect(within(items[1]).getByText("mezera")).toBeTruthy();
    expect(within(items[1]).getByText("Žádná položka dotazníku ji neměří.")).toBeTruthy();
    // A question the revision does not hold is not checked: unknown, never pokryto.
    expect(within(items[2]).getByText("neznámé")).toBeTruthy();
    expect(within(items[2]).getByText(/v revizi 2 není/)).toBeTruthy();
    // Nothing was submitted or started from here.
    expect(calls.filter((c) => c.body !== null && (c.url.startsWith(REVISIONS) || c.url.includes("/research/runs")))).toEqual([]);
  });

  it("says the copy moved since the revision, and links to the check before a run", async () => {
    stub({ [REVISIONS]: () => ({ items: [rev(2, 1)] }), [READINESS]: () => readiness });
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    const s = await section();
    await within(s).findByText(/Návrh se od ní změnil/);
    expect(within(s).getByRole("link", { name: "Zkontrolovat před spuštěním" }).getAttribute("href")).toMatch(/\/run$/);
  });

  it("says when no revision exists yet, and reads no readiness", async () => {
    stub({ [REVISIONS]: () => ({ items: [] }) });
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    const s = await section();
    await within(s).findByText(/Návrh zatím nemá revizi/);
    expect(calls.some((c) => c.url.startsWith(READINESS))).toBe(false);
  });
});
