"use client";

// Studie a rozpočty's top as prototype v51 draws it (settings-redesign F7): four figures of the
// period (spent, held by running work, calls with no known bill, studies near their budget),
// then "Útrata podle výzkumníka": one row per person with the period's total and its share, a
// stacked bar of what it went on and those amounts, the studies it touched and its holds; a row
// opens to its studies (develop-spend-attribution 7, Q40). An OWNER or ADMIN sees every member
// and what is booked to nobody; a researcher sees themself only -- the API decides, the card
// shows what it was given. Unknown reads as unknown, never as 0 (lib/researcher-spend.ts).

import { Fragment, type ReactNode, useState } from "react";

import { type ResearcherSpend, type SpendPeriod, admin } from "@/lib/api";
import {
  type BarPart,
  PERIOD_LABEL,
  SPEND_PERIODS,
  type AmountLine,
  type NearLimitTally,
  nearLimitWords,
  isSpendReport,
  activityBar,
  overall,
  parts,
  personLabel,
  reservedLine,
  shareOf,
  totalLine,
  usd,
} from "@/lib/researcher-spend";
import { Button } from "../../rehome/ui";
import { ChoiceChips } from "../../ui/ChoiceChips";
import { FOCUS } from "../../ui/parts";
import { Empty } from "../states";
import { useResource } from "../useResource";

const TH = "px-2 py-1.5 text-left text-xs font-normal text-ink-faint";
const TD = "border-t border-border px-2 py-2.5 align-top text-sm";

async function load(period: SpendPeriod): Promise<ResearcherSpend> {
  const report: unknown = await admin.researcherSpend(period);
  if (!isSpendReport(report)) throw new Error("Odpověď serveru není přehled útraty.");
  return report;
}

function Amount({ line }: { line: AmountLine }) {
  return (
    <span className="whitespace-nowrap font-mono tabular-nums" data-exact={line.exact ? "true" : "false"}>
      {line.text}
      {line.exact ? null : <span aria-hidden="true" className="ml-1 text-status-warn">?</span>}
    </span>
  );
}

// What the spend went on, in the prototype's four colours from the chart palette (never the AI's
// violet, which marks a model at work): the Lead, fieldwork, analysis and report, Deep Research;
// anything else neutral. Each amount under the bar carries its activity's short name as well as
// its colour, so no part is read by colour alone.
const BAR: Record<BarPart["activity"], string> = {
  lead: "bg-viz-cat-1", fieldwork: "bg-viz-cat-2", analysis_report: "bg-viz-cat-4", deep_research: "bg-viz-cat-6", other: "bg-border-strong",
};
const LEGEND: [BarPart["activity"], string][] = [["lead", "Vedoucí"], ["fieldwork", "sběr"], ["analysis_report", "analýza a zpráva"], ["deep_research", "Deep Research"]];
/** Each activity's short name, as the legend and the amounts under a bar say it. */
const SHORT: Record<BarPart["activity"], string> = { lead: "Vedoucí", fieldwork: "sběr", analysis_report: "analýza a zpráva", deep_research: "Deep Research", other: "ostatní" };
// The prototype's legend has the four; spend booked to anything else (design proposals, a client
// document's AI proposals) gets its grey named too whenever a row shows it (Codex on #892).
const OTHER: [BarPart["activity"], string] = ["other", SHORT.other];
const hasOther = (report: ResearcherSpend) => report.people.some((p) => parts(p.by_activity).some((a) => a.activity === "other"));

/** What a person's spend went on, as one bar; the amounts are under it. */
function ActivityBar({ items }: { items: BarPart[] }) {
  if (!items.length) return null;
  return (
    <span data-activity-bar aria-hidden="true" className="mt-1 flex h-2.5 w-full overflow-hidden rounded-pill bg-surface-sunken">
      {items.map((p) => <i key={p.activity} title={p.label} className={`block h-full ${BAR[p.activity]}`} style={{ width: `${p.percent}%` }} />)}
    </span>
  );
}

/** The bar's amounts, in its order: each with its colour's dot and its activity's short name, to the
 *  eye and to a screen reader alike (the full name stays in the dot's title). */
function Parts({ items }: { items: ReturnType<typeof parts> }) {
  if (!items.length) return <span className="text-ink-faint">—</span>;
  return (
    <ul className="mt-1 flex flex-wrap gap-x-2.5 gap-y-0.5 font-mono text-[11px] text-ink-muted">
      {items.map((p) => (
        <li key={p.activity} data-part={p.activity} className="flex items-center gap-1">
          <span aria-hidden="true" title={p.label} className={`size-1.5 rounded-full ${BAR[p.activity]}`} />
          <span className="font-sans">{SHORT[p.activity]}</span> <Amount line={p.line} />
        </li>
      ))}
    </ul>
  );
}

function Tile({ icon, label, children, note }: { icon: string; label: string; children: ReactNode; note: ReactNode }) {
  return (
    <div data-spend-tile className="flex items-start gap-3 rounded-md border border-border bg-surface-raised px-3.5 py-3">
      <span aria-hidden="true" className="grid size-8 shrink-0 place-items-center rounded-full bg-surface-sunken text-sm text-ink-muted">{icon}</span>
      <div className="min-w-0">
        <div className="text-xs text-ink-muted">{label}</div>
        <div className="text-[22px] font-semibold leading-7 tabular-nums">{children}</div>
        <div className="text-xs text-ink-muted">{note}</div>
      </div>
    </div>
  );
}

/** The period's four figures: spent, held, calls with no known bill, studies near their budget. */
function Figures({ report, nearLimitCount }: { report: ResearcherSpend; nearLimitCount: NearLimitTally | null }) {
  const sum = overall(report);
  const line = totalLine(sum);
  const people = report.people.filter((p) => p.user_id !== null && p.total_usd > 0).length;
  const studies = new Set(report.people.flatMap((p) => p.studies.map((st) => st.study_id).filter((id) => id !== null))).size;
  return (
    <div data-org-spend className="grid grid-cols-[repeat(auto-fill,minmax(12.5rem,1fr))] gap-3">
      <Tile icon="Σ" label={`${report.everyone ? "Utraceno" : "Vaše útrata"} · ${PERIOD_LABEL[report.period].toLocaleLowerCase("cs")}`}
        note={line.note ?? <span title="výzkumníci · studie"><span aria-hidden="true">👤︎ </span>{people}<span className="sr-only"> výzkumníků</span> · <span aria-hidden="true">▤ </span>{studies}<span className="sr-only"> studií</span></span>}>
        <Amount line={line} />
      </Tile>
      <Tile icon="⧗" label="Rezervováno" note="běžící práce">{usd(sum.reserved_usd)}</Tile>
      <Tile icon="?" label="Nejistá volání" note="nikdy jako 0 USD">{sum.uncertain_calls}</Tile>
      <Tile icon="⚠" label="Téměř vyčerpané" note={nearLimitCount?.unknown ? `≥ 90 % rozpočtu · u ${nearLimitCount.unknown} nevíme` : "≥ 90 % rozpočtu"}>
        {nearLimitCount ? nearLimitWords(nearLimitCount) : "neznámo"}
      </Tile>
    </div>
  );
}

/** Up to two letters of a person's name or address; "?" for spend booked to nobody. */
function initials(label: string, known: boolean): string {
  if (!known) return "?";
  // Letters only, a letter with its marks one: "Kurátor (seed)" is KS, never "K(", and "Šárka" typed
  // decomposed (S + U+030C) is Š, never S.
  const words = label.normalize("NFC").match(/[\p{L}\p{M}]+/gu) ?? [];
  return words.slice(0, 2).map((w) => [...w][0]!.toLocaleUpperCase("cs")).join("") || "?";
}

export function ResearcherSpendCard({ nearLimitCount = null, roleOf = () => null }: {
  nearLimitCount?: NearLimitTally | null;
  /** A member's role in words ("Správce · Metodik"), from the members the page read; null: unknown. */
  roleOf?: (userId: string) => string | null;
}) {
  const [period, setPeriod] = useState<SpendPeriod>("this_month");
  const [open, setOpen] = useState<string | null>(null);
  const [explained, setExplained] = useState(false);
  const [res, retry] = useResource(() => load(period), [period]);
  const scope = res.state === "ready" ? (res.data.everyone ? "Vlastník a správce vidí všechny členy." : "Vidíte jen svou vlastní útratu.") : "";
  const about = `Každá platba se připisuje tomu, kdo placenou práci schválil nebo spustil (krok Vedoucího, běh, analýza, rešerše). ${scope} Měsíce podle UTC. Rezerva: částky blokované právě běžící prací, zatím neutracené. Otazník: některé volání nemá známou cenu, částka proto není přesná.`;

  return (
    <>
    {res.state === "ready" ? <Figures report={res.data} nearLimitCount={nearLimitCount} /> : null}
    <section data-researcher-spend aria-labelledby="researcher-spend-h" className="min-w-0 rounded-md border border-border bg-surface-raised px-4 py-4 sm:px-6 sm:py-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1.5">
          <h3 id="researcher-spend-h" className="text-base font-semibold">Útrata podle výzkumníka</h3>
          {/* A real disclosure: a keyboard and a touch open what the ⓘ explains, not only a hover. */}
          <button type="button" aria-expanded={explained} aria-controls="researcher-spend-about" aria-label="Jak se útrata počítá"
            title={about} onClick={() => setExplained((v) => !v)} data-dense
            className={`inline-flex size-11 items-center justify-center rounded-full text-sm text-ink-faint hover:text-ink sm:size-6 ${FOCUS}`}>ⓘ</button>
        </div>
        <ChoiceChips look="segmented" small label="Období" value={period} options={SPEND_PERIODS.map((p) => ({ key: p, label: PERIOD_LABEL[p] }))}
          onChange={(p) => { setPeriod(p); setOpen(null); }} />
      </div>
      <p id="researcher-spend-about" hidden={!explained} className="mt-1 max-w-3xl text-xs leading-5 text-ink-muted">{about}</p>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-3.5 gap-y-1 text-xs text-ink-muted">
        {(res.state === "ready" && hasOther(res.data) ? [...LEGEND, OTHER] : LEGEND).map(([key, label]) => <span key={key} data-legend={key} className="flex items-center gap-1"><span aria-hidden="true" className={`size-2 rounded-full ${BAR[key]}`} />{label}</span>)}
        {res.state === "ready" && !res.data.everyone ? <span aria-hidden="true">· jen vaše útrata</span> : null}
      </div>

      <div className="mt-3">
        {res.state === "loading" ? <p className="text-sm text-ink-muted">Načítám…</p> : null}
        {res.state === "not-found" ? <Empty>Přehled útraty zde není k dispozici.</Empty> : null}
        {res.state === "failed" ? (
          <div role="alert" className="flex flex-wrap items-center gap-2 rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm">
            <span><span className="font-semibold text-status-fault">Útratu nelze načíst.</span> {res.message}</span>
            <Button small onClick={retry}>Zkusit znovu</Button>
          </div>
        ) : null}
        {res.state === "ready" ? <Table report={res.data} open={open} setOpen={setOpen} roleOf={roleOf} /> : null}
      </div>
    </section>
    </>
  );
}

function Table({ report, open, setOpen, roleOf }: { report: ResearcherSpend; open: string | null; setOpen: (key: string | null) => void; roleOf: (userId: string) => string | null }) {
  if (!report.people.length) return <Empty>Za toto období nikdo nic neutratil.</Empty>;
  const sum = overall(report);
  return (
    // Its own scroll box where the page is narrower than the table, positioned so an absolute
    // screen-reader-only label inside it never widens the page.
    <div className="relative min-w-0 overflow-x-auto">
      <table className="w-full min-w-[44rem] border-collapse">
        <thead>
          <tr>
            <th scope="col" className={TH}>Výzkumník</th>
            <th scope="col" className={TH}>Utraceno</th>
            <th scope="col" className={TH}>Na co</th>
            <th scope="col" className={TH}><span aria-hidden="true" title="Studií">▤</span><span className="sr-only">Studií</span></th>
            <th scope="col" className={TH}><span aria-hidden="true">⧗ </span>rezerva</th>
            <th scope="col" className={TH}><span className="sr-only">Podle studií</span></th>
          </tr>
        </thead>
        <tbody>
          {report.people.map((p) => {
            const key = p.user_id ?? "__unattributed";
            const line = totalLine(p);
            const expanded = open === key;
            const label = personLabel(p);
            const role = p.user_id === null ? null : roleOf(p.user_id);
            return (
              <Fragment key={key}>
                <tr data-person={key}>
                  <th scope="row" className={`${TD} text-left font-normal`}>
                    <span className="flex items-start gap-2">
                      <span aria-hidden="true" className="grid size-8 shrink-0 place-items-center rounded-full bg-surface-sunken text-xs font-medium text-ink-muted">{initials(label, p.user_id !== null)}</span>
                      <span className="min-w-0">
                        <span className="block font-medium">{label}</span>
                        {role ? <span className="block text-xs text-ink-muted">{role}</span> : null}
                        {p.user_id === null ? <span className="block max-w-56 text-xs text-ink-muted">Placená práce, kterou nikdo neschválil ani nespustil jménem; nepřipisuje se odhadem.</span> : null}
                        {p.is_member === false ? <span className="block text-xs text-ink-muted">Již není členem organizace</span> : null}
                      </span>
                    </span>
                  </th>
                  <td className={TD}>
                    <b className="font-semibold"><Amount line={line} /></b>
                    {line.note ? <span className="block text-xs text-ink-muted">{line.note}</span> : null}
                    {report.everyone && shareOf(p, sum) ? <span data-share className="block text-xs text-ink-muted">{shareOf(p, sum)} organizace</span> : null}
                  </td>
                  <td className={`${TD} min-w-[12rem]`}><ActivityBar items={activityBar(p.by_activity)} /><Parts items={parts(p.by_activity)} /></td>
                  <td className={`${TD} font-mono tabular-nums`}>{p.study_count}</td>
                  <td className={TD}><span className="whitespace-nowrap font-mono tabular-nums">{p.reserved_usd > 0 ? usd(p.reserved_usd) : "—"}</span></td>
                  <td className={`${TD} text-right`}>
                    {p.studies.length ? (
                      <button type="button" data-dense aria-expanded={expanded} aria-label={`Podle studií: ${label}`} title="Podle studií" onClick={() => setOpen(expanded ? null : key)}
                        className={`inline-flex size-8 items-center justify-center rounded-sm text-ink-muted hover:bg-surface-sunken hover:text-ink ${FOCUS}`}>
                        <span aria-hidden="true">{expanded ? "▾" : "▸"}</span>
                      </button>
                    ) : null}
                  </td>
                </tr>
                {expanded ? (
                  <tr data-person-studies={key}>
                    <td colSpan={6} className="bg-surface-sunken py-2 pl-14 pr-4">
                      <ul className="flex flex-col">
                        {p.studies.map((st) => (
                          <li key={`${st.client_id}:${st.study_id ?? ""}`} data-study-spend={st.study_id ?? `client:${st.client_id}`} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-dashed border-border py-1 last:border-b-0">
                            <span className="min-w-0 text-sm">
                              {st.study_id === null ? "Vlastní práce klienta" : (st.study_name ?? st.study_id)}
                              <span className="text-xs text-ink-muted"> · {st.client_name ?? st.client_id}</span>
                            </span>
                            <span className="flex flex-wrap items-baseline gap-3">
                              {reservedLine(st) ? <span className="text-xs text-ink-muted">{reservedLine(st)}</span> : null}
                              <b className="font-semibold"><Amount line={totalLine(st)} /></b>
                            </span>
                          </li>
                        ))}
                      </ul>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
