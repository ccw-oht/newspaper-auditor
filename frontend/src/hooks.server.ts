import type { Handle } from '@sveltejs/kit';

export const handle: Handle = async ({ event, resolve }) => {
  // Suppress Chrome DevTools well-known path requests (harmless 404s)
  if (event.url.pathname.includes('.well-known/appspecific')) {
    return new Response('Not Found', { status: 404 });
  }

  return resolve(event);
};

