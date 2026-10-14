"use client";

// The Metodika tab's versions (ADR 0023, plan S4a): what a run started now pins, every stored
// version and what it changes against the preset it came from, the activation log, and -- for
// an organization OWNER or ADMIN -- the editor: the whole specification of a preset or a stored
// version, field by field, and each formula slot as an expression. The check is the domain's
// own (POST .../check, nothing stored) and its problems are shown at the field they name.
// Storing makes a new immutable version; it is in force only once put, and then only for runs
// started afterwards. The API refuses a non-administrator whatever this page shows.

import { type Dispatch, type FormEvent, type SetStateAction, memo, useCallback, useEffect, useMemo, useRef, useState } from "react";

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
import { relative } from "@/lib/format";
import { groupSteps } from "@/lib/methodology";
import {
  type EditField,
  changedPaths,
  editableSteps,
  fromInput,
  problemsFor,
  readPath,
  toInput,
  withPath,
} from "@/lib/methodology-edit";
import { Button, Field, Select, Tag, TextArea, TextInput } from "../../rehome/ui";
import { Loaded } from "../states";
import { useResource } from "../useResource";
import { describeError } from "./errors";
import { MethodologyComparison } from "./MethodologyComparison";
import { StepContext } from "./MethodologyContext";
import { Formula } from "./MethodologyFormula";

const V = "aia.settings.methodology.versions";
const M = "aia.settings.methodology";
export type People = (id: string | null) => string;
const when = (iso: string) => relative(iso) ?? iso;

export function MethodologyVersions({ summary, people, onEditing, onDirty }: {
  summary: MethodModuleSummary; people: People;
  /** The editor is open (the read-only catalogue steps aside). */
  onEditing?: (value: boolean) => void;
  /** The open editor holds changes nothing has saved (leaving needs a decision). */
  onDirty?: (value: boolean) => void;
}) {
  const [res, retry] = useResource(() => methodology.versions(summary.id), [summary.id]);
  return <Loaded res={res} retry={retry}>{(data) => <Body summary={summary} data={data} people={people} reload={retry} onEditing={onEditing} onDirty={onDirty} />}</Loaded>;
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

function Body({ summary, data, people, reload, onEditing, onDirty }: { summary: MethodModuleSummary; data: MethodVersions; people: People; reload: () => void; onEditing?: (value: boolean) => void; onDirty?: (value: boolean) => void }) {
  const [done, setDone] = useState<{ message: string; version: MethodVersion | null } | null>(null);
  const [activating, setActivating] = useState<{ version: number | null } | null>(null);
  const presetStart = (name: string): Start => ({ base: name, spec: data.presets[name] ?? {}, formulas: {}, from: name });
  const versionStart = (v: MethodVersion): Start => ({ base: v.base_preset, spec: v.spec, formulas: v.formulas, from: v.name });
  // An edit starts from what is in force (product owner, 2026-10-13): the stored version in force,
  // else the code's newest preset, which computes what the code's preset in force computes byte for
  // byte and declares the constants that preset keeps in code, so an edit can move them (f588045c).
  const editStart = (): Start => {
    const stored = data.in_force.origin === "stored" ? data.versions.find((v) => v.version_number === data.in_force.version_number) : undefined;
    const from = stored ? versionStart(stored) : presetStart(summary.presets[0] ?? summary.in_force ?? "");
    return { ...from, inForce: data.in_force.name };
  };
  // The methodologists who may edit open on the editor (product owner, 2026-10-13).
  const [start, setStart] = useState<Start | null>(() => (data.may_administer ? editStart() : null));
  const opened = useRef(start !== null);
  useEffect(() => {
    if (!opened.current) return;
    opened.current = false;
    onEditing?.(true);
  }, [onEditing]);
  const [dirty, setDirty] = useState(false);
  useEffect(() => { onDirty?.(start !== null && dirty); }, [start, dirty, onDirty]);
  const [pending, setPending] = useState<{ next: Start | null } | null>(null);
  const changeStart = (asked: Start | null) => {
    const next = asked && { ...asked, byPerson: true };
    if (start && dirty) { setPending({ next }); return; }
    setStart(next); setDirty(false); onEditing?.(next !== null);
  };
  const inForce = data.in_force;
  const currentSpec = inForce.origin === "stored"
    ? data.versions.find((version) => version.version_number === inForce.version_number)?.spec
    : data.presets[inForce.preset ?? summary.in_force ?? ""];
  return (
    <section aria-labelledby={`mv-${summary.id}`} data-methodology-versions={summary.id} className="flex flex-col gap-3 rounded-md border border-border bg-surface-raised p-4">
      <h3 id={`mv-${summary.id}`} className="text-sm font-semibold">{t(`${V}.title`)}</h3>
      <p data-in-force className="text-sm">
        {t(`${V}.inForce`)}: <strong className="font-mono">{inForce.name}</strong>{" "}
        <Tag>{t(`${V}.origin.${inForce.origin}`)}</Tag>
      </p>
      {start ? null : <p className="max-w-3xl text-xs leading-5 text-ink-muted">{t(`${V}.pinNote`)}</p>}
      {pending ? <InlineConfirm message={t(`${V}.replaceDraft`)} action={t(`${V}.discardDraft`)} onCancel={() => setPending(null)} onConfirm={() => { setStart(pending.next); onEditing?.(pending.next !== null); setDirty(false); setPending(null); }} /> : null}
      {data.may_administer ? null : <p className="text-xs text-ink-muted">{t(`${V}.adminNote`)}</p>}
      {done ? (
        <div role="status" className="flex flex-wrap items-center gap-3 text-sm">
          <span>{done.message}</span>
          {done.version && data.may_administer && !activating ? <Button small variant="primary" onClick={() => setActivating({ version: done.version!.version_number })}>{tv(`${V}.activate`, { name: done.version.name })}</Button> : null}
        </div>
      ) : null}
      {data.may_administer && start ? (
        <Editor
          key={`${start.from}`}
          summary={summary}
          start={start}
          currentSpec={currentSpec}
          currentName={inForce.name}
          presets={Object.keys(data.presets)}
          onBase={(name) => changeStart(presetStart(name))}
          onDirty={setDirty}
          onCancel={() => changeStart(null)}
          onSaved={(saved) => { setStart(null); setDirty(false); onEditing?.(false); setDone({ message: tv(`${V}.saved`, { name: saved.name }), version: saved }); reload(); }}
        />
      ) : null}

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
                    {inForce.version_number === v.version_number ? <Tag>{t(`${V}.current`)}</Tag> : null}
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
                    {data.may_administer && inForce.version_number !== v.version_number && done?.version?.version_number !== v.version_number ? (
                      <Button small disabled={start !== null && dirty} onClick={() => { setDone(null); setActivating({ version: v.version_number }); }}>{tv(`${V}.activate`, { name: v.name })}</Button>
                    ) : null}
                    {data.may_administer ? <Button small onClick={() => { setDone(null); changeStart(versionStart(v)); }}>{t(`${V}.editFrom`)}</Button> : null}
                  </div>
                </li>
              );
            })}
          </ul>
        ) : <p className="mt-1 text-sm text-ink-muted">{t(`${V}.none`)}</p>}
      </div>

      {data.may_administer && inForce.origin === "stored" ? (
        <div><Button small disabled={start !== null && dirty} onClick={() => { setDone(null); setActivating({ version: null }); }}>{tv(`${V}.reset`, { preset: summary.in_force ?? "" })}</Button></div>
      ) : null}
      {activating ? (
        <Activate
          moduleId={summary.id}
          version={activating.version}
          name={activating.version === null ? (summary.in_force ?? "") : (data.versions.find((v) => v.version_number === activating.version)?.name ?? "")}
          onCancel={() => setActivating(null)}
          onDone={() => { setActivating(null); setDone({ message: t(`${V}.activated`), version: null }); reload(); }}
        />
      ) : null}

      {data.may_administer && !start ? <div><Button variant="primary" small onClick={() => { setDone(null); changeStart(editStart()); }}>{t(`${V}.edit`)}</Button></div> : null}

      <details>
        <summary className="cursor-pointer text-sm font-semibold">{t(`${V}.history`)}</summary>
        {data.history.length ? (
          <ul className="mt-1 flex flex-col gap-1 text-sm">
            {data.history.map((h) => (
              <li key={h.activation_id} data-methodology-activation={h.activation_id}>
                <strong className="font-mono">{h.version_number === null ? tv(`${V}.backToPreset`, { preset: summary.in_force ?? "" }) : `e${h.version_number}`}</strong>
                {" "}· {people(h.activated_by)} · {when(h.activated_at)}
                {h.reason ? <span className="text-ink-muted"> — {h.reason}</span> : null}
              </li>
            ))}
          </ul>
        ) : <p className="mt-1 text-sm text-ink-muted">{t(`${V}.noHistory`)}</p>}
      </details>
    </section>
  );
}

function Activate({ moduleId, version, name, onCancel, onDone }: { moduleId: string; version: number | null; name: string; onCancel: () => void; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const go = async () => {
    setBusy(true);
    setError(null);
    try {
      await methodology.activate(moduleId, version, reason.trim());
      onDone();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div data-methodology-activate className="flex flex-col gap-2 rounded-sm border border-border p-3">
      <h4 className="text-sm font-semibold">{tv(version === null ? `${V}.resetTitle` : `${V}.activateTitle`, { name })}</h4>
      <p className="text-xs text-ink-muted">{t(`${V}.pinNote`)}</p>
      <Field label={t(`${V}.reason`)}>
        <TextInput value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} />
      </Field>
      {error ? <p role="alert" className="text-sm text-status-fault">{error}</p> : null}
      <div className="flex gap-2">
        <Button variant="primary" disabled={busy} onClick={() => void go()}>{t(`${V}.confirm`)}</Button>
        <Button disabled={busy} onClick={onCancel}>{t(`${V}.cancel`)}</Button>
      </div>
    </div>
  );
}

function Editor(props: {
  summary: MethodModuleSummary; start: Start; presets: string[]; currentSpec?: Record<string, unknown>; currentName: string;
  onBase: (name: string) => void; onDirty: (value: boolean) => void; onCancel: () => void; onSaved: (v: MethodVersion) => void;
}) {
  // The labels and slots of the preset the edit is based on; the values come from `start`.
  const [res, retry] = useResource(() => methodology.get(props.summary.id, props.start.base), [props.summary.id, props.start.base]);
  return <Loaded res={res} retry={retry}>{(detail) => <EditorForm {...props} detail={detail} />}</Loaded>;
}

function EditorForm({ summary, start, presets, detail, currentSpec, onBase, onDirty, onCancel, onSaved }: {
  summary: MethodModuleSummary; start: Start; presets: string[]; detail: MethodModuleDetail; currentSpec?: Record<string, unknown>; currentName: string;
  onBase: (name: string) => void; onDirty: (value: boolean) => void; onCancel: () => void; onSaved: (v: MethodVersion) => void;
}) {
  const steps = useMemo(() => editableSteps(detail), [detail]);
  const builtin = useMemo(() => new Map(steps.flatMap(({ step }) => step.formulas.map((f) => [f.slot_id, f.expression] as const))), [steps]);
  const [raw, setRaw] = useState<Record<string, string>>(() =>
    Object.fromEntries(steps.flatMap(({ fields }) => fields.map((f) => [f.reference, toInput(readPath(start.spec, f.reference))]))),
  );
  const [exprs, setExprs] = useState<Record<string, string>>(() =>
    Object.fromEntries([...builtin].map(([slot, expr]) => [slot, start.formulas[slot] ?? expr])),
  );
  const [note, setNote] = useState("");
  const [check, setCheck] = useState<MethodCheck | null>(null);
  const [comparison, setComparison] = useState<MethodCompare | null>(null);
  const [operation, setOperation] = useState<"check" | "compare" | "store" | null>(null);
  const busy = operation !== null;
  const [error, setError] = useState<string | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  // Read once: only an edit a person asked for moves the page to itself.
  const focusOnOpen = useRef(start.byPerson === true);

  useEffect(() => {
    // Starting an edit moves the person to the focused block, especially on a
    // phone where the methodology summary is taller than one viewport.
    if (!focusOnOpen.current) return;
    headingRef.current?.scrollIntoView?.({ block: "start" });
    headingRef.current?.focus({ preventScroll: true });
  }, []);

  const router = useRouter();
  const [selectedStep, setSelectedStep] = useState(steps[0]?.step.id ?? "");
  const grouped = useMemo(() => groupSteps(detail).map(({ group, steps: groupItems }) => ({ group, items: groupItems.map((item) => steps.find(({ step }) => step.id === item.id)).filter((item): item is (typeof steps)[number] => item !== undefined) })).filter(({ items }) => items.length), [detail, steps]);
  // Where each step sits: its stage, every step's title for the context's links, and the audit
  // points AIA does not compute yet (empty groups, listed after the outline).
  const titles = useMemo(() => Object.fromEntries(detail.step_details.map((s) => [s.id, s.title_cs])), [detail]);
  const stageOf = useMemo(() => new Map(groupSteps(detail).flatMap(({ group, steps: groupItems }) => group ? groupItems.map((item) => [item.id, group.title_cs] as const) : [])), [detail]);
  const notYet = useMemo(() => groupSteps(detail).filter(({ group, steps: groupItems }) => group && !groupItems.length).map(({ group }) => group!.title_cs.replace(/^Zatím v AIA není:\s*/, "")), [detail]);
  const [leaveHref, setLeaveHref] = useState<string | null>(null);
  const changedCount = Object.keys(raw).filter((r) => raw[r] !== toInput(readPath(start.spec, r))).length + [...builtin.keys()].filter((slot) => exprs[slot] !== (start.formulas[slot] ?? builtin.get(slot))).length;
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
  const clearPreview = useCallback(() => { setCheck(null); setComparison(null); setError(null); }, []);
  const showFirstProblem = (problems: Record<string, string>) => {
    const first = steps.find(({ step, fields }) => fields.some((f) => problemsFor(problems, `spec.${f.reference}`).length) || step.formulas.some((f) => problemsFor(problems, `formula.${f.slot_id}`).length));
    if (first) setSelectedStep(first.step.id);
  };

  // The whole edit, or the fields the page itself cannot read (a word where a number was).
  const build = (): { edit: { base_preset: string; spec: Record<string, unknown>; formulas: Record<string, string> } } | { local: Record<string, string> } => {
    let spec = start.spec;
    const local: Record<string, string> = {};
    for (const [reference, text] of Object.entries(raw)) {
      const parsed = fromInput(readPath(start.spec, reference), text);
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
    if ("local" in built) {
      setCheck({ valid: false, problems: built.local, not_computed: [], formulas_latex: {} }); showFirstProblem(built.local);
      return;
    }
    setOperation(store ? "store" : "check");
    try {
      const checked = await methodology.check(summary.id, built.edit);
      setCheck(checked); showFirstProblem(checked.problems);
      if (store && checked.valid) onSaved(await methodology.propose(summary.id, { ...built.edit, note: note.trim() }));
    } catch (e) {
      setError(describeError(e));
    } finally {
      setOperation(null);
    }
  };
  // The edit beside what is in force on fictional panels; a refused edit shows its problems.
  const compare = async () => {
    setError(null);
    setComparison(null);
    const built = build();
    if ("local" in built) {
      setCheck({ valid: false, problems: built.local, not_computed: [], formulas_latex: {} }); showFirstProblem(built.local);
      return;
    }
    setOperation("compare");
    try {
      const result = await methodology.compare(summary.id, built.edit);
      if (result.valid) setComparison(result);
      else { setCheck({ valid: false, problems: result.problems, not_computed: [], formulas_latex: {} }); showFirstProblem(result.problems); }
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
  const problemLinks = Object.entries(problems).map(([path, message]) => {
    const owner = steps.find(({ step, fields }) => fields.some((field) => path === `spec.${field.reference}` || path.startsWith(`spec.${field.reference}.`)) || step.formulas.some((formula) => path === `formula.${formula.slot_id}` || path.startsWith(`formula.${formula.slot_id}.`)));
    return { path, message, owner };
  });
  const fieldChanged = (reference: string) => raw[reference] !== toInput(readPath(start.spec, reference));
  const slotChanged = (slot: string) => exprs[slot] !== (start.formulas[slot] ?? builtin.get(slot));
  const stepState = ({ step, fields }: (typeof steps)[number]) => ({
    changes: fields.filter((f) => fieldChanged(f.reference)).length + step.formulas.filter((f) => slotChanged(f.slot_id)).length,
    problems: fields.some((f) => problemsFor(problems, `spec.${f.reference}`).length) || step.formulas.some((f) => problemsFor(problems, `formula.${f.slot_id}`).length),
  });
  // What the draft changes, in words: a field's old and new value, a formula's title.
  const draftChanges = steps.flatMap(({ step, fields }) => [
    ...fields.filter((f) => fieldChanged(f.reference)).map((f) => ({ key: f.reference, label: f.label_cs, from: toInput(readPath(start.spec, f.reference)), to: raw[f.reference] })),
    ...step.formulas.filter((f) => slotChanged(f.slot_id)).map((f) => ({ key: f.slot_id, label: f.title_cs, from: null, to: null })),
  ]);
  const flow: { key: string; label: string; note: string; state: "done" | "now" | "todo" | "fault" }[] = [
    { key: "edit", label: t(`${V}.flow.edit`), note: changedCount ? tv(`${V}.flowEdits`, { count: changedCount }) : "", state: check ? "done" : "now" },
    { key: "check", label: t(`${V}.flow.check`), note: check ? (check.valid ? t(`${V}.flowPassed`) : tv(`${V}.flowProblems`, { count: Object.keys(check.problems).length })) : "", state: check ? (check.valid ? "done" : "fault") : "todo" },
    { key: "compare", label: t(`${V}.flow.compare`), note: comparison ? t(`${V}.flowDone`) : "", state: comparison ? "done" : check?.valid ? "now" : "todo" },
    { key: "store", label: t(`${V}.flow.store`), note: "", state: comparison ? "now" : "todo" },
    { key: "activate", label: t(`${V}.flow.activate`), note: "", state: "todo" },
  ];
  const FLOW_LOOK = { done: "text-ink", now: "font-semibold text-signal", todo: "text-ink-faint", fault: "font-semibold text-status-fault" } as const;
  const DOT_LOOK = { done: "border-ink bg-ink text-surface-raised", now: "border-signal bg-surface-raised text-signal", todo: "border-border-strong text-ink-faint", fault: "border-status-fault bg-status-fault-wash text-status-fault" } as const;
  return (
    <form data-methodology-editor aria-label={t(`${V}.editorLabel`)} onSubmit={submit} className="flex min-w-0 max-w-full flex-col gap-4">
      {leaveHref ? <InlineConfirm message={t(`${V}.replaceDraft`)} action={t(`${V}.discardDraft`)} onCancel={() => setLeaveHref(null)} onConfirm={() => router.push(leaveHref)} /> : null}

      {/* What is being edited, and where the change stands in the safe sequence. */}
      <div className="flex flex-col gap-3 border-b border-border pb-3">
        <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
          <div className="mr-auto flex min-w-0 flex-col gap-0.5">
            <h4 ref={headingRef} tabIndex={-1} className="scroll-mt-24 text-base font-semibold">{start.inForce ? tv(`${V}.editorInForce`, { name: start.inForce }) : tv(`${V}.editorTitle`, { from: start.from })}</h4>
            {start.inForce && start.base !== start.inForce && start.from === start.base ? <p data-start-note className="max-w-2xl text-sm text-ink-muted">{tv(`${V}.editorSameAs`, { base: start.base, name: start.inForce })}</p> : null}
          </div>
          {presets.length > 1 ? (
            <Field label={t(`${V}.base`)} className="w-56">
              <Select aria-label={t(`${V}.base`)} disabled={busy} value={!start.inForce && start.from === start.base ? start.base : ""} onChange={(e) => e.target.value && onBase(e.target.value)}>
                {!start.inForce && start.from === start.base ? null : <option value="">{start.inForce ? t(`${V}.inForceOption`) : start.from}</option>}
                {presets.map((p) => <option key={p} value={p}>{p}</option>)}
              </Select>
            </Field>
          ) : null}
          <Button disabled={busy} onClick={onCancel}>{t(`${V}.cancel`)}</Button>
        </div>
        <ol aria-label={t(`${V}.flowLabel`)} data-methodology-flow className="flex flex-wrap items-center gap-y-2">
          {flow.map((f, i) => (
            <li key={f.key} data-flow-step={f.key} data-state={f.state} className={`flex items-center gap-2 pr-4 text-[13px] ${i ? "border-l border-border pl-4" : ""} ${FLOW_LOOK[f.state]}`}>
              <span aria-hidden="true" className={`inline-flex size-5 items-center justify-center rounded-full border font-mono text-[11px] ${DOT_LOOK[f.state]}`}>{i + 1}</span>
              {f.label}
              {f.note ? <span className="font-normal text-ink-muted">· {f.note}</span> : null}
            </li>
          ))}
        </ol>
      </div>

      {check && !check.valid ? <div role="alert" className="rounded-md border border-status-fault bg-status-fault-wash p-3 text-sm text-status-fault"><strong>{tv(`${V}.checkFailed`, { count: Object.keys(check.problems).length })}</strong><ul className="mt-2 space-y-1">{problemLinks.map(({ path, message, owner }) => <li key={path}>{owner ? <button type="button" className="min-h-11 text-left underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-focus-ring" onClick={() => {
          setSelectedStep(owner.step.id);
          requestAnimationFrame(() => { const target = [...document.querySelectorAll<HTMLElement>("[data-field], [data-edit-slot] textarea")].find((node) => path.includes(node.getAttribute("data-field") ?? node.closest("[data-edit-slot]")?.getAttribute("data-edit-slot") ?? "____")); target?.focus(); });
        }}>{owner.step.title_cs}: {message}</button> : <span>{path}: {message}</span>}</li>)}</ul></div> : null}

      <div className="grid min-w-0 gap-6 lg:grid-cols-[13rem_minmax(0,1fr)] 2xl:grid-cols-[13rem_minmax(0,1fr)_17rem]">
        {/* The calculation in its order: a group, then its steps. */}
        <nav aria-label={t(`${V}.outline`)} data-methodology-outline className="flex min-w-0 flex-col gap-3 lg:sticky lg:top-24 lg:max-h-[calc(100vh-7rem)] lg:self-start lg:overflow-y-auto">
          {grouped.map(({ group, items }) => (
            <div key={group?.id ?? "other"}>
              <p className="px-2 pb-1 text-xs font-semibold text-ink-faint">{group?.title_cs ?? "Další kroky"}</p>
              <ul className="flex flex-col gap-0.5">
                {items.map((item) => {
                  const state = stepState(item);
                  const on = item.step.id === selectedStep;
                  return (
                    <li key={item.step.id}>
                      <button
                        type="button"
                        data-edit-step-link={item.step.id}
                        aria-current={on ? "step" : undefined}
                        onClick={() => setSelectedStep(item.step.id)}
                        className={`flex min-h-9 w-full items-center gap-2 rounded-sm px-2 py-1 text-left text-[13px] leading-[18px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${on ? "bg-signal-wash font-semibold text-signal" : "text-ink hover:bg-surface-sunken"}`}
                      >
                        <span className="min-w-0 flex-1">{item.step.title_cs}</span>
                        {item.step.audit ? <span className="shrink-0 font-mono text-[11px] font-normal text-ink-faint">{item.step.audit}</span> : null}
                        {state.problems ? <span className="shrink-0 rounded-sm bg-status-fault-wash px-1 text-[11px] font-semibold text-status-fault">{t(`${V}.stepProblems`)}</span>
                          : state.changes ? <span className="size-2 shrink-0 rounded-full bg-signal" aria-label={tv(`${V}.stepChanges`, { count: state.changes })} /> : null}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
          {notYet.length ? (
            <div data-not-yet className="border-t border-border pt-3">
              <p className="px-2 pb-1 text-xs font-semibold text-ink-faint">{t(`${M}.notYet`)}</p>
              <ul className="flex flex-col gap-0.5 px-2 text-xs leading-5 text-ink-muted">
                {notYet.map((title) => <li key={title}>{title}</li>)}
              </ul>
            </div>
          ) : null}
        </nav>

        {/* The step: its formula first, each formula as written, then the parameters it reads. */}
        <div className="flex min-w-0 flex-col gap-4">
          {steps.map(({ step, fields }) => {
            const slots = step.formulas.map((f) => f.slot_id);
            const own = Object.fromEntries(Object.entries(problems).filter(([k]) => fields.some((f) => k === `spec.${f.reference}` || k.startsWith(`spec.${f.reference}.`)) || slots.some((slot) => k === `formula.${slot}` || k.startsWith(`formula.${slot}.`))));
            const values = Object.fromEntries(fields.map((f) => [f.reference, raw[f.reference]]));
            const formulas = Object.fromEntries(slots.map((slot) => [slot, exprs[slot]]));
            const written = Object.fromEntries(slots.filter((slot) => check?.formulas_latex[slot]).map((slot) => [slot, check!.formulas_latex[slot]]));
            const notComputed = slots.filter((slot) => check?.not_computed.includes(slot));
            return (
              <StepEditor
                key={step.id}
                step={step}
                fields={fields}
                hidden={selectedStep !== step.id}
                busy={busy}
                start={start}
                currentSpec={currentSpec}
                values={values}
                formulas={formulas}
                problems={own}
                written={written}
                notComputed={notComputed}
                setRaw={setRaw}
                setExprs={setExprs}
                clearPreview={clearPreview}
                stage={stageOf.get(step.id) ?? ""}
                titles={titles}
                onPick={setSelectedStep}
                signature={JSON.stringify([selectedStep === step.id, busy, values, formulas, own, written, notComputed])}
              />
            );
          })}
          {comparison ? <MethodologyComparison result={comparison} /> : null}
        </div>

        {/* Impact and the decision, in the safe order. */}
        <aside aria-label={t(`${V}.decision`)} className="flex min-w-0 flex-col gap-4 rounded-card border border-border bg-surface-raised p-4 lg:order-first lg:col-span-2 lg:grid lg:grid-cols-3 lg:items-start lg:gap-6 2xl:sticky 2xl:top-24 2xl:order-none 2xl:col-span-1 2xl:flex 2xl:self-start 2xl:gap-4">
          <div>
            <h5 className="text-sm font-semibold">{t(`${V}.draftChanges`)}</h5>
            {draftChanges.length ? (
              <ul className="mt-1 flex flex-col gap-1 text-sm">
                {draftChanges.map((c) => (
                  <li key={c.key} className="flex flex-wrap justify-between gap-x-3">
                    <span>{c.label}</span>
                    <span className="font-mono text-ink-muted">{c.from === null ? t(`${V}.formulaEdited`) : <>{c.from} → <b className="font-semibold text-ink">{c.to}</b></>}</span>
                  </li>
                ))}
              </ul>
            ) : <p className="mt-1 text-sm text-ink-muted">{t(`${V}.noDraftChanges`)}</p>}
          </div>
          <div className="flex flex-col gap-2 border-t border-border pt-3 lg:border-t-0 lg:pt-0 2xl:border-t 2xl:pt-3">
            {check?.valid ? <p role="status" className="text-sm text-ink">{t(`${V}.checkOk`)}</p> : null}
            {error ? <p role="alert" className="text-sm text-status-fault">{error}</p> : null}
            <Button className="w-full justify-center" disabled={busy} onClick={() => void run(false)}>{t(`${V}.check`)}</Button>
            <Button className="w-full justify-center !whitespace-normal" disabled={busy} onClick={() => void compare()}>{t(`${V}.compareButton`)}</Button>
          </div>
          <div className="flex flex-col gap-2 border-t border-border pt-3 lg:border-t-0 lg:pt-0 2xl:border-t 2xl:pt-3">
            <Field label={t(`${V}.note`)}>
              <TextInput disabled={busy} value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
            </Field>
            <Button className="min-h-11 w-full justify-center" type="submit" variant="primary" disabled={busy}>{t(`${V}.store`)}</Button>
            {operation ? <span role="status" className="text-xs text-ink-muted">{operation === "check" ? "Kontroluji na serveru…" : operation === "compare" ? "Porovnávám metodiky…" : "Kontroluji a ukládám novou verzi…"}</span> : null}
            <p className="text-xs leading-5 text-ink-muted">{t(`${V}.activateHint`)}</p>
          </div>
        </aside>
      </div>
    </form>
  );
}

/** One step of the editor, redrawn only when its own values, problems or visibility change:
 *  every keystroke would otherwise re-typeset every step's formulas (measured: the guided test
 *  went from 3.7 s to 5.4 s before this split). */
const StepEditor = memo(function StepEditor({ step, fields, hidden, busy, start, currentSpec, values, formulas, problems, written, notComputed, setRaw, setExprs, clearPreview, stage, titles, onPick }: {
  step: MethodStepOut; fields: EditField[]; hidden: boolean; busy: boolean; start: Start; currentSpec?: Record<string, unknown>;
  values: Record<string, string>; formulas: Record<string, string>; problems: Record<string, string>;
  written: Record<string, string>; notComputed: string[];
  setRaw: Dispatch<SetStateAction<Record<string, string>>>; setExprs: Dispatch<SetStateAction<Record<string, string>>>; clearPreview: () => void;
  /** The step's stage, every step's title and the move to another step: its place in the computation. */
  stage: string; titles: Record<string, string>; onPick: (stepId: string) => void;
  /** Everything above that can change, as one value: the memo compares this alone. */
  signature: string;
}) {
  return (
            <fieldset key={step.id} hidden={hidden} disabled={busy} data-edit-step={step.id} className="flex min-w-0 max-w-full flex-col gap-4">
      <legend className="mb-1 text-lg font-semibold leading-[26px]">{step.title_cs}</legend>
      {stage || step.audit ? <p data-step-stage className="text-xs text-ink-faint">{stage}{stage && step.audit ? " · " : ""}{step.audit ? <span className="font-mono">{tv(`${M}.audit`, { point: step.audit })}</span> : null}</p> : null}
      {step.note_cs ? <p className="max-w-3xl text-sm leading-6 text-ink-muted">{step.note_cs}</p> : null}
      {hidden ? null : <StepContext step={step} titles={titles} onPick={onPick} />}
      {step.formula_latex && !hidden ? <div className="min-w-0 max-w-full overflow-x-auto rounded-card border border-border bg-surface-raised px-6 py-5 text-center text-lg text-ink"><Formula latex={step.formula_latex} /></div> : null}

      {step.formulas.map((f) => {
        const own = problemsFor(problems, `formula.${f.slot_id}`);
        const replaced = (formulas[f.slot_id] ?? "").trim() !== f.expression;
        const writtenLatex = written[f.slot_id];
        return (
          <section key={f.slot_id} data-edit-slot={f.slot_id} aria-label={`${t(`${V}.formula`)} · ${f.title_cs}`} className="flex min-w-0 flex-col rounded-card border border-border bg-surface-raised">
            <div className="flex flex-col gap-2 p-4">
              <div className="flex flex-wrap items-baseline gap-x-3">
                <h5 className="text-sm font-semibold">{t(`${V}.formula`)} · {f.title_cs}</h5>
                {replaced ? <span className="text-xs font-semibold text-signal">{t(`${V}.replaced`)}</span> : null}
              </div>
              <div className="flex items-start gap-2">
                <TextArea
                  rows={2}
                  aria-label={`${t(`${V}.formula`)} · ${f.title_cs}`}
                  value={formulas[f.slot_id]}
                  aria-invalid={own.length > 0}
                  className="!min-h-0 flex-1 font-mono"
                  onChange={(e) => { setExprs((x) => ({ ...x, [f.slot_id]: e.target.value })); clearPreview(); }}
                />
                {formulas[f.slot_id] !== (start.formulas[f.slot_id] ?? f.expression) ? <Button variant="quiet" className="min-h-11" onClick={() => { setExprs((x) => ({ ...x, [f.slot_id]: start.formulas[f.slot_id] ?? f.expression })); clearPreview(); }}>{t(`${V}.restore`)}</Button> : null}
              </div>
              {replaced && writtenLatex && !hidden ? <div className="text-ink"><Formula latex={writtenLatex} /></div> : null}
              {notComputed.includes(f.slot_id) ? <span className="text-xs text-ink-muted">{t(`${V}.notComputed`)}</span> : null}
              {own.map((m) => <span key={m} role="alert" className="text-xs text-status-fault">{m}</span>)}
            </div>
            {f.variables.length && !hidden ? (
              <dl aria-label={t(`${V}.variables`)} className="grid grid-cols-[minmax(0,6rem)_minmax(0,1fr)] gap-x-4 border-t border-border px-4 py-3 text-sm">
                {f.variables.map((v) => (
                  <div key={v.name} className="contents">
                    <dt className="py-1"><Formula latex={v.latex} display={false} /></dt>
                    <dd className="py-1 text-ink-muted">{v.meaning_cs}{v.unit ? ` [${v.unit}]` : ""}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
            {f.properties.length && !hidden ? (
              <div className="border-t border-border px-4 py-3">
                <p className="text-sm font-semibold">{t(`${V}.mustHold`)}</p>
                <ul className="mt-1 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
                  {f.properties.map((pr, i) => <li key={`${pr.kind}-${i}`}>{pr.description_cs || t(`aia.settings.methodology.propertyKind.${pr.kind}`)}</li>)}
                </ul>
              </div>
            ) : null}
          </section>
        );
      })}

      {fields.length ? (
        <section aria-label={t(`${V}.parameters`)} className="rounded-card border border-border bg-surface-raised px-4">
          {fields.map((f, i) => {
            const own = problemsFor(problems, `spec.${f.reference}`);
            const original = toInput(readPath(start.spec, f.reference));
            const live = currentSpec ? readPath(currentSpec, f.reference) : undefined;
            return (
              <div key={f.reference} className={`grid items-start gap-x-4 gap-y-1 py-3 sm:grid-cols-[minmax(0,1fr)_14rem] ${i ? "border-t border-border" : ""}`}>
                <label htmlFor={`mf-${f.reference}`} className="pt-2 text-sm font-medium">{f.label_cs}{f.unit ? <span className="font-normal text-ink-muted"> · {f.unit}</span> : null}</label>
                <div className="flex flex-col gap-1">
                  <TextInput
                    id={`mf-${f.reference}`}
                    value={values[f.reference]}
                    aria-invalid={own.length > 0}
                    data-field={f.reference}
                    className="w-full font-mono"
                    inputMode={typeof readPath(start.spec, f.reference) === "number" ? "decimal" : undefined}
                    onChange={(e) => { setRaw((r) => ({ ...r, [f.reference]: e.target.value })); clearPreview(); }}
                  />
                  <span className={`text-xs ${(values[f.reference] !== original) ? "font-medium text-signal" : "text-ink-muted"}`}>
                    {(values[f.reference] !== original) ? `${t(`${V}.changed`)} · ${tv(`${V}.originalWas`, { value: original })}` : live === undefined ? tv(`${V}.originalWas`, { value: original }) : tv(`${V}.inForceValue`, { value: toInput(live) })}
                  </span>
                  {own.map((m) => <span key={m} role="alert" className="text-xs text-status-fault">{m}</span>)}
                </div>
              </div>
            );
          })}
        </section>
      ) : null}
    </fieldset>
  );
}, (a, b) => a.signature === b.signature && a.stage === b.stage && a.titles === b.titles && a.step === b.step && a.start === b.start && a.currentSpec === b.currentSpec);
