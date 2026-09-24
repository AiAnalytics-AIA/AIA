// The one way the rebuilt interface talks to the unit (ADR 0014). Same origin,
// from the browser, through the gated paths the classic document uses: the
// session cookie rides along, and the browser's Origin satisfies the gate's
// origin check on a POST. Answers are `unknown` here; each area parses what it
// reads (src/unit/projects.ts), so a unit that changes shape fails a parse, not
// a render.

import { type UnitRouteKey, resolveRoute } from "./routes";

export class UnitError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
  ) {
    super(message);
    this.name = "UnitError";
  }
}

// The classic interface's own wording for the same failures (requestJson).
export const TIMEOUT_MESSAGE =
  "Operace překročila časový limit. Backend nevrátil výsledek; zkuste ji znovu nebo otevřete diagnostiku.";

type Options = {
  body?: unknown;
  /** The id an id route is addressed by (a job, a workflow). */
  id?: string;
  /** Query parameters, e.g. { id } for GET /api/job. */
  query?: Record<string, string>;
  timeoutMs?: number;
  fetchImpl?: typeof fetch;
  /** Aborts the call from outside, e.g. when the screen that asked goes away. */
  signal?: AbortSignal;
};

export async function unit(
  key: UnitRouteKey,
  { body, id, query, timeoutMs = 120_000, fetchImpl = fetch, signal }: Options = {},
): Promise<unknown> {
  const { verb, path } = resolveRoute(key, id);
  const url = query ? `${path}?${new URLSearchParams(query).toString()}` : path;
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  signal?.addEventListener("abort", () => ctl.abort(), { once: true });
  try {
    const res = await fetchImpl(url, {
      method: verb,
      headers: verb === "POST" ? { "Content-Type": "application/json" } : undefined,
      body: verb === "POST" ? JSON.stringify(body ?? {}) : undefined,
      credentials: "same-origin",
      signal: ctl.signal,
    });
    const text = await res.text();
    let json: unknown = {};
    try {
      json = text ? JSON.parse(text) : {};
    } catch {
      json = { error: text || res.statusText };
    }
    if (!res.ok) {
      const error = (json as { error?: unknown }).error;
      throw new UnitError(typeof error === "string" && error ? error : res.statusText || `HTTP ${res.status}`, res.status);
    }
    return json;
  } catch (e) {
    if (e instanceof UnitError) throw e;
    if ((e as Error).name === "AbortError") throw new UnitError(TIMEOUT_MESSAGE, null);
    throw new UnitError((e as Error).message || String(e), null);
  } finally {
    clearTimeout(timer);
  }
}
