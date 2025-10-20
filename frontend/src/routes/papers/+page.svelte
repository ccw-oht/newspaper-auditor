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
  let selectedIds: Set<number> = new Set();
  let pageSize = Number(data.params.limit ?? 50);
  let progressCurrent = 0;
  let progressTotal = 0;
  let currentSortField: string = 'paper_name';
  let currentSortOrder: 'asc' | 'desc' = 'asc';

  $: currentSortField = (data.params.sort as string | undefined) ?? 'paper_name';
  $: currentSortOrder = (data.params.order as 'asc' | 'desc' | undefined) === 'desc' ? 'desc' : 'asc';

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
    if (data.params.sort) {
      search.set('sort', String(data.params.sort));
    }
    if (data.params.order) {
      search.set('order', String(data.params.order));
    }
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

  function updateSelection(ids: number[], checked: boolean) {
    const next = new Set(selectedIds);
    ids.forEach((id) => {
      if (checked) {
        next.add(id);
      } else {
        next.delete(id);
      }
    });
    selectedIds = next;
  }

  function handleSelectAll(event: CustomEvent<{ ids: number[]; checked: boolean }>) {
    updateSelection(event.detail.ids, event.detail.checked);
  }

  function handleSelectRange(event: CustomEvent<{ ids: number[]; checked: boolean }>) {
    updateSelection(event.detail.ids, event.detail.checked);
  }

  async function handleBatchAudit() {
    if (selectedIds.size === 0) {
      return;
    }

    try {
      loading = true;
      progressTotal = selectedArray.length;
      progressCurrent = 0;

      for (const id of selectedArray) {
        try {
          await runAudit(id);
        } catch (error) {
          console.error(error);
          window.alert(`Failed to re-run audit for paper ${id}. Continuing with remaining items.`);
        }

        progressCurrent += 1;
        await invalidateAll();

        const next = new Set(selectedIds);
        next.delete(id);
        selectedIds = next;
      }
    } catch (error) {
      console.error(error);
      window.alert('Failed to run batch audit. Check console for details.');
    } finally {
      loading = false;
      progressCurrent = 0;
      progressTotal = 0;
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

  async function handleSort(event: CustomEvent<{ field: string; order: 'asc' | 'desc' }>) {
    const params = new URLSearchParams(data.query);
    params.set('sort', event.detail.field);
    params.set('order', event.detail.order);
    params.set('offset', '0');
    await goto(`/papers?${params.toString()}`);
  }
</script>

<div class="page">
  <section>
    <h2>Papers</h2>
    <p class="subtitle">Filter newspapers, review audit status, and trigger updates.</p>
  </section>

  <div class="import-link">
    <button type="button" on:click={() => goto('/imports')}>Import CSV</button>
  </div>

  <PaperFilters
    values={data.params}
    options={data.response.options}
    on:filter={applyFilters}
    on:reset={resetFilters}
  />

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
      {loading
        ? `Running…${progressTotal ? ` (${progressCurrent}/${progressTotal})` : ''}`
        : 'Re-run selected'}
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
    on:selectRange={handleSelectRange}
    on:selectAll={handleSelectAll}
    on:sort={handleSort}
    selected={selectedArray}
    sortField={currentSortField}
    sortOrder={currentSortOrder}
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

.import-link {
  display: flex;
  justify-content: flex-end;
}

.import-link button {
  padding: 0.55rem 1rem;
  border: none;
  border-radius: 0.5rem;
  background-color: #22c55e;
  color: white;
  font-weight: 600;
  cursor: pointer;
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
