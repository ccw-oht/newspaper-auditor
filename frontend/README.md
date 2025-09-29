# Newspaper Audit UI (SvelteKit)

SvelteKit + TypeScript front end for browsing papers, filtering audits, and triggering re-runs.

## Getting Started

```bash
cd frontend
npm install
npm run dev
```

The dev server runs on <http://localhost:5173>. By default, API requests proxy to `http://localhost:18080` (matching the Docker compose mapping). Adjust `VITE_API_BASE_URL` or the proxy in `vite.config.ts` if your backend uses a different host/port.

## Environment Variables

Create a `.env` file in `frontend/` if you need to point at a different API:

```ini
PUBLIC_API_BASE_URL=http://localhost:18080
```

The proxy handles `/api/*` routes in dev. In production, the client uses `PUBLIC_API_BASE_URL` to hit the FastAPI service directly.

## Scripts

- `npm run dev` – start Vite in development mode.
- `npm run build` – produce a production build.
- `npm run preview` – preview production output locally.
- `npm run check` – run Svelte type checking.
- `npm run lint` – run ESLint.

## Project Structure

```
frontend/
├── src/
│   ├── lib/
│   │   ├── api/        # API clients and helpers
│   │   ├── components/ # Svelte components
│   │   └── types.ts    # Shared TypeScript interfaces
│   └── routes/
│       ├── +layout.svelte
│       ├── +page.svelte (redirects to /papers)
│       └── papers/
│           ├── +page.ts / +page.svelte
│           └── [id]/+page.ts / +page.svelte
└── vite.config.ts
```

## Next Steps

- Flesh out UI polish and responsive design.
- Add client-side caching/state management as needed.
- Hook up authentication when the backend supports it.
