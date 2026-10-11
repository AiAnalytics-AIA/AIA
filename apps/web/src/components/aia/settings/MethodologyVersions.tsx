"use client";

// The Metodika tab's versions (ADR 0023, plan S4a): what a run started now pins, every stored
// version and what it changes against the preset it came from, the activation log, and -- for
// an organization OWNER or ADMIN -- the editor: the whole specification of a preset or a stored
// version, field by field, and each formula slot as an expression. The check is the domain's
// own (POST .../check, nothing stored) and its problems are shown at the field they name.
// Storing makes a new immutable version; it is in force only once put, and then only for runs
// started afterwards. The API refuses a non-administrator whatever this page shows.

import { type FormEvent, useMemo, useState } from "react";

import { t, tv } from "@/i18n/t";
import {
  type MethodCheck,
  type MethodModuleDetail,
  type MethodModuleSummary,
  type MethodVersion,
  type MethodVersions,
  methodology,
} from "@/lib/api";
import { relative } from "@/lib/format";
import {
  changedPaths,
  editableSteps,
  fromInput,
  problemsFor,
  readPath,
  toInput,
  unplacedProblems,
  withPath,
} from "@/lib/methodology-edit";
import { Button, Field, Select, Tag, TextArea, TextInput } from "../../rehome/ui";
import { Loaded } from "../states";
import { useResource } from "../useResource";
import { describeError } from "./errors";
import { Formula } from "./MethodologyFormula";

const V = "aia.settings.methodology.versions";
export type People = (id: string | null) => string;
const when = (iso: string) => relative(iso) ?? iso;

export function MethodologyVersions({ summary, people }: { summary: MethodModuleSummary; people: People }) {
  const [res, retry] = useResource(() => methodology.versions(summary.id), [summary.id]);
  return <Loaded res={res} retry={retry}>{(data) => <Body summary={summary} data={data} people={people} reload={retry} />}</Loaded>;
}

/** Where an edit starts: a code preset, or a stored version (its spec and its formulas). */
type Start = { base: string; spec: Record<string, unknown>; formulas: Record<string, string>; from: string };

function Body({ summary, data, people, reload }: { summary: MethodModuleSummary; data: MethodVersions; people: People; reload: () => void }) {
  const [done, setDone] = useState<string | null>(null);
  const [activating, setActivating] = useState<{ version: number | null } | null>(null);
  const [start, setStart] = useState<Start | null>(null);
  const inForce = data.in_force;
  const presetStart = (name: string): Start => ({ base: name, spec: data.presets[name] ?? {}, formulas: {}, from: name });
  const versionStart = (v: MethodVersion): Start => ({ base: v.base_preset, spec: v.spec, formulas: v.formulas, from: v.name });
  return (
    <section aria-labelledby={`mv-${summary.id}`} data-methodology-versions={summary.id} className="flex flex-col gap-3 rounded-md border border-border bg-surface-raised p-4">
      <h3 id={`mv-${summary.id}`} className="text-sm font-semibold">{t(`${V}.title`)}</h3>
      <p data-in-force className="text-sm">
        {t(`${V}.inForce`)}: <strong className="font-mono">{inForce.name}</strong>{" "}
        <Tag>{t(`${V}.origin.${inForce.origin}`)}</Tag>
      </p>
      <p className="max-w-3xl text-xs text-ink-muted">{t(`${V}.pinNote`)}</p>
      {data.may_administer ? null : <p className="text-xs text-ink-muted">{t(`${V}.adminNote`)}</p>}
      {done ? <p role="status" className="text-sm text-status-done">{done}</p> : null}

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
                  <p className="text-xs">
                    {changed.length || formulas.length ? (
                      <>
                        {tv(`${V}.changes`, { base: v.base_preset })}{" "}
                        <span className="font-mono">{[...changed, ...formulas.map((f) => `ƒ ${f}`)].join(", ")}</span>
                      </>
                    ) : tv(`${V}.noChanges`, { base: v.base_preset })}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {data.may_administer && inForce.version_number !== v.version_number ? (
                      <Button small onClick={() => { setDone(null); setActivating({ version: v.version_number }); }}>{tv(`${V}.activate`, { name: v.name })}</Button>
                    ) : null}
                    {data.may_administer ? <Button small onClick={() => { setDone(null); setStart(versionStart(v)); }}>{t(`${V}.editFrom`)}</Button> : null}
                  </div>
                </li>
              );
            })}
          </ul>
        ) : <p className="mt-1 text-sm text-ink-muted">{t(`${V}.none`)}</p>}
      </div>

      {data.may_administer && inForce.origin === "stored" ? (
        <div><Button small onClick={() => { setDone(null); setActivating({ version: null }); }}>{tv(`${V}.reset`, { preset: summary.in_force ?? "" })}</Button></div>
      ) : null}
      {activating ? (
        <Activate
          moduleId={summary.id}
          version={activating.version}
          name={activating.version === null ? (summary.in_force ?? "") : (data.versions.find((v) => v.version_number === activating.version)?.name ?? "")}
          onCancel={() => setActivating(null)}
          onDone={() => { setActivating(null); setDone(t(`${V}.activated`)); reload(); }}
        />
      ) : null}

      {data.may_administer ? (
        start ? (
          <Editor
            key={`${start.from}`}
            summary={summary}
            start={start}
            presets={Object.keys(data.presets)}
            onBase={(name) => setStart(presetStart(name))}
            onCancel={() => setStart(null)}
            onSaved={(saved) => { setStart(null); setDone(tv(`${V}.saved`, { name: saved.name })); reload(); }}
          />
        ) : (
          <div>
            <Button variant="primary" small onClick={() => { setDone(null); setStart(inForce.origin === "stored" ? versionStart(data.versions.find((v) => v.version_number === inForce.version_number) as MethodVersion) : presetStart(summary.in_force ?? Object.keys(data.presets)[0])); }}>
              {t(`${V}.edit`)}
            </Button>
          </div>
        )
      ) : null}

      <div>
        <h4 className="text-sm font-semibold">{t(`${V}.history`)}</h4>
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
      </div>
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
  summary: MethodModuleSummary; start: Start; presets: string[];
  onBase: (name: string) => void; onCancel: () => void; onSaved: (v: MethodVersion) => void;
}) {
  // The labels and slots of the preset the edit is based on; the values come from `start`.
  const [res, retry] = useResource(() => methodology.get(props.summary.id, props.start.base), [props.summary.id, props.start.base]);
  return <Loaded res={res} retry={retry}>{(detail) => <EditorForm {...props} detail={detail} />}</Loaded>;
}

function EditorForm({ summary, start, presets, detail, onBase, onCancel, onSaved }: {
  summary: MethodModuleSummary; start: Start; presets: string[]; detail: MethodModuleDetail;
  onBase: (name: string) => void; onCancel: () => void; onSaved: (v: MethodVersion) => void;
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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      setCheck({ valid: false, problems: built.local, not_computed: [], formulas_latex: {} });
      return;
    }
    setBusy(true);
    try {
      const checked = await methodology.check(summary.id, built.edit);
      setCheck(checked);
      if (store && checked.valid) onSaved(await methodology.propose(summary.id, { ...built.edit, note: note.trim() }));
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    void run(true);
  };

  const problems = check?.problems ?? {};
  const placed = [...Object.keys(raw).map((r) => `spec.${r}`), ...[...builtin.keys()].map((s) => `formula.${s}`)];
  const elsewhere = unplacedProblems(problems, placed);
  return (
    <form data-methodology-editor onSubmit={submit} className="flex flex-col gap-4 rounded-sm border border-border p-3">
      <div className="flex flex-col gap-1">
        <h4 className="text-sm font-semibold">{tv(`${V}.editorTitle`, { from: start.from })}</h4>
        <p className="max-w-3xl text-xs text-ink-muted">{t(`${V}.editorHelp`)}</p>
      </div>
      {presets.length > 1 ? (
        <Field label={t(`${V}.base`)} className="max-w-xs">
          <Select value={start.from === start.base ? start.base : ""} onChange={(e) => e.target.value && onBase(e.target.value)}>
            {start.from === start.base ? null : <option value="">{start.from}</option>}
            {presets.map((p) => <option key={p} value={p}>{p}</option>)}
          </Select>
        </Field>
      ) : null}
      {elsewhere.length ? (
        <ul role="alert" className="flex flex-col gap-1 text-sm text-status-fault">
          {elsewhere.map(([k, m]) => <li key={k}><span className="font-mono">{k}</span>: {m}</li>)}
        </ul>
      ) : null}
      {steps.map(({ step, fields }) => (
        <fieldset key={step.id} data-edit-step={step.id} className="flex flex-col gap-2 border-t border-border pt-3">
          <legend className="text-sm font-semibold">{step.title_cs}</legend>
          {fields.map((f) => {
            const own = problemsFor(problems, `spec.${f.reference}`);
            const changed = raw[f.reference] !== toInput(readPath(start.spec, f.reference));
            return (
              <div key={f.reference} className="flex flex-col gap-1">
                <Field label={`${f.label_cs}${f.unit ? ` [${f.unit}]` : ""}`}>
                  <TextInput
                    value={raw[f.reference]}
                    aria-invalid={own.length > 0}
                    data-field={f.reference}
                    className="font-mono"
                    onChange={(e) => setRaw((r) => ({ ...r, [f.reference]: e.target.value }))}
                  />
                </Field>
                <span className="font-mono text-xs text-ink-faint">{f.reference}{changed ? ` · ${t(`${V}.changed`)}` : ""}</span>
                {own.map((m) => <span key={m} role="alert" className="text-xs text-status-fault">{m}</span>)}
              </div>
            );
          })}
          {step.formulas.map((f) => {
            const own = problemsFor(problems, `formula.${f.slot_id}`);
            const replaced = (exprs[f.slot_id] ?? "").trim() !== f.expression;
            const written = check?.formulas_latex[f.slot_id];
            return (
              <div key={f.slot_id} data-edit-slot={f.slot_id} className="flex flex-col gap-1">
                <Field label={`${t(`${V}.formula`)} · ${f.title_cs}`}>
                  <TextArea
                    rows={2}
                    value={exprs[f.slot_id]}
                    aria-invalid={own.length > 0}
                    className="font-mono"
                    onChange={(e) => setExprs((x) => ({ ...x, [f.slot_id]: e.target.value }))}
                  />
                </Field>
                <span className="text-xs text-ink-faint">
                  {t(`${V}.variables`)}: <span className="font-mono">{f.variables.map((v) => v.name).join(", ")}</span>
                  {replaced ? ` · ${t(`${V}.replaced`)}` : ""}
                </span>
                {replaced && written ? <div className="text-ink"><Formula latex={written} /></div> : null}
                {check?.not_computed.includes(f.slot_id) ? <span className="text-xs text-ink-muted">{t(`${V}.notComputed`)}</span> : null}
                {own.map((m) => <span key={m} role="alert" className="text-xs text-status-fault">{m}</span>)}
              </div>
            );
          })}
        </fieldset>
      ))}
      <Field label={t(`${V}.note`)}>
        <TextInput value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
      </Field>
      {check?.valid ? <p role="status" className="text-sm text-status-done">{t(`${V}.checkOk`)}</p> : null}
      {check && !check.valid ? <p role="alert" className="text-sm text-status-fault">{tv(`${V}.checkFailed`, { count: Object.keys(check.problems).length })}</p> : null}
      {error ? <p role="alert" className="text-sm text-status-fault">{error}</p> : null}
      <div className="flex flex-wrap gap-2">
        <Button disabled={busy} onClick={() => void run(false)}>{t(`${V}.check`)}</Button>
        <Button type="submit" variant="primary" disabled={busy}>{t(`${V}.store`)}</Button>
        <Button disabled={busy} onClick={onCancel}>{t(`${V}.cancel`)}</Button>
      </div>
    </form>
  );
}
