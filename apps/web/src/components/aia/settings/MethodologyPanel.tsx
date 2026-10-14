"use client";

// The Metodika tab: AIA's mathematics as it runs (ADR 0023, GET /api/v1/methodology). Each
// method module's steps in computation order -- for the Sociomap, the audit's F1-F16 -- with
// the formula as MathML, its symbols, every value it reads and where that value comes from
// (the methodology in force, or a constant in code), the evidence behind it and the tests
// that hold it. Values are read from the code by the API; nothing is copied into the page.
// An editable module also shows its versions and, for an administrator, the editor
// (MethodologyVersions.tsx).

import { useCallback, useState } from "react";

import { t } from "@/i18n/t";
import { type MethodFormula, type MethodModuleDetail, type MethodModuleSummary, type MethodStepOut, methodology } from "@/lib/api";
import { groupSteps, showValue } from "@/lib/methodology";
import { Button, Tag, TextInput } from "../../rehome/ui";
import { InlineConfirm } from "../../rehome/step";
import { Loaded } from "../states";
import { useResource } from "../useResource";
import { Formula } from "./MethodologyFormula";
import { MethodologyVersions, type People } from "./MethodologyVersions";

const M = "aia.settings.methodology";
const WORDS = { absent: t(`${M}.absent`), none: t(`${M}.none`), yes: t(`${M}.yes`), no: t(`${M}.no`) };

async function loadList(): Promise<MethodModuleSummary[]> {
  const body: unknown = await methodology.list();
  // A body that is not a list is not "no methodology": say so rather than draw an empty tab.
  if (!Array.isArray(body)) throw new Error(t(`${M}.malformed`));
  return body as MethodModuleSummary[];
}

const anyone: People = (id) => id ?? "—";
const PURPOSE_GROUPS = [
  { title: "Mapy objektů", ids: ["sociomap", "sociomap_reference", "sociomapping"] },
  { title: "Čísla ve výsledcích", ids: ["aggregation", "support"] },
  { title: "Respondenti a váhy", ids: ["response", "weighting"] },
] as const;

export function MethodologyPanel({ people = anyone }: { people?: People }) {
  const [res, retry] = useResource(loadList, []);
  return <Loaded res={res} retry={retry}>{(modules) => <Modules modules={modules} people={people} />}</Loaded>;
}

function Modules({ modules, people }: { modules: MethodModuleSummary[]; people: People }) {
  const [active, setActive] = useState(modules[0]?.id ?? null);
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  // The methodologists open on the editor of the area they last worked on; the chooser is a step away.
  const [chooserOpen, setChooserOpen] = useState(false);
  // Only unsaved changes make switching areas a decision; an open, untouched editor does not.
  const onDirty = useCallback((value: boolean) => setEditing(value), []);
  // Which area's editor is open: there the editor speaks for itself.
  const [openFor, setOpenFor] = useState<string | null>(null);
  const current = modules.find((m) => m.id === active) ?? null;
  const visible = modules.filter((m) => `${m.title_cs} ${m.note_cs}`.toLocaleLowerCase("cs").includes(query.trim().toLocaleLowerCase("cs")));
  const groups: { title: string; modules: MethodModuleSummary[] }[] = PURPOSE_GROUPS.map((group) => ({ title: group.title, modules: group.ids.map((id) => visible.find((module) => module.id === id)).filter((module): module is MethodModuleSummary => module !== undefined) }));
  const additional = visible.filter((module) => !PURPOSE_GROUPS.some((group) => (group.ids as readonly string[]).includes(module.id)));
  if (additional.length) groups.push({ title: "Další výpočty", modules: additional });
  return <div className="flex min-w-0 flex-col gap-4">
    {current ? (
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="text-xl font-semibold leading-7">{current.title_cs}</h3>
        <Button small variant="quiet" aria-expanded={chooserOpen} aria-controls="methodology-module-chooser" onClick={() => setChooserOpen((value) => !value)}>{chooserOpen ? "Skrýt výběr" : "Změnit oblast"}</Button>
        {/* A read-only area says why and what it is; an editable one lets the editor speak. */}
        {openFor === current.id ? null : <p className="basis-full max-w-3xl text-sm leading-6 text-ink-muted">{current.editable ? t(`${M}.editableModule`) : `${t(`${M}.readOnlyModule`)}${current.note_cs ? ` ${current.note_cs}` : ""}`}</p>}
      </header>
    ) : <Button className="self-start" aria-expanded={chooserOpen} aria-controls="methodology-module-chooser" onClick={() => setChooserOpen((value) => !value)}>Změnit oblast</Button>}
    {chooserOpen ? <div id="methodology-module-chooser" className="flex flex-col gap-3">
      <TextInput type="search" aria-label={t(`${M}.search`)} placeholder={t(`${M}.searchPlaceholder`)} value={query} onChange={(e) => setQuery(e.target.value)} />
      <nav aria-label={t(`${M}.modules`)} className="grid min-w-0 gap-3 md:grid-cols-2">
        {groups.filter((group) => group.modules.length).map((group) => <div key={group.title} role="group" aria-label={group.title} className="rounded-md border border-border bg-surface-raised p-3">
          <h3 className="mb-2 font-mono text-xs font-semibold uppercase tracking-wide text-ink-muted">{group.title}</h3>
          <div className="flex flex-col gap-2">{group.modules.map((m) => <button key={m.id} type="button" aria-label={m.title_cs} aria-pressed={m.id === active} onClick={() => {
            if (m.id === active) { setChooserOpen(false); return; }
            if (editing) setPending(m.id); else { setActive(m.id); setChooserOpen(false); }
          }} className={`min-h-11 w-full rounded-md border p-3 text-left text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${m.id === active ? "border-signal-edge bg-signal-wash" : "border-border bg-surface hover:border-border-strong"}`}>
            <span className="flex flex-wrap items-center justify-between gap-2"><strong>{m.title_cs}</strong><Tag>{m.editable ? "Upravitelné" : "Jen ke čtení"}</Tag></span>
            {m.note_cs ? <span className="mt-1 block line-clamp-2 text-xs leading-5 text-ink-muted">{m.note_cs}</span> : null}
          </button>)}</div>
        </div>)}
      </nav>
    </div> : null}
    {!visible.length ? <p role="status" className="text-sm text-ink-muted">{t(`${M}.noMatch`)}</p> : null}
    {pending ? <InlineConfirm message={t(`${M}.leaveEditor`)} action={t(`${M}.discardEditor`)} onCancel={() => { setPending(null); setChooserOpen(false); }} onConfirm={() => { setActive(pending); setPending(null); setEditing(false); setChooserOpen(false); }} /> : null}
    {current ? <ModuleView key={current.id} summary={current} people={people} onDirty={onDirty} onOpen={(open) => setOpenFor(open ? current.id : null)} /> : null}
  </div>;
}

function ModuleView({ summary, people, onDirty, onOpen }: { summary: MethodModuleSummary; people: People; onDirty: (value: boolean) => void; onOpen: (open: boolean) => void }) {
  const [preset, setPreset] = useState(summary.in_force ?? undefined);
  const [editing, setEditing] = useState(false);
  const [res, retry] = useResource(() => methodology.get(summary.id, preset), [summary.id, preset]);
  return <div className="flex min-w-0 flex-col gap-4">
    {summary.editable ? <MethodologyVersions summary={summary} people={people} onEditing={(open) => { setEditing(open); onOpen(open); }} onDirty={onDirty} /> : null}
    <div hidden={editing} className="flex min-w-0 flex-col gap-4">
      <div className="rounded-md border border-border p-3">
        <p className="text-sm font-semibold">{t(`${M}.catalogueTitle`)}</p>
        <p className="mt-1 text-xs leading-5 text-ink-muted">{t(`${M}.catalogueHelp`)}</p>
        {summary.presets.length > 1 ? <div role="radiogroup" aria-label={t(`${M}.preset`)} className="mt-3 flex flex-wrap gap-2">
          {summary.presets.map((p) => <button key={p} type="button" role="radio" aria-checked={p === preset} onClick={() => setPreset(p)} className={`rounded-sm border px-3 py-2 font-mono text-xs focus-visible:outline-2 focus-visible:outline-focus-ring ${p === preset ? "border-signal-edge bg-signal-wash text-signal" : "border-border text-ink-muted"}`}>
            {p}{p === summary.in_force ? ` · ${t(`${M}.codeDefault`)}` : ""}
          </button>)}
        </div> : null}
      </div>
      <Loaded res={res} retry={retry}>{(detail) => <Steps key={detail.preset ?? detail.id} detail={detail} />}</Loaded>
    </div>
  </div>;
}

function Steps({ detail }: { detail: MethodModuleDetail }) {
  const groups = groupSteps(detail);
  const [query, setQuery] = useState("");
  const shown = groups.map((item) => ({ ...item, steps: item.steps.filter((step) => `${step.title_cs} ${step.note_cs} ${step.values.map((v) => `${v.label_cs} ${v.reference} ${String(v.value)}`).join(" ")} ${step.formulas.map((f) => `${f.title_cs} ${f.note_cs}`).join(" ")}`.toLocaleLowerCase("cs").includes(query.trim().toLocaleLowerCase("cs"))) }));
  return <div className="flex min-w-0 flex-col gap-3">
    <TextInput type="search" aria-label={t(`${M}.findStep`)} placeholder={t(`${M}.findStepPlaceholder`)} value={query} onChange={(e) => setQuery(e.target.value)} />
    {shown.map(({ group, steps }, i) => {
      const original = groups[i];
      if (query.trim() && !steps.length && original.steps.length) return null;
      return <section key={group?.id ?? "all"} aria-labelledby={group ? `mg-${detail.id}-${group.id}` : undefined}>
        <details open={!!query.trim() || (i === 1 || groups.length === 1)} className="group rounded-md border border-border bg-surface-raised">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 p-4">
            <div className="min-w-0"><h3 id={group ? `mg-${detail.id}-${group.id}` : undefined} className="text-sm font-semibold">{group?.title_cs ?? t(`${M}.calculation`)}</h3>
            {group?.note_cs ? <p className="mt-1 text-xs leading-5 text-ink-muted">{group.note_cs}</p> : null}</div>
            <span className="shrink-0 text-xs text-ink-muted">{steps.length} {t(`${M}.steps`)} <span aria-hidden="true">⌄</span></span>
          </summary>
          <div className="flex min-w-0 flex-col gap-3 border-t border-border p-3">
            {steps.length ? steps.map((step) => <StepCard key={step.id} step={step} editable={detail.editable} />) : <p className="text-sm text-ink-muted">{t(`${M}.noSteps`)}</p>}
          </div>
        </details>
      </section>;
    })}
    {query.trim() && !shown.some((g) => g.steps.length) ? <p role="status" className="text-sm text-ink-muted">{t(`${M}.noMatch`)}</p> : null}
  </div>;
}

function StepCard({ step, editable }: { step: MethodStepOut; editable: boolean }) {
  return (
    <article aria-labelledby={`ms-${step.id}`} className="flex min-w-0 flex-col gap-3 rounded-md border border-border bg-surface-raised p-4">
      <h4 id={`ms-${step.id}`} className="text-sm font-semibold">{step.title_cs}</h4>
      <div className="text-ink"><Formula latex={step.formula_latex} /></div>
      {step.note_cs ? <p className="max-w-3xl text-sm text-ink-muted">{step.note_cs}</p> : null}
      {step.symbols.length ? (
        <dl aria-label={t(`${M}.symbols`)} className="grid grid-cols-[minmax(0,6rem)_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
          {step.symbols.map((y) => (
            <div key={y.latex} className="contents">
              <dt><Formula latex={y.latex} display={false} /></dt>
              <dd className="text-ink-muted">{y.meaning_cs}{y.unit ? ` [${y.unit}]` : ""}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {step.values.length ? (
        <table className="w-full table-fixed text-sm">
          <caption className="sr-only">{t(`${M}.values`)}</caption>
          <tbody>
            {step.values.map((v) => (
              <tr key={v.reference} className="border-t border-border">
                <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                  {v.label_cs}
                  <details className="mt-1 text-xs text-ink-faint"><summary className="cursor-pointer">{t(`${M}.fieldReference`)}</summary><code className="break-all">{v.reference}</code></details>
                </th>
                <td className="break-words py-1.5 pr-3 font-mono tabular-nums">{showValue(v, WORDS)}{v.unit && !v.absent && v.value !== null ? ` ${v.unit}` : ""}</td>
                <td className="py-1.5 text-right" title={t(`${M}.originHelp.${v.origin}`)}><Tag>{t(`${M}.origin.${v.origin}`)}</Tag></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {step.formulas.map((f) => <EditableFormula key={f.slot_id} formula={f} editable={editable} />)}
      {step.evidence.length ? (
        <ul aria-label={t(`${M}.evidence`)} className="flex flex-col gap-1 text-sm">
          {step.evidence.map((e) => (
            <li key={`${e.kind}:${e.ref}`} className="flex flex-wrap items-baseline gap-2">
              <Tag>{t(`${M}.evidenceKind.${e.kind}`)}</Tag>
              <span className="min-w-0 break-all font-mono text-xs">{e.ref}</span>
              {e.note_cs ? <span className="text-ink-muted">{e.note_cs}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      <details className="text-xs text-ink-muted">
        <summary className="cursor-pointer">{t(`${M}.implements`)}: <span className="break-all font-mono">{step.implements}</span></summary>
        <p className="mt-1">{t(`${M}.pin`)}: <span className="font-mono">{step.source_sha256.slice(0, 16)}…</span></p>
        {step.tests.length ? (
          <>
            <p className="mt-2">{t(`${M}.tests`)}:</p>
            <ul className="mt-1 flex flex-col gap-0.5 font-mono">
              {step.tests.map((test) => <li key={test} className="break-all">{test}</li>)}
            </ul>
          </>
        ) : null}
      </details>
    </article>
  );
}

/** A step's formula as the expression the engine evaluates, drawn from that expression. Its
 *  help says it can be replaced only where the module has a version editor. */
function EditableFormula({ formula, editable }: { formula: MethodFormula; editable: boolean }) {
  return (
    <details aria-label={`${t(`${M}.editable`)}: ${formula.title_cs}`} data-slot={formula.slot_id} className="rounded-sm border border-border p-3">
      <summary className="cursor-pointer text-xs font-semibold text-ink-muted">{t(`${M}.editable`)} · {formula.title_cs}</summary><div className="mt-3 flex min-w-0 flex-col gap-2">
      <p className="text-xs text-ink-muted">{t(editable ? `${M}.editableHelp` : `${M}.editableHelpLater`)}</p>
      <div className="text-ink"><Formula latex={formula.latex} /></div>
      <p className="text-sm">
        <span className="text-xs text-ink-muted">{t(`${M}.expression`)}: </span>
        <code className="whitespace-pre-wrap break-all font-mono text-xs">{formula.expression}</code>
      </p>
      {formula.note_cs ? <p className="text-xs text-ink-muted">{formula.note_cs}</p> : null}
      <dl aria-label={t(`${M}.variables`)} className="grid grid-cols-[minmax(0,3rem)_minmax(0,4rem)_minmax(0,1fr)] gap-x-3 gap-y-1 text-xs">
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
    </div></details>
  );
}
