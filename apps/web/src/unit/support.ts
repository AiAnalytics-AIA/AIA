// Diagnostika: createSupportBundle, ported. POST /api/support/bundle with the
// failed job's id; the unit answers with where to download the ZIP.

import { unit } from "./client";

/** The ZIP's download URL, or an error with the classic wording. */
export async function createSupportBundle(jobId: string | null, fetchImpl?: typeof fetch): Promise<string> {
  const r = (await unit("supportBundle", { body: { job_id: String(jobId || "") }, timeoutMs: 120_000, fetchImpl })) as {
    download_url?: unknown;
  };
  if (typeof r?.download_url !== "string" || !r.download_url) throw new Error("Backend nevytvořil diagnostický soubor.");
  return r.download_url;
}
