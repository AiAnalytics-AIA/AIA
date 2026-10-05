// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DESIGN_PATH, NATIVE_JOB_WAIT, NATIVE_TEST_TIMEOUT_MS, approveProposal, nativeAgentFixture } from "./test-native-agents";
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

type Call = { url: string; body: Record<string, unknown> | null };
let calls: Call[] = [];
function unitStub(analysis: unknown = ANALYSIS, over: Record<string, (b: unknown) => unknown> = {}) {
  calls = [];
  const ws = workspaceFixture(PROJECT, { analysis: analysis });
  const native = nativeAgentFixture((_action, baseline) => ({ project: { ...baseline, research_plan: { ...ANALYSIS, problem_summary: "Nové shrnutí." } }, proposal: { ...ANALYSIS, problem_summary: "Nové shrnutí." }, analysis: { ...ANALYSIS, problem_summary: "Nové shrnutí." } }), over);
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

  it("applies a design variant to the project", async () => {
    unitStub();
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("radio", { name: /Jen varianty/ }));
    expect(screen.getByRole("radio", { name: /Jen varianty/ }).getAttribute("aria-checked")).toBe("true");
    expect(screen.getByText("Použit návrh: Jen varianty")).toBeTruthy();
    expect(screen.getByText("Porovnat varianty")).toBeTruthy();
  });

  it("adds, renames and fills a set in place, removes an object, and removes a set only when confirmed", async () => {
    unitStub();
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    const names = () => screen.getAllByLabelText("Název sady").map((x) => (x as HTMLInputElement).value);
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
    // Renamed in place, through renamePlanSet, when the field is left.
    const kraje = screen.getAllByLabelText("Název sady")[1];
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
    expect(await screen.findByText("Nové shrnutí.", {}, { timeout: 4000 })).toBeTruthy();
    const [analyze] = posted(DESIGN_PATH);
    expect(((analyze.body?.content as { briefing: { what_is_known: string } }).briefing).what_is_known).toBe("Víme A.\n\nDoplnění k analýze:\nJen MHD?\nAno, jen MHD.");
    expect(push).not.toHaveBeenCalled();
  });

  it("comments on selected text, then works the comments in with a forced analysis", async () => {
    unitStub();
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    const text = (await screen.findByText("Jde o test nového konceptu.")).firstChild as Text;
    // jsdom lays nothing out: a selection has no box of its own.
    Range.prototype.getBoundingClientRect = () => ({ left: 100, top: 200, width: 80, height: 16, right: 180, bottom: 216, x: 100, y: 200, toJSON: () => ({}) });
    const range = document.createRange();
    range.setStart(text, 0);
    range.setEnd(text, 10);
    window.getSelection()!.removeAllRanges();
    window.getSelection()!.addRange(range);
    fireEvent.mouseUp(text.parentElement!);
    fireEvent.click(await screen.findByRole("button", { name: "Přidat komentář" }));
    // The comment is typed on its row, not in a prompt; Enter keeps it.
    const draft = await screen.findByLabelText("Co změnit? Enter uloží komentář");
    fireEvent.change(draft, { target: { value: "Není to test." } });
    fireEvent.keyDown(draft, { key: "Enter" });
    expect(await screen.findByText("Není to test.")).toBeTruthy();
    expect(screen.getByText("„Jde o test“")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Zpracovat komentáře" }));
    await approveProposal();
    expect(await screen.findByText("Upraveno podle vašich komentářů", {}, { timeout: 4000 })).toBeTruthy();
    const [analyze] = posted(DESIGN_PATH);
    // The revised briefing is frozen in the native Design Revision.
    expect(((analyze.body?.content as { briefing: { review_comments: string } }).briefing).review_comments).toBe("1. K textu „Jde o test“: Není to test.");
    expect(screen.queryByText("Není to test.")).toBeNull();
    // Set when the analysis resolves, after the plan above is drawn: waited for, never read at once.
    expect(await screen.findByText("Komentáře zapracovány", {}, NATIVE_JOB_WAIT)).toBeTruthy();
  });

  it("goes on to the questionnaire at its three paths", async () => {
    unitStub();
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /Další · dotazník/ }));
    expect(push).toHaveBeenCalledWith(stagePath("questionnaire"));
  });
});
