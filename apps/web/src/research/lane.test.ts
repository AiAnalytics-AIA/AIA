import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { blockers, designLane, questionnaireIssues, runLane } from "./lane";
import type { ResearchProject } from "./model";

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
  it("says nothing before the runs are loaded, and that nothing ran when none did", () => {
    expect(runLane(null).progress).toEqual({ tone: "idle", line: "" });
    expect(runLane([]).run).toEqual({ tone: "idle", line: "Nespuštěno" });
  });

  it("follows the newest run, and points results at the newest completed one", () => {
    const lane = runLane([
      { phase: "RUNNING", design_revision: 4, finished_at: null },
      { phase: "COMPLETED", design_revision: 3, finished_at: "2026-10-09T16:40:00Z" },
    ]);
    expect(lane.progress).toEqual({ tone: "running", line: "Běh 2 běží" });
    expect(lane.results).toEqual({ tone: "done", line: "Revize 3" });
  });

  it("names a waiting run as needing a person and a failed one as a fault", () => {
    expect(runLane([{ phase: "WAITING", design_revision: 1, finished_at: null }]).progress.tone).toBe("you");
    expect(runLane([{ phase: "FAILED", design_revision: 1, finished_at: null }]).progress.tone).toBe("fault");
  });
});
