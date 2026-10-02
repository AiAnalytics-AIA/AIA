"use client";

// The system prompts tab: what each step tells the model, edited here (ADR 0020).
//
// What an administrator can do: read a prompt, edit its instruction, save the edit as
// a new version, compare versions, test one on a fictional study, put one live, and go
// back to the wording shipped in code. What they cannot: edit the code's frame around
// the instruction (shown, never editable) or make an edit take effect for a job already
// queued -- a job keeps the prompt it was queued with. A saved version does not run until
// it is put live. By default the author may do that themselves (ADR 0019: no approval
// between people); an organization that requires independent review gets a refusal for
// the author instead, shown as the API gave it.
//
// Nothing here calls a model. A test queues a normal agent job pinned to the version.

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";

import { t, tv } from "@/i18n/t";
import {
  type AdminClient,
  type Member,
  type PromptSlotDetail,
  type PromptSlotSummary,
  type PromptVersion,
  type ResearchAgentAction,
  type ResearchAgentJob,
  type ResearchAgentResult,
  type SettingsDocument,
  Unauthenticated,
  admin,
  research,
  researchAgents,
} from "@/lib/api";
import { relative } from "@/lib/format";
import { diffLines, differs, summarise } from "@/lib/text-diff";
import { Button, Chip, Field, Select, Tag, TextArea, TextInput } from "../../rehome/ui";
import { EYEBROW, Empty, Loaded } from "../states";
import { useResource } from "../useResource";
import type { Part, StudyRow } from "./ControlPanel";
import { describeError } from "./errors";

const P = "aia.settings.prompts";

const ACTIONS: readonly ResearchAgentAction[] = [
  "analyze_brief", "build_questionnaire", "optimize_questionnaire", "propose_audience",
  "suggest_dimensions", "critique_design", "design_copilot", "answer_memory",
];

/** The agent action a research prompt belongs to; only those can be tested from here. */
export function actionOf(promptId: string): ResearchAgentAction | null {
  const name = promptId.startsWith("aia.research.") ? promptId.slice("aia.research.".length) : "";
  return ACTIONS.find((a) => a === name) ?? null;
}

const nameOf = (id: string) => t(`${P}.names.${id.replaceAll(".", "_")}`);
const short = (hash: string) => hash.slice(0, 8);
const when = (iso: string | null) => (iso ? (relative(iso) ?? iso) : "—");

type People = (id: string | null) => string;

type Props = {
  doc: SettingsDocument;
  members: Part<Member[]>;
  clients: Part<AdminClient[]>;
  studies: Part<StudyRow[]>;
};

/** The tab. Only an organization administrator is shown the prompts, and asked for them. */
export function SystemPromptsPanel({ doc, members, clients, studies }: Props) {
  if (!doc.may_administer) {
    return <p className="text-sm text-ink-muted">{t(`${P}.adminOnly`)}</p>;
  }
  const emails = new Map(members.ok ? members.data.map((m) => [m.user_id, m.email]) : []);
  const people: People = (id) => (id ? (emails.get(id) ?? id) : "—");
  return <Workspace people={people} clients={clients} studies={studies} />;
}

// ---------------------------------------------------------------- the workspace

async function loadList(): Promise<PromptSlotSummary[]> {
  const rows: unknown = await admin.prompts();
  // A body that is not a list is not "no prompts": say so rather than draw an empty page.
  if (!Array.isArray(rows)) throw new Error(t(`${P}.malformed`));
  return rows as PromptSlotSummary[];
}

function Workspace({ people, clients, studies }: { people: People; clients: Props["clients"]; studies: Props["studies"] }) {
  const [list, reloadList] = useResource(loadList, []);
  const [selected, setSelected] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);

  return (
    <Loaded res={list} retry={reloadList}>
      {(rows) => {
        const current = selected ?? rows.find((r) => r.wired)?.prompt_id ?? rows[0]?.prompt_id ?? null;
        const choose = (id: string) => {
          if (id === current) return;
          if (dirty) setPending(id);
          else setSelected(id);
        };
        return (
          <div className="grid gap-4 lg:grid-cols-[minmax(0,17rem)_minmax(0,1fr)]">
            <PromptList rows={rows} current={current} onChoose={choose} />
            <div className="min-w-0">
              {pending ? (
                <div role="alert" data-switch-guard className="mb-3 flex flex-wrap items-center gap-3 rounded-sm border border-status-you-ink/40 bg-status-you-wash p-3 text-sm">
                  <span>{tv(`${P}.guard.text`, { name: nameOf(pending) })}</span>
                  <Button small variant="primary" onClick={() => { setSelected(pending); setPending(null); setDirty(false); }}>{t(`${P}.guard.discard`)}</Button>
                  <Button small onClick={() => setPending(null)}>{t(`${P}.guard.stay`)}</Button>
                </div>
              ) : null}
              {current ? (
                <Editor key={current} promptId={current} people={people} clients={clients} studies={studies} onChanged={reloadList} onDirty={setDirty} />
              ) : (
                <Empty>{t(`${P}.none`)}</Empty>
              )}
            </div>
          </div>
        );
      }}
    </Loaded>
  );
}

function stateChip(row: PromptSlotSummary): ReactNode {
  if (!row.wired) return <Tag>{t(`${P}.state.locked`)}</Tag>;
  if (row.active.origin === "stored") return <Chip tone="you">{tv(`${P}.state.edited`, { label: row.active.label })}</Chip>;
  return <Chip tone="neutral">{t(`${P}.state.baseline`)}</Chip>;
}

function PromptList({ rows, current, onChoose }: { rows: PromptSlotSummary[]; current: string | null; onChoose: (id: string) => void }) {
  const families = [...new Set(rows.map((r) => r.family))];
  return (
    <nav aria-label={t(`${P}.listLabel`)} className="flex flex-col gap-4">
      {families.map((family) => (
        <div key={family} data-family={family}>
          <h3 className={EYEBROW}>{t(`${P}.families.${family}`)}</h3>
          <ul className="mt-1 flex flex-col gap-1">
            {rows.filter((r) => r.family === family).map((row) => (
              <li key={row.prompt_id}>
                <button
                  type="button"
                  data-prompt={row.prompt_id}
                  aria-current={row.prompt_id === current ? "true" : undefined}
                  onClick={() => onChoose(row.prompt_id)}
                  className={`flex w-full flex-col items-start gap-1 rounded-sm border px-3 py-2 text-left text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${row.prompt_id === current ? "border-signal bg-signal-wash" : "border-border bg-surface-raised hover:bg-surface-sunken"}`}
                >
                  <span className="font-medium text-ink">{nameOf(row.prompt_id)}</span>
                  {stateChip(row)}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

// ---------------------------------------------------------------- the editor

/** The text that runs for a prompt now: the active stored version's, or the code's wording. */
function runningText(d: PromptSlotDetail): string {
  if (d.active.origin !== "stored") return d.baseline_text;
  return d.versions.find((v) => v.version_number === d.active.version_number)?.text ?? d.baseline_text;
}

function Editor(props: {
  promptId: string; people: People; clients: Props["clients"]; studies: Props["studies"];
  onChanged: () => void; onDirty: (dirty: boolean) => void;
}) {
  const [detail, reload] = useResource(() => admin.prompt(props.promptId), [props.promptId]);
  return (
    <Loaded res={detail} retry={reload}>
      {(d) => <EditorBody detail={d} {...props} reload={() => { reload(); props.onChanged(); }} />}
    </Loaded>
  );
}

function EditorBody({ detail, people, clients, studies, reload, onDirty }: {
  detail: PromptSlotDetail; people: People; clients: Props["clients"]; studies: Props["studies"];
  reload: () => void; onDirty: (dirty: boolean) => void;
}) {
  const router = useRouter();
  const start = runningText(detail);
  const [draft, setDraft] = useState(start);
  const [reference, setReference] = useState(start);
  const [basedOn, setBasedOn] = useState(detail.active.origin === "stored" ? detail.active.label : "baseline");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<{ ok: boolean; text: string; savedVersion?: number } | null>(null);
  const [activating, setActivating] = useState<{ version: number | null } | null>(null);
  const [testing, setTesting] = useState<number | null>(null);
  const [compare, setCompare] = useState<{ a: string; b: string }>({
    a: detail.active.origin === "stored" ? `v${detail.active.version_number}` : "baseline",
    b: "draft",
  });

  const dirty = differs(draft, reference);
  useEffect(() => {
    onDirty(dirty);
    return () => onDirty(false);
  }, [dirty, onDirty]);
  // Leaving the page with an unsaved edit asks first; saving or discarding lifts it.
  useEffect(() => {
    if (!dirty) return;
    const guard = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [dirty]);

  const trimmed = draft.trim();
  const duplicateOf = useMemo(() => {
    if (!trimmed) return null;
    if (trimmed === detail.baseline_text.trim()) return t(`${P}.baselineName`);
    return detail.versions.find((v) => v.text === trimmed)?.label ?? null;
  }, [trimmed, detail]);
  const missing = detail.required_literals.filter((lit) => !trimmed.includes(lit));
  const problem =
    !trimmed ? t(`${P}.editor.empty`)
    : trimmed.length > detail.max_chars ? tv(`${P}.editor.tooLong`, { max: detail.max_chars })
    : missing.length ? tv(`${P}.editor.missing`, { text: missing.join(", ") })
    : draft.includes("\u0000") ? t(`${P}.editor.badChar`)
    : null;
  const canSave = detail.wired && !problem && !duplicateOf && !busy;

  const fail = (e: unknown) => {
    if (e instanceof Unauthenticated) {
      router.replace(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
      return;
    }
    setAnswer({ ok: false, text: describeError(e) });
  };

  async function save() {
    setBusy(true);
    setAnswer(null);
    try {
      const saved = await admin.savePrompt(detail.prompt_id, { text: trimmed, note: note.trim(), based_on: basedOn });
      setDraft(saved.text);
      setReference(saved.text);
      setBasedOn(saved.label);
      setNote("");
      setAnswer({ ok: true, text: tv(`${P}.editor.saved`, { label: saved.label }), savedVersion: saved.version_number });
      reload();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  const textOf = (versionNumber: number | null) =>
    versionNumber === null ? detail.baseline_text : (detail.versions.find((v) => v.version_number === versionNumber)?.text ?? "");

  const options = [
    { key: "baseline", label: t(`${P}.baselineName`), text: detail.baseline_text },
    ...detail.versions.map((v) => ({ key: `v${v.version_number}`, label: v.label, text: v.text })),
    { key: "draft", label: t(`${P}.compare.draft`), text: draft },
  ];
  const side = (key: string) => options.find((o) => o.key === key) ?? options[0];

  return (
    <div data-editor={detail.prompt_id} className="flex flex-col gap-5">
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-base font-semibold">{nameOf(detail.prompt_id)}</h3>
          {stateChip(detail)}
          {dirty ? <Chip tone="you">{t(`${P}.guard.unsaved`)}</Chip> : null}
        </div>
        <p className="max-w-3xl text-sm text-ink-muted">{t(`${P}.about.${detail.family}`)}</p>
        <p className="text-xs text-ink-faint">
          <code>{detail.prompt_id}</code> · {t(`${P}.runs`)}: {detail.active.origin === "stored" ? detail.active.label : tv(`${P}.baselineVersion`, { version: detail.baseline_version })}
          {" · "}SHA-256 <code>{short(detail.active.text_sha256)}</code>
          {detail.active.activated_by ? <> · {tv(`${P}.activatedBy`, { who: people(detail.active.activated_by), when: when(detail.active.activated_at) })}</> : null}
        </p>
      </header>

      {!detail.wired ? (
        <div data-locked className="flex flex-col gap-3">
          <p role="note" className="rounded-sm border border-border bg-surface-sunken p-3 text-sm">
            {t(`${P}.unwired.${detail.unwired_reason ?? "unknown"}`)}
          </p>
          <details className="rounded-sm border border-border">
            <summary className="cursor-pointer px-3 py-2 text-sm font-medium">{t(`${P}.editor.showBaseline`)}</summary>
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap border-t border-border p-3 font-mono text-xs leading-5">{detail.baseline_text}</pre>
          </details>
        </div>
      ) : (
        <>
          <details data-frame className="rounded-sm border border-border bg-surface-sunken">
            <summary className="cursor-pointer px-3 py-2 text-sm font-medium">{t(`${P}.editor.frameTitle`)}</summary>
            <div className="border-t border-border p-3">
              <p className="mb-2 text-xs text-ink-muted">{t(`${P}.editor.frameNote`)}</p>
              <pre className="max-h-64 overflow-auto whitespace-pre-wrap font-mono text-xs leading-5 text-ink-muted">{detail.fixed_prefix}</pre>
            </div>
          </details>

          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => { e.preventDefault(); if (canSave) void save(); }}
          >
            <Field label={t(`${P}.editor.textLabel`)}>
              <TextArea
                name="instruction" rows={14} spellCheck={false} value={draft}
                onChange={(e) => setDraft(e.target.value)}
                aria-invalid={problem ? true : undefined}
                aria-describedby={`${detail.prompt_id}-hint`}
                className="w-full font-mono text-[13px]"
              />
            </Field>
            <div id={`${detail.prompt_id}-hint`} className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <span data-problem={problem ? "yes" : "no"} className={problem ? "text-status-fault" : duplicateOf ? "text-ink-muted" : "text-ink-faint"}>
                {problem ?? (duplicateOf ? tv(`${P}.editor.duplicate`, { label: duplicateOf }) : tv(`${P}.editor.basedOn`, { label: basedOn === "baseline" ? t(`${P}.baselineName`) : basedOn }))}
              </span>
              <span className="font-mono text-ink-faint">{trimmed.length} / {detail.max_chars}</span>
            </div>
            <div className="flex flex-wrap items-end gap-2">
              <Field label={t(`${P}.editor.noteLabel`)} className="min-w-64 flex-1">
                <TextInput name="note" value={note} maxLength={255} onChange={(e) => setNote(e.target.value)} placeholder={t(`${P}.editor.notePlaceholder`)} />
              </Field>
              <Button type="submit" variant="primary" disabled={!canSave}>{busy ? t(`${P}.editor.saving`) : t(`${P}.editor.save`)}</Button>
              <Button disabled={!dirty || busy} onClick={() => { setDraft(reference); setAnswer(null); }}>{t(`${P}.editor.revert`)}</Button>
            </div>
            <p className="text-xs text-ink-faint">{t(`${P}.editor.notLiveYet`)}</p>
            {answer ? (
              <div role="status" data-answer={answer.ok ? "ok" : "refused"} className={`flex flex-wrap items-center gap-3 text-sm ${answer.ok ? "text-status-done" : "text-status-fault"}`}>
                <span>{answer.text}</span>
                {answer.ok && answer.savedVersion ? (
                  <Button small onClick={() => setActivating({ version: answer.savedVersion ?? null })}>{tv(`${P}.versions.activate`, { label: `e${answer.savedVersion}` })}</Button>
                ) : null}
              </div>
            ) : null}
          </form>

          <Versions
            detail={detail} people={people}
            onLoad={(text, label) => { setDraft(text); setReference(text); setBasedOn(label); setAnswer(null); }}
            onCompare={(key) => setCompare((c) => ({ ...c, a: key }))}
            onActivate={(version) => setActivating({ version })}
            onTest={(version) => setTesting(version)}
          />

          {activating ? (
            <Activation
              key={`${activating.version}`}
              detail={detail}
              version={activating.version}
              label={activating.version === null ? t(`${P}.baselineName`) : `e${activating.version}`}
              dirty={dirty}
              onCancel={() => setActivating(null)}
              onDone={(label, text) => {
                setActivating(null);
                if (!dirty) { setDraft(text); setReference(text); setBasedOn(label); }
                setAnswer({ ok: true, text: tv(`${P}.activate.done`, { label: activating.version === null ? t(`${P}.baselineName`) : label }) });
                reload();
              }}
              textOf={textOf}
            />
          ) : null}

          {testing !== null ? (
            <TestRun key={testing} detail={detail} version={testing} studies={studies} clients={clients} onClose={() => setTesting(null)} />
          ) : null}

          <Compare options={options} state={compare} onChange={setCompare} side={side} />

          <History detail={detail} people={people} />
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- versions

function Versions({ detail, people, onLoad, onCompare, onActivate, onTest }: {
  detail: PromptSlotDetail; people: People;
  onLoad: (text: string, label: string) => void;
  onCompare: (key: string) => void;
  onActivate: (version: number | null) => void;
  onTest: (version: number) => void;
}) {
  const baselineRunning = detail.active.origin === "baseline";
  const canTest = actionOf(detail.prompt_id) !== null;
  const TH = "px-2 py-1 text-left font-mono text-[11px] font-normal uppercase tracking-[0.08em] text-ink-faint";
  const TD = "px-2 py-1.5 align-top text-sm";
  const row = (v: PromptVersion | null) => {
    const running = v === null ? baselineRunning : detail.active.version_number === v.version_number;
    const key = v === null ? "baseline" : `v${v.version_number}`;
    const label = v === null ? t(`${P}.baselineName`) : v.label;
    return (
      <tr key={key} data-version={key} data-running={running ? "yes" : "no"}>
        <td className={TD}><span className="font-medium">{label}</span></td>
        <td className={TD}>{v === null ? t(`${P}.versions.byCode`) : people(v.created_by)}</td>
        <td className={`${TD} text-ink-muted`}>{v === null ? "—" : when(v.created_at)}</td>
        <td className={`${TD} max-w-56 text-ink-muted`}>{v === null ? tv(`${P}.baselineVersion`, { version: detail.baseline_version }) : v.note || "—"}</td>
        <td className={TD}>{running ? <Chip tone="done">{t(`${P}.versions.running`)}</Chip> : null}</td>
        <td className={TD}>
          <div className="flex flex-wrap gap-1">
            <Button small onClick={() => onLoad(v === null ? detail.baseline_text : v.text, v === null ? "baseline" : v.label)}>{t(`${P}.versions.load`)}</Button>
            <Button small onClick={() => onCompare(key)}>{t(`${P}.versions.compare`)}</Button>
            {!running ? (
              <Button small variant="primary" onClick={() => onActivate(v === null ? null : v.version_number)}>
                {v === null ? t(`${P}.versions.reset`) : tv(`${P}.versions.activate`, { label })}
              </Button>
            ) : null}
            {v !== null && canTest ? <Button small onClick={() => onTest(v.version_number)}>{t(`${P}.versions.test`)}</Button> : null}
          </div>
        </td>
      </tr>
    );
  };
  return (
    <section aria-labelledby="pv-h" className="flex flex-col gap-2">
      <h4 id="pv-h" className={EYEBROW}>{t(`${P}.versions.title`)}</h4>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>{(["version", "author", "when", "note", "state", "actions"] as const).map((k) => <th key={k} className={TH}>{t(`${P}.versions.col.${k}`)}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-border">
            {[...detail.versions].map((v) => row(v))}
            {row(null)}
          </tbody>
        </table>
      </div>
      {!detail.versions.length ? <p className="text-xs text-ink-faint">{t(`${P}.versions.none`)}</p> : null}
    </section>
  );
}

// ---------------------------------------------------------------- activation

function Activation({ detail, version, label, dirty, onCancel, onDone, textOf }: {
  detail: PromptSlotDetail; version: number | null; label: string; dirty: boolean;
  onCancel: () => void; onDone: (label: string, text: string) => void; textOf: (version: number | null) => string;
}) {
  const router = useRouter();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function go() {
    setBusy(true);
    setError(null);
    try {
      const active = await admin.activatePrompt(detail.prompt_id, version, reason.trim());
      onDone(active.label, textOf(version));
    } catch (e) {
      if (e instanceof Unauthenticated) {
        router.replace(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
        return;
      }
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section data-activation aria-labelledby="pa-h" className="flex flex-col gap-3 rounded-sm border border-status-you-ink/40 bg-status-you-wash p-4">
      <h4 id="pa-h" className="text-sm font-semibold">{version === null ? t(`${P}.activate.resetTitle`) : tv(`${P}.activate.title`, { label })}</h4>
      <p className="text-sm">{tv(`${P}.activate.impact`, { from: detail.active.origin === "stored" ? detail.active.label : t(`${P}.baselineName`), to: label })}</p>
      <p className="text-xs text-ink-muted">{t(`${P}.activate.queuedKeep`)}</p>
      {dirty ? <p className="text-xs text-ink-muted">{t(`${P}.activate.draftStays`)}</p> : null}
      <Field label={t(`${P}.activate.reasonLabel`)}>
        <TextInput value={reason} maxLength={255} onChange={(e) => setReason(e.target.value)} />
      </Field>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="primary" disabled={busy} onClick={() => void go()}>{busy ? t(`${P}.editor.saving`) : t(`${P}.activate.confirm`)}</Button>
        <Button disabled={busy} onClick={onCancel}>{t(`${P}.activate.cancel`)}</Button>
      </div>
      {error ? <p role="alert" data-refusal className="text-sm text-status-fault">{error}</p> : null}
    </section>
  );
}

// ---------------------------------------------------------------- compare

type Option = { key: string; label: string; text: string };

function Compare({ options, state, onChange, side }: {
  options: Option[]; state: { a: string; b: string }; onChange: (s: { a: string; b: string }) => void; side: (key: string) => Option;
}) {
  const a = side(state.a);
  const b = side(state.b);
  const ops = useMemo(() => diffLines(a.text, b.text), [a.text, b.text]);
  const { added, removed } = summarise(ops);
  const same = !differs(a.text, b.text);
  return (
    <details data-compare className="rounded-sm border border-border" open={state.a !== "baseline" || undefined}>
      <summary className="cursor-pointer px-3 py-2 text-sm font-medium">{t(`${P}.compare.title`)}</summary>
      <div className="flex flex-col gap-3 border-t border-border p-3">
        <div className="flex flex-wrap items-end gap-3">
          <Field label={t(`${P}.compare.from`)}>
            <Select value={state.a} onChange={(e) => onChange({ ...state, a: e.target.value })} className="w-auto">
              {options.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
            </Select>
          </Field>
          <Field label={t(`${P}.compare.to`)}>
            <Select value={state.b} onChange={(e) => onChange({ ...state, b: e.target.value })} className="w-auto">
              {options.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
            </Select>
          </Field>
          <span data-summary className="pb-2 text-xs text-ink-muted">{same ? t(`${P}.compare.same`) : tv(`${P}.compare.summary`, { added, removed })}</span>
        </div>
        {same ? null : (
          <pre aria-label={t(`${P}.compare.title`)} className="max-h-96 overflow-auto rounded-sm border border-border bg-surface p-0 font-mono text-xs leading-5">
            {ops.map((op, i) => (
              <div
                key={i}
                data-diff={op.kind}
                className={`flex gap-2 px-2 ${op.kind === "add" ? "bg-status-running-wash text-ink" : op.kind === "del" ? "bg-status-fault-wash text-ink" : "text-ink-muted"}`}
              >
                <span aria-hidden className="w-3 shrink-0 select-none text-ink-faint">{op.kind === "add" ? "+" : op.kind === "del" ? "−" : " "}</span>
                <span className="sr-only">{t(`${P}.compare.${op.kind === "same" ? "same_line" : op.kind}`)}: </span>
                <span className="whitespace-pre-wrap break-words">{op.text || " "}</span>
              </div>
            ))}
          </pre>
        )}
      </div>
    </details>
  );
}

// ---------------------------------------------------------------- history

function History({ detail, people }: { detail: PromptSlotDetail; people: People }) {
  return (
    <details data-history className="rounded-sm border border-border">
      <summary className="cursor-pointer px-3 py-2 text-sm font-medium">{t(`${P}.history.title`)}</summary>
      <div className="border-t border-border p-3">
        {detail.history.length ? (
          <ul className="flex flex-col gap-1 text-sm">
            {detail.history.map((h) => (
              <li key={h.activation_id} data-activation-row>
                <strong>{h.label ?? t(`${P}.baselineName`)}</strong> · {people(h.activated_by)} · {when(h.activated_at)}
                {h.reason ? <span className="text-ink-muted"> — {h.reason}</span> : null}
              </li>
            ))}
          </ul>
        ) : <p className="text-sm text-ink-muted">{t(`${P}.history.none`)}</p>}
      </div>
    </details>
  );
}

// ---------------------------------------------------------------- test a version

const POLL_MS = 3000;

function TestRun({ detail, version, studies, clients, onClose }: {
  detail: PromptSlotDetail; version: number; studies: Props["studies"]; clients: Props["clients"]; onClose: () => void;
}) {
  const router = useRouter();
  const action = actionOf(detail.prompt_id);
  const clientName = new Map(clients.ok ? clients.data.map((c) => [c.client_id, c.name]) : []);
  const eligible = studies.ok ? studies.data.map((r) => r.study).filter((s) => s.kind === "RESEARCH" && s.accepts_work) : [];
  const [studyId, setStudyId] = useState(eligible[0]?.study_id ?? "");
  const [revisions, setRevisions] = useState<{ id: string; label: string }[] | null>(null);
  const [revisionId, setRevisionId] = useState("");
  const [job, setJob] = useState<ResearchAgentJob | null>(null);
  const [result, setResult] = useState<ResearchAgentResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const resultFor = useRef<string | null>(null);

  const fail = (e: unknown) => {
    if (e instanceof Unauthenticated) {
      router.replace(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
      return;
    }
    setError(describeError(e));
  };

  // The study's design revisions, newest first; the newest is the default.
  useEffect(() => {
    if (!studyId) return;
    let live = true;
    setRevisions(null);
    setRevisionId("");
    research.revisions(studyId).then(
      (items) => {
        if (!live) return;
        const sorted = [...items].sort((a, b) => b.revision - a.revision);
        setRevisions(sorted.map((r) => ({ id: r.revision_id, label: `#${r.revision} · ${r.source_stage}` })));
        setRevisionId(sorted[0]?.revision_id ?? "");
      },
      (e: unknown) => { if (live) { setRevisions([]); fail(e); } },
    );
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studyId]);

  // Follow the job until it ends, then read its proposal once.
  useEffect(() => {
    if (!job || !studyId) return;
    if (job.is_terminal || job.status === "WAITING_PROVIDER") {
      if (job.status === "COMPLETED" && resultFor.current !== job.run_id) {
        resultFor.current = job.run_id;
        researchAgents.result(studyId, job.run_id).then(setResult, fail);
      }
      return;
    }
    const timer = setTimeout(() => {
      researchAgents.job(studyId, job.run_id).then(setJob, fail);
    }, POLL_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job, studyId]);

  async function run() {
    if (!action) return;
    setBusy(true);
    setError(null);
    setResult(null);
    resultFor.current = null;
    try {
      setJob(await researchAgents.start(studyId, revisionId, action, "", version));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section data-test-run aria-labelledby="pt-h" className="flex flex-col gap-3 rounded-sm border border-border p-4">
      <div className="flex items-center justify-between gap-2">
        <h4 id="pt-h" className="text-sm font-semibold">{tv(`${P}.test.title`, { label: `e${version}` })}</h4>
        <Button small variant="quiet" onClick={onClose}>{t(`${P}.test.close`)}</Button>
      </div>
      <p className="max-w-3xl text-sm text-ink-muted">{t(`${P}.test.intro`)}</p>
      <p role="note" className="text-xs text-ink-muted">{t(`${P}.test.cost`)}</p>
      {!eligible.length ? <Empty>{t(`${P}.test.noStudies`)}</Empty> : (
        <div className="flex flex-wrap items-end gap-3">
          <Field label={t(`${P}.test.study`)}>
            <Select value={studyId} onChange={(e) => setStudyId(e.target.value)} className="w-auto">
              {eligible.map((s) => <option key={s.study_id} value={s.study_id}>{s.name} · {clientName.get(s.client_id) ?? s.client_id}</option>)}
            </Select>
          </Field>
          <Field label={t(`${P}.test.revision`)}>
            <Select value={revisionId} onChange={(e) => setRevisionId(e.target.value)} className="w-auto" disabled={!revisions?.length}>
              {(revisions ?? []).map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
            </Select>
          </Field>
          <Button variant="primary" disabled={busy || !revisionId || (!!job && !job.is_terminal)} onClick={() => void run()}>
            {busy ? t(`${P}.test.starting`) : t(`${P}.test.start`)}
          </Button>
        </div>
      )}
      {revisions && !revisions.length && studyId ? <p className="text-xs text-ink-muted">{t(`${P}.test.noRevision`)}</p> : null}
      {error ? <p role="alert" data-refusal className="text-sm text-status-fault">{error}</p> : null}
      {job ? (
        <div data-job className="flex flex-col gap-2 text-sm">
          <p>
            <Chip tone={job.status === "COMPLETED" ? "done" : job.needs_attention ? "fault" : "running"}>{job.status}</Chip>{" "}
            {tv(`${P}.test.ranWith`, { version: job.prompt_version ?? "—" })}
            {job.actual_cost_usd !== null ? <> · ${job.actual_cost_usd.toFixed(4)}</> : null}
          </p>
          {job.status === "WAITING_PROVIDER" ? <p className="text-xs text-ink-muted">{t(`${P}.test.parked`)}</p> : null}
          {result ? (
            <details open data-result>
              <summary className="cursor-pointer font-medium">{t(`${P}.test.result`)}</summary>
              <pre className="mt-2 max-h-96 overflow-auto rounded-sm border border-border bg-surface p-3 font-mono text-xs leading-5">{JSON.stringify(result.result.proposal, null, 2)}</pre>
            </details>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
