#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

PYTHON_BIN="$(require_python_bin)"

cd "$ROOT_DIR/backend"

HOST="$("$PYTHON_BIN" - <<'PY'
from app.core.config import settings
print(settings.BACKEND_HOST or "127.0.0.1")
PY
)"

PORT="$("$PYTHON_BIN" - <<'PY'
from app.core.config import settings
print(settings.BACKEND_PORT or 8000)
PY
)"

PORT="${PORT:-9008}"
RELOAD_ARGS=()
if [[ "${BACKEND_RELOAD:-1}" != "0" ]]; then
  RELOAD_ARGS+=(--reload)
fi

if [[ ${#RELOAD_ARGS[@]} -gt 0 ]]; then
  exec "$PYTHON_BIN" -m uvicorn app.main:app "${RELOAD_ARGS[@]}" --host "$HOST" --port "$PORT"
else
  exec "$PYTHON_BIN" -m uvicorn app.main:app --host "$HOST" --port "$PORT"
fi
