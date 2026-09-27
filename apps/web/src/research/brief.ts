// Zadání, the research flow's first step (ADR 0014, area A4): what the classic
// brief does to the project, ported from the bindings that run --
// setProblemType1785, updateTop / updateBrief, the attachment and link handlers,
// briefAttachmentContext1785, and ensureAnalysis1776 with its wrapper @412858.
// Every function here is pure: it returns the next project (and analysis), and
// the screen hands that to the store, which saves it as `save(reason)` does.
// brief.parity.test.ts runs each original under Node and compares.

import { type Attachment, type Template, PROBLEM_TYPES, type ResearchProject, briefFingerprint, defaultsMerge, selectedProblemTypes } from "./model";
import type { Analysis } from "./store";

/** The empty project's title; the field shows empty rather than this. */
export const DEFAULT_TITLE = "Nový výzkum";

export function titleValue(p: ResearchProject): string {
  return p.title === DEFAULT_TITLE ? "" : p.title || "";
}

/** setProblemType1785: toggle one type; the first chosen type fills an empty goal with its default. */
export function toggleProblemType(p: ResearchProject, key: string): ResearchProject {
  const x = PROBLEM_TYPES.find((v) => v[0] === key);
  if (!x) return p;
  const a = new Set(selectedProblemTypes(p));
  if (a.has(key)) a.delete(key);
  else a.add(key);
  const arr = [...a];
  const next: ResearchProject = {
    ...p,
    briefing: { ...(p.briefing || {}), problem_types: arr, problem_type: arr[0] || "" },
    ui_state: { ...(p.ui_state || {}), problem_types: arr },
  };
  if (!String(p.goal || "").trim() && arr.length === 1 && x[3]) next.goal = x[3];
  return next;
}

/** The project's own fields (updateTop) and the briefing's (updateBrief). */
export type TopField = "title" | "goal" | "decision_use";
export type BriefingField = "product_description" | "situation" | "what_is_known" | "constraints";

/**
 * updateTop / updateBrief. The analysis is of the brief as it was, so it is
 * dropped by every briefing edit and by the goal and the decision -- not by the title.
 */
export function editBrief(
  p: ResearchProject,
  analysis: Analysis | null,
  field: TopField | BriefingField,
  value: string,
): { project: ResearchProject; analysis: Analysis | null } {
  if (field === "title" || field === "goal" || field === "decision_use") {
    return { project: { ...p, [field]: value }, analysis: field === "title" ? analysis : null };
  }
  return { project: { ...p, briefing: { ...p.briefing, [field]: value } }, analysis: null };
}

const attachments = (p: ResearchProject): Attachment[] => p.briefing?.attachments || [];

/** uploadBriefAttachments1785 reads at most this many files per pick. */
export const MAX_FILES_PER_PICK = 8;
/** Its request timeout: a large file's text is extracted before the unit answers. */
export const ATTACHMENT_TIMEOUT_MS = 180_000;

/** fileToB64: a file's bytes as base64, read in 32 KiB chunks so a large file never overflows the call stack. */
export async function fileToBase64(file: Blob): Promise<string> {
  const a = new Uint8Array(await file.arrayBuffer());
  const chunks: string[] = [];
  for (let i = 0; i < a.length; i += 0x8000) chunks.push(String.fromCharCode(...a.subarray(i, i + 0x8000)));
  return btoa(chunks.join(""));
}

/** The records POST /api/project/attachment returned, appended in order. */
export function addAttachments(p: ResearchProject, records: Attachment[]): ResearchProject {
  return { ...p, briefing: { ...(p.briefing || {}), attachments: [...attachments(p), ...records] } };
}

export const LINK_INVALID = "Vložte odkaz začínající http:// nebo https://";

/** addBriefLink1785: a link is kept only when it is http(s). */
export function addLink(p: ResearchProject, raw: string): { project: ResearchProject } | { error: string } {
  const url = String(raw || "").trim();
  if (!/^https?:\/\//i.test(url)) return { error: LINK_INVALID };
  return {
    project: addAttachments(p, [{ kind: "url", url, title: url, context_excerpt: "Externí odkaz přiložený uživatelem." }]),
  };
}

/** removeBriefAttachment1785 */
export function removeAttachment(p: ResearchProject, i: number): ResearchProject {
  return { ...p, briefing: { ...(p.briefing || {}), attachments: attachments(p).filter((_, j) => j !== i) } };
}

/** What briefAttachmentsHtml1785 prints under an attachment's name. */
export function attachmentLine(x: Attachment): { name: string; detail: string } {
  if (x.kind === "url") return { name: x.title || x.url || "", detail: x.url || "" };
  return {
    name: x.filename || "Příloha",
    detail: `${Math.round((x.size_bytes || 0) / 1024)} KB${x.text_extracted ? " · text načten" : " · reference"}`,
  };
}

/** briefAttachmentContext1785: what the model reads of the attachments, at most 22 000 characters. */
export function attachmentContext(p: ResearchProject): string {
  return attachments(p)
    .map((x) => (x.kind === "url" ? `URL: ${x.url}` : `${x.filename}: ${x.context_excerpt || "[soubor přiložen bez textové extrakce]"}`))
    .join("\n\n")
    .slice(0, 22000);
}

/** The wrapper @412858: the attachment context is refreshed before every analysis. */
export function withAttachmentContext(p: ResearchProject): ResearchProject {
  return { ...p, briefing: { ...(p.briefing || {}), attachments_context: attachmentContext(p) } };
}

/** appendWizardNext1789's `disabled`: nothing to analyse until there is a goal or a description. */
export function canAnalyse(p: ResearchProject): boolean {
  return Boolean(String(p.goal || p.briefing?.product_description || "").trim());
}

export const BRIEF_EMPTY = "Nejdřív popište zadání výzkumu.";

/** ensureAnalysis1776's own refusal: neither a goal nor a description (each trimmed on its own). */
export function briefEmpty(p: ResearchProject): boolean {
  return !String(p.goal || "").trim() && !String(p.briefing?.product_description || "").trim();
}
export const ANALYSIS_REUSED = "Používám uloženou AI analýzu tohoto stejného zadání.";
export const ANALYSIS_JOB_TITLE = "AI chápe aktuální zadání";
export const ANALYSIS_WARN_MS = 40_000;

/** An analysis of this same brief, if one is kept (it has objectives and the brief's signature). */
export function reusableAnalysis(p: ResearchProject, analysis: Analysis | null): Analysis | null {
  if (!analysis || analysis._brief_signature !== briefFingerprint(p)) return null;
  return Array.isArray(analysis.objectives) && analysis.objectives.length ? analysis : null;
}

/** The body ensureAnalysis1776 POSTs to /api/research/analyze (before the job adds its own keys). */
export function analysisPayload(p: ResearchProject): Record<string, unknown> {
  return {
    briefing: { ...p.briefing, goal: p.goal, decision_use: p.decision_use, study_config: {} },
    n: p.n,
    model: "sonnet",
    provider: "claude_code_subscription",
  };
}

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T;
const isRecord = (x: unknown): x is Record<string, unknown> => typeof x === "object" && x !== null && !Array.isArray(x);

/**
 * What ensureAnalysis1776 does with the job's result: the AI's project over the
 * template, with the person's own title, goal, decision, briefing and screen
 * state kept; the later steps' choices reset; the analysis signed with the brief.
 */
export function mergeAnalysis(p: ResearchProject, result: unknown, template: Template): { project: ResearchProject; analysis: Analysis } {
  const r = isRecord(result) ? result : {};
  const sig = briefFingerprint(p);
  const preserved = {
    title: p.title,
    goal: p.goal,
    decision_use: p.decision_use,
    briefing: clone(p.briefing || {}),
    ui_state: clone(p.ui_state || {}),
  };
  const analysis: Analysis = { ...(isRecord(r.analysis) ? (r.analysis as Analysis) : {}), _brief_signature: sig };
  const next = defaultsMerge(r.project, template);
  next.title = preserved.title || next.title;
  next.goal = preserved.goal || next.goal;
  next.decision_use = preserved.decision_use || next.decision_use;
  next.briefing = { ...(next.briefing || {}), ...preserved.briefing };
  next.ui_state = {
    ...(next.ui_state || {}),
    ...preserved.ui_state,
    questionnaire_path: "choose",
    audience_entry: "choose",
    persona_path: "choose",
  };
  next.run_policy = { ...(next.run_policy || {}), provider: "claude_code_subscription", allow_provider_fallback: false };
  return { project: next, analysis };
}
