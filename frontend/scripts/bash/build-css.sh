#!/bin/bash

# ════════════════════════════════════════════════════════════════════════════
# Build CSS — Tailwind CLI Compiler
# ════════════════════════════════════════════════════════════════════════════
#
# Uso:
#   ./scripts/bash/build-css.sh          # Build una vez
#   ./scripts/bash/build-css.sh --watch  # Watch mode
#   ./scripts/bash/build-css.sh --minify # Production minified
#
# ════════════════════════════════════════════════════════════════════════════

set -e

FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INPUT_CSS="${FRONTEND_DIR}/src/styles/globals.css"
OUTPUT_CSS="${FRONTEND_DIR}/public/styles.css"
TAILWIND_CONFIG="${FRONTEND_DIR}/tailwind.config.js"

# Ensure output directory exists
mkdir -p "$(dirname "${OUTPUT_CSS}")"

# Determine flags based on arguments
FLAGS=""
if [[ "$1" == "--watch" ]]; then
  FLAGS="--watch"
  echo "🔍 Starting CSS watcher..."
elif [[ "$1" == "--minify" ]]; then
  FLAGS="--minify"
  echo "📦 Building minified CSS..."
else
  echo "🔨 Building CSS..."
fi

# Run Tailwind CLI
cd "${FRONTEND_DIR}"
npx tailwindcss \
  -i "${INPUT_CSS}" \
  -o "${OUTPUT_CSS}" \
  -c "${TAILWIND_CONFIG}" \
  ${FLAGS}

if [ $? -eq 0 ]; then
  echo "✅ CSS build successful at ${OUTPUT_CSS}"
  ls -lh "${OUTPUT_CSS}"
else
  echo "❌ CSS build failed"
  exit 1
fi
