#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

cd "$ROOT_DIR"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  log_error "未找到 docker compose / docker-compose，请先安装 Docker Desktop 或 Docker Compose"
  exit 1
fi

log_info "启动基础依赖服务..."
"${COMPOSE_CMD[@]}" up -d
"${COMPOSE_CMD[@]}" ps
