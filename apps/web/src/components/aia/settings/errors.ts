// How an API refusal is said on the settings page: the status, the machine word and the
// API's own sentence, verbatim, with the request id to quote. Shared by the control panel
// and the system prompts tab so a refusal reads the same wherever it happens.

import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";

export function describeError(e: unknown): string {
  if (e instanceof ApiError) return `HTTP ${e.status} · ${e.code}: ${e.message}${e.requestId ? ` (${e.requestId})` : ""}`;
  return e instanceof Error ? e.message : String(e);
}

/** The OWNER guard's refusals (details.reason) said in Czech; any other refusal as given. */
const OWNER_REFUSALS = new Set(["owner_only", "last_owner"]);
export function describeMemberError(e: unknown): string {
  const reason = e instanceof ApiError ? e.details.reason : undefined;
  if (typeof reason === "string" && OWNER_REFUSALS.has(reason)) return t(`aia.settings.panel.members.refused.${reason}`);
  return describeError(e);
}
