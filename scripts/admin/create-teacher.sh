#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

if [[ $# -ne 3 ]]; then
  log_error "用法: ./create_teacher.sh <phone> <name> <password>"
  exit 1
fi

PYTHON_BIN="$(require_python_bin)"
PHONE="$1"
NAME="$2"
PASSWORD="$3"

cd "$ROOT_DIR"
exec env PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" backend/scripts/create_teacher.py "$PHONE" "$NAME" "$PASSWORD"
