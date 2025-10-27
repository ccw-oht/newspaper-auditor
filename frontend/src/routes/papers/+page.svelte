<script lang="ts">
  /* eslint-env browser */
  import PaperFilters from '$components/PaperFilters.svelte';
  import type { FilterValues } from '$lib/types';
  import PaperTable from '$components/PaperTable.svelte';
  import { runAudit, fetchPaperIds, exportPapers, deletePapers } from '$lib/api';
  import type { PaperListParams, PaperListResponse } from '$lib/types';
  import { goto, invalidateAll } from '$app/navigation';
  import { browser } from '$app/environment';
  import { paperFilterQuery } from '$lib/stores/paperFilters';

  export let data: {
    response: PaperListResponse;
    params: Partial<PaperListParams>;
    query: string;
  };

  $: if (browser) {
    paperFilterQuery.set(data.query);
  }

  let loading = false;
  let selectedIds: Set<number> = new Set();
  let pageSize = Number(data.params.limit ?? 50);
  let progressCurrent = 0;
  let progressTotal = 0;
  let currentSortField: string = 'paper_name';
  let currentSortOrder: 'asc' | 'desc' = 'asc';
  let allSelectedAcross = false;
  let bulkLoading = false;
  let bulkError: string | null = null;
  let exportLoading = false;
  let exportError: string | null = null;
  let deleteLoading = false;
  let deleteError: string | null = null;

  $: currentSortField = (data.params.sort as string | undefined) ?? 'paper_name';
  $: currentSortOrder = (data.params.order as 'asc' | 'desc' | undefined) === 'desc' ? 'desc' : 'asc';

  $: {
    const incomingLimit = Number(data.params.limit ?? 50);
    if (!Number.isNaN(incomingLimit) && incomingLimit > 0 && incomingLimit !== pageSize) {
      pageSize = incomingLimit;
    }
  }

  $: selectedArray = Array.from(selectedIds);
  $: selectedCount = selectedArray.length;
  $: pageIds = data.response.items.map((item) => item.id);
  $: pageSelectionCount = pageIds.filter((id) => selectedIds.has(id)).length;
  $: pageFullySelected = pageIds.length > 0 && pageSelectionCount === pageIds.length;
  $: showSelectAllBanner = pageFullySelected && !allSelectedAcross;
  $: showAllAcrossBanner = allSelectedAcross && selectedCount > 0;

  async function applyFilters(event: CustomEvent<FilterValues>) {
    selectedIds = new Set();
    allSelectedAcross = false;
    bulkError = null;
    exportError = null;
    deleteError = null;
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
   allSelectedAcross = false;
    bulkError = null;
    exportError = null;
    deleteError = null;
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
    allSelectedAcross = false;
    exportError = null;
    deleteError = null;
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
    bulkError = null;
    if (!checked) {
      allSelectedAcross = false;
      exportError = null;
      deleteError = null;
    }
  }

  function handleSelectAll(event: CustomEvent<{ ids: number[]; checked: boolean }>) {
    updateSelection(event.detail.ids, event.detail.checked);
    if (!event.detail.checked) {
      allSelectedAcross = false;
      exportError = null;
      deleteError = null;
    }
  }

  function handleSelectRange(event: CustomEvent<{ ids: number[]; checked: boolean }>) {
    updateSelection(event.detail.ids, event.detail.checked);
    if (!event.detail.checked) {
      allSelectedAcross = false;
      exportError = null;
      deleteError = null;
    }
  }

  async function handleBatchAudit() {
    if (selectedIds.size === 0) {
      return;
    }

    try {
      loading = true;
      progressTotal = selectedArray.length;
      progressCurrent = 0;
      deleteError = null;

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
        allSelectedAcross = false;
        exportError = null;
        deleteError = null;
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

  async function selectEntireResult() {
    if (bulkLoading) return;
    bulkLoading = true;
    bulkError = null;
    exportError = null;
    deleteError = null;
    try {
      const idParams: Partial<PaperListParams> = {
        state: data.params.state,
        city: data.params.city,
        has_pdf: data.params.has_pdf,
        pdf_only: data.params.pdf_only,
        paywall: data.params.paywall,
        notices: data.params.notices,
        responsive: data.params.responsive,
        chain_owner: data.params.chain_owner,
        cms_platform: data.params.cms_platform,
        cms_vendor: data.params.cms_vendor,
        q: data.params.q,
      };

      const result = await fetchPaperIds(idParams);
      selectedIds = new Set(result.ids);
      allSelectedAcross = true;
    } catch (error) {
      bulkError = error instanceof Error ? error.message : 'Failed to select all results.';
      allSelectedAcross = false;
      exportError = null;
      deleteError = null;
    } finally {
      bulkLoading = false;
    }
  }

  function clearSelection() {
    selectedIds = new Set();
    allSelectedAcross = false;
    bulkError = null;
    exportError = null;
    deleteError = null;
  }

  async function handleExport() {
    if (selectedIds.size === 0 || exportLoading) {
      return;
    }
    exportLoading = true;
    exportError = null;
    deleteError = null;
    try {
      const ids = Array.from(selectedIds);
      const blob = await exportPapers(ids);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `papers_export_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error) {
      exportError = error instanceof Error ? error.message : 'Failed to export selection.';
    } finally {
      exportLoading = false;
    }
  }

  async function handleDeleteSelected() {
    if (selectedIds.size === 0 || deleteLoading) {
      return;
    }

    const confirmed = window.confirm(
      `Delete ${selectedIds.size} selected paper${selectedIds.size === 1 ? '' : 's'} and all associated audits?`
    );
    if (!confirmed) {
      return;
    }

    deleteLoading = true;
    deleteError = null;
    try {
      const ids = Array.from(selectedIds);
      await deletePapers(ids);
      selectedIds = new Set();
      allSelectedAcross = false;
      bulkError = null;
      exportError = null;
      await invalidateAll();
    } catch (error) {
      console.error(error);
      deleteError = error instanceof Error ? error.message : 'Failed to delete selected papers.';
    } finally {
      deleteLoading = false;
    }
  }
</script>

<div class="page">
  <section>
    <h2>Papers</h2>
    <p class="subtitle">Filter newspapers, review audit status, and trigger updates.</p>
  </section>

  <PaperFilters
    values={data.params}
    options={data.response.options}
    on:filter={applyFilters}
    on:reset={resetFilters}
  />

  {#if showSelectAllBanner}
    <div class="bulk-banner">
      <span>All {pageIds.length} items on this page are selected.</span>
      {#if data.response.total > pageIds.length}
        <button type="button" on:click={selectEntireResult} disabled={bulkLoading}>
          {bulkLoading ? 'Selecting…' : `Select all ${data.response.total} items`}
        </button>
      {/if}
    </div>
  {/if}

  {#if showAllAcrossBanner}
    <div class="bulk-banner info">
      <span>All {data.response.total} items are selected.</span>
      <button type="button" on:click={clearSelection}>Clear selection</button>
    </div>
  {/if}

  {#if bulkError}
    <p class="error">{bulkError}</p>
  {/if}

  {#if exportError}
    <p class="error">{exportError}</p>
  {/if}

  {#if deleteError}
    <p class="error">{deleteError}</p>
  {/if}

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
    <button type="button" on:click={handleExport} disabled={selectedCount === 0 || exportLoading}>
      {exportLoading ? 'Exporting…' : 'Export CSV'}
    </button>
    <button
      type="button"
      class="danger"
      on:click={handleDeleteSelected}
      disabled={selectedCount === 0 || deleteLoading}
    >
      {deleteLoading ? 'Deleting…' : 'Delete selected'}
    </button>
  </div>

  <PaperTable
    items={data.response.items}
    total={data.response.total}
    limit={pageSize}
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

.import-link .import-btn {
  padding: 0.55rem 1rem;
  border-radius: 0.5rem;
  background-color: #22c55e;
  color: white;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
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

  .actions button.danger {
    background-color: #dc2626;
  }

  .actions button.danger[disabled] {
    background-color: #dc2626;
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

  .bulk-banner {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    border-radius: 0.5rem;
    background-color: #f3f4ff;
    border: 1px solid #c7d2fe;
    color: #1e3a8a;
  }

  .bulk-banner.info {
    background-color: #ecfdf5;
    border-color: #a7f3d0;
    color: #047857;
  }

  .bulk-banner button {
    padding: 0.45rem 0.75rem;
    border: none;
    border-radius: 0.5rem;
    background-color: #2563eb;
    color: white;
    font-weight: 600;
    cursor: pointer;
  }

  .error {
    color: #b91c1c;
    font-weight: 600;
  }
</style>
