"use client";

// The system prompts tab: what each step tells the model, edited here (ADR 0020).
//
// What an administrator can do: read a prompt, edit its instruction, save the edit as
// a new version, compare versions, put one live, and go back to the wording shipped in
// code. What they cannot: edit the code's frame around
// the instruction (shown, never editable) or make an edit take effect for a job already
// queued -- a job keeps the prompt it was queued with. A saved version does not run until
// it is put live. By default the author may do that themselves (ADR 0019: no approval
// between people); an organization that requires independent review gets a refusal for
// the author instead, shown as the API gave it.
//
// Nothing here calls a model or starts paid work: trying a draft from Settings was removed
// (X10, system-prompts-settings #14; the product owner, 2026-10-20). Paid AI work starts only
// through the Lead in a study; a version's effect is seen on the next real job, which pins it.

import { useRouter } from "next/navigation";
import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";

import { t, tv } from "@/i18n/t";
import {
  type Member,
  type PromptSlotDetail,
  type PromptSlotSummary,
  type PromptVersion,
  type SettingsDocument,
  Unauthenticated,
  admin,
} from "@/lib/api";
import { relative } from "@/lib/format";
import { diffLines, differs, summarise } from "@/lib/text-diff";
import { Button, Field, Select, TextArea, TextInput } from "../../rehome/ui";
import { Technical } from "./technical";
import { Empty, Loaded } from "../states";
import { useResource } from "../useResource";
import type { Part } from "./ControlPanel";
import { describeError } from "./errors";
import { waitingChanged } from "./sections";
import { PhosphorIcon } from "../../icons/PhosphorIcon";

const P = "aia.settings.prompts";

/**
 * The version in force, marked the same way wherever it is shown: the list's dot, the editor's chip
 * and the Verze table's row. Green (`in-force`) is the interface's colour for "in force" alone.
 */
const IN_FORCE = "bg-in-force-wash";
const IN_FORCE_EDGE = "shadow-[inset_3px_0_0_var(--in-force)]";
const IN_FORCE_DOT = "bg-in-force";

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
};

/** The tab. Only an organization administrator is shown the prompts, and asked for them. */
export function SystemPromptsPanel({ doc, members }: Props) {
  if (!doc.may_administer) {
    return <p className="text-sm text-ink-muted">{t(`${P}.adminOnly`)}</p>;
  }
  const emails = new Map(members.ok ? members.data.map((m) => [m.user_id, m.email]) : []);
  const people: People = (id) => (id ? (emails.get(id) ?? id) : "—");
  return <>
    <ChangeSteps />
    <Workspace people={people} />
  </>;
}

// ---------------------------------------------------------------- the workspace

async function loadList(): Promise<PromptSlotSummary[]> {
  const rows: unknown = await admin.prompts();
  // A body that is not a list is not "no prompts": say so rather than draw an empty page.
  if (!Array.isArray(rows)) throw new Error(t(`${P}.malformed`));
  return rows as PromptSlotSummary[];
}

function Workspace({ people }: { people: People }) {
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
          <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-6 lg:grid-cols-[13.125rem_minmax(0,1fr)]">
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
                <Editor key={current} promptId={current} people={people} onChanged={reloadList} onDirty={setDirty} />
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

/** "v3": a stored version as the list and the Verze table say it. */
const shortName = (n: number) => tv(`${P}.short`, { n });

/**
 * Whether a stored version waits to be switched on: saved after the last switch-on (or with none
 * ever made). A number above the one in force is not enough -- a rollback to v2 or a reset to the
 * code's wording leaves v3 "dřívější", not waiting (review of #838), and a switch-on settles every
 * version saved before it.
 */
function waitsForActivation(v: Pick<PromptVersion, "version_number" | "created_at">, detail: Pick<PromptSlotDetail, "active" | "history">): boolean {
  if (detail.active.origin === "stored" && detail.active.version_number === v.version_number) return false;
  const last = [detail.active.activated_at, ...detail.history.map((h) => h.activated_at)].filter((x): x is string => !!x).sort().at(-1);
  return last === undefined || v.created_at > last;
}

/**
 * Where a prompt stands, in words: the version in force, and a saved one waiting -- said only where
 * the list knows it. The summary carries no version's date, so a newer number waits only when nothing
 * was ever switched on; otherwise the list does not say, and unknown never reads as waiting.
 */
function standing(row: PromptSlotSummary): { text: string; waiting: boolean } {
  if (!row.wired) return { text: t(`${P}.state.locked`), waiting: false };
  const active = row.active.origin === "stored" ? row.active.version_number : null;
  const live = active === null ? t(`${P}.state.baseline`) : tv(`${P}.state.inForce`, { v: shortName(active) });
  const waiting = row.latest_number !== null && row.active.activated_at === null && row.active.origin === "baseline";
  return { text: waiting ? `${live} · ${tv(`${P}.state.waiting`, { v: shortName(row.latest_number!) })}` : live, waiting };
}

/** How many prompts have a saved version waiting to be switched on, as the list knows it: what the
 *  section menu counts for an administrator (prototype v54), never more than `standing` says. */
export function waitingPrompts(rows: readonly PromptSlotSummary[]): number {
  return rows.filter((row) => standing(row).waiting).length;
}

/** The list: the prompts a person may edit, then those read only, each with where it stands. */
function PromptList({ rows, current, onChoose }: { rows: PromptSlotSummary[]; current: string | null; onChoose: (id: string) => void }) {
  const [query, setQuery] = useState("");
  const q = query.trim().toLocaleLowerCase("cs");
  const matching = rows.filter((r) => `${nameOf(r.prompt_id)} ${r.prompt_id} ${t(`${P}.families.${r.family}`)}`.toLocaleLowerCase("cs").includes(q));
  const groups = [
    { key: "editable", rows: matching.filter((r) => r.wired) },
    { key: "readOnly", rows: matching.filter((r) => !r.wired) },
  ];
  return (
    <nav aria-label={t(`${P}.listLabel`)} className="min-w-0 lg:sticky lg:top-4">
      <div className="flex flex-col gap-2 pb-3">
        <TextInput type="search" aria-label={t(`${P}.search`)} placeholder={t(`${P}.searchPlaceholder`)} value={query} onChange={(e) => setQuery(e.target.value)} />
        <span role="status" className="text-xs text-ink-muted">{tv(`${P}.found`, { shown: matching.length, total: rows.length })}</span>
      </div>
      <div className="flex max-h-64 flex-col overflow-y-auto overscroll-contain rounded-md border border-border lg:max-h-[70vh]">
        {groups.map((group) => group.rows.length ? (
          <div key={group.key} data-group={group.key}>
            <h3 className="px-2.5 pb-1 pt-3 text-[11px] uppercase tracking-[0.06em] text-ink-faint">{t(`${P}.${group.key}`)}</h3>
            <ul className="flex flex-col">
              {group.rows.map((row) => {
                const on = row.prompt_id === current;
                const { text, waiting } = standing(row);
                return (
                  <li key={row.prompt_id}>
                    <button type="button" data-prompt={row.prompt_id} data-waiting={waiting ? "true" : undefined} aria-current={on ? "true" : undefined}
                      onClick={() => onChoose(row.prompt_id)}
                      className={`flex min-h-11 w-full min-w-0 flex-col items-start justify-center gap-0.5 border-b border-border px-2.5 py-2 text-left text-[13px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${on ? "bg-signal-wash shadow-[inset_3px_0_0_var(--signal)]" : waiting ? "bg-status-you-wash hover:bg-surface-sunken" : "hover:bg-surface-sunken"}`}>
                      <span className={`max-w-full break-words ${on ? "font-semibold text-signal" : "text-ink"}`}>{nameOf(row.prompt_id)}</span>
                      <span className="flex max-w-full items-center gap-1.5 text-xs text-ink-muted">
                        {row.wired ? <i aria-hidden="true" className={`size-1.5 shrink-0 rounded-full ${IN_FORCE_DOT}`} /> : null}
                        <span className="truncate">{text}</span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null)}
        {!matching.length ? <div className="flex flex-col gap-2 p-3 text-sm"><p>{t(`${P}.noMatch`)}</p><Button small onClick={() => setQuery("")}>{t(`${P}.clearSearch`)}</Button></div> : null}
      </div>
    </nav>
  );
}

/** "Jak se instrukce mění": the three steps of a change, and why there is no test here. */
function ChangeSteps() {
  return (
    <section data-change-steps aria-labelledby="pf-h" className="mb-5 rounded-md border border-border bg-surface-raised px-5 py-4">
      <h3 id="pf-h" className="text-sm font-semibold">{t(`${P}.flow.label`)}</h3>
      <ol className="mt-2.5 grid grid-cols-[repeat(auto-fit,minmax(11.25rem,1fr))] gap-2.5">
        {([1, 2, 3] as const).map((n) => (
          <li key={n} className="rounded-md border border-border px-3 py-2.5">
            <b className="text-sm font-medium">{n} · {t(`${P}.flow.step${n}`)}</b>
            <p className="mt-0.5 text-xs leading-[18px] text-ink-muted">{t(`${P}.flow.what${n}`)}</p>
          </li>
        ))}
      </ol>
      <p data-no-test className="mt-2.5 text-xs leading-5 text-ink-muted">{t(`${P}.flow.noTest`)}</p>
    </section>
  );
}

// ---------------------------------------------------------------- the editor

/** The text that runs for a prompt now: the active stored version's, or the code's wording. */
function runningText(d: PromptSlotDetail): string {
  if (d.active.origin !== "stored") return d.baseline_text;
  return d.versions.find((v) => v.version_number === d.active.version_number)?.text ?? d.baseline_text;
}

function Editor(props: {
  promptId: string; people: People;
  onChanged: () => void; onDirty: (dirty: boolean) => void;
}) {
  const [detail, reload] = useResource(() => admin.prompt(props.promptId), [props.promptId]);
  return (
    <Loaded res={detail} retry={reload}>
      {(d) => <EditorBody detail={d} {...props} reload={() => { reload(); props.onChanged(); }} />}
    </Loaded>
  );
}

function EditorBody({ detail, people, reload, onDirty }: {
  detail: PromptSlotDetail; people: People;
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
      waitingChanged();
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
  // The newest stored version waiting to be switched on, whoever saved it: the chip the design shows ("v4 čeká").
  const waitingNumbers = detail.versions.filter((v) => waitsForActivation(v, detail)).map((v) => v.version_number);
  if (justSaved && !detail.versions.some((v) => v.version_number === justSaved.version_number)) waitingNumbers.push(justSaved.version_number);
  const waitingNumber = waitingNumbers.length ? Math.max(...waitingNumbers) : null;
  const basedOnName = basedOn === "baseline" ? t(`${P}.baselineName`) : versionName(basedOn);

  if (!detail.wired) {
    return (
      <div data-editor={detail.prompt_id} className="flex min-w-0 flex-col gap-4">
        <Heading detail={detail} dirty={false} waiting={null} />
        <div data-locked className="flex flex-col gap-3">
          <p role="note" className="max-w-3xl text-sm">{t(`${P}.unwired.${detail.unwired_reason ?? "unknown"}`)}</p>
          <h4 className="text-sm font-semibold">{t(`${P}.editor.showBaseline`)}</h4>
          <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-sm border border-border bg-surface-raised p-4 text-sm leading-6">{detail.baseline_text}</pre>
        </div>
      </div>
    );
  }

  return (
    <div data-editor={detail.prompt_id} className="flex min-w-0 flex-col gap-6">
      <div className="flex min-w-0 flex-col gap-4">
        <Heading detail={detail} dirty={dirty} waiting={waitingNumber} />
        <div data-frame className="flex min-w-0 flex-col gap-2">
          <p className="flex max-w-3xl items-start gap-2 text-sm text-ink-muted">
            <PhosphorIcon name="lock-simple" className="mt-0.5 shrink-0" />
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
            name="instruction" rows={20} disabled={busy} spellCheck={false} value={draft}
            onChange={(e) => setDraft(e.target.value)}
            aria-invalid={problem ? true : undefined}
            aria-describedby={`${detail.prompt_id}-hint`}
            className="min-h-[28.75rem] w-full resize-y text-[13px] leading-5"
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

        {compareOpen ? <Compare options={options} state={compare} onChange={setCompare} side={side} onClose={() => setCompareOpen(false)} /> : null}
      </div>

      <aside aria-label={t(`${P}.versions.title`)} className="flex min-w-0 flex-col gap-5">
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
          detail={detail} people={people} offered={activating ? null : savedWaiting}
          onLoad={(text, label) => {
            if (busy) return;
            if (dirty) { setPendingLoad({ text, label }); return; }
            setDraft(text); setReference(text); setBasedOn(label); setAnswer(null); setPendingLoad(null);
          }}
          onCompare={(key) => { setCompare((c) => ({ ...c, a: key })); setCompareOpen(true); }}
          onActivate={(version) => setActivating({ version })}
        />

        <History detail={detail} people={people} />
      </aside>
    </div>
  );
}

/** The prompt's name, its state as chips, what it does and where it runs. */
function Heading({ detail, dirty, waiting }: { detail: PromptSlotDetail; dirty: boolean; waiting: number | null }) {
  const key = detail.prompt_id.replaceAll(".", "_");
  const purpose = t(`${P}.purpose.${key}`);
  const where = t(`${P}.where.${key}`);
  const known = (text: string, k: string) => text !== `${P}.${k}.${key}`;
  const chip = "inline-flex min-h-[22px] items-center rounded-pill border px-2 text-xs";
  return (
    <header className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <h3 className="text-xl font-semibold">{nameOf(detail.prompt_id)}</h3>
        {!detail.wired ? <span className={`${chip} border-border text-ink-muted`}>{t(`${P}.chips.fixed`)}</span> : <>
          <span data-prompt-in-force className={`${chip} border-in-force font-medium text-ink ${IN_FORCE}`}>
            {detail.active.origin === "stored" ? tv(`${P}.chips.inForce`, { v: shortName(detail.active.version_number!) }) : t(`${P}.chips.inForceBaseline`)}
          </span>
          {waiting !== null ? <span data-waiting-chip className={`${chip} border-status-you-ink/40 bg-status-you-wash text-ink`}>{tv(`${P}.chips.waiting`, { v: shortName(waiting) })}</span> : null}
          {dirty ? <span className={`${chip} border-status-you-ink/40 font-medium text-status-you-ink`}>{t(`${P}.guard.unsaved`)}</span> : null}
        </>}
      </div>
      <dl className="grid max-w-3xl grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-ink-faint">{t(`${P}.whatItDoes`)}</dt>
        <dd className="text-ink-muted">{known(purpose, "purpose") ? purpose : t(`${P}.about.${detail.family}`)}</dd>
        {known(where, "where") ? <><dt className="text-ink-faint">{t(`${P}.whereItRuns`)}</dt><dd className="text-ink-muted">{where}</dd></> : null}
      </dl>
    </header>
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

function Versions({ detail, people, offered, onLoad, onCompare, onActivate }: {
  detail: PromptSlotDetail; people: People;
  /** The version the next-step card offers to switch on: its own button is the one, never two. */
  offered: number | null;
  onLoad: (text: string, label: string) => void;
  onCompare: (key: string) => void;
  onActivate: (version: number | null) => void;
}) {
  const activeNumber = detail.active.origin === "stored" ? detail.active.version_number : null;
  const head = "px-2 py-1.5 text-left text-xs font-normal text-ink-faint";
  const cell = "border-t border-border px-2 py-2 align-top";
  const row = (v: PromptVersion | null) => {
    const running = v === null ? activeNumber === null : activeNumber === v.version_number;
    const waiting = v !== null && !running && waitsForActivation(v, detail);
    const key = v === null ? "baseline" : `v${v.version_number}`;
    const state = running ? t(`${P}.versions.stateInForce`) : waiting ? t(`${P}.versions.stateWaiting`) : v === null ? t(`${P}.versions.stateCode`) : t(`${P}.versions.stateEarlier`);
    const tone = running ? `${IN_FORCE} ${IN_FORCE_EDGE}` : waiting ? "bg-status-you-wash" : "";
    // The actions stand on a row of their own under the version's facts: a fifth column of buttons
    // pushed the page wider than 1024 px (proposal_prompt_journey).
    return (
      <tbody key={key} data-version={key} data-running={running ? "yes" : "no"} className={tone}>
      <tr>
        <td className={`${cell} font-medium sm:whitespace-nowrap`}>
          {v === null ? t(`${P}.baselineName`) : shortName(v.version_number)}
          {/* Under 640 px the author and the time stand under the version: the row keeps every fact without a scroll. */}
          <span className="block text-xs font-normal text-ink-muted sm:hidden">{v === null ? t(`${P}.versions.byCode`) : `${people(v.created_by)} · ${when(v.created_at)}`}</span>
        </td>
        <td className={`${cell} ${running ? "text-ink" : waiting ? "text-ink" : "text-ink-muted"}`}>
          <span className="inline-flex items-center gap-1.5 xl:whitespace-nowrap">
            <i aria-hidden="true" className={`size-1.5 shrink-0 rounded-full ${running ? IN_FORCE_DOT : waiting ? "bg-status-you" : "bg-border-strong"}`} />{state}
          </span>
          {v?.note ? <span className="block break-words text-xs text-ink-muted">{v.note}</span> : null}
        </td>
        <td className={`${cell} hidden break-words text-ink-muted sm:table-cell`}>{v === null ? t(`${P}.versions.byCode`) : people(v.created_by)}</td>
        <td className={`${cell} hidden whitespace-nowrap text-ink-muted sm:table-cell`}>{v === null ? "—" : when(v.created_at)}</td>
      </tr>
      <tr>
        <td colSpan={4} className="px-2 pb-2">
          <div className="flex flex-wrap gap-1.5">
            <Button small onClick={() => onLoad(v === null ? detail.baseline_text : v.text, v === null ? "baseline" : v.label)}>{t(`${P}.versions.load`)}</Button>
            <Button small onClick={() => onCompare(key)}>{t(`${P}.versions.compare`)}</Button>
            {!running && (v === null || v.version_number !== offered) ? <Button small onClick={() => onActivate(v === null ? null : v.version_number)}>{v === null ? t(`${P}.versions.reset`) : tv(`${P}.versions.activate`, { label: versionAcc(v.label) })}</Button> : null}
          </div>
        </td>
      </tr>
      </tbody>
    );
  };
  return (
    <section aria-labelledby="pv-h" className="flex min-w-0 flex-col">
      <h4 id="pv-h" className="text-sm font-semibold">{t(`${P}.versions.title`)}</h4>
      <div className="mt-1 max-w-full overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th scope="col" className={head}>{t(`${P}.versions.col.version`)}</th>
              <th scope="col" className={head}>{t(`${P}.versions.col.state`)}</th>
              <th scope="col" className={`${head} hidden sm:table-cell`}>{t(`${P}.versions.col.author`)}</th>
              <th scope="col" className={`${head} hidden sm:table-cell`}>{t(`${P}.versions.col.when`)}</th>
            </tr>
          </thead>
          {[...detail.versions].map((v) => row(v))}
          {row(null)}
        </table>
      </div>
      {!detail.versions.length ? <p className="text-xs text-ink-faint">{t(`${P}.versions.none`)}</p> : null}
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
      waitingChanged();
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
