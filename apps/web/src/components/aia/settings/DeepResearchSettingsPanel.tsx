"use client";

// The Deep Research tab: every policy value Deep Research runs by, what is in force
// and who approved it (ADR 0022, GET /api/v1/deep-research/settings). Until someone
// approves a value, the code's proposed default is in force and is labelled so. An
// administrator proposes a value -- a new version, not yet in force -- and approves a
// version or withdraws to the default; each change takes effect for runs enqueued
// after it. Switches, secrets and the model route are not here: they stay in the
// deployment, and no setting turns a rail off. What is allowed is the API's to say:
// its refusal is shown as it gave it.

import { type FormEvent, useCallback, useEffect, useState } from "react";

import { useRouter } from "next/navigation";
import { InlineConfirm } from "../../rehome/step";
import { DR_GROUP_HELP, researchPolicyHelp } from "./settings-guide";
import { cs } from "@/i18n/cs";
import { t, tv } from "@/i18n/t";
import {
  type DrSetting,
  type DrSettingDetail,
  type DrSettingValue,
  type DrSettingsOverview,
  deepResearchSettings,
} from "@/lib/api";
import { STATUS_VALUES, groupsInOrder, inputKind, parseInput, toInput } from "@/lib/deep-research-settings";
import { relative } from "@/lib/format";
import { Button, Field, Select, TextArea, TextInput } from "../../rehome/ui";
import { Technical } from "./technical";
import { Loaded } from "../states";
import { useResource } from "../useResource";
import { describeError } from "./errors";

const D = "aia.settings.deepResearch";
const LABELS: Record<string, string> = cs.aia.settings.deepResearch.labels;
const UNITS: Record<string, string> = cs.aia.settings.deepResearch.units;

type People = (id: string | null) => string;

const when = (iso: string | null) => (iso ? (relative(iso) ?? iso) : "—");
const number = new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: 6 });

/** A setting's name in Czech; the catalogue's own label when the page has none for it. */
export const labelOf = (s: Pick<DrSetting, "key" | "label">) => LABELS[s.key] ?? s.label;

/** A value as a reader sees it. Null is unknown -- the code holds nothing -- never zero. */
export function showValue(type: string, value: DrSettingValue): string {
  if (value === null) return t(`${D}.unknown`);
  if (typeof value === "boolean") return t(`${D}.${value ? "yes" : "no"}`);
  if (Array.isArray(value)) return value.length ? value.join(", ") : t(`${D}.emptyList`);
  if (typeof value === "number") return number.format(value);
  if (inputKind(type) === "status") return t(`${D}.status.${value}`);
  return value;
}

function unitOf(s: DrSetting): string {
  return s.unit ? (UNITS[s.unit] ?? s.unit) : "";
}

function bounds(s: DrSetting): string | null {
  const min = s.minimum === null ? null : number.format(s.minimum);
  const max = s.maximum === null ? null : number.format(s.maximum);
  if (min !== null && max !== null) return tv(`${D}.bounds`, { min, max });
  if (min !== null) return tv(`${D}.boundsMin`, { min });
  if (max !== null) return tv(`${D}.boundsMax`, { max });
  return null;
}

async function load(): Promise<DrSettingsOverview> {
  const body: unknown = await deepResearchSettings.list();
  // A body without a list is not "no settings": say so rather than draw an empty tab.
  if (!body || typeof body !== "object" || !Array.isArray((body as DrSettingsOverview).settings)) {
    throw new Error(t(`${D}.malformed`));
  }
  return body as DrSettingsOverview;
}

export function DeepResearchSettingsPanel({ people }: { people: People }) {
  const [res, retry] = useResource(load, []);
  return <Loaded res={res} retry={retry}>{(overview) => <Overview overview={overview} people={people} reload={retry} />}</Loaded>;
}

const TH = "px-2 py-1 text-left font-mono text-[11px] font-normal uppercase tracking-[0.08em] text-ink-faint";
const TD = "px-2 py-2 align-top text-sm";
const FLAGS = ["required_for_live", "lower_only", "method"] as const;

// The canvas design (AIA desktop research studio, "Nastavení · Deep Research"): the groups on
// the left with what still waits in each, the chosen group's rules as a table, and a rule's
// change opened in place beneath its row -- propose, then approve. Every group stays mounted
// and is only hidden, so a draft survives a change of group; a search or the live filter
// shows the matches of every group at once.
function Overview({ overview, people, reload }: { overview: DrSettingsOverview; people: People; reload: () => void }) {
  const [open, setOpen] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [liveOnly, setLiveOnly] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [pending, setPending] = useState<{ key: string | null } | null>(null);
  const groups = groupsInOrder(overview.settings);
  const [chosen, setChosen] = useState(() => groups.find((g) => g.group === "budgets")?.group ?? groups[0]?.group ?? "");
  const toggle = (key: string) => {
    const next = open === key ? null : key;
    if (dirty) setPending({ key: next }); else { setOpen(next); setDirty(false); }
  };
  const missing = new Set(overview.missing_for_live);
  const q = query.trim().toLocaleLowerCase("cs");
  const across = !!q || liveOnly;
  const matches = (s: DrSetting) => (s.key === open && dirty) ||
    (`${labelOf(s)} ${s.key} ${researchPolicyHelp(s.key, s.group)}`.toLocaleLowerCase("cs").includes(q) && (!liveOnly || missing.has(s.key)));
  const anyVisible = overview.settings.some(matches);
  return (
    <div className="flex flex-col gap-4">
      {overview.may_administer ? null : <p className="text-sm text-ink-muted">{t(`${D}.adminNote`)}</p>}
      <Technical><p data-technical className="text-xs text-ink-faint">{tv(`${D}.catalogue`, { version: overview.catalogue_version })}</p></Technical>
      <Readiness count={missing.size} liveOnly={liveOnly} onToggle={() => setLiveOnly((v) => !v)} />
      {pending ? <InlineConfirm message={t(`${D}.draftGuard`)} action={t(`${D}.discardDraft`)} onCancel={() => setPending(null)} onConfirm={() => { setOpen(pending.key); setDirty(false); setPending(null); }} /> : null}
      <div className="grid min-w-0 gap-4 lg:grid-cols-[15rem_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-2">
          <TextInput type="search" aria-label={t(`${D}.search`)} placeholder={t(`${D}.searchPlaceholder`)} value={query} onChange={(e) => setQuery(e.target.value)} />
          <nav aria-label={t(`${D}.groupsLabel`)} className="flex flex-col gap-0.5">
            {groups.map(({ group, settings }) => {
              const waiting = settings.filter((s) => missing.has(s.key)).length;
              const on = !across && group === chosen;
              return (
                <button
                  key={group} type="button" data-dr-group-link={group} aria-current={on ? "true" : undefined}
                  onClick={() => { setChosen(group); setQuery(""); setLiveOnly(false); }}
                  className={`flex min-h-10 items-center gap-2 rounded-sm px-3 text-left text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${on ? "bg-signal-wash font-semibold text-signal" : "text-ink hover:bg-surface-sunken"}`}
                >
                  <span className="min-w-0 flex-1">{t(`${D}.groups.${group}`)}</span>
                  {waiting ? <span className="rounded-sm border border-status-you-ink/40 bg-status-you-wash px-1.5 text-xs font-semibold text-status-you-ink" title={t(`${D}.waitingHelp`)}>{waiting}</span> : <span className="text-xs text-ink-faint">{settings.length}</span>}
                </button>
              );
            })}
          </nav>
        </div>
        <div className="flex min-w-0 flex-col gap-6">
          {!anyVisible ? <p role="status" className="text-sm text-ink-muted">{t(`${D}.noMatch`)}</p> : null}
          {groups.map(({ group, settings }) => {
            const shown = settings.filter(matches);
            const hidden = across ? !shown.length : group !== chosen;
            return (
              <section key={group} data-dr-group={group} aria-labelledby={`dr-${group}`} hidden={hidden} className="flex min-w-0 flex-col gap-2">
                <div>
                  <h3 id={`dr-${group}`} className="text-base font-semibold">{t(`${D}.groups.${group}`)}</h3>
                  <p className="max-w-3xl text-sm leading-6 text-ink-muted">{DR_GROUP_HELP[group] ?? researchPolicyHelp("", group)}</p>
                </div>
                <div className="overflow-x-auto"><table className="w-full">
                  <thead><tr><th className={TH}>{t(`${D}.col.setting`)}</th><th className={`${TH} w-48`}>{t(`${D}.col.value`)}</th><th className={`${TH} w-24`}><span className="sr-only">{t(`${D}.col.action`)}</span></th></tr></thead>
                  <tbody className="divide-y divide-border">
                    {settings.map((s) => (
                      <Row
                        key={s.key}
                        setting={s}
                        shown={across ? shown.includes(s) : true}
                        missing={missing.has(s.key)}
                        people={people}
                        open={open === s.key}
                        onToggle={() => toggle(s.key)}
                        onDirty={setDirty}
                        mayAdminister={overview.may_administer}
                        onChanged={reload}
                      />
                    ))}
                  </tbody>
                </table></div>
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/** What live still needs, in one line; its button shows exactly those rules. */
function Readiness({ count, liveOnly, onToggle }: { count: number; liveOnly: boolean; onToggle: () => void }) {
  return (
    <div data-live-readiness className={`flex flex-wrap items-center gap-x-4 gap-y-2 rounded-sm border px-4 py-3 text-sm ${count ? "border-status-you/40 bg-status-you-wash" : "border-border bg-surface-raised"}`}>
      <p className="min-w-0 flex-1">
        {count ? <><strong className="font-semibold">{t(`${D}.live.blocked`)}</strong> {tv(`${D}.live.waiting`, { count })}</> : t(`${D}.live.ready`)}{" "}
        <span className="text-ink-muted">{t(`${D}.live.note`)}</span>
      </p>
      {count ? <Button aria-pressed={liveOnly} onClick={onToggle}>{t(`${D}.live.${liveOnly ? "showAll" : "showWaiting"}`)}</Button> : null}
    </div>
  );
}

function Row({ setting: s, shown, missing, people, open, onToggle, mayAdminister, onChanged, onDirty }: {
  setting: DrSetting; shown: boolean; missing: boolean; people: People; open: boolean; onToggle: () => void; mayAdminister: boolean; onChanged: () => void; onDirty: (value: boolean) => void;
}) {
  const approved = s.origin === "approved";
  const range = bounds(s);
  return (
    <>
      <tr data-dr-setting={s.key} data-missing={missing ? s.key : undefined} hidden={!shown} className={open ? "bg-signal-wash/50" : undefined}>
        <td className={TD}>
          <div className="font-medium text-ink">{labelOf(s)}</div>
          <p className="mt-0.5 max-w-prose text-[13px] leading-5 text-ink-muted">{researchPolicyHelp(s.key, s.group)}</p>
          {FLAGS.some((f) => s[f]) ? (
            <p className="mt-1 flex flex-wrap gap-x-3 text-xs">
              {FLAGS.filter((f) => s[f]).map((f) => <span key={f} title={t(`${D}.flagHelp.${f}`)} className={f === "required_for_live" && missing ? "font-semibold text-status-you-ink" : "text-ink-muted"}>{t(`${D}.flag.${f}`)}</span>)}
            </p>
          ) : null}
          <Technical><code data-technical className="mt-1 block break-all text-xs text-ink-faint">{s.key}</code></Technical>
        </td>
        <td className={TD}>
          <span data-value className={`break-words font-mono ${s.value === null ? "text-status-you-ink" : ""}`}>{showValue(s.type, s.value)}</span>
          {s.value !== null && unitOf(s) ? <span className="text-ink-muted"> {unitOf(s)}</span> : null}
          {range ? <div className="text-xs text-ink-faint">{range}</div> : null}
          <span data-origin={s.origin} className={`mt-1 block text-xs ${approved ? "font-semibold text-ink" : "text-ink-muted"}`}>{t(`${D}.origin.${s.origin}`)}</span>
          {approved && s.version !== null ? (
            <span className="block text-xs text-ink-muted">{tv(`${D}.origin.approvedBy`, { version: s.version, who: people(s.approved_by), when: when(s.approved_at) })}</span>
          ) : null}
        </td>
        <td className={`${TD} text-right`}>
          <Button small onClick={onToggle} aria-expanded={open} aria-controls={`dr-detail-${s.key}`}>{t(`${D}.${open ? "close" : mayAdminister ? "open" : "view"}`)}</Button>
        </td>
      </tr>
      {open ? (
        <tr hidden={!shown}><td colSpan={3} id={`dr-detail-${s.key}`} className="bg-surface-sunken px-3 py-4">
          <Detail settingKey={s.key} people={people} mayAdminister={mayAdminister} onChanged={onChanged} onDirty={onDirty} />
        </td></tr>
      ) : null}
    </>
  );
}

function Detail({ settingKey, people, mayAdminister, onChanged, onDirty }: { settingKey: string; people: People; mayAdminister: boolean; onChanged: () => void; onDirty: (value: boolean) => void }) {
  const [res, retry] = useResource(() => deepResearchSettings.get(settingKey), [settingKey]);
  const changed = () => {
    retry();
    onChanged();
  };
  return (
    <Loaded res={res} retry={retry}>
      {(detail) => <DetailBody detail={detail} people={people} mayAdminister={mayAdminister} onChanged={changed} onDirty={onDirty} />}
    </Loaded>
  );
}

type Approving = { version: number | null } | null;

/** Where a rule's change stands: propose, approve, in force for new runs. */
function Flow({ detail }: { detail: DrSettingDetail }) {
  const inForce = detail.origin === "approved" ? detail.version : null;
  const newest = detail.versions.reduce<number | null>((n, v) => (n === null || v.version_number > n ? v.version_number : n), null);
  const waiting = newest !== null && newest !== inForce;
  const state = (step: 1 | 2 | 3) =>
    step === 1 ? (waiting || inForce !== null ? "done" : "now")
    : step === 2 ? (waiting ? "now" : inForce !== null ? "done" : "")
    : inForce !== null && !waiting ? "done" : "";
  return (
    <ol data-dr-flow aria-label={t(`${D}.flow.label`)} className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
      {([1, 2, 3] as const).map((n) => {
        const st = state(n);
        return (
          <li key={n} data-state={st || "later"} className={`flex items-center gap-2 ${st === "now" ? "font-semibold text-signal" : st === "done" ? "text-ink" : "text-ink-faint"}`}>
            <span aria-hidden="true" className={`inline-flex size-5 items-center justify-center rounded-full border font-mono text-[11px] ${st === "done" ? "border-ink bg-ink text-surface-raised" : st === "now" ? "border-signal" : "border-border-strong"}`}>{n}</span>
            {t(`${D}.flow.step${n}`)}
          </li>
        );
      })}
    </ol>
  );
}

function DetailBody({ detail, people, mayAdminister, onChanged, onDirty }: { detail: DrSettingDetail; people: People; mayAdminister: boolean; onChanged: () => void; onDirty: (value: boolean) => void }) {
  const [approving, setApproving] = useState<Approving>(null);
  const [done, setDone] = useState<string | null>(null);
  const [draftDirty, setDraftDirty] = useState(false);
  const dirtyChanged = useCallback((value: boolean) => { setDraftDirty(value); onDirty(value); }, [onDirty]);
  const inForce = detail.origin === "approved" ? detail.version : null;
  return (
    <div data-dr-detail={detail.key} className="flex flex-col gap-4">
      {mayAdminister ? <Flow detail={detail} /> : null}
      {done ? <p role="status" className="text-sm font-medium text-ink">{done}</p> : null}
      <div className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-3">
          {approving ? (
            <Approve
              settingKey={detail.key}
              version={approving.version}
              onCancel={() => setApproving(null)}
              onDone={() => { setApproving(null); setDone(t(`${D}.approve.done`)); onChanged(); }}
            />
          ) : null}
          {mayAdminister ? <Propose key={`${detail.origin}:${detail.version}`} detail={detail} onDirty={dirtyChanged} onSaved={(n) => { setDone(tv(`${D}.propose.saved`, { version: n })); onChanged(); }} /> : null}
          {!mayAdminister ? <p className="text-sm text-ink-muted">{t(`${D}.adminNote`)}</p> : null}
        </div>
        <div className="flex min-w-0 flex-col gap-4">
          <div>
            <h4 className="text-sm font-semibold">{t(`${D}.detail.versions`)}</h4>
            {detail.versions.length ? (
              <ul className="mt-1 flex flex-col divide-y divide-border text-sm">
                {detail.versions.map((v) => (
                  <li key={v.version_number} data-dr-version={v.version_number} className="flex flex-wrap items-center gap-x-2 gap-y-1 py-2">
                    <strong>{tv(`${D}.detail.version`, { version: v.version_number })}</strong>
                    <span className="break-words font-mono">{showValue(detail.type, v.value)}</span>
                    {inForce === v.version_number ? <span className="text-xs font-semibold text-signal">{t(`${D}.detail.inForce`)}</span> : null}
                    <span className="basis-full text-xs text-ink-muted">{people(v.created_by)} · {when(v.created_at)}{v.note ? ` · ${v.note}` : ""}</span>
                    {v.source_url ? <a className="text-xs underline" href={v.source_url} target="_blank" rel="noreferrer noopener">{t(`${D}.detail.source`)}</a> : null}
                    {mayAdminister && inForce !== v.version_number ? (
                      <Button small disabled={draftDirty} onClick={() => { setDone(null); setApproving({ version: v.version_number }); }}>{tv(`${D}.detail.approve`, { version: v.version_number })}</Button>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : <p className="mt-1 text-sm text-ink-muted">{t(`${D}.detail.noVersions`)}</p>}
            {mayAdminister && inForce !== null ? (
              <div className="mt-2"><Button small disabled={draftDirty} onClick={() => { setDone(null); setApproving({ version: null }); }}>{t(`${D}.approve.withdraw`)}</Button></div>
            ) : null}
          </div>
          <div>
            <h4 className="text-sm font-semibold">{t(`${D}.detail.history`)}</h4>
            {detail.history.length ? (
              <ul className="mt-1 flex flex-col gap-1 text-sm">
                {detail.history.map((h) => (
                  <li key={h.approval_id} data-dr-approval={h.approval_id}>
                    <strong>{h.version_number === null ? t(`${D}.detail.withdrawn`) : tv(`${D}.detail.version`, { version: h.version_number })}</strong> · {people(h.approved_by)} · {when(h.approved_at)}
                    {h.reason ? <span className="text-ink-muted"> — {h.reason}</span> : null}
                  </li>
                ))}
              </ul>
            ) : <p className="mt-1 text-sm text-ink-muted">{t(`${D}.detail.noHistory`)}</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

function Approve({ settingKey, version, onCancel, onDone }: { settingKey: string; version: number | null; onCancel: () => void; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const go = async () => {
    setBusy(true);
    setError(null);
    try {
      await deepResearchSettings.approve(settingKey, version, reason.trim());
      onDone();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div data-dr-approve className="flex flex-col gap-2 rounded-sm border border-signal-edge bg-surface-raised p-3">
      <h4 className="text-sm font-semibold">{version === null ? t(`${D}.approve.withdrawTitle`) : tv(`${D}.approve.title`, { version })}</h4>
      <Field label={t(`${D}.approve.reason`)}>
        <TextInput value={reason} maxLength={255} onChange={(e) => setReason(e.target.value)} />
      </Field>
      {error ? <p role="alert" className="text-sm text-status-fault">{error}</p> : null}
      <div className="flex gap-2">
        <Button variant="primary" disabled={busy} onClick={() => void go()}>{t(`${D}.approve.confirm`)}</Button>
        <Button disabled={busy} onClick={onCancel}>{t(`${D}.approve.cancel`)}</Button>
      </div>
    </div>
  );
}

function Propose({ detail, onSaved, onDirty }: { detail: DrSettingDetail; onSaved: (version: number) => void; onDirty: (value: boolean) => void }) {
  const kind = inputKind(detail.type);
  const [raw, setRaw] = useState(() => toInput(detail.type, detail.value));
  const [source, setSource] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const [leaveHref, setLeaveHref] = useState<string | null>(null);
  const dirty = raw !== toInput(detail.type, detail.value) || !!source.trim() || !!note.trim();
  useEffect(() => { onDirty(dirty); }, [dirty, onDirty]);
  useEffect(() => {
    if (!dirty) return;
    const unload = (e: BeforeUnloadEvent) => e.preventDefault();
    const leave = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const link = (e.target as Element).closest?.("a[href]") as HTMLAnchorElement | null;
      if (!link || link.target || link.download || link.origin !== location.origin || link.pathname === location.pathname) return;
      e.preventDefault(); setLeaveHref(link.pathname + link.search + link.hash);
    };
    window.addEventListener("beforeunload", unload); document.addEventListener("click", leave, true);
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", leave, true); };
  }, [dirty]);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const parsed = parseInput(detail.type, raw);
    if (!parsed.ok) {
      setError(t(`${D}.propose.invalid.${parsed.reason}`));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const saved = await deepResearchSettings.propose(detail.key, { value: parsed.value, source_url: source.trim(), note: note.trim() });
      onSaved(saved.version_number); setRaw(toInput(detail.type, detail.value)); setSource(""); setNote("");
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  };
  const valueLabel = kind === "lines" ? `${t(`${D}.propose.value`)} · ${t(`${D}.propose.lines`)}` : t(`${D}.propose.value`);
  return (
    <form data-dr-propose onSubmit={(e) => void submit(e)} className="flex min-w-0 flex-col gap-3">
      {leaveHref ? <InlineConfirm message={t(`${D}.draftGuard`)} action={t(`${D}.discardDraft`)} onCancel={() => setLeaveHref(null)} onConfirm={() => router.push(leaveHref)} /> : null}
      <h4 className="text-sm font-semibold">{t(`${D}.propose.title`)}</h4>
      <Field label={valueLabel}>
        {kind === "decision" ? (
          <Select disabled={busy} value={raw} onChange={(e) => setRaw(e.target.value)}>
            <option value="true">{t(`${D}.yes`)}</option>
            <option value="false">{t(`${D}.no`)}</option>
          </Select>
        ) : kind === "status" ? (
          <Select disabled={busy} value={raw} onChange={(e) => setRaw(e.target.value)}>
            {STATUS_VALUES.map((v) => <option key={v} value={v}>{t(`${D}.status.${v}`)}</option>)}
          </Select>
        ) : kind === "lines" ? (
          <TextArea disabled={busy} aria-label={t(`${D}.propose.value`)} value={raw} onChange={(e) => setRaw(e.target.value)} />
        ) : (
          <TextInput
            disabled={busy} value={raw}
            onChange={(e) => setRaw(e.target.value)}
            inputMode={kind === "whole" ? "numeric" : kind === "decimal" ? "decimal" : undefined}
            type={kind === "date" ? "date" : kind === "url" ? "url" : "text"}
          />
        )}
      </Field>
      <div className="flex flex-wrap gap-2">
        <Field label={t(`${D}.propose.source`)} className="w-full min-w-0 sm:min-w-64 sm:flex-1">
          <TextInput disabled={busy} type="url" value={source} maxLength={500} onChange={(e) => setSource(e.target.value)} />
        </Field>
        <Field label={t(`${D}.propose.note`)} className="w-full min-w-0 sm:min-w-64 sm:flex-1">
          <TextInput disabled={busy} value={note} maxLength={255} onChange={(e) => setNote(e.target.value)} />
        </Field>
      </div>
      {error ? <p role="alert" className="text-sm text-status-fault">{error}</p> : null}
      <div className="flex flex-wrap gap-2"><Button type="submit" variant="primary" disabled={busy}>{t(`${D}.propose.submit`)}</Button><Button disabled={busy || !dirty} onClick={() => { setRaw(toInput(detail.type, detail.value)); setNote(""); setSource(""); setError(null); }}>{t(`${D}.revertDraft`)}</Button></div>
    </form>
  );
}
