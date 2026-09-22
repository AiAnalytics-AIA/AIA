import { t } from "@/i18n/t";
import { Money, Value } from "@/components/ui";

/**
 * The study route returns cost fields as null exactly when the viewer lacks
 * VIEW_COSTS (`apps/api/src/aia_api/routers/scope.py:204`); the domain budget is
 * never null. So null here is withheld, and says so — not "chybí", not 0.
 */
export function StudyMoney({ value }: { value: number | null | undefined }) {
  return value == null ? <Value value={null} state="suppressed" reason={t("study.costsWithheld")} /> : <Money value={value} />;
}
