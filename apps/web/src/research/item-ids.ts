// Stable item ids in a research design (working-copy-edit-ops WCE1, ADR 0029 decision 2): the
// web's port of packages/aia_core/src/aia_core/domain/item_ids.py, held to it by one case file,
// packages/aia_core/tests/fixtures/item_ids/cases.json (item-ids.test.ts reads it).
//
// The ids live beside the lists they name, so every reader of a list of strings reads it as
// before and nothing a run compiles changes: the plan's objectives / research_questions /
// hypotheses carry objective_ids / research_question_ids / hypothesis_ids (in research_plan and
// in the analysis), a question's kategorie carries kategorie_ids, a tracked set's objects carry
// object_ids, and a section without an id gets the one the compiler gives it. Each entry is
// { id, bound }: the id and a hash of the wording it was last given with, so a list another writer
// changed is still read right (the server's module says how). Pure: every function returns new
// documents. The store writes the ids only behind AIA_WEB_STABLE_ITEM_IDS (/config's stableItemIds).

import { CASE_FOLDS } from "./case-folds";

type Obj = Record<string, unknown>;
const isObj = (x: unknown): x is Obj => !!x && typeof x === "object" && !Array.isArray(x);

/** The plan's id-bearing lists: the list, its id list, the kind and its prefix (ID_LISTS). */
export const ID_LISTS = [
  ["objectives", "objective_ids", "objective", "obj_"],
  ["research_questions", "research_question_ids", "research_question", "rq_"],
  ["hypotheses", "hypothesis_ids", "hypothesis", "hyp_"],
] as const;
export const OPTION_IDS = "kategorie_ids";
export const OBJECT_IDS = "object_ids";
/** Every key an id list is kept under: never an item or a field of its own. */
export const SIDECAR_KEYS: ReadonlySet<string> = new Set([...ID_LISTS.map((l) => l[1]), OPTION_IDS, OBJECT_IDS]);

const ID = /^[A-Za-z0-9_.-]{1,80}$/;
// Whitespace as Python's str.split reads it (JavaScript's \s differs on U+001C-U+001F and U+FEFF).
const WS = /[\t\n\x0b\x0c\r \x1c-\x1f\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/g;

/**
 * A wording as identity compares it, as the server's fold does (" ".join(split()).casefold()):
 * whitespace collapsed and trimmed, case-folded -- lower-casing plus CASE_FOLDS (sharp s, final sigma).
 */
export function fold(text: string): string {
  let out = "";
  for (const ch of text.replace(WS, " ").replace(/^ | $/g, "")) out += CASE_FOLDS[ch] ?? ch.toLowerCase();
  return out;
}

const encoder = new TextEncoder();
/** (a * b) mod 2^64 for two 64-bit numbers as [high, low] 32-bit halves, in 16-bit limbs (exact). */
function mul64(ahi: number, alo: number, bhi: number, blo: number): [number, number] {
  const a = [alo & 0xffff, alo >>> 16, ahi & 0xffff, ahi >>> 16];
  const b = [blo & 0xffff, blo >>> 16, bhi & 0xffff, bhi >>> 16];
  const r = [0, 0, 0, 0];
  let carry = 0;
  for (let k = 0; k < 4; k++) {
    let sum = carry;
    for (let i = 0; i <= k; i++) sum += a[i] * b[k - i];
    r[k] = sum % 0x10000;
    carry = Math.floor(sum / 0x10000);
  }
  return [(r[3] * 0x10000 + r[2]) >>> 0, (r[1] * 0x10000 + r[0]) >>> 0];
}

const hex8 = (n: number): string => n.toString(16).padStart(8, "0");

/** Ten hex digits of FNV-1a 64 over the UTF-8 bytes, mixed by MurmurHash3's 64-bit finaliser. */
export function fnv10(text: string): string {
  let hi = 0xcbf29ce4;
  let lo = 0x84222325;
  for (const byte of encoder.encode(text)) {
    lo = (lo ^ byte) >>> 0;
    [hi, lo] = mul64(hi, lo, 0x00000100, 0x000001b3);
  }
  // h ^= h >> 33; h *= 0xff51afd7ed558ccd; h ^= h >> 33; h *= 0xc4ceb9fe1a85ec53; h ^= h >> 33
  lo = (lo ^ (hi >>> 1)) >>> 0;
  [hi, lo] = mul64(hi, lo, 0xff51afd7, 0xed558ccd);
  lo = (lo ^ (hi >>> 1)) >>> 0;
  [hi, lo] = mul64(hi, lo, 0xc4ceb9fe, 0x1a85ec53);
  lo = (lo ^ (hi >>> 1)) >>> 0;
  return (hex8(hi) + hex8(lo)).slice(0, 10);
}

export const boundOf = (text: string): string => fnv10(fold(text));

/** The id a wording takes when nothing names it: deterministic, so every read agrees. */
export const derivedId = (prefix: string, kind: string, text: string, occurrence: number): string =>
  prefix + fnv10(`${kind}\x00${fold(text)}\x00${occurrence}`);

export type Entry = { id: string; bound: string };

const entry = (raw: unknown): Entry | null =>
  isObj(raw) && typeof raw.id === "string" && ID.test(raw.id) && typeof raw.bound === "string" ? { id: raw.id, bound: raw.bound } : null;

/** An id list as stored; null when there is none (or it is not a list). */
export const entries = (raw: unknown): (Entry | null)[] | null => (Array.isArray(raw) ? raw.map(entry) : null);

const strings = (value: unknown): string[] | null =>
  Array.isArray(value) && value.every((x) => typeof x === "string") ? [...(value as string[])] : null;

/** One longest common subsequence's index pairs, in order (the server's _lcs, same tie rule). */
function lcs(a: readonly string[], b: readonly string[]): [number, number][] {
  const n = a.length;
  const m = b.length;
  const t: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) t[i][j] = a[i] === b[j] ? t[i + 1][j + 1] + 1 : Math.max(t[i + 1][j], t[i][j + 1]);
  }
  const out: [number, number][] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      out.push([i, j]);
      i++;
      j++;
    } else if (t[i + 1][j] >= t[i][j + 1]) i++;
    else j++;
  }
  return out;
}

/**
 * Each position's id: from the list's own entries (anchored by wording, rewords in place between
 * anchors when the counts agree), else by wording from `previous`, else derived. Unique.
 */
export function reconcile(
  texts: readonly string[],
  { prefix, kind, entries: given, previous = null }: { prefix: string; kind: string; entries: readonly (Entry | null)[] | null; previous?: readonly (readonly [string, string])[] | null },
): string[] {
  const ids: (string | null)[] = texts.map(() => null);
  const bounds = texts.map(boundOf);
  const used = new Set<string>();
  if (given !== null) {
    const seen = new Set<string>();
    const live: Entry[] = [];
    for (const e of given) {
      if (e !== null && !seen.has(e.id)) {
        seen.add(e.id);
        live.push(e);
      }
    }
    const anchors = lcs(live.map((e) => e.bound), bounds);
    const taken = new Set<number>();
    for (const [li, pos] of anchors) {
      ids[pos] = live[li].id;
      taken.add(li);
    }
    bounds.forEach((bound, pos) => {
      if (ids[pos] !== null) return;
      const li = live.findIndex((e, k) => !taken.has(k) && e.bound === bound);
      if (li >= 0) {
        ids[pos] = live[li].id;
        taken.add(li);
      }
    });
    const edgesE = [-1, ...anchors.map(([li]) => li), live.length];
    const edgesP = [-1, ...anchors.map(([, pos]) => pos), texts.length];
    for (let g = 0; g < edgesE.length - 1; g++) {
      const gapE: number[] = [];
      for (let li = edgesE[g] + 1; li < edgesE[g + 1]; li++) if (!taken.has(li)) gapE.push(li);
      const gapP: number[] = [];
      for (let p = edgesP[g] + 1; p < edgesP[g + 1]; p++) if (ids[p] === null) gapP.push(p);
      if (gapE.length && gapE.length === gapP.length) {
        gapE.forEach((li, k) => {
          ids[gapP[k]] = live[li].id;
          taken.add(li);
        });
      }
    }
  } else if (previous !== null) {
    const offered = previous.map(([id, text]) => [id, fold(text)] as const);
    const claimed = new Set<number>();
    texts.forEach((text, pos) => {
      const folded = fold(text);
      const k = offered.findIndex(([id, prior], i) => !claimed.has(i) && prior === folded && !used.has(id));
      if (k >= 0) {
        ids[pos] = offered[k][0];
        claimed.add(k);
        used.add(offered[k][0]);
      }
    });
  }
  for (const id of ids) if (id !== null) used.add(id);
  const occurrences = new Map<string, number>();
  return texts.map((text, pos) => {
    const folded = fold(text);
    occurrences.set(folded, (occurrences.get(folded) ?? 0) + 1);
    const named = ids[pos];
    if (named !== null) return named;
    const base = derivedId(prefix, kind, text, occurrences.get(folded) ?? 1);
    let candidate = base;
    for (let n = 2; used.has(candidate); n++) candidate = `${base}-${n}`;
    used.add(candidate);
    return candidate;
  });
}

/** The ids `holder[idsKey]` gives `holder[listKey]`, or null when they are absent or do not line up. */
export function listIds(holder: unknown, listKey: string, idsKey: string): string[] | null {
  if (!isObj(holder)) return null;
  const texts = strings(holder[listKey]);
  const es = entries(holder[idsKey]);
  if (texts === null || es === null || es.length !== texts.length || es.some((e) => e === null)) return null;
  const out = es.map((e) => (e as Entry).id);
  return new Set(out).size === out.length ? out : null;
}

const pairs = (holder: unknown, listKey: string, idsKey: string): [string, string][] | null => {
  const ids = listIds(holder, listKey, idsKey);
  const texts = isObj(holder) ? strings(holder[listKey]) : null;
  return ids && texts ? ids.map((id, i) => [id, texts[i]]) : null;
};

function withList(holder: Obj, listKey: string, idsKey: string, prefix: string, kind: string, previous: [string, string][] | null): void {
  const texts = strings(holder[listKey]);
  if (texts === null) return;
  const ids = reconcile(texts, { prefix, kind, entries: entries(holder[idsKey]), previous });
  holder[idsKey] = ids.map((id, i) => ({ id, bound: boundOf(texts[i]) }));
}

// -- sections: the compiler's ids ----------------------------------------------------------------

/** Python's truthiness for a JSON value. */
const truthy = (v: unknown): boolean => (Array.isArray(v) ? v.length > 0 : isObj(v) ? Object.keys(v).length > 0 : !!v);
/** research_design._text, for the JSON values a title or an id can be; null for one it cannot read alike. */
function text(value: unknown): string | null {
  if (value === null || value === undefined) return "";
  if (typeof value === "boolean") return value ? "True" : "False";
  if (typeof value === "string" || (typeof value === "number" && Number.isInteger(value))) return String(value).replace(/\s+/g, " ").trim();
  return null;
}
function slug(value: string, prefix: string): string {
  const folded = value.normalize("NFKD").replace(/[^\x00-\x7f]/g, "");
  const s = folded.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  if (!s) return prefix;
  return /^[0-9]/.test(s) ? `${prefix}_${s}` : s;
}
function unique(base: string, used: Set<string>): string {
  let candidate = base;
  for (let i = 2; used.has(candidate); i++) candidate = `${base}_${i}`;
  used.add(candidate);
  return candidate;
}

/**
 * The id each section has, or is given: the compiler's for one without (compile_design), so the
 * specification compiled before and after is the same; a section it skips gets its title's slug.
 * null for an entry that is not an object, and for a title the two languages cannot read alike
 * (the server then gives it its id when it reads it; nothing is stored here).
 */
export function sectionIds(sections: readonly unknown[]): (string | null)[] {
  const out: unknown[] = [];
  const compiled = new Set<string>();
  let unreadable = false;
  sections.forEach((sec, k) => {
    const i = k + 1;
    if (!isObj(sec)) {
      out.push(null);
      return;
    }
    const kind = text(truthy(sec.type) ? sec.type : "questions");
    const source = text(truthy(sec.id) ? sec.id : sec.title);
    if (kind === null || source === null) {
      unreadable = true;
      out.push(truthy(sec.id) ? sec.id : null);
      return;
    }
    let made = slug(source || `sekce_${i}`, "sec");
    const compiles = kind === "questions" || kind === "object_battery";
    if (compiles) made = unique(made, compiled);
    out.push(truthy(sec.id) ? sec.id : compiles ? made : null);
  });
  if (unreadable) return out.map((x) => (typeof x === "string" ? x : null));
  const taken = new Set<string>([...out.filter((x): x is string => typeof x === "string"), ...compiled]);
  sections.forEach((sec, k) => {
    if (isObj(sec) && out[k] === null) {
      const title = text(sec.title);
      out[k] = title === null ? null : unique(slug(title || `sekce_${k + 1}`, "sec"), taken);
    }
  });
  return out.map((x) => (typeof x === "string" ? x : null));
}

// -- a design -----------------------------------------------------------------------------------

function planLists(plan: Obj, previous: unknown, fallback: unknown = null): void {
  for (const [listKey, idsKey, kind, prefix] of ID_LISTS) {
    let source = previous !== null ? pairs(previous, listKey, idsKey) : null;
    if (source === null && fallback !== null) source = pairs(fallback, listKey, idsKey);
    withList(plan, listKey, idsKey, prefix, kind, source);
  }
}

function byId(sections: unknown): Map<string, Obj> {
  const out = new Map<string, Obj>();
  if (!Array.isArray(sections)) return out;
  for (const sec of sections) {
    if (!isObj(sec)) continue;
    if (typeof sec.id === "string" && !out.has(`s:${sec.id}`)) out.set(`s:${sec.id}`, sec);
    for (const q of Array.isArray(sec.questions) ? sec.questions : []) {
      if (isObj(q) && typeof q.id === "string" && !out.has(`q:${q.id}`)) out.set(`q:${q.id}`, q);
    }
  }
  return out;
}

function withSections(content: Obj, previous: Obj | null): void {
  const raw = content.sections;
  if (!Array.isArray(raw)) return;
  const prior = previous ? byId(previous.sections) : new Map<string, Obj>();
  const given = sectionIds(raw);
  content.sections = raw.map((sec, k) => {
    if (!isObj(sec)) return sec;
    const section: Obj = { ...sec };
    if (!truthy(section.id) && given[k] !== null) section.id = given[k];
    const sid = String(section.id);
    if (section.type === "object_battery") {
      withList(section, "objects", OBJECT_IDS, "o_", "object", pairs(prior.get(`s:${sid}`), "objects", OBJECT_IDS));
    } else if (Array.isArray(section.questions)) {
      section.questions = section.questions.map((q) => {
        if (!isObj(q)) return q;
        const question: Obj = { ...q };
        const prev = typeof question.id === "string" ? pairs(prior.get(`q:${question.id}`), "kategorie", OPTION_IDS) : null;
        withList(question, "kategorie", OPTION_IDS, "opt_", "option", prev);
        return question;
      });
    }
    return section;
  });
}

const copy = <T>(x: T): T => JSON.parse(JSON.stringify(x)) as T;

/**
 * The design (content and its separate analysis) with every item's id written in; copies. A list
 * keeps the ids its own id list gives it; one without is matched by wording to the same list in
 * `previous` (the baseline), else its ids are derived.
 */
export function withItemIds<C extends Obj, A extends Obj>(
  content: C,
  analysis: A | null = null,
  previous: readonly [Obj, Obj | null] | null = null,
): [C, A | null] {
  const [prevContent, prevAnalysis] = previous ? withItemIds(previous[0], previous[1]) : [null, null];
  const body = copy(content) as Obj;
  const prevPlan = prevContent && isObj(prevContent.research_plan) ? prevContent.research_plan : null;
  if (isObj(body.research_plan)) {
    const plan = { ...body.research_plan };
    planLists(plan, prevPlan);
    body.research_plan = plan;
  }
  withSections(body, prevContent);
  let working: Obj | null = null;
  if (analysis !== null) {
    working = copy(analysis) as Obj;
    planLists(working, prevAnalysis ?? prevPlan, isObj(body.research_plan) ? body.research_plan : null);
  }
  return [body as C, working as A | null];
}

// -- links follow a reword ------------------------------------------------------------------------

const linkKey = (t: string): string => t.replace(/\s+/g, " ").trim();

function stated(content: Obj): readonly [string, string] | null {
  if (!isObj(content.research_plan)) return null;
  for (const [listKey, idsKey] of [ID_LISTS[1], ID_LISTS[0]]) {
    const texts = strings(content.research_plan[listKey]);
    if (texts && texts.some((t) => t.trim())) return [listKey, idsKey];
  }
  return null;
}

function relink(links: unknown, renamed: Map<string, string>): unknown {
  if (!Array.isArray(links)) return links;
  const keys = new Set<string>();
  const out: unknown[] = [];
  for (const link of links) {
    const next = typeof link === "string" ? (renamed.get(linkKey(link)) ?? link) : link;
    const key = typeof next === "string" ? linkKey(next) : null;
    if (key !== null && keys.has(key)) continue;
    if (key !== null) keys.add(key);
    out.push(next);
  }
  return out;
}

/**
 * `after` (ids written in) with each reworded research question's links -- the questionnaire
 * items that measure it, the key of its comparison -- carried to its new wording.
 */
export function followRewords<C extends Obj>(before: Obj, after: C): C {
  const out: Obj = { ...after };
  const list = stated(after);
  if (list === null) return out as C;
  const [listKey, idsKey] = list;
  const old = new Map(pairs(before.research_plan, listKey, idsKey) ?? []);
  const fresh = pairs(after.research_plan, listKey, idsKey) ?? [];
  const still = new Set(fresh.map(([, t]) => linkKey(t)));
  const renamed = new Map<string, string>();
  for (const [id, t] of fresh) {
    const was = old.get(id);
    if (was === undefined || linkKey(was) === linkKey(t) || still.has(linkKey(was))) continue;
    if (!renamed.has(linkKey(was))) renamed.set(linkKey(was), t.trim());
  }
  if (!renamed.size) return out as C;
  if (Array.isArray(out.sections)) {
    out.sections = out.sections.map((sec) => {
      if (!isObj(sec)) return sec;
      const section: Obj = { ...sec };
      if ("research_questions" in section) section.research_questions = relink(section.research_questions, renamed);
      if (Array.isArray(section.questions)) {
        section.questions = section.questions.map((q) => (isObj(q) && "research_questions" in q ? { ...q, research_questions: relink(q.research_questions, renamed) } : q));
      }
      return section;
    });
  }
  const plan = out.research_plan;
  if (isObj(plan) && isObj(plan.research_question_comparisons)) {
    const moved: Obj = {};
    for (const [t, kind] of Object.entries(plan.research_question_comparisons)) {
      const key = renamed.get(linkKey(t)) ?? t;
      if (!(key in moved) || key === t) moved[key] = kind;
    }
    out.research_plan = { ...plan, research_question_comparisons: moved };
  }
  return out as C;
}

/** What the store keeps after a change: `after` with its ids (read against `before`), links followed. */
export function settleItemIds<C extends Obj, A extends Obj>(before: readonly [Obj, Obj | null], after: readonly [C, A | null]): [C, A | null] {
  const base = withItemIds(before[0], before[1]);
  const [content, analysis] = withItemIds(after[0], after[1], base);
  return [followRewords(base[0], content), analysis];
}

/** The wording an item id names in a design (a plan list, an option, an object), or null. */
export function wordingOf(content: Obj, analysis: Obj | null, kind: string, id: string): string | null {
  const [body, working] = withItemIds(content, analysis);
  const spec = ID_LISTS.find((l) => l[2] === kind);
  if (!spec) return null;
  for (const holder of [body.research_plan, working]) {
    const found = (pairs(holder, spec[0], spec[1]) ?? []).find(([x]) => x === id);
    if (found) return found[1];
  }
  return null;
}
