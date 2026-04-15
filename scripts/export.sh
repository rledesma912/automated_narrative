#!/bin/bash
# Exportar historia a Markdown

STORY_ID="${1:-}"

if [ -z "$STORY_ID" ]; then
    echo "❌ Uso: $0 <story_id> [output_file.md]"
    exit 1
fi

OUTPUT="${2:-/dev/stdout}"

echo "📥 Exportando a Markdown..."

if [ "$OUTPUT" = "/dev/stdout" ]; then
    curl -s "http://localhost:8010/api/v1/stories/$STORY_ID/export"
else
    curl -s "http://localhost:8010/api/v1/stories/$STORY_ID/export" > "$OUTPUT"
    echo "✅ Guardado en: $OUTPUT"
fi