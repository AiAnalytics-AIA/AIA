"use client";

// Vzorek (plan artifact-sample; research-lead-workbench D2): the prototype's sample stage over what
// AIA keeps elsewhere. The sample size and the dimensions are Dimenze's, the audience is Cílová
// skupina's, and the forecast and readiness are the server's, read on the design as it stands. So
// this view edits nothing and decides nothing: it shows what is set, what the server forecasts,
// and links to where each is set.

import type { ReactNode } from "react";

import { t } from "@/i18n/t";
import type { OutlookVerdict } from "@/lib/api";
import { codeWords } from "@/lib/reason-words";
import { VERDICT_ORDER } from "@/lib/research-execution";
import { outlookSummary, personaSourcesOf, supportForecastOf } from "@/lib/sample-view";
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
  const { store, frame } = useResearch();
  const readiness = useSampleReadiness(store, frame.studyId, frame.canEdit);
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
      <p className="text-sm text-ink-muted">Přehled vzorku jen ke čtení. Velikost a dimenze se nastavují v Dimenzích, cílová skupina ve svém kroku; zda vzorek stačí, ověří Kontrola a spuštění na serveru.</p>
      <Sec n={1} title="Velikost a složení" aside={n ? `n ${n}` : undefined} aia="sample:size">
        <div data-aia="sample:n">
          <div className="flex items-center gap-2"><Glyph tone={n ? "done" : "inert"} size={12} /><h3 className="text-sm font-semibold">Velikost vzorku</h3></div>
          <p className="mt-1 text-2xl font-semibold tabular-nums">{n ? `N = ${n}` : "Nenastaveno"}</p>
          <p className="text-sm text-ink-muted">Doporučeno {rec.n}: {rec.why}</p>
          <button type="button" className="mt-1 text-sm text-signal underline" onClick={() => onOpen("dimensions")}>Upravit v Dimenzích</button>
        </div>
        <div>
          <div className="flex items-center gap-2"><Glyph tone={audienceReady(project) ? "done" : "inert"} size={12} /><h3 className="text-sm font-semibold">Cílová skupina</h3></div>
          <p className="mt-1 text-sm">{description || "Bez popisu"}{filters ? ` · ${filters} ${filters === 1 ? "filtr" : filters < 5 ? "filtry" : "filtrů"}` : ""}</p>
          <button type="button" className="mt-1 text-sm text-signal underline" onClick={() => onOpen("audience")}>Upravit cílovou skupinu</button>
        </div>
        <div>
          <div className="flex items-center gap-2"><Glyph tone={dims.length ? "done" : "inert"} size={12} /><h3 className="text-sm font-semibold">Dimenze</h3></div>
          {dims.length ? <ul className="mt-1 flex flex-wrap gap-1.5">{dims.map((d) => <li key={d} className="rounded-sm border border-border px-2 py-0.5 text-sm">{PERSONA_DIM_LABELS[d] ?? d}</li>)}</ul> : <p className="mt-1 text-sm text-ink-muted">Žádné</p>}
        </div>
      </Sec>
      <Sec n={2} title="Odhad podpory před během" aside="odhad, ne výsledek" aia="sample:forecast">
        <Forecast readiness={readiness} />
        <p className="text-sm text-ink-muted">
          Skutečná podpora dvojic se ověří až z výsledných dat (
          <button type="button" className="text-signal underline" onClick={() => onOpen("sociomap")}>Sociomapa</button>
          ). Kvóta ji nezaručuje.
        </p>
      </Sec>
      <Sec n={3} title="Kdo bude odpovídat" aia="sample:respondents">
        <Respondents readiness={readiness} onOpen={onOpen} />
      </Sec>
      <button type="button" className="self-start rounded-control border border-border-strong px-3 py-1.5 text-sm font-medium" onClick={() => onOpen("fieldwork")}>Ověřit v Kontrole a spuštění</button>
    </div>
  );
}

function Forecast({ readiness }: { readiness: SampleReadiness }) {
  if (readiness.kind === "loading") return <p className="text-sm text-ink-muted" role="status">Načítám odhad ze serveru…</p>;
  if (readiness.kind === "failed") return <p className="text-sm text-status-fault" role="alert">Odhad se nepodařilo načíst: {readiness.message}</p>;
  if (readiness.kind === "none") return <p className="text-sm text-ink-muted">Návrh zatím nikdo neodeslal ke kontrole, takže odhad není. Odhad je neznámý.</p>;
  const support = supportForecastOf(readiness.readiness);
  const outlook = outlookSummary(readiness.readiness);
  return (
    <>
      <p className="text-xs text-ink-muted">Podle revize návrhu {readiness.revision}</p>
      <div className="flex items-start gap-2" data-aia="sample:forecast:support">
        <span className="mt-1"><Glyph tone={support.known ? (STATUS_TONE[support.status] ?? "inert") : "inert"} size={12} title={support.known ? support.status : "neznámé"} /></span>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">Opora výsledků{support.known ? "" : ": neznámé"}</h3>
          <p className="text-sm">{support.message ?? "Server oporu pro tento běh předem nespočítal."}</p>
        </div>
      </div>
      <div className="flex items-start gap-2" data-aia="sample:forecast:outlook">
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
  return (
    <>
      {readiness.kind === "loading" ? <p className="text-sm text-ink-muted" role="status">Načítám nabídku ze serveru…</p>
        : readiness.kind === "failed" ? <p className="text-sm text-status-fault">Nabídku se nepodařilo načíst.</p>
        : !sources ? <p className="text-sm text-ink-muted">Server zdroje respondentů nevrátil: neznámé.</p>
        : (
          <ul className="flex flex-col gap-2" aria-label="Zdroje respondentů">
            {sources.map((o) => (
              <li key={o.source} className={`flex items-start gap-2 text-sm ${o.offered ? "" : "text-ink-muted"}`} data-aia={`sample:respondents:${o.source}`}>
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
      <p className="text-sm text-ink-muted">
        Zdroj se volí ve Spuštění, u startu běhu, který ho zapíše.{" "}
        <button type="button" className="text-signal underline" onClick={() => onOpen("fieldwork")}>Změnit ve Spuštění</button>
      </p>
    </>
  );
}
