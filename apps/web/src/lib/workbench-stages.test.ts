// The workbench's eleven stages over today's routes (research-lead-workbench D2): every stage
// reaches a route, every route shows a stage, and a stage's tone is the lane's.
import { describe, expect, it } from "vitest";

import { PHASES, STAGES, STAGE_ORDER, fieldworkStep, openFieldwork, stageHref, stageOf, stageState } from "./workbench-stages";
import type { StepKey } from "@/research/steps";

const href = (step: StepKey) => `/s/${step}`;

describe("workbench stages", () => {
  it("are the prototype's eleven, each in one of the six phases", () => {
    expect(STAGE_ORDER).toHaveLength(11);
    const phases = new Set(PHASES.map((p) => p.id));
    for (const s of STAGE_ORDER) expect(phases.has(STAGES[s].phase)).toBe(true);
  });

  it("each open a route, and the route shows the same stage back", () => {
    for (const s of STAGE_ORDER) {
      const url = stageHref(s, href);
      const [path, hash = ""] = url.split("#");
      const step = path!.split("/").pop() as StepKey;
      expect(stageOf(step, hash ? `#${hash}` : ""), s).toBe(s);
    }
  });

  it("open Sběr dat on Průběh while the newest run moves, else on Kontrola (FLD9)", () => {
    const moving = (tone: "running" | "you" | "fault") => ({ run: { tone: "done" as const, line: "Spuštěno 1×" }, progress: { tone, line: "Běh 1" } });
    for (const tone of ["running", "you", "fault"] as const) expect(fieldworkStep(moving(tone)), tone).toBe("progress");
    // A run with its results, a cancelled one, none, and runs not yet read: Kontrola a spuštění.
    expect(fieldworkStep({ run: { tone: "done", line: "Spuštěno 1×" }, progress: { tone: "done", line: "Běh 1: výsledky připraveny" } })).toBe("run");
    expect(fieldworkStep({ run: { tone: "done", line: "Spuštěno 2×" }, progress: { tone: "idle", line: "Běh 2: zrušeno" } })).toBe("run");
    expect(fieldworkStep({ run: { tone: "idle", line: "Nespuštěno" }, progress: { tone: "idle", line: "Zatím žádný běh" } })).toBe("run");
    expect(fieldworkStep({})).toBe("run");
    expect(fieldworkStep()).toBe("run");
  });

  it("open Sběr dat from another stage by its runs, keep Průběh, and leave Kontrola for Průběh only while a run moves (FLD9)", () => {
    const moving = { progress: { tone: "running" as const, line: "Běh 1: běží" } };
    const ended = { progress: { tone: "done" as const, line: "Běh 1: výsledky připraveny" } };
    expect(openFieldwork(null, moving)).toBe("progress");
    expect(openFieldwork(null, ended)).toBe("run");
    // On Kontrola: the Lead's run card opens Průběh while a run moves, else nothing moves.
    expect(openFieldwork("run", moving)).toBe("progress");
    expect(openFieldwork("run", ended)).toBeNull();
    // On Průběh nothing moves, a finished run's progress included.
    expect(openFieldwork("progress", moving)).toBeNull();
    expect(openFieldwork("progress", ended)).toBeNull();
  });

  it("put the result views on Výsledky by the hash ResultsWorkspace reads, old anchors included", () => {
    expect(stageHref("sociomap", href)).toBe("/s/results#maps");
    expect(stageOf("results", "#measure-q3")).toBe("results");
    expect(stageOf("results", "#res-sociomap")).toBe("sociomap");
    expect(stageOf("results", "#res-literature")).toBe("report");
    expect(stageOf("results", "")).toBe("results");
    expect(stageOf("progress", "")).toBe("fieldwork");
  });

  it("read their state from the lane and say nothing for a stage the lane does not know", () => {
    const lane = {
      persona: { tone: "done" as const, line: "2 dimenze · N=600" },
      dimensions: { tone: "done" as const, line: "2 dimenze" },
      sample: { tone: "done" as const, line: "N=600" },
      run: { tone: "done" as const, line: "Spuštěno 1×" },
      progress: { tone: "running" as const, line: "Běh 1: běží" },
      results: { tone: "idle" as const, line: "Zatím nic" },
    };
    // Dimenze and Vzorek each read their own line, not the classic track's shared one (#945).
    expect(stageState("dimensions", lane)).toEqual({ tone: "done", line: "2 dimenze", word: "Hotovo" });
    expect(stageState("sample", lane)).toEqual({ tone: "done", line: "N=600", word: "Hotovo" });
    expect(stageState("fieldwork", lane)).toEqual({ tone: "running", line: "Běh 1: běží", word: "Běží" });
    expect(stageState("analysis", lane)).toEqual({ tone: "inert", line: "Zatím nic", word: "" });
    expect(stageState("brief", lane)).toEqual({ tone: "inert", line: "", word: "" });
  });

  it("call Sběr dat done only when the newest run's results are ready, never because a run was started", () => {
    const started = { tone: "done" as const, line: "Spuštěno 2×" };
    const cancelled = { run: started, progress: { tone: "idle" as const, line: "Běh 2: zrušeno" }, results: { tone: "idle" as const, line: "Zatím nic" } };
    expect(stageState("fieldwork", cancelled)).toEqual({ tone: "inert", line: "Běh 2: zrušeno", word: "" });
    const unread = { run: started, progress: { tone: "idle" as const, line: "Běh 2: neznámý stav" } };
    expect(stageState("fieldwork", unread)).toEqual({ tone: "inert", line: "Běh 2: neznámý stav", word: "" });
    const none = { run: { tone: "idle" as const, line: "Nespuštěno" }, progress: { tone: "idle" as const, line: "Zatím žádný běh" } };
    expect(stageState("fieldwork", none)).toEqual({ tone: "inert", line: "Nespuštěno", word: "" });
    const ready = { run: started, progress: { tone: "done" as const, line: "Běh 2: výsledky připraveny" } };
    expect(stageState("fieldwork", ready)).toEqual({ tone: "done", line: "Běh 2: výsledky připraveny", word: "Hotovo" });
  });

  it("call Výsledky done when a run's results are ready, and say nothing of Sociomapa, Analýza and Zpráva, which the lane does not know", () => {
    const lane = { results: { tone: "done" as const, line: "Revize 2" } };
    expect(stageState("results", lane)).toEqual({ tone: "done", line: "Revize 2", word: "Hotovo" });
    for (const view of ["sociomap", "analysis", "report"] as const) {
      expect(stageState(view, lane)).toEqual({ tone: "inert", line: "Revize 2", word: "" });
    }
  });
});
