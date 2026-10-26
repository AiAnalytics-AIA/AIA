"use client";

// Vzorek (plan artifact-sample; research-lead-workbench D2): the prototype's sample stage over what
// AIA keeps elsewhere. The sample size is set here (SMP7; Nigel, 26 Oct 2026: N is set on Vzorek); the
// dimensions are Dimenze's, the audience is Cílová skupina's, and the forecast and readiness are the
// server's, read on the design as it stands. Beyond n this view edits nothing and decides nothing: it
// shows what is set, what the server forecasts, and links to where each is set.

import { type ReactNode, useEffect, useState } from "react";

import { TOUCH, TOUCH_LINK } from "@/components/ui/parts";
import { t, tv } from "@/i18n/t";
import { plural } from "@/lib/format";
import { sampleAia } from "@/lib/artifacts/sample";
import type { OutlookVerdict, PersonaSourceOption } from "@/lib/api";
import { codeWords } from "@/lib/reason-words";
import { SUPPORT_FORECAST_CHECK, checkStage, compositionOf, outlookTiles, personaSourcesOf, readinessSummary, sourceChosenOnRun, supportForecastOf, type CompositionRow } from "@/lib/sample-view";
import { STAGES } from "@/lib/workbench-stages";
import type { WorkbenchStage } from "@/lib/workbench-stages";
import { audienceReady } from "@/research/audience";
import type { ResearchProject } from "@/research/model";
import { chosenDimensions, clientDimensions, dimensionLabels, recommendedSample } from "@/research/persona";
import { workspace } from "@/lib/api";
import { CodedWords } from "../rehome/research/CodedWords";
import { SampleSize } from "../rehome/research/SampleSize";
import { useResearch } from "../rehome/research/context";
import { Glyph, type GlyphTone } from "./Glyph";
import { useSampleReadiness, type SampleReadiness } from "./useSampleReadiness";

type Open = (stage: WorkbenchStage) => void;

export function SampleView({ project, onOpen }: { project: ResearchProject; onOpen: Open }) {
  const { store, frame, state } = useResearch();
  const readiness = useSampleReadiness(store, frame.studyId, frame.canEdit, state.revision);
  const labels = useDimensionLabels(frame.studyId);
  return <SampleArtifact project={project} readiness={readiness} onOpen={onOpen} labels={labels} size={<SampleSize />} />;
}

/**
 * The dimension names Dimenze shows: the system's, with the client's own library dimensions by
 * their titles, so a library dimension is never named by its id (spec vzorek V6, critique d2).
 * Without the client's knowledge, the system's names.
 */
function useDimensionLabels(studyId: string): Record<string, string> {
  const [labels, setLabels] = useState(() => dimensionLabels({}));
  useEffect(() => {
    let live = true;
    workspace.studyContext(studyId).then(
      (c) => live && setLabels(dimensionLabels(clientDimensions(c.client))),
      () => {},
    );
    return () => {
      live = false;
    };
  }, [studyId]);
  return labels;
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

/** How many groups the composition lists before the rest fold away (the v73 board: six). */
const CELLS_SHOWN = 6;

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
          <th scope="col" className="py-1 pr-3 font-normal">Skupina</th>
          <th scope="col" className="py-1 pr-3 text-right font-normal">Podíl</th>
          <th scope="col" className="py-1 text-right font-normal">Respondentů</th>
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
        <CellTable rows={c.rows.slice(0, CELLS_SHOWN)} caption="Složení vzorku podle kvót" />
        {c.rows.length > CELLS_SHOWN ? (
          <details className="text-sm">
            <summary className={`cursor-pointer text-signal ${TOUCH}`}>Dalších {plural(c.rows.length - CELLS_SHOWN, "skupina", "skupiny", "skupin")}</summary>
            <CellTable rows={c.rows.slice(CELLS_SHOWN)} caption="Další skupiny vzorku" />
          </details>
        ) : null}
        <p className="text-sm text-ink-muted">Kvóta říká, kolik lidí každé skupiny vytáhneme; neříká, že odpoví na každou otázku.</p>
      </>
    );
  return (
    <div>
      <div className="flex items-center gap-2">
        <Glyph tone={c.kind === "drawn" ? "done" : "inert"} size={12} />
        <h3 className="text-sm font-semibold">Složení podle kvót{c.kind === "drawn" && c.fields.length ? ` · ${c.fields.join(" × ").toLocaleLowerCase("cs")}` : ""}</h3>
      </div>
      {body}
    </div>
  );
}

const STATUS_TONE: Record<string, GlyphTone> = { PASS: "done", WARN: "done-warn", FAIL: "fault" };
const VERDICT_TONE: Record<OutlookVerdict, GlyphTone> = { ANSWERABLE: "done", UNKNOWN: "inert", AT_RISK: "you", UNANSWERABLE: "fault" };

/** A link to the stage where a part of the sample is set: its name, what is set there, and the way. */
function LinkCard({ title, caption, done, onClick }: { title: string; caption: string; done: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className={`flex items-start gap-2 rounded-card border border-border px-3 py-2 text-left hover:bg-surface ${TOUCH}`}>
      <span className="mt-1"><Glyph tone={done ? "done" : "inert"} size={12} /></span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-sm font-semibold">{title}</span>
        <span className="text-sm text-ink-muted">{caption}</span>
      </span>
      <span aria-hidden className="text-ink-muted">›</span>
    </button>
  );
}

/** `size` is the sample size's control (SampleSize); without one, n is read only. */
export function SampleArtifact({ project, readiness, onOpen, labels = dimensionLabels({}), size }: { project: ResearchProject; readiness: SampleReadiness; onOpen: Open; labels?: Record<string, string>; size?: ReactNode }) {
  const n = Number(project.n) || 0;
  const dims = chosenDimensions(project);
  const rec = recommendedSample(project);
  const audience = project.audience ?? {};
  const description = typeof audience.description === "string" ? audience.description : "";
  const filters = audience.filters && typeof audience.filters === "object" ? Object.keys(audience.filters).length : 0;
  return (
    <div className="flex max-w-3xl flex-col gap-4" aria-label="Vzorek" data-sample-view>
      <p className="text-sm text-ink-muted">Velikost vzorku nastavujete tady; dimenze v Dimenzích, cílová skupina ve svém kroku; zda vzorek stačí, říká server níže. Běh se spouští ve Sběru dat.</p>
      <Sec n={1} title="Velikost a složení" aside={n ? `n ${n}` : undefined} aia={sampleAia.section("size")}>
        <div data-aia={sampleAia.n()}>
          <div className="flex items-center gap-2"><Glyph tone={n ? "done" : "inert"} size={12} /><h3 className="text-sm font-semibold">Velikost vzorku</h3></div>
          {size ? <div className="mt-2">{size}</div> : (
            <>
              <p className="mt-1 text-2xl font-semibold tabular-nums">{n ? `N = ${n}` : "Nenastaveno"}</p>
              <p className="text-sm text-ink-muted">Doporučeno {rec.n}: {rec.why}</p>
            </>
          )}
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-2">
          <LinkCard
            title="Cílová skupina"
            caption={`${description || "Bez popisu"}${filters ? ` · ${plural(filters, "faktor", "faktory", "faktorů")}` : ""}`}
            done={audienceReady(project)}
            onClick={() => onOpen("audience")}
          />
          <LinkCard title="Dimenze" caption={dims.length ? dims.map((d) => labels[d] ?? d).join(", ") : "Žádné"} done={dims.length > 0} onClick={() => onOpen("dimensions")} />
        </div>
        <Composition readiness={readiness} />
      </Sec>
      <Sec n={2} title="Kolik dat bude za čísly" aside="odhad před během, ne výsledek" aia={sampleAia.section("forecast")}>
        <Forecast readiness={readiness} />
        {/* Pair support is not forecast: AIA cannot ask who knows both brands before a run (R9). */}
        <div className="flex items-start gap-2 text-sm text-ink-muted">
          <span className="mt-1"><Glyph tone="inert" size={12} /></span>
          <p className="min-w-0">
            <span className="font-semibold text-ink">Mapa značek:</span> podporu dvojic AIA před během neodhadne; ověří se až z dat (
            <button type="button" className="text-signal underline" onClick={() => onOpen("sociomap")}>Sociomapa</button>
            ). Kvóta ji nezaručuje.
          </p>
        </div>
      </Sec>
      <Ready readiness={readiness} onOpen={onOpen} />
      <Sec n={4} title="Kdo bude odpovídat" aia={sampleAia.section("respondents")}>
        <Respondents readiness={readiness} onOpen={onOpen} />
      </Sec>
    </div>
  );
}

// Připravenost ke spuštění (SMP4): every check the server ran on the working copy, worst first, each
// with the stage that fixes it. Read only: whether to start is the person's, on Sběr dat.
function Ready({ readiness, onOpen }: { readiness: SampleReadiness; onOpen: Open }) {
  const summary = readiness.kind === "ready" ? readinessSummary(readiness.readiness) : null;
  const forecast = readiness.kind === "ready" ? supportForecastOf(readiness.readiness) : null;
  // The server's `ready` decides; the counts only say why.
  const aside = !summary ? undefined
    : !summary.ready ? (summary.blocking ? `${plural(summary.blocking, "kontrola", "kontroly", "kontrol")} brání spuštění` : "server spuštění nepovolí")
    : summary.unknown ? "stav některých kontrol neznámý"
    : summary.warnings ? `${summary.warnings} varování, nic nebrání`
    : "nic nebrání";
  return (
    <Sec n={3} title="Připravenost ke spuštění" aside={aside} aia={sampleAia.section("ready")}>
      {readiness.kind === "loading" ? <p className="text-sm text-ink-muted" role="status">Načítám kontroly ze serveru…</p>
        : readiness.kind === "failed" ? <p className="text-sm text-status-fault" role="alert">Kontroly se nepodařilo načíst: {readiness.message}</p>
        : readiness.kind === "none" || !summary ? <p className="text-sm text-ink-muted">Obsah studie zatím není uložený, takže kontroly neproběhly.</p>
        : (
          <ul className="flex flex-col" aria-label="Kontroly připravenosti">
            {summary.checks.filter((c) => c.id !== SUPPORT_FORECAST_CHECK).map((c) => {
              const stage = checkStage(c.id);
              return (
                <li key={c.id} className="flex items-start gap-2 border-t border-border py-1.5 text-sm first:border-t-0" data-aia={sampleAia.ready(c.id) ?? undefined}>
                  <span className="mt-1"><Glyph tone={STATUS_TONE[c.status] ?? "inert"} size={12} title={c.status} /></span>
                  <span className="min-w-0 flex-1">{c.message}</span>
                  {stage ? <button type="button" className={`shrink-0 text-xs ${TOUCH_LINK}`} onClick={() => onOpen(stage)}>{STAGES[stage].label}</button> : null}
                </li>
              );
            })}
          </ul>
        )}
      {/* The forecast is shown in section 2; here it is counted, and named when it warns. */}
      {forecast && (!forecast.known || forecast.status !== "PASS") && summary?.checks.some((c) => c.id === SUPPORT_FORECAST_CHECK) ? (
        <p className="text-sm text-ink-muted">{forecast.known ? "Odhad opory výsledků varuje" : "Opora výsledků je předem neznámá"}: viz oddíl 2.</p>
      ) : null}
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" className={`rounded-control border border-border-strong px-3 py-1.5 text-sm font-medium ${TOUCH}`} onClick={() => onOpen("fieldwork")}>Pokračovat na Sběr dat</button>
        {summary?.ready && !summary.unknown && summary.warnings ? <span className="text-xs text-ink-muted">Lze pokračovat s omezeními.</span> : null}
      </div>
    </Sec>
  );
}

/** §02's tiles, in the board's words; unanswerable only appears when an item is (spec vzorek V4). */
const TILE: Record<OutlookVerdict, string> = {
  ANSWERABLE: "Zodpověditelné otázky",
  AT_RISK: "Ohrožené",
  UNKNOWN: "Nelze říct předem",
  UNANSWERABLE: "Bez odpovědi",
};

function shortReason(code: string): string {
  const key = `research.exec.outlook.short.${code}`;
  const words = t(key);
  return words === key ? tv("research.exec.outlook.short.other", { code }) : words;
}

function Forecast({ readiness }: { readiness: SampleReadiness }) {
  if (readiness.kind === "loading") return <p className="text-sm text-ink-muted" role="status">Načítám odhad ze serveru…</p>;
  if (readiness.kind === "failed") return <p className="text-sm text-status-fault" role="alert">Odhad se nepodařilo načíst: {readiness.message}</p>;
  if (readiness.kind === "none") return <p className="text-sm text-ink-muted">Obsah studie zatím není uložený, takže odhad není. Odhad je neznámý.</p>;
  const support = supportForecastOf(readiness.readiness);
  const tiles = outlookTiles(readiness.readiness);
  return (
    <>
      <p className="text-xs text-ink-muted">Podle pracovní kopie, revize {readiness.revision}</p>
      <div className="flex items-start gap-2" data-aia={sampleAia.forecast("support")}>
        <span className="mt-1"><Glyph tone={support.known ? (STATUS_TONE[support.status] ?? "inert") : "inert"} size={12} title={support.known ? undefined : "neznámé"} /></span>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">Opora výsledků{support.known ? "" : ": neznámé"}</h3>
          <p className="text-sm">{support.message ?? "Server oporu pro tento běh předem nespočítal."}</p>
        </div>
      </div>
      <div data-aia={sampleAia.forecast("outlook")}>
        <h3 className="sr-only">Na co běh odpoví</h3>
        {tiles ? (
          <ul className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-2" aria-label="Na co běh odpoví">
            {tiles.map((tile) => (
              <li key={tile.verdict} className="rounded-card border border-border px-3 py-2" data-verdict={tile.verdict}>
                <div className="flex items-center gap-1.5 text-xs text-ink-muted"><Glyph tone={VERDICT_TONE[tile.verdict]} size={10} />{TILE[tile.verdict]}</div>
                <div className="text-2xl font-semibold tabular-nums">{tile.count}</div>
                {tile.reason && tile.count ? <div className="text-xs text-ink-muted">{shortReason(tile.reason)}</div> : null}
              </li>
            ))}
          </ul>
        ) : <p className="text-sm">Na co běh odpoví: neznámé. Server výhled otázek pro tento návrh nevrátil.</p>}
      </div>
    </>
  );
}

const R = "research.exec.respondents";

// Kdo bude odpovídat (SMP5, SQ1 = Q54 b): what the server offers and its default, read only. The
// source is chosen in Sběr dat, beside the start that pins it, so nothing here sets it.
function Respondents({ readiness, onOpen }: { readiness: SampleReadiness; onOpen: Open }) {
  const sources = readiness.kind === "ready" ? personaSourcesOf(readiness.readiness) : null;
  // The choice is made in Sběr dat, beside the start that pins it, and only for a run AI respondents
  // answer; elsewhere there is none to send the person to.
  const chosen = readiness.kind === "ready" && sourceChosenOnRun(readiness.readiness);
  if (readiness.kind === "loading") return <p className="text-sm text-ink-muted" role="status">Načítám nabídku ze serveru…</p>;
  if (readiness.kind === "failed") return <p className="text-sm text-status-fault">Nabídku se nepodařilo načíst.</p>;
  if (readiness.kind === "ready" && readiness.readiness.fieldwork_source !== "ai_runtime") {
    return <p className="text-sm">Toto nasazení nesbírá data přes AI respondenty, takže se zdroj respondentů nevolí.</p>;
  }
  if (!sources) return <p className="text-sm text-ink-muted">Server zdroje respondentů nevrátil: neznámé.</p>;
  // One line: the source a run takes unless the person chooses otherwise (spec vzorek V7). The
  // others, with why one is not offered, stay one click away.
  const main = sources.find((o) => o.offered && o.default) ?? null;
  const rest = sources.filter((o) => o !== main);
  const change = chosen ? <button type="button" className="shrink-0 text-sm text-signal underline" onClick={() => onOpen("fieldwork")}>Změnit ve Sběru dat</button> : null;
  return (
    <>
      {main ? (
        <div className="flex items-start gap-2 text-sm">
          <SourceRow source={main} />
          {change}
        </div>
      ) : (
        <div className="flex items-start gap-2 text-sm">
          <p className="min-w-0 flex-1 text-ink-muted">Server výchozí zdroj respondentů neoznačil: neznámý.</p>
          {change}
        </div>
      )}
      {rest.length ? (
        <details className="text-sm">
          <summary className={`cursor-pointer text-ink-muted ${TOUCH}`}>Další zdroje ({rest.length})</summary>
          <ul className="mt-2 flex flex-col gap-2" aria-label="Další zdroje respondentů">
            {rest.map((o) => <li key={o.source} className="flex"><SourceRow source={o} /></li>)}
          </ul>
        </details>
      ) : null}
    </>
  );
}

function SourceRow({ source: o }: { source: PersonaSourceOption }) {
  return (
    <span className={`flex min-w-0 flex-1 items-start gap-2 ${o.offered ? "" : "text-ink-muted"}`} data-aia={sampleAia.respondents(o.source) ?? undefined}>
      <span className="mt-1"><Glyph tone={o.offered ? (o.default ? "done" : "ready") : "inert"} size={12} title={o.offered ? "nabízeno" : "nenabízeno"} /></span>
      <span className="flex min-w-0 flex-col">
        <span>
          <span className="font-semibold">{t(`${R}.${o.source}`)}</span>
          {o.default ? <span className="text-ink-muted"> · {t(`${R}.default`)}</span> : null}
          {o.offered ? null : <span> · nenabízeno</span>}
        </span>
        <span className="text-xs text-ink-muted">{o.offered ? t(`${R}.${o.source}Help`) : <CodedWords inline coded={codeWords(`${R}.reason`, o.reason ?? "")} />}</span>
      </span>
    </span>
  );
}
