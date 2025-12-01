<script lang="ts">
  import { runResearchFeatures } from '$lib/api';
  import type { ResearchSessionDetail, ResearchFeature, ResearchEvidenceItem } from '$lib/types';

  export let data: {
    session: ResearchSessionDetail;
  };

  let session: ResearchSessionDetail = data.session;
  let refreshAllLoading = false;
  let errorMessage: string | null = null;
  let featureLoading = new Set<number>();

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

  async function refreshFeatures(featureIds?: number[]) {
    try {
      if (!session) return;
      if (featureIds && featureIds.length === 1) {
        const next = new Set(featureLoading);
        next.add(featureIds[0]);
        featureLoading = next;
      } else {
        refreshAllLoading = true;
      }
      errorMessage = null;
      const updated = await runResearchFeatures(session.id, featureIds);
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
      } else {
        refreshAllLoading = false;
      }
    }
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

  <section class="features">
    <h3>Feature Findings</h3>
    <div class="feature-grid">
      {#each session.features as feature}
        <article class="feature-card">
          <header>
            <div>
              <h4>{feature.name}</h4>
              <p class="status">
                Status: <span class={`badge ${feature.status}`}>{feature.status}</span>
                <span class="timestamp">· {formatDate(feature.last_evaluated_at)}</span>
              </p>
            </div>
            <button
              type="button"
              on:click={() => refreshFeatures([feature.id])}
              disabled={featureLoading.has(feature.id)}
            >
              {featureLoading.has(feature.id) ? 'Refreshing…' : 'Refresh'}
            </button>
          </header>
          <p class="keywords">
            Keywords:
            {feature.keywords.join(', ')}
          </p>
          {#if feature.error}
            <p class="error">Error: {feature.error}</p>
          {/if}
          {#if matchesFor(feature).length === 0}
            <p>No evidence captured yet.</p>
          {:else}
            <ul class="evidence-list">
              {#each matchesFor(feature) as match}
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
        </article>
      {/each}
    </div>
  </section>

  <section class="papers">
    <h3>Paper Snapshot ({session.papers.length})</h3>
    <div class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>Paper</th>
            <th>Location</th>
            <th>Website</th>
            <th>Owner</th>
          </tr>
        </thead>
        <tbody>
          {#each session.papers as paper}
            <tr>
              <td>{snapshotValue(paper, 'paper_name') || '—'}</td>
              <td>{snapshotValue(paper, 'city') || '—'}, {snapshotValue(paper, 'state') || '—'}</td>
              <td>
                {#if snapshotValue(paper, 'website_url')}
                  <a href={snapshotValue(paper, 'website_url')} target="_blank" rel="noreferrer">
                    {snapshotValue(paper, 'website_url')}
                  </a>
                {:else}
                  —
                {/if}
              </td>
              <td>{snapshotValue(paper, 'chain_owner') || '—'}</td>
            </tr>
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

  .table-wrapper {
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  th,
  td {
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid #e5e7eb;
    text-align: left;
  }
</style>

