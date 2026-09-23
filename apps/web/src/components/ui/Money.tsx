import { formatMoney } from "@/design/format";
import { Value } from "./Value";

/** A monetary amount, always with its currency. `null` is "chybí", never 0,00. */
export function Money({ value, currency = "USD", digits = 2 }: { value: number | null | undefined; currency?: string; digits?: number }) {
  if (value == null || Number.isNaN(value)) return <Value value={null} />;
  return <span data-state={value === 0 ? "zero" : "value"} className="whitespace-nowrap tabular-nums">{formatMoney(value, currency, digits)}</span>;
}
