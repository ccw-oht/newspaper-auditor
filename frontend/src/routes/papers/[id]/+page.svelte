<script lang="ts">
  /* eslint-env browser */
  import { goto, invalidateAll } from '$app/navigation';
  import { enqueueAuditJob, enqueueLookupJob, updatePaper, fetchPaperDetail, clearAuditResults } from '$lib/api';
  import type { PaperDetail, AuditSummary } from '$lib/types';
  import { formatRelativeTime } from '$lib/formatters';
  import { paperFilterQuery } from '$lib/stores/paperFilters';

  export let data: { detail: PaperDetail };

  let paper = data.detail;
  let saving = false;
  let auditing = false;
  let lookingUp = false;
  let lookupError: string | null = null;
  let clearing = false;
  let overrideSaving = false;
  let overrideError: string | null = null;
  let toastMessage: string | null = null;
  let toastTimer: ReturnType<typeof setTimeout> | null = null;
  let selectedAuditId = paper.latest_audit?.id ?? null;
  let selectedAudit: PaperDetail['audits'][number] | null = paper.audits[0] ?? null;
  let currentAudit: (PaperDetail['audits'][number] & { overrides?: Record<string, string | null | undefined> | null }) | (AuditSummary & { overrides?: Record<string, string | null | undefined> | null }) | null = paper.latest_audit ?? selectedAudit;
  let filterQuery = '';
  let lookupInfo: Record<string, unknown> | null = null;
  let lookupLogs: Record<string, unknown> | null = null;
  let primaryContact = '';
  let socialMediaText = '';

  $: selectedAudit = paper.audits.find((audit) => audit.id === selectedAuditId) ?? paper.audits[0] ?? null;

  $: currentAudit = (() => {
    if (paper.latest_audit && (selectedAuditId === null || selectedAuditId === paper.latest_audit.id)) {
      return paper.latest_audit;
    }
    return selectedAudit ?? paper.latest_audit ?? null;
  })();
  $: filterQuery = $paperFilterQuery;
  $: lookupInfo = (paper.extra_data?.contact_lookup as Record<string, unknown> | undefined) ?? null;
  $: lookupLogs = (lookupInfo?.logs as Record<string, unknown> | undefined) ?? null;

  let form = buildFormValues(paper);
  setContactExtrasFromPaper();

  const summaryFields: { key: keyof PaperDetail['audits'][number]; label: string }[] = [
    { key: 'has_pdf', label: 'Has PDF' },
    { key: 'pdf_only', label: 'PDF Only' },
    { key: 'paywall', label: 'Paywall' },
    { key: 'notices', label: 'Public Notices' },
    { key: 'responsive', label: 'Responsive' }
  ];

  type OverrideKey =
    | 'has_pdf'
    | 'pdf_only'
    | 'paywall'
    | 'notices'
    | 'responsive'
    | 'cms_platform'
    | 'cms_vendor';

  const overrideConfig: { key: OverrideKey; label: string; type: 'select' | 'text' }[] = [
    { key: 'has_pdf', label: 'Has PDF', type: 'select' },
    { key: 'pdf_only', label: 'PDF Only', type: 'select' },
    { key: 'paywall', label: 'Paywall', type: 'select' },
    { key: 'notices', label: 'Public Notices', type: 'select' },
    { key: 'responsive', label: 'Responsive', type: 'select' },
    { key: 'cms_platform', label: 'CMS platform', type: 'text' },
    { key: 'cms_vendor', label: 'CMS vendor', type: 'text' }
  ];

  const overrideSelectOptions = ['', 'Yes', 'No', 'Manual Review'];

  function buildOverrideForm(overrides: Record<string, string | null | undefined> | null | undefined) {
    const initial: Record<OverrideKey, string> = {
      has_pdf: '',
      pdf_only: '',
      paywall: '',
      notices: '',
      responsive: '',
      cms_platform: '',
      cms_vendor: ''
    };
    if (!overrides) return initial;
    overrideConfig.forEach(({ key }) => {
      const value = overrides[key];
      if (typeof value === 'string') {
        initial[key] = value;
      } else if (value != null) {
        initial[key] = String(value);
      }
    });
    return initial;
  }

  let overrideForm = buildOverrideForm(paper.audit_overrides ?? paper.latest_audit?.overrides ?? null);

  $: auditSummary = currentAudit
    ? (() => {
        const auditRecord = currentAudit as unknown as Record<string, string | null | undefined>;
        const overrides = (currentAudit?.overrides ?? {}) as Record<string, string | null | undefined>;
        return summaryFields.map(({ key, label }) => ({
          key,
          label,
          value: auditRecord[key as string] ?? '—',
          overridden: overrides[key as string] !== undefined
        }));
      })()
    : [];

  $: auditNotes = currentAudit?.notes
    ? currentAudit.notes
        .split('|')
        .map((item) => item.trim())
        .filter(Boolean)
    : [];

  $: auditSources = currentAudit?.sources
    ? currentAudit.sources
        .split('+')
        .map((item) => item.trim())
        .filter(Boolean)
    : [];

  function statusClass(key: string, value: string | null | undefined) {
    const normalized = (value ?? '').toString().trim().toLowerCase();
    if (!normalized || normalized === '—') return 'status neutral';
    if (normalized.startsWith('manual')) return 'status review';
    const invert = key === 'pdf_only';
    if (normalized.startsWith('yes')) {
      return invert ? 'status no' : 'status yes';
    }
    if (normalized.startsWith('no')) {
      return invert ? 'status yes' : 'status no';
    }
    return 'status neutral';
  }

  function buildFormValues(current: PaperDetail) {
    return {
      state: current.state ?? '',
      city: current.city ?? '',
      paper_name: current.paper_name ?? '',
      website_url: current.website_url ?? '',
      chain_owner: current.chain_owner ?? '',
      phone: current.phone ?? '',
      email: current.email ?? '',
      mailing_address: current.mailing_address ?? '',
      county: current.county ?? ''
    };
  }

  function formatJson(value: unknown): string {
    return JSON.stringify(value, null, 2);
  }

  function setContactExtrasFromPaper() {
    const value = safeString((paper.extra_data?.contact_lookup as Record<string, unknown> | undefined)?.primary_contact);
    primaryContact = value ?? '';
    const socialLinks = (paper.extra_data?.contact_lookup as Record<string, unknown> | undefined)?.social_media_links;
    if (Array.isArray(socialLinks)) {
      socialMediaText = socialLinks
        .filter((item) => typeof item === 'string' && item.trim())
        .map((item) => item.trim())
        .join('\n');
    } else {
      socialMediaText = '';
    }
  }

  async function save() {
    try {
      saving = true;
      const payload = Object.fromEntries(
        Object.entries(form).map(([key, value]) => [key, value.trim() ? value.trim() : null])
      );
      const primaryContactValue = primaryContact.trim();
      const socialLinks = parseSocialMediaLinks(socialMediaText);
      if (primaryContactValue) {
        const lookupPayload = {
          ...(lookupInfo ?? {}),
          primary_contact: primaryContactValue,
          social_media_links: socialLinks.length > 0 ? socialLinks : undefined
        };
        payload.extra_data = { contact_lookup: lookupPayload };
      } else if (socialLinks.length > 0) {
        const lookupPayload = {
          ...(lookupInfo ?? {}),
          social_media_links: socialLinks
        };
        payload.extra_data = { contact_lookup: lookupPayload };
      }
      const updated = await updatePaper(paper.id, payload);
      paper = updated;
      form = buildFormValues(paper);
      setContactExtrasFromPaper();
      overrideForm = buildOverrideForm(paper.audit_overrides ?? paper.latest_audit?.overrides ?? null);
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
      await enqueueAuditJob([paper.id]);
      showToast(`Queued audit for ${paper.paper_name ?? `Paper ${paper.id}`}.`);
    } catch (error) {
      console.error(error);
      window.alert('Failed to re-run audit');
    } finally {
      auditing = false;
    }
  }

  async function clearAudit() {
    if (clearing) return;
    const confirmed = window.confirm('Clear all stored audit results for this paper?');
    if (!confirmed) return;

    try {
      clearing = true;
      await clearAuditResults(paper.id);
      await invalidateAll();
      paper = await fetchPaperDetail(paper.id);
      form = buildFormValues(paper);
      setContactExtrasFromPaper();
      selectedAuditId = paper.latest_audit?.id ?? null;
      overrideForm = buildOverrideForm(paper.audit_overrides ?? paper.latest_audit?.overrides ?? null);
    } catch (error) {
      console.error(error);
      window.alert('Failed to clear audit data');
    } finally {
      clearing = false;
    }
  }

  async function runLookupForPaper() {
    if (lookingUp) return;
    lookupError = null;
    try {
      lookingUp = true;
      await enqueueLookupJob([paper.id]);
      showToast(`Queued lookup for ${paper.paper_name ?? `Paper ${paper.id}`}.`);
    } catch (error) {
      console.error(error);
      lookupError = error instanceof Error ? error.message : 'Failed to run lookup';
    } finally {
      lookingUp = false;
    }
  }

  function viewAudit(id: number) {
    selectedAuditId = id;
  }


  async function backToList() {
    const query = filterQuery.trim();
    const target = query ? `/papers?${query}` : '/papers';
    await goto(target);
  }

  function normalizedWebsiteUrl(url: string | null | undefined): string | null {
    if (!url) return null;
    const trimmed = url.trim();
    if (!trimmed) return null;
    if (/^[a-zA-Z][a-zA-Z0-9+\-.]*:/.test(trimmed)) {
      return trimmed;
    }
    return `https://${trimmed.replace(/^\/+/, '')}`;
  }

  function safeString(value: unknown): string | null {
    if (typeof value !== 'string') return null;
    const trimmed = value.trim();
    return trimmed ? trimmed : null;
  }

  function parseSocialMediaLinks(value: string): string[] {
    return value
      .split(/[\n,]+/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function lookupLinks(): string[] {
    if (!lookupInfo) return [];
    const sources = lookupInfo.source_links;
    if (!Array.isArray(sources)) return [];
    return sources.filter((value) => typeof value === 'string' && value.trim()).map((value) => value.trim());
  }

  function lookupSocialLinks(): string[] {
    if (!lookupInfo) return [];
    const links = lookupInfo.social_media_links;
    if (!Array.isArray(links)) return [];
    return links.filter((value) => typeof value === 'string' && value.trim()).map((value) => value.trim());
  }

  function lookupQueries(): string[] {
    if (!lookupInfo) return [];
    const queries = lookupInfo.web_search_queries;
    if (!Array.isArray(queries)) return [];
    return queries.filter((value) => typeof value === 'string' && value.trim()).map((value) => value.trim());
  }

  function lookupUsageEntries(): { label: string; value: string }[] {
    if (!lookupInfo) return [];
    const usage = lookupInfo.usage_metadata as Record<string, unknown> | undefined;
    if (!usage) return [];
    const entries: { label: string; value: string }[] = [];
    const keys: Array<[string, string]> = [
      ['prompt_token_count', 'Prompt tokens'],
      ['candidates_token_count', 'Completion tokens'],
      ['total_token_count', 'Total tokens'],
      ['tool_use_prompt_token_count', 'Tool prompt tokens'],
      ['thoughts_token_count', 'Thoughts tokens']
    ];
    keys.forEach(([key, label]) => {
      const value = usage[key];
      if (value !== undefined && value !== null) {
        entries.push({ label, value: String(value) });
      }
    });
    return entries;
  }

  async function saveOverrides() {
    if (overrideSaving) return;
    overrideSaving = true;
    overrideError = null;
    try {
      const overridesPayload: Record<string, string> = {};
      overrideConfig.forEach(({ key, type }) => {
        const rawValue = overrideForm[key];
        if (type === 'select') {
          if (rawValue && rawValue.trim()) {
            overridesPayload[key] = rawValue.trim();
          }
        } else {
          const cleaned = rawValue?.trim();
          if (cleaned) {
            overridesPayload[key] = cleaned;
          }
        }
      });

      await updatePaper(paper.id, {
        audit_overrides: Object.keys(overridesPayload).length > 0 ? overridesPayload : null
      });

      paper = await fetchPaperDetail(paper.id);
      form = buildFormValues(paper);
      overrideForm = buildOverrideForm(paper.audit_overrides ?? paper.latest_audit?.overrides ?? null);
      selectedAuditId = paper.latest_audit?.id ?? selectedAuditId;
      await invalidateAll();
    } catch (error) {
      console.error(error);
      overrideError = error instanceof Error ? error.message : 'Failed to save overrides';
    } finally {
      overrideSaving = false;
    }
  }

  function showToast(message: string) {
    toastMessage = message;
    if (toastTimer) {
      clearTimeout(toastTimer);
    }
    toastTimer = setTimeout(() => {
      toastMessage = null;
      toastTimer = null;
    }, 3000);
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
    <div class="header-actions">
      <button class="audit" type="button" disabled={auditing} on:click={rerunAudit}>
        {auditing ? 'Running…' : 'Re-run audit'}
      </button>
      <button
        class={`audit secondary${lookupInfo ? ' lookup-done' : ''}`}
        type="button"
        disabled={lookingUp}
        on:click={runLookupForPaper}
      >
        {lookingUp ? 'Looking…' : 'Run lookup'}
      </button>
      <button class="audit secondary" type="button" disabled={clearing} on:click={clearAudit}>
        {clearing ? 'Clearing…' : 'Clear audit data'}
      </button>
    </div>
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
          Chain owner
          <input bind:value={form.chain_owner} />
        </label>
        <label>
          Phone
          <input bind:value={form.phone} />
        </label>
        <label>
          Primary Contact
          <input bind:value={primaryContact} placeholder="Add primary contact" />
        </label>
        <label>
          Social media links
          <textarea rows="3" bind:value={socialMediaText} placeholder="https://..." />
        </label>
        <label>
          Email
          <input bind:value={form.email} />
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

      <div class="panel lookup">
        <h3>Lookup sources</h3>
        {#if lookupInfo}
          <p class="meta">
            <strong>Last lookup:</strong>
            {safeString(lookupInfo.last_lookup_at) ?? 'Unknown'}
          </p>
          <dl class="lookup-list">
            <div>
              <dt>Contact name</dt>
              <dd>{safeString(lookupInfo.contact_name) ?? '—'}</dd>
            </div>
            <div>
              <dt>Primary contact</dt>
              <dd>{safeString(lookupInfo.primary_contact) ?? '—'}</dd>
            </div>
            <div>
              <dt>Website</dt>
              <dd>{safeString(lookupInfo.website) ?? '—'}</dd>
            </div>
            <div>
              <dt>Chain owner</dt>
              <dd>{safeString(lookupInfo.chain_owner) ?? '—'}</dd>
            </div>
            <div>
              <dt>Publication frequency</dt>
              <dd>{safeString(lookupInfo.publication_frequency) ?? '—'}</dd>
            </div>
            <div>
              <dt>County</dt>
              <dd>{safeString(lookupInfo.county) ?? '—'}</dd>
            </div>
            <div>
              <dt>Phone</dt>
              <dd>{safeString(lookupInfo.phone) ?? '—'}</dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>{safeString(lookupInfo.email) ?? '—'}</dd>
            </div>
            <div>
              <dt>Mailing address</dt>
              <dd>{safeString(lookupInfo.mailing_address) ?? '—'}</dd>
            </div>
            <div>
              <dt>Social media</dt>
              <dd>
                {#if lookupSocialLinks().length > 0}
                  {#each lookupSocialLinks() as link, index}
                    <a href={link} target="_blank" rel="noreferrer">{link}</a>{index < lookupSocialLinks().length - 1 ? ', ' : ''}
                  {/each}
                {:else}
                  —
                {/if}
              </dd>
            </div>
          </dl>
          {#if safeString(lookupInfo.wikipedia_link)}
            <a class="link" href={safeString(lookupInfo.wikipedia_link) ?? undefined} target="_blank" rel="noreferrer">
              Wikipedia
            </a>
          {/if}
          {#if lookupLinks().length > 0}
            <div class="links">
              <h4>Source links</h4>
              {#each lookupLinks() as link}
                <a href={link} target="_blank" rel="noreferrer">{link}</a>
              {/each}
            </div>
          {:else}
            <p class="empty">No source links captured.</p>
          {/if}
          {#if lookupQueries().length > 0}
            <div class="lookup-meta">
              <h4>Search queries</h4>
              <ul>
                {#each lookupQueries() as query}
                  <li>{query}</li>
                {/each}
              </ul>
            </div>
          {/if}
          {#if lookupUsageEntries().length > 0}
            <div class="lookup-meta">
              <h4>Usage</h4>
              <ul>
                {#each lookupUsageEntries() as entry}
                  <li>{entry.label}: {entry.value}</li>
                {/each}
              </ul>
            </div>
          {/if}
          {#if lookupLogs}
            <details class="lookup-logs">
              <summary>Full lookup prompt + response</summary>
              <pre>{formatJson(lookupLogs)}</pre>
            </details>
          {/if}
        {:else}
          <p class="empty">No lookup run yet.</p>
        {/if}
        {#if lookupError}
          <p class="error">{lookupError}</p>
        {/if}
      </div>

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
        {#if currentAudit}
          <div class="audit-meta">
            <div>
              <span class="meta-label">Audit time</span>
              <span class="meta-value">{currentAudit.timestamp ? new Date(currentAudit.timestamp).toLocaleString() : '—'}</span>
            </div>
            <div>
              <span class="meta-label">CMS platform</span>
              <span class="meta-value">{currentAudit.cms_platform ?? '—'}</span>
            </div>
            <div>
              <span class="meta-label">CMS vendor</span>
              <span class="meta-value">{currentAudit.cms_vendor ?? '—'}</span>
            </div>
            <div>
              <span class="meta-label">Frequency</span>
              <span class="meta-value">{paper.publication_frequency ?? '—'}</span>
            </div>
          </div>

          <div class="status-grid">
            {#each auditSummary as field}
              <div class={`status-card ${statusClass(field.key, field.value)}${field.overridden ? ' overridden' : ''}`}>
                <span class="label">
                  {field.label}
                  {#if field.overridden}
                    <span class="override-flag">Override</span>
                  {/if}
                </span>
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
          <div class="preview-frame">
            <iframe
              title="Homepage preview"
              srcdoc={selectedAudit.homepage_html}
              sandbox=""
              referrerpolicy="no-referrer"
            />
          </div>
        {:else}
          <p class="empty">No snapshot captured for this audit.</p>
        {/if}
        {#if normalizedWebsiteUrl(paper.website_url)}
          <a
            class="visit-site"
            href={normalizedWebsiteUrl(paper.website_url) ?? undefined}
            target="_blank"
            rel="noreferrer"
          >
            Visit Site
          </a>
        {/if}
      </div>

      <div class="panel overrides">
        <h3>Audit overrides</h3>
        <p class="hint">Use these fields to override automated audit results. Leave blank to rely on the latest audit.</p>
        <form class="override-form" on:submit|preventDefault={saveOverrides}>
          <div class="override-grid">
            {#each overrideConfig as field}
              <label>
                {field.label}
                {#if field.type === 'select'}
                  <select bind:value={overrideForm[field.key]}>
                    {#each overrideSelectOptions as option}
                      <option value={option}>{option || 'Use audit result'}</option>
                    {/each}
                  </select>
                {:else}
                  <input type="text" bind:value={overrideForm[field.key]} placeholder="Use audit result" />
                {/if}
              </label>
            {/each}
          </div>
          {#if overrideError}
            <p class="error">{overrideError}</p>
          {/if}
          <button type="submit" class="override-save" disabled={overrideSaving}>
            {overrideSaving ? 'Saving…' : 'Save overrides'}
          </button>
        </form>
      </div>
    </section>
  </div>
</section>

{#if toastMessage}
  <div class="toast" role="status" aria-live="polite">{toastMessage}</div>
{/if}

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

  .audit:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  .audit.secondary {
    background-color: #f3f4f6;
    color: #1f2937;
    border: 1px solid #d1d5db;
  }

  .audit.secondary.lookup-done {
    background-color: #16a34a;
    border-color: #15803d;
    color: #ffffff;
  }

  .audit.secondary[disabled] {
    color: #9ca3af;
  }

  .header-actions {
    display: flex;
    gap: 0.75rem;
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

  .toast {
    position: fixed;
    bottom: 1.5rem;
    left: 50%;
    transform: translateX(-50%);
    background: #111827;
    color: white;
    padding: 0.75rem 1.25rem;
    border-radius: 999px;
    font-weight: 600;
    box-shadow: 0 10px 20px rgba(15, 23, 42, 0.25);
    z-index: 40;
  }

  @media (max-width: 640px) {
    .toast {
      left: 1rem;
      right: 1rem;
      transform: none;
      text-align: center;
    }
  }

  .panel.lookup .meta {
    margin: 0;
    color: #374151;
    font-size: 0.9rem;
  }

  .panel.lookup .link {
    color: #2563eb;
    font-weight: 600;
    text-decoration: none;
  }

  .panel.lookup .links {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .panel.lookup .links a {
    color: #2563eb;
    font-size: 0.85rem;
    text-decoration: none;
    word-break: break-word;
  }

  .lookup-meta {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .lookup-meta h4 {
    margin: 0;
    font-size: 0.85rem;
    color: #111827;
  }

  .panel.lookup .links h4 {
    margin: 0;
    font-size: 0.85rem;
    color: #111827;
  }

  .lookup-meta ul {
    margin: 0;
    padding-left: 1.1rem;
    color: #4b5563;
    font-size: 0.85rem;
  }

  .lookup-logs summary {
    cursor: pointer;
    font-weight: 600;
  }

  .lookup-logs pre {
    margin-top: 0.75rem;
  }

  .lookup-list {
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .lookup-list div {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    font-size: 0.85rem;
    color: #374151;
  }

  .lookup-list dt {
    font-weight: 600;
    color: #111827;
  }

  .lookup-list dd {
    margin: 0;
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
    border: 1px solid #d1d5db;
    border-radius: 0.75rem;
    overflow: auto;
    max-height: 480px;
  }

  .preview-frame iframe {
    width: 100%;
    height: 100%;
    min-height: 480px;
  }

  .visit-site {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    margin-top: 0.75rem;
    color: #2563eb;
    font-weight: 600;
    text-decoration: none;
  }

  .visit-site:hover {
    text-decoration: underline;
  }

  .panel.overrides {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .panel.overrides .hint {
    color: #6b7280;
    margin: 0;
    font-size: 0.9rem;
  }

  .override-form {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .override-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
  }

  .override-grid label {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    font-size: 0.85rem;
    color: #374151;
  }

  .override-grid select,
  .override-grid input {
    padding: 0.45rem 0.5rem;
    border-radius: 0.5rem;
    border: 1px solid #d1d5db;
    font-size: 0.9rem;
  }

  .override-save {
    align-self: flex-start;
    padding: 0.55rem 1.1rem;
    border-radius: 0.5rem;
    border: none;
    background-color: #2563eb;
    color: white;
    font-weight: 600;
    cursor: pointer;
  }

  .override-save[disabled] {
    opacity: 0.6;
    cursor: not-allowed;
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

  .status-card.overridden {
    box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.35);
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

  .override-flag {
    margin-left: 0.35rem;
    padding: 0.1rem 0.35rem;
    border-radius: 999px;
    background: rgba(59, 130, 246, 0.15);
    color: #1d4ed8;
    font-size: 0.6rem;
    letter-spacing: 0.05em;
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
