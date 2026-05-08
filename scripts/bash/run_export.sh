#!/bin/bash
# Script para exportar una historia a YAML canónico
# Uso: ./run_export.sh <story-id> [output-path]
# Ejemplo: ./run_export.sh feba722b-dc89-4009-9764-98ac4207696b

set -e

cd "$(dirname "$0")/../.."

STORY_ID="${1:-}"
OUTPUT_PATH="${2:-}"

if [[ -z "$STORY_ID" ]]; then
    echo "Uso: $0 <story-id> [output-path]"
    echo "Ejemplo: $0 feba722b-dc89-4009-9764-98ac4207696b input_stories/barco_fantasmo.yaml"
    echo ""
    echo "Para obtener los story-id disponibles, ejecuta: make list"
    exit 1
fi

if [[ -n "$OUTPUT_PATH" ]]; then
    PYTHONPATH=. uv run python -m src export-yaml "$STORY_ID" --output "$OUTPUT_PATH"
else
    PYTHONPATH=. uv run python -m src export-yaml "$STORY_ID"
fi