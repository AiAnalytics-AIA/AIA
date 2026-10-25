"use client";

// The Metodika tab's versions (ADR 0023, plan S4a): what a run started now pins, every stored
// version and what it changes against the preset it came from, the activation log, and -- for
// the Metodik -- the editor: one list of every parameter of a preset or a stored version, in the
// order the computation reads them, with each formula slot as an expression for the expert
// (settings-redesign F6, prototype v51). The check is the domain's own (POST .../check, nothing
// stored) and its problems are shown at the field they name; the page states no bound of its own.
// Storing makes a new immutable version; it is in force only once put, and then only for runs
// started afterwards. The API refuses a non-administrator whatever this page shows.

import { type Dispatch, type FormEvent, type ReactNode, type SetStateAction, memo, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useRouter } from "next/navigation";
import { InlineConfirm } from "../../rehome/step";
import { t, tv } from "@/i18n/t";
import {
  type MethodCheck,
  type MethodCompare,
  type MethodModuleDetail,
  type MethodModuleSummary,
  type MethodStepOut,
  type MethodVersion,
  type MethodVersions,
  methodology,
} from "@/lib/api";
import { plural, relative } from "@/lib/format";
import { groupSteps, stageNumbers, stepNumbers } from "@/lib/methodology";
import {
  type EditField,
  changedPaths,
  editableSteps,
  fillReading,
  fromInput,
  problemsFor,
  readPath,
  toInput,
  withPath,
} from "@/lib/methodology-edit";
import { Button, Field, Select, Tag, TextArea, TextInput } from "../../rehome/ui";
import { ChoiceChips } from "../../ui/ChoiceChips";
import { ConfirmDialog } from "../../ui/ConfirmDialog";
import { FOCUS } from "../../ui/parts";
import { Loaded } from "../states";
import { type Resource, useResource } from "../useResource";
import { describeError } from "./errors";
import { MethodologyComparison } from "./MethodologyComparison";
import { Formula } from "./MethodologyFormula";

const V = "aia.settings.methodology.versions";
export type People = (id: string | null) => string;
const when = (iso: string) => relative(iso) ?? iso;

export function MethodologyVersions({ summary, people, calc, onEditing, onDirty, versions }: {
  summary: MethodModuleSummary; people: People;
  /** The page's own read of these versions and its reload, shared with the module's head; absent,
   *  the component reads them itself. */
  versions?: { res: Resource<MethodVersions>; reload: () => void };
  /** The module's calculation, shown on Výpočet (settings-redesign 10b). */
  calc?: ReactNode;
  /** The editor is open (the read-only catalogue steps aside). */
  onEditing?: (value: boolean) => void;
  /** The open editor holds changes nothing has saved (leaving needs a decision). */
  onDirty?: (value: boolean) => void;
}) {
  const [own, ownRetry] = useResource(() => (versions ? Promise.resolve(null) : methodology.versions(summary.id)), [summary.id, versions === undefined]);
  const res = versions ? versions.res : (own as Resource<MethodVersions>);
  const retry = versions ? versions.reload : ownRetry;
  if (res.state === "ready") return <Body summary={summary} data={res.data} people={people} calc={calc} reload={retry} onEditing={onEditing} onDirty={onDirty} />;
  // Versions not read (yet): the calculation is still the module's, shown under why.
  return <div className="flex min-w-0 flex-col gap-4"><Loaded res={res} retry={retry}>{() => null}</Loaded>{calc}</div>;
}

/** Where an edit starts: a code preset, or a stored version (its spec and its formulas). */
type Start = {
  base: string; spec: Record<string, unknown>; formulas: Record<string, string>; from: string;
  /** A person asked for this edit (the page then moves to it); the editor a methodologist
   *  opens on stays where the page is. */
  byPerson?: boolean;
  /** The methodology in force this edit starts from, by name: the editor says so. */
  inForce?: string;
};

/** A module's parts (settings-redesign 10b, design "Metodika" board): each a tab, all kept mounted
 *  so an unsaved edit survives a look at the calculation or the versions. */
type View = "calc" | "versions" | "compare" | "edit";
const VIEWS: readonly View[] = ["calc", "versions", "compare", "edit"];

function Body({ summary, data, people, calc, reload, onEditing, onDirty }: { summary: MethodModuleSummary; data: MethodVersions; people: People; calc?: ReactNode; reload: () => void; onEditing?: (value: boolean) => void; onDirty?: (value: boolean) => void }) {
  const [done, setDone] = useState<{ message: string; version: MethodVersion | null } | null>(null);
  const [activating, setActivating] = useState<{ version: number | null } | null>(null);
  const presetStart = (name: string): Start => ({ base: name, spec: data.presets[name] ?? {}, formulas: {}, from: name });
  const versionStart = (v: MethodVersion): Start => ({ base: v.base_preset, spec: v.spec, formulas: v.formulas, from: v.name });
  // An edit starts from what is in force (product owner, 2026-10-13): the stored version in force,
  // else the code's preset in force (not merely the first one listed).
  const editStart = (): Start => {
    const stored = data.in_force.origin === "stored" ? data.versions.find((v) => v.version_number === data.in_force.version_number) : undefined;
    const from = stored ? versionStart(stored) : presetStart(summary.in_force ?? summary.presets[0] ?? "");
    return { ...from, inForce: data.in_force.name };
  };
  // The methodologists who may edit open on the editor (product owner, 2026-10-13); anyone else on
  // the calculation. Editing is theirs alone (D-14): the API's may_edit, the Metodik mark (#823), says who that is.
  const [start, setStart] = useState<Start | null>(() => (data.may_edit ? editStart() : null));
  const [view, setView] = useState<View>(data.may_edit ? "edit" : "calc");
  useEffect(() => { onEditing?.(view === "edit" && start !== null); }, [view, start, onEditing]);
  // The editor's last comparison, shown on Porovnání; any change to the draft clears it.
  const [comparison, setComparison] = useState<MethodCompare | null>(null);
  const onCompared = useCallback((c: MethodCompare | null) => { setComparison(c); if (c) setView("compare"); }, []);
  const [dirty, setDirty] = useState(false);
  useEffect(() => { onDirty?.(start !== null && dirty); }, [start, dirty, onDirty]);
  const [pending, setPending] = useState<{ next: Start | null; again: boolean } | null>(null);
  // Each discarded edit starts a fresh one: the list is drawn again from what is in force.
  const [fresh, setFresh] = useState(0);
  const begin = (next: Start | null, again: boolean) => {
    setStart(next); setDirty(false); setComparison(null);
    if (again) setFresh((n) => n + 1);
    // An edit opens on Upravit; a cancelled one returns to the calculation it was made against.
    setView(next ? "edit" : "calc");
  };
  const changeStart = (asked: Start | null, again = false) => {
    // Zahodit úpravu starts over where the person is; it moves nobody to the top of the page.
    const next = asked && { ...asked, byPerson: !again };
    if (start && dirty) { setPending({ next, again }); return; }
    begin(next, again);
  };
  const inForce = data.in_force;
  const currentSpec = inForce.origin === "stored"
    ? data.versions.find((version) => version.version_number === inForce.version_number)?.spec
    : data.presets[inForce.preset ?? summary.in_force ?? ""];
  const currentFormulas = inForce.origin === "stored" ? (data.versions.find((version) => version.version_number === inForce.version_number)?.formulas ?? {}) : {};
  // Both sides are the same only when no edit is open, or the open one starts from exactly what is
  // in force and is untouched: an edit from another version differs before a key is pressed.
  const sameAsInForce = start === null || (!dirty && currentSpec !== undefined
    && changedPaths(currentSpec, start.spec).filter((p) => p !== "methodology_version").length === 0
    && JSON.stringify(Object.entries(start.formulas).sort()) === JSON.stringify(Object.entries(currentFormulas).sort()));
  return (
    // The module's parts sit under its head, as prototype v51 draws them: what is in force is the
    // head's chip, and said again on Verze a aktivace (fidelity F6).
    <section aria-labelledby={`mv-${summary.id}`} data-methodology-versions={summary.id} className="flex min-w-0 flex-col gap-3">
      <h3 id={`mv-${summary.id}`} className="sr-only">{t(`${V}.title`)}</h3>
      {pending ? <InlineConfirm message={t(`${V}.replaceDraft`)} action={t(`${V}.discardDraft`)} onCancel={() => setPending(null)} onConfirm={() => { begin(pending.next, pending.again); setPending(null); }} /> : null}
      {done ? (
        <div role="status" className="flex flex-wrap items-center gap-3 text-sm">
          <span>{done.message}</span>
          {done.version && data.may_edit && !activating ? <Button small variant="primary" onClick={() => setActivating({ version: done.version!.version_number })}>{tv(`${V}.activate`, { name: done.version.name })}</Button> : null}
        </div>
      ) : null}
      <div role="tablist" aria-label={t(`${V}.tabs.label`)} className="flex flex-wrap gap-0.5 border-b border-border">
        {VIEWS.map((v) => {
          const off = v === "edit" && !data.may_edit;
          return (
            <button key={v} type="button" role="tab" id={`mv-${summary.id}-tab-${v}`} aria-controls={`mv-${summary.id}-${v}`} aria-selected={view === v} disabled={off}
              // Upravit with nothing open starts the edit from what is in force (product owner, 2026-10-13).
              onClick={() => { if (v === "edit" && !start && data.may_edit) { setDone(null); changeStart(editStart()); } else setView(v); }}
              className={`-mb-px min-h-10 border-b-2 px-3 text-sm disabled:cursor-not-allowed disabled:opacity-45 ${FOCUS} ${view === v ? "border-signal font-medium text-ink" : "border-transparent text-ink-muted hover:text-ink"}`}>
              {off ? t(`${V}.tabs.editMetodik`) : t(`${V}.tabs.${v}`)}
            </button>
          );
        })}
      </div>

      <div role="tabpanel" id={`mv-${summary.id}-versions`} aria-labelledby={`mv-${summary.id}-tab-versions`} hidden={view !== "versions"} className="flex min-w-0 flex-col gap-4">
        <p data-in-force className="text-sm">
          {t(`${V}.inForce`)}: <strong className="font-mono">{inForce.name}</strong>{" "}
          <Tag>{t(`${V}.origin.${inForce.origin}`)}</Tag>
        </p>
        <p className="max-w-3xl text-xs leading-5 text-ink-muted">{t(`${V}.pinNote`)}</p>
        <div>
          <h4 className="text-sm font-semibold">{t(`${V}.list`)}</h4>
          {data.versions.length ? (
            <ul className="mt-1 flex flex-col gap-2 text-sm">
              {data.versions.map((v) => {
                const changed = changedPaths(data.presets[v.base_preset] ?? {}, v.spec).filter((p) => p !== "methodology_version");
                const formulas = Object.keys(v.formulas);
                return (
                  <li key={v.version_number} data-methodology-version={v.version_number} className="flex flex-col gap-1 rounded-sm border border-border p-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <strong className="font-mono">{v.name}</strong>
                      <span className="text-ink-muted">· {people(v.created_by)} · {when(v.created_at)}</span>
                      {inForce.version_number === v.version_number ? <span data-in-force-version className="inline-flex min-h-[22px] items-center rounded-pill border border-in-force px-2 text-xs text-in-force">{t(`${V}.current`)}</span> : null}
                    </div>
                    {v.note ? <p className="text-ink-muted">{v.note}</p> : null}
                    <div className="text-xs">
                      {changed.length || formulas.length ? (
                        <>
                          {tv(`${V}.changes`, { base: v.base_preset })}{" "}
                          <span>{tv(`${V}.versionChangeCount`, { fields: changed.length, formulas: formulas.length })}</span><details className="mt-1"><summary className="cursor-pointer text-ink-muted">{t(`${V}.changeDetails`)}</summary><span className="break-all font-mono">{[...changed, ...formulas.map((f) => `ƒ ${f}`)].join(", ")}</span></details>
                        </>
                      ) : tv(`${V}.noChanges`, { base: v.base_preset })}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {/* A version just saved is activated from its confirmation above: one button, never two. */}
                      {data.may_edit && inForce.version_number !== v.version_number && done?.version?.version_number !== v.version_number ? (
                        <Button small disabled={start !== null && dirty} onClick={() => { setDone(null); setActivating({ version: v.version_number }); }}>{tv(`${V}.activate`, { name: v.name })}</Button>
                      ) : null}
                      {data.may_edit ? <Button small onClick={() => { setDone(null); changeStart(versionStart(v)); }}>{t(`${V}.editFrom`)}</Button> : null}
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : <p className="mt-1 text-sm text-ink-muted">{t(`${V}.none`)}</p>}
        </div>
        {data.may_edit && inForce.origin === "stored" ? (
          <div><Button small disabled={start !== null && dirty} onClick={() => { setDone(null); setActivating({ version: null }); }}>{tv(`${V}.reset`, { preset: summary.in_force ?? "" })}</Button></div>
        ) : null}
        <div>
          <h4 className="text-sm font-semibold">{t(`${V}.history`)}</h4>
          {data.history.length ? (
            <div className="mt-1 overflow-x-auto">
              <table aria-label={t(`${V}.history`)} className="w-full min-w-[28rem] border-collapse text-sm">
                <thead><tr>{(["when", "who", "version", "why"] as const).map((c) => <th key={c} scope="col" className="px-2 py-1.5 text-left text-xs font-normal text-ink-faint">{t(`${V}.historyCol.${c}`)}</th>)}</tr></thead>
                <tbody>{data.history.map((h) => (
                  <tr key={h.activation_id} data-methodology-activation={h.activation_id}>
                    <td className="whitespace-nowrap border-t border-border px-2 py-2 align-top text-ink-muted">{when(h.activated_at)}</td>
                    <td className="border-t border-border px-2 py-2 align-top">{people(h.activated_by)}</td>
                    <td className="border-t border-border px-2 py-2 align-top font-mono">{h.version_number === null ? tv(`${V}.backToPreset`, { preset: summary.in_force ?? "" }) : `e${h.version_number}`}</td>
                    <td className="break-words border-t border-border px-2 py-2 align-top">{h.reason || <span className="text-ink-faint">{t(`${V}.noReason`)}</span>}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          ) : <p className="mt-1 text-sm text-ink-muted">{t(`${V}.noHistory`)}</p>}
        </div>
      </div>

      <div role="tabpanel" id={`mv-${summary.id}-compare`} aria-labelledby={`mv-${summary.id}-tab-compare`} hidden={view !== "compare"} className="flex min-w-0 flex-col gap-3">
        <p className="max-w-3xl text-sm leading-6 text-ink-muted">{t(`${V}.compareHelp`)}</p>
        {comparison ? <>
          <p data-compare-draft className="self-start rounded-pill border border-status-you-ink/40 bg-status-you-wash px-2 py-0.5 text-xs">{t(`${V}.compareDraft`)}</p>
          <MethodologyComparison result={comparison} />
        </> : <p data-compare-none className="text-sm text-ink-muted">{!data.may_edit ? t(`${V}.compareReader`) : sameAsInForce ? t(`${V}.compareSame`) : t(`${V}.compareNotYet`)}</p>}
      </div>

      <div role="tabpanel" id={`mv-${summary.id}-edit`} aria-labelledby={`mv-${summary.id}-tab-edit`} hidden={view !== "edit"} className="flex min-w-0 flex-col gap-3">
        {data.may_edit && start ? (
          <Editor
            key={`${start.from}:${fresh}`}
            summary={summary}
            start={start}
            currentSpec={currentSpec}
            nextName={`${start.base}+e${Math.max(0, ...data.versions.map((v) => v.version_number)) + 1}`}
            presets={Object.keys(data.presets)}
            onBase={(name) => changeStart(presetStart(name))}
            onDirty={setDirty}
            onCompared={onCompared}
            onDiscard={() => changeStart(editStart(), true)}
            onSaved={(saved) => { setStart(null); setDirty(false); setComparison(null); setView("versions"); setDone({ message: tv(`${V}.saved`, { name: saved.name }), version: saved }); reload(); }}
          />
        ) : data.may_edit ? <div><Button variant="primary" small onClick={() => { setDone(null); changeStart(editStart()); }}>{t(`${V}.edit`)}</Button></div> : null}
      </div>

      {/* The calculation last in the document (one panel shows at a time): its thousands of nodes after
          the editor keep a label's lookup of its field short (jsdom walks the tree in order). */}
      <div role="tabpanel" id={`mv-${summary.id}-calc`} aria-labelledby={`mv-${summary.id}-tab-calc`} hidden={view !== "calc"} className="flex min-w-0 flex-col gap-4">{calc}</div>

      {activating ? (
        <Activate
          moduleId={summary.id}
          version={activating.version}
          name={activating.version === null ? (summary.in_force ?? "") : (data.versions.find((v) => v.version_number === activating.version)?.name ?? "")}
          onCancel={() => setActivating(null)}
          onDone={() => { setActivating(null); setDone({ message: t(`${V}.activated`), version: null }); reload(); }}
        />
      ) : null}
      {data.may_edit ? null : <p className="text-xs text-ink-muted">{t(`${V}.adminNote`)}</p>}
    </section>
  );
}

/** Why a version is put in force: one of four, said in the audit, and a note if the person adds one. */
const REASONS = ["fix", "pilot", "owner", "default"] as const;
type Reason = (typeof REASONS)[number];

/** Putting a version in force, or back to the code (I7): one dialog that names the act, with the
 *  reason required, chosen as a chip (the design's four) and an optional note. */
function Activate({ moduleId, version, name, onCancel, onDone }: { moduleId: string; version: number | null; name: string; onCancel: () => void; onDone: () => void }) {
  const [why, setWhy] = useState<Reason | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // An edited Sociomap is internal until the register approves it (PC17): the act says so.
  const internal = moduleId === "sociomap" && version !== null;
  const go = async () => {
    if (!why) { setError(t(`${V}.reasonNeeded`)); return; }
    setBusy(true);
    setError(null);
    try {
      await methodology.activate(moduleId, version, `${t(`${V}.reasons.${why}`)}${note.trim() ? `: ${note.trim()}` : ""}`);
      onDone();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <ConfirmDialog open marker="methodology-activate" busy={busy} error={error}
      title={tv(version === null ? `${V}.resetTitle` : `${V}.activateTitle`, { name })}
      text={<>
        <p className="text-ink-muted">{t(`${V}.pinNote`)}</p>
        {/* The Sociomap register approves one exact method (aia-sociomap-3 as the code has it): a map
            computed by an edited version is internal until the register approves it, so the client
            report of a run started under it has no maps. The rule is the register's; this says it
            where it takes effect (PC17). */}
        {internal ? <p role="note" data-sociomap-internal className="mt-2 rounded-sm border border-status-you-ink/40 bg-status-you-wash p-2 text-xs">{t(`${V}.sociomapInternal`)}</p> : null}
      </>}
      confirmLabel={version === null ? t(`${V}.resetConfirm`) : internal ? t(`${V}.activateInternal`) : t(`${V}.activateConfirm`)}
      cancelLabel={t(`${V}.cancel`)}
      onConfirm={() => void go()} onCancel={onCancel}>
      <div className="flex flex-col gap-2">
        <p aria-hidden="true" className="text-xs text-ink-muted">{t(`${V}.reasonLabel`)}</p>
        <ChoiceChips label={t(`${V}.reasonLabel`)} value={why} options={REASONS.map((r) => ({ key: r, label: t(`${V}.reasons.${r}`) }))} onChange={(r) => { setWhy(r); setError(null); }} />
        <TextInput aria-label={t(`${V}.reasonNote`)} placeholder={t(`${V}.reasonNotePlaceholder`)} value={note} maxLength={400} onChange={(e) => setNote(e.target.value)} />
      </div>
    </ConfirmDialog>
  );
}

function Editor(props: {
  summary: MethodModuleSummary; start: Start; presets: string[]; currentSpec?: Record<string, unknown>; nextName: string;
  onBase: (name: string) => void; onDirty: (value: boolean) => void; onCompared: (c: MethodCompare | null) => void; onDiscard: () => void; onSaved: (v: MethodVersion) => void;
}) {
  // The labels and slots of the preset the edit is based on; the values come from `start`.
  const [res, retry] = useResource(() => methodology.get(props.summary.id, props.start.base), [props.summary.id, props.start.base]);
  return <Loaded res={res} retry={retry}>{(detail) => <EditorForm {...props} detail={detail} />}</Loaded>;
}

/** One parameter of the list: a field of the specification, the step that first reads it and
 *  where that step sits in the computation. */
type Row = { field: EditField; step: MethodStepOut; stage: string };

/** A value as the list shows it: a number with the Czech decimal comma, anything else as typed. */
const shown = (value: unknown): string => (typeof value === "number" ? String(value).replace(".", ",") : toInput(value));

/** The places a number carries ("0.25": 2, "1e-12": 12): one press of − / + moves its last one. */
function placesOf(value: number): number {
  const [mantissa, exponent] = String(value).split("e-");
  const places = mantissa.split(".")[1]?.length ?? 0;
  return exponent === undefined ? places : places + Number(exponent);
}

/** Whether a field's text, read as its original value's type, is that original value. */
function same(original: unknown, raw: string): boolean {
  const parsed = fromInput(original, raw);
  return parsed.ok && JSON.stringify(parsed.value) === JSON.stringify(original);
}

function EditorForm({ summary, start, presets, detail, currentSpec, nextName, onBase, onDirty, onCompared, onDiscard, onSaved }: {
  summary: MethodModuleSummary; start: Start; presets: string[]; detail: MethodModuleDetail; currentSpec?: Record<string, unknown>;
  /** What the stored edit will be called: the base and the module's next number. */
  nextName: string;
  onBase: (name: string) => void; onDirty: (value: boolean) => void;
  /** The comparison, shown on the module's Porovnání; null when the draft changed under it. */
  onCompared: (c: MethodCompare | null) => void; onDiscard: () => void; onSaved: (v: MethodVersion) => void;
}) {
  const steps = useMemo(() => editableSteps(detail), [detail]);
  const numbers = useMemo(() => stageNumbers(detail.groups), [detail]);
  const stepNumber = useMemo(() => stepNumbers(detail.groups), [detail]);
  // Every parameter once, in the order the computation reads them (settings-redesign F6, prototype
  // v51 "Parametry"): the first step that reads a field names its stage. The version's name is not
  // one: the store writes it.
  const rows = useMemo(() => {
    const seen = new Set<string>();
    const out: Row[] = [];
    const add = (step: MethodStepOut, stage: string) => {
      for (const field of steps.find((s) => s.step.id === step.id)?.fields ?? []) {
        if (field.reference === "methodology_version" || seen.has(field.reference)) continue;
        seen.add(field.reference);
        out.push({ field, step, stage });
      }
    };
    const placed = new Set<string>();
    for (const { group, steps: items } of groupSteps(detail)) {
      const n = group ? numbers.get(group.id) : undefined;
      for (const step of items) { placed.add(step.id); add(step, group ? `${n ? `M${n} ` : ""}${group.title_cs}` : ""); }
    }
    for (const { step } of steps) if (!placed.has(step.id)) add(step, "");
    return out;
  }, [detail, steps, numbers]);
  const slotSteps = useMemo(() => steps.filter(({ step }) => step.formulas.length), [steps]);
  const builtin = useMemo(() => new Map(steps.flatMap(({ step }) => step.formulas.map((f) => [f.slot_id, f.expression] as const))), [steps]);
  const original = useCallback((reference: string) => readPath(start.spec, reference), [start.spec]);
  const [raw, setRaw] = useState<Record<string, string>>(() => Object.fromEntries(rows.map(({ field }) => [field.reference, shown(readPath(start.spec, field.reference))])));
  const [exprs, setExprs] = useState<Record<string, string>>(() =>
    Object.fromEntries([...builtin].map(([slot, expr]) => [slot, start.formulas[slot] ?? expr])),
  );
  const [note, setNote] = useState("");
  const [check, setCheck] = useState<MethodCheck | null>(null);
  const [operation, setOperation] = useState<"check" | "compare" | "store" | null>(null);
  const busy = operation !== null;
  const [error, setError] = useState<string | null>(null);
  const [formulasOpen, setFormulasOpen] = useState(false);
  const headingRef = useRef<HTMLHeadingElement>(null);
  // Read once: only an edit a person asked for moves the page to itself.
  const focusOnOpen = useRef(start.byPerson === true);
  useEffect(() => {
    // Starting an edit moves the person to it, especially on a phone where the module's head is
    // taller than one viewport.
    if (!focusOnOpen.current) return;
    headingRef.current?.scrollIntoView?.({ block: "start" });
    headingRef.current?.focus({ preventScroll: true });
  }, []);

  const router = useRouter();
  const titles = useMemo(() => Object.fromEntries(detail.step_details.map((s) => [s.id, s.title_cs])), [detail]);
  const [leaveHref, setLeaveHref] = useState<string | null>(null);
  const fieldChanged = (reference: string) => !same(original(reference), raw[reference] ?? "");
  const slotChanged = (slot: string) => exprs[slot] !== (start.formulas[slot] ?? builtin.get(slot));
  const changedCount = rows.filter(({ field }) => fieldChanged(field.reference)).length + [...builtin.keys()].filter(slotChanged).length;
  const dirty = changedCount > 0 || !!note.trim();
  useEffect(() => { onDirty(dirty); }, [dirty, onDirty]);
  useEffect(() => {
    if (!dirty) return;
    const unload = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    const leave = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
      const link = (e.target as Element).closest?.("a[href]") as HTMLAnchorElement | null;
      if (!link || link.target || link.download || link.origin !== location.origin || link.pathname === location.pathname) return;
      e.preventDefault(); setLeaveHref(link.pathname + link.search + link.hash);
    };
    window.addEventListener("beforeunload", unload); document.addEventListener("click", leave, true);
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", leave, true); };
  }, [dirty]);
  const clearPreview = useCallback(() => { setCheck(null); setError(null); onCompared(null); }, [onCompared]);
  const setValue = useCallback((reference: string, value: string) => { setRaw((r) => ({ ...r, [reference]: value })); clearPreview(); }, [clearPreview]);
  const slotOf = useCallback((path: string) => [...builtin.keys()].find((slot) => path === `formula.${slot}` || path.startsWith(`formula.${slot}.`)), [builtin]);
  // A problem in a formula opens the formulas: a refused edit is never hidden in a closed part.
  const showProblems = (problems: Record<string, string>) => { if (Object.keys(problems).some((path) => slotOf(path))) setFormulasOpen(true); };
  // A problem's link owes the focus to its field: a formula's textarea exists only once the
  // formulas are drawn, so the focus is given after the render that mounts it, never on a frame
  // guess (AGENTS.md, "Focus an element after the render that mounts it").
  const [owedFocus, setOwedFocus] = useState<string | null>(null);
  const focusProblem = (path: string) => {
    if (slotOf(path)) setFormulasOpen(true);
    setOwedFocus(path);
  };
  useEffect(() => {
    if (!owedFocus) return;
    const slot = slotOf(owedFocus);
    const target = slot
      ? document.querySelector<HTMLElement>(`[data-edit-slot="${slot}"] textarea`)
      : [...document.querySelectorAll<HTMLElement>("[data-field]")].find((node) => owedFocus === `spec.${node.getAttribute("data-field")}` || owedFocus.startsWith(`spec.${node.getAttribute("data-field")}.`));
    // Not drawn yet: the render that opens the formulas runs this again.
    if (!target) return;
    target.focus();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- a one-shot focus, cleared once given
    setOwedFocus(null);
  }, [owedFocus, formulasOpen, slotOf]);

  // The whole edit, or the fields the page itself cannot read (a word where a number was).
  const build = (): { edit: { base_preset: string; spec: Record<string, unknown>; formulas: Record<string, string> } } | { local: Record<string, string> } => {
    let spec = start.spec;
    const local: Record<string, string> = {};
    for (const [reference, text] of Object.entries(raw)) {
      const parsed = fromInput(original(reference), text);
      if (!parsed.ok) local[`spec.${reference}`] = t(`${V}.parse.${parsed.reason}`);
      else spec = withPath(spec, reference, parsed.value);
    }
    if (Object.keys(local).length) return { local };
    const formulas = Object.fromEntries(Object.entries(exprs).map(([s, e]) => [s, e.trim()]).filter(([s, e]) => e !== builtin.get(s)));
    return { edit: { base_preset: start.base, spec, formulas } };
  };

  const run = async (store: boolean) => {
    setError(null);
    const built = build();
    if ("local" in built) { setCheck({ valid: false, problems: built.local, not_computed: [], formulas_latex: {} }); return; }
    setOperation(store ? "store" : "check");
    try {
      const checked = await methodology.check(summary.id, built.edit);
      setCheck(checked); showProblems(checked.problems);
      if (store && checked.valid) onSaved(await methodology.propose(summary.id, { ...built.edit, note: note.trim() }));
    } catch (e) {
      setError(describeError(e));
    } finally {
      setOperation(null);
    }
  };
  // The edit beside what is in force on fictional panels, shown on Porovnání; a refused edit shows
  // its problems here instead.
  const compare = async () => {
    setError(null);
    onCompared(null);
    const built = build();
    if ("local" in built) { setCheck({ valid: false, problems: built.local, not_computed: [], formulas_latex: {} }); return; }
    setOperation("compare");
    try {
      const result = await methodology.compare(summary.id, built.edit);
      if (result.valid) onCompared(result);
      else { setCheck({ valid: false, problems: result.problems, not_computed: [], formulas_latex: {} }); showProblems(result.problems); }
    } catch (e) {
      setError(describeError(e));
    } finally {
      setOperation(null);
    }
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    void run(true);
  };

  const problems = check?.problems ?? {};
  const owner = (path: string): string | null => {
    const row = rows.find(({ field }) => path === `spec.${field.reference}` || path.startsWith(`spec.${field.reference}.`));
    if (row) return row.field.label_cs;
    const slot = slotOf(path);
    return slot ? (steps.flatMap(({ step }) => step.formulas).find((f) => f.slot_id === slot)?.title_cs ?? null) : null;
  };
  const preview = check?.valid ? check.preview ?? [] : [];
  const valueOf = (path: string) => raw[path] ?? shown(readPath(start.spec, path));
  const internal = summary.id === "sociomap";
  return (
    <form data-methodology-editor aria-label={t(`${V}.editorLabel`)} onSubmit={submit} className="flex min-w-0 max-w-full flex-col gap-4">
      {leaveHref ? <InlineConfirm message={t(`${V}.replaceDraft`)} action={t(`${V}.discardDraft`)} onCancel={() => setLeaveHref(null)} onConfirm={() => router.push(leaveHref)} /> : null}

      {/* Where the edit starts and what it will be called (prototype v51: the note above the list). */}
      <div role="note" data-start-note className="flex flex-wrap items-end gap-x-4 gap-y-2 rounded-md border border-signal-edge bg-signal-tint px-3.5 py-3 text-sm leading-6">
        <p className="min-w-0 flex-1 basis-80">
          {start.inForce ? t(`${V}.startInForce`) : t(`${V}.startFrom`)} <b className="whitespace-nowrap font-mono font-semibold">{start.inForce ?? start.from}</b>.{" "}
          {start.inForce && start.base !== start.inForce && start.from === start.base ? <>{tv(`${V}.startSameAs`, { base: start.base })} </> : null}
          {t(`${V}.startNamed`)} <span className="whitespace-nowrap font-mono">{nextName}</span>{internal ? <> {t(`${V}.startIs`)} <b className="font-semibold">{t(`${V}.startInternal`)}</b>{t(`${V}.startUntil`)}</> : "."}
        </p>
        {presets.length > 1 ? (
          <Field label={t(`${V}.base`)} className="w-56">
            <Select aria-label={t(`${V}.base`)} disabled={busy} value={!start.inForce && start.from === start.base ? start.base : ""} onChange={(e) => e.target.value && onBase(e.target.value)}>
              {!start.inForce && start.from === start.base ? null : <option value="">{start.inForce ? t(`${V}.inForceOption`) : start.from}</option>}
              {presets.map((p) => <option key={p} value={p}>{p}</option>)}
            </Select>
          </Field>
        ) : null}
      </div>

      <section aria-labelledby={`mp-${summary.id}`} data-edit-params className="min-w-0 rounded-md border border-border bg-surface-raised px-4 pb-2 pt-3.5 sm:px-5">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 pb-2">
          <h3 id={`mp-${summary.id}`} ref={headingRef} tabIndex={-1} className="scroll-mt-24 text-base font-semibold">{t(`${V}.parameters`)}</h3>
          <p className="text-xs text-ink-muted">{t(`${V}.parametersHelp`)}</p>
        </div>
        <fieldset disabled={busy} className="m-0 min-w-0 border-0 p-0">
          <legend className="sr-only">{t(`${V}.parameters`)}</legend>
          {rows.map((row) => (
            <ParamRow key={row.field.reference} row={row} value={raw[row.field.reference] ?? ""} original={original(row.field.reference)}
              live={currentSpec ? readPath(currentSpec, row.field.reference) : undefined}
              reading={row.step.reading_cs ? fillReading(row.step.reading_cs, valueOf) : ""}
              problems={problemsFor(problems, `spec.${row.field.reference}`)} onChange={setValue} />
          ))}
          {rows.length ? null : <p className="py-3 text-sm text-ink-muted">{t(`${V}.noParameters`)}</p>}
        </fieldset>
      </section>

      {slotSteps.length ? (
        <details data-edit-formulas open={formulasOpen} onToggle={(e) => setFormulasOpen(e.currentTarget.open)} className="min-w-0 rounded-md border border-border bg-surface-raised">
          <summary className={`flex min-h-11 cursor-pointer list-none items-center gap-2 px-4 text-sm font-semibold sm:px-5 ${FOCUS}`}>
            <span aria-hidden="true" className="text-ink-faint">{formulasOpen ? "▾" : "▸"}</span>
            {t(`${V}.advancedFormulas`)}
            {[...builtin.keys()].filter(slotChanged).length ? <span className="text-xs font-normal text-signal">{tv(`${V}.formulasChanged`, { count: [...builtin.keys()].filter(slotChanged).length })}</span> : null}
          </summary>
          <div className="flex min-w-0 flex-col gap-5 border-t border-border px-4 py-4 sm:px-5">
            <p className="max-w-3xl text-xs leading-5 text-ink-muted">{t(`${V}.advancedHelp`)}</p>
            {formulasOpen ? slotSteps.map(({ step }) => {
              const slots = step.formulas.map((f) => f.slot_id);
              return (
                <FormulaSlots key={step.id} step={step} number={stepNumber.get(step.id) ?? ""} busy={busy} start={start} titles={titles}
                  formulas={Object.fromEntries(slots.map((slot) => [slot, exprs[slot]]))}
                  problems={Object.fromEntries(Object.entries(problems).filter(([k]) => slots.some((slot) => k === `formula.${slot}` || k.startsWith(`formula.${slot}.`))))}
                  written={Object.fromEntries(slots.filter((slot) => check?.formulas_latex[slot]).map((slot) => [slot, check!.formulas_latex[slot]]))}
                  notComputed={slots.filter((slot) => check?.not_computed.includes(slot))}
                  setExprs={setExprs} clearPreview={clearPreview} />
              );
            }) : null}
          </div>
        </details>
      ) : null}

      <Field label={t(`${V}.note`)} className="max-w-xl">
        <TextInput disabled={busy} value={note} maxLength={500} placeholder={t(`${V}.notePlaceholder`)} onChange={(e) => setNote(e.target.value)} />
      </Field>

      {/* The decision, kept in reach under a long list: check, compare, store, or throw the edit away.
          On a phone it would take a fifth of the screen, so there it sits at the end of the list. */}
      <div data-edit-actions className="z-10 flex flex-wrap items-center gap-2 border-t border-border bg-surface py-3 sm:sticky sm:bottom-0">
        <Button disabled={busy} onClick={() => void run(false)}>{t(`${V}.check`)}</Button>
        <Button disabled={busy} onClick={() => void compare()}>{t(`${V}.compareButton`)}</Button>
        <Button type="submit" variant="primary" disabled={busy || changedCount === 0}>{t(`${V}.store`)}</Button>
        <Button variant="quiet" disabled={busy} onClick={onDiscard}>{t(`${V}.discard`)}</Button>
        {changedCount ? <span data-draft-chip className="inline-flex min-h-[22px] items-center rounded-pill border border-signal-edge bg-signal-tint px-2 text-xs text-ink">{tv(`${V}.unsaved`, { count: plural(changedCount, "změna", "změny", "změn") })}</span> : null}
        {operation ? <OperationStatus key={operation} operation={operation} /> : <span className="text-xs text-ink-muted">{t(`${V}.activateHint`)}</span>}
      </div>

      {error ? <p role="alert" className="text-sm text-status-fault">{error}</p> : null}
      {check && !check.valid ? (
        <div role="alert" className="rounded-md border border-status-fault bg-status-fault-wash p-3 text-sm text-status-fault">
          <strong>{tv(`${V}.checkFailed`, { count: Object.keys(check.problems).length })}</strong>
          <ul className="mt-2 space-y-1">{Object.entries(problems).map(([path, message]) => {
            const name = owner(path);
            return <li key={path}>{name ? <button type="button" className="min-h-11 text-left underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-focus-ring" onClick={() => focusProblem(path)}>{name}: {message}</button> : <span>{path}: {message}</span>}</li>;
          })}</ul>
        </div>
      ) : null}
      {check?.valid ? (
        <div role="status" data-check-result className="rounded-md border border-signal-edge bg-signal-tint px-3.5 py-3 text-sm">
          <p>{t(`${V}.checkOk`)}</p>
          {preview.length ? (
            <div data-step-preview className="mt-2">
              <p className="text-xs font-medium text-ink-muted">{summary.preview_title_cs || t(`${V}.preview`)}</p>
              <ul className="mt-1 flex flex-col gap-1.5">
                {preview.map((line, i) => (
                  <li key={i} data-preview-status={line.status} data-preview-step={line.step_id} className="flex items-start gap-3">
                    {line.status ? <span className={`w-24 flex-none rounded-sm px-1.5 text-center text-xs font-medium leading-5 ${line.status === "FAIL" ? "bg-status-fault-wash text-status-fault" : line.status === "WARN" ? "bg-status-you-wash text-status-you-ink" : "bg-ink/10 text-ink"}`}>{t(`${V}.previewStatus.${line.status}`)}</span> : null}
                    <span>{titles[line.step_id] ? <span className="text-ink-muted">{titles[line.step_id]}: </span> : null}{line.message_cs}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </form>
  );
}

/** One parameter: its name and stage, the value it started from, and the value now, with − / +
 *  for a number. The text is the draft as typed: the domain's check reads it, nothing here clamps
 *  or rounds it (IA-1), and its problems are shown under it. */
const ParamRow = memo(function ParamRow({ row, value, original, live, reading, problems, onChange }: {
  row: Row; value: string; original: unknown; live: unknown; reading: string; problems: string[];
  onChange: (reference: string, value: string) => void;
}) {
  const { field } = row;
  const id = `mf-${field.reference}`;
  const changed = !same(original, value);
  const numeric = typeof original === "number";
  const places = numeric ? placesOf(original) : 0;
  const nudge = (direction: 1 | -1, big: boolean) => {
    const parsed = fromInput(original, value);
    if (!parsed.ok || typeof parsed.value !== "number") return;
    const next = parsed.value + direction * 10 ** -places * (big ? 10 : 1);
    // The step never takes a place the value has: 0,255 − 0,01 is 0,245, not 0,25 rounded down.
    onChange(field.reference, shown(Number(next.toFixed(Math.min(Math.max(places, placesOf(parsed.value)), 20)))));
  };
  const steppable = numeric && (() => { const parsed = fromInput(original, value); return parsed.ok && typeof parsed.value === "number"; })();
  const hintId = `${id}-hint`;
  const step = (direction: 1 | -1) => (
    <button type="button" tabIndex={-1} disabled={!steppable}
      aria-label={tv(direction > 0 ? "input.increase" : "input.decrease", { label: field.label_cs })}
      onClick={(e) => nudge(direction, e.shiftKey)}
      className={`inline-flex size-11 shrink-0 items-center justify-center text-ink-muted hover:bg-surface-sunken hover:text-ink disabled:opacity-40 disabled:hover:bg-transparent sm:size-8 ${FOCUS}`}>
      {direction > 0 ? "+" : "−"}
    </button>
  );
  const others = [live !== undefined && JSON.stringify(live) !== JSON.stringify(original) ? tv(`${V}.inForceValue`, { value: shown(live) }) : "", numeric ? t(`${V}.boundsHint`) : ""].filter(Boolean).join(" · ");
  return (
    <div data-edit-row={field.reference} data-edit-step={row.step.id} data-changed={changed || undefined}
      className={`grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-4 gap-y-1.5 border-b border-dashed border-border px-1 py-2.5 last:border-b-0 sm:grid-cols-[minmax(0,1fr)_8.75rem_13rem] ${changed ? "bg-signal-tint" : ""}`}>
      <div className="flex min-w-0 flex-col gap-0.5">
        <label htmlFor={id} className="text-sm">{field.label_cs}{field.unit ? <span className="text-ink-muted"> · {field.unit}</span> : null}</label>
        <span className="text-xs text-ink-muted">
          {row.stage}{field.effect ? <> · <span data-effect={field.effect} className={field.effect === "warns" ? "text-status-you-ink" : field.effect === "changes_stored" ? "text-signal" : "text-status-fault"}>{t(`${V}.effect.${field.effect}`)}</span></> : null}
        </span>
        {reading ? <span data-step-reading className="font-mono text-xs text-ink">{reading}</span> : null}
      </div>
      <span data-original title={t(`${V}.originalValue`)} className="min-w-0 pt-1 text-right font-mono text-xs text-ink-faint [overflow-wrap:anywhere] sm:pt-2 sm:text-left">{shown(original)}</span>
      <div className="col-span-2 flex min-w-0 flex-col gap-1 sm:col-span-1">
        {numeric ? (
          <span className={`inline-flex w-full items-stretch overflow-hidden rounded-control border focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus-ring ${problems.length ? "border-status-fault" : "border-border-strong"} bg-surface-raised`}>
            {step(-1)}
            <input id={id} data-field={field.reference} value={value} inputMode="decimal" aria-invalid={problems.length > 0} aria-describedby={hintId}
              onChange={(e) => onChange(field.reference, e.target.value)}
              onKeyDown={(e) => { if (e.key === "ArrowUp" || e.key === "ArrowDown") { e.preventDefault(); nudge(e.key === "ArrowUp" ? 1 : -1, e.shiftKey); } }}
              className="min-h-11 w-0 min-w-0 flex-1 border-x border-border bg-transparent px-1 text-center font-mono text-sm text-ink outline-none sm:min-h-8" />
            {step(1)}
          </span>
        ) : (
          <TextInput id={id} data-field={field.reference} value={value} aria-invalid={problems.length > 0} aria-describedby={others ? hintId : undefined} className="w-full font-mono"
            onChange={(e) => onChange(field.reference, e.target.value)} />
        )}
        {others ? <span id={hintId} className="text-[11px] leading-4 text-ink-faint">{others}</span> : null}
      </div>
      {problems.map((m) => <span key={m} role="alert" className="col-span-full rounded-sm bg-status-fault-wash px-2 py-1 text-xs text-status-fault">{m}</span>)}
    </div>
  );
});

/** A step's editable formulas, for the expert: each slot's expression, what it may not break and
 *  what the step keeps around it. Redrawn only when its own expressions or problems change: every
 *  keystroke would otherwise re-typeset every formula (measured 3.7 s → 5.4 s for the guided test). */
const FormulaSlots = memo(function FormulaSlots({ step, number, busy, start, titles, formulas, problems, written, notComputed, setExprs, clearPreview }: {
  step: MethodStepOut; number: string; busy: boolean; start: Start; titles: Record<string, string>;
  formulas: Record<string, string>; problems: Record<string, string>; written: Record<string, string>; notComputed: string[];
  setExprs: Dispatch<SetStateAction<Record<string, string>>>; clearPreview: () => void;
}) {
  return (
    <fieldset disabled={busy} data-edit-formula-step={step.id} className="m-0 flex min-w-0 flex-col gap-3 border-0 p-0">
      <legend className="mb-1 text-sm font-semibold">{number ? <span className="mr-2 font-mono text-xs font-normal text-ink-faint">{number}</span> : null}{titles[step.id] ?? step.title_cs}</legend>
      {step.formula_latex ? <div className="min-w-0 max-w-full overflow-x-auto text-ink"><Formula latex={step.formula_latex} /></div> : null}
      {step.formulas.map((f) => {
        const own = problemsFor(problems, `formula.${f.slot_id}`);
        const replaced = (formulas[f.slot_id] ?? "").trim() !== f.expression;
        const writtenLatex = written[f.slot_id];
        return (
          <section key={f.slot_id} data-edit-slot={f.slot_id} aria-label={`${t(`${V}.formula`)} · ${f.title_cs}`} className="flex min-w-0 flex-col rounded-md border border-border">
            <div className="flex flex-col gap-2 p-3">
              <div className="flex flex-wrap items-baseline gap-x-3">
                <h5 className="text-sm font-medium">{t(`${V}.formula`)} · {f.title_cs}</h5>
                {replaced ? <span className="text-xs font-semibold text-signal">{t(`${V}.replaced`)}</span> : null}
              </div>
              <div className="flex items-start gap-2">
                <TextArea rows={2} aria-label={`${t(`${V}.formula`)} · ${f.title_cs}`} value={formulas[f.slot_id]} aria-invalid={own.length > 0} className="!min-h-0 flex-1 font-mono"
                  onChange={(e) => { setExprs((x) => ({ ...x, [f.slot_id]: e.target.value })); clearPreview(); }} />
                {formulas[f.slot_id] !== (start.formulas[f.slot_id] ?? f.expression) ? <Button variant="quiet" className="min-h-11" onClick={() => { setExprs((x) => ({ ...x, [f.slot_id]: start.formulas[f.slot_id] ?? f.expression })); clearPreview(); }}>{t(`${V}.restore`)}</Button> : null}
              </div>
              {replaced && writtenLatex ? <div className="min-w-0 overflow-x-auto text-ink"><Formula latex={writtenLatex} /></div> : null}
              {notComputed.includes(f.slot_id) ? <span className="text-xs text-ink-muted">{t(`${V}.notComputed`)}</span> : null}
              {own.map((m) => <span key={m} role="alert" className="text-xs text-status-fault">{m}</span>)}
            </div>
            {f.variables.length ? (
              <dl aria-label={t(`${V}.variables`)} className="grid grid-cols-[minmax(0,6rem)_minmax(0,1fr)] gap-x-4 border-t border-border px-3 py-2 text-sm">
                {f.variables.map((v) => (
                  <div key={v.name} className="contents">
                    <dt className="py-1"><Formula latex={v.latex} display={false} /></dt>
                    <dd className="py-1 text-ink-muted">{v.meaning_cs}{v.unit ? ` [${v.unit}]` : ""}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
            {f.kept_cs.length ? (
              <div data-kept className="border-t border-border px-3 py-2">
                <p className="text-sm font-medium">{t(`aia.settings.methodology.kept`)}</p>
                <p className="mt-0.5 text-xs text-ink-muted">{t(`${V}.scope`)}</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm">{f.kept_cs.map((k) => <li key={k}>{k}</li>)}</ul>
              </div>
            ) : null}
            {f.properties.length ? (
              <div className="border-t border-border px-3 py-2">
                <p className="text-sm font-medium">{t(`${V}.mustHold`)}</p>
                <ul className="mt-1 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
                  {f.properties.map((pr, i) => <li key={`${pr.kind}-${i}`}>{pr.description_cs || t(`aia.settings.methodology.propertyKind.${pr.kind}`)}</li>)}
                </ul>
              </div>
            ) : null}
          </section>
        );
      })}
    </fieldset>
  );
}, (a, b) => a.busy === b.busy && a.step === b.step && a.start === b.start && a.number === b.number && a.titles === b.titles
  && JSON.stringify([a.formulas, a.problems, a.written, a.notComputed]) === JSON.stringify([b.formulas, b.problems, b.written, b.notComputed]));

/** What the editor is doing on the server, and for how long: a comparison computes maps on three
 *  panels (about 10 s; the first after a deploy, while the kernels compile, up to a minute), so after
 *  3 s the seconds count up and after 10 s it says why. The count is not announced each second. */
function OperationStatus({ operation }: { operation: "check" | "compare" | "store" }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return (
    <span data-operation={operation} className="text-xs text-ink-muted">
      <span role="status">{operation === "check" ? "Kontroluji na serveru…" : operation === "compare" ? "Porovnávám metodiky…" : "Kontroluji a ukládám novou verzi…"}</span>
      {seconds >= 3 ? <span data-elapsed aria-hidden="true"> {tv(`${V}.elapsed`, { n: seconds })}</span> : null}
      {operation === "compare" && seconds >= 10 ? <span role="status" data-compare-slow className="mt-1 block">{t(`${V}.compareSlow`)}</span> : null}
    </span>
  );
}
