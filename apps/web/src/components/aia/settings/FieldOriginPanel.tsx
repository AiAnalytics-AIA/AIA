"use client";

// The Metodika area "Původ polí" (methodology-tab V1c, canvas MethodologyTiers): what decides
// the uses of each population field, read-only. The tables come from code
// (GET /methodology/field-policy); the fields and every verdict from the in-force (LIVE)
// version's characteristics -- the policy's own answers, shown as given, never recomputed.
// It changes only with a new population version or a reviewed code change.

import { useState } from "react";

import { t, tv } from "@/i18n/t";
import { type FieldPolicyTables, type PopulationCharacteristics, type PopulationField, methodology, population } from "@/lib/api";
import { ORIGIN_WORDS, RULE_WORDS, counts, fieldRules, originName, ruleIds, ruleName, selectFields, type Selection } from "@/lib/field-origin";
import { reasonKey, summarize } from "@/lib/population";
import { Button, TextInput } from "../../rehome/ui";
import { Loaded } from "../states";
import { useResource } from "../useResource";

const C = "aia.intelligence.population.characteristics";
const F = "aia.settings.methodology.fieldOrigin";

/** The in-force population's version, its characteristics, or why there are none. */
type Population = { label: string | null; characteristics: PopulationCharacteristics | null };

async function loadAll(): Promise<{ tables: FieldPolicyTables; population: Population }> {
  const [tables, registry] = await Promise.all([methodology.fieldPolicy(), population.registry()]);
  const live = summarize(registry).live;
  if (!live) return { tables, population: { label: null, characteristics: null } };
  return { tables, population: { label: live.label, characteristics: await population.characteristics(live.version_id) } };
}

export function FieldOriginPanel() {
  const [res, retry] = useResource(loadAll, []);
  return <Loaded res={res} retry={retry}>{({ tables, population: pop }) => <Origin tables={tables} pop={pop} />}</Loaded>;
}

const shown = (n: number | null | undefined) => (n === null || n === undefined ? t(`${F}.unknown`) : tv(`${F}.fields`, { n }));

function Origin({ tables, pop }: { tables: FieldPolicyTables; pop: Population }) {
  const kept = pop.characteristics?.dictionary_kept ? pop.characteristics : null;
  const fields = kept?.fields ?? null;
  const n = counts(tables, fields);
  const [sel, setSel] = useState<Selection>(null);
  const [query, setQuery] = useState("");
  const list = fields ? selectFields(tables, fields, sel, query) : [];
  const [open, setOpen] = useState<string | null>(null);
  const opened = list.find((f) => f.field === open) ?? list[0] ?? null;
  const pick = (next: Selection) => setSel(sel && next && sel.kind === next.kind && sel.id === next.id ? null : next);
  const on = (kind: NonNullable<Selection>["kind"], id: string) => sel?.kind === kind && sel.id === id;
  const rowClass = (active: boolean) =>
    `grid w-full items-center gap-4 border-t border-border px-4 py-2 text-left text-sm focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-focus-ring ${active ? "bg-signal-wash shadow-[inset_3px_0_0_var(--color-signal)]" : "hover:bg-surface-sunken"}`;
  const selLabel = sel ? (sel.kind === "origin" ? tv(`${F}.byOrigin`, { name: originName(sel.id) }) : sel.kind === "rule" ? tv(`${F}.byRule`, { name: ruleName(sel.id) }) : tv(`${F}.byGrade`, { grade: sel.id })) : null;

  return <div className="flex min-w-0 flex-col gap-4">
    <p className="max-w-4xl text-sm leading-6 text-ink-muted">
      {pop.label ? tv(`${F}.intro`, { n: fields ? String(fields.length) : t(`${F}.unknownCount`), version: pop.label }) : t(`${F}.noLive`)}
      {pop.characteristics && !kept ? ` ${t(`${F}.notKept`)}` : ""}
    </p>
    <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
      <div className="flex min-w-0 flex-col gap-4">
        <section aria-labelledby="fo-origin" className="rounded-md border border-border bg-surface-raised">
          <div className="px-4 pb-3 pt-3"><h4 id="fo-origin" className="font-semibold">{t(`${F}.originTitle`)}</h4><p className="mt-1 text-xs leading-5 text-ink-muted">{t(`${F}.originHelp`)}</p></div>
          {tables.origins.map((o) => <button key={o.id} type="button" aria-pressed={on("origin", o.id)} onClick={() => pick({ kind: "origin", id: o.id })} className={`${rowClass(on("origin", o.id))} grid-cols-[180px_minmax(0,1fr)_80px_170px]`}>
            <strong>{originName(o.id)}</strong>
            <span className="text-xs leading-5 text-ink-muted">{ORIGIN_WORDS[o.id]?.means ?? o.statuses.join(", ")}</span>
            <span className="text-right text-xs text-ink-muted">{shown(n.origins[o.id])}</span>
            <span className={`justify-self-start rounded-full px-2 py-0.5 text-xs font-semibold ${o.measured ? "bg-surface-sunken text-ink" : "bg-status-you-wash text-status-you-ink"}`}>{o.measured ? t(`${F}.asMeasured`) : t(`${F}.asModelled`)}</span>
          </button>)}
        </section>
        <section aria-labelledby="fo-rules" className="rounded-md border border-border bg-surface-raised">
          <div className="px-4 pb-3 pt-3"><h4 id="fo-rules" className="font-semibold">{t(`${F}.rulesTitle`)}</h4><p className="mt-1 text-xs leading-5 text-ink-muted">{tv(`${F}.rulesHelp`, { n: tables.phrases.length })}</p></div>
          {ruleIds(tables).map((r) => <button key={r} type="button" aria-pressed={on("rule", r)} onClick={() => pick({ kind: "rule", id: r })} className={`${rowClass(on("rule", r))} grid-cols-[240px_minmax(0,1fr)_80px]`}>
            <strong>{ruleName(r)}</strong>
            <span className="text-xs leading-5 text-ink-muted">{RULE_WORDS[r]?.effect ?? r}</span>
            <span className="text-right text-xs text-ink-muted">{shown(n.rules[r])}</span>
          </button>)}
        </section>
        <section aria-labelledby="fo-grade" className="rounded-md border border-border bg-surface-raised">
          <div className="px-4 pb-3 pt-3"><h4 id="fo-grade" className="font-semibold">{t(`${F}.gradeTitle`)}</h4><p className="mt-1 text-xs leading-5 text-ink-muted">{t(`${F}.gradeHelp`)}</p></div>
          <div className="flex flex-wrap gap-2 border-t border-border px-4 py-3">
            {tables.grades.map((g) => <button key={g.grade} type="button" aria-pressed={on("grade", g.grade)} onClick={() => pick({ kind: "grade", id: g.grade })} className={`min-h-9 rounded-sm border px-3 text-sm focus-visible:outline-2 focus-visible:outline-focus-ring ${on("grade", g.grade) ? "border-signal-edge bg-signal-wash text-signal" : "border-border"}`}>
              {tv(`${F}.grade`, { grade: g.grade })} · {shown(n.grades[g.grade])}{g.client_blocking ? ` · ${t(`${F}.neverClient`)}` : ""}
            </button>)}
          </div>
          <ul className="flex flex-col gap-1 border-t border-border px-4 py-3 text-xs leading-5 text-ink-muted">
            <li>{t(`${F}.persona`)}</li>
            <li>{t(`${F}.weighting`)}</li>
          </ul>
        </section>
      </div>

      <aside aria-labelledby="fo-fields" className="flex min-w-0 flex-col rounded-md border border-border bg-surface-raised">
        <div className="flex flex-col gap-2 p-4">
          <h4 id="fo-fields" className="font-semibold">{t(`${F}.fieldsTitle`)}{pop.label ? <span className="font-normal text-ink-muted"> · {pop.label}</span> : null}</h4>
          <TextInput type="search" aria-label={t(`${F}.search`)} placeholder={t(`${F}.search`)} value={query} onChange={(e) => setQuery(e.target.value)} disabled={!fields} />
          {selLabel ? <span className="flex flex-wrap items-center gap-2 text-sm"><span className="rounded-full bg-signal-wash px-3 py-0.5 font-medium text-signal">{selLabel}</span><Button small variant="quiet" onClick={() => setSel(null)}>{t(`${F}.clear`)}</Button></span> : null}
        </div>
        {fields ? <>
          <ul aria-label={t(`${F}.fieldsTitle`)} className="max-h-80 overflow-auto border-t border-border">
            {list.map((f) => <li key={f.field}><button type="button" aria-pressed={opened?.field === f.field} onClick={() => setOpen(f.field)} className={`flex w-full flex-col items-start border-b border-border px-4 py-2 text-left text-sm focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-focus-ring ${opened?.field === f.field ? "bg-signal-wash" : "hover:bg-surface-sunken"}`}>
              <span className="font-medium">{f.description || f.field}</span>
              <span className="text-xs text-ink-muted">{originName(f.provenance_class)} · {tv(`${F}.grade`, { grade: f.production_grade || "—" })}</span>
            </button></li>)}
          </ul>
          {list.length ? null : <p role="status" className="px-4 py-3 text-sm text-ink-muted">{t(`${F}.noMatch`)}</p>}
          {opened ? <FieldUses tables={tables} field={opened} /> : null}
        </> : <p className="border-t border-border px-4 py-3 text-sm text-ink-muted">{t(`${F}.noFields`)}</p>}
      </aside>
    </div>
  </div>;
}

function FieldUses({ tables, field }: { tables: FieldPolicyTables; field: PopulationField }) {
  const rules = fieldRules(tables, field);
  return <section aria-labelledby="fo-field" className="border-t border-border p-4">
    <p className="text-xs font-semibold text-ink-muted">{t(`${F}.chosen`)}</p>
    <h5 id="fo-field" className="text-base font-semibold">{field.description || field.field}</h5>
    <p className="mt-1 text-xs leading-5 text-ink-muted">
      {originName(field.provenance_class)} · {tv(`${F}.grade`, { grade: field.production_grade || "—" })} · {rules === null ? t(`${F}.unknownSentence`) : rules.length ? rules.map(ruleName).join(", ") : t(`${F}.noRule`)}
    </p>
    <dl className="mt-2">
      {field.uses.map((u) => {
        const { key, values } = reasonKey(u.reason);
        return <div key={u.use} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 border-t border-border py-2 text-sm">
          <dt>{t(`${C}.use.${u.use}`)}</dt>
          <dd className={`font-semibold ${u.allowed ? "text-ink" : "text-status-fault"}`}>{u.allowed ? t(`${C}.allowed`) : t(`${C}.refused`)}</dd>
          <dd className="col-span-2 text-xs leading-5 text-ink-muted">
            {tv(`${C}.reason.${key}`, values)}
            {u.obligations.length ? ` · ${tv(`${F}.duties`, { list: u.obligations.map((o) => t(`${C}.obligation.${o}`)).join(", ") })}` : ""}
          </dd>
        </div>;
      })}
    </dl>
  </section>;
}
