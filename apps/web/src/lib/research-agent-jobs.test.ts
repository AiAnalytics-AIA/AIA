// @vitest-environment jsdom
// Where an agent job stands, as a stage acts on it (CR-2): a job stopped at the study's budget cap
// waits for a person's lift and goes on as the same job; it is never read as a failure to retry.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, type ResearchAgentJob } from "./api";
import { BUDGET_WAIT_MESSAGE, agentJobState, agentJobUpdate, followAgentJob, jobCostAsked, jobCostQuestion, withJobCostConfirmation } from "./research-agent-jobs";
import { JobError } from "@/research/jobs";

const job = (status: string, stepStatus: string, over: Partial<ResearchAgentJob> = {}): ResearchAgentJob =>
  ({
    run_id: "RUN-J1", design_revision_id: "REV-1", action: "build_questionnaire", status,
    is_terminal: ["COMPLETED", "FAILED", "CANCELLED"].includes(status), needs_attention: false,
    context_sha256: "x", harness_version: "3", created_at: "2026-10-20T09:00:00Z", actual_cost_usd: null,
    steps: [{ step_id: "STEP-agent", node_key: "agent", status: stepStatus, waiting_reason: null, error_message: null }],
    ...over,
  }) as unknown as ResearchAgentJob;

beforeEach(() => sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "a@example.test", subject: "s" })));
afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear(); });

describe("agentJobState", () => {
  it("reads a job whose step waits for budget as waiting for budget, whatever the run's status says", () => {
    expect(agentJobState(job("AWAITING_BUDGET", "AWAITING_BUDGET", { needs_attention: true }))).toBe("awaiting_budget");
    expect(agentJobState(job("RUNNING", "AWAITING_BUDGET"))).toBe("awaiting_budget");
  });

  it("tells every other state apart, and an unknown one is still running, never done", () => {
    expect(agentJobState(job("COMPLETED", "SUCCEEDED"))).toBe("completed");
    expect(agentJobState(job("CANCELLED", "CANCELLED"))).toBe("cancelled");
    expect(agentJobState(job("FAILED", "FAILED"))).toBe("failed");
    expect(agentJobState(job("WAITING_PROVIDER", "WAITING_PROVIDER"))).toBe("waiting");
    expect(agentJobState(job("AWAITING_GATE", "AWAITING_GATE", { needs_attention: true }))).toBe("waiting");
    expect(agentJobState(job("RECOVERY_REQUIRED", "FAILED"))).toBe("waiting");
    expect(agentJobState(job("RUNNING", "RUNNING"))).toBe("running");
    expect(agentJobState(job("PENDING", "RUNNABLE"))).toBe("running");
    expect(agentJobState(job("SOMETHING_NEW", "RUNNABLE"))).toBe("running");
  });

  it("says in the job panel that the job waits for the study's budget", () => {
    const u = agentJobUpdate(job("AWAITING_BUDGET", "AWAITING_BUDGET", { needs_attention: true }), "Návrh dotazníku");
    expect(u.phase).toBe("Čeká na rozpočet studie");
    expect(u.paused).toBe(BUDGET_WAIT_MESSAGE);
  });
});

describe("followAgentJob", () => {
  const serve = (answer: ResearchAgentJob) =>
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL) => {
      const body = String(url).startsWith("/config")
        ? { cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", apiBase: "", build: { sha: null } }
        : answer;
      return new Response(JSON.stringify(body), { status: 200 });
    }));

  it("stops on a budget wait with its own kind and the job's id, never a generic error", async () => {
    serve(job("AWAITING_BUDGET", "AWAITING_BUDGET", { needs_attention: true }));
    const thrown = await followAgentJob("STU-1", "RUN-J1", "Návrh dotazníku", () => {}).catch((e: unknown) => e);
    expect(thrown).toBeInstanceOf(JobError);
    expect((thrown as JobError).kind).toBe("awaiting_budget");
    expect((thrown as JobError).jobId).toBe("RUN-J1");
    expect((thrown as JobError).message).toBe(BUDGET_WAIT_MESSAGE);
  });

  it("still reports another wait or a failure as an error", async () => {
    serve(job("FAILED", "FAILED", { steps: [{ step_id: "S", node_key: "agent", status: "FAILED", waiting_reason: null, error_message: "boom" }] as ResearchAgentJob["steps"] }));
    const thrown = await followAgentJob("STU-1", "RUN-J1", "x", () => {}).catch((e: unknown) => e);
    expect((thrown as JobError).kind).toBe("error");
    expect((thrown as JobError).message).toBe("boom");
  });

  it("returns a completed job", async () => {
    serve(job("COMPLETED", "SUCCEEDED"));
    await expect(followAgentJob("STU-1", "RUN-J1", "x", () => {})).resolves.toMatchObject({ run_id: "RUN-J1" });
  });
});

describe("a job whose ceiling reaches the study's confirmation threshold (LO15)", () => {
  const asked = () => new ApiError(409, "cost_confirmation_required", "confirm", null, { ceiling_usd: 2, limit_usd: 1 });

  it("reads the server's ceiling and threshold, and nothing else", () => {
    expect(jobCostAsked(asked())).toEqual({ ceiling: 2, limit: 1 });
    expect(jobCostAsked(new ApiError(409, "cost_ceiling_unknown", "x", null, { limit_usd: 1 }))).toBeNull();
    expect(jobCostAsked(new ApiError(409, "cost_confirmation_required", "x", null, { ceiling_usd: "2", limit_usd: 1 }))).toBeNull();
    expect(jobCostAsked(new Error("x"))).toBeNull();
    expect(jobCostQuestion({ ceiling: 2.5, limit: 1 })).toContain("Práh potvrzení");
  });

  it("asks once and confirms exactly the ceiling the server named", async () => {
    const create = vi.fn(async (usd?: number) => { if (usd === undefined) throw asked(); return usd; });
    const confirm = vi.fn(async () => true);
    await expect(withJobCostConfirmation(create, confirm)).resolves.toBe(2);
    expect(create.mock.calls).toEqual([[undefined], [2]]);
    expect(confirm).toHaveBeenCalledTimes(1);
  });

  it("starts nothing on a no, and passes any other refusal through unasked", async () => {
    const create = vi.fn(async (): Promise<number> => { throw asked(); });
    await expect(withJobCostConfirmation(create, async () => false)).rejects.toMatchObject({ code: "cost_confirmation_required" });
    expect(create).toHaveBeenCalledTimes(1);
    const other = vi.fn(async (): Promise<number> => { throw new ApiError(409, "stale_design", "x", null); });
    const confirm = vi.fn(async () => true);
    await expect(withJobCostConfirmation(other, confirm)).rejects.toMatchObject({ code: "stale_design" });
    expect(confirm).not.toHaveBeenCalled();
  });
});
