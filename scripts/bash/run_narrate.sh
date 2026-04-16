#!/bin/bash
# Script para narrar beats específicos de una historia

set -e

cd "$(dirname "$0")/../.."

STORY_ID="${1:-}"
BEATS="${2:-}"

if [[ -z "$STORY_ID" ]] || [[ -z "$BEATS" ]]; then
    echo "Uso: $0 <story-id> <beats>"
    echo "Ejemplo: $0 12345-abcde 1,2,3"
    exit 1
fi

PYTHONPATH=. uv run python -m src narrate --story-id "$STORY_ID" --beats "$BEATS"