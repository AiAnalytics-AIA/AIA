// A failure as a person reads it (design system v3, I-StavyObsahu): one Czech sentence that says
// what happened and what to do, never the API's English message, a status code or a request id.
// Those stay available as technical detail, said after the sentence and labelled as such.

import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";

/** The Czech sentence: by the HTTP status, else a dropped connection. A refusal a screen knows by
 *  its code is said by that screen first; this is what everything else falls back to. */
export function errorWords(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 401) return t("errors.status.401");
    if (e.status === 403) return t("errors.status.403");
    if (e.status === 404) return t("errors.status.404");
    if (e.status === 409) return t("errors.status.409");
    if (e.status === 413) return t("errors.status.413");
    if (e.status === 400 || e.status === 422) return t("errors.status.422");
    if (e.status === 429) return t("errors.status.429");
    if (e.status >= 500) return t("errors.status.500");
    return t("errors.generic");
  }
  // fetch() rejects with a TypeError when the request never reached the server.
  if (e instanceof TypeError) return t("errors.network");
  // Any other Error was thrown by this client, in its own Czech words.
  if (e instanceof Error && e.message) return e.message;
  return t("errors.generic");
}

/** What a developer or an administrator needs to trace an API refusal: status, code, the API's
 *  words, the request id. A failure the client raised itself has none beyond its sentence. */
export function errorTechnical(e: unknown): string | null {
  if (e instanceof ApiError) return `HTTP ${e.status} · ${e.code}: ${e.message}${e.requestId ? ` (${e.requestId})` : ""}`;
  if (e instanceof TypeError && e.message) return e.message;
  return null;
}

/** For a place that takes one string: the sentence, then the technical detail labelled as such. */
export function errorText(e: unknown): string {
  const tech = errorTechnical(e);
  return tech ? `${errorWords(e)} (${t("errors.technical")}: ${tech})` : errorWords(e);
}
