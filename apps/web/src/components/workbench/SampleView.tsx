"use client";

// Vzorek (plan research-lead-workbench D2): the prototype's sample stage as a read-only view over
// what AIA keeps elsewhere. The sample size and the dimensions are Dimenze's, the audience is Cílová
// skupina's, and whether n is enough is decided on Kontrola by the server's support forecast. So
// this view edits nothing and decides nothing: it shows what is set and links to where it is set.

import { audienceReady } from "@/research/audience";
import { PERSONA_DIM_LABELS, chosenDimensions, recommendedSample } from "@/research/persona";
import type { ResearchProject } from "@/research/model";
import { Glyph } from "./Glyph";

export function SampleView({ project, onOpen }: { project: ResearchProject; onOpen: (stage: "dimensions" | "audience" | "fieldwork") => void }) {
  const n = Number(project.n) || 0;
  const dims = chosenDimensions(project);
  const rec = recommendedSample(project);
  const audience = project.audience ?? {};
  const description = typeof audience.description === "string" ? audience.description : "";
  const filters = audience.filters && typeof audience.filters === "object" ? Object.keys(audience.filters).length : 0;
  return (
    <section className="flex max-w-3xl flex-col gap-4" aria-label="Vzorek" data-sample-view>
      <p className="text-sm text-ink-muted">Přehled vzorku jen ke čtení. Velikost a dimenze se nastavují v Dimenzích, cílová skupina ve svém kroku; zda vzorek stačí, ověří Kontrola a spuštění na serveru.</p>
      <div className="rounded-card border border-border bg-surface-raised p-4">
        <div className="flex items-center gap-2"><Glyph tone={n ? "done" : "inert"} size={12} /><h2 className="text-base font-semibold">Velikost vzorku</h2></div>
        <p className="mt-1 text-2xl font-semibold tabular-nums">{n ? `N = ${n}` : "Nenastaveno"}</p>
        <p className="text-sm text-ink-muted">Doporučeno {rec.n}: {rec.why}</p>
        <button type="button" className="mt-2 text-sm text-signal underline" onClick={() => onOpen("dimensions")}>Upravit v Dimenzích</button>
      </div>
      <div className="rounded-card border border-border bg-surface-raised p-4">
        <div className="flex items-center gap-2"><Glyph tone={audienceReady(project) ? "done" : "inert"} size={12} /><h2 className="text-base font-semibold">Cílová skupina</h2></div>
        <p className="mt-1 text-sm">{description || "Bez popisu"}{filters ? ` · ${filters} ${filters === 1 ? "filtr" : filters < 5 ? "filtry" : "filtrů"}` : ""}</p>
        <button type="button" className="mt-2 text-sm text-signal underline" onClick={() => onOpen("audience")}>Upravit cílovou skupinu</button>
      </div>
      <div className="rounded-card border border-border bg-surface-raised p-4">
        <div className="flex items-center gap-2"><Glyph tone={dims.length ? "done" : "inert"} size={12} /><h2 className="text-base font-semibold">Dimenze</h2></div>
        {dims.length ? <ul className="mt-1 flex flex-wrap gap-1.5">{dims.map((d) => <li key={d} className="rounded-sm border border-border px-2 py-0.5 text-sm">{PERSONA_DIM_LABELS[d] ?? d}</li>)}</ul> : <p className="mt-1 text-sm text-ink-muted">Žádné</p>}
      </div>
      <button type="button" className="self-start rounded-control border border-border-strong px-3 py-1.5 text-sm font-medium" onClick={() => onOpen("fieldwork")}>Ověřit v Kontrole a spuštění</button>
    </section>
  );
}
