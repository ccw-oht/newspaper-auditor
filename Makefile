.PHONY: help dev-backend dev-frontend compose-up compose-down compose-down-clean ingest install frontend-install

help:
	@echo "Available targets:"
	@echo "  dev-backend  - Run FastAPI app with hot reload"
	@echo "  dev-frontend - Run frontend dev server (SvelteKit)"
	@echo "  compose-up   - Start Postgres via docker compose"
	@echo "  compose-down - Stop Postgres and remove containers"
	@echo "  ingest       - Example: make ingest CSV=path/to/file.csv"

DATABASE_URL ?= postgresql://audit_user:audit_pass@localhost:55432/auditdb

export DATABASE_URL

VENV ?= .venv
PYTHON ?= python3
UVICORN ?= uvicorn
FRONTEND_DIR ?= frontend
NPM ?= npm

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

frontend-install:
	cd $(FRONTEND_DIR) && $(NPM) install

dev-frontend: frontend-install
	cd $(FRONTEND_DIR) && $(NPM) run dev -- --host

ingest: install
	@if [ -z "$(CSV)" ]; then \
		echo "Usage: make ingest CSV=path/to/file.csv [OPTS=...]"; \
		exit 1; \
	fi
	. $(VENV)/bin/activate && $(PYTHON) -m backend.load_papers $(CSV) $(OPTS)
