#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON:-python3}"
UVICORN_BIN="${UVICORN:-uvicorn}"
NPM_BIN="${NPM:-npm}"
FRONTEND_DIR="${FRONTEND_DIR:-$ROOT_DIR/frontend}"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Virtual environment not found at $VENV_DIR"
  echo "Run 'make install' first."
  exit 1
fi

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  if [[ -n "${backend_pid:-}" ]]; then
    kill "$backend_pid" >/dev/null 2>&1 || true
  fi
  if [[ -n "${worker_pid:-}" ]]; then
    kill "$worker_pid" >/dev/null 2>&1 || true
  fi
  if [[ -n "${frontend_pid:-}" ]]; then
    kill "$frontend_pid" >/dev/null 2>&1 || true
  fi
  wait >/dev/null 2>&1 || true
  exit "$exit_code"
}

prefix_logs() {
  local label="$1"
  while IFS= read -r line; do
    printf '[%s] %s\n' "$label" "$line"
  done
}

trap cleanup EXIT INT TERM

echo "Starting backend on http://localhost:8000"
(
  cd "$ROOT_DIR"
  . "$VENV_DIR/bin/activate"
  exec "$UVICORN_BIN" backend.app:app --reload --host 0.0.0.0 --port 8000 2>&1
) | prefix_logs "backend" &
backend_pid=$!

echo "Starting audit worker"
(
  cd "$ROOT_DIR"
  . "$VENV_DIR/bin/activate"
  exec "$PYTHON_BIN" -m backend.services.job_worker 2>&1
) | prefix_logs "worker" &
worker_pid=$!

echo "Starting frontend on http://localhost:5173"
(
  cd "$FRONTEND_DIR"
  exec "$NPM_BIN" run dev -- --host 2>&1
) | prefix_logs "frontend" &
frontend_pid=$!

while true; do
  if ! kill -0 "$backend_pid" >/dev/null 2>&1; then
    wait "$backend_pid"
    exit $?
  fi
  if ! kill -0 "$worker_pid" >/dev/null 2>&1; then
    wait "$worker_pid"
    exit $?
  fi
  if ! kill -0 "$frontend_pid" >/dev/null 2>&1; then
    wait "$frontend_pid"
    exit $?
  fi
  sleep 1
done
