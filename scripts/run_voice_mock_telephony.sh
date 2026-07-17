#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

if [[ "${APP_ENV:-development}" != "development" ]]; then
  echo "Voice mock telephony is available only when APP_ENV=development." >&2
  exit 1
fi

case "${VOICE_TELEPHONY_PROVIDER:-local}" in
  local) ;;
  elevenlabs_twilio)
    echo "VOICE_TELEPHONY_PROVIDER=elevenlabs_twilio is reserved for Phase F and is not implemented." >&2
    exit 1
    ;;
  *)
    echo "Unsupported VOICE_TELEPHONY_PROVIDER: ${VOICE_TELEPHONY_PROVIDER}" >&2
    exit 1
    ;;
esac

: "${VOICE_MOCK_TELEPHONY_TARGET_WS_URL:?VOICE_MOCK_TELEPHONY_TARGET_WS_URL is required}"
: "${VOICE_STREAM_WS_AUTH_TOKEN:?VOICE_STREAM_WS_AUTH_TOKEN is required}"

PYTHON_BIN="${PYTHON_BIN:-${ROOT_DIR}/.venv/bin/python}"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

exec "${PYTHON_BIN}" "${ROOT_DIR}/tools/voice_mock_telephony/main.py" "$@"
