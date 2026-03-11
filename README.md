# Newspaper Audit API

Automates auditing of newspaper websites, persists results in Postgres, and exposes them through a FastAPI service. This document summarizes the current capabilities, explains how to run the stack locally, and outlines the key CLI utilities for working with CSV data and per-site audits.

## Project Structure
- `backend/` – FastAPI application, audit logic, SQLAlchemy models, CSV utilities.
- `docker/` – Compose definition and API Dockerfile.
- `test-csv/` – Sample CSVs you can ingest while experimenting.

## Prerequisites
- Docker Desktop or Docker Engine 20+
- Python 3.11 (optional, if you want to run loaders/CLI outside Docker)

## Environment Variables
The backend reads `DATABASE_URL`. By default it uses local Postgres on `localhost:55432`:

```bash
export DATABASE_URL=postgresql://audit_user:audit_pass@localhost:55432/auditdb
```

If you run the API inside Docker, set `DATABASE_URL` explicitly (for example: `postgresql://audit_user:audit_pass@db:5432/auditdb`).

The lookup feature uses Gemini and requires an API key:

```bash
export GEMINI_API_KEY=your_key_here
```

## Running the Stack
Only Postgres runs in Docker; the FastAPI backend, background worker, and frontend run locally.

### One-command local dev

```bash
make dev
```

This starts:
- Postgres in Docker
- FastAPI on `http://localhost:8000`
- The background job worker
- The frontend on `http://localhost:5173`

This is the recommended local workflow because audits and lookups triggered from the UI are queued background jobs. If the worker is not running, a new audit will stay queued and appear to do nothing.

### Cleaning up local processes

If you have multiple terminal tabs open, it is easy to leave old backend or frontend dev servers running and then hit port conflicts the next time you start work in this repo.

Check what is listening on the common local ports:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
lsof -nP -iTCP:5173 -sTCP:LISTEN
lsof -nP -iTCP:55432 -sTCP:LISTEN
```

Typical meanings in this project:
- `8000` – FastAPI backend
- `5173` – Svelte/Vite frontend
- `55432` – Postgres from Docker

To stop a local dev server by PID:

```bash
kill <pid>
```

If it does not exit cleanly:

```bash
kill -9 <pid>
```

For Docker-managed Postgres, prefer stopping it cleanly with:

```bash
make compose-down
```

If `make dev` reports that `:8000` or `:5173` is already in use, run the `lsof` commands above first and clear out the older process before starting again.

### Start / Stop Postgres
- **Start**
  ```bash
  make compose-up
  ```
- **Stop**
  ```bash
  make compose-down
  ```
- **Fresh start (drops volume)**
  ```bash
  make compose-down-clean
  ```

Postgres is exposed on `localhost:55432`.

To open a psql shell:

```bash
make db-shell
```

### Backend Dev Server (hot reload)
1. Ensure the virtual environment and dependencies are installed (handled automatically the first time you run the target).
2. Launch FastAPI with auto-reload:
   ```bash
   make dev-backend
   ```

The API listens on `http://localhost:8000` and reloads whenever files under `backend/` change.

### Background Worker

Run this in a separate terminal if you are not using `make dev`:

```bash
make dev-worker
```

The frontend queues audits and lookups through `/jobs/*`; the worker is what actually executes them.

### Frontend Dev Server
From the project root:

```bash
make dev-frontend
```

The first run installs frontend dependencies under `frontend/`. A Vite/SvelteKit dev server starts (default at `http://localhost:5173/`) and hot reloads on file changes.

### CSV Import Preview

- The API exposes `/imports/preview` and `/imports/commit` for CSV ingestion.
- A UI is available at `http://localhost:5173/imports` to upload a CSV, review staged rows, choose actions (insert/overwrite/merge/skip), and commit changes.
- When running commands manually, ensure `python-multipart` is installed (`pip install python-multipart`).

## Database Utilities

Enter Postgres shell:

```bash
cd docker
docker compose exec db psql -U audit_user -d auditdb
```

Helpful psql commands:

- `\dt` – list tables (`papers`, `audits`).
- `\d papers` – describe the `papers` table schema.
- `\q` – quit.

## CLI: Audit Runner
The core audit logic lives in `backend/audit.py`. You can run it against a CSV file to generate audit columns.

```bash
python -m backend.audit path/to/input.csv [--force]
```

- `--force` ignores any existing `<basename>_Audit.csv` and rebuilds results.
- Without `--force`, the script resumes from cached results when possible.

The command outputs progress to the terminal and writes `<basename>_Audit.csv` in the same directory as the input file.

### Browser Automation for Anti-Bot Protection

The audit script now includes automatic browser automation fallback for websites with anti-bot protection (like McClatchy sites). This uses Playwright with stealth mode to bypass JavaScript-based protection.

**Setup:**
1. Install Python dependencies (includes `playwright` and `playwright-stealth`):
   ```bash
   pip install -r requirements.txt
   ```

2. Install Playwright browsers:
   ```bash
   playwright install chromium
   ```

**How it works:**
- The script first attempts standard HTTP requests with browser-like headers
- If a request fails with HTTP 403 (Forbidden) or the domain is known to have anti-bot protection, it automatically falls back to browser automation
- Browser automation uses stealth mode to avoid detection
- Known protected domains (McClatchy sites) automatically use browser automation
- Do not enable `AUDIT_PLAYWRIGHT_ONLY=1` for normal local work unless you are actively debugging fetch behavior. That flag forces browser automation for every site and makes audits slower and more fragile.

**Known protected domains:**
- McClatchy newspaper sites (miamiherald.com, sacbee.com, kansascity.com, etc.)
- Automatically detected by domain matching

You can add more domains to the `BROWSER_REQUIRED_DOMAINS` set in `backend/audit.py` if needed.

## CLI: Paper Loader
`backend/load_papers.py` ingests CSV rows into the `papers` table, handling deduplication and optional truncation. Unknown CSV columns are stored inside the `extra_data` JSON field.

Dry run:

```bash
python -m backend.load_papers path/to/papers.csv --dry-run
```

Actual ingest:

```bash
python -m backend.load_papers path/to/papers.csv
```

Optional flags:
- `--truncate` – clears `audits` and `papers` tables before loading.
- `--dry-run` – parses and reports counts without writing.

> Tip: run `--dry-run` first to verify skip counts and column mappings.

You can also use the Makefile helper (ensures the virtual environment is active):

```bash
make ingest CSV=path/to/papers.csv
```
Add `OPTS="--dry-run"` or other flags to pass options through.

## API Smoke Tests

With Postgres running (`make compose-up`) and the dev server active (`make dev-backend`):

- Root: `curl http://localhost:8000/`
- Papers list: `curl http://localhost:8000/papers`
- Single audit trigger: `curl -X POST http://localhost:8000/audits/1`
- Batch audit trigger:
  ```bash
  curl -X POST http://localhost:8000/audits/batch \
       -H "Content-Type: application/json" \
       -d '{"ids": [1, 2, 3]}'
  ```
- Single lookup trigger:
  ```bash
  curl -X POST http://localhost:8000/lookup/1
  ```
- Batch lookup trigger:
  ```bash
  curl -X POST http://localhost:8000/lookup/batch \
       -H "Content-Type: application/json" \
       -d '{"ids": [1, 2, 3]}'
  ```

Responses are serialized via Pydantic schemas (`backend/schemas.py`) and include any `extra_data` captured during ingest.

## Common Maintenance Tasks

- **Rebuild tables (fresh start)**:
  ```bash
  docker compose down -v
  docker compose up -d --build
  ```
  The `-v` flag removes the Postgres volume, wiping all data.

- **Schema adjustments**:
  Use `psql` to run `ALTER TABLE` statements whenever the SQLAlchemy models change (e.g., dropping unique constraints or adding columns). For example, adding the chain/vendor/platform columns introduced in July 2024:
  ```sql
  ALTER TABLE papers ADD COLUMN chain_owner TEXT;
  ALTER TABLE papers ADD COLUMN cms_platform TEXT;
  ALTER TABLE papers ADD COLUMN cms_vendor TEXT;
  ```

- **Add email column (Lookup feature)**:
  ```bash
  make migrate-email
  ```

- **View audit history for a paper**:
  ```sql
  SELECT * FROM audits WHERE paper_id = <id> ORDER BY timestamp DESC;
  ```
  Run inside `psql` after connecting to the database container.

## Troubleshooting

- **Port already allocated** – adjust host port mappings in `docker/docker-compose.yml` (Postgres defaults to `55432:5432`; change the left-hand port if it collides).
- **Database host not found** – ensure `DATABASE_URL` is set to `localhost` when running scripts outside Docker.
- **Unique constraint errors during ingest** – run `--dry-run` to identify duplicates; the loader now merges rows by `(paper_name, city, state)`.

## What’s Next
- Frontend UI for browsing papers/audits and triggering audits interactively.
- Upload flow for CSV ingest through the web interface.
- Additional heuristics and detectors as outlined in `app-spec.md`.

---

Feel free to expand this README as the project evolves (tests, deployment steps, frontend instructions, etc.).
