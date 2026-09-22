import { notFound } from "next/navigation";
import type { ApiResult } from "./client";

/**
 * A 404 from the API becomes the page's 404. The API answers "not found" both
 * for a missing resource and for one the viewer may not see, so the page must
 * not say which (`app.notFound`). Every other failure is returned for the page
 * to render as an error — never as an empty result.
 */
export function orNotFound<T>(r: ApiResult<T>): ApiResult<T> {
  if (!r.ok && r.error.kind === "not_found") notFound();
  return r;
}
