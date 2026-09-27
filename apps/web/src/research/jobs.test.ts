import { describe, expect, it, vi } from "vitest";

import { legacyContext, statement } from "../testing/legacy";
import {
  CANCEL_CONFIRM, JOB_BUSY, JobError, type JobRead, type JobUpdate, cancelJob, fmtTime, jobMeta, jobMetaLine,
  jobOutcome, jobPayload, runJob, usualRange,
} from "./jobs";

// The classic `job` wrapper and the meta-line statement inside the original
// job body, evaluated verbatim; _job1790 is stubbed to capture the payload it
// is handed, with the base's own client_request_id line.
const legacy = legacyContext({
  prelude: [
    "var CAPTURED=null;var _job1790=async function(endpoint,payload){payload={...(payload||{}),client_request_id:(payload?.client_request_id||'REQ-FIXED')};CAPTURED=payload;return null};",
    "var aiProviderLabel=function(){return 'AI partner'};",
    `var __meta=function(t,payload,elapsed){let pm={textContent:''};${statement("let hb=t.heartbeat_age_seconds==null?'—':fmtTime(t.heartbeat_age_seconds)", "+' · '+cost;")}return pm.textContent};`,
  ],
  functions: ["fmtTime", "usualRange", "activeProvider1790", "job"],
});

describe("time formats are the classic ones", () => {
  it.each([0, 0.4, 1, 59.4, 59.6, 60, 61, 119.5, 3599, 3600, 3661, 7322, -5, null, "12"])("fmtTime(%j)", (x) => {
    expect(fmtTime(x)).toBe(legacy.run("fmtTime(__x)", { __x: x }));
  });
  it.each([[[10, 90]], [[1]], [null], ["x"], [[3600, 7200]]])("usualRange(%j)", (x) => {
    expect(usualRange(x)).toBe(legacy.run("usualRange(__x)", { __x: x }));
  });
});

describe("jobPayload is what the classic wrapper and job POST", () => {
  const cases = [
    { name: "a saved project, Claude Code", PROJECT_ID: "PRJ-1", PROJECT_REVISION_1790: 4, provider: "claude_code_subscription", payload: { briefing: { goal: "x" }, project: { title: "t", run_policy: { cost_mode: "REFERENCE" } } } },
    { name: "an unsaved project", PROJECT_ID: null, PROJECT_REVISION_1790: null, provider: "claude_code_subscription", payload: { n: 300 } },
    { name: "no revision yet, one in the payload", PROJECT_ID: "PRJ-2", PROJECT_REVISION_1790: null, provider: "anthropic", payload: { project_revision: 2, spec: { a: 1 } } },
    { name: "another provider is not forced", PROJECT_ID: "PRJ-3", PROJECT_REVISION_1790: 1, provider: "openai", payload: { project: { run_policy: {} } } },
    { name: "a caller's request id is kept", PROJECT_ID: "PRJ-4", PROJECT_REVISION_1790: 1, provider: "anthropic", payload: { client_request_id: "MINE" } },
  ];
  it.each(cases.map((c) => [c.name, c] as const))("%s", async (_, c) => {
    const globals = { PROJECT_ID: c.PROJECT_ID, PROJECT_REVISION_1790: c.PROJECT_REVISION_1790, PROJECT_META_1790: { preferred_provider: c.provider }, PROJECT: {}, BOOT: {} };
    await legacy.run("job('/api/x', __p, 't')", { ...globals, __p: c.payload });
    const expected = legacy.run("CAPTURED");
    const mine = jobPayload(structuredClone(c.payload), { projectId: c.PROJECT_ID, revision: c.PROJECT_REVISION_1790, provider: c.provider }, "REQ-FIXED");
    expect(mine).toEqual(expected);
    expect(Object.keys(mine)).toEqual(Object.keys(expected as object));
  });
});

describe("the meta line is the classic one", () => {
  const telemetries = [
    {},
    { elapsed_seconds: 75, usual_seconds: [30, 90], hard_seconds: 900, provider_stage: "print", heartbeat_age_seconds: 3, provider: "claude_code_subscription", model: "sonnet" },
    { provider: "anthropic", actual_cost_usd: 0.01234 },
    { provider: "anthropic", estimated_cost_usd: 0.5, heartbeat_age_seconds: 0 },
    { provider: "strict_claude_x" },
  ];
  it.each(telemetries.map((t, i) => [i, t] as const))("telemetry %i", (_, t) => {
    // The classic job computes `elapsed` first: Number(t.elapsed_seconds ?? <wall clock>).
    const expected = legacy.run("__meta(__t,__payload,Number(__t.elapsed_seconds??42))", { __t: t, __payload: { model: "opus" } });
    expect(jobMetaLine(jobMeta({ telemetry: t } as JobRead, { model: "opus", elapsed: 42 }))).toBe(expected);
  });
});

describe("jobOutcome", () => {
  it("says what each state means, in the classic words", () => {
    expect(jobOutcome({ state: "done", result: { a: 1 } })).toEqual({ kind: "done", result: { a: 1 } });
    expect(jobOutcome({ state: "running" })).toEqual({ kind: "running" });
    expect(jobOutcome({ state: "queued" })).toEqual({ kind: "running" });
    expect(jobOutcome({ state: "waiting_user" })).toMatchObject({ message: "AI krok čeká na zásah. Projekt zůstává uložený." });
    expect(jobOutcome({ state: "waiting_user", result: { error: "Doplňte cíl." } })).toMatchObject({ message: "Doplňte cíl." });
    expect(jobOutcome({ state: "paused", phase: "Limit." })).toMatchObject({ note: "Běh je bezpečně pozastaven. Limit. · checkpoint zůstává uložený" });
    expect(jobOutcome({ state: "error", telemetry: { provider_error: "429" } })).toMatchObject({ message: "429" });
    expect(jobOutcome({ state: "error" })).toMatchObject({ message: "AI krok se nepodařilo dokončit. Projekt zůstává uložený; otevřete Diagnostiku." });
    expect(jobOutcome({ state: "cancelled" })).toMatchObject({ kind: "cancelled", message: "JOB_CANCELLED: Běh byl zrušen uživatelem." });
  });
});

function unitStub(reads: JobRead[]) {
  const calls: { url: string; body: unknown }[] = [];
  const fetchImpl = vi.fn<typeof fetch>(async (url, init) => {
    calls.push({ url: String(url), body: init?.body ? JSON.parse(String(init.body)) : undefined });
    const answer = String(url).startsWith("/api/job?") ? (reads.shift() ?? { state: "running" }) : { job_id: "JOB-1" };
    return new Response(JSON.stringify(answer), { status: 200 });
  });
  return { calls, fetchImpl };
}
const ctx = { projectId: "PRJ-1", revision: 3, provider: "claude_code_subscription" };
const quick = { sleep: async () => {}, now: () => 1_000, requestId: () => "REQ-T" };

describe("runJob", () => {
  it("starts the job, reads it every poll and resolves with its result", async () => {
    const { calls, fetchImpl } = unitStub([{ state: "running", phase: "AI čte zadání" }, { state: "paused", phase: "Limit" }, { state: "done", result: { analysis: { objectives: ["a"] } } }]);
    const updates: JobUpdate[] = [];
    const result = await runJob("researchAnalyze", { n: 300 }, { title: "AI chápe aktuální zadání", ctx, fetchImpl, onUpdate: (u) => updates.push(u), ...quick });
    expect(result).toEqual({ analysis: { objectives: ["a"] } });
    expect(calls[0]).toEqual({ url: "/api/research/analyze", body: { n: 300, project_id: "PRJ-1", project_revision: 3, provider: "claude_code_subscription", client_request_id: "REQ-T" } });
    expect(calls.slice(1).map((c) => c.url)).toEqual(["/api/job?id=JOB-1", "/api/job?id=JOB-1", "/api/job?id=JOB-1"]);
    expect(updates.map((u) => u.phase)).toEqual(["Zakládám durable úlohu…", "AI čte zadání", "Limit", "Pracuji…"]);
    expect(updates[2].paused).toContain("Běh je bezpečně pozastaven.");
  });

  it.each([
    ["error", { state: "error", result: { error: "Provider selhal." } }, "Provider selhal."],
    ["waiting_user", { state: "waiting_user" }, "AI krok čeká na zásah. Projekt zůstává uložený."],
    ["cancelled", { state: "cancelled" }, "JOB_CANCELLED: Běh byl zrušen uživatelem."],
  ])("throws a JobError when the job ends %s", async (kind, read, message) => {
    const { fetchImpl } = unitStub([read as JobRead]);
    const err = await runJob("researchAnalyze", {}, { title: "t", ctx, fetchImpl, ...quick }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(JobError);
    expect(err).toMatchObject({ kind, message, jobId: "JOB-1" });
  });

  it("refuses a second job while one runs, and frees the slot when it ends", async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((r) => (release = r));
    const { fetchImpl } = unitStub([{ state: "done", result: 1 }]);
    const first = runJob("researchAnalyze", {}, { title: "t", ctx, fetchImpl, ...quick, sleep: () => gate });
    await Promise.resolve();
    await expect(runJob("researchAnalyze", {}, { title: "t", ctx, fetchImpl, ...quick })).rejects.toMatchObject({ kind: "busy", message: JOB_BUSY });
    release();
    await expect(first).resolves.toBe(1);
    const again = unitStub([{ state: "done", result: 2 }]);
    await expect(runJob("researchAnalyze", {}, { title: "t", ctx, fetchImpl: again.fetchImpl, ...quick })).resolves.toBe(2);
  });

  it("cancels with the classic body", async () => {
    const { calls, fetchImpl } = unitStub([]);
    await cancelJob("JOB 9", fetchImpl);
    expect(calls[0]).toEqual({ url: "/api/jobs/JOB%209/cancel", body: { source: "ui_progress_button", reason: "explicit_user_confirmation" } });
    expect(CANCEL_CONFIRM).toBe("Opravdu chcete tento běh zrušit? Rozpracovaný krok se bezpečně ukončí.");
  });
});
