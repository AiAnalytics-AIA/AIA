import type {
  ClientResponse,
  EventResponse,
  ErrorResponse,
  ImpactResponse,
  Page,
  ProjectDetailResponse,
  ProjectResponse,
  StageResponse,
  StudyResponse,
} from "./types";

/**
 * Structural checks on API responses. A response that fails is reported as
 * `invalid_response`, never rendered: a missing field becomes a visible error,
 * not a silently coerced default. Only the fields the web client reads are
 * checked; extra fields pass through.
 *
 * Enum-valued fields are checked as strings only. Narrowing to the domain unions
 * happens at render time (`appearance()`), where an unknown value shows "?".
 */

type Rec = Record<string, unknown>;

const isRec = (u: unknown): u is Rec => typeof u === "object" && u !== null && !Array.isArray(u);
const str = (o: Rec, k: string) => typeof o[k] === "string";
const strOrNull = (o: Rec, k: string) => o[k] === null || typeof o[k] === "string";
const num = (o: Rec, k: string) => typeof o[k] === "number" && Number.isFinite(o[k]);
/** Absent or null is allowed — the API omits cost fields the viewer may not see. */
const numOpt = (o: Rec, k: string) => o[k] === undefined || o[k] === null || num(o, k);
const bool = (o: Rec, k: string) => typeof o[k] === "boolean";
const strArr = (o: Rec, k: string) => Array.isArray(o[k]) && (o[k] as unknown[]).every((x) => typeof x === "string");

function all(o: Rec, checks: [(o: Rec, k: string) => boolean, string[]][]): boolean {
  return checks.every(([f, keys]) => keys.every((k) => f(o, k)));
}

export function parseClient(u: unknown): ClientResponse | null {
  if (!isRec(u)) return null;
  return all(u, [[str, ["client_id", "slug", "name", "status", "reference"]], [num, ["study_count"]]]) ? (u as ClientResponse) : null;
}

export function parseStudy(u: unknown): StudyResponse | null {
  if (!isRec(u)) return null;
  return all(u, [
    [str, ["study_id", "client_id", "slug", "name", "status"]],
    [bool, ["accepts_work"]],
    [strOrNull, ["your_role"]],
    [numOpt, ["budget_usd", "spent_usd", "remaining_usd"]],
  ])
    ? (u as StudyResponse)
    : null;
}

export function parseStage(u: unknown): StageResponse | null {
  if (!isRec(u)) return null;
  return all(u, [
    [str, ["stage_type", "status", "label"]],
    [num, ["ordinal", "artifact_count"]],
    [strOrNull, ["waiting_reason", "quota_reset_at", "started_at", "finished_at"]],
    [bool, ["is_complete"]],
  ])
    ? (u as StageResponse)
    : null;
}

export function parseProject(u: unknown): ProjectResponse | null {
  if (!isRec(u)) return null;
  return all(u, [
    [str, ["project_id", "title", "project_type", "status", "current_stage"]],
    [num, ["current_revision"]],
    [strOrNull, ["last_completed_stage"]],
  ])
    ? (u as ProjectResponse)
    : null;
}

export function parseProjectDetail(u: unknown): ProjectDetailResponse | null {
  const p = parseProject(u);
  if (!p || !isRec(u) || !Array.isArray(u.stages)) return null;
  const stages = u.stages.map(parseStage);
  if (stages.some((s) => s === null)) return null;
  return { ...(u as ProjectDetailResponse), stages: stages as StageResponse[] };
}

export function parseImpact(u: unknown): ImpactResponse | null {
  if (!isRec(u)) return null;
  return all(u, [[strOrNull, ["root_stage"]], [strArr, ["invalidate", "preserve"]], [bool, ["presentation_only"]]])
    ? (u as ImpactResponse)
    : null;
}

export function parseEvent(u: unknown): EventResponse | null {
  if (!isRec(u)) return null;
  return all(u, [[num, ["event_id", "revision"]], [str, ["event_type", "level", "message", "created_at"]], [strOrNull, ["stage_type"]]])
    ? (u as EventResponse)
    : null;
}

export function parseError(u: unknown): ErrorResponse | null {
  if (!isRec(u) || !str(u, "code") || !str(u, "message")) return null;
  return { code: u.code as string, message: u.message as string, details: isRec(u.details) ? u.details : {}, request_id: typeof u.request_id === "string" ? u.request_id : null };
}

/** A list of `item`s, null if any one fails — a partial list would read as complete. */
export function listOf<T>(item: (u: unknown) => T | null): (u: unknown) => T[] | null {
  return (u) => {
    if (!Array.isArray(u)) return null;
    const out = u.map(item);
    return out.some((x) => x === null) ? null : (out as T[]);
  };
}

/** A paginated `{items, page}` envelope. */
export function pageOf<T>(item: (u: unknown) => T | null): (u: unknown) => Page<T> | null {
  return (u) => {
    if (!isRec(u) || !isRec(u.page)) return null;
    const items = listOf(item)(u.items);
    const pg = u.page;
    if (!items || !num(pg, "total") || !bool(pg, "has_more")) return null;
    return { items, page: { total: pg.total as number, limit: Number(pg.limit), offset: Number(pg.offset), has_more: pg.has_more as boolean } };
  };
}
