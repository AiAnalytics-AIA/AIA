// The web's reading of a proposal against the server's design_items (ADR 0026 decision 5): the
// same case file, packages/aia_core/tests/fixtures/design_items/cases.json, is read by
// packages/aia_core/tests/test_design_items.py. proposalDiff and questionnaireReplacement see the
// research plan's lists, its tracked sets, its summary and the questionnaire's own questions and
// battery objects; on those, they must name the items the server names, and nothing else.
// briefFingerprint must sign a brief exactly as the server's brief_signature does.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { briefFingerprint, type ResearchProject } from "./model";
import { proposalDiff, questionnaireReplacement } from "./proposal-diff";
import type { Analysis } from "./store";

type Doc = Record<string, unknown>;
type Case = { name: string; note: string; before: { content: Doc; analysis: Doc | null }; after: { content: Doc; analysis: Doc | null }; items: string[] };
const FILE = JSON.parse(readFileSync(join(process.cwd(), "../../packages/aia_core/tests/fixtures/design_items/cases.json"), "utf8")) as {
  cases: Case[];
  brief_signatures: { name: string; content: Doc; signature: string }[];
};

const KINDS: Record<string, string> = { objectives: "objective", research_questions: "research_question", hypotheses: "hypothesis" };
const key = (s: string) => s.toLocaleLowerCase("cs").replace(/\s+/g, " ");
const isObj = (x: unknown): x is Doc => !!x && typeof x === "object" && !Array.isArray(x);

/** The items the web's diff names for one document's plan (the research plan, or the analysis). */
function planItems(doc: "content" | "analysis", before: Doc, after: Doc): string[] {
  const d = proposalDiff(before as Analysis, after);
  const out: string[] = [];
  for (const l of d.lists) for (const x of [...l.added, ...l.removed]) out.push(`${doc}:${KINDS[l.key]}:${key(x.trim())}`);
  for (const s of d.sets) if (s.status !== "same") out.push(`${doc}:tracked_set:${key(s.title)}`);
  if (d.summary) out.push(doc === "content" ? "content:plan:problem_summary" : "analysis:field:problem_summary");
  return out;
}

/** questionnaireReplacement's wording, back to the question or battery that holds it. */
function questionnaireItems(before: Doc, after: Doc): string[] {
  const r = questionnaireReplacement(before, after);
  const holder = (sections: unknown, text: string): string[] =>
    (Array.isArray(sections) ? sections.filter(isObj) : []).flatMap((s) => [
      ...(Array.isArray(s.questions) ? s.questions.filter(isObj) : []).filter((q) => String(q.text ?? "").trim() === text).map((q) => `content:question:${String(q.id)}`),
      ...(Array.isArray(s.objects) && s.objects.includes(text) ? [`content:battery:${String(s.id)}`] : []),
    ]);
  return [...r.removed.flatMap((x) => holder(before.sections, x)), ...r.added.flatMap((x) => holder(after.sections, x))];
}

/** The kinds the web reads: a server item of any other kind is not the web's to name. */
const seen = (item: string) => /^(content|analysis):(objective|research_question|hypothesis|tracked_set|question|battery):/.test(item)
  || item === "content:plan:problem_summary" || item === "analysis:field:problem_summary";

describe("the web's proposal diff names the items design_items names", () => {
  it.each(FILE.cases)("$name", (c) => {
    const web = new Set([
      ...planItems("content", isObj(c.before.content.research_plan) ? c.before.content.research_plan : {}, isObj(c.after.content.research_plan) ? c.after.content.research_plan : {}),
      ...planItems("analysis", c.before.analysis ?? {}, c.after.analysis ?? {}),
      ...questionnaireItems(c.before.content, c.after.content),
    ]);
    // A question added or removed also changes its section, which the web does not read.
    expect([...web].sort()).toEqual(c.items.filter(seen).sort());
  });
});

describe("briefFingerprint signs a brief as brief_signature does", () => {
  it.each(FILE.brief_signatures)("$name", (s) => {
    expect(briefFingerprint(s.content as ResearchProject)).toBe(s.signature);
  });
});
