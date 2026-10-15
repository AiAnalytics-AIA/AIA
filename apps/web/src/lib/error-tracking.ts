// What broke in the browser, sent to GlitchTip (.planning/plans/error-tracking.md chunk 4).
//
// GlitchTip speaks Sentry's protocol, so this drives @sentry/browser -- loaded only when
// /config names a DSN (a dynamic import: a deployment without one downloads none of it).
// Reported: an uncaught error, an unhandled rejection (the SDK's global handlers) and a
// render crash an error boundary caught (reportError). Not reported: anything AIA handled.
//
// What may leave is decided here, as the API and the worker decide it in aia_core:
// secret shapes redacted by key and by value, every URL without its query or fragment (a
// search, a code or a state can ride there), request headers but the user agent dropped,
// no user, no session tracking, no tracing, no replay.

import type { PublicConfig } from "@/lib/public-config";

type Sdk = typeof import("./error-tracking-sdk");
type Settings = PublicConfig["errorTracking"];
type Json = unknown;

const REDACTED = "[redacted]";
// The same shapes as aia_core.infrastructure.redaction: a key named like a secret, and
// provider keys, bearer tokens, JWTs and `token=...` assignments inside any text.
const SECRET_KEY = /(api[_-]?key|secret|token|password|passwd|credential|authorization|cookie)/i;
const SECRET_VALUES: [RegExp, string][] = [
  [/sk-[A-Za-z0-9][A-Za-z0-9_-]{15,}/g, REDACTED],
  [/Bearer\s+[A-Za-z0-9._-]{10,}/gi, REDACTED],
  [/eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}/g, REDACTED],
  [/((?:api[_-]?key|token|secret|password)\s*[=:]\s*)[A-Za-z0-9._-]{12,}/gi, `$1${REDACTED}`],
];
const URL_KEYS = new Set(["url", "from", "to"]);
const QUEUE_LIMIT = 10;

let sdk: Sdk | null = null;
let starting: Promise<boolean> | null = null;
let pending: { error: unknown; tags?: Record<string, string> }[] = [];

/** Start the reporter once, if a DSN is configured. Resolves to whether it is on. */
export function startErrorTracking(
  settings: Settings | undefined,
  load: () => Promise<Sdk> = () => import("./error-tracking-sdk"),
): Promise<boolean> {
  if (!settings?.dsn) return Promise.resolve(false);
  if (starting) return starting;
  const dsn = settings.dsn;
  starting = load().then((loaded) => {
    loaded.init({
      dsn,
      environment: settings.environment ?? undefined,
      release: settings.release ?? undefined,
      sendDefaultPii: false,
      sendClientReports: false,
      integrations: (defaults) => defaults.filter((i) => i.name !== "BrowserSession"),
      initialScope: { tags: { service: "web" } },
      beforeSend: (event) => scrubEvent(event),
      beforeBreadcrumb: (crumb) => scrubBreadcrumb(crumb),
    });
    sdk = loaded;
    const queued = pending;
    pending = [];
    for (const { error, tags } of queued) report(loaded, error, tags);
    return true;
  });
  return starting;
}

/** A crash an error boundary caught. Held (up to ten) until the reporter has started. */
export function reportError(error: unknown, tags?: Record<string, string>): void {
  if (sdk) report(sdk, error, tags);
  else if (pending.length < QUEUE_LIMIT) pending.push({ error, tags });
}

function report(loaded: Sdk, error: unknown, tags?: Record<string, string>): void {
  loaded.withScope((scope) => {
    scope.setTag("caught_by", "error_boundary");
    for (const [key, value] of Object.entries(tags ?? {})) scope.setTag(key, value);
    loaded.captureException(error);
  });
}

/** Tests only. */
export function resetErrorTracking(): void {
  sdk = null;
  starting = null;
  pending = [];
}

// -------------------------------------------------------------------- scrubbing --

/** The event as it may leave. Typed loosely: it is the JSON object the SDK sends. */
export function scrubEvent<T>(event: T): T {
  const e = event as Record<string, Json>;
  const request = e.request as Record<string, Json> | undefined;
  if (request && typeof request === "object") {
    const headers = (request.headers ?? {}) as Record<string, string>;
    e.request = {
      url: withoutQuery(request.url),
      headers: Object.fromEntries(
        Object.entries(headers).filter(([k]) => k.toLowerCase() === "user-agent"),
      ),
    };
  }
  delete e.user;
  const breadcrumbs = e.breadcrumbs;
  if (Array.isArray(breadcrumbs)) e.breadcrumbs = breadcrumbs.map((c) => scrubBreadcrumb(c));
  return redact(e) as T;
}

/** A breadcrumb as it may leave: every URL without its query, everything redacted. */
export function scrubBreadcrumb<T>(crumb: T): T {
  const c = crumb as Record<string, Json>;
  const data = c.data as Record<string, Json> | undefined;
  if (data && typeof data === "object") {
    for (const key of Object.keys(data)) if (URL_KEYS.has(key)) data[key] = withoutQuery(data[key]);
  }
  return redact(c) as T;
}

export function redact(value: Json, depth = 0): Json {
  if (depth > 8) return "[truncated]";
  if (typeof value === "string") {
    return SECRET_VALUES.reduce((text, [pattern, replacement]) => text.replace(pattern, replacement), value);
  }
  if (Array.isArray(value)) return value.map((item) => redact(item, depth + 1));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([k, v]) => [k, SECRET_KEY.test(k) ? REDACTED : redact(v, depth + 1)]),
    );
  }
  return value;
}

function withoutQuery(url: Json): Json {
  if (typeof url !== "string") return url;
  const cut = url.search(/[?#]/);
  return cut === -1 ? url : url.slice(0, cut);
}
