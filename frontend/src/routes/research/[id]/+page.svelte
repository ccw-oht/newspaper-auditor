<script lang="ts">
  import { runResearchFeatures } from '$lib/api';
  import type { ResearchSessionDetail, ResearchFeature, ResearchEvidenceItem } from '$lib/types';

  export let data: {
    session: ResearchSessionDetail;
  };

  let session: ResearchSessionDetail = data.session;
  let refreshAllLoading = false;
  let refreshSelectionLoading = false;
  let errorMessage: string | null = null;
  let featureLoading = new Set<number>();
  let selectedPaperIds = new Set<number>();
  let expandedPaperIds = new Set<number>();
  let paperLoading = new Set<number>();
  let selectAllCheckbox: HTMLInputElement | null = null;
  let paperSortOrder: 'asc' | 'desc' = 'asc';
  let pageSize = 25;
  let currentPage = 1;

  $: if (selectAllCheckbox) {
    selectAllCheckbox.indeterminate =
      selectedPaperIds.size > 0 && selectedPaperIds.size < session.papers.length;
  }

  $: sortedPapers = [...session.papers].sort((a, b) => {
    const nameA = (snapshotValue(a, 'paper_name') || '').toLowerCase();
    const nameB = (snapshotValue(b, 'paper_name') || '').toLowerCase();
    if (nameA === nameB) return 0;
    return paperSortOrder === 'asc' ? (nameA > nameB ? 1 : -1) : nameA < nameB ? 1 : -1;
  });

  $: totalPages = Math.max(1, Math.ceil(sortedPapers.length / pageSize));
  $: currentPage = Math.min(currentPage, totalPages);
  $: visiblePapers = sortedPapers.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  function matchesFor(feature: ResearchFeature): ResearchEvidenceItem[] {
    const evidence = feature.evidence?.matches;
    if (!Array.isArray(evidence)) return [];
    return evidence as ResearchEvidenceItem[];
  }

  function snapshotValue(
    paper: ResearchSessionDetail['papers'][number],
    key: string
  ): string | null {
    const snapshot = paper.snapshot ?? {};
    const value = snapshot[key];
    if (typeof value === 'string') return value;
    if (value === null || value === undefined) return null;
    return String(value);
  }

  function formatDate(value: string | null | undefined): string {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
  }

  function formatFilterValue(value: unknown): string {
    if (value === null || value === undefined) return '—';
    if (Array.isArray(value)) {
      return value.join(', ');
    }
    return String(value);
  }

  async function refreshFeatures(featureIds?: number[], paperIds?: number[]) {
    try {
      if (!session) return;
      if (featureIds && featureIds.length === 1) {
        const next = new Set(featureLoading);
        next.add(featureIds[0]);
        featureLoading = next;
      } else if (paperIds && paperIds.length > 0) {
        if (paperIds.length === 1) {
          const next = new Set(paperLoading);
          next.add(paperIds[0]);
          paperLoading = next;
        }
        refreshSelectionLoading = true;
      } else {
        refreshAllLoading = true;
      }
      errorMessage = null;
      const updated = await runResearchFeatures(session.id, featureIds, paperIds);
      const lookup = new Map(updated.map((feature) => [feature.id, feature]));
      session = {
        ...session,
        features: session.features.map((feature) => lookup.get(feature.id) ?? feature)
      };
    } catch (error) {
      console.error(error);
      errorMessage = error instanceof Error ? error.message : 'Failed to refresh features.';
    } finally {
      if (featureIds && featureIds.length === 1) {
        const next = new Set(featureLoading);
        next.delete(featureIds[0]);
        featureLoading = next;
      } else if (paperIds && paperIds.length > 0) {
        if (paperIds.length === 1) {
          const next = new Set(paperLoading);
          next.delete(paperIds[0]);
          paperLoading = next;
        }
        refreshSelectionLoading = false;
      } else {
        refreshAllLoading = false;
      }
    }
  }

  function matchesForPaper(feature: ResearchFeature, paperId: number): ResearchEvidenceItem[] {
    return matchesFor(feature).filter((match) => match.paper_id === paperId);
  }

  function paperFeatureStatus(feature: ResearchFeature, paperId: number): 'found' | 'missing' | 'error' {
    if (feature.error) return 'error';
    return matchesForPaper(feature, paperId).length > 0 ? 'found' : 'missing';
  }

  function togglePaperSelection(paperId: number) {
    const next = new Set(selectedPaperIds);
    if (next.has(paperId)) {
      next.delete(paperId);
    } else {
      next.add(paperId);
    }
    selectedPaperIds = next;
  }

  function selectAllPapers() {
    selectedPaperIds = new Set(session.papers.map((paper) => paper.id));
  }

  function clearPaperSelection() {
    selectedPaperIds = new Set();
  }

  function toggleExpandPaper(paperId: number) {
    const next = new Set(expandedPaperIds);
    if (next.has(paperId)) {
      next.delete(paperId);
    } else {
      next.add(paperId);
    }
    expandedPaperIds = next;
  }

  function featureLabel(feature: ResearchFeature, paperId: number): string {
    const matches = matchesForPaper(feature, paperId);
    if (matches.length > 0) return 'Feature found';
    if (feature.error) return 'Feature error';
    return 'No match yet';
  }
</script>

<div class="page">
  <header>
    <div>
      <h2>{session.name}</h2>
      {#if session.description}
        <p class="subtitle">{session.description}</p>
      {/if}
    </div>
    <div class="actions">
      <a href="/research" class="link">Back to list</a>
      <button type="button" on:click={() => refreshFeatures()} disabled={refreshAllLoading}>
        {refreshAllLoading ? 'Refreshing…' : 'Refresh all features'}
      </button>
    </div>
  </header>

  <section class="metadata">
    <div>
      <h4>Filters</h4>
      {#if Object.keys(session.filter_params || {}).length === 0}
        <p>No filters captured.</p>
      {:else}
        <div class="chips">
          {#each Object.entries(session.filter_params) as entry}
            <span class="chip">{entry[0]}: {formatFilterValue(entry[1])}</span>
          {/each}
        </div>
      {/if}
    </div>
    <div>
      <h4>Recreate query</h4>
      {#if session.query_string}
        <a
          class="link"
          href={`/papers?${session.query_string}`}
        >
          Open Papers view
        </a>
      {:else}
        <p>No query saved.</p>
      {/if}
    </div>
    <div>
      <h4>Created</h4>
      <p>{formatDate(session.created_at)}</p>
    </div>
  </section>

  {#if errorMessage}
    <p class="error">{errorMessage}</p>
  {/if}

  <section class="papers">
    <div class="paper-header">
      <div>
        <h3>Feature Report ({session.papers.length})</h3>
        <p class="subtitle">Each paper shows whether features matched; expand to see artifacts.</p>
      </div>
      <div class="paper-actions">
        <button
          type="button"
          class="secondary"
          on:click={selectedPaperIds.size === session.papers.length ? clearPaperSelection : selectAllPapers}
        >
          {selectedPaperIds.size === session.papers.length ? 'Clear selection' : 'Select all'}
        </button>
        <button
          type="button"
          on:click={() => refreshFeatures(undefined, Array.from(selectedPaperIds))}
          disabled={selectedPaperIds.size === 0 || refreshSelectionLoading}
        >
          {refreshSelectionLoading
            ? 'Refreshing selection…'
            : `Refresh ${selectedPaperIds.size || ''} selected`}
        </button>
      </div>
    </div>
    <div class="pagination">
      <label class="page-size">
        Entries per page
        <select bind:value={pageSize} on:change={() => (currentPage = 1)}>
          <option value={10}>10</option>
          <option value={25}>25</option>
          <option value={50}>50</option>
          <option value={100}>100</option>
        </select>
      </label>
      <div class="page-controls">
        <button type="button" on:click={() => (currentPage = Math.max(1, currentPage - 1))} disabled={currentPage === 1}>
          Prev
        </button>
        <span>Page {currentPage} of {totalPages}</span>
        <button
          type="button"
          on:click={() => (currentPage = Math.min(totalPages, currentPage + 1))}
          disabled={currentPage === totalPages}
        >
          Next
        </button>
      </div>
    </div>
    <div class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th class="checkbox-col">
              <input
                type="checkbox"
                bind:this={selectAllCheckbox}
                checked={selectedPaperIds.size === session.papers.length}
                on:change={() =>
                  selectedPaperIds.size === session.papers.length ? clearPaperSelection() : selectAllPapers()
                }
              />
            </th>
            <th>
              <button
                class="sort-button"
                type="button"
                aria-label={`Sort by paper name (${paperSortOrder === 'asc' ? 'ascending' : 'descending'})`}
                on:click={() => (paperSortOrder = paperSortOrder === 'asc' ? 'desc' : 'asc')}
              >
                Paper {paperSortOrder === 'asc' ? '▴' : '▾'}
              </button>
            </th>
            <th>Features</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each visiblePapers as paper}
            <tr class:selected={selectedPaperIds.has(paper.id)}>
              <td class="checkbox-col">
                <input
                  type="checkbox"
                  checked={selectedPaperIds.has(paper.id)}
                  on:change={() => togglePaperSelection(paper.id)}
                />
              </td>
              <td>
                <div class="paper-cell">
                  <button
                    type="button"
                    class="twirl"
                    aria-expanded={expandedPaperIds.has(paper.id)}
                    on:click={() => toggleExpandPaper(paper.id)}
                  >
                    {expandedPaperIds.has(paper.id) ? '▾' : '▸'}
                  </button>
                  <div>
                    <button
                      type="button"
                      class="paper-name"
                      on:click={() => toggleExpandPaper(paper.id)}
                      aria-expanded={expandedPaperIds.has(paper.id)}
                    >
                      {snapshotValue(paper, 'paper_name') || '—'}
                    </button>
                    <div class="paper-meta">
                      {#if snapshotValue(paper, 'website_url')}
                        <a href={snapshotValue(paper, 'website_url')} target="_blank" rel="noreferrer">
                          {snapshotValue(paper, 'website_url')}
                        </a>
                      {:else}
                        —
                      {/if}
                    </div>
                  </div>
                </div>
              </td>
              <td>
                <div class="feature-chips">
                  {#each session.features as feature}
                    {#if feature.status === 'running'}
                      <span class="status-chip running">{feature.name}: running</span>
                    {:else if feature.status === 'error'}
                      <span class="status-chip error">{feature.name}: error</span>
                    {:else if matchesForPaper(feature, paper.id).length > 0}
                      <span class="status-chip found">{feature.name}: found</span>
                    {:else}
                      <span class="status-chip missing">{feature.name}: none</span>
                    {/if}
                  {/each}
                </div>
              </td>
              <td class="actions-cell">
                <button
                  type="button"
                  class="secondary"
                  on:click={() => refreshFeatures(undefined, [paper.id])}
                  disabled={paperLoading.has(paper.id) || refreshSelectionLoading}
                >
                  {paperLoading.has(paper.id) ? 'Refreshing…' : 'Refresh paper'}
                </button>
              </td>
            </tr>
            {#if expandedPaperIds.has(paper.id)}
              <tr class="detail-row">
                <td colspan="4">
                  <div class="feature-details">
                    {#each session.features as feature}
                      <div class="detail-block">
                        <div class="detail-header">
                          <div>
                            <span class={`status-chip ${paperFeatureStatus(feature, paper.id)}`}>
                              {feature.name}: {featureLabel(feature, paper.id)}
                            </span>
                            <span class="keywords">Keywords: {feature.keywords.join(', ')}</span>
                            <span class="timestamp">· {formatDate(feature.last_evaluated_at)}</span>
                          </div>
                          {#if feature.error}
                            <span class="status-chip error">Error</span>
                          {/if}
                        </div>
                        {#if feature.error}
                          <p class="error">Feature error: {feature.error}</p>
                        {/if}
                        {#if matchesForPaper(feature, paper.id).length === 0}
                          <p class="muted">No matches for this paper yet.</p>
                        {:else}
                          <ul class="detail-list">
                            {#each matchesForPaper(feature, paper.id) as match}
                              <li>
                                <div class="source">
                                  <span class="badge">{match.source_type}</span>
                                  {#if match.url}
                                    <a href={match.url} target="_blank" rel="noreferrer">
                                      {match.title || match.url}
                                    </a>
                                  {:else}
                                    <span>{match.title || 'Match'}</span>
                                  {/if}
                                </div>
                                {#if match.excerpt}
                                  <p class="excerpt">{match.excerpt}</p>
                                {/if}
                                <p class="keywords">Matched: {match.matched_keywords.join(', ')}</p>
                              </li>
                            {/each}
                          </ul>
                        {/if}
                      </div>
                    {/each}
                  </div>
                </td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
    </div>
  </section>
</div>

<style>
  .page {
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

  h2 {
    margin: 0;
  }

  .subtitle {
    margin: 0.25rem 0 0;
    color: #6b7280;
  }

  .actions {
    display: flex;
    gap: 0.75rem;
    align-items: center;
  }

  button {
    background-color: #2563eb;
    color: white;
    border: none;
    border-radius: 0.5rem;
    padding: 0.5rem 0.9rem;
    font-weight: 600;
    cursor: pointer;
  }

  button[disabled] {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .link {
    text-decoration: none;
    color: #2563eb;
    font-weight: 600;
  }

  .metadata {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
    background: white;
    border-radius: 0.75rem;
    padding: 1rem 1.25rem;
    border: 1px solid #e5e7eb;
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }

  .chip {
    background: #eef2ff;
    color: #312e81;
    padding: 0.2rem 0.5rem;
    border-radius: 999px;
    font-size: 0.75rem;
  }

  .error {
    color: #b91c1c;
    font-weight: 600;
  }

  .features,
  .papers {
    background: white;
    border-radius: 0.75rem;
    padding: 1rem 1.25rem;
    border: 1px solid #e5e7eb;
  }

  .feature-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1rem;
  }

  .feature-card {
    border: 1px solid #e5e7eb;
    border-radius: 0.75rem;
    padding: 0.9rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .feature-card header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.25rem;
  }

  .status {
    margin: 0.2rem 0 0;
    font-size: 0.85rem;
    color: #4b5563;
  }

  .badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: #e5e7eb;
    border-radius: 999px;
    padding: 0.1rem 0.5rem;
    font-size: 0.75rem;
    text-transform: capitalize;
  }

  .badge.completed {
    background: #dcfce7;
    color: #15803d;
  }

  .badge.running {
    background: #fef9c3;
    color: #a16207;
  }

  .badge.error {
    background: #fee2e2;
    color: #b91c1c;
  }

  .timestamp {
    margin-left: 0.25rem;
    color: #9ca3af;
  }

  .keywords {
    margin: 0;
    font-size: 0.85rem;
    color: #374151;
  }

  .evidence-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .evidence-list li {
    border-top: 1px solid #e5e7eb;
    padding-top: 0.5rem;
  }

  .source {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .excerpt {
    margin: 0.35rem 0;
    font-size: 0.9rem;
    color: #4b5563;
  }

  .paper-name {
    font-weight: 700;
    border: none;
    background: transparent;
    padding: 0;
    margin: 0;
    cursor: pointer;
    color: #0f172a;
    text-align: left;
  }

  .paper-meta {
    font-size: 0.9rem;
    color: #4b5563;
  }

  .paper-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .paper-actions {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  .paper-actions .secondary {
    background: #f3f4f6;
    color: #111827;
    border: 1px solid #e5e7eb;
  }

  .table-wrapper {
    overflow-x: auto;
  }

  .pagination {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: 0.5rem 0;
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  .page-size {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: #4b5563;
    font-size: 0.95rem;
  }

  .page-size select {
    padding: 0.35rem 0.5rem;
    border-radius: 0.5rem;
    border: 1px solid #d1d5db;
  }

  .page-controls {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    flex-wrap: wrap;
  }

  .page-controls button {
    padding: 0.35rem 0.7rem;
    border-radius: 0.5rem;
    border: 1px solid #d1d5db;
    background: #f3f4f6;
    color: #111827;
    cursor: pointer;
  }

  .page-controls button[disabled] {
    opacity: 0.6;
    cursor: not-allowed;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  .checkbox-col {
    width: 44px;
    text-align: center;
  }

  .checkbox-col input {
    width: 16px;
    height: 16px;
  }

  th,
  td {
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid #e5e7eb;
    text-align: left;
  }

  tr.selected {
    background: #f8fafc;
  }

  .paper-cell {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .paper-name {
    font-weight: 600;
  }

  .twirl {
    background: transparent;
    border: none;
    font-size: 1rem;
    cursor: pointer;
    padding: 0;
    line-height: 1;
  }

  .feature-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }

  .status-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.2rem 0.5rem;
    border-radius: 999px;
    font-size: 0.78rem;
    background: #e5e7eb;
    color: #111827;
    text-transform: capitalize;
  }

  .status-chip.found {
    background: #dcfce7;
    color: #166534;
  }

  .status-chip.missing {
    background: #fee2e2;
    color: #991b1b;
  }

  .status-chip.running {
    background: #fef9c3;
    color: #854d0e;
  }

  .status-chip.error {
    background: #fee2e2;
    color: #b91c1c;
  }

  .detail-row td {
    background: #f9fafb;
  }

  .actions-cell {
    text-align: right;
  }

  .feature-details {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 0.75rem;
  }

  .detail-block {
    border: 1px solid #e5e7eb;
    border-radius: 0.65rem;
    padding: 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    background: white;
  }

  .detail-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .muted {
    color: #6b7280;
    margin: 0;
  }

  .detail-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
  }

  .sort-button {
    border: none;
    background: transparent;
    font-weight: 700;
    cursor: pointer;
    color: #0f172a;
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
  }
</style>
