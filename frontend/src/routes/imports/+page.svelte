<script lang="ts">
  /* eslint-env browser */
  import { goto } from '$app/navigation';
  import { previewImport, commitImport } from '$lib/api';
  import type {
    ImportPreviewResponse,
    ImportPreviewRow,
    ImportCommitRow,
    ImportCommitResult
  } from '$lib/types';

  let file: File | null = null;
  let preview: ImportPreviewResponse | null = null;
  let previewError: string | null = null;
  let commitError: string | null = null;
  let previewing = false;
  let committing = false;
  let commitResult: ImportCommitResult | null = null;

  let actionSelections: Record<string, string> = {};
  let fieldActionSelections: Record<string, Record<string, string>> = {};

  function onFileChange(event: Event) {
    const target = event.currentTarget as HTMLInputElement | null;
    file = target?.files?.[0] ?? null;
    previewError = null;
    commitError = null;
    commitResult = null;
  }

  function defaultAction(row: ImportPreviewRow): string {
    if (row.allowed_actions.length === 0) return 'skip';
    if (row.status === 'new' && row.allowed_actions.includes('insert')) return 'insert';
    if (row.status === 'update' && row.allowed_actions.includes('skip')) return 'skip';
    if (row.status === 'duplicate' && row.allowed_actions.includes('skip')) return 'skip';
    if (row.status === 'possible_duplicate' && row.allowed_actions.includes('skip')) return 'skip';
    return row.allowed_actions[0];
  }

  function actionLabel(action: string): string {
    switch (action) {
      case 'insert':
        return 'insert new entry';
      case 'overwrite':
        return 'overwrite all';
      case 'skip':
        return 'skip all';
      default:
        return action.replace(/_/g, ' ');
    }
  }

  function initialFieldActions(row: ImportPreviewRow): Record<string, string> {
    const fieldActions: Record<string, string> = {};
    Object.keys(row.differences || {})
      .filter((field) => field !== 'extra_data')
      .forEach((field) => {
        const existingValue = row.existing?.[field];
        const isEmpty =
          existingValue === null ||
          existingValue === undefined ||
          (typeof existingValue === 'string' && existingValue.trim() === '');
        fieldActions[field] = isEmpty ? 'overwrite' : 'keep';
      });
    return fieldActions;
  }

  function hasOverwriteField(row: ImportPreviewRow, fieldActions: Record<string, string>): boolean {
    if (!row.existing) return false;
    return Object.values(fieldActions).some((value) => value === 'overwrite');
  }

  function ensureDefaults(response: ImportPreviewResponse) {
    actionSelections = {};
    fieldActionSelections = {};
    response.rows.forEach((row) => {
      if (row.existing && ['update', 'duplicate', 'possible_duplicate'].includes(row.status)) {
        const fieldActions = initialFieldActions(row);
        fieldActionSelections[row.temp_id] = fieldActions;
        if (hasOverwriteField(row, fieldActions) && row.allowed_actions.includes('overwrite')) {
          actionSelections[row.temp_id] = 'overwrite';
        } else {
          actionSelections[row.temp_id] = defaultAction(row);
        }
      } else {
        actionSelections[row.temp_id] = defaultAction(row);
      }
    });
    actionSelections = { ...actionSelections };
    fieldActionSelections = { ...fieldActionSelections };
  }

  async function handlePreview() {
    if (!file) {
      previewError = 'Please choose a CSV file first.';
      return;
    }
    previewError = null;
    commitError = null;
    commitResult = null;
    previewing = true;
    try {
      const resp = await previewImport(file);
      preview = resp;
      ensureDefaults(resp);
    } catch (err) {
      preview = null;
      actionSelections = {};
      fieldActionSelections = {};
      previewError = err instanceof Error ? err.message : 'Failed to preview import.';
    } finally {
      previewing = false;
    }
  }

  function onActionChange(row: ImportPreviewRow, event: Event) {
    const target = event.currentTarget as HTMLSelectElement | null;
    if (!target) return;
    const nextAction = target.value;
    actionSelections = { ...actionSelections, [row.temp_id]: nextAction };
    if (!row.existing || !['update', 'duplicate', 'possible_duplicate'].includes(row.status)) {
      return;
    }
    const current = fieldActionSelections[row.temp_id] ?? initialFieldActions(row);
    let updated: Record<string, string> = { ...current };
    if (nextAction === 'overwrite') {
      updated = Object.fromEntries(Object.keys(current).map((field) => [field, 'overwrite']));
    } else if (nextAction === 'skip' || nextAction === 'merge_extra') {
      updated = Object.fromEntries(Object.keys(current).map((field) => [field, 'keep']));
    }
    fieldActionSelections = { ...fieldActionSelections, [row.temp_id]: updated };
  }

  function resolveAction(row: ImportPreviewRow): string {
    return actionSelections[row.temp_id] ?? defaultAction(row);
  }

  function resolveFieldAction(row: ImportPreviewRow, field: string): string {
    return fieldActionSelections[row.temp_id]?.[field] ?? 'overwrite';
  }

  function onFieldActionChange(row: ImportPreviewRow, field: string, event: Event) {
    const target = event.currentTarget as HTMLSelectElement | null;
    if (!target) return;
    const current = fieldActionSelections[row.temp_id] ?? {};
    fieldActionSelections = {
      ...fieldActionSelections,
      [row.temp_id]: { ...current, [field]: target.value }
    };
  }

  async function handleCommit() {
    if (!preview) return;
    committing = true;
    commitError = null;
    try {
      const rows: ImportCommitRow[] = preview.rows.map((row) => ({
        temp_id: row.temp_id,
        action: resolveAction(row),
        data: row.data,
        existing_id: (row.existing?.id as number | undefined) ?? null,
        status: row.status,
        field_actions: fieldActionSelections[row.temp_id] ?? null
      }));

      const result = await commitImport({ rows });
      commitResult = result;
      preview = null;
      actionSelections = {};
      fieldActionSelections = {};
      file = null;
      const input = document.getElementById('csv-input') as HTMLInputElement | null;
      if (input) {
        input.value = '';
      }

      setTimeout(() => {
        goto('/papers');
      }, 2000);
    } catch (err) {
      commitError = err instanceof Error ? err.message : 'Failed to commit import.';
    } finally {
      committing = false;
    }
  }

  function resetEverything() {
    file = null;
    preview = null;
    previewError = null;
    commitError = null;
    commitResult = null;
    actionSelections = {};
    fieldActionSelections = {};
    const input = document.getElementById('csv-input') as HTMLInputElement | null;
    if (input) {
      input.value = '';
    }
  }
</script>

<div class="page">
  <header class="header">
    <div>
      <h1>CSV Import</h1>
      <p class="subtitle">Upload a CSV, review changes, and merge them into the database.</p>
    </div>
    <button type="button" class="back" on:click={() => goto('/papers')}>&larr; Back to Papers</button>
  </header>

  <section class="panel">
    <h2>1. Upload CSV</h2>
    <div class="form-row">
      <input id="csv-input" type="file" accept=".csv" on:change={onFileChange} />
      <button type="button" on:click={handlePreview} disabled={!file || previewing}>
        {previewing ? 'Uploading…' : 'Preview Import'}
      </button>
      <button type="button" class="secondary" on:click={resetEverything}>Reset</button>
    </div>
    {#if previewError}
      <p class="error">{previewError}</p>
    {/if}
  </section>

  {#if preview}
    <section class="panel">
      <h2>2. Review Changes</h2>
      <div class="summary">
        <span><strong>New:</strong> {preview.summary.new}</span>
        <span><strong>Updates:</strong> {preview.summary.update}</span>
        <span><strong>Duplicates:</strong> {preview.summary.duplicate}</span>
        <span><strong>Possible duplicates:</strong> {preview.summary.possible_duplicate}</span>
        <span><strong>Invalid:</strong> {preview.summary.invalid}</span>
      </div>

      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Paper</th>
              <th>City</th>
              <th>State</th>
              <th>Action</th>
              <th>Differences</th>
              <th>Issues</th>
            </tr>
          </thead>
          <tbody>
            {#each preview.rows as row}
              <tr class={`status-${row.status}`}>
                <td>{row.status}</td>
                <td>{row.data.paper_name ?? '—'}</td>
                <td>{row.data.city ?? '—'}</td>
                <td>{row.data.state ?? '—'}</td>
                <td>
                  <select value={resolveAction(row)} on:change={(event) => onActionChange(row, event)}>
                    {#each row.allowed_actions as action}
                      <option value={action}>{actionLabel(action)}</option>
                    {/each}
                  </select>
                </td>
                <td>
                  {#if Object.keys(row.differences).length === 0}
                    <span class="muted">No changes</span>
                  {:else}
                    <ul>
                      {#each Object.entries(row.differences) as [field, diff]}
                        <li>
                          <span class="field">{field}</span>
                          <span class="old">{String(diff.old ?? '—')}</span>
                          <span class="arrow">→</span>
                          <span class="new">{String(diff.new ?? '—')}</span>
                          {#if row.existing && field !== 'extra_data' && ['update', 'duplicate', 'possible_duplicate'].includes(row.status) && resolveAction(row) !== 'skip'}
                            <select
                              class="field-action"
                              value={resolveFieldAction(row, field)}
                              on:change={(event) => onFieldActionChange(row, field, event)}
                            >
                              <option value="overwrite">overwrite</option>
                              <option value="keep">keep existing</option>
                            </select>
                          {/if}
                        </li>
                      {/each}
                    </ul>
                  {/if}
                </td>
                <td>
                  {#if row.issues.length === 0}
                    <span class="muted">—</span>
                  {:else}
                    <ul>
                      {#each row.issues as issue}
                        <li>{issue}</li>
                      {/each}
                    </ul>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <h2>3. Commit</h2>
      <p>Select the desired action for each row, then commit the import.</p>
      <div class="actions">
        <button type="button" on:click={handleCommit} disabled={committing}>
          {committing ? 'Committing…' : 'Commit Changes'}
        </button>
      </div>
      {#if commitError}
        <p class="error">{commitError}</p>
      {/if}
      {#if commitResult}
        <div class="success">
          <p><strong>Import complete!</strong></p>
          <p>Inserted {commitResult.inserted}, updated {commitResult.updated}, skipped {commitResult.skipped}.</p>
        </div>
      {/if}
    </section>
  {/if}
</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    padding-bottom: 4rem;
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .subtitle {
    color: #6b7280;
    margin-top: 0.25rem;
  }

  .back {
    border: none;
    background: transparent;
    color: #2563eb;
    cursor: pointer;
    font-weight: 600;
  }

  .panel {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 0.75rem;
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .form-row {
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
  }

  button {
    padding: 0.55rem 1rem;
    border-radius: 0.5rem;
    border: none;
    background-color: #2563eb;
    color: white;
    font-weight: 600;
    cursor: pointer;
  }

  button.secondary {
    background-color: #e5e7eb;
    color: #111827;
  }

  button[disabled] {
    opacity: 0.65;
    cursor: not-allowed;
  }

  .error {
    color: #dc2626;
    font-weight: 600;
  }

  .success {
    background-color: #ecfdf5;
    border: 1px solid #10b981;
    border-radius: 0.5rem;
    padding: 0.75rem 1rem;
    color: #065f46;
  }

  .summary {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    color: #4b5563;
  }

  .table-wrapper {
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  thead {
    background: #f9fafb;
  }

  th,
  td {
    padding: 0.75rem;
    text-align: left;
    border-bottom: 1px solid #e5e7eb;
    vertical-align: top;
    font-size: 0.9rem;
  }

  tr.status-invalid {
    background-color: #fef2f2;
  }

  tr.status-duplicate {
    background-color: #fffbeb;
  }

  select {
    width: 100%;
    padding: 0.35rem 0.5rem;
    border-radius: 0.5rem;
    border: 1px solid #d1d5db;
    font-size: 0.9rem;
  }

  ul {
    margin: 0;
    padding-left: 1.25rem;
  }

  .muted {
    color: #6b7280;
  }

  .field {
    font-weight: 600;
    margin-right: 0.35rem;
  }

  .old {
    color: #b91c1c;
  }

  .new {
    color: #047857;
  }

  .arrow {
    margin: 0 0.25rem;
    color: #6b7280;
  }

  .field-action {
    margin-left: 0.5rem;
    width: auto;
    min-width: 150px;
  }

  .actions {
    display: flex;
    gap: 1rem;
  }
</style>
