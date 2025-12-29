.PHONY: help dev-backend dev-frontend compose-up compose-down compose-down-clean ingest install frontend-install migrate-email migrate-publication-frequency db-shell

help:
	@echo "Available targets:"
	@echo "  dev-backend  - Run FastAPI app with hot reload"
	@echo "  dev-frontend - Run frontend dev server (SvelteKit)"
	@echo "  compose-up   - Start Postgres via docker compose"
	@echo "  compose-down - Stop Postgres and remove containers"
	@echo "  migrate-email - Add the email column to papers"
	@echo "  migrate-publication-frequency - Add the publication_frequency column to papers"
	@echo "  db-shell     - Open a psql shell in the Postgres container"
	@echo "  ingest       - Example: make ingest CSV=path/to/file.csv"

DATABASE_URL ?= postgresql://audit_user:audit_pass@localhost:55432/auditdb

export DATABASE_URL

VENV ?= .venv
PYTHON ?= python3
UVICORN ?= uvicorn
FRONTEND_DIR ?= frontend
NPM ?= npm
FRONTEND_STAMP ?= $(FRONTEND_DIR)/node_modules/.install-complete

$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)

install: $(VENV)/bin/activate requirements.txt
	. $(VENV)/bin/activate && pip install -r requirements.txt

compose-up:
	cd docker && docker compose up -d

compose-down:
	cd docker && docker compose down

compose-down-clean:
	cd docker && docker compose down -v

dev-backend: install
	. $(VENV)/bin/activate && $(UVICORN) backend.app:app --reload --host 0.0.0.0 --port 8000

frontend-install: $(FRONTEND_STAMP)

$(FRONTEND_STAMP): $(FRONTEND_DIR)/package.json $(FRONTEND_DIR)/package-lock.json
	cd $(FRONTEND_DIR) && $(NPM) install --no-fund --no-audit
	@mkdir -p $(dir $(FRONTEND_STAMP))
	@touch $(FRONTEND_STAMP)

dev-frontend: frontend-install
	cd $(FRONTEND_DIR) && $(NPM) run dev -- --host

ingest: install
	@if [ -z "$(CSV)" ]; then \
		echo "Usage: make ingest CSV=path/to/file.csv [OPTS=...]"; \
		exit 1; \
	fi
	. $(VENV)/bin/activate && $(PYTHON) -m backend.load_papers $(CSV) $(OPTS)

migrate-email: install
	. $(VENV)/bin/activate && $(PYTHON) -m backend.migrations.add_paper_email

migrate-publication-frequency: install
	. $(VENV)/bin/activate && $(PYTHON) -m backend.migrations.add_publication_frequency
db-shell:
	cd docker && docker compose exec db psql -U audit_user -d auditdb
