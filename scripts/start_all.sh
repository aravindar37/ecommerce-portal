#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/.env}"
DEFAULT_PYTHON_BIN="python3"
if [[ -x "${REPO_ROOT}/.venv/bin/python3" ]]; then
  DEFAULT_PYTHON_BIN="${REPO_ROOT}/.venv/bin/python3"
fi
PYTHON_BIN="${PYTHON_BIN:-${DEFAULT_PYTHON_BIN}}"
NPM_BIN="${NPM_BIN:-npm}"
HOST="${HOST:-127.0.0.1}"

CORE_PORT="${CORE_PORT:-4000}"
SEARCH_PORT="${SEARCH_PORT:-4001}"
CHAT_PORT="${CHAT_PORT:-4002}"
WEB_PORT="${WEB_PORT:-3000}"

LOG_DIR="${LOG_DIR:-${REPO_ROOT}/artifacts/logs}"
PID_DIR="${PID_DIR:-${REPO_ROOT}/artifacts/pids}"

declare -a STARTED_PIDS=()
declare -a STARTED_NAMES=()
CLEANED_UP=false

usage() {
  cat <<'USAGE'
Usage: ./scripts/start_all.sh

Starts Core, Search, Chat, and Web using .env from the repository root.
Copy .env.example to .env and fill in your credentials before running.

Optional environment variables:
  ENV_FILE=/path/to/.env
  HOST=127.0.0.1
  CORE_PORT=4000
  SEARCH_PORT=4001
  CHAT_PORT=4002
  WEB_PORT=3000
  LOG_DIR=./artifacts/logs
  PID_DIR=./artifacts/pids
  PYTHON_BIN=.venv/bin/python3
  NPM_BIN=npm

Press Ctrl-C to stop all processes started by this script.
USAGE
}

log() {
  printf '[start_all] %s\n' "$*"
}

fail() {
  printf '[start_all] error: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1 — make sure it is installed and on PATH"
}

require_python_module() {
  local module_name="$1"
  if ! "${PYTHON_BIN}" -c "import ${module_name}" >/dev/null 2>&1; then
    fail "Python module '${module_name}' is not installed for ${PYTHON_BIN}. Run: ${PYTHON_BIN} -m pip install -e services/core_service -e services/search_service -e services/chat_service"
  fi
}

load_env() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    if [[ -f "${REPO_ROOT}/.env.example" ]]; then
      fail "environment file not found: ${ENV_FILE}
       Copy .env.example and fill in your credentials:
         cp ${REPO_ROOT}/.env.example ${REPO_ROOT}/.env"
    else
      fail "environment file not found: ${ENV_FILE}"
    fi
  fi
  log "loading environment from ${ENV_FILE}"
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
}

wait_for_http() {
  local name="$1"
  local url="$2"
  local attempts="${3:-60}"
  local delay_seconds="${4:-1}"
  local attempt
  for ((attempt = 1; attempt <= attempts; attempt += 1)); do
    if curl -fsS -o /dev/null "${url}" >/dev/null 2>&1; then
      log "${name} ready: ${url}"
      return 0
    fi
    sleep "${delay_seconds}"
  done
  return 1
}

is_ready() {
  local url="$1"
  curl -fsS -o /dev/null "${url}" >/dev/null 2>&1
}

start_process() {
  local name="$1"
  local log_file="$2"
  shift 2
  log "starting ${name}; log: ${log_file}"
  "$@" >"${log_file}" 2>&1 &
  local pid="$!"
  STARTED_PIDS+=("${pid}")
  STARTED_NAMES+=("${name}")
  printf '%s\n' "${pid}" >"${PID_DIR}/${name}.pid"
}

start_process_in_dir() {
  local name="$1"
  local log_file="$2"
  local run_dir="$3"
  shift 3
  log "starting ${name}; log: ${log_file}"
  (
    cd "${run_dir}"
    "$@"
  ) >"${log_file}" 2>&1 &
  local pid="$!"
  STARTED_PIDS+=("${pid}")
  STARTED_NAMES+=("${name}")
  printf '%s\n' "${pid}" >"${PID_DIR}/${name}.pid"
}

cleanup() {
  local index
  if [[ "${CLEANED_UP}" == "true" ]]; then
    return
  fi
  CLEANED_UP=true
  if [[ "${#STARTED_PIDS[@]}" -eq 0 ]]; then
    return
  fi
  log "stopping processes started by this script"
  for index in "${!STARTED_PIDS[@]}"; do
    local pid="${STARTED_PIDS[${index}]}"
    local name="${STARTED_NAMES[${index}]}"
    if kill -0 "${pid}" >/dev/null 2>&1; then
      log "stopping ${name} (${pid})"
      kill "${pid}" >/dev/null 2>&1 || true
    fi
  done
}

watch_started_processes() {
  local index
  log "all services are ready"
  log "frontend:     http://${HOST}:${WEB_PORT}"
  log "core service: http://${HOST}:${CORE_PORT}/api/health"
  log "search:       http://${HOST}:${SEARCH_PORT}/api/health"
  log "chat:         http://${HOST}:${CHAT_PORT}/api/health"
  log "press Ctrl-C to stop all processes started by this script"
  while true; do
    for index in "${!STARTED_PIDS[@]}"; do
      local pid="${STARTED_PIDS[${index}]}"
      local name="${STARTED_NAMES[${index}]}"
      if ! kill -0 "${pid}" >/dev/null 2>&1; then
        log "${name} exited unexpectedly; see ${LOG_DIR}/${name}.log"
        exit 1
      fi
    done
    sleep 2
  done
}

main() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
  fi

  require_command curl

  # Create all artifact directories upfront
  mkdir -p \
    "${LOG_DIR}" \
    "${PID_DIR}" \
    "${REPO_ROOT}/artifacts/core_service" \
    "${REPO_ROOT}/artifacts/chat_service" \
    "${REPO_ROOT}/artifacts/ingestion" \
    "${REPO_ROOT}/artifacts/embeddings"

  load_env
  require_command "${PYTHON_BIN}"
  require_command "${NPM_BIN}"
  require_python_module fastapi
  require_python_module uvicorn

  local core_url="http://${HOST}:${CORE_PORT}/api/health"
  local search_url="http://${HOST}:${SEARCH_PORT}/api/health"
  local chat_url="http://${HOST}:${CHAT_PORT}/api/health"
  local web_url="http://${HOST}:${WEB_PORT}"

  trap cleanup EXIT INT TERM

  # ── Core Service ────────────────────────────────────────────────────────────
  if is_ready "${core_url}"; then
    log "Core Service already running: ${core_url}"
  else
    start_process "core_service" "${LOG_DIR}/core_service.log" \
      env PYTHONPATH="${REPO_ROOT}/services/core_service${PYTHONPATH:+:${PYTHONPATH}}" \
      "${PYTHON_BIN}" -m uvicorn app.main:app --host "${HOST}" --port "${CORE_PORT}"

    # Search and Chat both read Core state on startup — wait for Core before
    # starting them so they don't miss seeded data or fail connection checks.
    wait_for_http "Core Service" "${core_url}" 60 1 \
      || fail "Core Service did not become healthy; see ${LOG_DIR}/core_service.log"
  fi

  # ── Search Service ──────────────────────────────────────────────────────────
  if is_ready "${search_url}"; then
    log "Search Service already running: ${search_url}"
  else
    start_process "search_service" "${LOG_DIR}/search_service.log" \
      env PYTHONPATH="${REPO_ROOT}/services/search_service${PYTHONPATH:+:${PYTHONPATH}}" \
      "${PYTHON_BIN}" -m uvicorn app.main:app --host "${HOST}" --port "${SEARCH_PORT}"
    wait_for_http "Search Service" "${search_url}" 60 1 \
      || fail "Search Service did not become healthy; see ${LOG_DIR}/search_service.log"
  fi

  # ── Chat Service ────────────────────────────────────────────────────────────
  if is_ready "${chat_url}"; then
    log "Chat Service already running: ${chat_url}"
  else
    start_process "chat_service" "${LOG_DIR}/chat_service.log" \
      env PYTHONPATH="${REPO_ROOT}/services/chat_service${PYTHONPATH:+:${PYTHONPATH}}" \
      "${PYTHON_BIN}" -m uvicorn app.main:app --host "${HOST}" --port "${CHAT_PORT}"
    wait_for_http "Chat Service" "${chat_url}" 60 1 \
      || fail "Chat Service did not become healthy; see ${LOG_DIR}/chat_service.log"
  fi

  # ── Web (Next.js dev server) ────────────────────────────────────────────────
  # Started last — all backends are confirmed healthy before the UI launches.
  if is_ready "${web_url}"; then
    log "Web app already running: ${web_url}"
  else
    # Clear the Next.js build cache before starting the dev server.
    # A stale or production-mode .next directory causes ChunkLoadErrors and
    # 500s on page routes when the dev server restarts after a rebuild.
    if [[ -d "${REPO_ROOT}/apps/web/.next" ]]; then
      log "clearing stale .next build cache"
      rm -rf "${REPO_ROOT}/apps/web/.next"
    fi
    start_process_in_dir "web" "${LOG_DIR}/web.log" "${REPO_ROOT}/apps/web" \
      "${NPM_BIN}" exec -- next dev --hostname "${HOST}" --port "${WEB_PORT}"
    # next dev compiles lazily on first request — allow extra time
    wait_for_http "Web app" "${web_url}" 120 1 \
      || fail "Web app did not become healthy; see ${LOG_DIR}/web.log"
  fi

  if [[ "${#STARTED_PIDS[@]}" -eq 0 ]]; then
    log "all services were already running"
    log "frontend: ${web_url}"
    exit 0
  fi

  watch_started_processes
}

main "$@"
