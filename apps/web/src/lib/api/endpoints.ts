import { apiGet, type ApiResult } from "./client";
import type { ClientResponse, EventResponse, ImpactResponse, Page, ProjectDetailResponse, ProjectResponse, StudyResponse } from "./types";
import { listOf, pageOf, parseClient, parseEvent, parseImpact, parseProject, parseProjectDetail, parseStudy } from "./validate";

/**
 * The routes the slice reads, one function each. Paths mirror
 * `apps/api/src/aia_api/routers/{scope,projects}.py`; every project route is
 * study-scoped. There is deliberately nothing here for workflow runs, gates,
 * approvals, reservations or "needs me" — the API has no route for them yet
 * (see `UNAVAILABLE_CAPABILITIES` in `@/fixtures/registry`).
 */

const enc = encodeURIComponent;

export const listClients = (): Promise<ApiResult<ClientResponse[]>> => apiGet("/clients", listOf(parseClient));

export const listStudies = (clientId?: string): Promise<ApiResult<StudyResponse[]>> =>
  apiGet(clientId ? `/studies?client_id=${enc(clientId)}` : "/studies", listOf(parseStudy));

export const getStudy = (studyId: string): Promise<ApiResult<StudyResponse>> => apiGet(`/studies/${enc(studyId)}`, parseStudy);

export const listProjects = (studyId: string): Promise<ApiResult<Page<ProjectResponse>>> =>
  apiGet(`/studies/${enc(studyId)}/projects`, pageOf(parseProject));

export const getProject = (studyId: string, projectId: string): Promise<ApiResult<ProjectDetailResponse>> =>
  apiGet(`/studies/${enc(studyId)}/projects/${enc(projectId)}`, parseProjectDetail);

export const getImpact = (studyId: string, projectId: string, field: string): Promise<ApiResult<ImpactResponse>> =>
  apiGet(`/studies/${enc(studyId)}/projects/${enc(projectId)}/impact?field=${enc(field)}`, parseImpact);

export const listEvents = (studyId: string, projectId: string, limit = 20): Promise<ApiResult<EventResponse[]>> =>
  apiGet(`/studies/${enc(studyId)}/projects/${enc(projectId)}/events?limit=${limit}`, listOf(parseEvent));
