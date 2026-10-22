// The Sociomap's declared inputs, locked once declared (ADR 0029 decision 8; the server's
// domain/edit_ops.py locked_items, declares_sociomap_inputs). A save that changes one is refused
// whole as sociomap_input_locked (working-copy-edit-ops WCE2c). The store puts the locked items back
// as they were saved, so the person's other changes still save; WCE8 is where a locked input is
// changed on purpose. Pure.

import type { ResearchProject } from "./model";

type Obj = Record<string, unknown>;
const isObj = (x: unknown): x is Obj => typeof x === "object" && x !== null && !Array.isArray(x);
const sectionsOf = (p: Obj): Obj[] => (Array.isArray(p.sections) ? p.sections.filter(isObj) : []);
const questionsOf = (s: Obj): Obj[] => (Array.isArray(s.questions) ? s.questions.filter(isObj) : []);
const isBattery = (s: Obj) => s.type === "object_battery";
const isRating = (q: Obj) => q.sociomap_rating === true;

/** Whether the design declares a Sociomap input: a rating question, or a set naming its context objects. */
export function declaresSociomapInputs(project: ResearchProject): boolean {
  return sectionsOf(project as Obj).some((s) => (isBattery(s) && "context_objects" in s) || questionsOf(s).some(isRating));
}

/**
 * `edited` with every input `saved` had locked put back as it was saved: each tracked set
 * (an object_battery section) and each rating question, by id, where it stands now or, when removed,
 * where it stood. `edited` itself (the same object) when nothing was put back, or nothing was locked.
 * An item without an id cannot be found again and is left as it is.
 */
export function restoreLocked(saved: ResearchProject, edited: ResearchProject): ResearchProject {
  if (!declaresSociomapInputs(saved)) return edited;
  const before = sectionsOf(saved as Obj);
  const raw = (edited as Obj).sections;
  if (!Array.isArray(raw)) return edited;
  let changed = false;
  const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
  const sections: unknown[] = [...raw];

  before.forEach((battery, at) => {
    if (!isBattery(battery) || typeof battery.id !== "string") return;
    const now = sections.findIndex((s) => isObj(s) && s.id === battery.id);
    if (now >= 0 && same(sections[now], battery)) return;
    if (now >= 0) sections[now] = battery;
    else sections.splice(Math.min(at, sections.length), 0, battery);
    changed = true;
  });

  for (const section of before) {
    if (isBattery(section)) continue;
    questionsOf(section).forEach((question, at) => {
      if (!isRating(question) || typeof question.id !== "string") return;
      const where = sections.findIndex((s) => isObj(s) && questionsOf(s).some((q) => q.id === question.id));
      if (where >= 0) {
        const holder = sections[where] as Obj;
        const list = holder.questions as unknown[];
        const index = list.findIndex((q) => isObj(q) && q.id === question.id);
        if (same(list[index], question)) return;
        sections[where] = { ...holder, questions: list.map((q, i) => (i === index ? question : q)) };
      } else {
        const home = sections.findIndex((s) => isObj(s) && s.id === section.id && Array.isArray(s.questions));
        if (home < 0) return;
        const holder = sections[home] as Obj;
        const list = [...(holder.questions as unknown[])];
        list.splice(Math.min(at, list.length), 0, question);
        sections[home] = { ...holder, questions: list };
      }
      changed = true;
    });
  }
  return changed ? ({ ...edited, sections } as ResearchProject) : edited;
}
