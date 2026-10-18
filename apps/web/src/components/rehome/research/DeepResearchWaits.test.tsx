// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import type { DeepResearchRun, ResearchAgentJob, ResearchStep } from "@/lib/api";

import { AgentBudgetWaits } from "./AgentBudgetWaits";
import { DeepResearchWaits } from "./DeepResearchWaits";
import { signedIn } from "./test-workspace";

const STUDY = { study_id: "STU-1", name: "Fiktivní", budget_usd: 10, spent_usd: 9.5, remaining_usd: 0.5 };
let posts: { url: string; body: unknown }[] = [];

beforeEach(() => {
  signedIn();
  posts = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url).split("?")[0];
      if (u === "/config") return new Response(JSON.stringify({ apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost" }));
      if (u === "/api/v1/studies/STU-1") return new Response(JSON.stringify(STUDY));
      if (init?.method === "POST") {
        posts.push({ url: u, body: init.body ? JSON.parse(String(init.body)) : null });
        return new Response("{}");
      }
      return new Response("{}", { status: 404 });
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const deep = (steps: DeepResearchRun["steps"], over: Partial<DeepResearchRun> = {}): DeepResearchRun => ({
  run_id: "DRR-1", design_revision_id: "REV-1", preset: "QUICK", channels: ["WEB"], status: "WAITING_PROVIDER",
  phase: "WAITING", is_terminal: false, needs_attention: false, retryable: false, created_at: null, steps,
  actual_cost_usd: 0, ...over,
});
const deepStep = (status: string, waiting_reason: string | null = null) =>
  ({ step_id: "STP-1", node_key: "plan", status, waiting_reason, error_message: null });

describe("a Deep Research run that waits for a person (PC4)", () => {
  it("lets a run parked for the AI runtime go on: the same run, nothing started", async () => {
    const changed = vi.fn();
    render(<DeepResearchWaits run={deep([deepStep("WAITING_PROVIDER", "ai_runtime_unavailable")])} studyId="STU-1" canEdit onChanged={changed} onError={vi.fn()} />);
    expect(screen.getByText(t("research.exec.parkedResume"))).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: t("research.exec.resume") }));
    await waitFor(() => expect(changed).toHaveBeenCalled());
    expect(posts.map((p) => p.url)).toEqual(["/api/v1/studies/STU-1/deep-research/runs/DRR-1/resume"]);
  });

  it("lifts a step stopped at the budget cap with the total the person names", async () => {
    const changed = vi.fn();
    render(<DeepResearchWaits run={deep([deepStep("AWAITING_BUDGET", "budget_exceeded")])} studyId="STU-1" canEdit onChanged={changed} onError={vi.fn()} />);
    const form = await screen.findByRole("form", { name: t("research.exec.budget.title") });
    await within(form).findByText(/10\.00/);
    fireEvent.change(within(form).getByLabelText(t("research.exec.budget.amount")), { target: { value: "12" } });
    fireEvent.click(within(form).getByRole("button", { name: t("research.exec.budget.lift") }));
    await waitFor(() => expect(changed).toHaveBeenCalled());
    expect(posts).toEqual([{ url: "/api/v1/studies/STU-1/deep-research/runs/DRR-1/budget", body: { budget_usd: 12, note: "" } }]);
  });

  it("offers nothing for a run that waits on its own, has ended, or may not change here", () => {
    const quota = render(<DeepResearchWaits run={deep([deepStep("WAITING_PROVIDER", "provider_quota_exhausted")])} studyId="STU-1" canEdit onChanged={vi.fn()} onError={vi.fn()} />);
    expect(quota.container.textContent).toBe("");
    quota.unmount();
    const ended = render(<DeepResearchWaits run={deep([deepStep("AWAITING_BUDGET")], { is_terminal: true })} studyId="STU-1" canEdit onChanged={vi.fn()} onError={vi.fn()} />);
    expect(ended.container.textContent).toBe("");
    ended.unmount();
    const closed = render(<DeepResearchWaits run={deep([deepStep("WAITING_PROVIDER", "ai_runtime_unavailable")])} studyId="STU-1" canEdit={false} onChanged={vi.fn()} onError={vi.fn()} />);
    expect(closed.container.textContent).toBe("");
  });
});

const job = (status: string, over: Partial<ResearchAgentJob> = {}): ResearchAgentJob => ({
  run_id: "RUN-J1", design_revision_id: "REV-1", action: "analyze_brief", status, is_terminal: false,
  needs_attention: false, context_sha256: "c", harness_version: "1", created_at: null,
  steps: [{ step_id: "STP-J", node_key: "agent", kind: "research_agent", status } as unknown as ResearchStep],
  actual_cost_usd: 0, ...over,
});

describe("an AI job stopped at the study's budget cap (PC4)", () => {
  it("lifts the same job: asking again would only return it", async () => {
    const refresh = vi.fn(async () => undefined);
    render(<AgentBudgetWaits jobs={[job("AWAITING_BUDGET"), job("COMPLETED", { run_id: "RUN-J2" })]} studyId="STU-1" canEdit onChanged={refresh} />);
    expect(screen.getByText(t("research.aiBudget.title"))).toBeTruthy();
    const form = await screen.findByRole("form", { name: "Analýza zadání" });
    await within(form).findByText(/10\.00/);
    fireEvent.change(within(form).getByLabelText(t("research.exec.budget.amount")), { target: { value: "11" } });
    fireEvent.click(within(form).getByRole("button", { name: t("research.exec.budget.lift") }));
    await waitFor(() => expect(refresh).toHaveBeenCalled());
    expect(posts).toEqual([{ url: "/api/v1/studies/STU-1/research/agent-jobs/RUN-J1/budget", body: { budget_usd: 11, note: "" } }]);
  });

  it("says nothing when no job waits for budget, and offers no lift to who may not change the study", () => {
    const none = render(<AgentBudgetWaits jobs={[job("COMPLETED")]} studyId="STU-1" canEdit onChanged={vi.fn()} />);
    expect(none.container.textContent).toBe("");
    none.unmount();
    render(<AgentBudgetWaits jobs={[job("AWAITING_BUDGET")]} studyId="STU-1" canEdit={false} onChanged={vi.fn()} />);
    expect(screen.getByText(t("research.aiBudget.title"))).toBeTruthy();
    expect(screen.queryByRole("form")).toBeNull();
  });
});
