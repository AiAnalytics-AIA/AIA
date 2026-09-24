// Czech plurals and relative time for the client-first shell.

import { t, tv } from "@/i18n/t";

/** "1 aktivní práce", "3 aktivní práce", "5 aktivních prací": the Czech one / few / many. */
export function plural(n: number, one: string, few: string, many: string): string {
  const word = n === 1 ? one : n >= 2 && n <= 4 ? few : many;
  return `${n} ${word}`;
}

/** "před 20 min", "před 3 h", "včera", "před 4 dny", or the date. Null for no date. */
export function relative(iso: string | null | undefined, now: Date = new Date()): string | null {
  if (!iso) return null;
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return null;
  const minutes = Math.floor((now.getTime() - then.getTime()) / 60_000);
  if (minutes < 1) return t("aia.time.justNow");
  if (minutes < 60) return tv("aia.time.minutes", { n: minutes });
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return tv("aia.time.hours", { n: hours });
  const days = Math.floor(hours / 24);
  if (days === 1) return t("aia.time.yesterday");
  if (days < 7) return tv("aia.time.days", { n: days });
  return then.toLocaleDateString("cs-CZ", { day: "numeric", month: "numeric", year: "numeric" });
}
