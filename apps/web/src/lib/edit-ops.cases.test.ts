// The web's half of the working copy's edit vocabulary (ADR 0029 decision 1; working-copy-edit-ops
// WCE0): the same case file, packages/aia_core/tests/fixtures/edit_ops/cases.json, is read by
// packages/aia_core/tests/test_edit_ops.py. applyLeadEdit must make of every edit what the server's
// apply_edit makes of it, or refuse it with the same word; isTextEdit must mark the same edits as
// text; the trace must key a link and read the research questions as research_trace and
// analysis.native do. The lock and what an edit touches are the server's alone.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import type { ResearchProject } from "@/research/model";
import { linkKey, researchQuestionsOf } from "@/research/trace";
import type { Analysis } from "@/research/store";
import { applyEdit, isTextEdit, type LeadEdit, type WorkingEdit } from "./lead";

type Doc = Record<string, unknown>;
type Spec = { op: string; availability: "applied" | "declared"; in_lead_output: boolean; text: "structural" | "by_payload" };
const FILE = JSON.parse(readFileSync(join(process.cwd(), "../../packages/aia_core/tests/fixtures/edit_ops/cases.json"), "utf8")) as {
  ids: string[];
  refusals: string[];
  catalogue: Spec[];
  apply: { name: string; before: { content: Doc; analysis: Doc | null }; edit: WorkingEdit; expect: { content: Doc; analysis: Doc | null } | { refused: string } }[];
  text_edits: { edit: LeadEdit; text: boolean }[];
  link_keys: { text: string; key: string }[];
  research_questions_of: { name: string; design: Doc; expect: string[] }[];
};

/** The web's ids in the case file's order; a new section takes `sec_` and the next id's suffix. */
function ids(): () => string {
  const next = [...FILE.ids];
  return () => `Q_${next.shift()}`;
}

// Every applied operation the Lead's output carries, as the web types it (LeadEdit["op"]).
const WEB_OPS: Record<LeadEdit["op"], true> = {
  set_text: true, list_add: true, list_replace: true, list_remove: true,
  question_add: true, question_edit: true, question_remove: true, set_n: true,
};

describe("the edit vocabulary", () => {
  it("has the server's applied operations, and no other, in the web's type", () => {
    const applied = FILE.catalogue.filter((s) => s.availability === "applied" && s.in_lead_output).map((s) => s.op);
    expect(Object.keys(WEB_OPS).sort()).toEqual(applied.sort());
    for (const op of Object.keys(WEB_OPS)) expect(FILE.apply.some((c) => c.edit.op === op)).toBe(true);
    // Applied and a person's alone (WCE13): in the web's working edits, never in the Lead's type.
    const alone = FILE.catalogue.filter((s) => s.availability === "applied" && !s.in_lead_output).map((s) => s.op);
    expect(alone).toEqual(["route_set"]);
    expect(FILE.apply.some((c) => c.edit.op === "route_set")).toBe(true);
  });

  it.each(FILE.apply.map((c) => [c.name, c] as const))("%s", (_name, c) => {
    const got = applyEdit({ project: c.before.content as unknown as ResearchProject, analysis: c.before.analysis as Analysis | null }, c.edit, ids());
    if ("refused" in c.expect) {
      expect("reason" in got ? got.reason : null).toBe(c.expect.refused);
      expect(FILE.refusals).toContain(c.expect.refused);
    } else {
      expect("content" in got ? { content: got.content.project, analysis: got.content.analysis } : got).toEqual(c.expect);
    }
  });

  it("changes nothing it was given", () => {
    const c = FILE.apply.find((x) => x.name === "a research question added")!;
    const before = JSON.parse(JSON.stringify(c.before)) as typeof c.before;
    applyEdit({ project: before.content as unknown as ResearchProject, analysis: before.analysis as Analysis | null }, c.edit, ids());
    expect(before).toEqual(c.before);
  });

  it.each(FILE.text_edits.map((c) => [JSON.stringify(c.edit), c] as const))("text only: %s", (_name, c) => {
    expect(isTextEdit(c.edit)).toBe(c.text);
  });
});

describe("the trace's reading", () => {
  it.each(FILE.link_keys.map((c) => [JSON.stringify(c.text), c] as const))("keys the link %s", (_name, c) => {
    expect(linkKey(c.text)).toBe(c.key);
  });

  it.each(FILE.research_questions_of.map((c) => [c.name, c] as const))("research questions: %s", (_name, c) => {
    expect(researchQuestionsOf(c.design as unknown as ResearchProject)).toEqual(c.expect);
  });
});
