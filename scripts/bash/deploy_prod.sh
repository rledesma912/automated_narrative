#!/usr/bin/env bash
# deploy_prod.sh — pase a producción (Spec-520).
#
# Producción cambia solo acá: construye las imágenes desde `main` (código y
# config/ viajan dentro de la imagen) y las levanta con docker compose.
# Aborta sin tocar nada ante el primer problema.
#
#   make deploy         → validaciones + backup + build + verificación
#   make deploy-check   → solo las validaciones (1–4)
#
# Variables (para probar contra una copia): PROD_DB, BACKUP_ROOT, API_URL.
# DEPLOY_SKIP_GIT_CHECKS=1 saltea 1–3, y solo se acepta con --check.
set -euo pipefail

cd "$(dirname "$0")/../.."

PROD_DB="${PROD_DB:-data/prod/stories.db}"
BACKUP_ROOT="${BACKUP_ROOT:-data/prod}"
API_URL="${API_URL:-http://localhost:8010}"
CHECK_ONLY=0
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=1

step() { echo "▸ $*"; }
ok()   { echo "  ✓ $*"; }
fail() { echo "  ✗ $1" >&2; [[ -n "${2:-}" ]] && echo "    → $2" >&2; exit 1; }

if [[ "${DEPLOY_SKIP_GIT_CHECKS:-0}" == "1" && $CHECK_ONLY -eq 0 ]]; then
  fail "DEPLOY_SKIP_GIT_CHECKS solo se permite con --check" "Sacá la variable para desplegar."
fi

if [[ "${DEPLOY_SKIP_GIT_CHECKS:-0}" == "1" ]]; then
  step "1–3. Git: salteado (DEPLOY_SKIP_GIT_CHECKS, solo prueba)"
else
  step "1. Rama"
  branch="$(git rev-parse --abbrev-ref HEAD)"
  [[ "$branch" == "main" ]] || fail "No estás en main (estás en '$branch')." \
    "Mergeá a main y hacé: git checkout main && git pull --ff-only"
  ok "main"

  step "2. Cambios sin commitear"
  if [[ -n "$(git status --porcelain)" ]]; then
    git status --short >&2
    fail "Hay cambios sin commitear o archivos sin trackear: entrarían a la imagen." \
      "Commitealos o descartalos antes de desplegar."
  fi
  ok "árbol limpio"

  step "3. Al día con GitHub"
  git fetch -q origin main || fail "No se pudo consultar GitHub (git fetch)." "Revisá la conexión."
  local_sha="$(git rev-parse HEAD)"
  remote_sha="$(git rev-parse origin/main)"
  [[ "$local_sha" == "$remote_sha" ]] || fail \
    "main local (${local_sha:0:7}) no coincide con origin/main (${remote_sha:0:7})." \
    "Hacé git pull --ff-only (o push si faltan commits en GitHub)."
  ok "main = origin/main (${local_sha:0:7})"
fi

step "4. Generaciones en curso"
set +e
active="$(python3 scripts/prod_db.py active-jobs "$PROD_DB")"
code=$?
set -e
case $code in
  0) ok "ninguna" ;;
  1) fail "Hay $active generación(es) en curso en prod." "Esperá a que terminen y volvé a intentar." ;;
  2) fail "No existe la DB de prod ($PROD_DB)." "Revisá PROD_DB." ;;
  *) fail "No se pudo consultar la DB de prod ($PROD_DB)." ;;
esac

if [[ $CHECK_ONLY -eq 1 ]]; then
  echo "✅ Listo para desplegar (deploy-check: no se tocó nada)."
  exit 0
fi

commit="$(git rev-parse --short HEAD)"

step "5. Backup de la DB de prod"
backup_path="$(python3 scripts/prod_db.py backup "$PROD_DB" \
  "$BACKUP_ROOT/backup_$(date +%F)" "$(date +%H%M)-$commit")" \
  || fail "El backup falló: no se desplegó nada."
ok "$backup_path"

step "6. Build y arranque (docker compose up -d --build backend frontend)"
docker compose up -d --build backend frontend \
  || fail "Falló el build o el arranque." "Prod puede haber quedado con la versión anterior; revisá 'docker compose ps'. Backup: $backup_path"

step "7. Verificación"
healthy=0
for _ in $(seq 1 30); do
  if health="$(curl -fsS "$API_URL/api/v1/health" 2>/dev/null)"; then healthy=1; break; fi
  sleep 2
done
[[ $healthy -eq 1 ]] || fail "El backend no responde en $API_URL/api/v1/health." \
  "Revisá 'docker compose logs backend'. Backup: $backup_path"
profile="$(curl -fsS "$API_URL/api/v1/config/active-profile" | python3 -c 'import json,sys; print(json.load(sys.stdin)["active_profile"])')"
ok "health: $health"
ok "perfil activo: $profile"
ok "commit desplegado: $commit"
echo "✅ Producción actualizada a $commit. Backup: $backup_path"
