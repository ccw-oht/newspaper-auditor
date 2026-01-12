<script lang="ts">
  /* eslint-env browser */
  import { onDestroy, onMount } from 'svelte';
  import { fade, slide } from 'svelte/transition';
  import { clearJobHistory, fetchJobHistoryItems } from '$lib/api';
  import type { JobHistoryItem } from '$lib/types';

  let items: JobHistoryItem[] = [];
  let loading = false;
  let error: string | null = null;
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let expandedIds = new Set<number>();
  let hoverExpandedId: number | null = null;
  let hoverTimer: number | null = null;

  async function loadHistory() {
    try {
      loading = true;
      items = await fetchJobHistoryItems(200, 0);
      error = null;
    } catch (err) {
      console.error(err);
      error = 'Failed to load job history.';
    } finally {
      loading = false;
    }
  }

  async function handleClear() {
    try {
      await clearJobHistory();
      await loadHistory();
    } catch (err) {
      console.error(err);
      error = 'Failed to clear history.';
    }
  }

  function formatJson(value: unknown): string {
    return JSON.stringify(value, null, 2);
  }

  function formatTimestamp(value: string | null | undefined): string {
    if (!value) return '—';
    return new Date(value).toLocaleString();
  }

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
    if (hoverTimer !== null) {
      clearTimeout(hoverTimer);
    }
    hoverTimer = window.setTimeout(() => {
      hoverExpandedId = id;
      hoverTimer = null;
    }, 140);
  }

  function clearHoverDetails(id: number) {
    if (hoverTimer !== null) {
      clearTimeout(hoverTimer);
      hoverTimer = null;
    }
    if (hoverExpandedId === id) {
      hoverExpandedId = null;
    }
  }

  onMount(() => {
    loadHistory();
    pollTimer = setInterval(loadHistory, 10000);
  });

  onDestroy(() => {
    if (pollTimer) {
      clearInterval(pollTimer);
    }
  });
</script>

<section class="history-page">
  <header>
    <div>
      <h2>Job history</h2>
      <p>Review completed and canceled audits/lookups.</p>
    </div>
    <div class="actions">
      <button type="button" on:click={loadHistory} disabled={loading}>Refresh</button>
      <button type="button" class="danger" on:click={handleClear}>Clear history</button>
    </div>
  </header>

  {#if error}
    <p class="error">{error}</p>
  {/if}

  <div class="table">
    <div class="table-header">
      <span>Paper</span>
      <span>Action</span>
      <span>Status</span>
      <span>Job</span>
      <span>Completed</span>
      <span></span>
    </div>
    {#if items.length === 0}
      <p class="empty">{loading ? 'Loading…' : 'No history yet.'}</p>
    {:else}
      {#each items as item}
        <div class="table-row">
          <div class="table-row-main">
            <a class="paper-name" href={`/papers/${item.paper_id}`}>
              {item.paper_name ?? `Paper ${item.paper_id}`}
            </a>
            <span>{item.job_type === 'audit' ? 'Audit' : 'Lookup'}</span>
            <span class={`status ${item.status}`}>{item.status}</span>
            <span>#{item.job_id}</span>
            <span>{formatTimestamp(item.completed_at)}</span>
            <button
              type="button"
              class="detail-toggle"
              on:click={() => toggleDetails(item.item_id)}
              on:mouseenter={() => showHoverDetails(item.item_id)}
              on:mouseleave={() => clearHoverDetails(item.item_id)}
              aria-expanded={expandedIds.has(item.item_id) || hoverExpandedId === item.item_id}
            >
              {expandedIds.has(item.item_id) ? 'Hide' : hoverExpandedId === item.item_id ? 'Pin' : 'Details'}
            </button>
          </div>
          {#if expandedIds.has(item.item_id) || hoverExpandedId === item.item_id}
            <div class="detail-panel" transition:slide={{ duration: 240 }}>
              {#if item.error}
                <p class="job-error">{item.error}</p>
              {/if}
              {#if item.result}
                <pre>{formatJson(item.result)}</pre>
              {:else}
                <p class="empty">No metadata recorded.</p>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    {/if}
  </div>
</section>

<style>
  .history-page {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
  }

  header h2 {
    margin: 0 0 0.35rem;
  }

  header p {
    margin: 0;
    color: #6b7280;
  }

  .actions {
    display: flex;
    gap: 0.5rem;
  }

  .actions button {
    border: 1px solid #d1d5db;
    background: white;
    border-radius: 0.5rem;
    padding: 0.4rem 0.75rem;
    cursor: pointer;
  }

  .actions .danger {
    border-color: #f87171;
    color: #b91c1c;
    background: #fee2e2;
  }

  .table {
    border: 1px solid #e5e7eb;
    background: white;
    border-radius: 12px;
    overflow: hidden;
  }

  .table-header {
    display: grid;
    grid-template-columns: minmax(180px, 2fr) 120px 120px 100px 160px 110px;
    gap: 1rem;
    padding: 0.85rem 1rem;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #6b7280;
    background: #f9fafb;
  }

  .table-row {
    border-top: 1px solid #e5e7eb;
  }

  .table-row-main {
    display: grid;
    grid-template-columns: minmax(180px, 2fr) 120px 120px 100px 160px 110px;
    gap: 1rem;
    padding: 0.85rem 1rem;
    align-items: center;
  }

  .paper-name {
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: #111827;
    text-decoration: none;
  }

  .paper-name:hover {
    text-decoration: underline;
  }

  .detail-panel {
    padding: 0 1rem 1rem;
  }

  .status {
    text-transform: capitalize;
    font-size: 0.75rem;
    padding: 0.2rem 0.5rem;
    border-radius: 999px;
    background: #f3f4f6;
    color: #374151;
  }

  .status.completed {
    background: #dcfce7;
    color: #166534;
  }

  .status.failed {
    background: #fee2e2;
    color: #991b1b;
  }

  .status.canceled {
    background: #fef3c7;
    color: #92400e;
  }

  .job-error {
    color: #dc2626;
    margin: 0.35rem 0 0;
    font-size: 0.85rem;
  }

  pre {
    background: #111827;
    color: #f9fafb;
    padding: 0.75rem;
    border-radius: 8px;
    overflow: auto;
    font-size: 0.8rem;
  }

  .empty {
    color: #6b7280;
    font-size: 0.9rem;
  }

  .error {
    color: #dc2626;
  }

  .detail-toggle {
    border: 1px solid #d1d5db;
    background: #f3f4f6;
    color: #111827;
    border-radius: 0.5rem;
    padding: 0.35rem 0.6rem;
    font-size: 0.8rem;
    cursor: pointer;
    transition: opacity 0.2s ease, transform 0.2s ease;
  }

  .detail-toggle:hover {
    opacity: 0.9;
    transform: translateY(-1px);
  }

  @media (max-width: 900px) {
    .table-header,
    .table-row-main {
      grid-template-columns: 1fr 80px 90px 90px;
      grid-template-areas:
        "paper action status"
        "job completed details";
    }

    .table-header span:nth-child(1),
    .table-row-main .paper-name {
      grid-area: paper;
    }

    .table-header span:nth-child(2),
    .table-row-main span:nth-child(2) {
      grid-area: action;
    }

    .table-header span:nth-child(3),
    .table-row-main span:nth-child(3) {
      grid-area: status;
    }

    .table-header span:nth-child(4),
    .table-row-main span:nth-child(4) {
      grid-area: job;
    }

    .table-header span:nth-child(5),
    .table-row-main span:nth-child(5) {
      grid-area: completed;
    }

    .table-row-main .detail-toggle {
      grid-area: details;
      justify-self: start;
    }
  }
</style>
