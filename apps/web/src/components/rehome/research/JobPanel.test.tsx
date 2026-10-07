// @vitest-environment jsdom
// The job panel shows a thinking orb while the model works on the job's step, and
// the running icon otherwise: a queued or waiting job is not thinking.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { agentJobUpdate } from "@/lib/research-agent-jobs";
import type { ResearchAgentJob } from "@/lib/api";
import { JobPanel } from "./JobPanel";

const job = (status: string, stepStatus: string | null): ResearchAgentJob =>
  ({
    run_id: "JOB-1", design_revision_id: "REV-1", action: "build_questionnaire", status, is_terminal: false, needs_attention: false,
    context_sha256: "x", harness_version: "1", created_at: "2026-10-07T08:00:00Z", actual_cost_usd: null,
    steps: stepStatus ? [{ node_key: "agent", status: stepStatus, waiting_reason: null, error_message: null }] : [],
  }) as unknown as ResearchAgentJob;

const orbIn = (j: ResearchAgentJob) => {
  const { container } = render(<JobPanel job={agentJobUpdate(j, "Návrh dotazníku")} onCancel={() => {}} />);
  const orb = container.querySelector<HTMLElement>("[data-orb]");
  return orb ? `${orb.dataset.orb}/${orb.dataset.orbInk}` : null;
};

afterEach(cleanup);

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
