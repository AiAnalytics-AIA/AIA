// Můj Vedoucí on the rail (prototype-build PBA2, lead-identity LI7 widened to every page): one item
// whose words follow GET /lead's hatched state. No Lead yet: "Vypěstovat Vedoucího" (lane H's
// wording, LI9: a Lead is grown from a test tube); a Lead: "Můj Vedoucí". Not read yet, unreadable or
// out of shape is unknown, and unknown opens Můj Vedoucí's own page, which shows its loading state:
// never the grow step on a guess. Both land on /app/lead, which offers growing when there is none.

import { t } from "@/i18n/t";

import { appRoutes } from "./app-routes";

export type LeadPresence = "hatched" | "none" | "unknown";

/** What GET /lead answered, as the rail reads it; anything else is unknown. */
export function leadPresence(answer: unknown): LeadPresence {
  if (!answer || typeof answer !== "object") return "unknown";
  const hatched = (answer as { hatched?: unknown }).hatched;
  if (hatched === true) return "hatched";
  if (hatched === false) return "none";
  return "unknown";
}

// A Lead once grown stays grown for this tab: the rail does not ask GET /lead again on every page.
let hatchedSeen = false;
export const hatchedRemembered = (): boolean => hatchedSeen;
export function rememberPresence(presence: LeadPresence): void {
  if (presence === "hatched") hatchedSeen = true;
}
/** For tests: the tab's memory of a grown Lead, forgotten. */
export function forgetHatched(): void {
  hatchedSeen = false;
}

export function railLeadItem(presence: LeadPresence): { label: string; href: string; grow: boolean } {
  if (presence === "none") return { label: t("aia.navLeadGrow"), href: appRoutes.lead(), grow: true };
  return { label: t("aia.navLead"), href: appRoutes.lead(), grow: false };
}
