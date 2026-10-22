// What reads each questionnaire item downstream (artifact-questionnaire QST8, V2's "Závislosti",
// prototypes/research-lead-v2/src/artifacts/DesignStages.tsx:132-139). Over the working copy, by
// the rules the server applies once the design is compiled and run; it decides nothing itself:
// - a section other than a question block or a tracked set is not part of the study
//   (domain/research_design.py:842-844);
// - every tracked set gets its own Sociomap (domain/research_sociomap.py:575-584) and its
//   context objects are mapped but out of the PRIMARY scores (research_design.py:328-331);
// - a scale question declared `sociomap_rating` joins the rating universe every set's map is
//   read over (research_sociomap.py:388-405); without a set no map is made (:585);
// - an open question's answers are shown as illustrations and no analysis cites them
//   (domain/question_outlook.py:61-62, 153);
// - a question with a condition (`filtr`) is refused at the run (research_design.py:1093-1101), and
//   so is a set with familiarity required (battery_familiarity, research_design.py:1206-1212 @ 6359f8ee;
//   read with Python's bool(), :910).
// What else the compiler may refuse (a scale, too few options) Kontrola names, so a reader
// listed here is what the item feeds once it compiles, never a verdict that it will.

import type { ResearchProject } from "./model";
import { SET_MAX, SET_MIN, type Question, type Section, questionCondition, sections } from "./questionnaire";

/** A downstream stage of the workbench that reads questionnaire items. */
export type Reader = "fieldwork" | "results" | "sociomap" | "analysis" | "report";

/** Why an item reaches no stage yet; the person fixes it on Dotazník. */
export type Held = "no_text" | "condition" | "set_size" | "familiarity";

export type ItemReaders = {
  kind: "question" | "set";
  /** The item's stored id; null when it has none yet (the compiler gives one). */
  id: string | null;
  /** The item's section's index in the questionnaire (where its card is). */
  section: number;
  /** Q1… across question blocks, Sada 1… across sets, as the editor numbers them. */
  label: string;
  /** The question's wording or the set's title / family; "" when there is none. */
  text: string;
  /** The open question: its answers are data, never admitted evidence. */
  open: boolean;
  /** The scale question declared a Sociomap rating item. */
  rating: boolean;
  /** The set's declared context objects (SECONDARY). */
  context: string[];
  readers: Reader[];
  held: Held | null;
};

const str = (x: unknown): string => (typeof x === "string" ? x.trim() : "");
/** Python's bool(), as the compiler reads a flag: empty strings, lists and objects are false. */
const pyTrue = (x: unknown): boolean =>
  Array.isArray(x) ? x.length > 0 : x && typeof x === "object" ? Object.keys(x).length > 0 : Boolean(x);

function questionReaders(q: Question, si: number, n: number, hasSet: boolean): ItemReaders {
  const text = str(q.text);
  const open = q.typ === "otevrena";
  const rating = q.typ === "skala" && q.sociomap_rating === true;
  const held: Held | null = !text ? "no_text" : questionCondition(q) ? "condition" : null;
  const readers: Reader[] = held
    ? []
    : open
      ? ["fieldwork", "results"]
      : ["fieldwork", "results", ...(rating && hasSet ? (["sociomap"] as const) : []), "analysis", "report"];
  return { kind: "question", id: str(q.id) || null, section: si, label: `Q${n}`, text, open, rating, context: [], readers, held };
}

function setReaders(sec: Section, si: number, n: number): ItemReaders {
  const objects = (sec.objects || []).map(str).filter(Boolean);
  const size = new Set(objects).size;
  const held: Held | null = size < SET_MIN || size > SET_MAX ? "set_size" : pyTrue(sec.familiarity_required) ? "familiarity" : null;
  const declared = Array.isArray(sec.context_objects) ? (sec.context_objects as unknown[]).map(str).filter(Boolean) : [];
  return {
    kind: "set",
    id: str(sec.id) || null,
    section: si,
    label: `Sada ${n}`,
    text: str(sec.title) || str(sec.object_family) || str(sec.object_type),
    open: false,
    rating: false,
    context: declared,
    readers: held ? [] : ["fieldwork", "results", "sociomap", "analysis", "report"],
    held,
  };
}

/** Every question and tracked set of the questionnaire, in its order, with what reads it. */
export function questionnaireReaders(p: ResearchProject): ItemReaders[] {
  const xs = sections(p);
  const hasSet = xs.some((s) => s.type === "object_battery" && !setReaders(s, 0, 0).held);
  const out: ItemReaders[] = [];
  let qn = 0;
  let sn = 0;
  xs.forEach((sec, si) => {
    const kind = sec.type || "questions";
    if (kind === "questions") for (const q of sec.questions || []) out.push(questionReaders(q, si, ++qn, hasSet));
    else if (kind === "object_battery") out.push(setReaders(sec, si, ++sn));
  });
  return out;
}

/** The items a stage reads, in questionnaire order. */
export function readBy(items: ItemReaders[], reader: Reader): ItemReaders[] {
  return items.filter((i) => i.readers.includes(reader));
}
