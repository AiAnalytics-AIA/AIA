"use client";

// Vzorek (plan artifact-sample; research-lead-workbench D2): the prototype's sample stage over what
// AIA keeps elsewhere. The sample size and the dimensions are Dimenze's, the audience is Cílová
// skupina's, and the forecast and readiness are the server's, read on the design as it stands. So
// this view edits nothing and decides nothing: it shows what is set, what the server forecasts,
// and links to where each is set.

import type { ReactNode } from "react";

import { TOUCH, TOUCH_LINK } from "@/components/ui/parts";
import { t } from "@/i18n/t";
import { plural } from "@/lib/format";
import { sampleAia } from "@/lib/artifacts/sample";
import type { OutlookVerdict } from "@/lib/api";
import { codeWords } from "@/lib/reason-words";
import { VERDICT_ORDER } from "@/lib/research-execution";
import { SUPPORT_FORECAST_CHECK, checkStage, compositionOf, outlookSummary, personaSourcesOf, readinessLine, readinessSummary, sourceChosenOnRun, supportForecastOf, type CompositionRow } from "@/lib/sample-view";
import { STAGES } from "@/lib/workbench-stages";
import type { WorkbenchStage } from "@/lib/workbench-stages";
import { audienceReady } from "@/research/audience";
import type { ResearchProject } from "@/research/model";
import { PERSONA_DIM_LABELS, chosenDimensions, recommendedSample } from "@/research/persona";
import { CodedWords } from "../rehome/research/CodedWords";
import { useResearch } from "../rehome/research/context";
import { Glyph, type GlyphTone } from "./Glyph";
import { useSampleReadiness, type SampleReadiness } from "./useSampleReadiness";

type Open = (stage: WorkbenchStage) => void;

export function SampleView({ project, onOpen }: { project: ResearchProject; onOpen: Open }) {
  const { store, frame, state } = useResearch();
  const readiness = useSampleReadiness(store, frame.studyId, frame.canEdit, state.revision);
  return <SampleArtifact project={project} readiness={readiness} onOpen={onOpen} />;
}

function Sec({ n, title, aside, aia, children }: { n: number; title: string; aside?: string; aia: string; children: ReactNode }) {
  return (
    <section className="rounded-card border border-border bg-surface-raised p-4" aria-label={title} data-aia={aia}>
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="text-sm tabular-nums text-ink-muted">{n}</span>
        <h2 className="text-base font-semibold">{title}</h2>
        {aside ? <span className="ml-auto text-sm text-ink-muted">{aside}</span> : null}
      </div>
      <div className="mt-2 flex flex-col gap-3">{children}</div>
    </section>
  );
}

/** How many cells the composition lists before the rest fold away. */
const CELLS_SHOWN = 10;

/** One decimal on every row, so a column of shares reads aligned ("3,0 %" beside "2,7 %"). */
const share = (x: number) => `${(x * 100).toLocaleString("cs-CZ", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`;

function CellRows({ rows }: { rows: CompositionRow[] }) {
  return rows.map((r) => (
    <tr key={r.key} className="border-t border-border" data-aia={sampleAia.quota(r.key) ?? undefined}>
      <td className="py-1 pr-3">{r.label}</td>
      <td className="py-1 pr-3 text-right tabular-nums">{share(r.share)}</td>
      <td className="py-1 text-right tabular-nums">{r.n}</td>
    </tr>
  ));
}

function CellTable({ rows, caption }: { rows: CompositionRow[]; caption: string }) {
  return (
    <table className="mt-1 w-full text-sm">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr className="text-left text-ink-muted">
          <th scope="col" className="py-1 pr-3 font-normal">Kvótní buňka</th>
          <th scope="col" className="py-1 pr-3 text-right font-normal">Podíl</th>
          <th scope="col" className="py-1 text-right font-normal">n</th>
        </tr>
      </thead>
      <tbody><CellRows rows={rows} /></tbody>
    </table>
  );
}

/** §1's composition (SMP2): the sampler's own quota allotment for a panel run, read only. */
function Composition({ readiness }: { readiness: SampleReadiness }) {
  if (readiness.kind !== "ready") return null;
  const c = compositionOf(readiness.readiness);
  const body =
    c.kind === "roster" ? <p className="mt-1 text-sm text-ink-muted">Fiktivní respondenti se nevybírají podle kvót.</p>
    : c.kind === "unknown" ? <p className="mt-1 text-sm">Složení vzorku z populace: neznámé. Server ho pro tento návrh předem nevybral.</p>
    : c.kind === "refused" ? <p className="mt-1 text-sm" role="status">Vzorek z populace teď nelze vybrat: {c.words}</p>
    : (
      <>
        <p className="mt-1 text-sm text-ink-muted">
          Podle: {c.fields.join(" × ")}. {plural(c.rows.length, "buňka", "buňky", "buněk")} s respondenty
          {c.donors !== null ? `, ${plural(c.donors, "různý dárce", "různí dárci", "různých dárců")}` : ""}.
        </p>
        <CellTable rows={c.rows.slice(0, CELLS_SHOWN)} caption="Složení vzorku podle kvót" />
        {c.rows.length > CELLS_SHOWN ? (
          <details className="text-sm">
            <summary className={`cursor-pointer text-signal ${TOUCH}`}>Dalších {plural(c.rows.length - CELLS_SHOWN, "buňka", "buňky", "buněk")}</summary>
            <CellTable rows={c.rows.slice(CELLS_SHOWN)} caption="Další buňky vzorku" />
          </details>
        ) : null}
      </>
    );
  return (
    <div>
      <div className="flex items-center gap-2"><Glyph tone={c.kind === "drawn" ? "done" : "inert"} size={12} /><h3 className="text-sm font-semibold">Složení podle kvót</h3></div>
      {body}
    </div>
  );
}

const STATUS_TONE: Record<string, GlyphTone> = { PASS: "done", WARN: "done-warn", FAIL: "fault" };
const VERDICT_TONE: Record<OutlookVerdict, GlyphTone> = { ANSWERABLE: "done", UNKNOWN: "inert", AT_RISK: "you", UNANSWERABLE: "fault" };

export function SampleArtifact({ project, readiness, onOpen }: { project: ResearchProject; readiness: SampleReadiness; onOpen: Open }) {
  const n = Number(project.n) || 0;
  const dims = chosenDimensions(project);
  const rec = recommendedSample(project);
  const audience = project.audience ?? {};
  const description = typeof audience.description === "string" ? audience.description : "";
  const filters = audience.filters && typeof audience.filters === "object" ? Object.keys(audience.filters).length : 0;
  return (
    <div className="flex max-w-3xl flex-col gap-4" aria-label="Vzorek" data-sample-view>
      <p className="text-sm text-ink-muted">Přehled vzorku jen ke čtení. Velikost a dimenze se nastavují v Dimenzích, cílová skupina ve svém kroku; zda vzorek stačí, říká server níže. Běh se spouští ve Sběru dat.</p>
      <Sec n={1} title="Velikost a složení" aside={n ? `n ${n}` : undefined} aia={sampleAia.section("size")}>
        <div data-aia={sampleAia.n()}>
          <div className="flex items-center gap-2"><Glyph tone={n ? "done" : "inert"} size={12} /><h3 className="text-sm font-semibold">Velikost vzorku</h3></div>
          <p className="mt-1 text-2xl font-semibold tabular-nums">{n ? `N = ${n}` : "Nenastaveno"}</p>
          <p className="text-sm text-ink-muted">Doporučeno {rec.n}: {rec.why}</p>
          <button type="button" className={`mt-1 text-sm ${TOUCH_LINK}`} onClick={() => onOpen("dimensions")}>Upravit v Dimenzích</button>
        </div>
        <div>
          <div className="flex items-center gap-2"><Glyph tone={audienceReady(project) ? "done" : "inert"} size={12} /><h3 className="text-sm font-semibold">Cílová skupina</h3></div>
          <p className="mt-1 text-sm">{description || "Bez popisu"}{filters ? ` · ${filters} ${filters === 1 ? "filtr" : filters < 5 ? "filtry" : "filtrů"}` : ""}</p>
          <button type="button" className={`mt-1 text-sm ${TOUCH_LINK}`} onClick={() => onOpen("audience")}>Upravit cílovou skupinu</button>
        </div>
        <div>
          <div className="flex items-center gap-2"><Glyph tone={dims.length ? "done" : "inert"} size={12} /><h3 className="text-sm font-semibold">Dimenze</h3></div>
          {dims.length ? <ul className="mt-1 flex flex-wrap gap-1.5">{dims.map((d) => <li key={d} className="rounded-sm border border-border px-2 py-0.5 text-sm">{PERSONA_DIM_LABELS[d] ?? d}</li>)}</ul> : <p className="mt-1 text-sm text-ink-muted">Žádné</p>}
        </div>
        <Composition readiness={readiness} />
      </Sec>
      <Sec n={2} title="Odhad podpory před během" aside="odhad, ne výsledek" aia={sampleAia.section("forecast")}>
        <Forecast readiness={readiness} />
        <p className="text-sm text-ink-muted">
          Skutečná podpora dvojic se ověří až z výsledných dat (
          <button type="button" className="text-signal underline" onClick={() => onOpen("sociomap")}>Sociomapa</button>
          ). Kvóta ji nezaručuje.
        </p>
      </Sec>
      <Ready readiness={readiness} onOpen={onOpen} />
      <Sec n={4} title="Kdo bude odpovídat" aia={sampleAia.section("respondents")}>
        <Respondents readiness={readiness} onOpen={onOpen} />
      </Sec>
    </div>
  );
}

// Připravenost ke spuštění (SMP4, SMP4b): every check the server ran on the working copy, worst
// first, in words, each with one way to fix it where it is fixed. Read only: whether to start is the
// person's, on Sběr dat.

/** A check's status in the board's words; a status this client does not know is said so. */
const STATUS_WORDS: Record<string, string> = { PASS: "V pořádku", WARN: "Upozornění: běh poběží", FAIL: "Brání spuštění" };

/** "Opravit v …": where a check's stage is, in the locative; another stage is opened by its name. */
const FIX_IN: Partial<Record<WorkbenchStage, string>> = { dimensions: "v Dimenzích", audience: "v Cílové skupině", questionnaire: "v Dotazníku" };

function Ready({ readiness, onOpen }: { readiness: SampleReadiness; onOpen: Open }) {
  const summary = readiness.kind === "ready" ? readinessSummary(readiness.readiness) : null;
  const forecast = readiness.kind === "ready" ? supportForecastOf(readiness.readiness) : null;
  const line = summary ? readinessLine(summary) : null;
  return (
    <Sec n={3} title="Připravenost ke spuštění" aia={sampleAia.section("ready")}>
      {readiness.kind === "loading" ? <p className="text-sm text-ink-muted" role="status">Načítám kontroly ze serveru…</p>
        : readiness.kind === "failed" ? <p className="text-sm text-status-fault" role="alert">Kontroly se nepodařilo načíst: {readiness.message}</p>
        : readiness.kind === "none" || !summary || !line ? <p className="text-sm text-ink-muted">Obsah studie zatím není uložený, takže kontroly neproběhly.</p>
        : (
          <>
            <p className="flex items-center gap-2 text-sm font-semibold" role="status"><Glyph tone={line.tone} size={12} />{line.words}</p>
            <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted" aria-label="Vysvětlivky">
              {(["PASS", "WARN", "FAIL"] as const).map((s) => <li key={s} className="flex items-center gap-1.5"><Glyph tone={STATUS_TONE[s]} size={10} />{STATUS_WORDS[s]}</li>)}
            </ul>
            <ul className="flex flex-col" aria-label="Kontroly připravenosti">
              {summary.checks.filter((c) => c.id !== SUPPORT_FORECAST_CHECK).map((c) => {
                const stage = checkStage(c.id);
                return (
                  <li key={c.id} className="flex items-start gap-2 border-t border-border py-1.5 text-sm first:border-t-0" data-aia={sampleAia.ready(c.id) ?? undefined}>
                    <span className="mt-1"><Glyph tone={STATUS_TONE[c.status] ?? "inert"} size={12} title={STATUS_WORDS[c.status] ?? "neznámý stav"} /></span>
                    <span className="min-w-0 flex-1">{c.message}</span>
                    {stage ? (
                      <button type="button" className={`shrink-0 text-xs ${TOUCH_LINK}`} data-opens={STAGES[stage].label} onClick={() => onOpen(stage)}>
                        {FIX_IN[stage] ? `Opravit ${FIX_IN[stage]}` : `Otevřít ${STAGES[stage].label}`}
                      </button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </>
        )}
      {/* The forecast is shown in section 2; here it is counted, and named when it warns. */}
      {forecast && (!forecast.known || forecast.status !== "PASS") && summary?.checks.some((c) => c.id === SUPPORT_FORECAST_CHECK) ? (
        <p className="text-sm text-ink-muted">{forecast.known ? "Odhad opory výsledků varuje" : "Opora výsledků je předem neznámá"}: viz oddíl 2.</p>
      ) : null}
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" className={`rounded-control border border-border-strong px-3 py-1.5 text-sm font-medium ${TOUCH}`} onClick={() => onOpen("fieldwork")}>Pokračovat na Sběr dat</button>
      </div>
    </Sec>
  );
}

function Forecast({ readiness }: { readiness: SampleReadiness }) {
  if (readiness.kind === "loading") return <p className="text-sm text-ink-muted" role="status">Načítám odhad ze serveru…</p>;
  if (readiness.kind === "failed") return <p className="text-sm text-status-fault" role="alert">Odhad se nepodařilo načíst: {readiness.message}</p>;
  if (readiness.kind === "none") return <p className="text-sm text-ink-muted">Obsah studie zatím není uložený, takže odhad není. Odhad je neznámý.</p>;
  const support = supportForecastOf(readiness.readiness);
  const outlook = outlookSummary(readiness.readiness);
  return (
    <>
      <p className="text-xs text-ink-muted">Podle pracovní kopie, revize {readiness.revision}</p>
      <div className="flex items-start gap-2" data-aia={sampleAia.forecast("support")}>
        <span className="mt-1"><Glyph tone={support.known ? (STATUS_TONE[support.status] ?? "inert") : "inert"} size={12} title={support.known ? support.status : "neznámé"} /></span>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">Opora výsledků{support.known ? "" : ": neznámé"}</h3>
          <p className="text-sm">{support.message ?? "Server oporu pro tento běh předem nespočítal."}</p>
        </div>
      </div>
      <div className="flex items-start gap-2" data-aia={sampleAia.forecast("outlook")}>
        <span className="mt-1"><Glyph tone={outlook ? (outlook.UNANSWERABLE ? "fault" : outlook.AT_RISK ? "you" : outlook.UNKNOWN ? "inert" : "done") : "inert"} size={12} /></span>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">Na co běh odpoví{outlook ? "" : ": neznámé"}</h3>
          {outlook ? (
            <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm">
              {VERDICT_ORDER.map((v) => (
                <li key={v} className="flex items-center gap-1.5"><Glyph tone={VERDICT_TONE[v]} size={10} /><span className="tabular-nums">{outlook[v]}</span> {t(`research.exec.outlook.verdict.${v}`)}</li>
              ))}
            </ul>
          ) : <p className="text-sm">Server výhled otázek pro tento návrh nevrátil.</p>}
        </div>
      </div>
    </>
  );
}

const R = "research.exec.respondents";

// Kdo bude odpovídat (SMP5, SQ1 = Q54 b): what the server offers and its default, read only. The
// source is chosen on Spuštění, beside the start that pins it, so nothing here sets it.
function Respondents({ readiness, onOpen }: { readiness: SampleReadiness; onOpen: Open }) {
  const sources = readiness.kind === "ready" ? personaSourcesOf(readiness.readiness) : null;
  // Spuštění offers the choice only for a run AI respondents answer; elsewhere there is none to send the person to.
  const chosen = readiness.kind === "ready" && sourceChosenOnRun(readiness.readiness);
  return (
    <>
      {readiness.kind === "loading" ? <p className="text-sm text-ink-muted" role="status">Načítám nabídku ze serveru…</p>
        : readiness.kind === "failed" ? <p className="text-sm text-status-fault">Nabídku se nepodařilo načíst.</p>
        : readiness.kind === "ready" && readiness.readiness.fieldwork_source !== "ai_runtime" ? <p className="text-sm">Toto nasazení nesbírá data přes AI respondenty, takže se zdroj respondentů nevolí.</p>
        : !sources ? <p className="text-sm text-ink-muted">Server zdroje respondentů nevrátil: neznámé.</p>
        : (
          <ul className="flex flex-col gap-2" aria-label="Zdroje respondentů">
            {sources.map((o) => (
              <li key={o.source} className={`flex items-start gap-2 text-sm ${o.offered ? "" : "text-ink-muted"}`} data-aia={sampleAia.respondents(o.source) ?? undefined}>
                <span className="mt-1"><Glyph tone={o.offered ? (o.default ? "done" : "ready") : "inert"} size={12} title={o.offered ? "nabízeno" : "nenabízeno"} /></span>
                <span className="flex min-w-0 flex-col">
                  <span>
                    <span className="font-semibold">{t(`${R}.${o.source}`)}</span>
                    {o.default ? <span className="text-ink-muted"> · {t(`${R}.default`)}</span> : null}
                    {o.offered ? null : <span> · nenabízeno</span>}
                  </span>
                  <span className="text-xs text-ink-muted">{o.offered ? t(`${R}.${o.source}Help`) : <CodedWords inline coded={codeWords(`${R}.reason`, o.reason ?? "")} />}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      {chosen ? (
        <p className="text-sm text-ink-muted">
          Zdroj se volí ve Spuštění, u startu běhu, který ho zapíše.{" "}
          <button type="button" className="text-signal underline" onClick={() => onOpen("fieldwork")}>Změnit ve Spuštění</button>
        </p>
      ) : null}
    </>
  );
}
