<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { FilterValues } from '$lib/types';

  export let values: FilterValues = {};

  const dispatch = createEventDispatcher<{ filter: FilterValues; reset: void }>();

  let local = {
    state: values.state ?? '',
    has_pdf: values.has_pdf ?? '',
    pdf_only: values.pdf_only ?? '',
    paywall: values.paywall ?? '',
    notices: values.notices ?? '',
    responsive: values.responsive ?? '',
    q: values.q ?? '',
    limit: String(values.limit ?? 50)
  };

  const auditOptions = ['', 'Yes', 'No', 'Manual Review'];

  function onSubmit() {
    dispatch('filter', {
      state: local.state || undefined,
      has_pdf: local.has_pdf || undefined,
      pdf_only: local.pdf_only || undefined,
      paywall: local.paywall || undefined,
      notices: local.notices || undefined,
      responsive: local.responsive || undefined,
      q: local.q || undefined,
      limit: Number(local.limit) || 50
    });
  }

  function onReset() {
    local = {
      state: '',
      has_pdf: '',
      pdf_only: '',
      paywall: '',
      notices: '',
      responsive: '',
      q: '',
      limit: '50'
    };
    dispatch('reset');
  }
</script>

<form class="filters" on:submit|preventDefault={onSubmit}>
  <div>
    <label>
      State
      <input bind:value={local.state} placeholder="e.g. AL" maxlength="2" />
    </label>
  </div>
  <div>
    <label>
      Search
      <input bind:value={local.q} placeholder="Paper name or city" />
    </label>
  </div>
  <div class="grid">
    <label>
      Has PDF
      <select bind:value={local.has_pdf}>
        {#each auditOptions as option}
          <option value={option}>{option || 'Any'}</option>
        {/each}
      </select>
    </label>
    <label>
      PDF Only
      <select bind:value={local.pdf_only}>
        {#each auditOptions as option}
          <option value={option}>{option || 'Any'}</option>
        {/each}
      </select>
    </label>
    <label>
      Paywall
      <select bind:value={local.paywall}>
        {#each auditOptions as option}
          <option value={option}>{option || 'Any'}</option>
        {/each}
      </select>
    </label>
    <label>
      Notices
      <select bind:value={local.notices}>
        {#each auditOptions as option}
          <option value={option}>{option || 'Any'}</option>
        {/each}
      </select>
    </label>
    <label>
      Responsive
      <select bind:value={local.responsive}>
        {#each auditOptions as option}
          <option value={option}>{option || 'Any'}</option>
        {/each}
      </select>
    </label>
    <label>
      Page Size
      <select bind:value={local.limit}>
        <option value="25">25</option>
        <option value="50">50</option>
        <option value="100">100</option>
      </select>
    </label>
  </div>

  <div class="actions">
    <button type="submit">Apply</button>
    <button type="button" on:click={onReset}>Clear</button>
  </div>
</form>

<style>
  form.filters {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    background-color: white;
    padding: 1.5rem;
    border-radius: 0.75rem;
    border: 1px solid #e5e7eb;
  }

  label {
    display: flex;
    flex-direction: column;
    font-size: 0.875rem;
    gap: 0.35rem;
    font-weight: 600;
    color: #374151;
  }

  input,
  select {
    padding: 0.5rem 0.75rem;
    border-radius: 0.5rem;
    border: 1px solid #d1d5db;
    font-size: 0.95rem;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
  }

  .actions {
    display: flex;
    gap: 0.75rem;
  }

  button {
    padding: 0.55rem 1rem;
    border: none;
    border-radius: 0.5rem;
    font-weight: 600;
    cursor: pointer;
  }

  button[type='submit'] {
    background-color: #2563eb;
    color: white;
  }

  button[type='button'] {
    background-color: #e5e7eb;
    color: #111827;
  }
</style>
