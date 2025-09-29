<script lang="ts">
  /* eslint-env browser */
  import PaperFilters from '$components/PaperFilters.svelte';
  import type { FilterValues } from '$lib/types';
  import PaperTable from '$components/PaperTable.svelte';
  import { runAudit } from '$lib/api';
  import type { PaperListParams, PaperListResponse } from '$lib/types';
  import { goto, invalidateAll } from '$app/navigation';

  export let data: {
    response: PaperListResponse;
    params: Partial<PaperListParams>;
    query: string;
  };

  let loading = false;

  async function applyFilters(event: CustomEvent<FilterValues>) {
    const search = new URLSearchParams();
    const { detail } = event;
    Object.entries(detail).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') return;
      search.set(key, String(value));
    });
    await goto(`/papers${search.toString() ? `?${search}` : ''}`);
  }

  async function resetFilters() {
    await goto('/papers');
  }

  async function handleAudit(event: CustomEvent<{ id: number }>) {
    try {
      loading = true;
      await runAudit(event.detail.id);
      await invalidateAll();
    } catch (error) {
      console.error(error);
      window.alert('Failed to re-run audit. Check console for details.');
    } finally {
      loading = false;
    }
  }

  async function changePage(event: CustomEvent<{ offset: number }>) {
    const params = new URLSearchParams(data.query);
    params.set('offset', String(event.detail.offset));
    if (!params.has('limit') && data.params.limit) {
      params.set('limit', String(data.params.limit));
    }
    await goto(`/papers?${params.toString()}`);
  }
</script>

<div class="page">
  <section>
    <h2>Papers</h2>
    <p class="subtitle">Filter newspapers, review audit status, and trigger updates.</p>
  </section>

  <PaperFilters values={data.params} on:filter={applyFilters} on:reset={resetFilters} />

  <PaperTable
    items={data.response.items}
    total={data.response.total}
    limit={Number(data.params.limit ?? 50)}
    offset={Number(data.params.offset ?? 0)}
    on:audit={handleAudit}
    on:paginate={changePage}
    {loading}
  />
</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  h2 {
    margin: 0;
    font-size: 1.75rem;
  }

  .subtitle {
    color: #6b7280;
    margin-top: 0.25rem;
  }
</style>
