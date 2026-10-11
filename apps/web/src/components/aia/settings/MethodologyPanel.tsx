"use client";

// The Metodika tab: AIA's mathematics as it runs (ADR 0023, GET /api/v1/methodology). Each
// method module's steps in computation order -- for the Sociomap, the audit's F1-F16 -- with
// the formula as MathML, its symbols, every value it reads and where that value comes from
// (the methodology in force, or a constant in code), the evidence behind it and the tests
// that hold it. Values are read from the code by the API; nothing is copied into the page.
// Read-only: stored methodology versions, and with them editing, are a later chunk.

import { useState } from "react";

// Temml's layout rules (display math in Firefox and Safari, enclosures, primes) and the
// system math font stack: Cambria Math on Windows, STIX Two Math on macOS.
import "temml/dist/Temml-Local.css";

import { t } from "@/i18n/t";
import { type MethodFormula, type MethodModuleDetail, type MethodModuleSummary, type MethodStepOut, methodology } from "@/lib/api";
import { formulaMathML, groupSteps, showValue } from "@/lib/methodology";
import { Tag } from "../../rehome/ui";
import { Loaded } from "../states";
import { useResource } from "../useResource";

const M = "aia.settings.methodology";
const WORDS = { absent: t(`${M}.absent`), none: t(`${M}.none`), yes: t(`${M}.yes`), no: t(`${M}.no`) };

async function loadList(): Promise<MethodModuleSummary[]> {
  const body: unknown = await methodology.list();
  // A body that is not a list is not "no methodology": say so rather than draw an empty tab.
  if (!Array.isArray(body)) throw new Error(t(`${M}.malformed`));
  return body as MethodModuleSummary[];
}

export function MethodologyPanel() {
  const [res, retry] = useResource(loadList, []);
  return <Loaded res={res} retry={retry}>{(modules) => <Modules modules={modules} />}</Loaded>;
}

function Modules({ modules }: { modules: MethodModuleSummary[] }) {
  const [active, setActive] = useState(modules[0]?.id ?? null);
  const current = modules.find((m) => m.id === active) ?? null;
  return (
    <div className="flex flex-col gap-4">
      <nav aria-label={t(`${M}.modules`)} className="flex flex-wrap gap-2">
        {modules.map((m) => (
          <button
            key={m.id}
            type="button"
            aria-pressed={m.id === active}
            onClick={() => setActive(m.id)}
            className={`rounded-sm border px-3 py-1.5 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${m.id === active ? "border-border-strong bg-surface-raised font-semibold text-ink" : "border-border text-ink-muted hover:text-ink"}`}
          >
            {m.title_cs}
          </button>
        ))}
      </nav>
      {current ? <ModuleView key={current.id} summary={current} /> : null}
    </div>
  );
}

function ModuleView({ summary }: { summary: MethodModuleSummary }) {
  const [preset, setPreset] = useState(summary.in_force ?? undefined);
  const [res, retry] = useResource(() => methodology.get(summary.id, preset), [summary.id, preset]);
  return (
    <div className="flex flex-col gap-4">
      {summary.note_cs ? <p className="max-w-3xl text-sm text-ink-muted">{summary.note_cs}</p> : null}
      {summary.presets.length > 1 ? (
        <div role="radiogroup" aria-label={t(`${M}.preset`)} className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-xs font-medium text-ink-muted">{t(`${M}.preset`)}</span>
          {summary.presets.map((p) => (
            <button
              key={p}
              type="button"
              role="radio"
              aria-checked={p === preset}
              onClick={() => setPreset(p)}
              className={`rounded-sm border px-2 py-1 font-mono text-xs ${p === preset ? "border-border-strong bg-surface-raised text-ink" : "border-border text-ink-muted hover:text-ink"}`}
            >
              {p}
              {p === summary.in_force ? ` · ${t(`${M}.inForce`)}` : ""}
            </button>
          ))}
        </div>
      ) : null}
      <Loaded res={res} retry={retry}>{(detail) => <Steps detail={detail} />}</Loaded>
    </div>
  );
}

function Steps({ detail }: { detail: MethodModuleDetail }) {
  return (
    <div className="flex flex-col gap-6">
      {groupSteps(detail).map(({ group, steps }) => (
        <section key={group?.id ?? "all"} aria-labelledby={group ? `mg-${detail.id}-${group.id}` : undefined} className="flex flex-col gap-3">
          {group ? (
            <header className="border-b border-border pb-1">
              <h3 id={`mg-${detail.id}-${group.id}`} className="text-sm font-semibold">{group.title_cs}</h3>
              {group.note_cs ? <p className="mt-1 max-w-3xl text-sm text-ink-muted">{group.note_cs}</p> : null}
            </header>
          ) : null}
          {steps.length ? steps.map((s) => <StepCard key={s.id} step={s} />) : <p className="text-sm text-ink-muted">{t(`${M}.noSteps`)}</p>}
        </section>
      ))}
    </div>
  );
}

/** A formula as MathML; its LaTeX, said so, when it cannot be drawn. */
export function Formula({ latex, display = true }: { latex: string; display?: boolean }) {
  const mathml = formulaMathML(latex, display);
  if (mathml === null) {
    return (
      <span className="flex flex-col gap-1">
        <code className="font-mono text-xs">{latex}</code>
        <span className="text-xs text-status-fault">{t(`${M}.formulaError`)}</span>
      </span>
    );
  }
  // Temml's own output, trust off: built from the catalogue's LaTeX, no link or HTML passes.
  return <span className="overflow-x-auto" dangerouslySetInnerHTML={{ __html: mathml }} />;
}

function StepCard({ step }: { step: MethodStepOut }) {
  return (
    <article aria-labelledby={`ms-${step.id}`} className="flex flex-col gap-3 rounded-md border border-border bg-surface-raised p-4">
      <h4 id={`ms-${step.id}`} className="text-sm font-semibold">{step.title_cs}</h4>
      <div className="text-ink"><Formula latex={step.formula_latex} /></div>
      {step.note_cs ? <p className="max-w-3xl text-sm text-ink-muted">{step.note_cs}</p> : null}
      {step.symbols.length ? (
        <dl aria-label={t(`${M}.symbols`)} className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
          {step.symbols.map((y) => (
            <div key={y.latex} className="contents">
              <dt><Formula latex={y.latex} display={false} /></dt>
              <dd className="text-ink-muted">{y.meaning_cs}{y.unit ? ` [${y.unit}]` : ""}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {step.values.length ? (
        <table className="w-full text-sm">
          <caption className="sr-only">{t(`${M}.values`)}</caption>
          <tbody>
            {step.values.map((v) => (
              <tr key={v.reference} className="border-t border-border">
                <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                  {v.label_cs}
                  <span className="block font-mono text-xs text-ink-faint">{v.reference}</span>
                </th>
                <td className="py-1.5 pr-3 font-mono tabular-nums">{showValue(v, WORDS)}{v.unit && !v.absent && v.value !== null ? ` ${v.unit}` : ""}</td>
                <td className="py-1.5 text-right" title={t(`${M}.originHelp.${v.origin}`)}><Tag>{t(`${M}.origin.${v.origin}`)}</Tag></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {step.formulas.map((f) => <EditableFormula key={f.slot_id} formula={f} />)}
      {step.evidence.length ? (
        <ul aria-label={t(`${M}.evidence`)} className="flex flex-col gap-1 text-sm">
          {step.evidence.map((e) => (
            <li key={`${e.kind}:${e.ref}`} className="flex flex-wrap items-baseline gap-2">
              <Tag>{t(`${M}.evidenceKind.${e.kind}`)}</Tag>
              <span className="font-mono text-xs">{e.ref}</span>
              {e.note_cs ? <span className="text-ink-muted">{e.note_cs}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      <details className="text-xs text-ink-muted">
        <summary className="cursor-pointer">{t(`${M}.implements`)}: <span className="font-mono">{step.implements}</span></summary>
        <p className="mt-1">{t(`${M}.pin`)}: <span className="font-mono">{step.source_sha256.slice(0, 16)}…</span></p>
        {step.tests.length ? (
          <>
            <p className="mt-2">{t(`${M}.tests`)}:</p>
            <ul className="mt-1 flex flex-col gap-0.5 font-mono">
              {step.tests.map((test) => <li key={test}>{test}</li>)}
            </ul>
          </>
        ) : null}
      </details>
    </article>
  );
}

/** A step's formula as the expression the engine evaluates, drawn from that expression. */
function EditableFormula({ formula }: { formula: MethodFormula }) {
  return (
    <section aria-label={`${t(`${M}.editable`)}: ${formula.title_cs}`} data-slot={formula.slot_id} className="flex flex-col gap-2 rounded-sm border border-border p-3">
      <h5 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{t(`${M}.editable`)} · {formula.title_cs}</h5>
      <p className="text-xs text-ink-muted">{t(`${M}.editableHelp`)}</p>
      <div className="text-ink"><Formula latex={formula.latex} /></div>
      <p className="text-sm">
        <span className="text-xs text-ink-muted">{t(`${M}.expression`)}: </span>
        <code className="font-mono text-xs">{formula.expression}</code>
      </p>
      {formula.note_cs ? <p className="text-xs text-ink-muted">{formula.note_cs}</p> : null}
      <dl aria-label={t(`${M}.variables`)} className="grid grid-cols-[max-content_max-content_1fr] gap-x-3 gap-y-1 text-xs">
        {formula.variables.map((v) => (
          <div key={v.name} className="contents">
            <dt className="font-mono">{v.name}</dt>
            <dd><Formula latex={v.latex} display={false} /></dd>
            <dd className="text-ink-muted">{v.meaning_cs}{v.unit ? ` [${v.unit}]` : ""}{v.vector ? ` · ${t(`${M}.vector`)}` : ""}</dd>
          </div>
        ))}
      </dl>
      {formula.properties.length ? (
        <div className="text-xs">
          <p className="text-ink-muted">{t(`${M}.properties`)}:</p>
          <ul className="mt-1 list-disc pl-5">
            {formula.properties.map((p, i) => (
              <li key={`${p.kind}-${i}`}>
                {p.description_cs || t(`${M}.propertyKind.${p.kind}`)}
                {p.variable ? <span className="font-mono"> ({p.variable})</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
