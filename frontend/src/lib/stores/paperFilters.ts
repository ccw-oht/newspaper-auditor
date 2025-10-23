import { browser } from '$app/environment';
import { writable, type Writable } from 'svelte/store';

const defaultValue = '';

const createPaperFilterQuery = (): Writable<string> => {
  const store = writable(defaultValue);
  if (!browser) {
    return {
      subscribe: store.subscribe,
      set: () => {
        /* no-op on server to avoid leaking state */
      },
      update: (_updater) => {
        /* no-op on server to avoid leaking state */
      }
    } satisfies Writable<string>;
  }

  return store;
};

export const paperFilterQuery = createPaperFilterQuery();
