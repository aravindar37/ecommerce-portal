#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
[[ -f .env ]] || { echo "Missing .env." >&2; exit 1; }
set -a
source .env
set +a

[[ "${APP_ENV:-development}" == "development" ]] || { echo "The local voice tester requires APP_ENV=development." >&2; exit 1; }
: "${VOICE_STREAM_WS_AUTH_TOKEN:?VOICE_STREAM_WS_AUTH_TOKEN is required}"
: "${TEST_ADMIN_TOKEN:?TEST_ADMIN_TOKEN is required}"

echo "Starting local voice call tester at http://127.0.0.1:4011"
exec .venv/bin/python -m uvicorn tools.local_voice_call_tester.server:app --host 127.0.0.1 --port 4011 --log-level debug
