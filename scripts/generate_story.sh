#!/bin/bash
# Generar historia completa (plan + todos los beats)

cd "$(dirname "$0")/.."

STORY_ID="${1:-}"

if [ -z "$STORY_ID" ]; then
    echo "❌ Uso: $0 <story_id>"
    exit 1
fi

echo "🎬 Generando historia completa: $STORY_ID"

curl -X POST "http://localhost:8010/api/v1/stories/$STORY_ID/plan" \
    -H "Content-Type: application/json" \
    -s | jq .

echo ""
echo "📖 Generando beats..."

BEATS=$(curl -s "http://localhost:8010/api/v1/stories/$STORY_ID/beats" | jq '. | length')

for i in $(seq 1 "$BEATS"); do
    echo "🎤 Generando beat $i/$BEATS..."
    curl -X POST "http://localhost:8010/api/v1/stories/$STORY_ID/beats/$i" \
        -H "Content-Type: application/json" \
        -s | jq -c '.'
done

echo ""
echo "✅ Historia completa!"
echo "📥 Exportar: curl http://localhost:8010/api/v1/stories/$STORY_ID/export"