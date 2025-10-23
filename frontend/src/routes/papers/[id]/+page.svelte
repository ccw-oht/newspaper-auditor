<script lang="ts">
  /* eslint-env browser */
  import { goto, invalidateAll } from '$app/navigation';
  import { tick } from 'svelte';
  import { runAudit, updatePaper, fetchPaperDetail } from '$lib/api';
  import type { PaperDetail } from '$lib/types';
  import { formatRelativeTime } from '$lib/formatters';
  import { paperFilterQuery } from '$lib/stores/paperFilters';

  export let data: { detail: PaperDetail };

  let paper = data.detail;
  let saving = false;
  let auditing = false;
  let selectedAuditId = paper.latest_audit?.id ?? null;
  let selectedAudit: PaperDetail['audits'][number] | null = paper.audits[0] ?? null;
  let previewExpanded = false;
  let filterQuery = '';

  $: selectedAudit = paper.audits.find((audit) => audit.id === selectedAuditId) ?? paper.audits[0] ?? null;
  $: filterQuery = $paperFilterQuery;

  let form = buildFormValues(paper);

  const summaryFields: { key: keyof PaperDetail['audits'][number]; label: string }[] = [
    { key: 'has_pdf', label: 'Has PDF' },
    { key: 'pdf_only', label: 'PDF Only' },
    { key: 'paywall', label: 'Paywall' },
    { key: 'notices', label: 'Public Notices' },
    { key: 'responsive', label: 'Responsive' }
  ];

  $: auditSummary = selectedAudit
    ? (() => {
        const auditRecord = selectedAudit as unknown as Record<string, string | null | undefined>;
        return summaryFields.map(({ key, label }) => ({
          label,
          value: auditRecord[key as string] ?? '—'
        }));
      })()
    : [];

  $: auditNotes = selectedAudit?.notes
    ? selectedAudit.notes
        .split('|')
        .map((item) => item.trim())
        .filter(Boolean)
    : [];

  $: auditSources = selectedAudit?.sources
    ? selectedAudit.sources
        .split('+')
        .map((item) => item.trim())
        .filter(Boolean)
    : [];

  function statusClass(value: string | null | undefined) {
    const normalized = (value ?? '').toLowerCase();
    if (normalized.startsWith('yes')) return 'status yes';
    if (normalized.startsWith('no')) return 'status no';
    if (normalized.startsWith('manual')) return 'status review';
    return 'status neutral';
  }

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

  async function backToList() {
    const query = filterQuery.trim();
    const target = query ? `/papers?${query}` : '/papers';
    await goto(target);
  }
</script>

<section class="detail">
  <div class="header">
    <div>
      <button class="back" type="button" on:click={backToList}>← Back to list</button>
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
          <div class="audit-meta">
            <div>
              <span class="meta-label">Audit time</span>
              <span class="meta-value">{new Date(selectedAudit.timestamp).toLocaleString()}</span>
            </div>
            <div>
              <span class="meta-label">Chain owner</span>
              <span class="meta-value">{selectedAudit.chain_owner ?? '—'}</span>
            </div>
            <div>
              <span class="meta-label">CMS platform</span>
              <span class="meta-value">{selectedAudit.cms_platform ?? '—'}</span>
            </div>
            <div>
              <span class="meta-label">CMS vendor</span>
              <span class="meta-value">{selectedAudit.cms_vendor ?? '—'}</span>
            </div>
          </div>

          <div class="status-grid">
            {#each auditSummary as field}
              <div class={`status-card ${statusClass(field.value)}`}>
                <span class="label">{field.label}</span>
                <span class="value">{field.value}</span>
              </div>
            {/each}
          </div>

          <div class="sources">
            <h4>Sources</h4>
            {#if auditSources.length === 0}
              <p class="empty">—</p>
            {:else}
              <div class="badges">
                {#each auditSources as source}
                  <span class="badge">{source}</span>
                {/each}
              </div>
            {/if}
          </div>

          <div class="notes">
            <h4>Notes</h4>
            {#if auditNotes.length === 0}
              <p class="empty">—</p>
            {:else}
              <ul>
                {#each auditNotes as note}
                  <li>{note}</li>
                {/each}
              </ul>
            {/if}
          </div>
        {:else}
          <p class="empty">Select an audit to view details.</p>
        {/if}
      </div>

      <div class="panel preview">
        <h3>Homepage preview</h3>
        {#if selectedAudit?.homepage_html}
          <div class={`preview-frame ${previewExpanded ? 'expanded' : ''}`}>
            <iframe title="Homepage preview" srcdoc={selectedAudit.homepage_html} />
            {#if !previewExpanded}
              <div class="fade"></div>
            {/if}
          </div>
          <button class="toggle-preview" type="button" on:click={() => (previewExpanded = !previewExpanded)}>
            {previewExpanded ? 'Collapse preview' : 'Expand preview'}
          </button>
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
    border: none;
  }

  .preview-frame {
    position: relative;
    border: 1px solid #d1d5db;
    border-radius: 0.75rem;
    overflow: hidden;
    max-height: 420px;
  }

  .preview-frame.expanded {
    max-height: none;
  }

  .preview-frame iframe {
    width: 100%;
    height: 100%;
    min-height: 480px;
  }

  .preview-frame .fade {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 80px;
    background: linear-gradient(transparent, rgba(255, 255, 255, 0.95));
    pointer-events: none;
  }

  .toggle-preview {
    margin-top: 0.5rem;
    align-self: flex-start;
    border: none;
    background: none;
    color: #2563eb;
    font-weight: 600;
    cursor: pointer;
  }

  .audit-meta {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .meta-label {
    font-size: 0.75rem;
    text-transform: uppercase;
    color: #6b7280;
    letter-spacing: 0.05em;
  }

  .meta-value {
    font-weight: 600;
    color: #111827;
  }

  .status-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 0.75rem;
    margin-bottom: 1rem;
  }

  .status-card {
    border-radius: 0.75rem;
    padding: 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    box-shadow: inset 0 0 0 1px #e5e7eb;
    background: #f9fafb;
  }

  .status-card .label {
    font-size: 0.75rem;
    text-transform: uppercase;
    color: #6b7280;
    letter-spacing: 0.05em;
  }

  .status-card .value {
    font-weight: 700;
    font-size: 1rem;
  }

  .status.yes {
    box-shadow: inset 0 0 0 1px rgba(22, 163, 74, 0.25);
    background: rgba(220, 252, 231, 0.7);
    color: #166534;
  }

  .status.no {
    box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.25);
    background: rgba(254, 226, 226, 0.7);
    color: #b91c1c;
  }

  .status.review {
    box-shadow: inset 0 0 0 1px rgba(245, 158, 11, 0.25);
    background: rgba(254, 243, 199, 0.7);
    color: #b45309;
  }

  .status.neutral {
    box-shadow: inset 0 0 0 1px #e5e7eb;
    background: #f9fafb;
    color: #374151;
  }

  .sources,
  .notes {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .sources h4,
  .notes h4 {
    margin: 0;
    font-size: 0.95rem;
    color: #1f2937;
  }

  .badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .badge {
    padding: 0.25rem 0.6rem;
    border-radius: 999px;
    background: #e0f2fe;
    color: #0c4a6e;
    font-size: 0.8rem;
    font-weight: 600;
  }

  .notes ul {
    margin: 0;
    padding-left: 1.25rem;
    color: #374151;
  }

  .notes li {
    margin-bottom: 0.35rem;
  }

  @media (max-width: 960px) {
    .content {
      grid-template-columns: 1fr;
    }
  }
</style>
