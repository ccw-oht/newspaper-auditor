<script lang="ts">
  import { page } from '$app/stores';
  import { onDestroy, onMount } from 'svelte';
  import { cancelJob, clearJobQueue, fetchActiveJobItems, fetchActiveJobs, fetchQueueState, updateQueueState } from '$lib/api';
  import type { JobQueueItem, JobSummary } from '$lib/types';

  const navLinks = [
    { href: '/papers', label: 'Papers' },
    { href: '/imports', label: 'Imports' },
    { href: '/research', label: 'Research' },
    { href: '/history', label: 'History' }
  ];

  let queueJobs: JobSummary[] = [];
  let queueItems: JobQueueItem[] = [];
  let queuePaused = false;
  let queueError: string | null = null;
  let queueNotice: string | null = null;
  let queueExpanded = true;
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  async function refreshQueue() {
    try {
      const [jobs, items, state] = await Promise.all([fetchActiveJobs(), fetchActiveJobItems(), fetchQueueState()]);
      queueJobs = jobs;
      queueItems = items;
      queuePaused = state.paused;
      queueError = null;
    } catch (error) {
      console.error(error);
      queueError = 'Failed to refresh queue status.';
    }
  }

  async function toggleQueuePause() {
    try {
      const next = await updateQueueState(!queuePaused);
      queuePaused = next.paused;
      queueError = null;
      queueNotice = null;
    } catch (error) {
      console.error(error);
      queueError = 'Failed to update queue status.';
    }
  }

  async function handleCancel(jobId: number) {
    try {
      await cancelJob(jobId);
      await refreshQueue();
      queueNotice = 'Canceled pending job.';
    } catch (error) {
      console.error(error);
      queueError = 'Failed to cancel job.';
    }
  }

  async function handleClearQueue() {
    try {
      const result = await clearJobQueue();
      await refreshQueue();
      if (result.canceled_jobs || result.canceled_items) {
        queueNotice = `Queue cleared (${result.canceled_jobs} job${result.canceled_jobs === 1 ? '' : 's'}, ${result.canceled_items} item${result.canceled_items === 1 ? '' : 's'}).`;
      } else {
        queueNotice = 'No queued items to clear.';
      }
      queueError = null;
    } catch (error) {
      console.error(error);
      queueError = 'Failed to clear queue.';
    }
  }

  onMount(() => {
    refreshQueue();
    pollTimer = setInterval(refreshQueue, 5000);
  });

  onDestroy(() => {
    if (pollTimer) {
      clearInterval(pollTimer);
    }
  });
</script>

<svelte:head>
  <title>Newspaper Audit Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
</svelte:head>

<div class="app-shell">
  <header class="app-header">
    <div class="branding">
      <img src="/audit.png" alt="Newspaper Audit logo" class="logo" />
      <h1>Newspaper Audit Dashboard</h1>
    </div>
    <nav>
      {#each navLinks as link}
        <a
          href={link.href}
          class:active={$page.url.pathname.startsWith(link.href)}
        >
          {link.label}
        </a>
      {/each}
    </nav>
  </header>
  <main>
    <slot />
  </main>

  <aside class={`queue-panel${queueExpanded ? ' expanded' : ''}`} aria-live="polite">
    <button class="queue-toggle" type="button" on:click={() => (queueExpanded = !queueExpanded)}>
      {queueExpanded ? 'Hide queue' : 'Show queue'}
    </button>
    {#if queueExpanded}
      <div class="queue-card">
        <div class="queue-header">
          <div>
            <h2>Background queue</h2>
            <p class="queue-meta">
              {queuePaused ? 'Paused' : 'Running'} · {queueJobs.length} active
            </p>
          </div>
          <div class="queue-actions">
            <button type="button" on:click={toggleQueuePause}>
              {queuePaused ? 'Start' : 'Stop'}
            </button>
            <button type="button" on:click={handleClearQueue}>Clear queue</button>
            <a class="queue-link" href="/history">History</a>
          </div>
        </div>
        {#if queueError}
          <p class="queue-error">{queueError}</p>
        {/if}
        {#if queueNotice}
          <p class="queue-notice">{queueNotice}</p>
        {/if}
        {#if queueJobs.length === 0}
          <p class="queue-empty">No active jobs.</p>
        {:else}
          <ul class="queue-list">
            {#each queueJobs as job}
              <li>
                <div class="queue-job">
                  <div>
                    <strong>{job.job_type === 'audit' ? 'Audit' : 'Lookup'}</strong>
                    <span>#{job.id}</span>
                    <span class="queue-status">{job.status}</span>
                  </div>
                  <div class="queue-progress">
                    {job.processed_count}/{job.total_count}
                  </div>
                </div>
                {#if job.status === 'pending'}
                  <button type="button" class="queue-cancel" on:click={() => handleCancel(job.id)}>
                    Cancel pending
                  </button>
                {/if}
              </li>
            {/each}
          </ul>
        {/if}
        {#if queueItems.length > 0}
          <div class="queue-items">
            <div class="queue-items-header">Paper · Action · Status</div>
            <ul>
              {#each queueItems as item}
                <li>
                  <span class="queue-item-name">{item.paper_name ?? `Paper ${item.paper_id}`}</span>
                  <span>{item.job_type === 'audit' ? 'Audit' : 'Lookup'}</span>
                  <span class="queue-item-status">{item.status}</span>
                </li>
              {/each}
            </ul>
          </div>
        {/if}
      </div>
    {/if}
  </aside>
</div>

<style>
  :global(body) {
    margin: 0;
    font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background-color: #f3f4f6;
    color: #111827;
  }

  .app-shell {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  .app-header {
    background-color: #111827;
    color: white;
    padding: 1.5rem 2rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .branding {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .logo {
    height: 2.5rem;
    width: auto;
  }

  nav a {
    color: white;
    margin-left: 1rem;
    text-decoration: none;
    font-weight: 600;
  }

  nav a:hover {
    text-decoration: underline;
  }

  main {
    flex: 1;
    padding: 2rem;
  }

  .queue-panel {
    position: fixed;
    right: 1.5rem;
    bottom: 1.5rem;
    z-index: 30;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.5rem;
  }

  .queue-toggle {
    border: none;
    background: #111827;
    color: white;
    padding: 0.45rem 0.75rem;
    border-radius: 999px;
    font-weight: 600;
    cursor: pointer;
  }

  .queue-card {
    width: min(360px, 90vw);
    background: white;
    border-radius: 16px;
    padding: 1rem;
    box-shadow: 0 12px 30px rgba(15, 23, 42, 0.18);
    border: 1px solid #e5e7eb;
  }

  .queue-header {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-start;
  }

  .queue-header h2 {
    margin: 0;
    font-size: 1rem;
  }

  .queue-meta {
    margin: 0.25rem 0 0;
    color: #6b7280;
    font-size: 0.85rem;
  }

  .queue-actions {
    display: flex;
    gap: 0.4rem;
    align-items: center;
  }

  .queue-actions button,
  .queue-actions .queue-link {
    border: 1px solid #d1d5db;
    background: #f9fafb;
    color: #111827;
    border-radius: 0.5rem;
    padding: 0.35rem 0.6rem;
    font-size: 0.85rem;
    text-decoration: none;
    cursor: pointer;
  }

  .queue-actions button:hover,
  .queue-actions .queue-link:hover {
    background: #f3f4f6;
  }

  .queue-error {
    color: #dc2626;
    margin: 0.6rem 0 0;
    font-size: 0.85rem;
  }

  .queue-notice {
    color: #2563eb;
    margin: 0.6rem 0 0;
    font-size: 0.85rem;
  }

  .queue-empty {
    margin: 0.75rem 0 0;
    color: #6b7280;
    font-size: 0.85rem;
  }

  .queue-list {
    list-style: none;
    padding: 0;
    margin: 0.75rem 0 0;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .queue-job {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.9rem;
    gap: 0.5rem;
  }

  .queue-job span {
    color: #6b7280;
    font-size: 0.8rem;
    margin-left: 0.4rem;
  }

  .queue-status {
    text-transform: capitalize;
  }

  .queue-progress {
    font-variant-numeric: tabular-nums;
    font-size: 0.85rem;
    color: #111827;
  }

  .queue-cancel {
    margin-top: 0.35rem;
    border: none;
    background: #fee2e2;
    color: #991b1b;
    padding: 0.3rem 0.5rem;
    border-radius: 0.5rem;
    font-size: 0.8rem;
    cursor: pointer;
  }

  .queue-items {
    margin-top: 0.75rem;
    border-top: 1px solid #e5e7eb;
    padding-top: 0.6rem;
  }

  .queue-items-header {
    font-size: 0.75rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 0.35rem;
  }

  .queue-items ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    max-height: 180px;
    overflow-y: auto;
  }

  .queue-items li {
    display: grid;
    grid-template-columns: minmax(140px, 1fr) 60px 70px;
    gap: 0.5rem;
    font-size: 0.82rem;
    color: #374151;
  }

  .queue-item-name {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .queue-item-status {
    text-transform: capitalize;
  }

  @media (max-width: 640px) {
    .queue-panel {
      right: 1rem;
      left: 1rem;
      bottom: 1rem;
      align-items: stretch;
    }

    .queue-card {
      width: 100%;
    }

    .queue-header {
      flex-direction: column;
      align-items: flex-start;
    }
  }
</style>
