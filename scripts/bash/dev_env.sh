#!/usr/bin/env bash
# dev_env.sh — entorno DEV siempre levantado (Spec-540).
#
# Dev corre en contenedores propios (docker-compose.dev.yml, proyecto
# `narrative-dev`) con el código del directorio de trabajo montado: cada cambio
# se ve recargando la página. Detrás de nginx: storymaker.test → :3040.
#
#   make dev-up       → construye si hace falta, levanta y verifica
#   make dev-down     → baja los contenedores de dev
#   make dev-rebuild  → reconstruye las imágenes (dependencias nuevas) y levanta
#   make dev-status   → rama, commit, contenedores, /health y UI (≠ 0 si algo falla)
#   make dev-logs     → últimas líneas de api y ui
#   make dev-db       → recrea data/dev/stories.db vacía con los catálogos y la verifica
#
# Nunca toca prod: ni docker-compose.yml, ni data/prod/, ni .env.prod.
set -euo pipefail

cd "$(dirname "$0")/../.."

COMPOSE=(docker compose -f docker-compose.dev.yml)
API_URL="http://localhost:8040"
UI_URL="http://localhost:3040"
DB="data/dev/stories.db"

export DEV_UID="${DEV_UID:-$(id -u)}"
export DEV_GID="${DEV_GID:-$(id -g)}"

step() { echo "▸ $*"; }
ok()   { echo "  ✓ $*"; }
fail() { echo "  ✗ $1" >&2; [[ -n "${2:-}" ]] && echo "    → $2" >&2; return 1; }

wait_healthy() {
  local i
  for i in $(seq 1 30); do
    curl -fsS -o /dev/null "$API_URL/api/v1/health" 2>/dev/null \
      && curl -fsS -o /dev/null "$UI_URL/" 2>/dev/null && return 0
    sleep 2
  done
  return 1
}

# init_db() dentro del contenedor + verificación: catálogos con datos, 0 historias.
init_and_verify_db() {
  "${COMPOSE[@]}" run --rm --no-deps -T api .venv/bin/python - <<'PY'
import asyncio, sqlite3, sys
from src.infrastructure.database.connection import init_db

asyncio.run(init_db())
con = sqlite3.connect("data/dev/stories.db")
count = lambda t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
catalogs = {t: count(t) for t in ("genre", "subgenre", "entity_nature", "genre_entity_nature")}
stories = count("story")
for t, n in catalogs.items():
    print(f"  {t}: {n}")
print(f"  story: {stories}")
empty = [t for t, n in catalogs.items() if n == 0]
if empty or stories:
    sys.exit(f"  ✗ catálogos vacíos: {empty}" if empty else f"  ✗ quedaron {stories} historias")
PY
}

cmd_up() {
  mkdir -p data/dev frontend/public/output_stories
  if [[ ! -s "$DB" ]]; then
    step "No hay $DB: se crea vacía con los catálogos"
    init_and_verify_db
  fi
  step "Levantando dev (narrative-dev)"
  "${COMPOSE[@]}" up -d "$@"
  step "Esperando api y ui"
  wait_healthy || { fail "dev no respondió en 60 s" "make dev-logs"; exit 1; }
  cmd_status
}

cmd_status() {
  local branch commit dirty rc=0 html
  branch=$(git rev-parse --abbrev-ref HEAD)
  commit=$(git rev-parse --short HEAD)
  dirty=$(git status --porcelain | wc -l)
  echo "▸ Dev: storymaker.test → $UI_URL  (API $API_URL)"
  echo "  rama $branch · commit $commit$([[ $dirty -gt 0 ]] && echo " · $dirty archivo(s) sin commitear")"
  "${COMPOSE[@]}" ps --format '  {{.Name}}: {{.Status}}'
  if curl -fsS -o /dev/null "$API_URL/api/v1/health"; then ok "API /health"; else fail "API /health no responde" "make dev-logs" || rc=1; fi
  if html=$(curl -fsS "$UI_URL/"); then
    if grep -q 'data-env="dev"' <<<"$html"; then ok "UI en modo dev"; else fail "la UI responde pero no está en modo dev (ENV)" || rc=1; fi
    grep -q "$commit" <<<"$html" && ok "UI muestra el commit $commit" || fail "la UI no muestra el commit $commit" || rc=1
  else
    fail "UI no responde" "make dev-logs" || rc=1
  fi
  return $rc
}

cmd_db() {
  local stories=0
  [[ -s "$DB" ]] && stories=$(python3 -c 'import sqlite3, sys; print(sqlite3.connect(sys.argv[1]).execute("SELECT COUNT(*) FROM story").fetchone()[0])' "$DB" 2>/dev/null || echo 0)
  if [[ "$stories" -gt 0 && "${1:-}" != "--yes" ]]; then
    fail "$DB tiene $stories historia(s)" "Para borrarlas: make dev-db ARGS=--yes (o dev_env.sh db --yes)"
    exit 1
  fi
  step "Recreando $DB (había $stories historia(s))"
  "${COMPOSE[@]}" stop api >/dev/null 2>&1 || true
  rm -f "$DB" "$DB-wal" "$DB-shm"
  mkdir -p data/dev
  init_and_verify_db
  ok "DB vacía con los catálogos"
  if "${COMPOSE[@]}" ps -a --format '{{.Name}}' | grep -q narrative-api-dev; then
    "${COMPOSE[@]}" start api >/dev/null
    ok "API de dev levantada de nuevo"
  fi
}

case "${1:-}" in
  up)      shift; cmd_up "$@" ;;
  down)    "${COMPOSE[@]}" down ;;
  rebuild) "${COMPOSE[@]}" build && cmd_up --force-recreate ;;
  status)  cmd_status ;;
  logs)    "${COMPOSE[@]}" logs --tail "${2:-60}" ;;
  db)      shift; cmd_db "$@" ;;
  *)       echo "uso: $0 up|down|rebuild|status|logs [n]|db [--yes]" >&2; exit 2 ;;
esac
