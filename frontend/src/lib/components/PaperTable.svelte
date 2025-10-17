<script lang="ts">
  /* eslint-env browser */
  import type { PaperSummary } from '$lib/types';
  import { createEventDispatcher } from 'svelte';
  import { formatRelativeTime } from '$lib/formatters';

  export let items: PaperSummary[] = [];
  export let total = 0;
  export let limit = 50;
  export let offset = 0;
  export let loading = false;
  export let selected: number[] = [];

  const dispatch = createEventDispatcher<{
    audit: { id: number };
    paginate: { offset: number };
    select: { id: number; checked: boolean };
    selectRange: { ids: number[]; checked: boolean };
    selectAll: { ids: number[]; checked: boolean };
  }>();

  const totalPages = Math.max(1, Math.ceil(total / limit));
  const currentPage = Math.floor(offset / limit) + 1;

  let selectAllCheckbox: HTMLInputElement | null = null;
  let selectedSet = new Set<number>();
  let lastToggledIndex: number | null = null;
  let itemsFingerprint: string | null = null;

  $: selectedSet = new Set(selected);
  $: allVisibleSelected = items.length > 0 && items.every((item) => selectedSet.has(item.id));
  $: someSelected = items.some((item) => selectedSet.has(item.id));
  $: {
    if (selectAllCheckbox) {
      selectAllCheckbox.indeterminate = someSelected && !allVisibleSelected;
    }
  }

  function goToPage(page: number) {
    const target = Math.max(1, Math.min(totalPages, page));
    dispatch('paginate', { offset: (target - 1) * limit });
  }

  $: if (lastToggledIndex !== null && (lastToggledIndex < 0 || lastToggledIndex >= items.length)) {
    lastToggledIndex = null;
  }

  $: {
    const currentFingerprint = items.map((item) => item.id).join(',');
    if (currentFingerprint !== itemsFingerprint) {
      itemsFingerprint = currentFingerprint;
      lastToggledIndex = null;
    }
  }

  function handleItemClick(event: MouseEvent, id: number, index: number) {
    const target = event.currentTarget as HTMLInputElement | null;
    const checked = target?.checked ?? false;

    if (event.shiftKey && lastToggledIndex !== null) {
      const start = Math.min(lastToggledIndex, index);
      const end = Math.max(lastToggledIndex, index);
      const rangeIds = items.slice(start, end + 1).map((item) => item.id);
      dispatch('selectRange', { ids: rangeIds, checked });
    } else {
      dispatch('select', { id, checked });
    }

    lastToggledIndex = index;
  }

  function onSelectAll(checked: boolean) {
    dispatch('selectAll', { ids: items.map((item) => item.id), checked });
  }

  function extractChecked(event: Event): boolean {
    const target = event.currentTarget as HTMLInputElement | null;
    return target?.checked ?? false;
  }
</script>

<div class="table-wrapper">
  <table>
    <thead>
      <tr>
        <th class="select">
          <input
            type="checkbox"
            bind:this={selectAllCheckbox}
            checked={allVisibleSelected && items.length > 0}
            on:change={(event) => onSelectAll(extractChecked(event))}
            aria-label="Select visible papers"
          />
        </th>
        <th>Paper</th>
        <th>City</th>
        <th>State</th>
        <th>Website</th>
        <th>Has PDF</th>
        <th>Paywall</th>
        <th>Notices</th>
        <th>Responsive</th>
        <th>Chain</th>
        <th>CMS</th>
        <th>Last Audit</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#if items.length === 0}
        <tr>
          <td colspan="13" class="empty">No results</td>
        </tr>
      {:else}
        {#each items as item, index}
          <tr>
            <td class="select">
              <input
                type="checkbox"
                checked={selectedSet.has(item.id)}
                on:click={(event) => handleItemClick(event, item.id, index)}
                aria-label={`Select ${item.paper_name ?? 'paper'}`}
              />
            </td>
            <td>
              <a class="paper-link" href={`/papers/${item.id}`}>{item.paper_name ?? '—'}</a>
            </td>
            <td>{item.city ?? '—'}</td>
            <td>{item.state ?? '—'}</td>
            <td>
              {#if item.website_url}
                <a class="external" href={item.website_url} target="_blank" rel="noreferrer">
                  Visit
                </a>
              {:else}
                —
              {/if}
            </td>
            <td>{item.latest_audit?.has_pdf ?? '—'}</td>
            <td>{item.latest_audit?.paywall ?? '—'}</td>
            <td>{item.latest_audit?.notices ?? '—'}</td>
            <td>{item.latest_audit?.responsive ?? '—'}</td>
            <td>{item.latest_audit?.chain_owner ?? '—'}</td>
            <td>{item.latest_audit?.cms_vendor ?? '—'}</td>
            <td>{item.latest_audit?.timestamp ? formatRelativeTime(item.latest_audit.timestamp) : 'Never'}</td>
            <td>
              <button type="button" disabled={loading} on:click={() => dispatch('audit', { id: item.id })}>
                Re-run
              </button>
            </td>
          </tr>
        {/each}
      {/if}
    </tbody>
  </table>

  <div class="pagination">
    <button type="button" on:click={() => goToPage(currentPage - 1)} disabled={currentPage === 1 || loading}>
      Previous
    </button>
    <span>
      Page {currentPage} of {totalPages}
    </span>
    <button
      type="button"
      on:click={() => goToPage(currentPage + 1)}
      disabled={currentPage === totalPages || loading}
    >
      Next
    </button>
  </div>
</div>

<style>
  .table-wrapper {
    background: white;
    border-radius: 0.75rem;
    border: 1px solid #e5e7eb;
    overflow: hidden;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  thead {
    background-color: #f9fafb;
  }

  th,
  td {
    text-align: left;
    padding: 0.75rem;
    border-bottom: 1px solid #e5e7eb;
    font-size: 0.9rem;
  }

  th.select,
  td.select {
    width: 3rem;
    text-align: center;
  }

  a.paper-link {
    color: #111827;
    font-weight: 600;
    text-decoration: none;
  }

  a.external {
    color: #2563eb;
  }

  button {
    padding: 0.35rem 0.75rem;
    border-radius: 0.5rem;
    border: none;
    background-color: #2563eb;
    color: white;
    font-weight: 600;
    cursor: pointer;
  }

  button[disabled] {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .empty {
    text-align: center;
    padding: 2rem;
    color: #6b7280;
  }

  .pagination {
    padding: 1rem;
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
    align-items: center;
  }

  .pagination span {
    color: #4b5563;
  }
</style>
