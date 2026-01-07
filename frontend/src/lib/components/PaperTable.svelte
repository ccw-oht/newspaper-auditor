<script lang="ts">
  /* eslint-env browser */
import type { AuditSummary, PaperSummary } from '$lib/types';
import { createEventDispatcher } from 'svelte';
import { slide } from 'svelte/transition';

export let items: PaperSummary[] = [];
export let total = 0;
export let limit = 50;
export let offset = 0;
export let loading = false;
export let selected: number[] = [];
export let sortField: string = 'paper_name';
export let sortOrder: 'asc' | 'desc' = 'asc';

let safeLimit = limit || 1;
let totalPages = 1;
let currentPage = 1;
let startEntry = 0;
let endEntry = 0;

const dispatch = createEventDispatcher<{
    audit: { id: number };
    lookup: { id: number };
    paginate: { offset: number };
    select: { id: number; checked: boolean };
    selectRange: { ids: number[]; checked: boolean };
    selectAll: { ids: number[]; checked: boolean };
    sort: { field: string; order: 'asc' | 'desc' };
  }>();

$: safeLimit = limit > 0 ? limit : 1;
$: totalPages = Math.max(1, Math.ceil(total / safeLimit));
$: currentPage = Math.floor(offset / safeLimit) + 1;
$: startEntry = total === 0 ? 0 : Math.min(offset + 1, total);
$: endEntry = total === 0 ? 0 : Math.min(offset + safeLimit, total);

  let selectAllCheckbox: HTMLInputElement | null = null;
  let selectedSet = new Set<number>();
  let lastToggledIndex: number | null = null;
  let itemsFingerprint: string | null = null;
  let expandedIds = new Set<number>();
  let hoverExpandedId: number | null = null;
  let hoverTimer: number | null = null;

  $: selectedSet = new Set(selected);
  $: allVisibleSelected = items.length > 0 && items.every((item) => selectedSet.has(item.id));
  $: someSelected = items.some((item) => selectedSet.has(item.id));
  $: {
    if (selectAllCheckbox) {
      selectAllCheckbox.indeterminate = someSelected && !allVisibleSelected;
    }
  }

function goToPage(page: number) {
  const target = Math.max(1, Math.min(totalPages, page));
  dispatch('paginate', { offset: (target - 1) * safeLimit });
}

function goToFirst() {
  dispatch('paginate', { offset: 0 });
}

function goToLast() {
  const lastPage = totalPages;
  dispatch('paginate', { offset: (lastPage - 1) * safeLimit });
}

  function toggleSort(field: string) {
    const nextOrder: 'asc' | 'desc' = field === sortField ? (sortOrder === 'asc' ? 'desc' : 'asc') : 'asc';
    dispatch('sort', { field, order: nextOrder });
  }

  function columnAriaSort(field: string): 'ascending' | 'descending' | 'none' {
    if (field !== sortField) return 'none';
    return sortOrder === 'asc' ? 'ascending' : 'descending';
  }

  $: if (lastToggledIndex !== null && (lastToggledIndex < 0 || lastToggledIndex >= items.length)) {
    lastToggledIndex = null;
  }

  $: {
    const currentFingerprint = items.map((item) => item.id).join(',');
    if (currentFingerprint !== itemsFingerprint) {
      itemsFingerprint = currentFingerprint;
      lastToggledIndex = null;
    }
  }

  $: {
    const visibleIds = new Set(items.map((item) => item.id));
    expandedIds = new Set(Array.from(expandedIds).filter((id) => visibleIds.has(id)));
  }

  function handleItemClick(event: MouseEvent, id: number, index: number) {
    const target = event.currentTarget as HTMLInputElement | null;
    const checked = target?.checked ?? false;

    if (event.shiftKey && lastToggledIndex !== null) {
      const start = Math.min(lastToggledIndex, index);
      const end = Math.max(lastToggledIndex, index);
      const rangeIds = items.slice(start, end + 1).map((item) => item.id);
      dispatch('selectRange', { ids: rangeIds, checked });
    } else {
      dispatch('select', { id, checked });
    }

    lastToggledIndex = index;
  }

  function onSelectAll(checked: boolean) {
    dispatch('selectAll', { ids: items.map((item) => item.id), checked });
  }

  function extractChecked(event: Event): boolean {
    const target = event.currentTarget as HTMLInputElement | null;
    return target?.checked ?? false;
  }

  function normalizeWebsiteUrl(url: string | null | undefined): string | null {
    if (!url) return null;
    const trimmed = url.trim();
    if (!trimmed) return null;

    if (/^[a-zA-Z][a-zA-Z0-9+\-.]*:/.test(trimmed)) {
      return trimmed;
    }

    return `https://${trimmed.replace(/^\/+/, '')}`;
  }

  function socialLinks(item: PaperSummary): string[] {
    const extra = item.extra_data as Record<string, unknown> | null | undefined;
    const lookup = extra?.contact_lookup as Record<string, unknown> | undefined;
    const links = lookup?.social_media_links;
    if (!Array.isArray(links)) return [];
    const cleaned = links
      .filter((value) => typeof value === 'string')
      .map((value) => value.trim())
      .filter(Boolean);
    return Array.from(new Set(cleaned));
  }

  function socialLabel(link: string): string {
    const lowered = link.toLowerCase();
    if (lowered.includes('facebook.com')) return 'Facebook';
    if (lowered.includes('instagram.com')) return 'Instagram';
    if (lowered.includes('linkedin.com')) return 'LinkedIn';
    if (lowered.includes('youtube.com') || lowered.includes('youtu.be')) return 'YouTube';
    if (lowered.includes('tiktok.com')) return 'TikTok';
    if (lowered.includes('twitter.com') || lowered.includes('x.com')) return 'X';
    if (lowered.includes('bsky.app') || lowered.includes('bsky.social') || lowered.includes('bluesky')) return 'Bluesky';
    if (lowered.includes('pinterest.com') || lowered.includes('pin.it')) return 'Pinterest';
    return 'Social link';
  }

  function socialIcon(
    link: string
  ): 'facebook' | 'instagram' | 'linkedin' | 'youtube' | 'tiktok' | 'x' | 'bluesky' | 'pinterest' | 'link' {
    const lowered = link.toLowerCase();
    if (lowered.includes('facebook.com')) return 'facebook';
    if (lowered.includes('instagram.com')) return 'instagram';
    if (lowered.includes('linkedin.com')) return 'linkedin';
    if (lowered.includes('youtube.com') || lowered.includes('youtu.be')) return 'youtube';
    if (lowered.includes('tiktok.com')) return 'tiktok';
    if (lowered.includes('twitter.com') || lowered.includes('x.com')) return 'x';
    if (lowered.includes('bsky.app') || lowered.includes('bsky.social') || lowered.includes('bluesky')) return 'bluesky';
    if (lowered.includes('pinterest.com') || lowered.includes('pin.it')) return 'pinterest';
    return 'link';
  }

  function statusClass(field: string, value: string | null | undefined): string {
    const normalized = (value ?? '').toString().trim().toLowerCase();
    if (!normalized || normalized === '—') return 'status neutral';
    if (normalized.startsWith('manual')) return 'status review';
    const invert = field === 'pdf_only';
    if (normalized.startsWith('yes')) {
      return invert ? 'status no' : 'status yes';
    }
    if (normalized.startsWith('no')) {
      return invert ? 'status yes' : 'status no';
    }
    return 'status neutral';
  }

  function isOverridden(summary: AuditSummary | null | undefined, field: string): boolean {
    const overrides = summary?.overrides as Record<string, unknown> | undefined;
    if (!overrides) return false;
    return overrides[field] !== undefined;
  }

  function auditFieldValue(summary: AuditSummary | null | undefined, field: string): string | null | undefined {
    if (!summary) return null;
    const record = summary as Record<string, string | null | undefined>;
    return record[field];
  }

  function hasLookup(item: PaperSummary): boolean {
    const extra = item.extra_data as Record<string, unknown> | null | undefined;
    if (!extra) return false;
    const lookup = extra.contact_lookup as Record<string, unknown> | undefined;
    return !!lookup;
  }

  function primaryContact(item: PaperSummary): string | null {
    const extra = item.extra_data as Record<string, unknown> | null | undefined;
    const lookup = extra?.contact_lookup as Record<string, unknown> | undefined;
    const value = lookup?.primary_contact;
    if (typeof value !== 'string') return null;
    const trimmed = value.trim();
    return trimmed ? trimmed : null;
  }

  const detailFields = [
    { key: 'has_pdf', label: 'Has PDF', short: 'PDF' },
    { key: 'pdf_only', label: 'PDF Only', short: 'Only' },
    { key: 'paywall', label: 'Paywall', short: 'Pay' },
    { key: 'notices', label: 'Notices', short: 'Not' },
    { key: 'responsive', label: 'Responsive', short: 'Resp' }
  ];

  function toggleDetails(id: number) {
    const next = new Set(expandedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    expandedIds = next;
  }
  function showHoverDetails(id: number) {
    if (hoverTimer !== null) {
      clearTimeout(hoverTimer);
    }
    hoverTimer = window.setTimeout(() => {
      hoverExpandedId = id;
      hoverTimer = null;
    }, 140);
  }

  function clearHoverDetails(id: number) {
    if (hoverTimer !== null) {
      clearTimeout(hoverTimer);
      hoverTimer = null;
    }
    if (hoverExpandedId === id) {
      hoverExpandedId = null;
    }
  }
</script>

<div class="table-wrapper">
  <table>
    <thead>
      <tr>
        <th class="select">
          <input
            type="checkbox"
            bind:this={selectAllCheckbox}
            checked={allVisibleSelected && items.length > 0}
            on:change={(event) => onSelectAll(extractChecked(event))}
            aria-label="Select visible papers"
          />
        </th>
        <th
          class="sortable"
          aria-sort={columnAriaSort('paper_name')}
        >
          <button type="button" on:click={() => toggleSort('paper_name')}>
            Paper
            {#if sortField === 'paper_name'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th
          class="sortable"
          aria-sort={columnAriaSort('city')}
        >
          <button type="button" on:click={() => toggleSort('city')}>
            City
            {#if sortField === 'city'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th
          class="sortable"
          aria-sort={columnAriaSort('state')}
        >
          <button type="button" on:click={() => toggleSort('state')}>
            State
            {#if sortField === 'state'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th
          class="sortable"
          aria-sort={columnAriaSort('website_url')}
        >
          <button type="button" on:click={() => toggleSort('website_url')}>
            Links
            {#if sortField === 'website_url'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th class="sortable audit-summary" aria-sort={columnAriaSort('timestamp')}>
          <button type="button" on:click={() => toggleSort('timestamp')}>
            Last Audit
            {#if sortField === 'timestamp'}
              <span class="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
            {/if}
          </button>
        </th>
        <th class="actions">Actions</th>
      </tr>
    </thead>
    <tbody>
      {#if items.length === 0}
        <tr>
          <td colspan="7" class="empty">No results</td>
        </tr>
      {:else}
        {#each items as item, index}
          <tr class:expanded={expandedIds.has(item.id) || hoverExpandedId === item.id}>
            <td class="select">
              <input
                type="checkbox"
                checked={selectedSet.has(item.id)}
                on:click={(event) => handleItemClick(event, item.id, index)}
                aria-label={`Select ${item.paper_name ?? 'paper'}`}
              />
            </td>
            <td class="paper-cell">
              <a class="paper-link" href={`/papers/${item.id}`} title="Click for full details.">
                {item.paper_name ?? '—'}
              </a>
            </td>
            <td>{item.city ?? '—'}</td>
            <td>{item.state ?? '—'}</td>
            <td>
              {#if normalizeWebsiteUrl(item.website_url) || socialLinks(item).length > 0}
                <div class="link-icons">
                  {#if normalizeWebsiteUrl(item.website_url)}
                    <a
                      class="icon-link site"
                      href={normalizeWebsiteUrl(item.website_url) ?? undefined}
                      target="_blank"
                      rel="noreferrer"
                      title="Website"
                      aria-label="Website"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" aria-hidden="true">
                        <path d="M16,2C8.268,2,2,8.268,2,16s6.268,14,14,14c7.732,0,14-6.268,14-14h0c0-7.732-6.268-14-14-14Zm0,26.903c-7.126,0-12.903-5.777-12.903-12.903S8.874,3.097,16,3.097s12.903,5.777,12.903,12.903-5.777,12.903-12.903,12.903Z" />
                        <path d="M16,3.77c-.104,0-.188,.084-.188,.188v2.17c0,.104,.084,.188,.188,.188s.188-.084,.188-.188V3.958c0-.104-.084-.188-.188-.188Z" />
                        <path d="M13.505,4.031c-.013,0-.025,.001-.038,.004-.102,.022-.167,.121-.145,.223l.449,2.123c.022,.102,.121,.167,.223,.145,.102-.022,.167-.121,.145-.223l-.449-2.123c-.019-.089-.097-.15-.185-.149h0Z" />
                        <path d="M18.503,4.033c-.088,0-.166,.06-.185,.149l-.451,2.123c-.022,.102,.043,.201,.145,.223,.102,.022,.201-.043,.223-.145l.451-2.123c.022-.102-.043-.201-.145-.223-.013-.003-.025-.004-.038-.004h0Z" />
                        <path d="M11.106,4.808c-.024,0-.049,.006-.073,.016-.095,.042-.138,.153-.095,.248l.881,1.983c.042,.095,.153,.138,.248,.095,.095-.042,.138-.153,.096-.248l-.881-1.983c-.032-.071-.102-.113-.175-.112h0Z" />
                        <path d="M20.91,4.814c-.073-.001-.144,.04-.175,.112l-.884,1.982c-.042,.095,0,.206,.095,.248,.095,.042,.206,0,.248-.095l.884-1.982c.042-.095,0-.206-.095-.248-.024-.011-.049-.016-.073-.016h0Z" />
                        <path d="M8.923,6.064c-.036,.001-.072,.013-.104,.036-.084,.061-.103,.178-.042,.263l1.274,1.756c.061,.084,.178,.103,.263,.042,.084-.061,.103-.178,.042-.263l-1.274-1.756c-.038-.053-.098-.08-.159-.078h0Z" />
                        <path d="M23.091,6.074c-.06-.002-.12,.025-.159,.077l-1.277,1.755c-.061,.084-.043,.202,.041,.263,.084,.061,.202,.043,.263-.041l1.276-1.755c.061-.084,.043-.202-.041-.263-.032-.023-.068-.035-.104-.036h0Z" />
                        <path d="M7.04,7.756c-.048,.003-.095,.023-.13,.062-.07,.077-.063,.196,.014,.266l1.613,1.452c.077,.07,.196,.063,.266-.014,.07-.077,.064-.196-.014-.266l-1.613-1.452c-.039-.035-.088-.051-.136-.048h0Z" />
                        <path d="M5.558,9.791c-.06,.004-.117,.037-.15,.094-.052,.09-.021,.205,.069,.257l1.879,1.085c.09,.052,.205,.021,.257-.069s.021-.205-.069-.257l-1.879-1.085c-.034-.02-.071-.027-.107-.025h0Z" />
                        <path d="M26.442,9.791c-.036-.003-.073,.005-.107,.025l-1.879,1.085c-.09,.052-.121,.167-.069,.257s.167,.121,.257,.069l1.879-1.085c.09-.052,.121-.167,.069-.257-.033-.056-.09-.09-.15-.094h0Z" />
                        <path d="M4.534,12.082c-.073,.006-.139,.055-.163,.129-.032,.099,.021,.205,.121,.237l2.063,.672c.099,.032,.205-.021,.237-.121,.032-.099-.021-.205-.121-.237l-2.063-.672c-.025-.008-.05-.011-.074-.009h0Z" />
                        <path d="M27.468,12.09c-.024-.002-.05,0-.074,.009l-2.064,.671c-.099,.032-.153,.138-.121,.237,.032,.099,.138,.153,.237,.121l2.064-.671c.099-.032,.153-.138,.121-.237-.024-.074-.09-.123-.163-.129h0Z" />
                        <path d="M4.006,14.547c-.087,.008-.159,.077-.169,.167-.011,.104,.064,.196,.167,.207l2.158,.228c.104,.011,.196-.064,.207-.167,.011-.104-.064-.196-.167-.207l-2.158-.228c-.013-.001-.026-.001-.038,0h0Z" />
                        <path d="M27.996,14.563c-.012-.001-.025-.001-.038,0l-2.158,.225c-.104,.011-.178,.103-.168,.207,.011,.104,.103,.178,.207,.168l2.158-.225c.104-.011,.178-.103,.168-.207-.009-.091-.081-.159-.168-.168h0Z" />
                        <path d="M6.2,16.838c-.012-.001-.025-.001-.038,0l-2.158,.225c-.104,.011-.178,.103-.168,.207,.011,.104,.103,.178,.207,.168l2.158-.225c.104-.011,.178-.103,.168-.207-.009-.091-.081-.159-.168-.168h0Z" />
                        <path d="M25.799,16.851c-.087,.008-.159,.077-.169,.167-.011,.104,.064,.196,.167,.207l2.158,.228c.104,.011,.196-.064,.207-.167,.011-.104-.064-.196-.167-.207l-2.158-.228c-.013-.001-.026-.001-.038,0h0Z" />
                        <path d="M6.628,18.865c-.024-.002-.05,0-.074,.009l-2.064,.671c-.099,.032-.153,.138-.121,.237,.032,.099,.138,.153,.237,.121l2.064-.671c.099-.032,.153-.138,.121-.237-.024-.074-.09-.123-.163-.129h0Z" />
                        <path d="M25.37,18.871c-.073,.006-.139,.055-.163,.129-.032,.099,.021,.205,.121,.237l2.063,.672c.099,.032,.205-.021,.237-.121,.032-.099-.021-.205-.121-.237l-2.063-.672c-.025-.008-.05-.011-.074-.009h0Z" />
                        <path d="M7.464,20.749c-.036-.003-.073,.005-.107,.025l-1.879,1.085c-.09,.052-.121,.167-.069,.257s.167,.121,.257,.069l1.879-1.085c.09-.052,.121-.167,.069-.257-.033-.056-.09-.09-.15-.094h0Z" />
                        <path d="M24.536,20.749c-.06,.004-.117,.037-.15,.094-.052,.09-.021,.205,.069,.257l1.879,1.085c.09,.052,.205,.021,.257-.069s.021-.205-.069-.257l-1.879-1.085c-.034-.20-.071-.027-.107-.025h0Z" />
                        <path d="M23.327,22.417c-.048,.003-.095,.023-.13,.062-.07,.077-.063,.196,.014,.266l1.613,1.452c.077,.07,.196,.063,.266-.014,.07-.077,.063-.196-.014-.266l-1.613-1.452c-.039-.035-.088-.051-.136-.048h0Z" />
                        <path d="M10.199,23.795c-.06-.002-.12,.025-.159,.077l-1.276,1.755c-.061,.084-.043,.202,.041,.263,.084,.061,.202,.043,.263-.041l1.276-1.755c.061-.084,.043-.202-.041-.263-.032-.023-.068-.035-.104-.036Z" />
                        <path d="M21.79,23.803c-.036,.001-.072,.013-.104,.036-.084,.061-.103,.178-.042,.263l1.274,1.756c.061,.084,.178,.103,.263,.042,.084-.061,.103-.178,.042-.263l-1.274-1.756c-.038-.053-.098-.08-.159-.078h0Z" />
                        <path d="M11.982,24.828c-.073-.002-.144,.04-.175,.112l-.884,1.982c-.042,.095,0,.206,.095,.248,.095,.042,.206,0,.248-.095l.884-1.982c.042-.095,0-.206-.095-.248-.024-.011-.049-.016-.073-.016h0Z" />
                        <path d="M20.006,24.833c-.024,0-.049,.006-.073,.016-.095,.042-.138,.153-.095,.248l.881,1.983c.042,.095,.153,.138,.248,.095,.095-.042,.138-.153,.095-.248l-.881-1.983c-.032-.071-.102-.113-.175-.112h0Z" />
                        <path d="M13.95,25.469c-.088,0-.166,.06-.185,.149l-.451,2.123c-.022,.102,.043,.201,.145,.223,.102,.022,.201-.043,.223-.145l.451-2.123c.022-.102-.043-.201-.145-.223-.013-.003-.025-.004-.038-.004h0Z" />
                        <path d="M18.044,25.47c-.013,0-.025,.001-.038,.004-.102,.022-.167,.121-.145,.223l.449,2.123c.022,.102,.121,.167,.223,.145,.102-.022,.167-.121,.145-.223l-.449-2.123c-.019-.089-.097-.15-.185-.149h0Z" />
                        <path d="M16,25.684c-.104,0-.188,.084-.188,.188v2.17c0,.104,.084,.188,.188,.188s.188-.084,.188-.188v-2.17c0-.104-.084-.188-.188-.188Z" />
                        <path d="M17.475,17.545l-2.95-3.089,10.465-7.04-7.515,10.129Z" />
                        <path d="M17.475,17.545l-2.95-3.089-7.515,10.129,10.465-7.04Z" opacity=".5" />
                        <path d="M7.01,24.585l10.465-7.04,7.515-10.129L7.01,24.585Z" isolation="isolate" opacity=".243" />
                      </svg>
                    </a>
                  {/if}
                  {#each socialLinks(item) as link}
                    <a
                      class={`icon-link social ${socialIcon(link)}`}
                      href={normalizeWebsiteUrl(link) ?? undefined}
                      target="_blank"
                      rel="noreferrer"
                      title={socialLabel(link)}
                      aria-label={socialLabel(link)}
                    >
                      {#if socialIcon(link) === 'facebook'}
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" aria-hidden="true">
                          <path d="M16,2c-7.732,0-14,6.268-14,14,0,6.566,4.52,12.075,10.618,13.588v-9.31h-2.887v-4.278h2.887v-1.843c0-4.765,2.156-6.974,6.835-6.974,.887,0,2.417,.174,3.043,.348v3.878c-.33-.035-.904-.052-1.617-.052-2.296,0-3.183,.87-3.183,3.13v1.513h4.573l-.786,4.278h-3.787v9.619c6.932-.837,12.304-6.74,12.304-13.897,0-7.732-6.268-14-14-14Z" />
                        </svg>
                      {:else if socialIcon(link) === 'instagram'}
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" aria-hidden="true">
                          <path d="M10.202,2.098c-1.49,.07-2.507,.308-3.396,.657-.92,.359-1.7,.84-2.477,1.619-.776,.779-1.254,1.56-1.61,2.481-.345,.891-.578,1.909-.644,3.4-.066,1.49-.08,1.97-.073,5.771s.024,4.278,.096,5.772c.071,1.489,.308,2.506,.657,3.396,.359,.92,.84,1.7,1.619,2.477,.779,.776,1.559,1.253,2.483,1.61,.89,.344,1.909,.579,3.399,.644,1.49,.065,1.97,.08,5.771,.073,3.801-.007,4.279-.024,5.773-.095s2.505-.309,3.395-.657c.92-.36,1.701-.84,2.477-1.62s1.254-1.561,1.609-2.483c.345-.89,.579-1.909,.644-3.398,.065-1.494,.081-1.971,.073-5.773s-.024-4.278-.095-5.771-.308-2.507-.657-3.397c-.36-.92-.84-1.7-1.619-2.477s-1.561-1.254-2.483-1.609c-.891-.345-1.909-.58-3.399-.644s-1.97-.081-5.772-.074-4.278,.024-5.771,.096m.164,25.309c-1.365-.059-2.106-.286-2.6-.476-.654-.252-1.12-.557-1.612-1.044s-.795-.955-1.05-1.608c-.192-.494-.423-1.234-.487-2.599-.069-1.475-.084-1.918-.092-5.656s.006-4.18,.071-5.656c.058-1.364,.286-2.106,.476-2.6,.252-.655,.556-1.12,1.044-1.612s.955-.795,1.608-1.05c.493-.193,1.234-.422,2.598-.487,1.476-.07,1.919-.084,5.656-.092,3.737-.008,4.181,.006,5.658,.071,1.364,.059,2.106,.285,2.599,.476,.654,.252,1.12,.555,1.612,1.044s.795,.954,1.051,1.609c.193,.492,.422,1.232,.486,2.597,.07,1.476,.086,1.919,.093,5.656,.007,3.737-.006,4.181-.071,5.656-.06,1.365-.286,2.106-.476,2.601-.252,.654-.556,1.12-1.045,1.612s-.955,.795-1.608,1.05c-.493,.192-1.234,.422-2.597,.487-1.476,.069-1.919,.084-5.657,.092s-4.18-.007-5.656-.071M21.779,8.517c.002,.928,.755,1.679,1.683,1.677s1.679-.755,1.677-1.683c-.002-.928-.755-1.679-1.683-1.677,0,0,0,0,0,0-.928,.002-1.678,.755-1.677,1.683m-12.967,7.496c.008,3.97,3.232,7.182,7.202,7.174s7.183-3.232,7.176-7.202c-.008-3.97-3.233-7.183-7.203-7.175s-7.182,3.233-7.174,7.203m2.522-.005c-.005-2.577,2.08-4.671,4.658-4.676,2.577-.005,4.671,2.08,4.676,4.658,.005,2.577-2.08,4.671-4.658,4.676-2.577,.005-4.671-2.079-4.676-4.656h0" />
                        </svg>
                      {:else if socialIcon(link) === 'linkedin'}
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" aria-hidden="true">
                          <path d="M26.111,3H5.889c-1.595,0-2.889,1.293-2.889,2.889V26.111c0,1.595,1.293,2.889,2.889,2.889H26.111c1.595,0,2.889-1.293,2.889-2.889V5.889c0-1.595-1.293-2.889-2.889-2.889ZM10.861,25.389h-3.877V12.87h3.877v12.519Zm-1.957-14.158c-1.267,0-2.293-1.034-2.293-2.31s1.026-2.31,2.293-2.31,2.292,1.034,2.292,2.31-1.026,2.31-2.292,2.31Zm16.485,14.158h-3.858v-6.571c0-1.802-.685-2.809-2.111-2.809-1.551,0-2.362,1.048-2.362,2.809v6.571h-3.718V12.87h3.718v1.686s1.118-2.069,3.775-2.069,4.556,1.621,4.556,4.975v7.926Z" fill-rule="evenodd" />
                        </svg>
                      {:else if socialIcon(link) === 'youtube'}
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" aria-hidden="true">
                          <path d="M31.331,8.248c-.368-1.386-1.452-2.477-2.829-2.848-2.496-.673-12.502-.673-12.502-.673,0,0-10.007,0-12.502,.673-1.377,.37-2.461,1.462-2.829,2.848-.669,2.512-.669,7.752-.669,7.752,0,0,0,5.241,.669,7.752,.368,1.386,1.452,2.477,2.829,2.847,2.496,.673,12.502,.673,12.502,.673,0,0,10.007,0,12.502-.673,1.377-.37,2.461-1.462,2.829-2.847,.669-2.512,.669-7.752,.669-7.752,0,0,0-5.24-.669-7.752ZM12.727,20.758V11.242l8.364,4.758-8.364,4.758Z" />
                        </svg>
                      {:else if socialIcon(link) === 'tiktok'}
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                          <path d="M14.8 4c.5 1.2 1.7 2.3 3.2 2.4V9a6.3 6.3 0 0 1-3.2-1v6.2a4.6 4.6 0 1 1-4.6-4.6h.4v2.6h-.4a2 2 0 1 0 2 2V4h2.6Z" />
                        </svg>
                      {:else if socialIcon(link) === 'x'}
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" aria-hidden="true">
                          <path d="M18.42,14.009L27.891,3h-2.244l-8.224,9.559L10.855,3H3.28l9.932,14.455L3.28,29h2.244l8.684-10.095,6.936,10.095h7.576l-10.301-14.991h0Zm-3.074,3.573l-1.006-1.439L6.333,4.69h3.447l6.462,9.243,1.006,1.439,8.4,12.015h-3.447l-6.854-9.804h0Z" />
                        </svg>
                      {:else if socialIcon(link) === 'bluesky'}
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" aria-hidden="true">
                          <path d="M23.931,5.298c-3.21,2.418-6.663,7.32-7.931,9.951-1.267-2.631-4.721-7.533-7.931-9.951-2.316-1.744-6.069-3.094-6.069,1.201,0,.857,.49,7.206,.778,8.237,.999,3.583,4.641,4.497,7.881,3.944-5.663,.967-7.103,4.169-3.992,7.372,5.908,6.083,8.492-1.526,9.154-3.476,.123-.36,.179-.527,.179-.379,0-.148,.057,.019,.179,.379,.662,1.949,3.245,9.558,9.154,3.476,3.111-3.203,1.671-6.405-3.992-7.372,3.24,.553,6.882-.361,7.881-3.944,.288-1.031,.778-7.38,.778-8.237,0-4.295-3.753-2.945-6.069-1.201Z" />
                        </svg>
                      {:else if socialIcon(link) === 'pinterest'}
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" aria-hidden="true">
                          <path d="M16,2C8.268,2,2,8.268,2,16c0,5.931,3.69,11.001,8.898,13.041-.122-1.108-.233-2.811,.049-4.02,.254-1.093,1.642-6.959,1.642-6.959,0,0-.419-.839-.419-2.079,0-1.947,1.128-3.4,2.533-3.4,1.194,0,1.771,.897,1.771,1.972,0,1.201-.765,2.997-1.16,4.661-.33,1.393,.699,2.53,2.073,2.53,2.488,0,4.401-2.624,4.401-6.411,0-3.352-2.409-5.696-5.848-5.696-3.983,0-6.322,2.988-6.322,6.076,0,1.203,.464,2.494,1.042,3.195,.114,.139,.131,.26,.097,.402-.106,.442-.342,1.393-.389,1.588-.061,.256-.203,.311-.468,.187-1.749-.814-2.842-3.37-2.842-5.424,0-4.416,3.209-8.472,9.25-8.472,4.857,0,8.631,3.461,8.631,8.086,0,4.825-3.042,8.708-7.265,8.708-1.419,0-2.752-.737-3.209-1.608,0,0-.702,2.673-.872,3.328-.316,1.216-1.169,2.74-1.74,3.67,1.31,.406,2.702,.624,4.145,.624,7.732,0,14-6.268,14-14S23.732,2,16,2Z" />
                        </svg>
                      {:else}
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                          <path d="M7.4 12.5a3.6 3.6 0 0 1 1.1-2.6l3.1-3.1a3.7 3.7 0 0 1 5.2 5.2l-1.7 1.7a.9.9 0 1 1-1.2-1.2l1.7-1.7a1.9 1.9 0 0 0-2.7-2.7l-3.1 3.1a1.9 1.9 0 0 0 0 2.7.9.9 0 0 1-1.3 1.2 3.6 3.6 0 0 1-1.1-2.6Zm9.2-1a3.6 3.6 0 0 1-1.1 2.6l-3.1 3.1a3.7 3.7 0 0 1-5.2-5.2l1.7-1.7a.9.9 0 1 1 1.2 1.2l-1.7 1.7a1.9 1.9 0 0 0 2.7 2.7l3.1-3.1a1.9 1.9 0 0 0 0-2.7.9.9 0 0 1 1.3-1.2 3.6 3.6 0 0 1 1.1 2.6Z" />
                        </svg>
                      {/if}
                    </a>
                  {/each}
                </div>
              {:else}
                —
              {/if}
            </td>
            <td class="audit-summary">
              <div class="audit-icons" aria-label="Latest audit results">
                {#each detailFields as field}
                  <span
                    class={`audit-icon ${statusClass(field.key, auditFieldValue(item.latest_audit, field.key))}${isOverridden(item.latest_audit, field.key) ? ' overridden' : ''}`}
                    title={`${field.label}: ${auditFieldValue(item.latest_audit, field.key) ?? '—'}`}
                    aria-label={`${field.label}: ${auditFieldValue(item.latest_audit, field.key) ?? '—'}`}
                  >
                    {field.short}
                  </span>
                {/each}
              </div>
            </td>
            <td class="actions">
              <div class="action-buttons">
                <button type="button" disabled={loading} on:click={() => dispatch('audit', { id: item.id })}>
                  Audit
                </button>
                <button
                  type="button"
                  class={`secondary${hasLookup(item) ? ' lookup-done' : ''}`}
                  disabled={loading}
                  on:click={() => dispatch('lookup', { id: item.id })}
                >
                  Lookup
                </button>
                <button
                  type="button"
                  class="secondary detail-toggle"
                  on:click={() => toggleDetails(item.id)}
                  on:mouseenter={() => showHoverDetails(item.id)}
                  on:mouseleave={() => clearHoverDetails(item.id)}
                  aria-expanded={expandedIds.has(item.id) || hoverExpandedId === item.id}
                >
                  {expandedIds.has(item.id) ? 'Hide' : hoverExpandedId === item.id ? 'Pin' : 'More ▾'}
                </button>
              </div>
            </td>
          </tr>
          {#if expandedIds.has(item.id) || hoverExpandedId === item.id}
            <tr class="detail-row">
              <td colspan="7">
                <div class="detail-content" transition:slide={{ duration: 360 }}>
                  <div class="detail-grid">
                    <div class="detail-block">
                      <h4>Audit</h4>
                      <div class="pill-row">
                        {#each detailFields as field}
                          <div class={`detail-pill ${statusClass(field.key, auditFieldValue(item.latest_audit, field.key))}${isOverridden(item.latest_audit, field.key) ? ' overridden' : ''}`}>
                            <span class="pill-label">{field.label}</span>
                            <span class="pill-value">{auditFieldValue(item.latest_audit, field.key) ?? '—'}</span>
                          </div>
                        {/each}
                      </div>
                    </div>
                    <div class="detail-block">
                      <h4>Platform</h4>
                      <div class="detail-line"><span>Owner:</span> {item.chain_owner ?? '—'}</div>
                      <div class="detail-line"><span>CMS platform:</span> {item.cms_platform ?? '—'}</div>
                      <div class="detail-line"><span>CMS vendor:</span> {item.cms_vendor ?? '—'}</div>
                      <div class="detail-line"><span>Frequency:</span> {item.publication_frequency ?? '—'}</div>
                    </div>
                    <div class="detail-block">
                      <h4>Contact</h4>
                      <div class="detail-line"><span>Primary contact:</span> {primaryContact(item) ?? '—'}</div>
                      <div class="detail-line"><span>Phone:</span> {item.phone ?? '—'}</div>
                      <div class="detail-line"><span>Email:</span> {item.email ?? '—'}</div>
                    </div>
                  </div>
                </div>
              </td>
            </tr>
          {/if}
        {/each}
      {/if}
    </tbody>
  </table>

  <div class="pagination">
    <div class="pagination-controls">
      <button type="button" on:click={goToFirst} disabled={currentPage === 1 || loading}>First</button>
      <button type="button" on:click={() => goToPage(currentPage - 1)} disabled={currentPage === 1 || loading}>
        Previous
      </button>
      <span class="page-indicator">Page {currentPage} of {totalPages}</span>
      <button
        type="button"
        on:click={() => goToPage(currentPage + 1)}
        disabled={currentPage === totalPages || loading}
      >
        Next
      </button>
      <button type="button" on:click={goToLast} disabled={currentPage === totalPages || loading}>Last</button>
    </div>
    <div class="pagination-summary">
      {#if total === 0}
        <span>No results</span>
      {:else}
        <span>Showing {startEntry}&ndash;{endEntry} of {total}</span>
      {/if}
    </div>
  </div>
</div>

<style>
  .table-wrapper {
    background: white;
    border-radius: 0.75rem;
    border: 1px solid #e5e7eb;
    overflow: visible;
    position: relative;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  thead {
    background-color: #f9fafb;
  }

  thead th {
    position: sticky;
    top: 0;
    z-index: 2;
    background-color: #f9fafb;
    box-shadow: inset 0 -1px 0 #e5e7eb;
  }

  th,
  td {
    text-align: left;
    padding: 0.75rem;
    border-bottom: 1px solid #e5e7eb;
    font-size: 0.9rem;
  }

  th.sortable {
    padding: 0;
  }

  th.sortable button {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 0.35rem;
    background: transparent;
    border: none;
    padding: 0.75rem;
    font: inherit;
    text-align: left;
    color: inherit;
    cursor: pointer;
  }

  th.sortable button:hover,
  th.sortable button:focus {
    background-color: #eef2ff;
    outline: none;
  }

  thead th.sortable button {
    background-color: transparent;
  }

  thead th.sortable button:hover,
  thead th.sortable button:focus {
    background-color: #e0e7ff;
  }

  .sort-indicator {
    font-size: 0.75rem;
    color: #6b7280;
  }

  th.select,
  td.select {
    width: 3rem;
    text-align: center;
  }

  th.actions,
  td.actions {
    width: 18rem;
  }

  th.audit-summary,
  td.audit-summary {
    width: 19rem;
  }

  td.paper-cell {
    max-width: 18rem;
  }

  td.paper-cell a.paper-link {
    display: inline-block;
    max-width: 100%;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  a.paper-link {
    color: #111827;
    font-weight: 600;
    text-decoration: none;
  }

  a.external {
    color: #2563eb;
  }

  .link-icons {
    display: flex;
    gap: 0.55rem;
    flex-wrap: wrap;
    align-items: center;
  }

  .icon-link {
    width: 2.2rem;
    height: 2.2rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 0;
    border: none;
    background: transparent;
    color: #111827;
  }

  .icon-link:hover {
    color: #2563eb;
    background: transparent;
  }

  .icon-link svg {
    width: 1.75rem;
    height: 1.75rem;
    fill: currentColor;
  }

  .icon-link.social {
    color: #111827;
  }

  .icon-link.facebook:hover {
    color: #1877f2;
  }

  .icon-link.instagram:hover {
    color: #dd2a7b;
  }

  .icon-link.x:hover {
    color: #1d9bf0;
  }

  .icon-link.youtube:hover {
    color: #ff0000;
  }

  .icon-link.linkedin:hover {
    color: #0a66c2;
  }

  .icon-link.bluesky:hover {
    color: #0ea5e9;
  }

  .icon-link.pinterest:hover {
    color: #e60023;
  }

  button {
    padding: 0.35rem 0.75rem;
    border-radius: 0.5rem;
    border: none;
    background-color: #2563eb;
    color: white;
    font-weight: 600;
    cursor: pointer;
  }

  button[disabled] {
    opacity: 0.6;
    cursor: not-allowed;
  }

  button.secondary {
    background-color: #f3f4f6;
    color: #111827;
    border: 1px solid #e5e7eb;
  }

  button.detail-toggle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 4.5rem;
  }

  button.lookup-done {
    background-color: #16a34a;
    border-color: #15803d;
    color: #ffffff;
  }

  .audit-icons {
    display: inline-flex;
    gap: 0.4rem;
    flex-wrap: wrap;
  }

  .audit-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 2.25rem;
    padding: 0.15rem 0.35rem;
    border-radius: 999px;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    border: 1px solid #e5e7eb;
    background: #f3f4f6;
    color: #374151;
  }

  .audit-icon.overridden {
    border-color: rgba(59, 130, 246, 0.35);
    background: rgba(219, 234, 254, 0.85);
    color: #1d4ed8;
  }

  .audit-icon.status.yes {
    border-color: rgba(22, 163, 74, 0.25);
    background: rgba(220, 252, 231, 0.85);
    color: #166534;
  }

  .audit-icon.status.no {
    border-color: rgba(239, 68, 68, 0.25);
    background: rgba(254, 226, 226, 0.85);
    color: #b91c1c;
  }

  .audit-icon.status.review {
    border-color: rgba(245, 158, 11, 0.25);
    background: rgba(254, 243, 199, 0.85);
    color: #b45309;
  }

  .audit-icon.status.neutral {
    border-color: #e5e7eb;
    background: #f3f4f6;
    color: #374151;
  }
  .action-buttons {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .detail-row td {
    background: #f9fafb;
    padding: 0;
  }

  .detail-content {
    overflow: hidden;
  }
  .detail-grid {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    padding: 1rem 1.25rem;
  }

  .detail-block h4 {
    margin: 0 0 0.5rem;
    font-size: 0.9rem;
    color: #111827;
  }

  .detail-line {
    display: flex;
    gap: 0.5rem;
    font-size: 0.85rem;
    color: #374151;
  }

  .detail-line span {
    font-weight: 600;
    color: #111827;
  }

  .pill-row {
    display: grid;
    gap: 0.5rem;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  }

  .detail-pill {
    border-radius: 0.75rem;
    padding: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    box-shadow: inset 0 0 0 1px #e5e7eb;
    background: #ffffff;
  }

  .detail-pill.overridden {
    box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.35);
  }

  .detail-pill.status.yes {
    box-shadow: inset 0 0 0 1px rgba(22, 163, 74, 0.25);
    background: rgba(220, 252, 231, 0.85);
    color: #166534;
  }

  .detail-pill.status.no {
    box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.25);
    background: rgba(254, 226, 226, 0.85);
    color: #b91c1c;
  }

  .detail-pill.status.review {
    box-shadow: inset 0 0 0 1px rgba(245, 158, 11, 0.25);
    background: rgba(254, 243, 199, 0.85);
    color: #b45309;
  }

  .detail-pill.status.neutral {
    box-shadow: inset 0 0 0 1px #e5e7eb;
    background: #f3f4f6;
    color: #374151;
  }

  .pill-label {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .pill-value {
    font-weight: 700;
    font-size: 0.9rem;
  }

  .empty {
    text-align: center;
    padding: 2rem;
    color: #6b7280;
  }

  .pagination {
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    align-items: center;
  }

  .pagination-controls {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
    justify-content: center;
  }

  .page-indicator {
    font-weight: 600;
    color: #111827;
  }

  .pagination-summary {
    color: #4b5563;
    font-size: 0.9rem;
  }
</style>
