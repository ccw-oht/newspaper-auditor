<script lang="ts">
  /* eslint-env browser */
import type { AuditSummary, PaperSummary } from '$lib/types';
import { createEventDispatcher } from 'svelte';
import { formatRelativeTime } from '$lib/formatters';

export let items: PaperSummary[] = [];
export let total = 0;
export let limit = 50;
export let offset = 0;
export let loading = false;
export let selected: number[] = [];
export let sortField: string = 'paper_name';
export let sortOrder: 'asc' | 'desc' = 'asc';

let safeLimit = limit || 1;
let totalPages = 1;
let currentPage = 1;
let startEntry = 0;
let endEntry = 0;

const dispatch = createEventDispatcher<{
    audit: { id: number };
    paginate: { offset: number };
    select: { id: number; checked: boolean };
    selectRange: { ids: number[]; checked: boolean };
    selectAll: { ids: number[]; checked: boolean };
    sort: { field: string; order: 'asc' | 'desc' };
  }>();

$: safeLimit = limit > 0 ? limit : 1;
$: totalPages = Math.max(1, Math.ceil(total / safeLimit));
$: currentPage = Math.floor(offset / safeLimit) + 1;
$: startEntry = total === 0 ? 0 : Math.min(offset + 1, total);
$: endEntry = total === 0 ? 0 : Math.min(offset + safeLimit, total);

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
  dispatch('paginate', { offset: (target - 1) * safeLimit });
}

function goToFirst() {
  dispatch('paginate', { offset: 0 });
}

function goToLast() {
  const lastPage = totalPages;
  dispatch('paginate', { offset: (lastPage - 1) * safeLimit });
}

  function toggleSort(field: string) {
    const nextOrder: 'asc' | 'desc' = field === sortField ? (sortOrder === 'asc' ? 'desc' : 'asc') : 'asc';
    dispatch('sort', { field, order: nextOrder });
  }

  function columnAriaSort(field: string): 'ascending' | 'descending' | 'none' {
    if (field !== sortField) return 'none';
    return sortOrder === 'asc' ? 'ascending' : 'descending';
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

  function normalizeWebsiteUrl(url: string | null | undefined): string | null {
    if (!url) return null;
    const trimmed = url.trim();
    if (!trimmed) return null;

    if (/^[a-zA-Z][a-zA-Z0-9+\-.]*:/.test(trimmed)) {
      return trimmed;
    }

    return `https://${trimmed.replace(/^\/+/, '')}`;
  }

  function statusClass(field: string, value: string | null | undefined): string {
    const normalized = (value ?? '').toString().trim().toLowerCase();
    if (!normalized || normalized === '—') return 'status neutral';
    if (normalized.startsWith('manual')) return 'status review';
    const invert = field === 'pdf_only';
    if (normalized.startsWith('yes')) {
      return invert ? 'status no' : 'status yes';
    }
    if (normalized.startsWith('no')) {
      return invert ? 'status yes' : 'status no';
    }
    return 'status neutral';
  }

  function isOverridden(summary: AuditSummary | null | undefined, field: string): boolean {
    const overrides = summary?.overrides as Record<string, unknown> | undefined;
    if (!overrides) return false;
    return overrides[field] !== undefined;
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
        <th
          class="sortable"
          aria-sort={columnAriaSort('paper_name')}
        >
          <button type="button" on:click={() => toggleSort('paper_name')}>
            Paper
            {#if sortField === 'paper_name'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th
          class="sortable"
          aria-sort={columnAriaSort('city')}
        >
          <button type="button" on:click={() => toggleSort('city')}>
            City
            {#if sortField === 'city'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th
          class="sortable"
          aria-sort={columnAriaSort('state')}
        >
          <button type="button" on:click={() => toggleSort('state')}>
            State
            {#if sortField === 'state'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th
          class="sortable"
          aria-sort={columnAriaSort('website_url')}
        >
          <button type="button" on:click={() => toggleSort('website_url')}>
            Website
            {#if sortField === 'website_url'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th
          class="sortable"
          aria-sort={columnAriaSort('has_pdf')}
        >
          <button type="button" on:click={() => toggleSort('has_pdf')}>
            Has PDF
            {#if sortField === 'has_pdf'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th
          class="sortable"
          aria-sort={columnAriaSort('pdf_only')}
        >
          <button type="button" on:click={() => toggleSort('pdf_only')}>
            PDF Only
            {#if sortField === 'pdf_only'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th
          class="sortable"
          aria-sort={columnAriaSort('paywall')}
        >
          <button type="button" on:click={() => toggleSort('paywall')}>
            Paywall
            {#if sortField === 'paywall'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th
          class="sortable"
          aria-sort={columnAriaSort('notices')}
        >
          <button type="button" on:click={() => toggleSort('notices')}>
            Notices
            {#if sortField === 'notices'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th
          class="sortable"
          aria-sort={columnAriaSort('responsive')}
        >
          <button type="button" on:click={() => toggleSort('responsive')}>
            Responsive
            {#if sortField === 'responsive'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th
          class="sortable"
          aria-sort={columnAriaSort('chain_owner')}
        >
          <button type="button" on:click={() => toggleSort('chain_owner')}>
            Chain
            {#if sortField === 'chain_owner'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th
          class="sortable"
          aria-sort={columnAriaSort('cms_platform')}
        >
          <button type="button" on:click={() => toggleSort('cms_platform')}>
            CMS Platform
            {#if sortField === 'cms_platform'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th
          class="sortable"
          aria-sort={columnAriaSort('cms_vendor')}
        >
          <button type="button" on:click={() => toggleSort('cms_vendor')}>
            CMS Vendor
            {#if sortField === 'cms_vendor'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th
          class="sortable"
          aria-sort={columnAriaSort('timestamp')}
        >
          <button type="button" on:click={() => toggleSort('timestamp')}>
            Last Audit
            {#if sortField === 'timestamp'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#if items.length === 0}
        <tr>
          <td colspan="15" class="empty">No results</td>
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
              {#if normalizeWebsiteUrl(item.website_url)}
                <a
                  class="external"
                  href={normalizeWebsiteUrl(item.website_url) ?? undefined}
                  target="_blank"
                  rel="noreferrer"
                >
                  Visit
                </a>
              {:else}
                —
              {/if}
            </td>
            <td>
              <span class={`status-pill ${statusClass('has_pdf', item.latest_audit?.has_pdf)}${isOverridden(item.latest_audit, 'has_pdf') ? ' overridden' : ''}`}>
                {item.latest_audit?.has_pdf ?? '—'}
              </span>
            </td>
            <td>
              <span class={`status-pill ${statusClass('pdf_only', item.latest_audit?.pdf_only)}${isOverridden(item.latest_audit, 'pdf_only') ? ' overridden' : ''}`}>
                {item.latest_audit?.pdf_only ?? '—'}
              </span>
            </td>
            <td>
              <span class={`status-pill ${statusClass('paywall', item.latest_audit?.paywall)}${isOverridden(item.latest_audit, 'paywall') ? ' overridden' : ''}`}>
                {item.latest_audit?.paywall ?? '—'}
              </span>
            </td>
            <td>
              <span class={`status-pill ${statusClass('notices', item.latest_audit?.notices)}${isOverridden(item.latest_audit, 'notices') ? ' overridden' : ''}`}>
                {item.latest_audit?.notices ?? '—'}
              </span>
            </td>
            <td>
              <span class={`status-pill ${statusClass('responsive', item.latest_audit?.responsive)}${isOverridden(item.latest_audit, 'responsive') ? ' overridden' : ''}`}>
                {item.latest_audit?.responsive ?? '—'}
              </span>
            </td>
            <td>{item.latest_audit?.chain_owner ?? '—'}</td>
            <td>{item.latest_audit?.cms_platform ?? '—'}</td>
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
    <div class="pagination-controls">
      <button type="button" on:click={goToFirst} disabled={currentPage === 1 || loading}>First</button>
      <button type="button" on:click={() => goToPage(currentPage - 1)} disabled={currentPage === 1 || loading}>
        Previous
      </button>
      <span class="page-indicator">Page {currentPage} of {totalPages}</span>
      <button
        type="button"
        on:click={() => goToPage(currentPage + 1)}
        disabled={currentPage === totalPages || loading}
      >
        Next
      </button>
      <button type="button" on:click={goToLast} disabled={currentPage === totalPages || loading}>Last</button>
    </div>
    <div class="pagination-summary">
      {#if total === 0}
        <span>No results</span>
      {:else}
        <span>Showing {startEntry}&ndash;{endEntry} of {total}</span>
      {/if}
    </div>
  </div>
</div>

<style>
  .table-wrapper {
    background: white;
    border-radius: 0.75rem;
    border: 1px solid #e5e7eb;
    overflow: visible;
    position: relative;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  thead {
    background-color: #f9fafb;
  }

  thead th {
    position: sticky;
    top: 0;
    z-index: 2;
    background-color: #f9fafb;
    box-shadow: inset 0 -1px 0 #e5e7eb;
  }

  th,
  td {
    text-align: left;
    padding: 0.75rem;
    border-bottom: 1px solid #e5e7eb;
    font-size: 0.9rem;
  }

  th.sortable {
    padding: 0;
  }

  th.sortable button {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 0.35rem;
    background: transparent;
    border: none;
    padding: 0.75rem;
    font: inherit;
    text-align: left;
    color: inherit;
    cursor: pointer;
  }

  th.sortable button:hover,
  th.sortable button:focus {
    background-color: #eef2ff;
    outline: none;
  }

  thead th.sortable button {
    background-color: transparent;
  }

  thead th.sortable button:hover,
  thead th.sortable button:focus {
    background-color: #e0e7ff;
  }

  .sort-indicator {
    font-size: 0.75rem;
    color: #6b7280;
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

  .status-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.15rem 0.5rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    border: 1px solid #e5e7eb;
    background: #f3f4f6;
    color: #374151;
    min-width: 3.25rem;
    text-transform: uppercase;
  }

  .status-pill.overridden {
    border-color: rgba(59, 130, 246, 0.35);
    background: rgba(219, 234, 254, 0.85);
    color: #1d4ed8;
  }

  .status-pill.status.yes {
    border-color: rgba(22, 163, 74, 0.25);
    background: rgba(220, 252, 231, 0.85);
    color: #166534;
  }

  .status-pill.status.no {
    border-color: rgba(239, 68, 68, 0.25);
    background: rgba(254, 226, 226, 0.85);
    color: #b91c1c;
  }

  .status-pill.status.review {
    border-color: rgba(245, 158, 11, 0.25);
    background: rgba(254, 243, 199, 0.85);
    color: #b45309;
  }

  .status-pill.status.neutral {
    border-color: #e5e7eb;
    background: #f3f4f6;
    color: #374151;
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
    flex-direction: column;
    gap: 0.75rem;
    align-items: center;
  }

  .pagination-controls {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
    justify-content: center;
  }

  .page-indicator {
    font-weight: 600;
    color: #111827;
  }

  .pagination-summary {
    color: #4b5563;
    font-size: 0.9rem;
  }
</style>
