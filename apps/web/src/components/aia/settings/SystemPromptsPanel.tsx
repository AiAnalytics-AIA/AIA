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
import { type ReactNode, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";

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
import { withJobCostConfirmation } from "@/lib/research-agent-jobs";
import { Button, Chip, Field, Select, TextArea, TextInput } from "../../rehome/ui";
import { Technical } from "./technical";
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

export const nameOf = (id: string) => {
  const key = `${P}.names.${id.replaceAll(".", "_")}`;
  const label = t(key);
  return label === key ? id.split(".").at(-1)!.replaceAll("_", " ") : label;
};
const short = (hash: string) => hash.slice(0, 8);
/** A stored version's label as a reader says it: the API's "e3" is "verze 3". */
const versionName = (label: string) => {
  const n = /^e(\d+)$/.exec(label)?.[1];
  return n ? tv(`${P}.versionName`, { n }) : label;
};
/** The same, as the object of a verb ("Zapnout verzi 3"). */
const versionAcc = (label: string) => {
  const n = /^e(\d+)$/.exec(label)?.[1];
  return n ? tv(`${P}.versionAcc`, { n }) : label;
};
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
          <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,15rem)_minmax(0,1fr)] 2xl:grid-cols-[minmax(0,17rem)_minmax(0,1fr)]">
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

/** Where a prompt stands, in words: no chip, no colour that has to be learnt. */
function stateText(row: PromptSlotSummary): ReactNode {
  if (!row.wired) return <span className="text-ink-faint">{t(`${P}.state.locked`)}</span>;
  if (row.active.origin === "stored") return <span className="text-ink">{tv(`${P}.state.edited`, { label: versionName(row.active.label) })}</span>;
  return <span className="text-ink-muted">{t(`${P}.state.baseline`)}</span>;
}

function PromptList({ rows, current, onChoose }: { rows: PromptSlotSummary[]; current: string | null; onChoose: (id: string) => void }) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const matching = rows.filter((r) =>
    (filter === "all" || r.wired === (filter === "editable")) &&
    `${nameOf(r.prompt_id)} ${r.prompt_id} ${t(`${P}.families.${r.family}`)}`.toLocaleLowerCase("cs").includes(query.trim().toLocaleLowerCase("cs")));
  const families = [...new Set(matching.map((r) => r.family))];
  return (
    <nav aria-label={t(`${P}.listLabel`)} className="min-w-0 lg:sticky lg:top-4">
      <div className="flex flex-col gap-2 pb-3">
        <TextInput type="search" aria-label={t(`${P}.search`)} placeholder={t(`${P}.searchPlaceholder`)} value={query} onChange={(e) => setQuery(e.target.value)} />
        <Select aria-label={t(`${P}.filter`)} value={filter} onChange={(e) => setFilter(e.target.value)}>
          {["all", "editable", "readOnly"].map((f) => <option key={f} value={f}>{t(`${P}.${f}`)}</option>)}
        </Select>
        <span role="status" className="text-xs text-ink-muted">{tv(`${P}.found`, { shown: matching.length, total: rows.length })}</span>
      </div>
      <div className="flex max-h-64 flex-col gap-4 overflow-y-auto overscroll-contain lg:max-h-[70vh]">
        {families.map((family) => (
          <div key={family} data-family={family}>
            <h3 className={EYEBROW}>{t(`${P}.families.${family}`)}</h3>
            <ul className="mt-1 flex flex-col gap-0.5">
              {matching.filter((r) => r.family === family).map((row) => (
                <li key={row.prompt_id}>
                  <button type="button" data-prompt={row.prompt_id} aria-current={row.prompt_id === current ? "true" : undefined}
                    onClick={() => onChoose(row.prompt_id)}
                    className={`flex min-h-11 w-full min-w-0 flex-col items-start justify-center rounded-sm px-3 py-1.5 text-left text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${row.prompt_id === current ? "bg-signal-wash" : "hover:bg-surface-sunken"}`}>
                    <span className={`break-words ${row.prompt_id === current ? "font-semibold text-signal" : "text-ink"}`}>{nameOf(row.prompt_id)}</span>
                    <span className="text-xs">{stateText(row)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
        {!matching.length ? <div className="flex flex-col gap-2 text-sm"><p>{t(`${P}.noMatch`)}</p><Button small onClick={() => { setQuery(""); setFilter("all"); }}>{t(`${P}.clearSearch`)}</Button></div> : null}
      </div>
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
  const [answer, setAnswer] = useState<{ ok: boolean; text: string } | null>(null);
  // The version this editor just saved, as the server returned it. Its "Zapnout" button shows
  // at once, before the detail has been read again, so what is said about that version (its
  // declaration, its text) is read from here until the detail lists it.
  const [justSaved, setJustSaved] = useState<PromptVersion | null>(null);
  const [activating, setActivating] = useState<{ version: number | null } | null>(null);
  // The version this editor saved and has not seen switched on: the next step offers it until
  // it runs. Its own state, so clearing a message or reverting an edit never loses it.
  const [offer, setOffer] = useState<number | null>(null);
  const [testing, setTesting] = useState<number | null>(null);
  const [pendingLoad, setPendingLoad] = useState<{ text: string; label: string } | null>(null);
  const [compareOpen, setCompareOpen] = useState(false);
  const activationRef = useRef<HTMLDivElement>(null);
  const [compare, setCompare] = useState<{ a: string; b: string }>({
    a: detail.active.origin === "stored" ? `v${detail.active.version_number}` : "baseline",
    b: "draft",
  });

  useEffect(() => {
    if (activating) activationRef.current?.scrollIntoView?.({ block: "center", behavior: "smooth" });
  }, [activating]);
  const dirty = differs(draft, reference) || !!note.trim();
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
    const stored = detail.versions.find((v) => !differs(v.text.trim(), trimmed));
    if (stored) return stored.label;
    if (!differs(trimmed, detail.baseline_text.trim())) return t(`${P}.baselineName`);
    return detail.versions.find((v) => !differs(v.text.trim(), trimmed))?.label ?? null;
  }, [trimmed, detail]);
  const missing = detail.required_literals.filter((lit) => !trimmed.includes(lit));
  const problem =
    !trimmed ? t(`${P}.editor.empty`)
    : trimmed.length > detail.max_chars ? tv(`${P}.editor.tooLong`, { max: detail.max_chars })
    : missing.length ? tv(`${P}.editor.missing`, { text: missing.join(", ") })
    : draft.includes("\u0000") ? t(`${P}.editor.badChar`)
    : null;
  const canSave = detail.wired && dirty && !problem && !duplicateOf && !busy;

  const fail = (e: unknown) => {
    if (e instanceof Unauthenticated) {
      router.replace(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search + window.location.hash)}`);
      return;
    }
    setAnswer({ ok: false, text: describeError(e) });
  };

  async function save() {
    if (!canSave) return;
    setBusy(true);
    setAnswer(null);
    try {
      const saved = await admin.savePrompt(detail.prompt_id, { text: trimmed, note: note.trim(), based_on: basedOn });
      setDraft(saved.text);
      setReference(saved.text);
      setBasedOn(saved.label);
      setNote("");
      setJustSaved(saved);
      setOffer(saved.version_number);
      setAnswer({ ok: true, text: tv(`${P}.editor.saved`, { label: versionName(saved.label) }) });
      reload();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  const versionOf = (versionNumber: number): PromptVersion | undefined =>
    detail.versions.find((v) => v.version_number === versionNumber) ?? (justSaved?.version_number === versionNumber ? justSaved : undefined);
  const textOf = (versionNumber: number | null) =>
    versionNumber === null ? detail.baseline_text : (versionOf(versionNumber)?.text ?? "");

  const options = [
    { key: "baseline", label: t(`${P}.baselineName`), text: detail.baseline_text },
    ...detail.versions.map((v) => ({ key: `v${v.version_number}`, label: v.label, text: v.text })),
    { key: "draft", label: t(`${P}.compare.draft`), text: draft },
  ];
  const side = (key: string) => options.find((o) => o.key === key) ?? options[0];

  const running = detail.active.origin === "stored" ? versionName(detail.active.label) : t(`${P}.baselineName`);
  const savedWaiting = offer !== null && detail.active.version_number !== offer ? offer : null;
  const canTest = actionOf(detail.prompt_id) !== null && detail.draft_test_client_ids.length > 0;
  const basedOnName = basedOn === "baseline" ? t(`${P}.baselineName`) : versionName(basedOn);

  if (!detail.wired) {
    return (
      <div data-editor={detail.prompt_id} className="flex min-w-0 flex-col gap-4">
        <Heading detail={detail} dirty={false} />
        <div data-locked className="flex flex-col gap-3">
          <p role="note" className="max-w-3xl text-sm">{t(`${P}.unwired.${detail.unwired_reason ?? "unknown"}`)}</p>
          <h4 className="text-sm font-semibold">{t(`${P}.editor.showBaseline`)}</h4>
          <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-sm border border-border bg-surface-raised p-4 text-sm leading-6">{detail.baseline_text}</pre>
        </div>
      </div>
    );
  }

  return (
    <div data-editor={detail.prompt_id} className="grid min-w-0 items-start gap-6 2xl:grid-cols-[minmax(0,1fr)_21rem]">
      <div className="flex min-w-0 flex-col gap-4">
        <Heading detail={detail} dirty={dirty} />
        <Flow dirty={dirty} savedWaiting={savedWaiting !== null} />
        <div data-frame className="flex min-w-0 flex-col gap-2">
          <p className="flex max-w-3xl items-start gap-2 text-sm text-ink-muted">
            <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 shrink-0"><path d="M4.5 7V5a3.5 3.5 0 0 1 7 0v2M3.5 7h9v6.5h-9z" /></svg>
            <span><span className="sr-only">{t(`${P}.editor.frameTitle`)}: </span>{t(`${P}.editor.frameNote`)}</span>
          </p>
          <Technical>
            <pre data-technical className="max-h-64 overflow-auto whitespace-pre-wrap border-l-2 border-border-strong bg-surface-sunken px-3 py-2 font-mono text-xs leading-5 text-ink-muted">{detail.fixed_prefix}</pre>
          </Technical>
        </div>

        <form className="flex min-w-0 flex-col gap-3" onSubmit={(e) => { e.preventDefault(); if (canSave) void save(); }}>
          {pendingLoad ? <div role="alert" className="flex flex-col gap-2 rounded-sm border border-status-you-ink/40 bg-status-you-wash p-3 text-sm">
            <p>{tv(`${P}.loadGuard`, { label: pendingLoad.label === "baseline" ? t(`${P}.baselineName`) : versionName(pendingLoad.label) })}</p><div className="flex flex-wrap gap-2">
              <Button small disabled={busy} onClick={() => { setDraft(pendingLoad.text); setReference(pendingLoad.text); setBasedOn(pendingLoad.label); setNote(""); setAnswer(null); setPendingLoad(null); }}>{t(`${P}.loadDiscard`)}</Button>
              <Button small onClick={() => setPendingLoad(null)}>{t(`${P}.loadStay`)}</Button>
            </div></div> : null}
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <label htmlFor={`${detail.prompt_id}-text`} className="text-sm font-semibold">{t(`${P}.editor.textLabel`)}</label>
            <span className="text-xs text-ink-faint">{tv(`${P}.editor.basedOn`, { label: basedOnName })} · <span className="font-mono">{trimmed.length} / {detail.max_chars}</span></span>
          </div>
          <TextArea
            id={`${detail.prompt_id}-text`}
            aria-label={t(`${P}.editor.textLabel`)}
            name="instruction" rows={18} disabled={busy} spellCheck={false} value={draft}
            onChange={(e) => setDraft(e.target.value)}
            aria-invalid={problem ? true : undefined}
            aria-describedby={`${detail.prompt_id}-hint`}
            className="w-full resize-y text-sm leading-6"
          />
          <p id={`${detail.prompt_id}-hint`} data-problem={problem ? "yes" : "no"} className={`text-sm ${problem ? "text-status-fault" : "text-ink-muted"}`}>
            {problem ?? (duplicateOf ? tv(`${P}.editor.duplicate`, { label: duplicateOf === t(`${P}.baselineName`) ? duplicateOf : versionName(duplicateOf) }) : t(`${P}.editor.notLiveYet`))}
          </p>
          {dirty && differs(draft, reference) ? <LiveDiff from={reference} to={draft} label={basedOnName} /> : null}
          <Field label={t(`${P}.editor.noteLabel`)}>
            <TextInput name="note" disabled={busy} value={note} maxLength={255} onChange={(e) => setNote(e.target.value)} placeholder={t(`${P}.editor.notePlaceholder`)} />
          </Field>
          <p data-declaration className="max-w-3xl text-sm text-ink-muted">{t(`${P}.editor.declaration`)}</p>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" variant="primary" disabled={!canSave}>{busy ? t(`${P}.editor.saving`) : t(`${P}.editor.save`)}</Button>
            <Button disabled={!dirty || busy} onClick={() => { setDraft(reference); setNote(""); setAnswer(null); setPendingLoad(null); }}>{t(`${P}.editor.revert`)}</Button>
          </div>
          {answer ? (
            <p role={answer.ok ? "status" : "alert"} data-answer={answer.ok ? "ok" : "refused"} className={`text-sm ${answer.ok ? "font-medium text-ink" : "text-status-fault"}`}>{answer.text}</p>
          ) : null}
        </form>

        {testing !== null ? (
          <TestRun key={testing} detail={detail} version={testing} studies={studies} clients={clients} onClose={() => setTesting(null)} />
        ) : null}
        {compareOpen ? <Compare options={options} state={compare} onChange={setCompare} side={side} onClose={() => setCompareOpen(false)} /> : null}
      </div>

      <aside aria-label={t(`${P}.versions.title`)} className="flex min-w-0 flex-col gap-5 2xl:sticky 2xl:top-4">
        <div data-running-card className="rounded-md border border-border bg-surface-raised p-4">
          <p className="text-xs font-semibold text-ink-faint">{t(`${P}.liveLabel`)}</p>
          <p className="mt-0.5 text-base font-semibold">{running}</p>
          <p className="text-sm text-ink-muted">
            {detail.active.activated_by ? tv(`${P}.activatedBy`, { who: people(detail.active.activated_by), when: when(detail.active.activated_at) }) : t(`${P}.runsFromCode`)}
          </p>
          <Technical>
            <p data-technical className="mt-2 break-words text-xs text-ink-faint"><code className="break-all">{detail.prompt_id}</code> · {tv(`${P}.baselineVersion`, { version: detail.baseline_version })} · SHA-256 <code>{short(detail.active.text_sha256)}</code></p>
          </Technical>
        </div>

        {savedWaiting !== null && !activating ? (
          <div data-next-step className="flex flex-col gap-2 rounded-md border border-signal-edge bg-signal-wash p-4 text-sm">
            <p><strong className="font-semibold">{tv(`${P}.next.saved`, { label: versionName(`e${savedWaiting}`) })}</strong> {t(`${P}.next.what`)}</p>
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" onClick={() => setActivating({ version: savedWaiting })}>{tv(`${P}.versions.activate`, { label: versionAcc(`e${savedWaiting}`) })}</Button>
              {canTest ? <Button onClick={() => setTesting(savedWaiting)}>{t(`${P}.versions.test`)}</Button> : null}
            </div>
          </div>
        ) : null}

        <div ref={activationRef}>
          {activating ? (
            <Activation
              key={`${activating.version}`}
              detail={detail}
              version={activating.version}
              record={activating.version === null ? undefined : versionOf(activating.version)}
              label={activating.version === null ? t(`${P}.baselineName`) : versionName(`e${activating.version}`)}
              dirty={dirty}
              onCancel={() => setActivating(null)}
              onDone={(label, text) => {
                setActivating(null);
                setOffer(null);
                if (!dirty) { setDraft(text); setReference(text); setBasedOn(label); }
                setAnswer({ ok: true, text: tv(`${P}.activate.done`, { label: activating.version === null ? t(`${P}.baselineName`) : versionName(label) }) });
                reload();
              }}
              textOf={textOf}
            />
          ) : null}
        </div>

        <Versions
          detail={detail} people={people} canTest={canTest} offered={activating ? null : savedWaiting}
          onLoad={(text, label) => {
            if (busy) return;
            if (dirty) { setPendingLoad({ text, label }); return; }
            setDraft(text); setReference(text); setBasedOn(label); setAnswer(null); setPendingLoad(null);
          }}
          onCompare={(key) => { setCompare((c) => ({ ...c, a: key })); setCompareOpen(true); }}
          onActivate={(version) => setActivating({ version })}
          onTest={(version) => setTesting(version)}
        />

        <History detail={detail} people={people} />
      </aside>
    </div>
  );
}

/** The prompt's name, what its family does, and whether an edit waits to be saved. */
function Heading({ detail, dirty }: { detail: PromptSlotDetail; dirty: boolean }) {
  return (
    <header className="flex flex-col gap-1">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="text-xl font-semibold">{nameOf(detail.prompt_id)}</h3>
        {dirty ? <span className="text-sm font-medium text-status-you-ink">{t(`${P}.guard.unsaved`)}</span> : null}
      </div>
      <p className="max-w-3xl text-sm text-ink-muted">{t(`${P}.about.${detail.family}`)}</p>
    </header>
  );
}

/** The safe order of a change: edit, save a version, try it (optional), switch it on. */
function Flow({ dirty, savedWaiting }: { dirty: boolean; savedWaiting: boolean }) {
  const now = savedWaiting ? 4 : dirty ? 2 : 1;
  return (
    <ol data-prompt-flow aria-label={t(`${P}.flow.label`)} className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
      {([1, 2, 3, 4] as const).map((n) => {
        const st = n === 3 ? (savedWaiting ? "optional" : "") : n < now ? "done" : n === now ? "now" : "";
        return (
          <li key={n} data-state={st || "later"} className={`flex items-center gap-2 ${st === "now" ? "font-semibold text-signal" : st === "done" ? "text-ink" : "text-ink-faint"}`}>
            <span aria-hidden="true" className={`inline-flex size-5 items-center justify-center rounded-full border font-mono text-[11px] ${st === "done" ? "border-ink bg-ink text-surface-raised" : st === "now" ? "border-signal" : "border-border-strong"}`}>{n}</span>
            {t(`${P}.flow.step${n}`)}
          </li>
        );
      })}
    </ol>
  );
}

/** What the edit changes against the text it started from, as it is typed. */
function LiveDiff({ from, to, label }: { from: string; to: string; label: string }) {
  const deferred = useDeferredValue(to);
  const ops = useMemo(() => diffLines(from, deferred), [from, deferred]);
  const { added, removed } = summarise(ops);
  const changed = ops.filter((op) => op.kind !== "same");
  return (
    <div data-live-diff className="rounded-sm border border-border bg-surface-raised">
      <p className="border-b border-border px-3 py-1.5 text-xs font-semibold text-ink-faint">{tv(`${P}.editor.liveDiff`, { label, added, removed })}</p>
      <div className="max-h-48 overflow-auto py-1 text-[13px] leading-5">
        {changed.map((op, i) => (
          <div key={i} data-diff={op.kind} className={`flex gap-2 px-3 ${op.kind === "add" ? "bg-status-running-wash" : "bg-status-fault-wash"}`}>
            <span aria-hidden className="w-3 shrink-0 select-none text-ink-faint">{op.kind === "add" ? "+" : "−"}</span>
            <span className="sr-only">{t(`${P}.compare.${op.kind}`)}: </span>
            <span className="whitespace-pre-wrap break-words">{op.text || " "}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- versions

function Versions({ detail, people, canTest, offered, onLoad, onCompare, onActivate, onTest }: {
  detail: PromptSlotDetail; people: People; canTest: boolean;
  /** The version the next-step card offers to switch on: its own button is the one, never two. */
  offered: number | null;
  onLoad: (text: string, label: string) => void;
  onCompare: (key: string) => void;
  onActivate: (version: number | null) => void;
  onTest: (version: number) => void;
}) {
  const baselineRunning = detail.active.origin === "baseline";
  const row = (v: PromptVersion | null) => {
    const running = v === null ? baselineRunning : detail.active.version_number === v.version_number;
    const key = v === null ? "baseline" : `v${v.version_number}`;
    const label = v === null ? t(`${P}.baselineName`) : versionName(v.label);
    return (
      <li key={key} data-version={key} data-running={running ? "yes" : "no"} className="flex min-w-0 flex-col gap-2 py-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <strong className="text-sm">{label}</strong>
          {running ? <span className="text-xs font-semibold text-signal">{t(`${P}.versions.running`)}</span> : null}
        </div>
        <p className="break-words text-xs text-ink-muted">{v === null ? t(`${P}.versions.byCode`) : <><span>{people(v.created_by)}</span> · <span>{when(v.created_at)}</span></>}</p>
        {v?.note ? <p className="break-words text-sm text-ink-muted">{v.note}</p> : null}
        <div className="flex flex-wrap gap-2">
          <Button small onClick={() => onLoad(v === null ? detail.baseline_text : v.text, v === null ? "baseline" : v.label)}>{t(`${P}.versions.load`)}</Button>
          <Button small onClick={() => onCompare(key)}>{t(`${P}.versions.compare`)}</Button>
          {!running && (v === null || v.version_number !== offered) ? <Button small onClick={() => onActivate(v === null ? null : v.version_number)}>{v === null ? t(`${P}.versions.reset`) : tv(`${P}.versions.activate`, { label: versionAcc(v.label) })}</Button> : null}
          {v !== null && canTest ? <Button small onClick={() => onTest(v.version_number)}>{t(`${P}.versions.test`)}</Button> : null}
        </div>
      </li>
    );
  };
  return (
    <section aria-labelledby="pv-h" className="flex flex-col">
      <h4 id="pv-h" className="text-sm font-semibold">{t(`${P}.versions.title`)}</h4>
      <ul className="flex flex-col divide-y divide-border">
        {[...detail.versions].map((v) => row(v))}
        {row(null)}
      </ul>
      {!detail.versions.length ? <p className="text-xs text-ink-faint">{t(`${P}.versions.none`)}</p> : null}
      {!canTest && actionOf(detail.prompt_id) !== null ? <p data-test-off className="mt-2 text-xs text-ink-muted">{t(`${P}.test.noFictional`)}</p> : null}
      {detail.versions.length ? (
        <div data-approval className="mt-3 flex flex-col gap-2 border-t border-border pt-3">
          <h5 className="text-sm font-semibold">{t(`${P}.approval.title`)}</h5>
          <ul className="flex flex-col gap-1 text-xs">
            {detail.versions.map((v) => (
              <li key={v.version_number} data-material={v.label}>
                <strong>{versionName(v.label)}</strong> ·{" "}
                {v.declared_class
                  ? tv(`${P}.approval.declaredBy`, { who: people(v.declared_by), when: when(v.declared_at) })
                  : <span data-undeclared>{t(`${P}.approval.undeclared`)}</span>}
                <Technical>{" · "}{t(`${P}.approval.hash`)}: <code className="break-all">{v.material_sha256}</code></Technical>
              </li>
            ))}
          </ul>
          <Technical><p data-technical className="text-xs text-ink-muted">{t(`${P}.approval.text`)}</p></Technical>
        </div>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------- activation

function Activation({ detail, version, record, label, dirty, onCancel, onDone, textOf }: {
  detail: PromptSlotDetail; version: number | null; record: PromptVersion | undefined; label: string; dirty: boolean;
  onCancel: () => void; onDone: (label: string, text: string) => void; textOf: (version: number | null) => string;
}) {
  const router = useRouter();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Only a version saved before declarations existed waits for an operator: every other edit
  // carries its author's declaration, which classifies it.
  const undeclared = version !== null && !record?.declared_class;
  async function go() {
    setBusy(true);
    setError(null);
    try {
      const active = await admin.activatePrompt(detail.prompt_id, version, reason.trim());
      onDone(active.label, textOf(version));
    } catch (e) {
      if (e instanceof Unauthenticated) {
        router.replace(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search + window.location.hash)}`);
        return;
      }
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section data-activation aria-labelledby="pa-h" className="flex flex-col gap-3 rounded-sm border border-status-you-ink/40 bg-status-you-wash p-4">
      <h4 id="pa-h" className="text-sm font-semibold">{version === null ? t(`${P}.activate.resetTitle`) : tv(`${P}.activate.title`, { label: version === null ? label : versionAcc(`e${version}`) })}</h4>
      <p className="text-sm">{tv(`${P}.activate.impact`, { from: detail.active.origin === "stored" ? detail.active.label : t(`${P}.baselineName`), to: label })}</p>
      <p className="text-xs text-ink-muted">{t(`${P}.activate.queuedKeep`)}</p>
      {undeclared ? <p data-needs-approval className="text-xs text-ink-muted">{tv(`${P}.activate.needsApproval`, { label })}</p> : null}
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

function Compare({ options, state, onChange, side, onClose }: {
  options: Option[]; state: { a: string; b: string }; onChange: (s: { a: string; b: string }) => void; side: (key: string) => Option; onClose: () => void;
}) {
  const a = side(state.a);
  const b = side(state.b);
  const ops = useMemo(() => diffLines(a.text, b.text), [a.text, b.text]);
  const { added, removed } = summarise(ops);
  const same = !differs(a.text, b.text);
  const ref = useRef<HTMLElement>(null);
  useEffect(() => { ref.current?.scrollIntoView?.({ block: "nearest", behavior: "smooth" }); }, []);
  return (
    <section ref={ref} data-compare aria-labelledby="pc-h" className="flex flex-col gap-3 rounded-md border border-border bg-surface-raised p-4">
      <div className="flex items-center justify-between gap-2">
        <h4 id="pc-h" className="text-sm font-semibold">{t(`${P}.compare.title`)}</h4>
        <Button small variant="quiet" onClick={onClose}>{t(`${P}.compare.close`)}</Button>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t(`${P}.compare.from`)}>
          <Select value={state.a} onChange={(e) => onChange({ ...state, a: e.target.value })} className="w-full sm:w-auto">
            {options.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
          </Select>
        </Field>
        <Field label={t(`${P}.compare.to`)}>
          <Select value={state.b} onChange={(e) => onChange({ ...state, b: e.target.value })} className="w-full sm:w-auto">
            {options.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
          </Select>
        </Field>
        <span data-summary className="pb-2 text-xs text-ink-muted">{same ? t(`${P}.compare.same`) : tv(`${P}.compare.summary`, { added, removed })}</span>
      </div>
      {same ? null : (
        <pre aria-label={t(`${P}.compare.title`)} className="max-h-96 overflow-auto rounded-sm border border-border bg-surface p-0 text-[13px] leading-5">
          {ops.map((op, i) => (
            <div
              key={i}
              data-diff={op.kind}
              className={`flex gap-2 px-2 ${op.kind === "add" ? "bg-status-running-wash text-ink" : op.kind === "del" ? "bg-status-fault-wash text-ink" : "text-ink-muted"}`}
            >
              <span aria-hidden className="w-3 shrink-0 select-none text-ink-faint">{op.kind === "add" ? "+" : op.kind === "del" ? "−" : " "}</span>
              <span className="sr-only">{t(`${P}.compare.${op.kind === "same" ? "same_line" : op.kind}`)}: </span>
              <span className="whitespace-pre-wrap break-words font-sans">{op.text || " "}</span>
            </div>
          ))}
        </pre>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- history

function History({ detail, people }: { detail: PromptSlotDetail; people: People }) {
  return (
    <section data-history aria-labelledby="ph-h" className="flex flex-col gap-1">
      <h4 id="ph-h" className="text-sm font-semibold">{t(`${P}.history.title`)}</h4>
      {detail.history.length ? (
        <ul className="flex flex-col gap-1 text-sm">
          {detail.history.map((h) => (
            <li key={h.activation_id} data-activation-row>
              <strong>{h.label ? versionName(h.label) : t(`${P}.baselineName`)}</strong> · {people(h.activated_by)} · {when(h.activated_at)}
              {h.reason ? <span className="text-ink-muted"> — {h.reason}</span> : null}
            </li>
          ))}
        </ul>
      ) : <p className="text-sm text-ink-muted">{t(`${P}.history.none`)}</p>}
    </section>
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
  // Only studies of a client the deployment lists as fictional; the API refuses any other server-side.
  const fictional = new Set(detail.draft_test_client_ids);
  const eligible = studies.ok
    ? studies.data.map((r) => r.study).filter((s) => s.kind === "RESEARCH" && s.accepts_work && fictional.has(s.client_id))
    : [];
  const [studyId, setStudyId] = useState(eligible[0]?.study_id ?? "");
  const [revisions, setRevisions] = useState<{ id: string; label: string }[] | null>(null);
  const [revisionId, setRevisionId] = useState("");
  const [job, setJob] = useState<ResearchAgentJob | null>(null);
  const [result, setResult] = useState<ResearchAgentResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The study's confirmation threshold asks before a job that reaches it (LO15): answered here.
  const [costAsk, setCostAsk] = useState<{ message: string; resolve: (yes: boolean) => void } | null>(null);
  const confirmCost = (message: string) => new Promise<boolean>((resolve) => setCostAsk({ message, resolve }));
  const answerCost = (yes: boolean) => { costAsk?.resolve(yes); setCostAsk(null); };
  const resultFor = useRef<string | null>(null);
  const [resultRetry, setResultRetry] = useState(0);
  const [resultFailed, setResultFailed] = useState(false);
  const generation = useRef(0);
  useEffect(() => () => { generation.current += 1; }, []);
  const changeStudy = (id: string) => {
    generation.current += 1;
    setStudyId(id); setJob(null); setResult(null); setError(null); setResultFailed(false);
    resultFor.current = null;
  };

  const fail = (e: unknown) => {
    if (e instanceof Unauthenticated) {
      router.replace(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search + window.location.hash)}`);
      return;
    }
    setError(describeError(e));
  };

  // The study's design revisions, newest first; the newest is the default.
  useEffect(() => {
    if (!studyId) return;
    let live = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- another study's revisions are cleared before its own are read
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

  // A failed read can retry the result, never the paid model call. Old reads cannot
  // attach a result to another study, job or unmounted test panel.
  useEffect(() => {
    if (!job || !studyId) return;
    let live = true;
    if (job.is_terminal || job.needs_attention || job.status.startsWith("WAITING")) {
      if (job.status === "COMPLETED" && resultFor.current !== job.run_id) {
        resultFor.current = job.run_id;
        researchAgents.result(studyId, job.run_id).then(
          (value) => { if (live) { setResult(value); setResultFailed(false); } },
          (e: unknown) => { if (live) { fail(e); setResultFailed(true); } },
        );
      }
      return () => { live = false; };
    }
    const timer = setTimeout(() => {
      researchAgents.job(studyId, job.run_id).then((value) => { if (live) setJob(value); }, (e: unknown) => { if (live) fail(e); });
    }, POLL_MS);
    return () => { live = false; clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job, studyId, resultRetry]);

  async function run() {
    if (!action || busy || !revisionId || (!!job && !job.is_terminal)) return;
    const operation = ++generation.current;
    setBusy(true);
    setError(null);
    setResult(null);
    resultFor.current = null;
    try {
      const queued = await withJobCostConfirmation(
        (usd) => researchAgents.start(studyId, revisionId, action, "", version, usd),
        confirmCost,
      );
      if (generation.current === operation) setJob(queued);
    } catch (e) {
      if (generation.current === operation) fail(e);
    } finally {
      if (generation.current === operation) setBusy(false);
    }
  }

  return (
    <section data-test-run aria-labelledby="pt-h" className="flex flex-col gap-3 rounded-sm border border-border p-4">
      <div className="flex items-center justify-between gap-2">
        <h4 id="pt-h" className="text-sm font-semibold">{tv(`${P}.test.title`, { label: versionAcc(`e${version}`) })}</h4>
        <Button small variant="quiet" onClick={onClose}>{t(`${P}.test.close`)}</Button>
      </div>
      <p className="max-w-3xl text-sm text-ink-muted">{t(`${P}.test.intro`)}</p>
      <p role="note" className="text-xs text-ink-muted">{t(`${P}.test.cost`)}</p>
      {!eligible.length ? <Empty>{t(`${P}.test.${fictional.size ? "noStudies" : "noFictional"}`)}</Empty> : (
        <div className="flex flex-wrap items-end gap-3">
          <Field label={t(`${P}.test.study`)}>
            <Select value={studyId} disabled={busy || (!!job && !job.is_terminal)} onChange={(e) => changeStudy(e.target.value)} className="w-full sm:w-auto">
              {eligible.map((s) => <option key={s.study_id} value={s.study_id}>{s.name} · {clientName.get(s.client_id) ?? s.client_id}</option>)}
            </Select>
          </Field>
          <Field label={t(`${P}.test.revision`)}>
            <Select value={revisionId} onChange={(e) => setRevisionId(e.target.value)} className="w-full sm:w-auto" disabled={!revisions?.length || busy || (!!job && !job.is_terminal)}>
              {(revisions ?? []).map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
            </Select>
          </Field>
          <Button variant="primary" disabled={busy || !revisionId || (!!job && !job.is_terminal)} onClick={() => void run()}>
            {busy ? t(`${P}.test.starting`) : t(`${P}.test.start`)}
          </Button>
        </div>
      )}
      {revisions && !revisions.length && studyId ? <p className="text-xs text-ink-muted">{t(`${P}.test.noRevision`)}</p> : null}
      {costAsk ? (
        <div role="alertdialog" aria-labelledby="pt-cost" data-cost-ask className="flex flex-col gap-2 rounded-sm border border-border p-3 text-sm">
          <p id="pt-cost">{costAsk.message}</p>
          <div className="flex gap-2">
            <Button variant="primary" onClick={() => answerCost(true)}>{t(`${P}.test.costConfirm`)}</Button>
            <Button onClick={() => answerCost(false)}>{t(`${P}.test.costDecline`)}</Button>
          </div>
        </div>
      ) : null}
      {error ? <p role="alert" data-refusal className="text-sm text-status-fault">{error}</p> : null}
      {resultFailed ? <Button onClick={() => { resultFor.current = null; setResultFailed(false); setError(null); setResultRetry((n) => n + 1); }}>{t(`${P}.retryResult`)}</Button> : null}
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
