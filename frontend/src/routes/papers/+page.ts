import { fetchPapers } from '$lib/api';
import type { PaperListParams } from '$lib/types';
import type { PageLoad } from './$types';

function parseParams(searchParams: URLSearchParams): Partial<PaperListParams> {
  const params: Partial<PaperListParams> = {};
  const anyParams = params as Record<string, unknown>;
  for (const [key, value] of searchParams.entries()) {
    if (!value) continue;
    if (key === 'limit' || key === 'offset') {
      params[key] = Number(value);
      continue;
    }
    anyParams[key] = value;
  }
  return params;
}

export const load: PageLoad = async ({ fetch, url }) => {
  const params = parseParams(url.searchParams);
  const response = await fetchPapers(params, fetch);
  return {
    response,
    params,
    query: url.searchParams.toString()
  };
};
