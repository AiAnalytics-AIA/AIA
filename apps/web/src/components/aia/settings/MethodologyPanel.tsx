"use client";

// The Metodika tab: AIA's mathematics as it runs (ADR 0023, GET /api/v1/methodology). Each
// method module's steps in computation order -- for the Sociomap, the audit's F1-F16 -- with
// the formula as MathML, its symbols, every value it reads and where that value comes from
// (the methodology in force, or a constant in code), the evidence behind it and the tests
// that hold it. Values are read from the code by the API; nothing is copied into the page.
// An editable module also shows its versions and, for an administrator, the editor
// (MethodologyVersions.tsx).

import { useCallback, useEffect, useState } from "react";

import { t, tv } from "@/i18n/t";
import { type MethodFormula, type MethodModuleDetail, type MethodModuleSummary, type MethodStepOut, type MethodVersions, methodology } from "@/lib/api";
import { type GroupedSteps, groupSteps, isParameter, methodologyCount, showValue, stageNumbers, stepNumbers, stepOrigin } from "@/lib/methodology";
import { Tag } from "../../rehome/ui";
import { ChoiceChips } from "../../ui/ChoiceChips";
import { InlineConfirm } from "../../rehome/step";
import { Loaded } from "../states";
import { type Resource, useResource } from "../useResource";
import { FieldOriginPanel } from "./FieldOriginPanel";
import { Formula } from "./MethodologyFormula";
import { StepContext } from "./MethodologyContext";
import { MethodologyVersions, type People } from "./MethodologyVersions";
import { ModuleArt, accentOf } from "./MethodologyArt";

const M = "aia.settings.methodology";
const WORDS = { absent: t(`${M}.absent`), none: t(`${M}.none`), yes: t(`${M}.yes`), no: t(`${M}.no`) };

async function loadList(): Promise<MethodModuleSummary[]> {
  const body: unknown = await methodology.list();
  // A body that is not a list is not "no methodology": say so rather than draw an empty tab.
  if (!Array.isArray(body)) throw new Error(t(`${M}.malformed`));
  return body as MethodModuleSummary[];
}

const anyone: People = (id) => id ?? "—";
/** A read-only area the panel adds itself: the population's field policy has no formulas or
 *  versions to show, so it is not a method module (methodology-tab V1c). */
type Area = Pick<MethodModuleSummary, "id" | "title_cs" | "note_cs" | "editable">;
const FIELD_ORIGIN: Area = {
  id: "field_origin",
  title_cs: "Původ polí: k čemu smí sloužit",
  note_cs: "Co rozhoduje, k čemu smí posloužit každé pole populace: jeho původ, věta o použití ve slovníku a kvalita.",
  editable: false,
};
/** The order the cards stand in: the map first (full width), then before a run, the numbers, the
 *  respondents, the population. No categories (the product owner, 2026-10-21: too few to filter). */
const ORDER = ["sociomap", "readiness", "support", "aggregation", "response", "weighting", "field_origin"];
/**
 * What the MVP does not list (D-13): the experimental Sociomapping (H-Model) and the 18.6.6
 * reference map are hidden; their pages stay readable by URL nowhere here, and the API still
 * serves them for the record.
 */
const HIDDEN_MODULES = new Set(["sociomap_reference", "sociomapping"]);
/** D-13: the MVP ships aia-sociomap-5 only. Earlier presets are not offered, unless one is in force. */
function presetsShown(summary: Pick<MethodModuleSummary, "id" | "presets" | "in_force">): string[] {
  if (summary.id !== "sociomap") return summary.presets;
  const base = (p: string) => p.split("+")[0];
  return summary.presets.filter((p) => base(p) === "aia-sociomap-5" || p === summary.in_force);
}

export function MethodologyPanel({ people = anyone }: { people?: People }) {
  const [res, retry] = useResource(loadList, []);
  return <Loaded res={res} retry={retry}>{(modules) => <Modules modules={modules} people={people} />}</Loaded>;
}

const BACK = "\u0000back";

function Modules({ modules, people }: { modules: MethodModuleSummary[]; people: People }) {
  // The tab opens on the catalogue (prototype v51, fidelity F4); a card opens its module.
  const [active, setActive] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  // Only unsaved changes make leaving a module a decision; an open, untouched editor does not.
  const onDirty = useCallback((value: boolean) => setEditing(value), []);
  const areas: Area[] = [...modules.filter((m) => !HIDDEN_MODULES.has(m.id)), FIELD_ORIGIN];
  const current = areas.find((m) => m.id === active) ?? null;
  const rank = (id: string) => (ORDER.includes(id) ? ORDER.indexOf(id) : ORDER.length);
  const cards = [...areas].sort((a, b) => rank(a.id) - rank(b.id));
  const summaryOf = (id: string) => modules.find((m) => m.id === id);
  const go = (id: string | null) => { if (editing) setPending(id ?? BACK); else setActive(id); };
  const confirm = pending ? <InlineConfirm message={t(`${M}.leaveEditor`)} action={t(`${M}.discardEditor`)} onCancel={() => setPending(null)} onConfirm={() => { setActive(pending === BACK ? null : pending); setPending(null); setEditing(false); }} /> : null;
  if (!current) {
    return <div className="flex min-w-0 flex-col gap-4">
      <p data-mvp-note className="max-w-4xl rounded-md border border-signal-edge bg-signal-tint px-4 py-3 text-sm leading-6">{t(`${M}.mvpNote`)}</p>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="text-base font-semibold">{t(`${M}.catalogue`)}</h2>
        <span className="text-xs text-ink-muted">{tv(`${M}.catalogueCount`, { n: cards.length })}</span>
      </div>
      <nav aria-label={t(`${M}.modules`)} className="grid min-w-0 gap-4 [grid-template-columns:repeat(auto-fill,minmax(min(100%,340px),1fr))]">
        {cards.map((m) => <ModuleCard key={m.id} area={m} summary={summaryOf(m.id)} onOpen={() => go(m.id)} />)}
      </nav>
    </div>;
  }
  const summary = summaryOf(current.id);
  return <div className="flex min-w-0 flex-col gap-4">
    <button type="button" data-methodology-back onClick={() => go(null)} className="inline-flex min-h-8 items-center gap-1.5 self-start rounded-sm px-2 text-sm text-ink-muted hover:bg-surface-sunken hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring">
      <span aria-hidden="true">←</span>{t(`${M}.back`)}
    </button>
    {confirm}
    <ModulePage key={current.id} area={current} summary={summary} people={people} onDirty={onDirty} />
  </div>;
}

/** An open module: its head and its parts, over one read of its versions -- the head's chips and the
 *  versions' tabs read the same answer, and an activation's reload moves both (review of #873). */
function ModulePage({ area, summary, people, onDirty }: { area: Area; summary: MethodModuleSummary | undefined; people: People; onDirty: (value: boolean) => void }) {
  const versions = useModuleFacts(summary);
  return <>
    <header data-module-header className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0 max-w-[720px]">
        <h2 className="font-serif text-xl font-semibold leading-7">{area.title_cs}</h2>
        <p className="mt-1.5 text-sm leading-6 text-ink-muted">{oneLine(area)}</p>
        {/* Who changes it, and for a read-only module the API's own note on what it is. */}
        <p data-module-note className="mt-1 text-xs leading-5 text-ink-faint">{area.editable ? t(`${M}.editableModule`) : `${t(`${M}.readOnlyModule`)}${area.note_cs ? ` ${area.note_cs}` : ""}`}</p>
      </div>
      {summary ? <ModuleChips summary={summary} res={versions.res} /> : null}
    </header>
    {area.id === FIELD_ORIGIN.id ? <FieldOriginPanel /> : null}
    {area.id !== FIELD_ORIGIN.id && summary ? <ModuleView summary={summary} people={people} onDirty={onDirty} onOpen={noop} versions={versions} /> : null}
  </>;
}

const noop = () => {};

/** A module's one line, as the catalogue and the module's head say it; the API's note else. */
function oneLine(area: Area): string {
  const key = `${M}.oneLine.${area.id}`;
  const line = t(key);
  return line === key ? area.note_cs : line;
}

/** What a module's versions say about it: what is in force, the register's word on it, and whether
 *  you may edit it. A read-only module has no versions to read; an unread answer is said, never
 *  presumed (review of #852). */
function useModuleFacts(summary: MethodModuleSummary | undefined): ModuleVersions {
  const editable = summary?.editable ?? false;
  const [res, reload] = useResource(() => (summary && editable ? methodology.versions(summary.id) : Promise.resolve(null)), [summary?.id, editable]);
  return { res, reload, editable };
}
type ModuleVersions = { res: Resource<MethodVersions | null>; reload: () => void; editable: boolean };

const CHIP = "inline-flex min-h-[22px] items-center gap-[5px] whitespace-nowrap rounded-[11px] border px-2 text-xs";

function RegisterChip({ status, head = false }: { status: string | null | undefined; head?: boolean }) {
  if (status === undefined) return <span data-register="loading" className="text-ink-muted">…</span>;
  if (status !== "CLIENT_FACING" && status !== "INTERNAL_ONLY") return <span data-register="unknown" className={`${CHIP} border-border text-ink-muted`}>{t(`${M}.facts.unknown`)}</span>;
  // Approved is a strong-edged chip, never green (green is only what is in force); internal is the fault's.
  return <span data-register={status} className={`${CHIP} ${status === "CLIENT_FACING" ? "border-border-strong text-ink" : "border-status-fault bg-status-fault-wash text-status-fault"}`}>{t(`${M}.register.${head ? `head${status}` : status}`)}</span>;
}

function ModuleChips({ summary, res }: { summary: MethodModuleSummary; res: Resource<MethodVersions | null> }) {
  const editable = summary.editable;
  const name = !editable ? summary.in_force : res.state === "ready" && res.data ? res.data.in_force.name : null;
  return <div data-module-chips className="flex flex-wrap items-center gap-1.5">
    {name ? <span data-in-force-chip className={`${CHIP} border-in-force bg-in-force-wash font-mono font-medium text-ink`}><span aria-hidden="true" className="size-1.5 rounded-full bg-in-force" />{tv(`${M}.inForceChip`, { name })}</span> : null}
    {summary.id === "sociomap" ? <RegisterChip head status={res.state === "ready" ? res.data?.in_force.register_status : res.state === "loading" ? undefined : null} /> : null}
    <span className={`${CHIP} border-border text-ink-muted`}>{tv(`${M}.stepsChip`, { steps: methodologyCount(summary.steps, "step"), groups: methodologyCount(summary.groups.length, "stageIn") })}</span>
  </div>;
}

function ModuleCard({ area, summary, onOpen }: { area: Area; summary: MethodModuleSummary | undefined; onOpen: () => void }) {
  const { res } = useModuleFacts(summary);
  const versions = res.state === "ready" ? res.data : null;
  const unread = res.state !== "loading" && res.state !== "ready";
  const wide = area.id === "sociomap";
  return <button type="button" data-module-card={area.id} aria-label={area.title_cs} onClick={onOpen} style={{ borderTopColor: `var(--${accentOf(area.id)})` }}
    className={`group flex min-w-0 flex-col overflow-hidden rounded-md border border-t-4 border-border bg-surface-raised text-left text-sm transition-transform duration-[var(--duration-confirm)] hover:-translate-y-0.5 hover:border-border-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring motion-reduce:transform-none ${wide ? "col-span-full" : ""}`}>
    <span className={`block ${wide ? "h-28" : "h-24"} border-b border-border bg-surface`}><ModuleArt id={area.id} /></span>
    <span className="flex flex-col gap-1.5 p-4">
      <span className="flex items-baseline justify-between gap-2"><strong className="text-[15px] font-semibold">{area.title_cs}</strong><span aria-hidden="true" style={{ color: `var(--${accentOf(area.id)})` }}>→</span></span>
      <span data-module-line className="block text-[13px] leading-[19px] text-ink-muted">{oneLine(area)}</span>
      <dl data-module-facts className="mt-1.5 grid grid-cols-[110px_1fr] gap-y-1.5 border-t border-border pt-2.5 text-xs">
        {summary ? <>
          <dt className="text-ink-faint">{t(`${M}.facts.inForce`)}</dt><dd className="break-words font-mono"><InForceFact summary={summary} res={res} /></dd>
          {area.id === "sociomap" ? <><dt className="text-ink-faint">{t(`${M}.facts.forClients`)}</dt><dd><RegisterChip status={versions ? versions.in_force.register_status : unread ? null : undefined} /></dd></> : null}
          <dt className="text-ink-faint">{t(`${M}.facts.calculation`)}</dt><dd>{tv(`${M}.facts.steps`, { steps: methodologyCount(summary.steps, "step"), groups: methodologyCount(summary.groups.length, "stage") })}</dd>
        </> : null}
        <dt className="text-ink-faint">{t(`${M}.facts.edits`)}</dt>
        <dd>{!area.editable ? t(`${M}.facts.readOnly`) : versions ? t(`${M}.facts.${versions.may_edit ? "youEdit" : "metodikEdits"}`) : unread ? t(`${M}.facts.unknown`) : "…"}</dd>
      </dl>
    </span>
  </button>;
}

/**
 * What is in force for the organization: an editable module's activation, read from its versions
 * (summary.in_force is only the code's preset); until read, "…", and unread, "nezjištěno". A
 * read-only module has no activations: its code preset, said as such (review of #852).
 */
function InForceFact({ summary, res }: { summary: MethodModuleSummary; res: Resource<MethodVersions | null> }) {
  if (!summary.editable) return <>{summary.in_force ? `${summary.in_force} · ${t(`${M}.codeDefault`)}` : t(`${M}.facts.fromCode`)}</>;
  if (res.state === "loading") return <>…</>;
  if (res.state !== "ready" || !res.data) return <span data-current-unknown>{t(`${M}.facts.unknown`)}</span>;
  const f = res.data.in_force;
  return <span data-current-name>{f.origin === "stored" ? f.name : `${f.name} · ${t(`${M}.codeDefault`)}`}</span>;
}

function ModuleView({ summary, people, onDirty, onOpen, versions }: { summary: MethodModuleSummary; people: People; onDirty: (value: boolean) => void; onOpen: (open: boolean) => void; versions: ModuleVersions }) {
  const [preset, setPreset] = useState(summary.in_force ?? undefined);
  const [res, retry] = useResource(() => methodology.get(summary.id, preset), [summary.id, preset]);
  const calc = <>
    {/* What the steps below document: the code's preset. One preset is said in a line (what is in
        force is in the head's chips); several are a choice, with what choosing does and does not do. */}
    {presetsShown(summary).length === 1 ? <p data-preset className="text-xs text-ink-muted">{tv(`${M}.documents`, { preset: presetsShown(summary)[0] })}</p> : null}
    {presetsShown(summary).length > 1 ? <div className="rounded-md border border-border p-3">
      <p className="text-sm font-semibold">{t(`${M}.catalogueTitle`)}</p>
      <p className="mt-1 text-xs leading-5 text-ink-muted">{t(`${M}.catalogueHelp`)}</p>
      <div role="radiogroup" aria-label={t(`${M}.preset`)} className="mt-3 flex flex-wrap gap-2">
        {presetsShown(summary).map((p) => <button key={p} type="button" role="radio" aria-checked={p === preset} onClick={() => setPreset(p)} className={`rounded-sm border px-3 py-2 font-mono text-xs focus-visible:outline-2 focus-visible:outline-focus-ring ${p === preset ? "border-signal-edge bg-signal-wash text-signal" : "border-border text-ink-muted"}`}>
          {p}{p === summary.in_force ? ` · ${t(`${M}.codeDefault`)}` : ""}
        </button>)}
      </div>
    </div> : null}
    <Loaded res={res} retry={retry}>{(detail) => <Steps key={detail.preset ?? detail.id} detail={detail} />}</Loaded>
  </>;
  // An editable module is its parts as tabs (settings-redesign 10b); a read-only one is its calculation.
  if (summary.editable) return <MethodologyVersions summary={summary} people={people} calc={calc} onEditing={onOpen} onDirty={onDirty} versions={{ res: versions.res as Resource<MethodVersions>, reload: versions.reload }} />;
  return <div className="flex min-w-0 flex-col gap-4">{calc}</div>;
}

/**
 * Výpočet (prototype v51, fidelity F5): the stages as tiles that pick one, a "S parametry" filter,
 * and each stage's steps as rows in the order the computation runs; a row opens on its formula,
 * its values and where they come from. A stage AIA does not compute yet is listed apart, never as a
 * tile with nothing behind it.
 */
function Steps({ detail }: { detail: MethodModuleDetail }) {
  const groups = groupSteps(detail);
  const numbers = stepNumbers(detail.groups);
  const stages = stageNumbers(detail.groups);
  const titles = Object.fromEntries(detail.step_details.map((s) => [s.id, s.title_cs]));
  const live = groups.filter((g) => g.steps.length);
  const notYet = groups.filter((g) => !g.steps.length && g.group);
  const key = (g: GroupedSteps[number]) => g.group?.id ?? "all";
  const [stage, setStage] = useState<string | null>(null);
  const [withValues, setWithValues] = useState(false);
  const [open, setOpen] = useState<ReadonlySet<string>>(() => new Set());
  const [goTo, setGoTo] = useState<string | null>(null);
  // "S parametry": the steps that read a value a version can change, not a code constant or the
  // method's own name.
  const filtered = (g: GroupedSteps[number]) => (withValues ? g.steps.filter((x) => x.values.some(isParameter)) : g.steps);
  const shown = live.filter((g) => stage === null || key(g) === stage).map((g) => ({ ...g, steps: filtered(g) })).filter((g) => g.steps.length);
  const allOpen = shown.length > 0 && shown.every((g) => g.steps.every((x) => open.has(x.id)));
  const toggle = (id: string) => setOpen((o) => { const n = new Set(o); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  // A context link opens the step it names wherever it is, then moves to it once drawn.
  const pick = (id: string) => { setStage(null); setWithValues(false); setOpen((o) => new Set(o).add(id)); setGoTo(id); };
  useEffect(() => {
    if (!goTo) return;
    const heading = document.getElementById(`ms-${goTo}`);
    heading?.scrollIntoView({ block: "start" });
    // The focus follows the move: the next Tab starts from the step the link named.
    heading?.querySelector<HTMLElement>("button[aria-expanded]")?.focus({ preventScroll: true });
    // eslint-disable-next-line react-hooks/set-state-in-effect -- a one-shot move, cleared once made
    setGoTo(null);
  }, [goTo]);
  const tile = (id: string | null, label: string, count: number) => {
    const on = stage === id;
    return <button key={id ?? "all"} type="button" data-stage-tile={id ?? "all"} aria-pressed={on} onClick={() => setStage(id)}
      className={`flex min-h-11 flex-col items-start rounded-md border px-3 py-2 text-left text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${on ? "border-signal bg-signal-wash" : "border-border bg-surface-raised hover:border-border-strong"}`}>
      <span className="font-medium">{label}</span><span className="text-xs text-ink-muted">{methodologyCount(count, "step")}</span>
    </button>;
  };
  return <div className="flex min-w-0 flex-col gap-3">
    <section aria-labelledby={`mstages-${detail.id}`} className="rounded-md border border-border bg-surface-raised px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={`mstages-${detail.id}`} className="text-sm font-semibold">{t(`${M}.stages`)}</h3>
        <button type="button" data-dense onClick={() => setOpen(allOpen ? new Set() : new Set(shown.flatMap((g) => g.steps.map((x) => x.id))))}
          className="min-h-8 rounded-sm px-2 text-sm text-ink-muted hover:bg-surface-sunken hover:text-ink focus-visible:outline-2 focus-visible:outline-focus-ring">{t(`${M}.${allOpen ? "collapseAll" : "expandAll"}`)}</button>
      </div>
      <div role="group" aria-label={t(`${M}.stagesGroup`)} className="mt-2.5 grid gap-2 [grid-template-columns:repeat(auto-fill,minmax(130px,1fr))]">
        {tile(null, t(`${M}.allStages`), live.reduce((n, g) => n + g.steps.length, 0))}
        {live.map((g) => tile(key(g), g.group ? `${stages.get(g.group.id) ? `M${stages.get(g.group.id)} · ` : ""}${g.group.title_cs}` : t(`${M}.calculation`), g.steps.length))}
      </div>
      <div className="mt-2.5 flex flex-wrap items-center gap-2 text-xs text-ink-muted">
        <span aria-hidden="true">{t(`${M}.onlySteps`)}</span>
        <ChoiceChips look="segmented" small label={t(`${M}.onlySteps`)} value={withValues ? "values" : "all"} options={[{ key: "all", label: t(`${M}.allSteps`) }, { key: "values", label: t(`${M}.withValues`) }]} onChange={(k) => setWithValues(k === "values")} />
        <span>{t(`${M}.stepsHelp`)}</span>
      </div>
    </section>
    {shown.map((g) => (
      <section key={key(g)} aria-labelledby={g.group ? `mg-${detail.id}-${g.group.id}` : undefined} className="rounded-md border border-border bg-surface-raised px-5 py-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border pb-2">
          <div className="flex items-center gap-2.5">
            {g.group && stages.get(g.group.id) ? <span data-stage-number className="inline-flex min-h-[22px] items-center rounded-[11px] border border-border px-2 font-mono text-xs text-ink-muted">M{stages.get(g.group.id)}</span> : null}
            <h3 id={g.group ? `mg-${detail.id}-${g.group.id}` : undefined} className="text-sm font-semibold">{g.group?.title_cs ?? t(`${M}.calculation`)}</h3>
          </div>
          <span className="text-xs text-ink-muted">{methodologyCount(g.steps.length, "step")}</span>
        </div>
        {g.group?.note_cs ? <p className="mt-2 break-words text-xs leading-5 text-ink-muted">{g.group.note_cs}</p> : null}
        {g.steps.map((step) => <StepRow key={step.id} step={step} number={numbers.get(step.id)} editable={detail.editable} titles={titles} open={open.has(step.id)} onToggle={() => toggle(step.id)} onPick={pick} />)}
      </section>
    ))}
    {withValues && !shown.length ? <p role="status" className="text-sm text-ink-muted">{t(`${M}.noValues`)}</p> : null}
    {notYet.length ? <section data-not-computed className="rounded-md border border-dashed border-border-strong px-5 py-4">
      <p className="text-sm font-semibold">{t(`${M}.notYet`)}</p>
      {/* One line each; the whole note on hover and to a screen reader. */}
      {notYet.map((g) => <section key={g.group!.id} aria-labelledby={`mg-${detail.id}-${g.group!.id}`} className="mt-2">
        <h3 id={`mg-${detail.id}-${g.group!.id}`} className="text-sm">{g.group!.title_cs} <span aria-hidden="true" className="text-ink-faint">·</span> <span className="text-xs font-normal text-ink-faint">{t(`${M}.noSteps`)}</span></h3>
        {g.group!.note_cs ? <p title={g.group!.note_cs} className="line-clamp-1 text-xs text-ink-muted">{g.group!.note_cs}</p> : null}
      </section>)}
    </section> : null}
  </div>;
}

/** A step as a row: its number, title, what it is for and its values; open, its formula, values,
 *  where they come from and what holds it. The heading names the step, so it can be found. */
function StepRow({ step, number, editable, titles, open, onToggle, onPick }: { step: MethodStepOut; number?: string; editable: boolean; titles: Record<string, string>; open: boolean; onToggle: () => void; onPick: (id: string) => void }) {
  const line = step.role_cs || step.note_cs.split(/(?<=\.)\s/)[0] || "";
  return <article aria-labelledby={`ms-${step.id}`} data-step={step.id} className="border-b border-border last:border-b-0">
    <h4 id={`ms-${step.id}`} aria-labelledby={`mst-${step.id}`} className="scroll-mt-4">
      <button type="button" aria-expanded={open} aria-labelledby={`mst-${step.id}`} aria-describedby={line ? `msl-${step.id}` : undefined} onClick={onToggle}
        className="flex w-full items-start gap-2.5 px-1 py-2 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring">
        <span data-step-number className="w-12 shrink-0 pt-0.5 font-mono text-xs text-ink-faint">{number ?? ""}</span>
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span id={`mst-${step.id}`} className="text-sm font-medium">{step.title_cs}</span>
          {line ? <span id={`msl-${step.id}`} className="text-xs leading-5 text-ink-muted">{line}</span> : null}
          {step.values.length ? <span className="flex flex-wrap gap-1.5">{step.values.map((v) => (
            <span key={v.reference} data-step-value className="inline-flex min-h-[22px] max-w-full flex-wrap items-center rounded-[11px] border border-border px-2 text-xs font-normal text-ink-muted">{v.label_cs}: <b className="ml-1 break-all font-mono font-medium text-ink">{showValue(v, WORDS)}{v.unit && !v.absent && v.value !== null ? ` ${v.unit}` : ""}</b></span>
          ))}</span> : null}
        </span>
        <span aria-hidden="true" className="pt-0.5 text-ink-faint">{open ? "▾" : "▸"}</span>
      </button>
    </h4>
    {open ? <div data-step-body className="flex min-w-0 flex-col gap-3 pb-4 pl-1 sm:pl-[3.625rem]"><StepBody step={step} editable={editable} titles={titles} onPick={onPick} /></div> : null}
  </article>;
}

/** An open step's detail: its formula, note, context, symbols, values, formulas, evidence and code. */
function StepBody({ step, editable, titles, onPick }: { step: MethodStepOut; editable: boolean; titles: Record<string, string>; onPick: (id: string) => void }) {
  return (
    <>
      {step.audit ? <p data-step-origin className="text-xs text-ink-faint">{stepOrigin(step.audit)}</p> : null}
      <div className="min-w-0 overflow-x-auto text-ink"><Formula latex={step.formula_latex} /></div>
      {step.note_cs ? <p className="max-w-3xl break-words text-sm text-ink-muted">{step.note_cs}</p> : null}
      <StepContext step={step} titles={titles} onPick={onPick} />
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
    </>
  );
}

/** A step's formula as the expression the engine evaluates, drawn from that expression. Its
 *  help says it can be replaced only where the module has a version editor. */
function EditableFormula({ formula, editable }: { formula: MethodFormula; editable: boolean }) {
  return (
    <details aria-label={`${t(`${M}.editable`)}: ${formula.title_cs}`} data-slot={formula.slot_id} className="rounded-sm border border-border p-3">
      <summary className="cursor-pointer text-xs font-semibold text-ink-muted">{t(`${M}.editable`)} · {formula.title_cs}</summary><div className="mt-3 flex min-w-0 flex-col gap-2">
      <p className="text-xs text-ink-muted">{t(editable ? `${M}.editableHelp` : `${M}.editableHelpLater`)}</p>
      <div className="min-w-0 overflow-x-auto text-ink"><Formula latex={formula.latex} /></div>
      <p className="text-sm">
        <span className="text-xs text-ink-muted">{t(`${M}.expression`)}: </span>
        <code className="whitespace-pre-wrap break-all font-mono text-xs">{formula.expression}</code>
      </p>
      {formula.note_cs ? <p className="break-words text-xs text-ink-muted">{formula.note_cs}</p> : null}
      {formula.kept_cs.length ? (
        <div data-kept className="text-xs">
          <p className="text-ink-muted">{t(`${M}.kept`)}:</p>
          <ul className="mt-1 list-disc pl-5">{formula.kept_cs.map((k) => <li key={k}>{k}</li>)}</ul>
        </div>
      ) : null}
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
