// A refused accept in words (ADR 0026 decision 5). The API names each item a proposal changes
// that the working copy changed too, as `document:kind:key` (domain/design_items.py ItemKey);
// this says them to the person, in Czech, and why the proposal cannot be used as it stands.
// It decides nothing: the server refused, and this only reads its refusal.

import { ApiError, type StaleProposalDetails } from "@/lib/api";

import { wordingOf } from "./item-ids";

const BRIEF: Record<string, string> = {
  title: "Název studie",
  goal: "Cíl studie",
  decision_use: "K čemu výsledek poslouží",
  "briefing.product_description": "Popis produktu",
  "briefing.situation": "Situace",
  "briefing.what_is_known": "Co už víme",
  "briefing.constraints": "Omezení",
};
const PLAN: Record<string, string> = {
  problem_summary: "Shrnutí problému",
  status: "Stav plánu",
  complexity: "Rozsah studie",
  method_reason: "Zdůvodnění metody",
};
const SINGLE: Record<string, string> = { audience: "Cílová skupina", dimensions: "Výběr dimenzí", n: "Velikost vzorku" };

type Obj = Record<string, unknown>;
const isObj = (x: unknown): x is Obj => !!x && typeof x === "object" && !Array.isArray(x);

/** A question's wording in the design the person has, when it is there. */
function questionText(project: Obj | null, id: string): string | null {
  const sections = Array.isArray(project?.sections) ? project.sections.filter(isObj) : [];
  for (const s of sections) {
    for (const q of Array.isArray(s.questions) ? s.questions.filter(isObj) : []) {
      if (q.id === id && typeof q.text === "string" && q.text.trim()) return q.text.trim();
    }
  }
  return null;
}

/**
 * One item, said in words: `content:objective:zjistit cenu` is Cíl „zjistit cenu“. A plan item
 * named by its stable id (WCE1, `content:research_question:rq_…`) is said by `said`, the wording the
 * server sent with the refusal (it knows the baseline, so a reworded or removed item too), else by
 * its wording in the design the person has, else by its key, as before.
 */
export function itemWords(item: string, project: Obj | null = null, said: string | null = null): string {
  const [, kind = "", ...rest] = item.split(":");
  const key = rest.join(":");
  const wording = () => said ?? (project ? wordingOf(project, null, kind, key) : null) ?? key;
  switch (kind) {
    case "brief": return BRIEF[key] ?? `Zadání: ${key.replace(/^briefing\./, "")}`;
    case "objective": return `Cíl „${wording()}“`;
    case "research_question": return `Výzkumná otázka „${wording()}“`;
    case "hypothesis": return `Hypotéza „${wording()}“`;
    case "tracked_set": return `Porovnávaná sada „${key}“`;
    case "plan": return PLAN[key] ?? `Plán výzkumu: ${key}`;
    case "section": return `Část dotazníku ${key}`;
    case "battery": return `Baterie dotazníku ${key}`;
    case "question": {
      const text = said ?? questionText(project, key);
      return text ? `Otázka „${text}“` : `Otázka ${key}`;
    }
    case "field": return PLAN[key] ?? `Pole ${key}`;
    default: return SINGLE[kind] ?? item;
  }
}

/** The refusal's details, when the error is a 409 stale_proposal; null for any other error. */
export function staleDetails(e: unknown): StaleProposalDetails | null {
  if (!(e instanceof ApiError) || e.status !== 409 || e.code !== "stale_proposal") return null;
  const d = e.details ?? {};
  const items = Array.isArray(d.conflicting_items) ? d.conflicting_items.filter((x): x is string => typeof x === "string") : [];
  const raw = d.conflicting_wording;
  const wording = raw && typeof raw === "object" && !Array.isArray(raw)
    ? Object.fromEntries(Object.entries(raw as Record<string, unknown>).filter((e): e is [string, string] => typeof e[1] === "string"))
    : {};
  return { reason: typeof d.reason === "string" ? d.reason : "", conflicting_items: items, conflicting_wording: wording };
}

/** Why a proposal cannot be used, in words, naming each item both changed (once). */
export function staleMessage(details: StaleProposalDetails, project: Obj | null = null): string {
  if (details.reason === "items_changed" && details.conflicting_items.length) {
    const said = details.conflicting_wording ?? {};
    const words = [...new Set(details.conflicting_items.map((i) => itemWords(i, project, said[i] ?? null)))];
    return `Návrh nejde použít: mezitím se změnilo, co návrh mění – ${words.join(", ")}. Vaše úpravy zůstávají; návrh připravte znovu nad současným zadáním.`;
  }
  if (details.reason === "unknown_baseline") {
    return "Návrh vznikl nad revizí, u které AIA nezná pracovní kopii, takže nejde ověřit, co by přepsal. Připravte ho znovu nad současným zadáním.";
  }
  if (details.reason === "lineage_changed") {
    return "Návrh vychází z podkladů, které se mezitím změnily. Připravte ho znovu.";
  }
  return "Návrh nejde použít: mezitím vznikla novější revize návrhu. Připravte ho znovu nad současným zadáním.";
}
