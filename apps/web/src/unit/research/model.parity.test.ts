import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { legacyContext, statement } from "../testing/legacy";
import { type Boot, PROBLEM_TYPES, type ResearchProject, briefFingerprint, defaultsMerge, selectedProblemTypes } from "./model";

// The research model against the classic interface's own functions, run under
// Node. The empty project is the unit's own template (GET /api/bootstrap),
// captured from the workbench: a template, no data.
const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/unit/research/fixtures/empty-project.json"), "utf8"));

const legacy = legacyContext({
  prelude: [
    "const clone=x=>JSON.parse(JSON.stringify(x));",
    "var PROBLEM_TYPES_1785=[];",
    statement("PROBLEM_TYPES_1785.splice(0,PROBLEM_TYPES_1785.length,", ");"),
  ],
  functions: ["defaultsMerge", "selectedProblemTypes1789", "briefFingerprint1780"],
});

const BOOTS: Boot[] = [
  { empty_project: EMPTY, ai_provider: "claude_code_subscription" },
  { empty_project: { ...EMPTY, run_policy: undefined, budget: undefined, ui_state: undefined }, ai_provider: "anthropic" },
];
const STORED: unknown[] = [
  null,
  {},
  { title: "Alfa", goal: "Zjistit cenu", n: 800, briefing: { situation: "trh" }, audience: { filters: { kraj: ["A"] } } },
  { audience: { strategy: "discover" }, run_policy: { provider: "anthropic", phase_overrides: { run: "x" } }, sections: [{ id: "s1" }] },
  { ui_state: { questionnaire_path: "manual", extra: 1 }, model: "opus", panel_mode: "special", unknown_field: { kept: true } },
];

describe("defaultsMerge is the classic defaultsMerge", () => {
  for (const [i, boot] of BOOTS.entries()) {
    for (const [j, stored] of STORED.entries()) {
      it(`boot ${i}, stored ${j}`, () => {
        const expected = legacy.run("defaultsMerge(__p)", { BOOT: boot, __p: stored });
        expect(defaultsMerge(stored, boot)).toEqual(expected);
      });
    }
  }
});

describe("the problem types and the brief fingerprint are the classic ones", () => {
  it("PROBLEM_TYPES is PROBLEM_TYPES_1785 after its final splice", () => {
    expect(legacy.run("PROBLEM_TYPES_1785")).toEqual(PROBLEM_TYPES.map((t) => [...t]));
  });

  const base = defaultsMerge({}, BOOTS[0]);
  const projects: ResearchProject[] = [
    base,
    { ...base, goal: "  Cíl  ", decision_use: "rozhodnutí", briefing: { ...base.briefing, problem_types: ["price", "brand", "price", "nope"] } },
    { ...base, briefing: { ...base.briefing, problem_types: [] }, ui_state: { ...base.ui_state, problem_types: ["tracking"] } },
    { ...base, briefing: { ...base.briefing, problem_type: "audience", review_comments: " 1. K textu " } },
    {
      ...base,
      briefing: {
        ...base.briefing,
        attachments: [{ sha256: "abc", filename: "a.pdf" }, { url: "https://x.test" }, { filename: "b.txt" }, {}],
      },
    },
  ];
  it.each(projects.map((p, i) => [i, p] as const))("project %i", (_, p) => {
    expect(selectedProblemTypes(p)).toEqual(legacy.run("selectedProblemTypes1789()", { PROJECT: p }));
    expect(briefFingerprint(p)).toBe(legacy.run("briefFingerprint1780()", { PROJECT: p }));
  });
});
