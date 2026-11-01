// @vitest-environment jsdom
// Zadání and Návrh with edits saved as the vocabulary's operations (AIA_WEB_EDIT_OPS, working-copy-
// edit-ops WCE3a). A file of its own: the screen reads the switch once per module (ResearchScreen.tsx
// switchesKnown), so it cannot be turned on beside the other stage tests.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NATIVE_TEST_TIMEOUT_MS, nativeAgentFixture } from "./test-native-agents";
import { ResearchScreen } from "./ResearchScreen";
import { type Template, defaultsMerge } from "@/research/model";
import { EMPTY_PROJECT, workspaceFixture } from "./test-workspace";
import { TEST_FRAME } from "./test-frame";

vi.setConfig({ testTimeout: NATIVE_TEST_TIMEOUT_MS });
let path = "/app/clients/CLI-1/research/STU-1/brief";
vi.mock("next/navigation", () => ({ usePathname: () => path, useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

/** AIA holding `project` as a store completes it, so the copy is owed nothing on load and edits go as operations. */
function aia(project: Record<string, unknown>, analysis: unknown) {
  const ws = workspaceFixture(defaultsMerge(project, { empty_project: EMPTY_PROJECT as Template["empty_project"] }) as unknown as Record<string, unknown>, { analysis });
  const over: Record<string, () => unknown> = {
    "/config": () => ({ editOps: true }),
    "/api/v1/studies/STU-1/research/limits": () => ({ methodology_version: "aia-readiness-1", version: null, sample_size: { min: 20, max: 10000 } }),
    "/api/v1/studies/STU-1/research/readiness/working": () => ({ working_revision: 3, research_trace: null, question_outlook: [] }),
  };
  const native = nativeAgentFixture(() => ({ project: {}, proposal: {} }), over, ws.write);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const at = String(url).split("?")[0];
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      const answer = native(at, init?.method ?? "GET", body) ?? ws.answer(at, init?.method ?? "GET", body) ?? over[at]?.();
      if (answer === undefined) return new Response(JSON.stringify({ code: "not_found", message: "No such resource." }), { status: 404 });
      return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
    }),
  );
  return ws;
}

const reword = async (scope: ReturnType<typeof within> | typeof screen, label: RegExp, name: string, value: string) => {
  fireEvent.click(scope.getByRole("button", { name: label }));
  const field = await scope.findByRole("textbox", { name });
  fireEvent.change(field, { target: { value } });
  fireEvent.keyDown(field, { key: "Enter", ctrlKey: true });
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("edits saved as the vocabulary's operations (WCE3a)", () => {
  it("sends Zadání's fields and objectives as one batch, and an undone removal back in its place as the copy", async () => {
    path = "/app/clients/CLI-1/research/STU-1/brief";
    const analysis = { problem_summary: "S", objectives: ["Změřit zájem", "Porovnat značky"], research_questions: [], hypotheses: [], tracked_sets: [] };
    const ws = aia({ title: "Studie", goal: "Cíl", decision_use: "Kampaň A, nebo B", research_plan: { objectives: ["Změřit zájem", "Porovnat značky"] } }, analysis);
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    const decision = within(await screen.findByRole("region", { name: "Rozhodnutí, které má výzkum podpořit" }));
    const goals = within(screen.getByRole("region", { name: "Cíle" }));
    await reword(decision, /^Upravit: Jaké rozhodnutí uděláte/, "Jaké rozhodnutí uděláte", "Kampaň B");
    await reword(goals, /^Upravit: Cíl 2/, "Cíl 2", "Porovnat tři značky");
    fireEvent.click(goals.getByRole("button", { name: "Přidat cíl" }));
    fireEvent.change(goals.getByRole("textbox", { name: "Přidat cíl" }), { target: { value: "Najít bariéry" } });
    fireEvent.keyDown(goals.getByRole("textbox", { name: "Přidat cíl" }), { key: "Enter" });
    await waitFor(() => expect(ws.batches).toHaveLength(1), { timeout: 10_000 });
    expect(ws.batches[0]).toEqual({
      base_revision: 3,
      reason: "brief_objective_add",
      ops: [
        { op: "set_text", field: "decision_use", value: "Kampaň B", why: "person" },
        { op: "list_replace", list: "plan.objectives", old: "Porovnat značky", value: "Porovnat tři značky", why: "person" },
        { op: "list_add", list: "plan.objectives", value: "Najít bariéry", why: "person" },
      ],
    });
    expect(ws.saves).toEqual([]);

    // Removed as an edit; put back in its place by Vrátit, which the vocabulary has no edit for: the copy goes whole.
    fireEvent.click(goals.getByRole("button", { name: "Odebrat cíl 1" }));
    fireEvent.click(screen.getByRole("button", { name: "Vrátit" }));
    await waitFor(() => expect(ws.saves).toHaveLength(1), { timeout: 10_000 });
    expect(ws.batches).toHaveLength(1);
    expect(ws.saves[0]!.base_revision).toBe(4);
    expect((ws.saves[0]!.content.research_plan as { objectives: string[] }).objectives).toEqual(["Změřit zájem", "Porovnat tři značky", "Najít bariéry"]);
  });

  it("writes an objective whole when another reads the same, so the edit never lands on the other one", async () => {
    path = "/app/clients/CLI-1/research/STU-1/brief";
    // Stored before repeats were refused: the vocabulary would name both by one wording.
    const ws = aia({ goal: "Cíl", research_plan: { objectives: ["Poznat trh", "poznat  trh", "Jiný"] } }, null);
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    const goals = within(await screen.findByRole("region", { name: "Cíle" }));
    fireEvent.click(goals.getByRole("button", { name: "Odebrat cíl 2" }));
    await waitFor(() => expect(ws.saves).toHaveLength(1), { timeout: 10_000 });
    expect(ws.batches).toEqual([]);
    expect((ws.saves[0]!.content.research_plan as { objectives: string[] }).objectives).toEqual(["Poznat trh", "Jiný"]);
  });

  it("sends Návrh's narrative items as the vocabulary's edits", async () => {
    path = "/app/clients/CLI-1/research/STU-1/plan";
    const ws = aia({ goal: "Cíl", research_plan: { problem_summary: "Uložený problém", objectives: ["Uložený cíl"], research_questions: ["Uložená otázka?"], status: "approved" } }, null);
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    expect(await screen.findByText("Uložený cíl")).toBeTruthy();
    await reword(screen, /^Upravit: Shrnutí výzkumného problému/, "Shrnutí výzkumného problému", "Upravený problém ");
    await reword(screen, /^Upravit: Výzkumná otázka 1/, "Výzkumná otázka 1", "Nová otázka?");
    await waitFor(() => expect(ws.batches).toHaveLength(1), { timeout: 10_000 });
    expect(ws.batches[0]!.ops).toEqual([
      { op: "set_text", field: "plan.problem_summary", value: "Upravený problém", why: "person" },
      { op: "list_replace", list: "plan.research_questions", old: "Uložená otázka?", value: "Nová otázka?", why: "person" },
    ]);
    expect(ws.saves).toEqual([]);
  });
});
