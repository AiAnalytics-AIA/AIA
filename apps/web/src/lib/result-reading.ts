// How a run's results read in words (plan research-results-clarity, chunk 2). The aggregate
// and the specification are the run's own stored artifacts; this module decides only what a
// sentence about them may say, so the Data view and the AI analysis say the same thing.
//
// One rule is carried here because a sentence can break it where a table cannot:
// * an order is stated only where 95 % intervals part -- the rule the Sociomap engine applies
//   to objects (audit F9, `rank_with_ties`). Overlapping intervals do not prove equality, so
//   the words are "cannot be confirmed", never "the same". A missing interval is unknown and
//   is never read as an order.

import { t } from "@/i18n/t";
import { type QuestionResult, type StoredPlaces, type SupportStatus, UNIT_PLACES } from "@/lib/research-execution";

/**
 * A measure's title when its specification gives it no wording (run-recovery-and-truth 6c): said
 * in words, never the id, which stays under the measure's technical details.
 */
export const untitled = (what: "question" | "object" | "set"): string => t(`research.exec.untitled.${what}`);

export type Estimate = { value: number; low: number | null; high: number | null };

/** Whether `a` lies above `b`: only when a's whole interval is above b's. */
export type Separation = "ABOVE" | "OVERLAP" | "UNKNOWN";

export function separation(a: Estimate, b: Estimate): Separation {
  if (a.low === null || a.high === null || b.low === null || b.high === null) return "UNKNOWN";
  return a.low > b.high ? "ABOVE" : "OVERLAP";
}

const fmt = (x: number, decimals: number) => x.toLocaleString("cs-CZ", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
const pctAt = (x: number, d: number) => `${fmt(x, d)} %`;
const finite = (x: unknown): x is number => typeof x === "number" && Number.isFinite(x);

function interval(raw: unknown): { low: number | null; high: number | null } {
  if (typeof raw !== "object" || raw === null) return { low: null, high: null };
  const { low, high } = raw as { low?: unknown; high?: unknown };
  return finite(low) && finite(high) && low <= high ? { low, high } : { low: null, high: null };
}

/** "A", "A a B", "A, B a C"; more than `max` names end with how many more there are. */
export function czechList(names: readonly string[], max = 4, more = "dalších"): string {
  if (names.length > max) return `${names.slice(0, max - 1).join(", ")} a ${names.length - max + 1} ${more}`;
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} a ${names[names.length - 1]}`;
}

export type ReadingTone = "plain" | "indicative" | "suppressed" | "empty";
export type MeasureReading = { text: string; tone: ReadingTone };

/** How a scale is named in a sentence: "na škále 1–5", nothing when the run did not record it. */
const onScale = (scale: readonly [number, number] | null | undefined) => (scale ? ` na škále ${scale[0]}–${scale[1]}` : "");

function choiceReading(result: QuestionResult, d: number): string | null {
  const pct = (x: number) => pctAt(x, d);
  const shares = (result.celkem_pct ?? {}) as Record<string, unknown>;
  const intervals = (result.intervaly_95 ?? {}) as Record<string, unknown>;
  const options = Object.entries(shares)
    .filter((entry): entry is [string, number] => finite(entry[1]))
    .map(([label, value]) => ({ label, value, ...interval(intervals[label]) }))
    .sort((a, b) => b.value - a.value);
  if (!options.length) return null;
  const multi = result.typ === "multi";
  const [leader, ...rest] = options;
  const share = `${leader.label} (${pct(leader.value)}${leader.low !== null && leader.high !== null ? `, 95% interval ${fmt(leader.low, d)}–${pct(leader.high)}` : ""})`;
  if (!rest.length) return `${multi ? "Vybíráno" : "Jediná odpověď"}: ${share}.`;
  if (leader.low === null) return `Nejvíce ${multi ? "vybíráno" : "odpovědí"}: ${share}; bez intervalu nelze pořadí odpovědí posoudit.`;
  const tied = rest.filter((option) => separation(leader, option) !== "ABOVE");
  if (!tied.length) return `${multi ? "Nejčastěji vybíráno" : "Nejčastější odpověď"}: ${share}, spolehlivě před ostatními ${multi ? "možnostmi" : "odpověďmi"}.`;
  const unknown = tied.some((option) => option.low === null);
  const names = [leader, ...tied].map((option) => `${option.label} (${pct(option.value)})`);
  return `Nejvíce ${multi ? "vybíráno" : "odpovědí"}: ${czechList(names, 4, "dalších možností")}; pořadí mezi nimi nelze potvrdit, ${unknown ? "některé intervaly chybějí nebo se překrývají" : "95% intervaly se překrývají"}.`;
}

function scaleReading(result: QuestionResult, scale: readonly [number, number] | null | undefined, topBox: number, at: StoredPlaces): string | null {
  if (!finite(result.prumer)) return null;
  const iv = interval(result.prumer_interval_95);
  const mean = `Průměr ${fmt(result.prumer, at.mean)}${onScale(scale)}${iv.low !== null && iv.high !== null ? ` (95% interval ${fmt(iv.low, at.mean)}–${fmt(iv.high, at.mean)})` : " (interval chybí)"}.`;
  const top = finite(result.top2box_pct) ? ` ${topBox === 2 ? "Horní dva body" : `Horní body (${topBox})`}: ${pctAt(result.top2box_pct, at.share)}.` : "";
  return mean + top;
}

/**
 * One measure in words. Suppressed: no number. Indicative: said first. A choice question names
 * its leading answer only as far as the intervals separate it from the next ones; a scale names
 * its mean with its interval and, when recorded, the scale it was asked on.
 */
export function readMeasure(result: QuestionResult, scale?: readonly [number, number] | null, topBox = 2, at: StoredPlaces = UNIT_PLACES): MeasureReading {
  if (result.support_status === "SUPPRESS") return { text: "Číselný výsledek je skrytý: podpora dat nestačí.", tone: "suppressed" };
  const words = result.typ === "vyber" || result.typ === "multi"
    ? choiceReading(result, at.share)
    : result.typ === "skala"
      ? scaleReading(result, scale, topBox, at)
      : Array.isArray(result.verbatimy) && result.verbatimy.length
        ? `Otevřená otázka: ${finite(result.n_platnych) ? `${result.n_platnych.toLocaleString("cs-CZ")} odpovědí, ` : ""}nekódováno.`
        : null;
  if (words === null) return { text: "Pro tuto otázku není k dispozici číselný souhrn.", tone: "empty" };
  return result.support_status === "INDICATIVE" ? { text: `Orientační: ${words}`, tone: "indicative" } : { text: words, tone: "plain" };
}

// ---- a set's objects compared ------------------------------------------------------------

export type RankedObject = Estimate & { id: string; label: string; support: SupportStatus };
export type ObjectComparison = {
  /** Highest mean first; only objects with a number. */
  ranked: RankedObject[];
  /** Objects left out: suppressed, or with no mean. Named so the reader knows they exist. */
  omitted: string[];
  /** The axis the comparison is drawn on: the set's scale, else the intervals' span. */
  domain: [number, number];
  /** What may be said about the top and the bottom; null when nothing may. */
  top: string | null;
  bottom: string | null;
};

/**
 * A set's objects on their mean. The top group is the highest object and every object it does
 * not lie wholly above; the bottom group the same from below. A group of one is "reliably" the
 * highest (lowest); a larger one is named with the order left open.
 */
export function compareObjects(objects: readonly { id: string; label: string; result: QuestionResult }[], scale?: readonly [number, number] | null): ObjectComparison {
  const ranked: RankedObject[] = [];
  const omitted: string[] = [];
  for (const { id, label, result } of objects) {
    if (result.support_status === "SUPPRESS" || !finite(result.prumer)) omitted.push(label);
    else ranked.push({ id, label, support: result.support_status, value: result.prumer, ...interval(result.prumer_interval_95) });
  }
  ranked.sort((a, b) => b.value - a.value);
  const lows = ranked.map((o) => o.low ?? o.value);
  const highs = ranked.map((o) => o.high ?? o.value);
  const domain: [number, number] = scale ? [scale[0], scale[1]] : ranked.length ? [Math.min(...lows), Math.max(...highs)] : [0, 1];
  if (ranked.length < 2) return { ranked, omitted, domain, top: null, bottom: null };
  if (ranked.some((o) => o.low === null)) {
    return { ranked, omitted, domain, top: "Pořadí objektů nelze posoudit: u některých chybí interval.", bottom: null };
  }
  const leader = ranked[0];
  const last = ranked[ranked.length - 1];
  const top = ranked.filter((o) => o === leader || separation(leader, o) !== "ABOVE");
  if (top.length === ranked.length) {
    return { ranked, omitted, domain, top: "Objekty se od sebe spolehlivě neliší: 95% intervaly všech se překrývají s nejvýše hodnoceným.", bottom: null };
  }
  const bottom = ranked.filter((o) => o === last || separation(o, last) !== "ABOVE");
  const say = (group: RankedObject[], one: string, many: string) => group.length === 1
    ? `${one}: ${group[0].label}.`
    : `${many}: ${czechList(group.map((o) => o.label), 4, "dalších")}; pořadí mezi nimi nelze potvrdit.`;
  return {
    ranked, omitted, domain,
    top: say(top, "Spolehlivě nejvýše hodnocený", "Nejvýše hodnocené"),
    bottom: say(bottom, "Spolehlivě nejníže hodnocený", "Nejníže hodnocené"),
  };
}

// ---- what an analysis claim cites ----------------------------------------------------------

/** The compiled specification as the results read it: wording, options and scales. */
export type CompiledSpecification = {
  n?: number | null;
  questions?: { id: string; text: string; typ?: string; options?: string[]; scale?: [number, number] | null }[];
  batteries?: { id: string; title: string; scale?: [number, number] | null; objects?: { id: string; label: string }[] }[];
};

/** The Data card a measure is shown on: a question's id, or `<set>:<object>`. */
export function measureAnchor(measureId: string): string {
  return `measure-${measureId.replace(/[^A-Za-z0-9_-]/g, "-")}`;
}

export type CitedMeasure = {
  /** The Data card's measure id (see measureAnchor). */
  measureId: string;
  /** The question's wording, or the object and its set. */
  title: string;
  /** What was measured, in words: "podíl odpovědi „Čaj“", "průměr", "platné odpovědi". */
  what: string;
  /** How the cited value is printed with its unit, at the places it was admitted at
   *  (`decimals`, from the claim) or 18.6.6's for its kind when the claim does not say. */
  format: (value: number, decimals?: number) => string;
};

const REF = /^(.+)\.(n|effective_n|mean|top2box|pct\.(\d+))$/;

/**
 * An analysis claim's evidence_ref (`<question>.<metric>`, as domain/analysis/native.py writes
 * it; a set object's question is `<set>_obj_<object>`) resolved against the run's specification.
 * Null for a reference this reading does not know: the claim then shows its raw reference.
 */
export function citedMeasure(ref: string, spec: CompiledSpecification | null | undefined): CitedMeasure | null {
  const match = REF.exec(ref);
  if (!match) return null;
  const [, questionId, metric, option] = match;
  const battery = (spec?.batteries ?? []).find((b) => questionId.startsWith(`${b.id}_obj_`));
  let measureId: string;
  let title: string;
  let options: string[] = [];
  if (battery) {
    const objectId = questionId.slice(`${battery.id}_obj_`.length);
    measureId = `${battery.id}:${objectId}`;
    title = `${battery.objects?.find((o) => o.id === objectId)?.label ?? untitled("object")} (${battery.title || untitled("set")})`;
  } else {
    const question = spec?.questions?.find((q) => q.id === questionId);
    measureId = questionId;
    title = question?.text || untitled("question");
    options = question?.options ?? [];
  }
  const pct = (v: number, d?: number) => pctAt(v, d ?? UNIT_PLACES.share);
  if (metric === "n") return { measureId, title, what: "platné odpovědi", format: (v, d) => fmt(v, d ?? 0) };
  if (metric === "effective_n") return { measureId, title, what: "efektivní n", format: (v, d) => fmt(v, d ?? 1) };
  if (metric === "mean") return { measureId, title, what: "průměr", format: (v, d) => fmt(v, d ?? UNIT_PLACES.mean) };
  if (metric === "top2box") return { measureId, title, what: "horní body škály", format: pct };
  const index = Number(option);
  return { measureId, title, what: `podíl odpovědi „${options[index - 1] ?? `možnost ${index}`}“`, format: pct };
}

// ---- a model's long text, formatted ----------------------------------------------------------

export type TextBlock =
  | { kind: "heading"; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "list"; ordered: boolean; items: string[]; start: number };

const BULLET = /^\s*(?:[-*•–])\s+(.*)$/;
const NUMBERED = /^\s*(\d+)[.)]\s+(.*)$/;
const HEADING = /^\s*#{1,6}\s+(.*?)\s*#*\s*$/;

/**
 * A model's long text (an analysis summary, a synthesis) as headings, paragraphs and lists, so
 * it reads as written rather than as one block. Every word is kept: only the line markers
 * ("- ", "## ") go, a numbered list keeps its numbers (its start, and one line numbered alone
 * -- "1. ledna 2024 …" -- stays text), and a line that is no marker joins the paragraph or
 * item before it.
 */
export function textBlocks(text: string | null | undefined): TextBlock[] {
  const blocks: TextBlock[] = [];
  let open: TextBlock | null = null;
  const close = () => { if (open) blocks.push(open); open = null; };
  for (const raw of (text ?? "").replace(/\r\n?/g, "\n").split("\n")) {
    const line = raw.trim();
    if (!line) { close(); continue; }
    const heading = HEADING.exec(line);
    const bullet = BULLET.exec(line);
    const numbered = bullet ? null : NUMBERED.exec(line);
    if (heading) { close(); blocks.push({ kind: "heading", text: heading[1] }); continue; }
    if (bullet || numbered) {
      const ordered = Boolean(numbered);
      const item = bullet ? bullet[1] : numbered![2];
      const current = open as TextBlock | null;
      if (current?.kind === "list" && current.ordered === ordered) current.items.push(item);
      else { close(); open = { kind: "list", ordered, items: [item], start: numbered ? Number(numbered[1]) : 1 }; }
      continue;
    }
    const current = open as TextBlock | null;
    if (current?.kind === "list") current.items[current.items.length - 1] += ` ${line}`;
    else if (current?.kind === "paragraph") current.text += ` ${line}`;
    else { close(); open = { kind: "paragraph", text: line }; }
  }
  close();
  // One numbered line is a sentence that starts with a number, not a list.
  return blocks.map((b) => (b.kind === "list" && b.ordered && b.items.length === 1 ? { kind: "paragraph", text: `${b.start}. ${b.items[0]}` } : b));
}

/** `**bold**` within a line, as runs; the asterisks go, every word stays. */
export function inlineRuns(text: string): { text: string; bold: boolean }[] {
  return text.split(/(\*\*[^*]+\*\*)/).filter(Boolean)
    .map((part) => (part.startsWith("**") && part.endsWith("**") && part.length > 4 ? { text: part.slice(2, -2), bold: true } : { text: part, bold: false }));
}
