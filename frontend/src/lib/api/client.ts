import type {
  PaperListParams,
  PaperListResponse,
  PaperDetail,
  PaperUpdatePayload,
  AuditOut,
  LookupResult,
  ImportPreviewResponse,
  ImportCommitRequest,
  ImportCommitResult,
  PaperIdList,
  BulkDeleteResult,
  ResearchSessionListResponse,
  ResearchSessionDetail,
  ResearchSessionCreatePayload,
  ResearchFeature,
  JobSummary,
  JobDetail,
  JobQueueState,
  JobQueueItem,
  JobHistoryItem
} from '$lib/types';
import { API_BASE_URL } from './config';

type FetchLike = typeof fetch;

enum HttpMethod {
  GET = 'GET',
  POST = 'POST',
  PATCH = 'PATCH',
  DELETE = 'DELETE'
}

interface RequestOptions extends RequestInit {
  fetchImpl?: FetchLike;
}

async function request<T>(path: string, { fetchImpl, headers, ...rest }: RequestOptions = {}): Promise<T> {
  const fetcher = fetchImpl ?? fetch;
  const response = await fetcher(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(headers ?? {})
    },
    ...rest
  });

  if (!response.ok) {
    const message = await safeErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

async function safeErrorMessage(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data === 'object' && data && 'detail' in data) {
      return `API error ${response.status}: ${data.detail}`;
    }
  } catch (_) {
    // ignore JSON parsing errors
  }
  return `API error ${response.status}: ${response.statusText}`;
}

function buildQuery(params: Partial<PaperListParams>): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    query.set(key, String(value));
  });
  const serialized = query.toString();
  return serialized ? `?${serialized}` : '';
}

export async function fetchPapers(params: Partial<PaperListParams> = {}, fetchImpl?: FetchLike): Promise<PaperListResponse> {
  const query = buildQuery(params);
  return request<PaperListResponse>(`/papers${query}`, { fetchImpl, method: HttpMethod.GET });
}

export async function fetchPaperDetail(id: number, fetchImpl?: FetchLike): Promise<PaperDetail> {
  return request<PaperDetail>(`/papers/${id}`, { fetchImpl, method: HttpMethod.GET });
}

export async function updatePaper(id: number, payload: PaperUpdatePayload, fetchImpl?: FetchLike): Promise<PaperDetail> {
  return request<PaperDetail>(`/papers/${id}`, {
    fetchImpl,
    method: HttpMethod.PATCH,
    body: JSON.stringify(payload)
  });
}

export async function runAudit(id: number, fetchImpl?: FetchLike): Promise<AuditOut> {
  return request<AuditOut>(`/audits/${id}`, { fetchImpl, method: HttpMethod.POST });
}

export async function runAuditBatch(ids: number[], fetchImpl?: FetchLike): Promise<AuditOut[]> {
  return request<AuditOut[]>(`/audits/batch`, {
    fetchImpl,
    method: HttpMethod.POST,
    body: JSON.stringify({ ids })
  });
}

export async function runLookup(id: number, fetchImpl?: FetchLike): Promise<LookupResult> {
  return request<LookupResult>(`/lookup/${id}`, { fetchImpl, method: HttpMethod.POST });
}

export async function runLookupBatch(ids: number[], fetchImpl?: FetchLike): Promise<LookupResult[]> {
  return request<LookupResult[]>(`/lookup/batch`, {
    fetchImpl,
    method: HttpMethod.POST,
    body: JSON.stringify({ ids })
  });
}

export async function clearAuditResults(id: number, fetchImpl?: FetchLike): Promise<void> {
  const fetcher = fetchImpl ?? fetch;
  const response = await fetcher(`${API_BASE_URL}/audits/${id}`, {
    method: HttpMethod.DELETE
  });
  if (!response.ok) {
    const message = await safeErrorMessage(response);
    throw new Error(message);
  }
}

export async function previewImport(file: File, fetchImpl?: FetchLike): Promise<ImportPreviewResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const fetcher = fetchImpl ?? fetch;
  const response = await fetcher(`${API_BASE_URL}/imports/preview`, {
    method: HttpMethod.POST,
    body: formData
  });
  if (!response.ok) {
    const message = await safeErrorMessage(response);
    throw new Error(message);
  }
  return response.json();
}

export async function commitImport(payload: ImportCommitRequest, fetchImpl?: FetchLike): Promise<ImportCommitResult> {
  return request<ImportCommitResult>(`/imports/commit`, {
    fetchImpl,
    method: HttpMethod.POST,
    body: JSON.stringify(payload)
  });
}

export async function fetchPaperIds(params: Partial<PaperListParams> = {}, fetchImpl?: FetchLike): Promise<PaperIdList> {
  const query = buildQuery(params);
  return request<PaperIdList>(`/papers/ids${query}`, { fetchImpl, method: HttpMethod.GET });
}

export async function exportPapers(ids: number[], fetchImpl?: FetchLike): Promise<Blob> {
  const fetcher = fetchImpl ?? fetch;
  const response = await fetcher(`${API_BASE_URL}/papers/export`, {
    method: HttpMethod.POST,
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ ids })
  });

  if (!response.ok) {
    const message = await safeErrorMessage(response);
    throw new Error(message);
  }

  return response.blob();
}

export async function deletePapers(ids: number[], fetchImpl?: FetchLike): Promise<BulkDeleteResult> {
  return request<BulkDeleteResult>(`/papers/delete`, {
    fetchImpl,
    method: HttpMethod.POST,
    body: JSON.stringify({ ids })
  });
}

export async function fetchResearchSessions(fetchImpl?: FetchLike): Promise<ResearchSessionListResponse> {
  return request<ResearchSessionListResponse>(`/research/sessions`, {
    fetchImpl,
    method: HttpMethod.GET
  });
}

export async function fetchResearchSessionDetail(id: number, fetchImpl?: FetchLike): Promise<ResearchSessionDetail> {
  return request<ResearchSessionDetail>(`/research/sessions/${id}`, {
    fetchImpl,
    method: HttpMethod.GET
  });
}

export async function createResearchSession(payload: ResearchSessionCreatePayload, fetchImpl?: FetchLike): Promise<ResearchSessionDetail> {
  return request<ResearchSessionDetail>(`/research/sessions`, {
    fetchImpl,
    method: HttpMethod.POST,
    body: JSON.stringify(payload)
  });
}

export async function runResearchFeatures(
  sessionId: number,
  featureIds?: number[],
  paperIds?: number[],
  fetchImpl?: FetchLike
): Promise<ResearchFeature[]> {
  const body: Record<string, unknown> = {};
  if (featureIds && featureIds.length > 0) {
    body.feature_ids = featureIds;
  }
  if (paperIds && paperIds.length > 0) {
    body.paper_ids = paperIds;
  }
  const response = await request<{ features: ResearchFeature[] }>(`/research/sessions/${sessionId}/run`, {
    fetchImpl,
    method: HttpMethod.POST,
    body: JSON.stringify(body)
  });
  return response.features;
}

export async function enqueueAuditJob(ids: number[], fetchImpl?: FetchLike): Promise<JobSummary> {
  return request<JobSummary>(`/jobs/audits`, {
    fetchImpl,
    method: HttpMethod.POST,
    body: JSON.stringify({ ids })
  });
}

export async function enqueueLookupJob(ids: number[], fetchImpl?: FetchLike): Promise<JobSummary> {
  return request<JobSummary>(`/jobs/lookups`, {
    fetchImpl,
    method: HttpMethod.POST,
    body: JSON.stringify({ ids })
  });
}

export async function fetchActiveJobs(fetchImpl?: FetchLike): Promise<JobSummary[]> {
  return request<JobSummary[]>(`/jobs/active`, { fetchImpl, method: HttpMethod.GET });
}

export async function fetchActiveJobItems(fetchImpl?: FetchLike): Promise<JobQueueItem[]> {
  return request<JobQueueItem[]>(`/jobs/active/items`, { fetchImpl, method: HttpMethod.GET });
}

export async function fetchJobHistoryItems(limit = 100, offset = 0, fetchImpl?: FetchLike): Promise<JobHistoryItem[]> {
  return request<JobHistoryItem[]>(`/jobs/history/items?limit=${limit}&offset=${offset}`, { fetchImpl, method: HttpMethod.GET });
}

export async function fetchJobHistory(limit = 50, offset = 0, fetchImpl?: FetchLike): Promise<JobSummary[]> {
  return request<JobSummary[]>(`/jobs/history?limit=${limit}&offset=${offset}`, { fetchImpl, method: HttpMethod.GET });
}

export async function fetchJobDetail(id: number, fetchImpl?: FetchLike): Promise<JobDetail> {
  return request<JobDetail>(`/jobs/${id}`, { fetchImpl, method: HttpMethod.GET });
}

export async function cancelJob(id: number, fetchImpl?: FetchLike): Promise<JobSummary> {
  return request<JobSummary>(`/jobs/${id}/cancel`, { fetchImpl, method: HttpMethod.POST });
}

export async function clearJobQueue(fetchImpl?: FetchLike): Promise<{ canceled_jobs: number; canceled_items: number }> {
  return request<{ canceled_jobs: number; canceled_items: number }>(`/jobs/queue`, { fetchImpl, method: HttpMethod.DELETE });
}

export async function clearJobHistory(fetchImpl?: FetchLike): Promise<{ deleted: number }> {
  return request<{ deleted: number }>(`/jobs/history`, { fetchImpl, method: HttpMethod.DELETE });
}

export async function fetchQueueState(fetchImpl?: FetchLike): Promise<JobQueueState> {
  return request<JobQueueState>(`/jobs/control`, { fetchImpl, method: HttpMethod.GET });
}

export async function updateQueueState(paused: boolean, fetchImpl?: FetchLike): Promise<JobQueueState> {
  return request<JobQueueState>(`/jobs/control`, {
    fetchImpl,
    method: HttpMethod.POST,
    body: JSON.stringify({ paused })
  });
}
