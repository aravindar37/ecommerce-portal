#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
[[ -f .env ]] || { echo "Missing .env." >&2; exit 1; }
set -a
source .env
set +a

PYTHON_BIN="${PYTHON_BIN:-$PWD/.venv/bin/python}"
[[ -x "$PYTHON_BIN" ]] || PYTHON_BIN=python3
mkdir -p artifacts/logs

start() {
  local name="$1" port="$2" module_path="$3"
  if curl --silent --fail --max-time 1 "http://127.0.0.1:${port}/api/health" >/dev/null; then
    echo "$name is already running on port $port"
    return
  fi
  echo "Starting $name on port $port; logs: artifacts/logs/${name}.log"
  env PYTHONPATH="$module_path${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port "$port" >"artifacts/logs/${name}.log" 2>&1 &
}

wait_for() {
  local port="$1"
  for _ in {1..30}; do
    curl --silent --fail --max-time 1 "http://127.0.0.1:${port}/api/health" >/dev/null && return 0
    sleep 1
  done
  return 1
}

start core_service 4000 "$PWD/services/core_service"
wait_for 4000 || { echo "Core Service failed; see artifacts/logs/core_service.log" >&2; exit 1; }
start search_service 4001 "$PWD/services/search_service"
start chat_service 4002 "$PWD/services/chat_service"
wait_for 4001 || { echo "Search Service failed; see artifacts/logs/search_service.log" >&2; exit 1; }
wait_for 4002 || { echo "Chat Service failed; see artifacts/logs/chat_service.log" >&2; exit 1; }
echo "Core, Search, and Chat Service are ready. They remain running in the background."
