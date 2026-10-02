// How an API refusal is said on the settings page: the status, the machine word and the
// API's own sentence, verbatim, with the request id to quote. Shared by the control panel
// and the system prompts tab so a refusal reads the same wherever it happens.

import { ApiError } from "@/lib/api";

export function describeError(e: unknown): string {
  if (e instanceof ApiError) return `HTTP ${e.status} · ${e.code}: ${e.message}${e.requestId ? ` (${e.requestId})` : ""}`;
  return e instanceof Error ? e.message : String(e);
}
