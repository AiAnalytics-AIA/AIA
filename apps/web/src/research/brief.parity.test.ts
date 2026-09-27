import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { declaration, effective, legacyContext, statement } from "@/testing/legacy";
import {
  ANALYSIS_JOB_TITLE,
  ANALYSIS_REUSED,
  ANALYSIS_WARN_MS,
  BRIEF_EMPTY,
  LINK_INVALID,
  briefEmpty,
  fileToBase64,
  addLink,
  analysisPayload,
  attachmentContext,
  attachmentLine,
  canAnalyse,
  editBrief,
  mergeAnalysis,
  removeAttachment,
  reusableAnalysis,
  toggleProblemType,
  withAttachmentContext,
} from "./brief";
import { type Attachment, type Template, PROBLEM_TYPES, type ResearchProject, briefFingerprint, defaultsMerge } from "./model";
import type { Analysis } from "./store";

// Zadání against the classic interface's own functions, run under Node with the
// DOM, the save and the job stubbed: what each does to PROJECT and ANALYSIS is
// compared with the port. The empty project is the unit's own template.
const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/research/fixtures/empty-project.json"), "utf8"));
const BOOT: Template = { empty_project: EMPTY, ai_provider: "claude_code_subscription" };

const legacy = legacyContext({
  prelude: [
    "const clone=x=>JSON.parse(JSON.stringify(x));",
    "var PROBLEM_TYPES_1785=[];",
    statement("PROBLEM_TYPES_1785.splice(0,PROBLEM_TYPES_1785.length,", ");"),
    // The screen, the save and the job, stubbed; each call is recorded.
    "var SAVES=[],ALERTS=[],TOASTS=[],JOBS=[],URL_INPUT='',JOB_RESULT=null,ANALYSIS=null,PROJECT=null;",
    "var LAST_CHECK=1,LAST_RESULT=1,VERIFICATION=1,localStorage={removeItem(){}};",
    "function save(r){SAVES.push(r||'autosave')}function renderBrief(){}function alert(m){ALERTS.push(m)}function toast(m){TOASTS.push(m)}",
    "function $(s){return {value:URL_INPUT}}function E(x){return String(x)}",
    "async function ensureClaudeReady1776(){return true}",
    "async function job(ep,payload,title,opts){JOBS.push({ep,payload:clone(payload),title,opts});return JOB_RESULT}",
  ],
  functions: [
    "defaultsMerge",
    "selectedProblemTypes1789",
    "briefFingerprint1780",
    "setProblemType1785",
    "updateTop",
    "updateBrief",
    "briefAttachmentContext1785",
    "briefAttachmentsHtml1785",
    "addBriefLink1785",
    "removeBriefAttachment1785",
  ],
});
// ensureAnalysis1776: the declaration, then the wrapper @412858 that refreshes the attachment context.
legacy.run(`${declaration("ensureAnalysis1776")};var _ensureAnalysis1785=ensureAnalysis1776;${effective("ensureAnalysis1776")}`);

const base = defaultsMerge({}, BOOT);
const withBrief = (b: Record<string, unknown>, top: Partial<ResearchProject> = {}): ResearchProject =>
  ({ ...base, ...top, briefing: { ...base.briefing, ...b } }) as ResearchProject;
const ATTACHMENTS: Attachment[] = [
  { kind: "file", filename: "brief.pdf", size_bytes: 20480, text_extracted: true, context_excerpt: "Shrnutí zadání.", sha256: "a1" },
  { kind: "url", url: "https://example.test/x", title: "https://example.test/x", context_excerpt: "Externí odkaz přiložený uživatelem." },
  { filename: "fotka.png", size_bytes: 1500 },
  { kind: "file", filename: "velky.txt", context_excerpt: "x".repeat(30000) },
];

describe("problem types toggle as setProblemType1785 does", () => {
  const cases: [string, ResearchProject, string][] = [
    ["first type fills an empty goal", base, "price"],
    ["a second type keeps the goal", withBrief({ problem_types: ["price"] }, { goal: PROBLEM_TYPES[0][3] }), "brand"],
    ["a written goal is never replaced", withBrief({}, { goal: "Můj cíl" }), "product"],
    ["toggling off", withBrief({ problem_types: ["price", "brand"] }), "price"],
    ["'other' has no default goal", base, "other"],
    ["types kept in ui_state only", { ...base, ui_state: { ...base.ui_state, problem_types: ["tracking"] } }, "audience"],
    ["an unknown key changes nothing", base, "nope"],
  ];
  for (const [name, p, key] of cases) {
    it(name, () => {
      const expected = legacy.run("SAVES=[];PROJECT=__p;setProblemType1785(__k);PROJECT", { __p: p, __k: key });
      expect(toggleProblemType(p, key)).toEqual(expected);
    });
  }
});

describe("brief edits drop the analysis as updateTop / updateBrief do", () => {
  const analysis = { objectives: ["x"], _brief_signature: "s" };
  for (const field of ["title", "goal", "decision_use"] as const) {
    it(`updateTop('${field}')`, () => {
      const expected = legacy.run<{ p: unknown; a: unknown }>("PROJECT=__p;ANALYSIS=__a;updateTop(__f,'nová hodnota');({p:PROJECT,a:ANALYSIS})", {
        __p: base, __a: analysis, __f: field,
      });
      const got = editBrief(base, analysis, field, "nová hodnota");
      expect(got.project).toEqual(expected.p);
      expect(got.analysis).toEqual(expected.a);
    });
  }
  for (const field of ["product_description", "situation", "what_is_known", "constraints"] as const) {
    it(`updateBrief('${field}')`, () => {
      const expected = legacy.run<{ p: unknown; a: unknown }>("PROJECT=__p;ANALYSIS=__a;updateBrief(__f,'text');({p:PROJECT,a:ANALYSIS})", {
        __p: base, __a: analysis, __f: field,
      });
      const got = editBrief(base, analysis, field, "text");
      expect(got.project).toEqual(expected.p);
      expect(got.analysis).toEqual(expected.a);
    });
  }
});

describe("attachments and links are the classic ones", () => {
  const p = withBrief({ attachments: ATTACHMENTS });
  it("the context is briefAttachmentContext1785, cut at 22 000 characters", () => {
    const expected = legacy.run<string>("PROJECT=__p;briefAttachmentContext1785()", { __p: p });
    expect(attachmentContext(p)).toBe(expected);
    expect(attachmentContext(p).length).toBe(22000);
  });
  it("each attachment's line is what briefAttachmentsHtml1785 prints", () => {
    const html = legacy.run<string>("PROJECT=__p;briefAttachmentsHtml1785()", { __p: p });
    for (const x of ATTACHMENTS) {
      const { name, detail } = attachmentLine(x);
      expect(html).toContain(`<b>${name}</b><span>${detail}</span>`);
    }
  });
  for (const url of ["https://example.test/a", "  HTTP://x.test  ", "ftp://x.test", "example.test", ""]) {
    it(`a link: ${JSON.stringify(url)}`, () => {
      const expected = legacy.run<{ p: unknown; alerts: string[] }>("ALERTS=[];PROJECT=__p;URL_INPUT=__u;addBriefLink1785();({p:PROJECT,alerts:ALERTS})", {
        __p: p, __u: url,
      });
      const got = addLink(p, url);
      if ("error" in got) {
        expect(expected.alerts).toEqual([got.error]);
        expect(expected.p).toEqual(p);
      } else {
        expect(expected.alerts).toEqual([]);
        expect(got.project).toEqual(expected.p);
      }
    });
  }
  it("the invalid-link message is the classic alert", () => {
    expect(addLink(p, "x")).toEqual({ error: LINK_INVALID });
  });
  for (const i of [0, 2, 3, 9]) {
    it(`removing attachment ${i}`, () => {
      const expected = legacy.run("PROJECT=__p;removeBriefAttachment1785(__i);PROJECT", { __p: p, __i: i });
      expect(removeAttachment(p, i)).toEqual(expected);
    });
  }
});

type Ran = { p: ResearchProject; a: unknown; jobs: { ep: string; payload: unknown; title: string; opts: unknown }[]; toasts: string[]; saves: string[]; error: string | null };
async function classicAnalysis(p: ResearchProject, analysis: unknown, result: unknown): Promise<Ran> {
  return legacy.run<Promise<Ran>>(
    `(async()=>{SAVES=[];TOASTS=[];JOBS=[];PROJECT=__p;ANALYSIS=__a;JOB_RESULT=__r;let error=null;
      try{await ensureAnalysis1776(false)}catch(e){error=e.message}
      return {p:PROJECT,a:ANALYSIS,jobs:JOBS,toasts:TOASTS,saves:SAVES,error}})()`,
    { BOOT, __p: p, __a: analysis, __r: result },
  );
}

describe("the AI analysis is ensureAnalysis1776 with its wrapper", () => {
  const brief = withBrief(
    { problem_types: ["product", "price"], situation: "Trh roste.", attachments: ATTACHMENTS.slice(0, 2) },
    { title: "Můj výzkum", goal: "Zjistit zájem", decision_use: "Uvést, nebo ne", n: 800 },
  );
  const RESULT = {
    analysis: { problem_summary: "Shrnutí", objectives: ["A", "B"], tracked_sets: [{ title: "Sada", objects: ["x", "y"] }] },
    project: {
      title: "AI název",
      goal: "AI cíl",
      briefing: { situation: "AI situace", extra: "AI doplnila" },
      research_plan: { status: "proposed", objectives: ["A"] },
      ui_state: { questionnaire_path: "ai", audience_entry: "own", persona_path: "ai", other: 1 },
      run_policy: { provider: "anthropic", allow_provider_fallback: true },
      n: 600,
    },
  };

  it("a new brief runs the job with the classic payload and merges its result", async () => {
    const ran = await classicAnalysis(brief, null, RESULT);
    expect(ran.error).toBeNull();
    const withCtx = withAttachmentContext(brief);
    expect(ran.jobs).toEqual([
      { ep: "/api/research/analyze", payload: analysisPayload(withCtx), title: ANALYSIS_JOB_TITLE, opts: { warnMs: ANALYSIS_WARN_MS } },
    ]);
    const got = mergeAnalysis(withCtx, RESULT, BOOT);
    expect(got.project).toEqual(ran.p);
    expect(got.analysis).toEqual(ran.a);
    expect(ran.saves).toEqual(["ai_analysis_1780"]);
  });

  it("a result without a project or analysis still merges as the classic one does", async () => {
    const ran = await classicAnalysis(brief, null, {});
    const got = mergeAnalysis(withAttachmentContext(brief), {}, BOOT);
    expect(got.project).toEqual(ran.p);
    expect(got.analysis).toEqual(ran.a);
  });

  it("the same brief reuses its analysis without a job", async () => {
    const kept = { objectives: ["A"], _brief_signature: briefFingerprint(brief) };
    const ran = await classicAnalysis(brief, kept, RESULT);
    expect(ran.jobs).toEqual([]);
    expect(ran.toasts).toEqual([ANALYSIS_REUSED]);
    expect(reusableAnalysis(brief, kept)).toEqual(kept);
  });

  const notReused: [string, Analysis | null][] = [
    ["another brief's analysis", { objectives: ["A"], _brief_signature: "jiný" }],
    ["an analysis without objectives", { objectives: [], _brief_signature: "" }],
    ["no analysis", null],
  ];
  for (const [name, kept] of notReused) {
    it(`${name} is not reused`, async () => {
      const k = kept && kept._brief_signature === "" ? { ...kept, _brief_signature: briefFingerprint(brief) } : kept;
      const ran = await classicAnalysis(brief, k, RESULT);
      expect(ran.jobs.length).toBe(1);
      expect(reusableAnalysis(brief, k)).toBeNull();
    });
  }

  for (const [name, p] of [
    ["no goal and no description", base],
    ["a goal of spaces", withBrief({}, { goal: "   " })],
    ["a description only", withBrief({ product_description: "Nový nápoj" })],
    ["a goal only", withBrief({}, { goal: "Cíl" })],
  ] as const) {
    it(`an empty brief is refused as the classic one is: ${name}`, async () => {
      const ran = await classicAnalysis(p, null, RESULT);
      expect(ran.error === BRIEF_EMPTY).toBe(briefEmpty(p));
    });
  }

  it("the next button's disabled state is appendWizardNext's condition", () => {
    const cond = (p: ResearchProject) => !String(p.goal || p.briefing?.product_description || "").trim();
    for (const p of [base, withBrief({}, { goal: " " }), withBrief({ product_description: "x" }), withBrief({}, { goal: "c" })]) {
      expect(canAnalyse(p)).toBe(!cond(p));
    }
    // Its source, so a change to the wrapper is seen here.
    expect(effective("renderBrief")).toContain("setTimeout(decorateAttach26,0)");
    expect(statement("const _renderBrief1789=renderBrief;", "};")).toContain(
      "appendWizardNext1789('analyzeBrief()','Další · vytvořit návrh',!String(PROJECT.goal||PROJECT.briefing?.product_description||'').trim())",
    );
  });
});

describe("files are read as fileToB64 reads them", () => {
  const l = legacyContext({ functions: ["fileToB64"], host: { btoa } });
  for (const size of [0, 5, 0x8000, 0x8000 * 2 + 17]) {
    it(`${size} bytes`, async () => {
      const bytes = Uint8Array.from({ length: size }, (_, i) => (i * 131 + 7) % 256);
      const blob = new Blob([bytes]);
      const expected = await l.run<Promise<string>>("fileToB64(__f)", { __f: blob });
      expect(await fileToBase64(blob)).toBe(expected);
      expect(Buffer.from(expected, "base64")).toEqual(Buffer.from(bytes));
    });
  }
});
