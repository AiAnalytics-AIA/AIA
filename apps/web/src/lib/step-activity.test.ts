// A running step's activity is what its events said, folded per step, in words; nothing else.
import { describe as group, expect, it } from "vitest";

import type { RunEvent } from "./api";
import { EMPTY_ACTIVITY, KEEP_LINES, activityOf, describe, foldActivity } from "./step-activity";

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
