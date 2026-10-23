"use client";

// "Útrata podle výzkumníka" (Settings → Studie a rozpočty; develop-spend-attribution 7, Q40):
// one row per researcher, the period's total and its parts, the holds open now and the
// studies it touched; a row opens to its studies. An OWNER or ADMIN sees every member and
// what is booked to nobody; a researcher sees themself only -- the API decides, the card shows
// what it was given. Unknown reads as unknown, never as 0 (lib/researcher-spend.ts).

import { Fragment, useState } from "react";

import { type ResearcherSpend, type SpendPeriod, admin } from "@/lib/api";
import {
  type BarPart,
  PERIOD_LABEL,
  SPEND_PERIODS,
  type AmountLine,
  isSpendReport,
  activityBar,
  overall,
  parts,
  personLabel,
  reservedLine,
  shareOf,
  studyCount,
  totalLine,
  usd,
} from "@/lib/researcher-spend";
import { Button } from "../../rehome/ui";
import { MoneyNames } from "./StudiesPanel";
import { EYEBROW, Empty } from "../states";
import { useResource } from "../useResource";

const TH = "px-2 py-1 text-left font-mono text-[11px] font-normal uppercase tracking-[0.08em] text-ink-faint";
const TD = "px-2 py-1.5 align-top text-sm";

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

// The bar's colours: the Lead, fieldwork, analysis and report, Deep Research, other (the design's four, and one more).
const BAR: Record<BarPart["activity"], string> = {
  lead: "bg-ink", fieldwork: "bg-signal", analysis_report: "bg-status-world", deep_research: "bg-ai", other: "bg-border-strong",
};

/** What a person's spend went on, as one bar; the amounts are beside it in words. */
function ActivityBar({ items }: { items: BarPart[] }) {
  if (!items.length) return null;
  return (
    <span data-activity-bar aria-hidden="true" className="mt-1 flex h-2 w-full max-w-56 overflow-hidden rounded-pill bg-surface-sunken">
      {items.map((p) => <i key={p.activity} title={p.label} className={`block h-full ${BAR[p.activity]}`} style={{ width: `${p.percent}%` }} />)}
    </span>
  );
}

function Tile({ label, children, note, highlight = false }: { label: string; children: React.ReactNode; note: string; highlight?: boolean }) {
  return (
    <div data-spend-tile className={`rounded-md border px-3.5 py-3 ${highlight ? "border-status-you bg-status-you-wash" : "border-border"}`}>
      <div className="text-xs text-ink-muted">{label}</div>
      <div className="mt-1 text-[22px] font-semibold leading-7 tabular-nums">{children}</div>
      <div className="mt-0.5 text-xs text-ink-muted">{note}</div>
    </div>
  );
}

/** "Útrata organizace": the period's spend, what running work holds, calls with no known bill, and
 *  studies near their budget; then the four money names. A researcher sees their own only. */
function OrgSpend({ report, nearLimitCount }: { report: ResearcherSpend; nearLimitCount: number | null }) {
  const sum = overall(report);
  const line = totalLine(sum);
  return (
    <section data-org-spend aria-labelledby="org-spend-h" className="min-w-0 rounded-md border border-border bg-surface-raised px-6 py-5">
      <h3 id="org-spend-h" className="text-base font-semibold">{report.everyone ? "Útrata organizace" : "Vaše útrata"} · {PERIOD_LABEL[report.period].toLocaleLowerCase("cs")}</h3>
      <div className="mt-3 grid grid-cols-[repeat(auto-fill,minmax(12.5rem,1fr))] gap-3">
        <Tile label="Utraceno" note={line.note ?? `${report.people.filter((p) => p.user_id !== null && p.total_usd > 0).length} výzkumníků`}><Amount line={line} /></Tile>
        <Tile label="Rezervováno" note="drží právě běžící práce">{usd(sum.reserved_usd)}</Tile>
        <Tile label="Nejistá volání" note="počítají se zvlášť, nikdy jako nula USD">{sum.uncertain_calls}</Tile>
        <Tile label="Téměř vyčerpané rozpočty" note="studie nad 90 % rozpočtu" highlight={(nearLimitCount ?? 0) > 0}>{nearLimitCount ?? "neznámo"}</Tile>
      </div>
      <MoneyNames />
    </section>
  );
}

function Parts({ items }: { items: ReturnType<typeof parts> }) {
  if (!items.length) return <span className="text-ink-faint">—</span>;
  return (
    <ul className="flex flex-wrap gap-x-3 gap-y-1">
      {items.map((p) => (
        <li key={p.activity} data-part={p.activity} className="text-xs">
          <span className="text-ink-muted">{p.label}</span> <Amount line={p.line} />
        </li>
      ))}
    </ul>
  );
}

export function ResearcherSpendCard({ nearLimitCount = null }: { nearLimitCount?: number | null }) {
  const [period, setPeriod] = useState<SpendPeriod>("this_month");
  const [open, setOpen] = useState<string | null>(null);
  const [res, retry] = useResource(() => load(period), [period]);

  return (
    <>
    {res.state === "ready" ? <OrgSpend report={res.data} nearLimitCount={nearLimitCount} /> : null}
    <section data-researcher-spend aria-labelledby="researcher-spend-h" className="min-w-0 rounded-md border border-border bg-surface-raised px-6 py-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 max-w-3xl">
          <h3 id="researcher-spend-h" className="text-base font-semibold">Útrata podle výzkumníka</h3>
          <p className="mt-1 text-sm leading-6 text-ink-muted">
            Každá platba se připisuje tomu, kdo placenou práci schválil nebo spustil.
            {res.state === "ready" && !res.data.everyone ? " Vidíte jen svou vlastní útratu." : null}
            {res.state === "ready" && res.data.everyone ? " Vlastník a správce vidí všechny členy." : null}
          </p>
        </div>
        <div role="group" aria-label="Období" className="flex flex-wrap gap-1">
          {SPEND_PERIODS.map((p) => (
            <Button key={p} small data-dense aria-pressed={period === p} variant={period === p ? "primary" : "secondary"} onClick={() => { setPeriod(p); setOpen(null); }}>
              {PERIOD_LABEL[p]}
            </Button>
          ))}
        </div>
      </div>

      <div className="mt-4">
        {res.state === "loading" ? <p className="text-sm text-ink-muted">Načítám…</p> : null}
        {res.state === "not-found" ? <Empty>Přehled útraty zde není k dispozici.</Empty> : null}
        {res.state === "failed" ? (
          <div role="alert" className="flex flex-wrap items-center gap-2 rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm">
            <span><span className="font-semibold text-status-fault">Útratu nelze načíst.</span> {res.message}</span>
            <Button small onClick={retry}>Zkusit znovu</Button>
          </div>
        ) : null}
        {res.state === "ready" ? <Table report={res.data} open={open} setOpen={setOpen} /> : null}
      </div>
      <p className="mt-3 text-xs leading-5 text-ink-faint">
        Měsíce podle UTC. Drženo: částky blokované právě běžící prací, zatím neutracené. Otazník: některé volání nemá známou cenu, částka proto není přesná.
      </p>
    </section>
    </>
  );
}

function Table({ report, open, setOpen }: { report: ResearcherSpend; open: string | null; setOpen: (key: string | null) => void }) {
  if (!report.people.length) return <Empty>Za toto období nikdo nic neutratil.</Empty>;
  const sum = overall(report);
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr>
            <th className={TH}>Výzkumník</th>
            <th className={`${TH} text-right`}>Celkem</th>
            <th className={TH}>Z toho</th>
            <th className={`${TH} text-right`}>Drženo</th>
            <th className={`${TH} text-right`}>Studie</th>
            <th className={TH} />
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {report.people.map((p) => {
            const key = p.user_id ?? "__unattributed";
            const line = totalLine(p);
            const expanded = open === key;
            return (
              <Fragment key={key}>
                <tr data-person={key}>
                  <td className={`${TD} font-medium`}>
                    {personLabel(p)}
                    {p.user_id === null ? <p className="text-xs font-normal text-ink-muted">Placená práce, kterou nikdo neschválil ani nespustil jménem; nepřipisuje se odhadem.</p> : null}
                    {p.is_member === false ? <p className="text-xs font-normal text-ink-muted">Již není členem organizace</p> : null}
                  </td>
                  <td className={`${TD} text-right`}>
                    <Amount line={line} />
                    {line.note ? <p className="text-xs text-ink-muted">{line.note}</p> : null}
                    {report.everyone && shareOf(p, sum) ? <p data-share className="text-xs text-ink-muted">{shareOf(p, sum)} útraty organizace</p> : null}
                  </td>
                  <td className={TD}><ActivityBar items={activityBar(p.by_activity)} /><Parts items={parts(p.by_activity)} /></td>
                  <td className={`${TD} text-right`}><span className="whitespace-nowrap font-mono tabular-nums">{p.reserved_usd > 0 ? usd(p.reserved_usd) : "—"}</span></td>
                  <td className={`${TD} text-right font-mono tabular-nums`}>{p.study_count}</td>
                  <td className={`${TD} text-right`}>
                    {p.studies.length ? (
                      <Button small data-dense aria-expanded={expanded} onClick={() => setOpen(expanded ? null : key)}>
                        {expanded ? "Skrýt studie" : "Po studiích"}
                      </Button>
                    ) : null}
                  </td>
                </tr>
                {expanded ? (
                  <tr data-person-studies={key}>
                    <td colSpan={6} className="bg-surface-sunken px-3 py-3">
                      <p className={EYEBROW}>{personLabel(p)} · {studyCount(p.study_count)}</p>
                      <ul className="mt-2 flex flex-col gap-2">
                        {p.studies.map((s) => (
                          <li key={`${s.client_id}:${s.study_id ?? ""}`} data-study-spend={s.study_id ?? `client:${s.client_id}`} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                            <span className="min-w-0 text-sm">
                              <span className="font-medium">{s.study_id === null ? "Vlastní práce klienta" : (s.study_name ?? s.study_id)}</span>
                              <span className="text-ink-muted"> · {s.client_name ?? s.client_id}</span>
                            </span>
                            <span className="flex flex-wrap items-baseline gap-3">
                              <Parts items={parts(s.by_activity)} />
                              <Amount line={totalLine(s)} />
                              {reservedLine(s) ? <span className="text-xs text-ink-muted">{reservedLine(s)}</span> : null}
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
        {report.everyone && report.people.length > 1 ? (
          <tfoot>
            <tr className="border-t border-border-strong">
              <td className={`${TD} font-semibold`}>Organizace celkem</td>
              <td className={`${TD} text-right font-semibold`}><Amount line={totalLine(sum)} /></td>
              <td className={TD} />
              <td className={`${TD} text-right font-mono tabular-nums`}>{sum.reserved_usd > 0 ? usd(sum.reserved_usd) : "—"}</td>
              <td className={TD} colSpan={2} />
            </tr>
          </tfoot>
        ) : null}
      </table>
    </div>
  );
}
