#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "Missing .env. Copy .env.example and configure ElevenLabs credentials." >&2
  exit 1
fi

set -a
source .env
set +a

if [[ "${APP_ENV:-development}" != "development" ]]; then
  echo "The ElevenLabs API tester runs only with APP_ENV=development." >&2
  exit 1
fi

if [[ -z "${ELEVENLABS_API_KEY:-}" || "${ELEVENLABS_API_KEY}" == replace-with-* ]]; then
  echo "ELEVENLABS_API_KEY is not configured." >&2
  exit 1
fi

echo "Starting local ElevenLabs API tester at http://127.0.0.1:4010 (credentials stay server-side)."
exec .venv/bin/python -m uvicorn tools.elevenlabs_api_tester.server:app --host 127.0.0.1 --port 4010 --log-level debug