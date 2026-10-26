// What an audit record changed, in words (settings-redesign F10, prototype v99's Změna column):
// read from what its writer stored -- the reason the scope repository fills with "a -> b", a status
// code, or the payload's from / to -- and the reason a person gave, apart from it. Pure. A reason
// a writer fills with its own code is never shown as a person's words; a code this file knows
// reads in Czech; a shape it does not know keeps its reason as written, and no change is invented.

import { cs } from "@/i18n/cs";
import { t, tv } from "@/i18n/t";

/** Deep Research's rule names, keyed by the rule's dotted key (so not through t()'s dotted path). */
const RULE_LABELS: Record<string, string> = cs.aia.settings.deepResearch.labels;

/** A record's change and the person's reason beside it. */
export type AuditChange = {
  /** The change itself ("100 → 120 USD", "výzkumník → správce"); null where the record carries none. */
  change: string | null;
  /** The reason a person gave, apart from the change; null where none was given. */
  why: string | null;
};

type Entry = { action: string; reason: string; payload: Record<string, unknown> | null | undefined };

const C = "aia.settings.panel.audit.change";
const money = new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: 2 });

/** A number as its writer stored it (100, "100.0"); null and Python's "None" are no amount; anything
 *  else is not a number (undefined), so its words are kept rather than read as one. */
function amount(v: unknown): number | null | undefined {
  if (v === null || v === "None" || v === "null") return null;
  const n = typeof v === "number" ? v : typeof v === "string" && v.trim() !== "" ? Number(v) : Number.NaN;
  return Number.isFinite(n) ? n : undefined;
}

/** "a -> b", as the scope repository writes a money change into the reason. */
function ends(reason: string): [string, string] | null {
  const m = /^\s*(\S+)\s*->\s*(\S+)\s*$/.exec(reason);
  return m ? [m[1], m[2]] : null;
}

/** A code's name under a copy key, or null where the copy has none. */
function known(key: string, code: string): string | null {
  const s = t(`${key}.${code}`);
  return s === `${key}.${code}` ? null : s;
}
/** A code's name under a copy key, or the code itself: never blank. */
const named = (key: string, code: string): string => known(key, code) ?? code;

const text = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v.trim() : null);
const scalar = (v: unknown): string => (v === null || v === undefined ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v));

/** A money change read from "a -> b"; null when either end is not an amount. `none` names no amount. */
function moneyChange(reason: string, none: string): string | null {
  const pair = ends(reason);
  if (!pair) return null;
  const [a, b] = pair.map(amount);
  if (a === undefined || b === undefined) return null;
  const word = (n: number | null) => (n === null ? none : `${money.format(n)} USD`);
  // "100 → 120 USD" when both are amounts; an end that is none says so in words.
  return a !== null && b !== null ? `${money.format(a)} → ${money.format(b)} USD` : `${word(a)} → ${word(b)}`;
}

/** A methodology version as Metodika names it: the code's preset, or "e3" (its "+e3"). */
const methodVersion = (v: unknown): string => (v === null || v === undefined ? t(`${C}.fromCode`) : typeof v === "number" ? `e${v}` : String(v));
/** A prompt version as Systémové prompty names it: "e3" is "verze 3"; any other label is the code's. */
function promptVersion(v: unknown): string {
  if (typeof v !== "string") return scalar(v);
  const n = /^e(\d+)$/.exec(v)?.[1];
  return n ? tv("aia.settings.prompts.versionName", { n }) : t("aia.settings.prompts.baselineName");
}
/** A Deep Research rule's version: none is the code's default. */
const ruleVersion = (v: unknown): string => (v === null || v === undefined ? t(`${C}.default`) : typeof v === "number" ? `v${v}` : String(v));

/** A reason a writer fills with a code of its own (a refusal, a decision): in Czech where the copy
 *  names it, else as written. Never read as a person's words when it is one of these. */
const REASON_WORDS: Record<string, string> = {
  owner_only: "aia.settings.panel.members.ownerOnly",
  last_owner: "aia.settings.panel.members.lastOwner",
};
function reasonWords(reason: string | null): string | null {
  if (!reason) return null;
  const copy = REASON_WORDS[reason];
  if (copy) return t(copy);
  return known(`${C}.code`, reason) ?? reason;
}

/** A record's change in words, and the person's reason apart from it. */
export function changeOf(e: Entry): AuditChange {
  const p = e.payload ?? {};
  const reason = text(e.reason);
  const why = text(p.why);
  switch (e.action) {
    // The reason holds the change itself: never shown again as a reason.
    case "STUDY_BUDGET_CHANGED":
    case "CLIENT_BUDGET_CHANGED":
      return { change: moneyChange(e.reason, "—") ?? reason, why };
    case "STUDY_SPEND_CONFIRM_CHANGED":
      return { change: moneyChange(e.reason, t(`${C}.noThreshold`)) ?? reason, why };
    case "CLIENT_STATUS_CHANGED":
      return { change: reason ? `→ ${named("aia.settings.panel.clientStatus", reason)}` : null, why };
    case "STUDY_STATUS_CHANGED":
      return { change: reason ? `→ ${named("aia.status", reason)}` : null, why };
    case "MEMBER_ADDED": {
      if (typeof p.to !== "string") return { change: null, why: null };
      const to = named("aia.orgRoles", p.to);
      if (p.from === null || p.from === undefined) return { change: tv(`${C}.joinedAs`, { role: to }), why: null };
      if (p.from === p.to) return { change: null, why: null };
      return { change: `${typeof p.from === "string" ? named("aia.orgRoles", p.from) : scalar(p.from)} → ${to}`, why: null };
    }
    case "SELF_APPROVAL_CONFIGURED": {
      // The reason is the writer's own "client=false": the change, never a person's words.
      const level = typeof p.level === "string" ? named(`${C}.level`, p.level) : null;
      const v = p.allow_self_approval;
      const state = v === true ? t(`${C}.allowed`) : v === false ? t(`${C}.forbidden`) : v === null ? t(`${C}.inherits`) : null;
      return { change: state ? (level ? `${level}: ${state}` : state) : null, why: null };
    }
    case "CLIENT_RULES_CHANGED": {
      const parts = Object.entries(p).flatMap(([key, moved]) => {
        if (!moved || typeof moved !== "object" || !("to" in moved)) return [];
        const { from, to } = moved as { from?: unknown; to: unknown };
        if (key === "data_posture") {
          const w = (v: unknown) => (v === null || v === undefined ? t(`${C}.unset`) : scalar(v));
          return [`${t(`${C}.posture`)}: ${w(from)} → ${w(to)}`];
        }
        if (key === "wallet_ceiling_usd") {
          const w = (v: unknown) => { const n = amount(v); return n === null ? t(`${C}.noCeiling`) : n === undefined ? scalar(v) : `${money.format(n)} USD`; };
          return [`${t(`${C}.ceiling`)}: ${w(from)} → ${w(to)}`];
        }
        return [`${key}: ${scalar(from)} → ${scalar(to)}`];
      });
      return { change: parts.length ? parts.join("; ") : null, why: reason };
    }
    // Methodology: the reason is the writer's "sociomap preset -> e3"; the person's is `why`, if any.
    case "METHODOLOGY_ACTIVATED":
    case "METHODOLOGY_RESET":
      return { change: "to" in p ? `${methodVersion(p.from)} → ${methodVersion(p.to)}` : null, why };
    case "METHODOLOGY_PROPOSED":
      // The version as Metodika names it, from its preset: "aia-sociomap-3+e2".
      return { change: typeof p.version === "number" && typeof p.base_preset === "string" ? `${p.base_preset}+e${p.version}` : null, why: null };
    case "PROMPT_ACTIVATED":
    case "PROMPT_RESET_TO_BASELINE":
      return { change: "to" in p ? `${promptVersion(p.from)} → ${promptVersion(p.to)}` : null, why };
    case "PROMPT_VERSION_CREATED":
      return { change: typeof p.version === "string" ? promptVersion(p.version) : null, why: null };
    case "DR_SETTING_APPROVED":
    case "DR_SETTING_WITHDRAWN":
      return { change: "to" in p ? `${ruleVersion(p.from)} → ${ruleVersion(p.to)}` : null, why };
    case "DR_SETTING_PROPOSED":
      return { change: "value" in p ? `${ruleVersion(p.version)}: ${scalar(p.value)}` : null, why: null };
    case "CLIENT_KNOWLEDGE_DECIDED":
      return { change: reason ? named(`${C}.decision`, reason) : null, why: null };
    case "MEMBER_ROLE_DENIED":
      // A refused deactivation or reactivation of an OWNER names itself in payload.change
      // (scope_repository.record_role_denied); a refused role change carries none. The reason is
      // the refusal's own code, in words.
      return { change: typeof p.change === "string" ? named(`${C}.denied`, p.change) : null, why: reasonWords(reason) };
    default:
      return { change: null, why: why ?? reasonWords(reason) };
  }
}

/** What an organization-level record concerns, from its payload: the methodology module, the
 *  prompt or the Deep Research rule it changed, by the name its own page gives it; null for none. */
export function concernsOf(e: Entry): string | null {
  const p = e.payload ?? {};
  if (e.action.startsWith("METHODOLOGY_") && typeof p.module === "string") {
    // The name Metodika's catalogue gives the module (MethodologyPanel nameOf); the stored id where
    // the copy names none, never blank.
    return known("aia.settings.methodology.name", p.module) ?? p.module;
  }
  if (e.action.startsWith("PROMPT_") && typeof p.prompt_id === "string") {
    return known("aia.settings.prompts.names", p.prompt_id.replaceAll(".", "_")) ?? p.prompt_id.split(".").at(-1)!.replaceAll("_", " ");
  }
  if (e.action.startsWith("DR_SETTING_") && typeof p.key === "string") return RULE_LABELS[p.key] ?? p.key;
  return null;
}
