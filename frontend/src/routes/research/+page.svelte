<script lang="ts">
  import type { ResearchSessionSummary } from '$lib/types';

  export let data: {
    sessions: ResearchSessionSummary[];
  };

  function formatDate(value: string): string {
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
</script>

<div class="page">
  <header>
    <div>
      <h2>Research Sessions</h2>
      <p class="subtitle">Track saved subsets of papers and keyword feature findings.</p>
    </div>
    <a class="cta" href="/papers">Create from Papers</a>
  </header>

  {#if data.sessions.length === 0}
    <div class="empty-state">
      <p>No research sessions yet.</p>
      <p>Select papers on the Papers page, then choose “Save as Research Session”.</p>
    </div>
  {:else}
    <div class="session-grid">
      {#each data.sessions as session}
        <article class="session-card">
          <header>
            <div>
              <h3>{session.name}</h3>
              {#if session.description}
                <p class="description">{session.description}</p>
              {/if}
            </div>
            <a class="link" href={`/research/${session.id}`}>View</a>
          </header>
          <dl>
            <div>
              <dt>Created</dt>
              <dd>{formatDate(session.created_at)}</dd>
            </div>
            <div>
              <dt>Papers</dt>
              <dd>{session.paper_count}</dd>
            </div>
            <div>
              <dt>Features</dt>
              <dd>{session.feature_count}</dd>
            </div>
          </dl>
          {#if session.filter_params && Object.keys(session.filter_params).length > 0}
            <div class="filters">
              {#each Object.entries(session.filter_params) as entry}
                <span class="chip">{entry[0]}: {formatFilterValue(entry[1])}</span>
              {/each}
            </div>
          {/if}
        </article>
      {/each}
    </div>
  {/if}
</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  h2 {
    margin: 0;
  }

  .subtitle {
    margin: 0.25rem 0 0;
    color: #6b7280;
  }

  .cta {
    background-color: #2563eb;
    color: white;
    padding: 0.65rem 1.2rem;
    border-radius: 0.5rem;
    text-decoration: none;
    font-weight: 600;
  }

  .empty-state {
    background: white;
    border-radius: 0.75rem;
    padding: 1.5rem;
    border: 1px dashed #d1d5db;
    text-align: center;
    color: #4b5563;
  }

  .session-grid {
    display: grid;
    gap: 1.25rem;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  }

  .session-card {
    background: white;
    border-radius: 0.75rem;
    padding: 1rem 1.25rem;
    border: 1px solid #e5e7eb;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .session-card header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .session-card h3 {
    margin: 0;
  }

  .description {
    margin: 0.25rem 0 0;
    color: #4b5563;
  }

  .session-card dl {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 0.5rem;
    margin: 0;
  }

  .session-card dt {
    font-size: 0.8rem;
    color: #6b7280;
  }

  .session-card dd {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
  }

  .link {
    text-decoration: none;
    color: #2563eb;
    font-weight: 600;
  }

  .filters {
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
</style>

