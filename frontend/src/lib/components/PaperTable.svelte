<script lang="ts">
  import type { PaperSummary } from '$lib/types';
  import { createEventDispatcher } from 'svelte';
  import { formatRelativeTime } from '$lib/formatters';

  export let items: PaperSummary[] = [];
  export let total = 0;
  export let limit = 50;
  export let offset = 0;
  export let loading = false;

  const dispatch = createEventDispatcher<{
    audit: { id: number };
    paginate: { offset: number };
  }>();

  const totalPages = Math.max(1, Math.ceil(total / limit));
  const currentPage = Math.floor(offset / limit) + 1;

  function goToPage(page: number) {
    const target = Math.max(1, Math.min(totalPages, page));
    dispatch('paginate', { offset: (target - 1) * limit });
  }
</script>

<div class="table-wrapper">
  <table>
    <thead>
      <tr>
        <th>Paper</th>
        <th>City</th>
        <th>State</th>
        <th>Website</th>
        <th>Has PDF</th>
        <th>Paywall</th>
        <th>Notices</th>
        <th>Responsive</th>
        <th>Last Audit</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#if items.length === 0}
        <tr>
          <td colspan="10" class="empty">No results</td>
        </tr>
      {:else}
        {#each items as item}
          <tr>
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
