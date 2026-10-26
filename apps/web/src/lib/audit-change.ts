// What an audit record changed, in words (settings-redesign F10, prototype v99's Změna column):
// read from what its writer stored -- the reason the scope repository fills with "a -> b", a status
// code, or the payload's from / to -- and the reason a person gave, apart from it. Pure. A shape
// this file does not know is never guessed at: its reason is kept as written.

import { t, tv } from "@/i18n/t";

/** A record's change and the person's reason beside it. */
export type AuditChange = {
  /** The change itself ("100 → 120 USD", "výzkumník → správce"); null where the record carries none. */
  change: string | null;
  /** The reason a person gave, apart from the change; null where none was given. */
  why: string | null;
};

type Record_ = { action: string; reason: string; payload: Record<string, unknown> | null | undefined };

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

/** A code's name under a copy key, or the code itself: never blank. */
function named(key: string, code: string): string {
  const s = t(`${key}.${code}`);
  return s === `${key}.${code}` ? code : s;
}

const text = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v.trim() : null);
const scalar = (v: unknown): string => (v === null || v === undefined ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v));
const version = (v: unknown, none: string): string => (v === null || v === undefined ? none : typeof v === "number" ? `v${v}` : String(v));

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

/** A record's change in words, and the person's reason apart from it. */
export function changeOf(e: Record_): AuditChange {
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
      if (typeof p.to !== "string") return { change: null, why: reason };
      const to = named("aia.orgRoles", p.to);
      if (p.from === null || p.from === undefined) return { change: tv(`${C}.joinedAs`, { role: to }), why: null };
      if (p.from === p.to) return { change: null, why: null };
      return { change: `${typeof p.from === "string" ? named("aia.orgRoles", p.from) : scalar(p.from)} → ${to}`, why: null };
    }
    case "SELF_APPROVAL_CONFIGURED": {
      const level = typeof p.level === "string" ? named(`${C}.level`, p.level) : null;
      const v = p.allow_self_approval;
      const state = v === true ? t(`${C}.allowed`) : v === false ? t(`${C}.forbidden`) : v === null ? t(`${C}.inherits`) : null;
      return { change: state ? (level ? `${level}: ${state}` : state) : null, why: reason };
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
    case "METHODOLOGY_ACTIVATED":
    case "METHODOLOGY_RESET":
      return { change: "to" in p ? `${version(p.from, t(`${C}.fromCode`))} → ${version(p.to, t(`${C}.fromCode`))}` : null, why: why ?? reason };
    case "METHODOLOGY_PROPOSED":
      return { change: p.version !== undefined && p.version !== null ? version(p.version, "—") : null, why: why ?? reason };
    case "PROMPT_ACTIVATED":
    case "PROMPT_RESET_TO_BASELINE":
      return { change: "to" in p ? `${scalar(p.from)} → ${scalar(p.to)}` : reason, why };
    case "PROMPT_VERSION_CREATED":
      return { change: text(p.version) ?? reason, why };
    case "DR_SETTING_APPROVED":
    case "DR_SETTING_WITHDRAWN":
      return { change: "to" in p ? `${version(p.from, t(`${C}.default`))} → ${version(p.to, t(`${C}.default`))}` : reason, why };
    case "DR_SETTING_PROPOSED":
      return { change: "value" in p ? `${version(p.version, "—")}: ${scalar(p.value)}` : reason, why: null };
    default:
      return { change: null, why: why ?? reason };
  }
}
