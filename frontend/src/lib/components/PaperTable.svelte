<script lang="ts">
  /* eslint-env browser */
import type { AuditSummary, PaperSummary } from '$lib/types';
import { createEventDispatcher } from 'svelte';
import { slide } from 'svelte/transition';

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
    lookup: { id: number };
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
  let expandedIds = new Set<number>();
  let hoverExpandedId: number | null = null;

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

  $: {
    const visibleIds = new Set(items.map((item) => item.id));
    expandedIds = new Set(Array.from(expandedIds).filter((id) => visibleIds.has(id)));
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

  function auditFieldValue(summary: AuditSummary | null | undefined, field: string): string | null | undefined {
    if (!summary) return null;
    const record = summary as Record<string, string | null | undefined>;
    return record[field];
  }

  function hasLookup(item: PaperSummary): boolean {
    const extra = item.extra_data as Record<string, unknown> | null | undefined;
    if (!extra) return false;
    const lookup = extra.contact_lookup as Record<string, unknown> | undefined;
    return !!lookup;
  }

  function primaryContact(item: PaperSummary): string | null {
    const extra = item.extra_data as Record<string, unknown> | null | undefined;
    const lookup = extra?.contact_lookup as Record<string, unknown> | undefined;
    const value = lookup?.primary_contact;
    if (typeof value !== 'string') return null;
    const trimmed = value.trim();
    return trimmed ? trimmed : null;
  }

  const detailFields = [
    { key: 'has_pdf', label: 'Has PDF', short: 'PDF' },
    { key: 'pdf_only', label: 'PDF Only', short: 'Only' },
    { key: 'paywall', label: 'Paywall', short: 'Pay' },
    { key: 'notices', label: 'Notices', short: 'Not' },
    { key: 'responsive', label: 'Responsive', short: 'Resp' }
  ];

  function toggleDetails(id: number) {
    const next = new Set(expandedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    expandedIds = next;
  }

  function showHoverDetails(id: number) {
    hoverExpandedId = id;
  }

  function clearHoverDetails(id: number) {
    if (hoverExpandedId === id) {
      hoverExpandedId = null;
    }
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
          class="sortable audit-summary"
          aria-sort={columnAriaSort('timestamp')}
        >
          <button type="button" on:click={() => toggleSort('timestamp')}>
            Last Audit
            {#if sortField === 'timestamp'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th class="actions">Actions</th>
      </tr>
    </thead>
    <tbody>
      {#if items.length === 0}
        <tr>
          <td colspan="7" class="empty">No results</td>
        </tr>
      {:else}
        {#each items as item, index}
          <tr class:expanded={expandedIds.has(item.id) || hoverExpandedId === item.id}>
            <td class="select">
              <input
                type="checkbox"
                checked={selectedSet.has(item.id)}
                on:click={(event) => handleItemClick(event, item.id, index)}
                aria-label={`Select ${item.paper_name ?? 'paper'}`}
              />
            </td>
            <td class="paper-cell">
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
            <td class="audit-summary">
              <div class="audit-icons" aria-label="Latest audit results">
                {#each detailFields as field}
                  <span
                    class={`audit-icon ${statusClass(field.key, auditFieldValue(item.latest_audit, field.key))}${isOverridden(item.latest_audit, field.key) ? ' overridden' : ''}`}
                    title={`${field.label}: ${auditFieldValue(item.latest_audit, field.key) ?? '—'}`}
                    aria-label={`${field.label}: ${auditFieldValue(item.latest_audit, field.key) ?? '—'}`}
                  >
                    {field.short}
                  </span>
                {/each}
              </div>
            </td>
            <td class="actions">
              <div class="action-buttons">
                <button type="button" disabled={loading} on:click={() => dispatch('audit', { id: item.id })}>
                  Audit
                </button>
                <button
                  type="button"
                  class={`secondary${hasLookup(item) ? ' lookup-done' : ''}`}
                  disabled={loading}
                  on:click={() => dispatch('lookup', { id: item.id })}
                >
                  Lookup
                </button>
                <button
                  type="button"
                  class="secondary"
                  on:click={() => toggleDetails(item.id)}
                  on:mouseenter={() => showHoverDetails(item.id)}
                  on:mouseleave={() => clearHoverDetails(item.id)}
                  aria-expanded={expandedIds.has(item.id) || hoverExpandedId === item.id}
                >
                  {expandedIds.has(item.id) ? 'Hide' : 'Details'}
                </button>
              </div>
            </td>
          </tr>
          {#if expandedIds.has(item.id) || hoverExpandedId === item.id}
            <tr class="detail-row">
              <td colspan="7">
                <div class="detail-content" transition:slide={{ duration: 360 }}>
                  <div class="detail-grid">
                    <div class="detail-block">
                      <h4>Audit</h4>
                      <div class="pill-row">
                        {#each detailFields as field}
                          <div class={`detail-pill ${statusClass(field.key, auditFieldValue(item.latest_audit, field.key))}${isOverridden(item.latest_audit, field.key) ? ' overridden' : ''}`}>
                            <span class="pill-label">{field.label}</span>
                            <span class="pill-value">{auditFieldValue(item.latest_audit, field.key) ?? '—'}</span>
                          </div>
                        {/each}
                      </div>
                    </div>
                    <div class="detail-block">
                      <h4>Platform</h4>
                      <div class="detail-line"><span>Chain:</span> {item.chain_owner ?? '—'}</div>
                      <div class="detail-line"><span>CMS platform:</span> {item.cms_platform ?? '—'}</div>
                      <div class="detail-line"><span>CMS vendor:</span> {item.cms_vendor ?? '—'}</div>
                      <div class="detail-line"><span>Frequency:</span> {item.publication_frequency ?? '—'}</div>
                    </div>
                    <div class="detail-block">
                      <h4>Contact</h4>
                      <div class="detail-line"><span>Primary contact:</span> {primaryContact(item) ?? '—'}</div>
                      <div class="detail-line"><span>Phone:</span> {item.phone ?? '—'}</div>
                      <div class="detail-line"><span>Email:</span> {item.email ?? '—'}</div>
                    </div>
                  </div>
                </div>
              </td>
            </tr>
          {/if}
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

  th.actions,
  td.actions {
    width: 18rem;
  }

  th.audit-summary,
  td.audit-summary {
    width: 19rem;
  }

  td.paper-cell {
    max-width: 18rem;
  }

  td.paper-cell a.paper-link {
    display: inline-block;
    max-width: 100%;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
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

  button.secondary {
    background-color: #f3f4f6;
    color: #111827;
    border: 1px solid #e5e7eb;
  }

  button.lookup-done {
    background-color: #16a34a;
    border-color: #15803d;
    color: #ffffff;
  }

  .audit-icons {
    display: inline-flex;
    gap: 0.4rem;
    flex-wrap: wrap;
  }

  .audit-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 2.25rem;
    padding: 0.15rem 0.35rem;
    border-radius: 999px;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    border: 1px solid #e5e7eb;
    background: #f3f4f6;
    color: #374151;
  }

  .audit-icon.overridden {
    border-color: rgba(59, 130, 246, 0.35);
    background: rgba(219, 234, 254, 0.85);
    color: #1d4ed8;
  }

  .audit-icon.status.yes {
    border-color: rgba(22, 163, 74, 0.25);
    background: rgba(220, 252, 231, 0.85);
    color: #166534;
  }

  .audit-icon.status.no {
    border-color: rgba(239, 68, 68, 0.25);
    background: rgba(254, 226, 226, 0.85);
    color: #b91c1c;
  }

  .audit-icon.status.review {
    border-color: rgba(245, 158, 11, 0.25);
    background: rgba(254, 243, 199, 0.85);
    color: #b45309;
  }

  .audit-icon.status.neutral {
    border-color: #e5e7eb;
    background: #f3f4f6;
    color: #374151;
  }

  .action-buttons {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .detail-row td {
    background: #f9fafb;
    padding: 0;
  }

  .detail-content {
    overflow: hidden;
  }

  .detail-grid {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    padding: 1rem 1.25rem;
  }

  .detail-block h4 {
    margin: 0 0 0.5rem;
    font-size: 0.9rem;
    color: #111827;
  }

  .detail-line {
    display: flex;
    gap: 0.5rem;
    font-size: 0.85rem;
    color: #374151;
  }

  .detail-line span {
    font-weight: 600;
    color: #111827;
  }

  .pill-row {
    display: grid;
    gap: 0.5rem;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  }

  .detail-pill {
    border-radius: 0.75rem;
    padding: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    box-shadow: inset 0 0 0 1px #e5e7eb;
    background: #ffffff;
  }

  .detail-pill.overridden {
    box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.35);
  }

  .detail-pill.status.yes {
    box-shadow: inset 0 0 0 1px rgba(22, 163, 74, 0.25);
    background: rgba(220, 252, 231, 0.85);
    color: #166534;
  }

  .detail-pill.status.no {
    box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.25);
    background: rgba(254, 226, 226, 0.85);
    color: #b91c1c;
  }

  .detail-pill.status.review {
    box-shadow: inset 0 0 0 1px rgba(245, 158, 11, 0.25);
    background: rgba(254, 243, 199, 0.85);
    color: #b45309;
  }

  .detail-pill.status.neutral {
    box-shadow: inset 0 0 0 1px #e5e7eb;
    background: #f3f4f6;
    color: #374151;
  }

  .pill-label {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .pill-value {
    font-weight: 700;
    font-size: 0.9rem;
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
