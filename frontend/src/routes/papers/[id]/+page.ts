import { fetchPaperDetail } from '$lib/api';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
  const id = Number(params.id);
  if (Number.isNaN(id)) {
    throw new Error('Invalid paper id');
  }

  const detail = await fetchPaperDetail(id, fetch);
  return { detail };
};
