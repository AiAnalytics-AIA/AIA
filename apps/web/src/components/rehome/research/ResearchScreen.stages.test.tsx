// @vitest-environment jsdom
// The study's screen stays mounted from stage to stage (research-lead-workbench 34), so what a
// remount used to reset is reset on the step: the page opens at its top in the classic layout, a
// review left open is kept for later and not carried over, AI pomoc closes, and a review a card
// asked the next stage for still opens there. The stages are stand-ins: the screen is the subject.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { resetConfigCache } from "@/lib/auth";
import { defaultsMerge, type Template } from "@/research/model";
import type { StepKey } from "@/research/steps";
import { OPEN_REVIEW_KEY } from "../../workbench/Workbench";
import { useResearch } from "./context";
import { ResearchScreen, resetWorkbenchSwitch } from "./ResearchScreen";
import { TEST_FRAME } from "./test-frame";
import { CONTENT_PATH, EMPTY_PROJECT, signedIn } from "./test-workspace";

vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/brief", useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }));

function Probe({ name }: { name: string }) {
  const { memory } = useResearch();
  return (
    <section>
      <h2>Stand-in {name}</h2>
      <button type="button" onClick={() => memory.set(OPEN_REVIEW_KEY, "RUN-J1")}>Ask the next stage for the review</button>
    </section>
  );
}
vi.mock("./steps", () => {
  const screens = Object.fromEntries((["brief", "plan", "questionnaire", "audience", "persona", "run", "progress", "results"] as const).map((k) => [k, () => <Probe name={k} />]));
  return { STEP_SCREENS: screens };
});

const JOBS = "/api/v1/studies/STU-1/research/agent-jobs";
const job = { run_id: "RUN-J1", design_revision_id: "REV-2", action: "build_questionnaire", status: "COMPLETED", is_terminal: true,
  needs_attention: false, context_sha256: "x", harness_version: "3", created_at: "2026-10-17T09:00:00Z", steps: [], actual_cost_usd: 0.1, proposal_state: "pending" };
const proposed = { title: "Alfa", sections: [{ id: "ai_section_1", type: "questions", title: "Zvyky", questions: [{ id: "ai_q_1_1", text: "Jak často pijete kávu?", typ: "skala" }] }] };
const posts: string[] = [];
function api(workbench: boolean) {
  posts.length = 0;
  vi.stubGlobal("matchMedia", (q: string) => ({ matches: q.includes("min-width: 1100px"), media: q, addEventListener: () => {}, removeEventListener: () => {} }));
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url).split("?")[0];
    const method = init?.method ?? "GET";
    if (method !== "GET") posts.push(`${method} ${u}`);
    const answer =
      u === "/config" ? { apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", workbench }
      : u === CONTENT_PATH && method === "GET" ? { study_id: "STU-1", state: "NATIVE", revision: 2, revision_id: "REV-2", content: { title: "Alfa" }, analysis: null, template: EMPTY_PROJECT, saved_at: null, saved_by: null, can_edit: true, lineage: {} }
      : u === JOBS ? [job]
      : u === `${JOBS}/RUN-J1/result` ? {
        result: { project: proposed, proposal: { message: "Návrh", sections: proposed.sections, warnings: [], comparisons: [] } },
        provenance: { agent_id: "aia.research.build_questionnaire", design_revision_id: "REV-2", context_sha256: "x", status: "COMPLETED" },
      }
      : u === "/api/v1/studies/STU-1/design/revisions/REV-2" ? { revision_id: "REV-2", revision: 2, content: defaultsMerge({ title: "Alfa" }, { empty_project: EMPTY_PROJECT } as unknown as Template) }
      : u.endsWith("/research/runs") ? { items: [] }
      : u.endsWith("/research/readiness") ? { design_revision_id: "REV-2", revision: 2, ready: false, checks: [], questions: 0, batteries: 0, objects: 0, n: 0, rules: "test" }
      : u.endsWith("/workspace/stage") ? {}
      : null;
    return answer === null
      ? new Response(JSON.stringify({ code: "not_found", message: "not here" }), { status: 404 })
      : new Response(JSON.stringify(answer), { status: 200 });
  }));
}

const scrollTo = vi.fn();
beforeEach(() => {
  resetWorkbenchSwitch();
  resetConfigCache();
  signedIn();
  scrollTo.mockClear();
  api(false);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const at = (step: StepKey) => <ResearchScreen step={step} frame={TEST_FRAME} />;
const openSaved = async () => {
  fireEvent.click(await screen.findByRole("button", { name: /Sestavit dotazník|dotazník/i }));
  return screen.findByRole("button", { name: "Použít návrh" });
};

describe("the classic layout across stages", () => {
  it("opens another stage at the page's top, not the first", async () => {
    vi.stubGlobal("scrollTo", scrollTo);
    const view = render(at("brief"));
    await screen.findByText("Stand-in brief");
    expect(scrollTo).not.toHaveBeenCalled();
    view.rerender(at("questionnaire"));
    await screen.findByText("Stand-in questionnaire");
    expect(scrollTo).toHaveBeenCalledWith(0, 0);
  });

  it("keeps a review left open for later, never carrying it over to the next stage", async () => {
    const view = render(at("brief"));
    await screen.findByRole("heading", { name: t("research.aiSaved") });
    await openSaved();
    view.rerender(at("questionnaire"));
    await waitFor(() => expect(document.querySelector("[data-proposal-review]")).toBeNull());
    // Kept, not decided: nothing accepted or dismissed, and the proposal is offered again.
    expect(posts.filter((p) => /accept|dismiss/.test(p))).toEqual([]);
    expect(await openSaved()).toBeTruthy();
  });

  it("opens a review a card asked the next stage for, once that stage shows", async () => {
    const view = render(at("brief"));
    await screen.findByRole("heading", { name: t("research.aiSaved") });
    fireEvent.click(screen.getByRole("button", { name: "Ask the next stage for the review" }));
    await new Promise((r) => setTimeout(r, 50));
    expect(document.querySelector("[data-proposal-review]")).toBeNull();
    view.rerender(at("questionnaire"));
    expect(await screen.findByRole("button", { name: "Použít návrh" })).toBeTruthy();
  });

  it("closes AI pomoc on another stage, as its own page did", async () => {
    const view = render(at("brief"));
    const help = await screen.findByRole("region", { name: t("research.aiHelpLabel") });
    const trigger = Array.from(help.querySelectorAll<HTMLButtonElement>("[data-assistance-trigger]")).find((b) => b.dataset.assistanceTrigger !== "critique_design" && b.dataset.assistanceTrigger !== "history")!;
    fireEvent.click(trigger);
    await waitFor(() => expect(document.getElementById("research-assistance-title")).not.toBeNull());
    view.rerender(at("questionnaire"));
    await screen.findByText("Stand-in questionnaire");
    await waitFor(() => expect(document.getElementById("research-assistance-title")).toBeNull());
  });
});
