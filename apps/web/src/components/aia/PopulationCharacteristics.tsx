"use client";

// What a population version is made of (population-operations P7d): its weights, field
// blocks, the 18 built-in subpanels adopted from 18.6.6 and every field with what it may
// serve. Read from GET /population/versions/{id}/characteristics, which reads the
// dictionary the version keeps -- never a respondent row. Nothing here writes.

import { useState } from "react";

import { t, tv } from "@/i18n/t";
import { type PopulationCharacteristics, type PopulationField, type PopulationRegistry, population } from "@/lib/api";
import { defaultVersionId, filterFields, reasonKey, subpanelFilterText, usability } from "@/lib/population";
import { StatusPill, Field, Select, Tag, TextInput } from "../rehome/ui";
import { Empty, Loaded } from "./states";
import { useResource } from "./useResource";

const C = "aia.intelligence.population.characteristics";

/** The Czech word for a code this page knows, or the code itself: never a missing key. */
function word(key: string, fallback: string): string {
  const v = t(key);
  return v === key ? fallback : v;
}

const number = (n: number) => n.toLocaleString("cs");

function reason(code: string): string {
  const { key, values } = reasonKey(code);
  return tv(`${C}.reason.${key}`, values);
}

export function PopulationCharacteristicsSection({ registry }: { registry: PopulationRegistry }) {
  const [versionId, setVersionId] = useState<string | null>(() => defaultVersionId(registry));
  if (!versionId) return null;
  return (
    <section className="mt-6 flex flex-col gap-4" aria-labelledby="pop-char-title">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 id="pop-char-title" className="text-base font-semibold">{t(`${C}.title`)}</h3>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-ink-muted">{t(`${C}.text`)}</p>
        </div>
        <Field label={t(`${C}.version`)} className="w-48">
          <Select value={versionId} onChange={(e) => setVersionId(e.target.value)}>
            {registry.versions.map((v) => (
              <option key={v.version_id} value={v.version_id}>{v.label}</option>
            ))}
          </Select>
        </Field>
      </div>
      <VersionCharacteristics key={versionId} versionId={versionId} />
    </section>
  );
}

function VersionCharacteristics({ versionId }: { versionId: string }) {
  const [res, retry] = useResource(() => population.characteristics(versionId), [versionId]);
  return <Loaded res={res} retry={retry}>{(c) => <CharacteristicsView c={c} />}</Loaded>;
}

function CharacteristicsView({ c }: { c: PopulationCharacteristics }) {
  return (
    <div className="flex flex-col gap-6">
      {c.dictionary_kept ? null : (
        <p role="status" className="rounded-sm border border-border bg-surface-sunken p-3 text-sm leading-6 text-ink">{t(`${C}.notKept`)}</p>
      )}
      <Weights c={c} />
      {c.blocks.length ? <Blocks c={c} /> : null}
      <Subpanels c={c} />
      {c.dictionary_kept ? <Fields fields={c.fields} blocks={c.blocks.map((b) => b.block)} /> : null}
    </div>
  );
}

function Weights({ c }: { c: PopulationCharacteristics }) {
  return (
    <div>
      <h4 className="mb-2 text-sm font-semibold">{t(`${C}.weights`)}</h4>
      <ul className="flex flex-col divide-y divide-border rounded-md border border-border bg-surface-raised">
        {c.weights.map((w) => (
          <li key={w.role} className="flex flex-wrap items-center gap-3 px-4 py-2 text-sm">
            <span className="font-semibold text-ink">{word(`${C}.weightRole.${w.role}`, w.role)}</span>
            {w.is_default ? <Tag>{t(`${C}.default`)}</Tag> : null}
            <span className="font-mono text-xs text-ink-faint">{w.column}</span>
            <span className="ml-auto text-xs text-ink-muted">
              {w.expected_total === null
                ? t(`${C}.noTotal`)
                : tv(`${C}.total`, { total: number(w.expected_total), tolerance: number(w.tolerance ?? 0) })}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Blocks({ c }: { c: PopulationCharacteristics }) {
  return (
    <div>
      <h4 className="mb-2 text-sm font-semibold">{t(`${C}.blocks`)}</h4>
      <ul className="flex flex-wrap gap-2">
        {c.blocks.map((b) => (
          <li key={b.block} className="rounded-sm border border-border px-2 py-1 text-xs text-ink">
            <span className="font-mono">{b.block}</span> <span className="text-ink-muted">· {tv(`${C}.blockFields`, { n: b.fields })}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Subpanels({ c }: { c: PopulationCharacteristics }) {
  return (
    <div>
      <h4 className="mb-1 text-sm font-semibold">{t(`${C}.subpanels`)}</h4>
      <p className="mb-2 max-w-2xl text-xs leading-5 text-ink-muted">
        {tv(`${C}.subpanelsText`, { version: c.subpanels_measured_on, weight: c.subpanels_measured_under_weight })} {c.subpanel_note}
      </p>
      <ul className="grid gap-2 md:grid-cols-2">
        {c.subpanels.map((s) => {
          const u = usability(s);
          return (
            <li key={s.key} className="rounded-sm border border-border p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-ink">{s.name}</span>
                <StatusPill tone={u === "usable" ? "done" : "neutral"}>{t(`${C}.usability.${u}`)}</StatusPill>
              </div>
              <p className="mt-1 font-mono text-xs text-ink-faint">{subpanelFilterText(s.filter)}</p>
              {u === "unusable" && s.reason ? <p className="mt-1 text-xs text-ink-muted">{reason(s.reason)}</p> : null}
              <div className="mt-2 flex flex-wrap gap-1">
                <Tag>{word(`${C}.subpanelStatus.${s.status}`, s.status)}</Tag>
                <Tag>{word(`${C}.tier.${s.support_tier}`, s.support_tier)}</Tag>
              </div>
              <p className="mt-2 text-xs text-ink-muted">
                {tv(`${C}.measured`, {
                  rows: number(s.measured_by_18_6_6.rows),
                  population: number(Math.round(s.measured_by_18_6_6.weighted_population)),
                  donors: number(s.measured_by_18_6_6.unique_core_donors),
                  effective: number(s.measured_by_18_6_6.effective_core_donors),
                })}
              </p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Fields({ fields, blocks }: { fields: PopulationField[]; blocks: string[] }) {
  const [query, setQuery] = useState("");
  const [block, setBlock] = useState<string | null>(null);
  const shown = filterFields(fields, query, block);
  return (
    <div>
      <h4 className="mb-2 text-sm font-semibold">{t(`${C}.fields`)}</h4>
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <Field label={t(`${C}.search`)} className="w-64">
          <TextInput type="search" value={query} onChange={(e) => setQuery(e.target.value)} />
        </Field>
        <Field label={t(`${C}.blocks`)} className="w-56">
          <Select value={block ?? ""} onChange={(e) => setBlock(e.target.value || null)}>
            <option value="">{t(`${C}.allBlocks`)}</option>
            {blocks.map((b) => (
              <option key={b} value={b}>{b}</option>
            ))}
          </Select>
        </Field>
        <span className="text-xs text-ink-muted">{tv(`${C}.shown`, { n: shown.length, total: fields.length })}</span>
      </div>
      {shown.length ? (
        <ul className="flex flex-col divide-y divide-border rounded-md border border-border bg-surface-raised">
          {shown.map((f) => (
            <FieldRow key={f.field} f={f} />
          ))}
        </ul>
      ) : (
        <Empty>{t(`${C}.noFields`)}</Empty>
      )}
    </div>
  );
}

function FieldRow({ f }: { f: PopulationField }) {
  return (
    <li className="px-4 py-2 text-sm">
      <details>
        <summary className="flex cursor-pointer flex-wrap items-center gap-2">
          <span className="font-mono text-ink">{f.field}</span>
          <Tag>{f.block}</Tag>
          <span className="font-mono text-xs text-ink-faint">{f.evidence_status}</span>
          {f.production_grade ? <span className="text-xs text-ink-faint">{f.production_grade}</span> : null}
          {f.is_weight ? <Tag>{t(`${C}.weight`)}</Tag> : null}
          {f.derived ? <Tag>{t(`${C}.derived`)}</Tag> : null}
          {f.persona_eligible ? <Tag>{t(`${C}.personaEligible`)}</Tag> : null}
          {f.description ? <span className="text-xs text-ink-muted">{f.description}</span> : null}
        </summary>
        <div className="mt-2 pl-2">
          <p className="mb-1 text-xs font-medium text-ink-muted">{t(`${C}.details`)}</p>
          {f.source ? <p className="mb-1 text-xs text-ink-faint">{f.source}</p> : null}
          <ul className="flex flex-col gap-1 text-xs">
            {f.uses.map((u) => (
              <li key={u.use} className="flex flex-wrap gap-2">
                <span className="w-56 text-ink">{word(`${C}.use.${u.use}`, u.use)}</span>
                <span className={u.allowed ? "text-ink" : "text-ink-muted"}>{u.allowed ? t(`${C}.allowed`) : t(`${C}.refused`)}</span>
                <span className="text-ink-faint">{reason(u.reason)}</span>
                {u.obligations.map((o) => (
                  <Tag key={o}>{word(`${C}.obligation.${o}`, o)}</Tag>
                ))}
              </li>
            ))}
          </ul>
        </div>
      </details>
    </li>
  );
}
