"use client";

// The Sociomap register's answer for one method, as a chip: what the module's head, its catalogue
// card and the versions table each say about a map's use for clients (domain/sociomap_register.py).

import { t } from "@/i18n/t";

const M = "aia.settings.methodology";
/** A head chip's frame (prototype v51): 22 px, pill, one line. */
export const CHIP = "inline-flex min-h-[22px] items-center gap-[5px] whitespace-nowrap rounded-[11px] border px-2 text-xs";

/** `undefined`: still reading; anything but the two answers: unknown, never presumed approved. */
export function RegisterChip({ status, head = false }: { status: string | null | undefined; head?: boolean }) {
  if (status === undefined) return <span data-register="loading" className="text-ink-muted">…</span>;
  if (status !== "CLIENT_FACING" && status !== "INTERNAL_ONLY") return <span data-register="unknown" className={`${CHIP} border-border text-ink-muted`}>{t(`${M}.facts.unknown`)}</span>;
  // Approved is a strong-edged chip, never green (green is only what is in force); internal is the fault's.
  return <span data-register={status} className={`${CHIP} ${status === "CLIENT_FACING" ? "border-border-strong text-ink" : "border-status-fault bg-status-fault-wash text-status-fault"}`}>{t(`${M}.register.${head ? `head${status}` : status}`)}</span>;
}
