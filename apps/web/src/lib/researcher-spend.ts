// How "Útrata podle výzkumníka" reads a person's spend (Settings → Studie a rozpočty,
// develop-spend-attribution 7, Q40). Pure: no fetch, no React.
//
// Unknown is shown as unknown, never as 0: a total with a call whose bill is not known says
// so beside the amount, and a total that is zero only because nothing is known reads
// "neznámá". A person with no rows at all has spent nothing, which is known (a sum over no
// rows is zero), and reads 0,00 USD.

import type { PersonSpend, ResearcherSpend, SpendActivity, SpendFigures, SpendPeriod } from "./api";
import { usdWords } from "./spend";

export const SPEND_PERIODS: readonly SpendPeriod[] = ["this_month", "last_month", "year_to_date"];

export const PERIOD_LABEL: Record<SpendPeriod, string> = {
  this_month: "Tento měsíc",
  last_month: "Minulý měsíc",
  year_to_date: "Od začátku roku",
};

/** The activities in the order the API sends them. */
const ACTIVITY_LABEL: Record<SpendActivity, string> = {
  lead: "Vedoucí výzkumu",
  fieldwork: "Sběr dat",
  analysis_report: "Analýza a zpráva",
  deep_research: "Deep Research",
  other: "Ostatní",
};

// Spend booked to nobody: from before spend was attributed, or paid work nobody started or approved
// by name. Never attributed by guess (the product owner, 2026-10-22: "Neznámý").
const UNATTRIBUTED = "Neznámý";

/** An amount in USD as Czech print reads it (spend.ts usdWords: a positive amount under a cent is
 *  not rounded to 0); a figure that is not a number is the spend's own "neznámá". */
export function usd(amount: number): string {
  return Number.isFinite(amount) ? usdWords(amount) : "neznámá";
}

/** "1 volání", "2 volání" -- Czech "volání" does not decline; the count is said as a number. */
function calls(n: number): string {
  return `${n} ${n === 1 ? "nejisté volání" : n >= 2 && n <= 4 ? "nejistá volání" : "nejistých volání"}`;
}

export type AmountLine = {
  /** The amount as shown. */
  text: string;
  /** False: a call's bill is not known, so the amount is not exact. */
  exact: boolean;
  /** What is not known, in words; null when everything is. */
  note: string | null;
};

/** A total in words, its uncertainty beside it. */
export function totalLine(f: SpendFigures): AmountLine {
  if (f.uncertain_calls <= 0) return { text: usd(f.total_usd), exact: true, note: null };
  const note = `${calls(f.uncertain_calls)}: cena není známa, částka není přesná`;
  if (f.total_usd === 0) return { text: "neznámá", exact: false, note };
  return { text: usd(f.total_usd), exact: false, note };
}

/** Open holds are not spend yet; null when none are open. */
export function reservedLine(f: SpendFigures): string | null {
  return f.reserved_usd > 0 ? `${usd(f.reserved_usd)} drženo v běžící práci` : null;
}

/** Who a row is for: the name, else the e-mail, else the id; the unattributed row by name. */
export function personLabel(p: Pick<PersonSpend, "user_id" | "display_name" | "email">): string {
  if (p.user_id === null) return UNATTRIBUTED;
  return p.display_name?.trim() || p.email?.trim() || p.user_id;
}

export type Part = { activity: SpendActivity; label: string; line: AmountLine; reserved: string | null };

/** A person's (or a study's) activities that hold anything, in the API's order. An activity
 *  with nothing settled, held or uncertain is a known zero and is left out of the parts. */
export function parts(byActivity: readonly (SpendFigures & { activity: SpendActivity })[]): Part[] {
  return byActivity
    .filter((a) => a.total_usd !== 0 || a.reserved_usd > 0 || a.uncertain_calls > 0)
    .map((a) => ({ activity: a.activity, label: ACTIVITY_LABEL[a.activity] ?? a.activity, line: totalLine(a), reserved: reservedLine(a) }));
}

/** "1 studie", "2 studie", "5 studií". */
export function studyCount(n: number): string {
  if (n === 1) return "1 studie";
  if (n >= 2 && n <= 4) return `${n} studie`;
  return `${n} studií`;
}

/** The sum of every person listed: what the organization spent in the period, as far as the
 *  caller may see. Its uncertainty is the sum of theirs. */
export function overall(report: ResearcherSpend): SpendFigures {
  const sum = (k: keyof SpendFigures) => report.people.reduce((n, p) => n + p[k], 0);
  return {
    model_usd: sum("model_usd"),
    outside_ledger_usd: sum("outside_ledger_usd"),
    total_usd: sum("total_usd"),
    reserved_usd: sum("reserved_usd"),
    uncertain_calls: sum("uncertain_calls"),
  };
}

/** A response is a spend report only with its people as a list; anything else is not, and the
 *  card says so rather than show an empty table that reads as "nobody spent anything". */
export function isSpendReport(value: unknown): value is ResearcherSpend {
  if (!value || typeof value !== "object") return false;
  const v = value as Partial<ResearcherSpend>;
  return Array.isArray(v.people) && typeof v.everyone === "boolean" && typeof v.period === "string";
}

/** A person's share of the period's total, whole percent; null when either is not known exactly. */
export function shareOf(person: SpendFigures, total: SpendFigures): string | null {
  if (person.uncertain_calls > 0 || total.uncertain_calls > 0 || total.total_usd <= 0) return null;
  return `${Math.round((person.total_usd / total.total_usd) * 100)} %`;
}

export type BarPart = { activity: SpendActivity; label: string; percent: number };

/** What a person's spend went on, as parts of one bar: the activities that cost something, in the API's order. */
export function activityBar(byActivity: readonly (SpendFigures & { activity: SpendActivity })[]): BarPart[] {
  const sum = byActivity.reduce((n, a) => n + Math.max(0, a.total_usd), 0);
  if (sum <= 0) return [];
  return byActivity.filter((a) => a.total_usd > 0).map((a) => ({ activity: a.activity, label: ACTIVITY_LABEL[a.activity], percent: (a.total_usd / sum) * 100 }));
}

/** "Téměř vyčerpáno": spent at or past 90 % of the study's budget (the product owner, 2026-10-22). Unknown is never near. */
const NEAR_LIMIT = 0.9;
export function nearLimit(s: { budget_usd: number | null; spent_usd: number | null }): boolean {
  if (s.budget_usd === null || s.spent_usd === null) return false;
  if (s.budget_usd <= 0) return s.spent_usd > 0;
  return s.spent_usd / s.budget_usd >= NEAR_LIMIT;
}

/** A study that accepts no new work: its budget can no longer run out (domain/scope.py accepts_work). */
const CLOSED = new Set(["DELIVERED", "ARCHIVED", "CANCELLED"]);

/** How many open studies are near their budget, and how many could not be judged (costs hidden or
 *  unread). A closed study is not counted, as the server's own tally does not count it. */
export type NearLimitTally = { near: number; unknown: number };
export function nearLimitTally(rows: readonly ({ ok: true; data: { budget_usd: number | null; spent_usd: number | null; status?: string } } | { ok: false })[]): NearLimitTally {
  let near = 0, unknown = 0;
  for (const r of rows) {
    if (r.ok && r.data.status && CLOSED.has(r.data.status)) continue;
    if (!r.ok || r.data.budget_usd === null || r.data.spent_usd === null) unknown++;
    else if (nearLimit(r.data)) near++;
  }
  return { near, unknown };
}
/** The tile's value: an exact count only when every study was judged; never 0 over an unknown (A6). */
export function nearLimitWords(t: NearLimitTally): string {
  if (!t.unknown) return String(t.near);
  return t.near ? `≥ ${t.near}` : "neznámo";
}
