// The Metodika area "Původ polí" (methodology-tab V1c): how the population's field policy
// decides what each field may serve, read from GET /methodology/field-policy (the tables, from
// code) and the in-force version's characteristics (every field and the policy's own answer
// for each use). Nothing here decides a use: a field's verdicts are the API's, shown as given.

import type { FieldPolicyTables, PopulationField } from "./api";

/** Each origin in words; an origin the page does not know is named by its code. */
export const ORIGIN_WORDS: Record<string, { name: string; means: string }> = {
  OBSERVED: { name: "Změřeno", means: "Odpověď respondenta nebo údaj ukotvení populace." },
  DONOR_MATCHED: { name: "Převzato od dárce", means: "Celý blok odpovědí převzatý od podobného respondenta jiného šetření." },
  DERIVED: { name: "Odvozeno", means: "Vypočteno z jiných polí podle zveřejněného postupu." },
  CALIBRATED: { name: "Kalibrováno", means: "Model sladěný s veřejnou statistikou nebo měřením." },
  HYBRID: { name: "Smíšené", means: "U části lidí změřeno, u ostatních modelováno." },
  MODELLED: { name: "Modelováno", means: "Odhad modelu, ne měření člověka." },
  PROVENANCE: { name: "Technický údaj", means: "Údaj o původu záznamu, ne o člověku." },
  UNCLASSIFIED: { name: "Nezařazeno", means: "Původ, který slovník nepojmenovává; mezi nimi váhy." },
};

/** Each rule a recommended-use sentence carries, and what it does where the policy applies it. */
export const RULE_WORDS: Record<string, { name: string; effect: string }> = {
  AUDIT_ONLY: { name: "Jen pro kontrolu", effect: "Pole nesmí k ničemu kromě kontroly záznamu." },
  NEVER_MEASURED_FACT: { name: "Nikdy jako změřený fakt", effect: "Ke klientovi jako měření nesmí." },
  NEVER_DIRECT_SCHWARTZ: { name: "Nikdy jako přímé měření hodnot", effect: "Ke klientovi jako měření nesmí." },
  AGGREGATE_ONLY: { name: "Jen souhrnně", effect: "Každé použití nese povinnost: jen souhrn a skupiny, nikdy jeden respondent." },
  PERSON_VALUE_MODELED: { name: "Hodnota osoby je modelovaná", effect: "Jen souhrnně; ke klientovi jako měření nesmí." },
  REQUIRES_MODELED_DISCLOSURE: { name: "Vyžaduje upozornění „modelováno“", effect: "Ke klientovi jako měření nesmí; jako modelované s upozorněním." },
  REQUIRES_SCOPE: { name: "Vyžaduje uvést rozsah", effect: "Každé použití nese povinnost uvést, pro koho číslo platí." },
  HISTORICAL_OR_EXPLORATORY: { name: "Historické nebo průzkumné", effect: "Ke klientovi jako měření nesmí." },
  SPECIFIED_WEIGHT_REQUIRED: { name: "Předepsaná váha", effect: "Každé použití nese povinnost vážit vahou, kterou slovník uvádí." },
};

export const originName = (id: string): string => ORIGIN_WORDS[id]?.name ?? id;
export const ruleName = (id: string): string => RULE_WORDS[id]?.name ?? id;

export type Selection = { kind: "origin" | "rule" | "grade"; id: string } | null;

/** The rules a field's recommended-use sentence carries; null for a sentence the code does not
 *  know (the policy refuses such a field for every use). */
export function fieldRules(tables: FieldPolicyTables, field: PopulationField): string[] | null {
  const phrase = tables.phrases.find((p) => p.phrase === field.recommended_use);
  return phrase ? phrase.rules : null;
}

/** Fields per origin, per rule and per grade. `null` counts: the version keeps no dictionary,
 *  so nothing is known (never zero). */
export function counts(tables: FieldPolicyTables, fields: PopulationField[] | null): {
  origins: Record<string, number | null>; rules: Record<string, number | null>; grades: Record<string, number | null>;
} {
  const origins: Record<string, number | null> = {};
  const rules: Record<string, number | null> = {};
  const grades: Record<string, number | null> = {};
  for (const o of tables.origins) origins[o.id] = fields ? 0 : null;
  for (const r of ruleIds(tables)) rules[r] = fields ? 0 : null;
  for (const g of tables.grades) grades[g.grade] = fields ? 0 : null;
  for (const f of fields ?? []) {
    origins[f.provenance_class] = (origins[f.provenance_class] ?? 0) + 1;
    for (const r of fieldRules(tables, f) ?? []) rules[r] = (rules[r] ?? 0) + 1;
    grades[f.production_grade] = (grades[f.production_grade] ?? 0) + 1;
  }
  return { origins, rules, grades };
}

/** Every rule any known sentence carries, in the order the page lists them. */
export function ruleIds(tables: FieldPolicyTables): string[] {
  const used = new Set(tables.phrases.flatMap((p) => p.rules));
  return [...Object.keys(RULE_WORDS).filter((r) => used.has(r)), ...[...used].filter((r) => !(r in RULE_WORDS)).sort()];
}

/** The fields a selection and a search leave; the search reads name, description and block. */
export function selectFields(tables: FieldPolicyTables, fields: PopulationField[], sel: Selection, query: string): PopulationField[] {
  const needle = query.trim().toLocaleLowerCase("cs");
  return fields.filter((f) => {
    if (sel?.kind === "origin" && f.provenance_class !== sel.id) return false;
    if (sel?.kind === "rule" && !(fieldRules(tables, f) ?? []).includes(sel.id)) return false;
    if (sel?.kind === "grade" && f.production_grade !== sel.id) return false;
    return !needle || [f.field, f.description, f.block].some((text) => text.toLocaleLowerCase("cs").includes(needle));
  });
}
