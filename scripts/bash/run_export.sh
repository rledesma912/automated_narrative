#!/bin/bash
# Script para exportar una historia a Markdown

set -e

cd "$(dirname "$0")/../.."

STORY_ID="${1:-}"
OUTPUT_DIR="${2:-output_stories}"

if [[ -z "$STORY_ID" ]]; then
    echo "Uso: $0 <story-id> [output-dir]"
    echo "Ejemplo: $0 12345-abcde output"
    exit 1
fi

PYTHONPATH=. uv run python -m src export --story-id "$STORY_ID" --format markdown --output "$OUTPUT_DIR"