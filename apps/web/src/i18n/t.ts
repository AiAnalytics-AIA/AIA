import { cs } from "@/i18n/cs";

// Minimal i18n helper (MVP): Czech-only UI.
// Docs remain English.

type Dict = typeof cs;

function get(obj: Record<string, unknown>, path: string) {
  return path
    .split(".")
    .reduce<unknown>(
      (acc, k) =>
        acc && typeof acc === "object"
          ? (acc as Record<string, unknown>)[k]
          : undefined,
      obj,
    );
}

export function t(key: string): string {
  const v = get(cs as unknown as Dict, key);
  if (typeof v === "string") return v;
  return key;
}

/** t() with `{name}` placeholders filled. */
export function tv(key: string, vars: Record<string, string | number>): string {
  return t(key).replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}
