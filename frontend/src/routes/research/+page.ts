import { fetchResearchSessions } from '$lib/api';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
  const response = await fetchResearchSessions(fetch);
  return {
    sessions: response.items
  };
};






