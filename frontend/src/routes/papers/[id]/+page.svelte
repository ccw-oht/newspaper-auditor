<script lang="ts">
  /* eslint-env browser */
  import { goto, invalidateAll } from '$app/navigation';
  import { tick } from 'svelte';
  import { runAudit, updatePaper, fetchPaperDetail } from '$lib/api';
  import type { PaperDetail } from '$lib/types';
  import { formatRelativeTime } from '$lib/formatters';

  export let data: { detail: PaperDetail };

  let paper = data.detail;
  let saving = false;
  let auditing = false;
  let selectedAuditId = paper.latest_audit?.id ?? null;
  let selectedAudit: PaperDetail['audits'][number] | null = paper.audits[0] ?? null;

  $: selectedAudit = paper.audits.find((audit) => audit.id === selectedAuditId) ?? paper.audits[0] ?? null;

  let form = buildFormValues(paper);

  function buildFormValues(current: PaperDetail) {
    return {
      state: current.state ?? '',
      city: current.city ?? '',
      paper_name: current.paper_name ?? '',
      website_url: current.website_url ?? '',
      phone: current.phone ?? '',
      mailing_address: current.mailing_address ?? '',
      county: current.county ?? ''
    };
  }

  async function save() {
    try {
      saving = true;
      const payload = Object.fromEntries(
        Object.entries(form).map(([key, value]) => [key, value.trim() ? value.trim() : null])
      );
      const updated = await updatePaper(paper.id, payload);
      paper = updated;
      form = buildFormValues(paper);
      await invalidateAll();
    } catch (error) {
      console.error(error);
      window.alert('Failed to update paper');
    } finally {
      saving = false;
    }
  }

  async function rerunAudit() {
    try {
      auditing = true;
      await runAudit(paper.id);
      await invalidateAll();
      paper = await fetchPaperDetail(paper.id);
      form = buildFormValues(paper);
      selectedAuditId = paper.latest_audit?.id ?? selectedAuditId;
      await tick();
      scrollPreviewIntoView();
    } catch (error) {
      console.error(error);
      window.alert('Failed to re-run audit');
    } finally {
      auditing = false;
    }
  }

  function viewAudit(id: number) {
    selectedAuditId = id;
  }

  function scrollPreviewIntoView() {
    const previewElement = document.querySelector('.preview');
    previewElement?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
</script>

<section class="detail">
  <div class="header">
    <div>
      <button class="back" type="button" on:click={() => goto('/papers')}>← Back to list</button>
      <h2>{paper.paper_name ?? 'Untitled Paper'}</h2>
      <p class="meta">
        {paper.city ?? 'Unknown city'}{paper.state ? `, ${paper.state}` : ''}
      </p>
    </div>
    <button class="audit" type="button" disabled={auditing} on:click={rerunAudit}>
      {auditing ? 'Running…' : 'Re-run audit'}
    </button>
  </div>

  <div class="content">
    <aside class="sidebar">
      <form class="panel" on:submit|preventDefault={save}>
        <h3>Contact details</h3>
        <label>
          Paper name
          <input bind:value={form.paper_name} />
        </label>
        <label>
          City
          <input bind:value={form.city} />
        </label>
        <label>
          State
          <input bind:value={form.state} maxlength="2" />
        </label>
        <label>
          Website URL
          <input bind:value={form.website_url} />
        </label>
        <label>
          Phone
          <input bind:value={form.phone} />
        </label>
        <label>
          Mailing address
          <textarea rows="3" bind:value={form.mailing_address} />
        </label>
        <label>
          County
          <input bind:value={form.county} />
        </label>
        <button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save changes'}</button>
      </form>

      <div class="panel history">
        <h3>Audit history</h3>
        {#if paper.audits.length === 0}
          <p class="empty">No audits yet.</p>
        {:else}
          <ul>
            {#each paper.audits as audit}
              <li class:selected={audit.id === selectedAuditId}>
                <button type="button" on:click={() => viewAudit(audit.id)}>
                  <span class="timestamp">{formatRelativeTime(audit.timestamp)}</span>
                  <span class="summary">
                    {audit.has_pdf ?? '—'} / {audit.paywall ?? '—'} / {audit.responsive ?? '—'}
                  </span>
                </button>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    </aside>

    <section class="main">
      <div class="panel audit-info" aria-live="polite">
        <h3>Audit details</h3>
        {#if selectedAudit}
          <dl>
            <div>
              <dt>Audit time</dt>
              <dd>{new Date(selectedAudit.timestamp).toLocaleString()}</dd>
            </div>
            <div>
              <dt>Has PDF</dt>
              <dd>{selectedAudit.has_pdf ?? '—'}</dd>
            </div>
            <div>
              <dt>PDF only</dt>
              <dd>{selectedAudit.pdf_only ?? '—'}</dd>
            </div>
            <div>
              <dt>Paywall</dt>
              <dd>{selectedAudit.paywall ?? '—'}</dd>
            </div>
            <div>
              <dt>Public notices</dt>
              <dd>{selectedAudit.notices ?? '—'}</dd>
            </div>
            <div>
              <dt>Responsive</dt>
              <dd>{selectedAudit.responsive ?? '—'}</dd>
            </div>
            <div>
              <dt>Chain owner</dt>
              <dd>{selectedAudit.chain_owner ?? '—'}</dd>
            </div>
            <div>
              <dt>CMS platform</dt>
              <dd>{selectedAudit.cms_platform ?? '—'}</dd>
            </div>
            <div>
              <dt>CMS vendor</dt>
              <dd>{selectedAudit.cms_vendor ?? '—'}</dd>
            </div>
            <div>
              <dt>Sources</dt>
              <dd>{selectedAudit.sources ?? '—'}</dd>
            </div>
            <div>
              <dt>Notes</dt>
              <dd>{selectedAudit.notes ?? '—'}</dd>
            </div>
          </dl>
        {:else}
          <p class="empty">Select an audit to view details.</p>
        {/if}
      </div>

      <div class="panel preview">
        <h3>Homepage preview</h3>
        {#if selectedAudit?.homepage_html}
          <iframe title="Homepage preview" srcdoc={selectedAudit.homepage_html} />
        {:else}
          <p class="empty">No snapshot captured for this audit.</p>
        {/if}
      </div>
    </section>
  </div>
</section>

<style>
  .detail {
    display: flex;
    flex-direction: column;
    gap: 2rem;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }

  .back {
    background: none;
    border: none;
    color: #2563eb;
    cursor: pointer;
    font-size: 0.95rem;
    margin-bottom: 0.5rem;
  }

  .audit {
    background-color: #2563eb;
    color: white;
    border: none;
    border-radius: 0.5rem;
    padding: 0.65rem 1rem;
    font-weight: 600;
    cursor: pointer;
  }

  .content {
    display: grid;
    grid-template-columns: 320px 1fr;
    gap: 1.5rem;
    align-items: start;
  }

  .panel {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 0.75rem;
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  form.panel label {
    font-size: 0.85rem;
    font-weight: 600;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  input,
  textarea {
    border-radius: 0.5rem;
    border: 1px solid #d1d5db;
    padding: 0.5rem 0.75rem;
    font-size: 0.95rem;
  }

  form.panel button {
    margin-top: 0.5rem;
    padding: 0.6rem 0.75rem;
    background: #10b981;
    color: white;
    border: none;
    border-radius: 0.5rem;
    font-weight: 600;
    cursor: pointer;
  }

  .history ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .history li button {
    width: 100%;
    text-align: left;
    border: 1px solid #d1d5db;
    border-radius: 0.5rem;
    padding: 0.5rem;
    background: none;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .history li.selected button {
    border-color: #2563eb;
    background: #eff6ff;
  }

  .timestamp {
    font-weight: 600;
    font-size: 0.85rem;
    color: #1f2937;
  }

  .summary {
    color: #4b5563;
    font-size: 0.8rem;
  }

  .empty {
    color: #6b7280;
  }

  .main {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .preview iframe {
    width: 100%;
    min-height: 480px;
    border: 1px solid #d1d5db;
    border-radius: 0.5rem;
  }

  dl {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
  }

  dt {
    font-size: 0.75rem;
    text-transform: uppercase;
    color: #6b7280;
  }

  dd {
    margin: 0;
    font-weight: 600;
    color: #111827;
  }

  @media (max-width: 960px) {
    .content {
      grid-template-columns: 1fr;
    }
  }
</style>
