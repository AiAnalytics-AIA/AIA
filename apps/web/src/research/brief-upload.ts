// What the Brief says when a file cannot be kept (artifact-brief audit): in Czech, never the API's
// English message. A file that is empty or larger than the server takes is refused here, before
// its bytes (base64, a third larger) are sent at all; anything the server refuses is said by its
// code. Pure.

import { t, tv } from "@/i18n/t";
import { ApiError } from "@/lib/api";

/** The largest file the brief keeps: domain/attachments.py ATTACHMENT_MAX_BYTES. */
export const ATTACHMENT_MAX_BYTES = 25 * 1024 * 1024;

/** Why a file of `size` bytes cannot be kept, by the server's own reason code; null when it can. */
export function fileProblem(size: number): "empty" | "too_large" | null {
  if (size <= 0) return "empty";
  if (size > ATTACHMENT_MAX_BYTES) return "too_large";
  return null;
}

const REASONS: Readonly<Record<string, string>> = {
  empty: "aia.sources.reasons.empty",
  too_large: "aia.sources.reasons.too_large",
  not_base64: "aia.sources.reasons.not_base64",
};

/**
 * A failed upload in words. A reason code the server gave (or fileProblem's) in its Czech words;
 * an API refusal without words of its own, named by its code; a failure that never reached the
 * API (the network), said as such.
 */
export function uploadProblem(e: unknown): string {
  const code = typeof e === "string" ? e : e instanceof ApiError ? e.code : null;
  if (code !== null && REASONS[code]) return t(REASONS[code]);
  if (code !== null) return tv("research.brief.uploadRefused", { code });
  return t("research.brief.uploadUnreachable");
}
