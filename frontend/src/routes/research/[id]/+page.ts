import { fetchResearchSessionDetail } from '$lib/api';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
  const sessionId = Number(params.id);
  const session = await fetchResearchSessionDetail(sessionId, fetch);
  return { session };
};






