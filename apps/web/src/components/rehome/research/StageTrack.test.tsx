// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StageTrack } from "./StageTrack";
import { stagePath } from "./test-frame";
import { signedIn } from "./test-workspace";

const RUNS = "/api/v1/studies/STU-1/research/runs";
const data = { node_key: "aggregate", kind: "research", status: "SUCCEEDED", artifact_id: "ART-1" };

const run = (phase: string, over: Record<string, unknown> = {}) => ({
  run_id: "RUN-1", study_id: "STU-1", design_revision_id: "REV-1", design_revision: 1, status: phase,
  phase, needs_attention: false, is_terminal: !["QUEUED", "RUNNING", "WAITING"].includes(phase),
  retryable: false, cancel_requested: false, fieldwork_source: "synthetic_fixture", retry_of: null, created: null,
  created_at: null, started_at: null, finished_at: null, steps: phase === "COMPLETED" ? [data] : [], artifact_ids: [],
  actual_cost_usd: 0, ...over,
});

let answers: unknown[] = [];
let reads = 0;
const LIMITS = "/api/v1/studies/STU-1/research/limits";
let limits: unknown = null;

beforeEach(() => {
  signedIn();
  reads = 0;
  limits = null;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL) => {
      const u = String(url).split("?")[0];
      if (u === "/config") return new Response(JSON.stringify({ apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost" }));
      if (u === LIMITS && limits) return new Response(JSON.stringify(limits));
      if (u !== RUNS) return new Response("{}", { status: 404 });
      const answer = answers[Math.min(reads, answers.length - 1)];
      reads += 1;
      return new Response(JSON.stringify({ items: answer }));
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  sessionStorage.clear();
});

describe("StageTrack", () => {
  it("judges a tracked set by the readiness methodology in force (#736)", async () => {
    // A stored maximum of 30: a 31-object set is outside what compile takes, whatever the preset says.
    answers = [[]];
    limits = { methodology_version: "aia-readiness-1+e1", version: 1, sample_size: { min: 20, max: 10000 }, tracked_set: { min: 3, max: 30, recommended_min: 5, recommended_max: 12 } };
    const set = { type: "object_battery", title: "Značky", objects: Array.from({ length: 31 }, (_, i) => `Z${i}`) };
    const empty = JSON.parse(readFileSync(join(process.cwd(), "src/research/fixtures/empty-project.json"), "utf8"));
    const state = { project: { ...empty, sections: [{ type: "questions", questions: [{ text: "Jak často?" }] }, set] }, analysis: null } as never;
    render(<StageTrack studyId="STU-1" state={state} current="questionnaire" stepHref={stagePath} />);
    expect(await screen.findByText("1 otázka · 1 sada · 1 sada mimo 5–30")).toBeTruthy();
  });

  it("follows a running run to its results without a reload", async () => {
    // productization-coherence PC5: read once, the track said "běží" beside a finished run.
    answers = [[run("RUNNING")], [run("COMPLETED")]];
    render(<StageTrack studyId="STU-1" state={null} current="progress" stepHref={stagePath} />);
    expect(await screen.findByText("Běh 1: běží")).toBeTruthy();
    expect(screen.getByText("Zatím nic")).toBeTruthy();
    expect(await screen.findByText("Běh 1: výsledky jsou hotové")).toBeTruthy();
    expect(screen.getByText("Revize 1")).toBeTruthy();
  });

  it("stops reading once nothing can change on its own", async () => {
    answers = [[run("COMPLETED")]];
    render(<StageTrack studyId="STU-1" state={null} current="results" stepHref={stagePath} />);
    expect(await screen.findByText("Běh 1: výsledky jsou hotové")).toBeTruthy();
    await new Promise((r) => setTimeout(r, 2500));
    expect(reads).toBe(1);
  });

  it("keeps reading a run that waits on a provider, which clears by itself, and not one that waits for a person", async () => {
    answers = [[run("WAITING", { steps: [{ node_key: "run", kind: "research", status: "WAITING_CAPACITY", artifact_id: null }] })]];
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { unmount } = render(<StageTrack studyId="STU-1" state={null} current="progress" stepHref={stagePath} />);
    await vi.waitFor(() => expect(reads).toBe(1));
    await vi.advanceTimersByTimeAsync(10_000);
    await vi.waitFor(() => expect(reads).toBe(2));
    unmount();

    reads = 0;
    answers = [[run("WAITING", { needs_attention: true, steps: [{ node_key: "run", kind: "research", status: "AWAITING_BUDGET", artifact_id: null }] })]];
    render(<StageTrack studyId="STU-1" state={null} current="progress" stepHref={stagePath} />);
    await vi.waitFor(() => expect(reads).toBe(1));
    await vi.advanceTimersByTimeAsync(30_000);
    expect(reads).toBe(1);
  });
});
