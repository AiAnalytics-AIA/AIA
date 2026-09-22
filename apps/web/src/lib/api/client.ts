import { parseError } from "./validate";

/**
 * Server-side client for the AIA API. Server components only: the development
 * identity header is not a CORS-allowed header, and credentials must not reach
 * the browser bundle.
 *
 * Configuration (read per request, so tests and `next start` see the same thing):
 *   AIA_API_URL      base URL including /api/v1   (default http://localhost:8000/api/v1)
 *   AIA_DEV_SUBJECT  development identity, sent as X-AIA-Subject. Unset = no identity,
 *                    and the API answers 401 — shown as such, never papered over.
 *   AIA_DEV_ORG      organization id, sent as X-AIA-Org, for a member of several.
 *
 * There is no production identity path yet: the web client has no sign-in
 * (open item OI-14). Until it does, this client authenticates only in local
 * development, and it says so on screen.
 */

export type ApiErrorKind =
  | "unreachable"
  | "unauthenticated"
  | "not_provisioned"
  | "organization_required"
  | "not_found"
  | "invalid_response"
  | "error";

export type ApiError = {
  kind: ApiErrorKind;
  /** HTTP status, or null when the API never answered. */
  status: number | null;
  /** The API's own code, when it sent the error contract. */
  code: string | null;
  message: string;
  requestId: string | null;
  path: string;
};

export type ApiResult<T> = { ok: true; data: T; requestId: string | null } | { ok: false; error: ApiError };

export type ApiConfig = { baseUrl: string; subject: string | null; org: string | null };

export function apiConfig(env: Record<string, string | undefined> = process.env): ApiConfig {
  return {
    baseUrl: (env.AIA_API_URL || "http://localhost:8000/api/v1").replace(/\/+$/, ""),
    subject: env.AIA_DEV_SUBJECT?.trim() || null,
    org: env.AIA_DEV_ORG?.trim() || null,
  };
}

/**
 * Map an HTTP failure to the kinds the screens distinguish. A 422 whose every
 * error is in the *path* (a malformed id such as `STU-nope`) is a not-found:
 * the id cannot name anything, and a validation message would tell a visitor
 * which id formats exist for no benefit.
 */
export function errorKind(status: number, code: string | null, details: Record<string, unknown> = {}): ApiErrorKind {
  if (status === 401) return "unauthenticated";
  if (status === 404) return "not_found";
  if (status === 422 && code === "validation_error" && onlyPathErrors(details)) return "not_found";
  if (code === "not_provisioned") return "not_provisioned";
  if (code === "organization_required") return "organization_required";
  return "error";
}

function onlyPathErrors(details: Record<string, unknown>): boolean {
  const errors = details.errors;
  return (
    Array.isArray(errors) &&
    errors.length > 0 &&
    errors.every((e) => typeof e === "object" && e !== null && Array.isArray((e as { loc?: unknown }).loc) && (e as { loc: unknown[] }).loc[0] === "path")
  );
}

type Fetch = (input: string, init: RequestInit) => Promise<Response>;

export async function apiGet<T>(
  path: string,
  parse: (u: unknown) => T | null,
  opts: { config?: ApiConfig; fetchImpl?: Fetch } = {},
): Promise<ApiResult<T>> {
  const config = opts.config ?? apiConfig();
  const doFetch: Fetch = opts.fetchImpl ?? ((i, init) => fetch(i, init));
  const headers: Record<string, string> = { Accept: "application/json" };
  if (config.subject) headers["X-AIA-Subject"] = config.subject;
  if (config.org) headers["X-AIA-Org"] = config.org;

  let res: Response;
  try {
    res = await doFetch(`${config.baseUrl}${path}`, { headers, cache: "no-store" });
  } catch (e) {
    return fail({ kind: "unreachable", status: null, code: null, message: e instanceof Error ? e.message : String(e), requestId: null, path });
  }

  const requestId = res.headers.get("x-request-id");
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }

  if (!res.ok) {
    const err = parseError(body);
    return fail({
      kind: errorKind(res.status, err?.code ?? null, err?.details),
      status: res.status,
      code: err?.code ?? null,
      message: err?.message ?? res.statusText,
      requestId: err?.request_id ?? requestId,
      path,
    });
  }

  const data = parse(body);
  if (data === null) {
    return fail({ kind: "invalid_response", status: res.status, code: null, message: "response did not match the expected shape", requestId, path });
  }
  return { ok: true, data, requestId };
}

function fail(error: ApiError): { ok: false; error: ApiError } {
  return { ok: false, error };
}
