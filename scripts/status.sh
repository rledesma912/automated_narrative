#!/bin/bash
# Ver estado de una historia

STORY_ID="${1:-}"

if [ -z "$STORY_ID" ]; then
    echo "❌ Uso: $0 <story_id>"
    exit 1
fi

echo "📋 Estado de historia: $STORY_ID"

curl -s "http://localhost:8010/api/v1/stories/$STORY_ID" | jq '.'

echo ""
echo "🎵 Beats:"

curl -s "http://localhost:8010/api/v1/stories/$STORY_ID/beats" | jq '.[] | "\(.number). \(.status) - \(.summary)"'