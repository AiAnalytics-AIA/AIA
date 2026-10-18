import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { blockers, designLane, questionnaireIssues, runLane } from "./lane";
import type { ResearchProject } from "./model";
import type { ResearchPhase, ResearchStep } from "@/lib/api";

const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/research/fixtures/empty-project.json"), "utf8")) as ResearchProject;
const project = (over: Record<string, unknown> = {}): ResearchProject => ({ ...structuredClone(EMPTY), ...over }) as ResearchProject;

const banks = { type: "object_battery", title: "Banky", objects: ["Horizont", "Spořitelna", "ČSOB", "Fio"] };
const block = (texts: string[]) => ({ type: "questions", title: "B1", questions: texts.map((text, i) => ({ id: `Q${i + 1}`, type: "single", text })) });

describe("designLane", () => {
  it("says a new study's stages are not started, and only the brief needs a person", () => {
    const lane = designLane({ project: project(), analysis: null });
    expect(lane.brief).toEqual({ tone: "you", line: "Chybí cíl" });
    expect(lane.plan.tone).toBe("idle");
    expect(lane.questionnaire).toEqual({ tone: "idle", line: "Zatím prázdný" });
    expect(lane.audience).toEqual({ tone: "idle", line: "Nevybráno" });
  });

  it("says a new study chose no dimension, never the recommended set as if it had (OI-54)", () => {
    // Reported by the owner on 2026-10-18: a new study's track read "4 dimenze · N=300".
    expect(designLane({ project: project(), analysis: null }).persona).toEqual({ tone: "done", line: "Bez dimenzí · N=300" });
    const chosen = project({ persona_dimensions: { approved: ["media", "cena"] } });
    expect(designLane({ project: chosen, analysis: null }).persona).toEqual({ tone: "done", line: "2 dimenze · N=300" });
  });

  it("marks the brief done once it has a goal", () => {
    expect(designLane({ project: project({ goal: "Jak nás vnímají" }), analysis: null }).brief.tone).toBe("done");
  });

  it("counts regular questions and sets apart, and names a question without wording", () => {
    const p = project({ sections: [block(["Hlavní banka?", "  "]), banks] as never });
    expect(questionnaireIssues(p)).toEqual({ questions: 2, sets: 1, empty: 1, badSets: 0 });
    expect(designLane({ project: p, analysis: null }).questionnaire).toEqual({ tone: "you", line: "2 otázky · 1 sada · 1 bez znění" });
  });

  it("names a tracked set outside 4-15 in the plan and in the questionnaire", () => {
    const small = { ...banks, objects: ["A", "B", "C"] };
    const p = project({ sections: [block(["Hlavní banka?"]), small] as never });
    expect(designLane({ project: p, analysis: null }).questionnaire.line).toBe("1 otázka · 1 sada · 1 sada mimo 4–15");
    expect(designLane({ project: p, analysis: { tracked_sets: [small] } as never }).plan).toEqual({ tone: "you", line: "1 sada mimo 4–15" });
  });

  it("says the audience is chosen only under the wizard's own condition", () => {
    const p = project({ ui_state: { ...EMPTY.ui_state, audience_entry: "analytics", analytics_choice: "cz18" } as never });
    expect(designLane({ project: p, analysis: null }).audience.tone).toBe("done");
  });
});

describe("blockers", () => {
  it("lists what a new study still lacks, in stage order", () => {
    expect(blockers({ project: project(), analysis: null }).map((b) => b.step)).toEqual(["brief", "questionnaire", "audience"]);
  });

  it("is empty for a design the stages would let run", () => {
    const p = project({
      goal: "Jak nás vnímají",
      sections: [block(["Hlavní banka?"]), banks] as never,
      ui_state: { ...EMPTY.ui_state, audience_entry: "analytics", analytics_choice: "cz18" } as never,
    });
    expect(blockers({ project: p, analysis: null })).toEqual([]);
  });

  it("points a question without wording to the questionnaire", () => {
    const p = project({ goal: "x", sections: [block([""])] as never });
    expect(blockers({ project: p, analysis: null })).toContainEqual({ step: "questionnaire", label: "Dotazník", detail: "1 otázka nemá znění" });
  });
});

describe("runLane", () => {
  const data = { node_key: "aggregate", kind: "research", status: "SUCCEEDED", artifact_id: "ART-1" } as ResearchStep;
  const blocked = { node_key: "analysis_executive", kind: "research_analysis", status: "SUCCEEDED", analysis_outcome: "BLOCKED" } as ResearchStep;
  const ran = (phase: ResearchPhase, design_revision: number, steps: ResearchStep[] = []) =>
    ({ phase, design_revision, is_terminal: !["RUNNING", "QUEUED", "WAITING"].includes(phase), steps });

  it("says nothing before the runs are loaded, and that nothing ran when none did", () => {
    expect(runLane(null).progress).toEqual({ tone: "idle", line: "" });
    expect(runLane([]).run).toEqual({ tone: "idle", line: "Nespuštěno" });
  });

  it("follows the newest run, and points results at the newest one whose results are ready", () => {
    const lane = runLane([ran("RUNNING", 4), ran("COMPLETED", 3, [data])]);
    expect(lane.progress).toEqual({ tone: "running", line: "Běh 2: běží" });
    expect(lane.results).toEqual({ tone: "done", line: "Revize 3" });
  });

  it("names a waiting run as needing a person and a run without data as a fault", () => {
    expect(runLane([ran("WAITING", 1)]).progress.tone).toBe("you");
    const stopped = { node_key: "run", kind: "research", status: "FAILED", artifact_id: null } as ResearchStep;
    expect(runLane([ran("FAILED", 1, [stopped])]).progress).toEqual({ tone: "fault", line: "Běh 1: bez dat k vyhodnocení" });
    // Listed without its steps (an older API), an ended run says only its phase.
    expect(runLane([ran("COMPLETED", 1)]).progress).toEqual({ tone: "idle", line: "Běh 1: dokončeno" });
  });

  it("never calls a completed run with a blocked module done, nor its results ready", () => {
    const lane = runLane([ran("COMPLETED", 2, [data, blocked])]);
    expect(lane.progress).toEqual({ tone: "fault", line: "Běh 1: potřebuje opravu" });
    expect(lane.results).toEqual({ tone: "idle", line: "Zatím nic" });
  });
});
