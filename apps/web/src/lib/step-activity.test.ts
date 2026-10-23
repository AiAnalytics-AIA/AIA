// A running step's activity is what its events said, folded per step, in words; nothing else.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe as group, expect, it } from "vitest";

import { t, tv } from "@/i18n/t";

import type { RunEvent } from "./api";
import { EMPTY_ACTIVITY, KEEP_LINES, activityOf, describe, foldActivity, lastReported } from "./step-activity";

let id = 0;
const ev = (over: Partial<RunEvent>): RunEvent => ({
  event_id: ++id,
  step_id: "STEP-a",
  attempt_id: "ATT-1",
  event_type: "STEP_PROGRESS",
  level: "INFO",
  message: "",
  payload: {},
  created_at: "2026-10-12T08:00:00Z",
  ...over,
});
const text = (e: RunEvent) => describe(e)?.text ?? null;

group("one event in words", () => {
  it("a step's own sentence stays as it is, with the counts it reported", () => {
    expect(text(ev({ message: "AI respondenti odpověděli", payload: { respondents: 40, of: 300 } }))).toBe(
      "AI respondenti odpověděli · 40 z 300 respondentů",
    );
    expect(text(ev({ message: "AI analyzuje modul", payload: { module: "executive", turn: 2 } }))).toBe(
      "AI analyzuje modul · modul executive, kolo 2",
    );
    expect(text(ev({ message: "agregace spočtena", payload: { artifact_id: "ART-1" } }))).toBe("agregace spočtena");
  });

  it("the engine's transitions say what happened, the reason without the node key", () => {
    expect(text(ev({ event_type: "ATTEMPT_CLAIMED", message: "run claimed by worker-1" }))).toBe("Worker krok převzal");
    expect(text(ev({ event_type: "STEP_SUCCEEDED", message: "run completed" }))).toBe("Krok dokončen");
    expect(describe(ev({ event_type: "STEP_DEFERRED", message: "run: provider quota" }))).toMatchObject({
      text: "Krok odložen: provider quota",
      level: "warn",
    });
  });

  it("a Deep Research code reads as words with its counts", () => {
    expect(text(ev({ message: "deep_research_plan", payload: { tracks: 5, planned: 3, reusable: 1, blocked: 1, beyond_limit: 0 } }))).toBe(
      "Plán: 3 stop k prozkoumání, 1 převzato z dřívějška, 1 blokováno",
    );
    expect(text(ev({ message: "deep_research_tool_succeeded", payload: { tool: "web_search", cost_usd: 0 } }))).toBe(
      "Vyhledávání dokončeno",
    );
    expect(describe(ev({ message: "deep_research_tool_failed", payload: { tool: "web_fetch" } }))?.level).toBe("warn");
  });

  it("a code it does not know, or one missing a count, says nothing rather than a guess", () => {
    expect(text(ev({ message: "deep_research_unknown", payload: { x: 1 } }))).toBeNull();
    expect(text(ev({ message: "deep_research_plan", payload: { planned: 3 } }))).toBeNull();
    expect(text(ev({ message: "deep_research_tool_succeeded", payload: { tool: "teleport" } }))).toBeNull();
    expect(text(ev({ message: "ai_request_answered", payload: { input_tokens: 10 } }))).toBeNull();
    // Tokens the provider did not report are said to be missing, not zero.
    expect(text(ev({ message: "ai_request_answered", payload: { input_tokens: null, output_tokens: null, cost_usd: 0.01, latency_ms: 500 } }))).toBe(
      "Model odpověděl · tokeny neuvedeny · $0.010 · 0.5 s",
    );
    expect(text(ev({ event_type: "RUN_STATUS", message: "RUNNING" }))).toBeNull();
  });

  it("a model's answer reads with its real tokens, cost and time", () => {
    expect(text(ev({ message: "ai_request_answered", payload: { input_tokens: 1200, output_tokens: 380, cost_usd: 0.0042, latency_ms: 3200 } }))).toBe(
      "Model odpověděl · 1200 → 380 tokenů · $0.004 · 3.2 s",
    );
  });
});

group("folding a feed", () => {
  it("keeps each step's own lines, newest last, and moves the cursor", () => {
    const a1 = ev({ step_id: "STEP-a", event_type: "ATTEMPT_CLAIMED", message: "x" });
    const b1 = ev({ step_id: "STEP-b", message: "agregace spočtena" });
    const run = ev({ step_id: null, event_type: "RUN_STATUS", message: "RUNNING" });
    const state = foldActivity(EMPTY_ACTIVITY, [b1, a1, run]);
    expect(state.cursor).toBe(run.event_id);
    expect(activityOf(state, "STEP-a")?.lines.map((l) => l.text)).toEqual(["Worker krok převzal"]);
    expect(activityOf(state, "STEP-b")?.lines.map((l) => l.text)).toEqual(["agregace spočtena"]);
    expect(activityOf(state, null)).toBeNull();
  });

  it("the same events read twice change nothing", () => {
    const events = [ev({ message: "AI respondenti odpověděli", payload: { respondents: 10, of: 50 } })];
    const once = foldActivity(EMPTY_ACTIVITY, events);
    expect(foldActivity(once, events)).toEqual(once);
  });

  it("keeps the latest count, the last few lines, and sums model answers and web calls", () => {
    let state = EMPTY_ACTIVITY;
    for (let i = 1; i <= KEEP_LINES + 3; i++) {
      state = foldActivity(state, [ev({ message: "AI respondenti odpověděli", payload: { respondents: i * 10, of: 300 } })]);
    }
    state = foldActivity(state, [
      ev({ message: "ai_request_answered", payload: { input_tokens: 100, output_tokens: 50, cost_usd: 0.01, latency_ms: 900 } }),
      ev({ message: "ai_request_answered", payload: { input_tokens: 200, output_tokens: 20, cost_usd: 0.02, latency_ms: 800 } }),
      ev({ message: "deep_research_tool_succeeded", payload: { tool: "web_fetch" } }),
      ev({ message: "deep_research_tool_failed", payload: { tool: "web_fetch" } }),
    ]);
    const a = activityOf(state, "STEP-a")!;
    expect(a.progress).toEqual({ done: (KEEP_LINES + 3) * 10, of: 300 });
    expect(a.lines).toHaveLength(KEEP_LINES);
    expect(a.lines.at(-1)?.text).toBe("Stažení stránky selhalo");
    expect(a.model).toEqual({ answered: 2, tokens: 370, costUsd: 0.03 });
    expect(a.toolCalls).toBe(1);
    // One answer without counts makes the total unknown, not smaller.
    const unknown = foldActivity(state, [ev({ message: "ai_request_answered", payload: { input_tokens: null, output_tokens: null, cost_usd: 0, latency_ms: 1 } })]);
    expect(activityOf(unknown, "STEP-a")?.model).toEqual({ answered: 3, tokens: null, costUsd: 0.03 });
  });
});

group("the fieldwork event contract (run-qc-and-checkpoint RQC7)", () => {
  // The case file the domain holds too (packages/aia_core/src/aia_core/domain/fieldwork_events.py).
  const contract = JSON.parse(
    readFileSync(join(process.cwd(), "../../packages/aia_core/tests/fixtures/fieldwork_events/contract.json"), "utf8"),
  ) as { version: string; events: Record<string, string[]> };
  const sample: Record<string, Record<string, unknown>> = {
    fieldwork_progress: { respondents: 40, of: 300, sent: 70, replayed: 50 },
    fieldwork_sample: {
      quota_fields: ["pohlavi", "vek"],
      cells: [
        { key: "zena/18-29", values: ["žena", "18-29"], n: 2 },
        { key: "muz/30-44", values: ["muž", "30-44"], n: 1 },
      ],
    },
    fieldwork_respondent: { respondent: 1, cell: "zena/18-29", sent: 2, replayed: 0 },
  };
  const of = (code: string) => ev({ message: code, payload: { version: contract.version, ...sample[code] } });

  it("reads every event of the contract: in words, or one respondent folded into its cell", () => {
    expect(Object.keys(contract.events).sort()).toEqual(Object.keys(sample).sort());
    for (const [code, keys] of Object.entries(contract.events)) {
      expect(Object.keys(of(code).payload ?? {}).sort()).toEqual([...keys].sort());
      if (code === "fieldwork_respondent") continue;
      expect(text(of(code))).not.toBeNull();
    }
    // A respondent is no log line of its own (hundreds would bury the rest): its cell's fill.
    expect(text(of("fieldwork_respondent"))).toBeNull();
    const folded = foldActivity(EMPTY_ACTIVITY, [of("fieldwork_sample"), of("fieldwork_respondent")]);
    expect(activityOf(folded, "STEP-a")?.quota?.cells.map((c) => c.answered)).toEqual([1, 0]);
  });

  it("fills each quota cell from its respondents; a new attempt counts again; a broken list is none (RQC7b)", () => {
    const respondent = (cell: string | null) => ev({ message: "fieldwork_respondent", payload: { respondent: 1, cell, sent: 1, replayed: 0 } });
    const state = foldActivity(EMPTY_ACTIVITY, [
      respondent("zena/18-29"), // before any cells: nothing to fill
      of("fieldwork_sample"),
      respondent("zena/18-29"),
      respondent("zena/18-29"),
      respondent("muz/30-44"),
      respondent("neznama"), // a cell the sample did not name fills nothing
      respondent(null),
    ]);
    const quota = activityOf(state, "STEP-a")?.quota;
    expect(quota?.cells).toEqual([
      { key: "zena/18-29", values: ["žena", "18-29"], n: 2, answered: 2 },
      { key: "muz/30-44", values: ["muž", "30-44"], n: 1, answered: 1 },
    ]);
    expect(activityOf(state, "STEP-a")?.lines.at(-1)?.text).toBe(tv("research.exec.activity.fieldworkSample", { cells: 2 }));
    // A retried attempt reports its cells again and counts its respondents from the first.
    const retried = foldActivity(state, [of("fieldwork_sample"), respondent("muz/30-44")]);
    expect(activityOf(retried, "STEP-a")?.quota?.cells.map((c) => c.answered)).toEqual([0, 1]);
    // One unreadable cell refuses the table: never a partial list read as the whole.
    const broken = ev({ message: "fieldwork_sample", payload: { quota_fields: [], cells: [{ key: "a", values: ["a"], n: 1 }, { key: "b", n: 1 }] } });
    expect(text(broken)).toBeNull();
    expect(activityOf(foldActivity(state, [broken]), "STEP-a")?.quota).toBeNull();
    // No cells (a sample drawn without quota fields) is no table, never "0 z 0".
    const none = ev({ message: "fieldwork_sample", payload: { quota_fields: [], cells: [] } });
    expect(text(none)).toBeNull();
    expect(activityOf(foldActivity(state, [none]), "STEP-a")?.quota).toBeNull();
    // A fold counts into its own copy: the state it was given is never changed.
    const before = activityOf(state, "STEP-a")?.quota?.cells.map((c) => c.answered);
    foldActivity(state, [respondent("zena/18-29"), respondent("zena/18-29")]);
    expect(activityOf(state, "STEP-a")?.quota?.cells.map((c) => c.answered)).toEqual(before);
  });

  it("reads progress as counted, the blocks replayed at no cost said only when there are any", () => {
    expect(text(ev({ message: "fieldwork_progress", payload: { respondents: 40, of: 300, sent: 70, replayed: 50 } }))).toBe(
      `${tv("research.exec.activity.fieldworkProgress", { done: 40, of: 300 })} · ${tv("research.exec.activity.fieldworkReplayed", { replayed: 50 })}`,
    );
    expect(text(ev({ message: "fieldwork_progress", payload: { respondents: 4, of: 30, sent: 8, replayed: 0 } }))).toBe(
      tv("research.exec.activity.fieldworkProgress", { done: 4, of: 30 }),
    );
    expect(text(ev({ message: "fieldwork_progress", payload: {} }))).toBeNull();
    const folded = foldActivity(EMPTY_ACTIVITY, [ev({ message: "fieldwork_progress", payload: { respondents: 40, of: 300, sent: 70, replayed: 0 } })]);
    expect(activityOf(folded, "STEP-a")?.progress).toEqual({ done: 40, of: 300 });
  });

  it("keeps a stopped step's count as last reported, with what came from the checkpoint (FLD3)", () => {
    const folded = foldActivity(EMPTY_ACTIVITY, [
      ev({ message: "fieldwork_progress", payload: { respondents: 10, of: 300, sent: 10, replayed: 50 } }),
      ev({ message: "fieldwork_progress", payload: { respondents: 40, of: 300, sent: 70, replayed: 50 } }),
    ]);
    const a = activityOf(folded, "STEP-a");
    expect(a?.replayed).toBe(50);
    const last = tv("research.exec.activity.lastReported", { done: 40, of: 300 });
    const stopped = `${last} · ${tv("research.exec.activity.fieldworkReplayed", { replayed: 50 })}`;
    for (const status of ["WAITING_PROVIDER", "AWAITING_BUDGET", "RECOVERY_REQUIRED", "FAILED", "CANCELLED"]) {
      expect(lastReported(a, status, false)).toBe(stopped);
    }
    // A step still marked running in a run that ended stopped there.
    expect(lastReported(a, "RUNNING", true)).toBe(stopped);
    // Running (its panel says it), queued for another attempt, succeeded or skipped: no old count.
    for (const status of ["RUNNING", "RUNNABLE", "CLAIMED", "BLOCKED", "SUCCEEDED", "SKIPPED"]) {
      expect(lastReported(a, status, false)).toBeNull();
    }
    expect(lastReported(activityOf(EMPTY_ACTIVITY, "STEP-a"), "WAITING_PROVIDER", false)).toBeNull();
    // A later attempt's event without `replayed` replayed nothing; the earlier attempt's count is not kept.
    const retried = foldActivity(folded, [ev({ message: "fieldwork_progress", payload: { respondents: 4, of: 30, sent: 8 } })]);
    expect(lastReported(activityOf(retried, "STEP-a"), "CANCELLED", false)).toBe(tv("research.exec.activity.lastReported", { done: 4, of: 30 }));
  });
});
