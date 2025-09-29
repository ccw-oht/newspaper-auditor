<script lang="ts">
  /* eslint-env browser */
  import PaperFilters from '$components/PaperFilters.svelte';
  import type { FilterValues } from '$lib/types';
  import PaperTable from '$components/PaperTable.svelte';
  import { runAudit, runAuditBatch } from '$lib/api';
  import type { PaperListParams, PaperListResponse } from '$lib/types';
  import { goto, invalidateAll } from '$app/navigation';

  export let data: {
    response: PaperListResponse;
    params: Partial<PaperListParams>;
    query: string;
  };

  let loading = false;
  let selectedIds: Set<number> = new Set();
  let pageSize = Number(data.params.limit ?? 50);

  $: selectedArray = Array.from(selectedIds);
  $: selectedCount = selectedArray.length;

  async function applyFilters(event: CustomEvent<FilterValues>) {
    selectedIds = new Set();
    const search = new URLSearchParams();
    const { detail } = event;
    Object.entries(detail).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') return;
      search.set(key, String(value));
    });
    await goto(`/papers${search.toString() ? `?${search}` : ''}`);
  }

  async function resetFilters() {
    selectedIds = new Set();
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

  function handleSelect(event: CustomEvent<{ id: number; checked: boolean }>) {
    const next = new Set(selectedIds);
    if (event.detail.checked) {
      next.add(event.detail.id);
    } else {
      next.delete(event.detail.id);
    }
    selectedIds = next;
  }

  function handleSelectAll(event: CustomEvent<{ ids: number[]; checked: boolean }>) {
    const next = new Set(selectedIds);
    event.detail.ids.forEach((id) => {
      if (event.detail.checked) {
        next.add(id);
      } else {
        next.delete(id);
      }
    });
    selectedIds = next;
  }

  async function handleBatchAudit() {
    if (selectedIds.size === 0) {
      return;
    }

    try {
      loading = true;
      await runAuditBatch(selectedArray);
      await invalidateAll();
      selectedIds = new Set();
    } catch (error) {
      console.error(error);
      window.alert('Failed to run batch audit. Check console for details.');
    } finally {
      loading = false;
    }
  }

  async function handlePageSizeChange(event: Event) {
    const target = event.currentTarget as HTMLSelectElement | null;
    if (!target) return;
    const nextSize = Number(target.value) || 50;
    pageSize = nextSize;
    const params = new URLSearchParams(data.query);
    params.set('limit', String(nextSize));
    params.set('offset', '0');
    await goto(`/papers?${params.toString()}`);
  }
</script>

<div class="page">
  <section>
    <h2>Papers</h2>
    <p class="subtitle">Filter newspapers, review audit status, and trigger updates.</p>
  </section>

  <PaperFilters values={data.params} on:filter={applyFilters} on:reset={resetFilters} />

  <div class="actions">
    <label class="page-size">
      Entries per page
      <select on:change={handlePageSizeChange} bind:value={pageSize}>
        <option value={25}>25</option>
        <option value={50}>50</option>
        <option value={100}>100</option>
      </select>
    </label>
    <span>{selectedCount} selected</span>
    <button type="button" on:click={handleBatchAudit} disabled={selectedCount === 0 || loading}>
      {loading ? 'Running…' : 'Re-run selected'}
    </button>
  </div>

  <PaperTable
    items={data.response.items}
    total={data.response.total}
    limit={Number(data.params.limit ?? 50)}
    offset={Number(data.params.offset ?? 0)}
    on:audit={handleAudit}
    on:paginate={changePage}
    on:select={handleSelect}
    on:selectAll={handleSelectAll}
    selected={selectedArray}
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

  .actions {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 1rem;
  }

  .actions span {
    color: #4b5563;
  }

  .actions button {
    padding: 0.55rem 1rem;
    border: none;
    border-radius: 0.5rem;
    background-color: #2563eb;
    color: white;
    font-weight: 600;
    cursor: pointer;
  }

  .actions button[disabled] {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .page-size {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: #4b5563;
  }

  .page-size select {
    padding: 0.35rem 0.5rem;
    border-radius: 0.5rem;
    border: 1px solid #d1d5db;
  }
</style>
