// @vitest-environment jsdom
// The job panel shows a thinking orb while the model works on the job's step, and
// the running icon otherwise: a queued or waiting job is not thinking.
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { agentJobUpdate } from "@/lib/research-agent-jobs";
import type { ResearchAgentJob } from "@/lib/api";
import { JobPanel } from "./JobPanel";

const job = (status: string, stepStatus: string | null): ResearchAgentJob =>
  ({
    run_id: "JOB-1", design_revision_id: "REV-1", action: "build_questionnaire", status, is_terminal: false, needs_attention: false,
    context_sha256: "x", harness_version: "1", created_at: "2026-10-07T08:00:00Z", actual_cost_usd: null,
    steps: stepStatus ? [{ step_id: "STEP-agent", node_key: "agent", status: stepStatus, waiting_reason: null, error_message: null }] : [],
  }) as unknown as ResearchAgentJob;

const orbIn = (j: ResearchAgentJob) => {
  const { container } = render(<JobPanel job={agentJobUpdate(j, "Návrh dotazníku")} onCancel={() => {}} />);
  const orb = container.querySelector<HTMLElement>("[data-orb]");
  return orb ? `${orb.dataset.orb}/${orb.dataset.orbInk}` : null;
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("the job panel's orb", () => {
  it("shows the action's orb while the agent step runs", () => {
    expect(orbIn(job("RUNNING", "RUNNING"))).toBe("composing/ai");
  });

  it("shows none while the job is queued", () => {
    expect(orbIn(job("QUEUED", "RUNNABLE"))).toBeNull();
  });

  it("shows none while the job waits", () => {
    expect(orbIn(job("WAITING_PROVIDER", "WAITING_PROVIDER"))).toBeNull();
  });
});

describe("the job panel's feed", () => {
  it("shows a large orb and what the job's step reported, read from the job's own feed", async () => {
    sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "a@example.test", subject: "s" }));
    const urls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL) => {
      const u = String(url);
      urls.push(u);
      const body = u.startsWith("/config")
        ? { cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", apiBase: "", build: { sha: null } }
        : [
            { event_id: 1, step_id: "STEP-agent", attempt_id: "A", event_type: "ATTEMPT_CLAIMED", level: "INFO", message: "agent claimed", payload: {}, created_at: null },
            { event_id: 2, step_id: "STEP-agent", attempt_id: "A", event_type: "STEP_PROGRESS", level: "INFO", message: "Připravený kontext; AI zpracovává návrh", payload: { action: "build_questionnaire" }, created_at: null },
          ];
      return new Response(JSON.stringify(body), { status: 200 });
    }));
    const { container } = render(<JobPanel job={agentJobUpdate(job("RUNNING", "RUNNING"), "Návrh dotazníku")} onCancel={() => {}} studyId="STU-1" />);
    const log = await screen.findByRole("log");
    expect(within(log).getAllByRole("listitem").map((l) => l.textContent)).toEqual(["Worker krok převzal", "Připravený kontext; AI zpracovává návrh"]);
    expect(container.querySelector<HTMLElement>("[data-orb]")?.style.width).toBe("64px");
    expect(urls.some((u) => u.startsWith("/api/v1/studies/STU-1/research/agent-jobs/JOB-1/events?since=0"))).toBe(true);
  });
});
