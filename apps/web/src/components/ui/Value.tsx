import { cs } from "@/i18n/cs";
import { evidenceGrade } from "@/design/evidence";
import { formatNumber } from "@/design/format";
import { EvidenceMark } from "./EvidenceMark";

/**
 * The one way a figure is rendered. Five states, never conflated:
 *   value      — we measured or modelled this
 *   zero       — we looked; the answer is zero (a value, drawn like one)
 *   na         — we never looked, or the answer did not arrive ("chybí")
 *   suppressed — we have it but withhold it; the reason is always given
 *   loading    — waiting for the server; no skeleton, no shimmer
 * `null`/`undefined` is NOT zero: it is "chybí". A NaN is "chybí" too.
 */
export type ValueState = "value" | "zero" | "na" | "suppressed" | "loading";

type Props = {
  value?: number | null;
  /** Force a state the number alone cannot express (suppressed, loading). */
  state?: "suppressed" | "loading";
  /** Required for suppression: small sample, permission… */
  reason?: string;
  format?: (v: number) => string;
  digits?: number;
  /** Evidence role of this figure. Omit when the figure carries no role. */
  role?: unknown;
  /** The grade the column header already declares; the mark is omitted when it matches. */
  inheritRole?: unknown;
};

export function valueState(value: number | null | undefined, forced?: "suppressed" | "loading"): ValueState {
  if (forced) return forced;
  if (value == null || Number.isNaN(value)) return "na";
  return value === 0 ? "zero" : "value";
}

export function Value({ value, state, reason, format, digits, role, inheritRole }: Props) {
  const st = valueState(value, state);
  if (st === "na") {
    return (
      <span data-state="na" title={cs.nulls.naLong} className="inline-block rounded-sm border border-null-mark px-1 text-xs font-semibold leading-4 tracking-[0.02em] text-null-mark [background:repeating-linear-gradient(135deg,transparent_0_3px,var(--border)_3px_4px)]">
        {cs.nulls.na}
      </span>
    );
  }
  if (st === "suppressed") {
    return (
      <span data-state="suppressed" title={`${cs.nulls.suppressedLong} — ${reason ?? cs.nulls.reasonMissing}`} className="inline-flex flex-wrap items-center gap-x-1 text-xs text-ink-muted">
        <span aria-hidden="true" className="inline-block h-2.5 w-7 rounded-[1px] bg-suppressed-fill" />
        <span>{cs.nulls.suppressed}</span>
        <span>· {reason ?? cs.nulls.reasonMissing}</span>
      </span>
    );
  }
  if (st === "loading") {
    return <span data-state="loading" role="status" aria-label={cs.nulls.loading} className="inline-block h-3 w-8 border-b-[1.5px] border-dotted border-ink-faint" />;
  }
  const n = value as number;
  const text = format ? format(n) : formatNumber(n, digits);
  const hasRole = role !== undefined;
  const grade = hasRole ? evidenceGrade(role) : null;
  const underline =
    grade === "modelled" || grade === "holdout-pending" ? "underline decoration-dotted decoration-[1.5px] underline-offset-[3px]"
    : grade === "unknown" ? "underline decoration-dashed decoration-[1.5px] underline-offset-[3px]" : "";
  const showMark = hasRole && !(inheritRole !== undefined && evidenceGrade(inheritRole) === grade);
  return (
    <span data-state={st} data-grade={grade ?? undefined} className="inline-flex items-baseline gap-[3px] whitespace-nowrap">
      <span className={`tabular-nums ${underline}`}>{text}</span>
      {showMark ? <EvidenceMark role={role} /> : null}
      {grade === "holdout-pending" ? <span className="rounded-sm border border-evidence-mark px-[3px] text-[11px] font-semibold leading-[14px]">{cs.evidence["holdout-pending"].short}</span> : null}
    </span>
  );
}
