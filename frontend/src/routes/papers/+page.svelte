<script lang="ts">
  /* eslint-env browser */
  import PaperFilters from '$components/PaperFilters.svelte';
  import type { FilterValues } from '$lib/types';
  import PaperTable from '$components/PaperTable.svelte';
  import { enqueueAuditJob, enqueueLookupJob, fetchActiveJobs, fetchPaperIds, exportPapers, deletePapers, createResearchSession, fetchPapers } from '$lib/api';
  import type { PaperListParams, PaperListResponse } from '$lib/types';
  import { goto, invalidateAll } from '$app/navigation';
  import { browser } from '$app/environment';
  import { paperFilterQuery } from '$lib/stores/paperFilters';
  import { onDestroy, onMount } from 'svelte';

  export let data: {
    response: PaperListResponse;
    params: Partial<PaperListParams>;
    query: string;
  };

  $: if (browser) {
    paperFilterQuery.set(data.query);
  }

  let loading = false;
  let lookupLoading = false;
  let lookupError: string | null = null;
  let selectedIds: Set<number> = new Set();
  let pageSize = Number(data.params.limit ?? 50);
  let response = data.response;
  let lastDataResponse = data.response;
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let pollInFlight = false;
  let queueActive = false;
  let currentSortField: string = 'paper_name';
  let currentSortOrder: 'asc' | 'desc' = 'asc';
  let allSelectedAcross = false;
  let bulkLoading = false;
  let bulkError: string | null = null;
  let exportLoading = false;
  let exportError: string | null = null;
  let deleteLoading = false;
  let deleteError: string | null = null;
  let toastMessage: string | null = null;
  let toastTimer: ReturnType<typeof setTimeout> | null = null;
  let researchFormOpen = false;
  let researchLoading = false;
  let researchError: string | null = null;
  let researchName = '';
  let researchDescription = '';
  type FeatureDraft = {
    id: number;
    name: string;
    keywords: string;
    desired_examples: number;
  };
  let featureDrafts: FeatureDraft[] = [
    { id: 1, name: 'City Council', keywords: 'city council, public notice', desired_examples: 5 }
  ];
  let nextFeatureDraftId = 2;

  $: currentSortField = (data.params.sort as string | undefined) ?? 'paper_name';
  $: currentSortOrder = (data.params.order as 'asc' | 'desc' | undefined) === 'desc' ? 'desc' : 'asc';

  $: {
    const incomingLimit = Number(data.params.limit ?? 50);
    if (!Number.isNaN(incomingLimit) && incomingLimit > 0 && incomingLimit !== pageSize) {
      pageSize = incomingLimit;
    }
  }

  $: if (data.response !== lastDataResponse) {
    response = data.response;
    lastDataResponse = data.response;
  }
  $: selectedArray = Array.from(selectedIds);
  $: selectedCount = selectedArray.length;
  $: pageIds = response.items.map((item) => item.id);
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

  async function handleAudit(event: CustomEvent<{ id: number; name: string }>) {
    try {
      loading = true;
      await enqueueAuditJob([event.detail.id]);
      showToast(`Queued audit for ${event.detail.name}.`);
    } catch (error) {
      console.error(error);
      window.alert('Failed to re-run audit. Check console for details.');
    } finally {
      loading = false;
    }
  }

  async function handleLookup(event: CustomEvent<{ id: number; name: string }>) {
    try {
      lookupLoading = true;
      await enqueueLookupJob([event.detail.id]);
      showToast(`Queued lookup for ${event.detail.name}.`);
    } catch (error) {
      console.error(error);
      window.alert('Failed to run lookup. Check console for details.');
    } finally {
      lookupLoading = false;
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
      deleteError = null;
      await enqueueAuditJob(selectedArray);
      showToast(`Queued ${selectedArray.length} audit${selectedArray.length === 1 ? '' : 's'}.`);
      selectedIds = new Set();
      allSelectedAcross = false;
      exportError = null;
      deleteError = null;
    } catch (error) {
      console.error(error);
      window.alert('Failed to run batch audit. Check console for details.');
    } finally {
      loading = false;
    }
  }

  async function handleBatchLookup() {
    if (selectedIds.size === 0) {
      return;
    }

    try {
      lookupLoading = true;
      const batchIds = [...selectedArray];
      lookupError = null;
      await enqueueLookupJob(batchIds);
      showToast(`Queued ${batchIds.length} lookup${batchIds.length === 1 ? '' : 's'}.`);
      selectedIds = new Set();
      allSelectedAcross = false;
      exportError = null;
      deleteError = null;
    } catch (error) {
      console.error(error);
      lookupError = error instanceof Error ? error.message : 'Failed to run batch lookup.';
    } finally {
      lookupLoading = false;
    }
  }

  async function refreshList() {
    if (!browser) return;
    if (document.visibilityState !== 'visible') return;
    try {
      const refreshed = await fetchPapers(data.params);
      response = refreshed;
    } catch (error) {
      console.error(error);
    }
  }

  async function pollUpdates() {
    if (!browser || pollInFlight) return;
    if (document.visibilityState !== 'visible') return;
    pollInFlight = true;
    try {
      const jobs = await fetchActiveJobs();
      const nextActive = jobs.length > 0;
      if (nextActive || queueActive) {
        await refreshList();
      }
      queueActive = nextActive;
    } catch (error) {
      console.error(error);
    } finally {
      pollInFlight = false;
    }
  }

  onMount(() => {
    pollTimer = setInterval(pollUpdates, 3000);
  });

  onDestroy(() => {
    if (pollTimer) {
      clearInterval(pollTimer);
    }
  });

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

  function showToast(message: string) {
    toastMessage = message;
    if (toastTimer) {
      clearTimeout(toastTimer);
    }
    toastTimer = setTimeout(() => {
      toastMessage = null;
      toastTimer = null;
    }, 3000);
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

  function addFeatureDraft() {
    featureDrafts = [
      ...featureDrafts,
      {
        id: nextFeatureDraftId++,
        name: '',
        keywords: '',
        desired_examples: 5
      }
    ];
  }

  function removeFeatureDraft(id: number) {
    featureDrafts = featureDrafts.filter((draft) => draft.id !== id);
  }

  function updateFeatureDraft(id: number, field: keyof FeatureDraft, value: string | number) {
    featureDrafts = featureDrafts.map((draft) => {
      if (draft.id !== id) return draft;
      return { ...draft, [field]: value };
    });
  }

  async function handleCreateResearchSession() {
    if (selectedIds.size === 0) {
      researchError = 'Select at least one paper before saving a research session.';
      return;
    }

    const preparedFeatures = featureDrafts
      .map((draft) => {
        const keywords = draft.keywords
          .split(',')
          .map((keyword) => keyword.trim())
          .filter(Boolean);
        return {
          name: draft.name.trim(),
          keywords,
          desired_examples: Number(draft.desired_examples) || 5
        };
      })
      .filter((feature) => feature.name && feature.keywords.length > 0);

    if (preparedFeatures.length === 0) {
      researchError = 'Add at least one feature with keywords.';
      return;
    }

    researchLoading = true;
    researchError = null;
    try {
      const payload = {
        name: (researchName || `Research Session (${new Date().toLocaleDateString()})`).trim(),
        description: researchDescription || undefined,
        paper_ids: Array.from(selectedIds),
        filter_params: data.params,
        query_string: data.query,
        features: preparedFeatures
      };
      const session = await createResearchSession(payload);
      await goto(`/research/${session.id}`);
    } catch (error) {
      researchError = error instanceof Error ? error.message : 'Failed to save research session.';
    } finally {
      researchLoading = false;
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
    options={response.options}
    on:filter={applyFilters}
    on:reset={resetFilters}
  />

  {#if showSelectAllBanner}
    <div class="bulk-banner">
      <span>All {pageIds.length} items on this page are selected.</span>
      {#if response.total > pageIds.length}
        <button type="button" on:click={selectEntireResult} disabled={bulkLoading}>
          {bulkLoading ? 'Selecting…' : `Select all ${response.total} items`}
        </button>
      {/if}
    </div>
  {/if}

  {#if showAllAcrossBanner}
    <div class="bulk-banner info">
      <span>All {response.total} items are selected.</span>
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

  {#if lookupError}
    <p class="error">{lookupError}</p>
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
    <button
      type="button"
      on:click={() => {
        researchFormOpen = !researchFormOpen;
        researchError = null;
      }}
      disabled={selectedCount === 0}
    >
      {researchFormOpen ? 'Close research form' : 'Save as Research Session'}
    </button>
    <button type="button" on:click={handleBatchAudit} disabled={selectedCount === 0 || loading}>
      {loading ? 'Queueing…' : 'Queue audit'}
    </button>
    <button type="button" on:click={handleBatchLookup} disabled={selectedCount === 0 || lookupLoading}>
      {lookupLoading ? 'Queueing…' : 'Queue lookup'}
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

  {#if researchFormOpen}
    <section class="research-form">
      <h3>Create research session</h3>
      <p class="subtitle">
        Save the current filters and selection, then define feature keyword sets to audit across all selected papers.
      </p>

      <label>
        Session name
        <input type="text" bind:value={researchName} placeholder="City Council Scan – Midwest" />
      </label>

      <label>
        Description
        <textarea bind:value={researchDescription} placeholder="Optional notes about the research goal."></textarea>
      </label>

      <div class="feature-list">
        <h4>Features</h4>
        {#each featureDrafts as feature}
          <div class="feature-row">
            <div class="field">
              <label>
                Feature name
                <input
                  type="text"
                  value={feature.name}
                  placeholder="City Council coverage"
                  on:input={(event) => updateFeatureDraft(feature.id, 'name', event.currentTarget?.value ?? '')}
                />
              </label>
            </div>
            <div class="field">
              <label>
                Keywords (comma-separated)
                <input
                  type="text"
                  value={feature.keywords}
                  placeholder="city council, council meeting"
                  on:input={(event) => updateFeatureDraft(feature.id, 'keywords', event.currentTarget?.value ?? '')}
                />
              </label>
            </div>
            <div class="field small">
              <label>
                Examples
                <input
                  type="number"
                  min="1"
                  max="50"
                  value={feature.desired_examples}
                  on:input={(event) => updateFeatureDraft(feature.id, 'desired_examples', Number(event.currentTarget?.value ?? 5))}
                />
              </label>
            </div>
            <button type="button" class="secondary" on:click={() => removeFeatureDraft(feature.id)} disabled={featureDrafts.length === 1}>
              Remove
            </button>
          </div>
        {/each}
        <button type="button" class="secondary" on:click={addFeatureDraft}>
          Add feature
        </button>
      </div>

      {#if researchError}
        <p class="error">{researchError}</p>
      {/if}

      <div class="form-actions">
        <button type="button" on:click={handleCreateResearchSession} disabled={researchLoading || selectedCount === 0}>
          {researchLoading ? 'Saving session…' : `Save ${selectedCount} paper${selectedCount === 1 ? '' : 's'}`}
        </button>
      </div>
    </section>
  {/if}

  <PaperTable
    items={response.items}
    total={response.total}
    limit={pageSize}
    offset={Number(data.params.offset ?? 0)}
    on:audit={handleAudit}
    on:lookup={handleLookup}
    on:paginate={changePage}
    on:select={handleSelect}
    on:selectRange={handleSelectRange}
    on:selectAll={handleSelectAll}
    on:sort={handleSort}
    selected={selectedArray}
    sortField={currentSortField}
    sortOrder={currentSortOrder}
    loading={loading || lookupLoading}
  />

  {#if toastMessage}
    <div class="toast" role="status" aria-live="polite">{toastMessage}</div>
  {/if}
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
    flex-wrap: wrap;
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

  .toast {
    position: fixed;
    bottom: 1.5rem;
    left: 50%;
    transform: translateX(-50%);
    background: #111827;
    color: white;
    padding: 0.75rem 1.25rem;
    border-radius: 999px;
    font-weight: 600;
    box-shadow: 0 10px 20px rgba(15, 23, 42, 0.25);
    z-index: 40;
  }

  @media (max-width: 640px) {
    .toast {
      left: 1rem;
      right: 1rem;
      transform: none;
      text-align: center;
    }
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

  .error-details {
    margin: 0.5rem 0 0;
    color: #7f1d1d;
    font-size: 0.9rem;
  }

  .error-details summary {
    cursor: pointer;
    font-weight: 600;
  }

  .research-form {
    margin-top: 1.5rem;
    background: white;
    border-radius: 0.75rem;
    border: 1px solid #e5e7eb;
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .research-form label {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    font-weight: 600;
    color: #374151;
  }

  .research-form input,
  .research-form textarea {
    border: 1px solid #d1d5db;
    border-radius: 0.5rem;
    padding: 0.5rem 0.65rem;
    font-size: 1rem;
  }

  .research-form textarea {
    min-height: 80px;
    resize: vertical;
  }

  .feature-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .feature-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    border: 1px solid #e5e7eb;
    border-radius: 0.75rem;
    padding: 0.75rem;
    align-items: flex-end;
  }

  .feature-row .field {
    flex: 1;
    min-width: 200px;
  }

  .feature-row .field.small {
    max-width: 120px;
  }

  .research-form .secondary {
    background: #f3f4f6;
    color: #111827;
    border: 1px solid #e5e7eb;
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
  }
</style>
