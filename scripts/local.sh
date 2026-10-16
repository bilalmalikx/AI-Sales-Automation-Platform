#!/usr/bin/env bash
# Local Codelps lifecycle. No data volumes are deleted by any command.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE="$ROOT/.local"
mkdir -p "$STATE"
chmod 700 "$STATE"
cd "$ROOT/backend"
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.live.yml -f docker-compose.delivery.yml)

frontend_pid() {
  local pid cwd command
  pid="$(lsof -t -nP -iTCP:4202 -sTCP:LISTEN 2>/dev/null | head -1 || true)"
  [[ -n "$pid" ]] || return 1
  cwd="$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')"
  command="$(ps -p "$pid" -o args=)"
  if [[ "$cwd" == "$ROOT/frontend" && ( "$command" == *"ng serve"* || "$command" == *"@angular/cli/bin/ng.js"* ) ]]; then
    printf '%s' "$pid"
  else
    return 1
  fi
}

backup() {
  local target
  mkdir -p "$STATE/backups"
  target="$STATE/backups/salesway-$(date -u +%Y%m%dT%H%M%SZ)-$$.dump"
  (umask 077; "${COMPOSE[@]}" exec -T postgres pg_dump -U salesway -d salesway --format=custom > "$target.partial")
  mv "$target.partial" "$target"
  printf 'Database backup: %s\n' "$target"
}

case "${1:-status}" in
  start)
    "${COMPOSE[@]}" up -d --wait postgres redis
    backup
    "${COMPOSE[@]}" up -d --build
    if frontend_pid >/dev/null; then
      printf 'Reusing this project frontend on port 4202.\n'
    else
      if lsof -nP -iTCP:4202 -sTCP:LISTEN >/dev/null 2>&1; then
        printf 'Port 4202 belongs to another process. Backend started; free that port before starting this frontend.\n' >&2
        exit 1
      fi
      NODE_BIN="${SALESWAY_NODE_BIN:-$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node}"
      [[ -x "$NODE_BIN" ]] || NODE_BIN="$(command -v node)"
      [[ -d "$ROOT/frontend/node_modules" ]] || { printf 'Run npm ci in frontend first.\n' >&2; exit 1; }
      cd "$ROOT/frontend"
      nohup "$NODE_BIN" node_modules/@angular/cli/bin/ng.js serve --configuration local --host localhost --port 4202 > "$STATE/frontend.log" 2>&1 &
    fi
    for attempt in $(seq 1 30); do
      if curl -fsS http://localhost:8002/health/ready >/dev/null 2>&1 && curl -fsS http://localhost:4202/ >/dev/null 2>&1; then
        printf 'Ready: http://localhost:4202/#/discovery\n'; exit 0
      fi
      sleep 2
    done
    printf 'Startup did not become ready in 60 seconds. Check .local/frontend.log and docker compose logs.\n' >&2
    exit 1
    ;;
  stop)
    if pid="$(frontend_pid)"; then kill -TERM "$pid"; fi
    "${COMPOSE[@]}" stop
    ;;
  status)
    "${COMPOSE[@]}" ps
    curl -fsS http://localhost:8002/health/ready
    printf '\n'
    curl -fsS -o /dev/null -w 'Frontend HTTP %{http_code}\n' http://localhost:4202/
    ;;
  backup) backup ;;
  *) printf 'Usage: bash scripts/local.sh start|stop|status|backup\n' >&2; exit 2 ;;
esac
