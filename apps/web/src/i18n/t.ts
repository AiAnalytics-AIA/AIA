import { cs } from "@/i18n/cs";

// Czech-only UI for now; docs remain English.

type Leaves<T, P extends string = ""> = {
  [K in keyof T & string]: T[K] extends string ? `${P}${K}` : Leaves<T[K], `${P}${K}.`>;
}[keyof T & string];

/** Every valid copy key, e.g. "portfolio.title". A typo is a type error, not a raw key on screen. */
export type CopyKey = Leaves<typeof cs>;

function get(obj: unknown, path: string): unknown {
  return path.split(".").reduce<unknown>(
    (acc, k) => (acc && typeof acc === "object" ? (acc as Record<string, unknown>)[k] : undefined),
    obj,
  );
}

export function t(key: CopyKey): string {
  const v = get(cs, key);
  return typeof v === "string" ? v : key;
}
