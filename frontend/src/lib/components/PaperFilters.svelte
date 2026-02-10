<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { FilterValues } from '$lib/types';

  import type { PaperListOptions } from '$lib/types';

  export let values: FilterValues = {};
  export let options: PaperListOptions = {
    states: [],
    cities: [],
    chainOwners: [],
    cmsPlatforms: [],
    cmsVendors: []
  };

  const dispatch = createEventDispatcher<{ filter: FilterValues; reset: void }>();

  let local = {
    state: values.state ?? '',
    city: values.city ?? '',
    has_pdf: values.has_pdf ?? '',
    pdf_only: values.pdf_only ?? '',
    paywall: values.paywall ?? '',
    notices: values.notices ?? '',
    responsive: values.responsive ?? '',
    chain_owner: values.chain_owner ?? '',
    cms_platform: values.cms_platform ?? '',
    cms_vendor: values.cms_vendor ?? '',
    has_lookup: values.has_lookup ?? '',
    has_import: values.has_import ?? '',
    has_audit: values.has_audit ?? '',
    q: values.q ?? ''
  };

  const auditOptions = ['', 'Yes', 'No', 'Manual Review'];
  const presenceOptions = [
    { value: '', label: 'Any' },
    { value: 'has', label: 'Has value' },
    { value: 'missing', label: 'Missing value' }
  ];

  let availableCities: string[] = options.cities;
  let availableChains: string[] = options.chainOwners;
  let availableCmsPlatforms: string[] = options.cmsPlatforms;
  let availableCmsVendors: string[] = options.cmsVendors;

  $: if (local.state && !options.states.includes(local.state)) {
    local.state = '';
  }

  $: if (local.city && !options.cities.includes(local.city)) {
    local.city = '';
  }

  $: availableCities = options.cities;

  $: availableChains = options.chainOwners;
  $: availableCmsPlatforms = options.cmsPlatforms;
  $: availableCmsVendors = options.cmsVendors;

  function onSubmit() {
    dispatch('filter', {
      state: local.state || undefined,
      city: local.city || undefined,
      has_pdf: local.has_pdf || undefined,
      pdf_only: local.pdf_only || undefined,
      paywall: local.paywall || undefined,
      notices: local.notices || undefined,
      responsive: local.responsive || undefined,
      chain_owner: local.chain_owner || undefined,
      cms_platform: local.cms_platform || undefined,
      cms_vendor: local.cms_vendor || undefined,
      has_lookup: local.has_lookup || undefined,
      has_import: local.has_import || undefined,
      has_audit: local.has_audit || undefined,
      q: local.q || undefined
    });
  }

  function onReset() {
    local = {
      state: '',
      city: '',
      has_pdf: '',
      pdf_only: '',
      paywall: '',
      notices: '',
      responsive: '',
      chain_owner: '',
      cms_platform: '',
      cms_vendor: '',
      has_lookup: '',
      has_import: '',
      has_audit: '',
      q: ''
    };
    dispatch('reset');
  }
</script>

<form class="filters" on:submit|preventDefault={onSubmit}>
  <div>
    <label>
      Keyword search
      <input bind:value={local.q} placeholder="Search papers, cities, chains…" />
    </label>
  </div>
  <div class="grid">
    <label>
      State
      <select bind:value={local.state} on:change={() => (local.city = '')}>
        <option value="">Any</option>
        {#each options.states as stateOption}
          <option value={stateOption}>{stateOption}</option>
        {/each}
      </select>
    </label>
    <label>
      City
      <select bind:value={local.city}>
        <option value="">Any</option>
        {#each availableCities as cityOption}
          <option value={cityOption}>{cityOption}</option>
        {/each}
      </select>
    </label>
    <label>
      Chain
      <select bind:value={local.chain_owner}>
        <option value="">Any</option>
        {#each availableChains as chain}
          <option value={chain}>{chain}</option>
        {/each}
      </select>
    </label>
    <label>
      CMS Platform
      <select bind:value={local.cms_platform}>
        <option value="">Any</option>
        {#each availableCmsPlatforms as platform}
          <option value={platform}>{platform}</option>
        {/each}
      </select>
    </label>
    <label>
      CMS Vendor
      <select bind:value={local.cms_vendor}>
        <option value="">Any</option>
        {#each availableCmsVendors as vendor}
          <option value={vendor}>{vendor}</option>
        {/each}
      </select>
    </label>
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
      Last Lookup
      <select bind:value={local.has_lookup}>
        {#each presenceOptions as option}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select>
    </label>
    <label>
      Last Import
      <select bind:value={local.has_import}>
        {#each presenceOptions as option}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select>
    </label>
    <label>
      Last Audit
      <select bind:value={local.has_audit}>
        {#each presenceOptions as option}
          <option value={option.value}>{option.label}</option>
        {/each}
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
