"use client";

// The Deep Research tab: every policy value Deep Research runs by, what is in force
// and who approved it (ADR 0022, GET /api/v1/deep-research/settings). Until someone
// approves a value, the code's proposed default is in force and is labelled so. An
// administrator proposes a value -- a new version, not yet in force -- and approves a
// version or withdraws to the default; each change takes effect for runs enqueued
// after it. Switches, secrets and the model route are not here: they stay in the
// deployment, and no setting turns a rail off. What is allowed is the API's to say:
// its refusal is shown as it gave it.

import { type FormEvent, useState } from "react";

import { cs } from "@/i18n/cs";
import { t, tv } from "@/i18n/t";
import {
  type DrSetting,
  type DrSettingDetail,
  type DrSettingValue,
  type DrSettingsOverview,
  deepResearchSettings,
} from "@/lib/api";
import { STATUS_VALUES, groupsInOrder, inputKind, missingForLive, parseInput, toInput } from "@/lib/deep-research-settings";
import { relative } from "@/lib/format";
import { Button, Field, Select, Tag, TextArea, TextInput } from "../../rehome/ui";
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

function Overview({ overview, people, reload }: { overview: DrSettingsOverview; people: People; reload: () => void }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="flex flex-col gap-4">
      <p className="max-w-3xl text-sm text-ink-muted">{t(`${D}.intro`)}</p>
      <p className="text-xs text-ink-faint">
        {tv(`${D}.catalogue`, { version: overview.catalogue_version })}
        {overview.may_administer ? null : <> · {t(`${D}.adminNote`)}</>}
      </p>
      <Readiness overview={overview} />
      {groupsInOrder(overview.settings).map(({ group, settings }) => (
        <section key={group} data-dr-group={group} aria-labelledby={`dr-${group}`} className="flex flex-col">
          <h3 id={`dr-${group}`} className="border-b border-border pb-1 text-sm font-semibold">{t(`${D}.groups.${group}`)}</h3>
          {settings.map((s) => (
            <Row
              key={s.key}
              setting={s}
              people={people}
              open={open === s.key}
              onToggle={() => setOpen(open === s.key ? null : s.key)}
              mayAdminister={overview.may_administer}
              onChanged={reload}
            />
          ))}
        </section>
      ))}
    </div>
  );
}

function Readiness({ overview }: { overview: DrSettingsOverview }) {
  const missing = missingForLive(overview);
  return (
    <div data-live-readiness className={`rounded-sm border p-3 text-sm ${missing.length ? "border-status-you/40 bg-status-you-wash" : "border-status-done/40 bg-surface"}`}>
      <h3 className="font-semibold">{t(`${D}.live.title`)}</h3>
      {missing.length ? (
        <>
          <p className="mt-1">{tv(`${D}.live.missing`, { count: missing.length })}</p>
          <ul className="mt-1 list-disc pl-5">
            {missing.map((s) => <li key={s.key} data-missing={s.key}>{labelOf(s)}</li>)}
          </ul>
        </>
      ) : <p className="mt-1">{t(`${D}.live.ready`)}</p>}
      <p className="mt-1 text-xs text-ink-muted">{t(`${D}.live.note`)}</p>
    </div>
  );
}

function Row({ setting: s, people, open, onToggle, mayAdminister, onChanged }: {
  setting: DrSetting; people: People; open: boolean; onToggle: () => void; mayAdminister: boolean; onChanged: () => void;
}) {
  const approved = s.origin === "approved";
  const range = bounds(s);
  return (
    <div data-dr-setting={s.key} className="border-b border-border py-2 last:border-b-0">
      <div className="grid grid-cols-1 gap-1 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)_minmax(0,2fr)_auto] md:items-center md:gap-4">
        <div className="min-w-0">
          <div className="text-sm text-ink">{labelOf(s)}</div>
          <code className="break-all text-[11px] text-ink-faint">{s.key}</code>
        </div>
        <div className="min-w-0 text-sm">
          <span data-value className="break-words font-medium">{showValue(s.type, s.value)}</span>
          {s.value !== null && unitOf(s) ? <span className="text-ink-muted"> {unitOf(s)}</span> : null}
          {range ? <div className="text-[11px] text-ink-faint">{range}</div> : null}
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-1 text-xs">
          <span data-origin={s.origin} className={approved ? "font-semibold text-status-done" : "text-ink-muted"}>{t(`${D}.origin.${s.origin}`)}</span>
          {approved && s.version !== null ? (
            <span className="text-ink-muted">{tv(`${D}.origin.approvedBy`, { version: s.version, who: people(s.approved_by), when: when(s.approved_at) })}</span>
          ) : null}
          {(["required_for_live", "lower_only", "method"] as const).filter((f) => s[f]).map((f) => (
            <span key={f} title={t(`${D}.flagHelp.${f}`)}><Tag>{t(`${D}.flag.${f}`)}</Tag></span>
          ))}
        </div>
        <Button small onClick={onToggle} aria-expanded={open} aria-controls={`dr-detail-${s.key}`}>{t(`${D}.${open ? "close" : "open"}`)}</Button>
      </div>
      {open ? (
        <div id={`dr-detail-${s.key}`} className="mt-2">
          <Detail settingKey={s.key} people={people} mayAdminister={mayAdminister} onChanged={onChanged} />
        </div>
      ) : null}
    </div>
  );
}

function Detail({ settingKey, people, mayAdminister, onChanged }: { settingKey: string; people: People; mayAdminister: boolean; onChanged: () => void }) {
  const [res, retry] = useResource(() => deepResearchSettings.get(settingKey), [settingKey]);
  const changed = () => {
    retry();
    onChanged();
  };
  return (
    <Loaded res={res} retry={retry}>
      {(detail) => <DetailBody detail={detail} people={people} mayAdminister={mayAdminister} onChanged={changed} />}
    </Loaded>
  );
}

type Approving = { version: number | null } | null;

function DetailBody({ detail, people, mayAdminister, onChanged }: { detail: DrSettingDetail; people: People; mayAdminister: boolean; onChanged: () => void }) {
  const [approving, setApproving] = useState<Approving>(null);
  const [done, setDone] = useState<string | null>(null);
  const inForce = detail.origin === "approved" ? detail.version : null;
  return (
    <div data-dr-detail={detail.key} className="flex flex-col gap-3 rounded-sm border border-border bg-surface p-3">
      {done ? <p role="status" className="text-sm text-status-done">{done}</p> : null}
      <div>
        <h4 className="text-sm font-semibold">{t(`${D}.detail.versions`)}</h4>
        {detail.versions.length ? (
          <ul className="mt-1 flex flex-col gap-1 text-sm">
            {detail.versions.map((v) => (
              <li key={v.version_number} data-dr-version={v.version_number} className="flex flex-wrap items-center gap-2">
                <strong>e{v.version_number}</strong>
                <span className="break-words">{showValue(detail.type, v.value)}</span>
                <span className="text-ink-muted">· {people(v.created_by)} · {when(v.created_at)}</span>
                {v.source_url ? <a className="text-xs underline" href={v.source_url} target="_blank" rel="noreferrer noopener">{t(`${D}.detail.source`)}</a> : null}
                {v.note ? <span className="text-ink-muted">— {v.note}</span> : null}
                {inForce === v.version_number ? <Tag>{t(`${D}.detail.inForce`)}</Tag> : null}
                {mayAdminister && inForce !== v.version_number ? (
                  <Button small onClick={() => { setDone(null); setApproving({ version: v.version_number }); }}>{tv(`${D}.detail.approve`, { version: v.version_number })}</Button>
                ) : null}
              </li>
            ))}
          </ul>
        ) : <p className="mt-1 text-sm text-ink-muted">{t(`${D}.detail.noVersions`)}</p>}
      </div>
      {mayAdminister && inForce !== null ? (
        <div><Button small onClick={() => { setDone(null); setApproving({ version: null }); }}>{t(`${D}.approve.withdraw`)}</Button></div>
      ) : null}
      {approving ? (
        <Approve
          settingKey={detail.key}
          version={approving.version}
          onCancel={() => setApproving(null)}
          onDone={() => { setApproving(null); setDone(t(`${D}.approve.done`)); onChanged(); }}
        />
      ) : null}
      {mayAdminister ? <Propose detail={detail} onSaved={(n) => { setDone(tv(`${D}.propose.saved`, { version: n })); onChanged(); }} /> : null}
      <div>
        <h4 className="text-sm font-semibold">{t(`${D}.detail.history`)}</h4>
        {detail.history.length ? (
          <ul className="mt-1 flex flex-col gap-1 text-sm">
            {detail.history.map((h) => (
              <li key={h.approval_id} data-dr-approval={h.approval_id}>
                <strong>{h.version_number === null ? t(`${D}.detail.withdrawn`) : `e${h.version_number}`}</strong> · {people(h.approved_by)} · {when(h.approved_at)}
                {h.reason ? <span className="text-ink-muted"> — {h.reason}</span> : null}
              </li>
            ))}
          </ul>
        ) : <p className="mt-1 text-sm text-ink-muted">{t(`${D}.detail.noHistory`)}</p>}
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
    <div data-dr-approve className="flex flex-col gap-2 rounded-sm border border-border p-3">
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

function Propose({ detail, onSaved }: { detail: DrSettingDetail; onSaved: (version: number) => void }) {
  const kind = inputKind(detail.type);
  const [raw, setRaw] = useState(() => toInput(detail.type, detail.value));
  const [source, setSource] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
      onSaved(saved.version_number);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  };
  const valueLabel = kind === "lines" ? `${t(`${D}.propose.value`)} · ${t(`${D}.propose.lines`)}` : t(`${D}.propose.value`);
  return (
    <form data-dr-propose onSubmit={(e) => void submit(e)} className="flex flex-col gap-2 rounded-sm border border-border p-3">
      <h4 className="text-sm font-semibold">{t(`${D}.propose.title`)}</h4>
      <Field label={valueLabel}>
        {kind === "decision" ? (
          <Select value={raw} onChange={(e) => setRaw(e.target.value)}>
            <option value="true">{t(`${D}.yes`)}</option>
            <option value="false">{t(`${D}.no`)}</option>
          </Select>
        ) : kind === "status" ? (
          <Select value={raw} onChange={(e) => setRaw(e.target.value)}>
            {STATUS_VALUES.map((v) => <option key={v} value={v}>{t(`${D}.status.${v}`)}</option>)}
          </Select>
        ) : kind === "lines" ? (
          <TextArea value={raw} onChange={(e) => setRaw(e.target.value)} />
        ) : (
          <TextInput
            value={raw}
            onChange={(e) => setRaw(e.target.value)}
            inputMode={kind === "whole" ? "numeric" : kind === "decimal" ? "decimal" : undefined}
            type={kind === "date" ? "date" : kind === "url" ? "url" : "text"}
          />
        )}
      </Field>
      <div className="flex flex-wrap gap-2">
        <Field label={t(`${D}.propose.source`)} className="min-w-64 flex-1">
          <TextInput type="url" value={source} maxLength={500} onChange={(e) => setSource(e.target.value)} />
        </Field>
        <Field label={t(`${D}.propose.note`)} className="min-w-64 flex-1">
          <TextInput value={note} maxLength={255} onChange={(e) => setNote(e.target.value)} />
        </Field>
      </div>
      {error ? <p role="alert" className="text-sm text-status-fault">{error}</p> : null}
      <div><Button type="submit" variant="primary" disabled={busy}>{t(`${D}.propose.submit`)}</Button></div>
    </form>
  );
}
