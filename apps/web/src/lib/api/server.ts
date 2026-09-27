// Server-side client for the AIA API. Imported only by server components and
// server actions: the browser never holds the API location or a credential.
//
// Configuration (environment of the Next.js server):
//   AIA_API_URL           e.g. http://localhost:8000 -- unset means "not connected",
//                         which the page renders as unavailable, never as fixtures.
//   AIA_WEB_DEV_SUBJECT   local development only: sent as X-AIA-Subject. The API
//                         accepts that header only when it runs with
//                         AIA_IDENTITY_PROVIDER=development in a local/test env.
//
// A Cognito session (an Authorization: Bearer token) replaces the development
// header when sign-in lands in the web client; that is not wired yet.

export type ApiError = {
  status: number | null; // null: the API could not be reached at all
  code: string;
  message: string;
  requestId: string | null;
};

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };

const PREFIX = "/api/v1";

export function apiConfigured(): boolean {
  return Boolean(process.env.AIA_API_URL?.trim());
}

function headers(json: boolean): HeadersInit {
  const h: Record<string, string> = { Accept: "application/json" };
  if (json) h["Content-Type"] = "application/json";
  const subject = process.env.AIA_WEB_DEV_SUBJECT?.trim();
  if (subject) h["X-AIA-Subject"] = subject;
  return h;
}

async function call<T>(method: string, path: string, body?: unknown): Promise<ApiResult<T>> {
  const base = process.env.AIA_API_URL?.trim().replace(/\/+$/, "");
  if (!base) {
    return {
      ok: false,
      error: { status: null, code: "not_configured", message: "AIA_API_URL is not set.", requestId: null },
    };
  }
  let response: Response;
  try {
    response = await fetch(`${base}${PREFIX}${path}`, {
      method,
      headers: headers(body !== undefined),
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch (err) {
    return {
      ok: false,
      error: {
        status: null,
        code: "unreachable",
        message: err instanceof Error ? err.message : String(err),
        requestId: null,
      },
    };
  }
  if (response.status === 204) return { ok: true, data: undefined as T };
  const text = await response.text();
  let parsed: unknown = null;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    parsed = null;
  }
  if (!response.ok) {
    // The API's one error contract: {code, message, details, request_id}.
    const e = (parsed && typeof parsed === "object" ? parsed : {}) as Record<string, unknown>;
    return {
      ok: false,
      error: {
        status: response.status,
        code: typeof e.code === "string" ? e.code : `http_${response.status}`,
        message: typeof e.message === "string" ? e.message : text.slice(0, 200),
        requestId: typeof e.request_id === "string" ? e.request_id : null,
      },
    };
  }
  return { ok: true, data: parsed as T };
}

export const api = {
  get: <T>(path: string) => call<T>("GET", path),
  post: <T>(path: string, body: unknown) => call<T>("POST", path, body),
  put: <T>(path: string, body: unknown) => call<T>("PUT", path, body),
};
