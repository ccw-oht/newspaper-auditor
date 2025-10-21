import type {
  PaperListParams,
  PaperListResponse,
  PaperDetail,
  PaperUpdatePayload,
  AuditOut,
  ImportPreviewResponse,
  ImportCommitRequest,
  ImportCommitResult,
  PaperIdList
} from '$lib/types';
import { API_BASE_URL } from './config';

type FetchLike = typeof fetch;

enum HttpMethod {
  GET = 'GET',
  POST = 'POST',
  PATCH = 'PATCH'
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
