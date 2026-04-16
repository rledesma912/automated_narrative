#!/bin/bash
# Script para generar solo el plan (beats) de una historia

set -e

cd "$(dirname "$0")/../.."

TITLE="${1:-}"
BEATS="${2:-10}"

if [[ -z "$TITLE" ]]; then
    echo "Uso: $0 \"Título\" [beats]"
    echo "Ejemplo: $0 \"Mi Historia\" 8"
    exit 1
fi

PYTHONPATH=. uv run python -m src plan --title "$TITLE" --beats $BEATS --mock