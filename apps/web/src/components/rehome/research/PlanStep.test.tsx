// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetBootCache } from "@/unit/boot";
import { briefFingerprint, defaultsMerge } from "@/unit/research/model";
import { CONFIRM_REMOVE_SET, PROMPT_COMMENT, PROMPT_SET_OBJECTS, PROMPT_SET_TITLE } from "@/unit/research/plan";
import { ResearchScreen } from "./ResearchScreen";

const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => "/app/research/PRJ-1/plan", useRouter: () => ({ push, replace }) }));

const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/unit/research/fixtures/empty-project.json"), "utf8"));
const BOOT = { empty_project: EMPTY, ai_provider: "claude_code_subscription", panel: { version: "v17.1.2" }, edition: { version: "18.6.6", claude_code_enabled: true } };
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
  _brief_signature: briefFingerprint(defaultsMerge(PROJECT, BOOT)),
};

type Call = { url: string; body: Record<string, unknown> | null };
let calls: Call[] = [];
function unitStub(analysis: unknown = ANALYSIS, over: Record<string, (b: unknown) => unknown> = {}) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ url: u, body });
      const answers: Record<string, (b: unknown) => unknown> = {
        "/api/bootstrap": () => BOOT,
        "/api/projects/load": () => ({ project_id: "PRJ-1", revision: 3, project_type: "research", project: PROJECT, analysis }),
        "/api/projects/save": () => ({ project_id: "PRJ-1", revision: 4 }),
        "/api/providers/claude-code/status": () => ({ ok: true }),
        "/api/research/analyze": () => ({ job_id: "JOB-1" }),
        "/api/job": () => ({ state: "done", result: { analysis: { ...ANALYSIS, problem_summary: "Nové shrnutí.", _brief_signature: undefined }, project: {} } }),
        ...over,
      };
      const answer = answers[u.split("?")[0]]?.(body) ?? {};
      return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
    }),
  );
}
const posted = (path: string) => calls.filter((c) => c.url.split("?")[0] === path);

/** The rebuilt dialog, answered as a person would. */
async function answerDialog(question: string, value: string | null) {
  const dialog = await screen.findByText(question);
  const form = dialog.closest("form") as HTMLFormElement;
  if (value === null) return fireEvent.click(within(form).getByRole("button", { name: "Zrušit" }));
  const input = within(form).queryByRole("textbox");
  if (input) fireEvent.change(input, { target: { value } });
  fireEvent.submit(form);
}

beforeEach(() => {
  resetBootCache();
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
});

describe("Návrh", () => {
  it("without an analysis says so, and offers the brief and the questionnaire", async () => {
    unitStub(null);
    render(<ResearchScreen projectId="PRJ-1" step="plan" />);
    expect(await screen.findByText("Zatím není návrh")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Zadání" }));
    expect(push).toHaveBeenCalledWith("/app/research/PRJ-1/brief");
    expect(screen.queryByText("KOMENTÁŘE K NÁVRHU")).toBeNull();
  });

  it("draws the analysis, its sets with the question preview, the follow-ups and the comments", async () => {
    unitStub();
    render(<ResearchScreen projectId="PRJ-1" step="plan" />);
    expect(await screen.findByRole("heading", { name: "Jak jsem zadání pochopil" })).toBeTruthy();
    expect(screen.getByText("Jde o test nového konceptu.")).toBeTruthy();
    expect(screen.getByText("Mírnější varianta vyhraje")).toBeTruthy();
    expect(screen.getByText("Jak vás oslovuje Jemná?")).toBeTruthy();
    expect(screen.getByText("2 položek")).toBeTruthy();
    expect(screen.getByText("Jen MHD?")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Zpracovat komentáře" }) as HTMLButtonElement).disabled).toBe(true);
    // The recommended variant is the chosen one until another is applied.
    expect(screen.getByRole("button", { name: /Varianty a cena/ }).getAttribute("aria-pressed")).toBe("true");
  });

  it("applies a design variant to the project", async () => {
    unitStub();
    render(<ResearchScreen projectId="PRJ-1" step="plan" />);
    fireEvent.click(await screen.findByRole("button", { name: /Jen varianty/ }));
    expect(screen.getByRole("button", { name: /Jen varianty/ }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByText("Použit návrh: Jen varianty")).toBeTruthy();
    expect(screen.getByText("Porovnat varianty")).toBeTruthy();
  });

  it("adds a set through the classic prompts, removes an object, and removes a set only when confirmed", async () => {
    unitStub();
    render(<ResearchScreen projectId="PRJ-1" step="plan" />);
    fireEvent.click(await screen.findByRole("button", { name: "Přidat sadu" }));
    await answerDialog(PROMPT_SET_TITLE, "Kraje");
    await answerDialog(PROMPT_SET_OBJECTS, "Praha, Brno");
    expect(await screen.findByRole("heading", { name: "Kraje" })).toBeTruthy();
    expect(screen.getByText("Geografické kategorie")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Odebrat Jemná" }));
    expect(screen.queryByText("Jak vás oslovuje Jemná?")).toBeNull();
    fireEvent.click(screen.getAllByRole("button", { name: "Odstranit sadu" })[1]);
    await answerDialog(CONFIRM_REMOVE_SET, null);
    expect(screen.getByRole("heading", { name: "Kraje" })).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: "Odstranit sadu" })[1]);
    await answerDialog(CONFIRM_REMOVE_SET, "");
    await waitFor(() => expect(screen.queryByRole("heading", { name: "Kraje" })).toBeNull());
  });

  it("answers the follow-up questions into the brief and analyses it again", async () => {
    unitStub();
    render(<ResearchScreen projectId="PRJ-1" step="plan" />);
    fireEvent.click(await screen.findByRole("button", { name: "Doplnit a aktualizovat návrh" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Napište odpovědi.");
    fireEvent.change(screen.getByPlaceholderText("Odpovězte jen na relevantní body…"), { target: { value: "Ano, jen MHD." } });
    fireEvent.click(screen.getByRole("button", { name: "Doplnit a aktualizovat návrh" }));
    expect(await screen.findByText("Nové shrnutí.", {}, { timeout: 4000 })).toBeTruthy();
    const [analyze] = posted("/api/research/analyze");
    expect((analyze.body?.briefing as { what_is_known: string }).what_is_known).toBe("Víme A.\n\nDoplnění k analýze:\nAno, jen MHD.");
    expect(push).not.toHaveBeenCalled();
  });

  it("comments on selected text, then works the comments in with a forced analysis", async () => {
    unitStub();
    render(<ResearchScreen projectId="PRJ-1" step="plan" />);
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
    await answerDialog(PROMPT_COMMENT, "Není to test.");
    expect(await screen.findByText("Není to test.")).toBeTruthy();
    expect(screen.getByText("„Jde o test“")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Zpracovat komentáře" }));
    expect(await screen.findByText("Upraveno podle vašich komentářů", {}, { timeout: 4000 })).toBeTruthy();
    const [analyze] = posted("/api/research/analyze");
    // Forced: the same brief would otherwise have been reused without a job.
    expect((analyze.body?.briefing as { review_comments: string }).review_comments).toBe("1. K textu „Jde o test“: Není to test.");
    expect(screen.queryByText("Není to test.")).toBeNull();
    expect(screen.getByText("Komentáře zapracovány")).toBeTruthy();
  });

  it("goes on to the questionnaire at its three paths", async () => {
    unitStub();
    render(<ResearchScreen projectId="PRJ-1" step="plan" />);
    fireEvent.click(await screen.findByRole("button", { name: /Další · dotazník/ }));
    expect(push).toHaveBeenCalledWith("/app/research/PRJ-1/questionnaire");
  });
});
